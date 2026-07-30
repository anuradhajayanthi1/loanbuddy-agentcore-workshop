"""Credit Analyst - an agent deployed as an MCP server on AgentCore Runtime.

Both a Gateway TARGET (the supervisor calls assess_credit through the
Gateway) and a Gateway CLIENT (it calls get_credit_report through that same
Gateway, with its own OAuth credential). Each leg authenticates separately.

Boundary facts worth grepping for:
  - No S3 access: this agent physically cannot read documents.
  - The supervisor has no Experian access: raw bureau data never enters the
    conversation context, no matter what the model is talked into.
  - Returns the ASSESSMENT (interpretation), never the raw report.
"""
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import boto3
import uvicorn
from bedrock_agentcore.identity.auth import requires_access_token
from bedrock_agentcore.runtime.context import BedrockAgentCoreContext
from mcp.client.streamable_http import streamablehttp_client
from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from strands.tools.mcp import MCPClient

from config import CFG
from policy import apply_policy, representative_rate
from underwriting import run_underwriting

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("credit-analyst")

mcp = FastMCP(
    "loanbuddy-credit-analyst",
    instructions="Credit assessment and underwriting for loan applications.",
    host="0.0.0.0",
    port=8000,
    stateless_http=True,
)

_ddb = boto3.resource("dynamodb", region_name=CFG.region)
_table = _ddb.Table(CFG.table_name)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_ddb(obj: Any) -> Any:
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _to_ddb(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_ddb(v) for v in obj]
    return obj


def _plain(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_plain(v) for v in obj]
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj


# ---------------------------------------------------------------------------
# Gateway client leg: this agent's OWN OAuth token, from its OWN provider.
#
# The Runtime sends this agent's workload identity token in the
# WorkloadAccessToken header. BedrockAgentCoreApp does this bookkeeping for
# HTTP-protocol agents; MCP servers run bare, so middleware (below) captures
# the header, and we hand it to the Identity SDK here IN THE TOOL'S OWN task
# (FastMCP executes tools in the session manager's task group, so a
# ContextVar set in middleware would not be visible there).
# ---------------------------------------------------------------------------

_workload_token: str | None = None  # one request at a time per microVM


def _resolve_workload_token() -> str | None:
    """The Runtime injects the WorkloadAccessToken header only for
    JWT-authorized inbound calls. This runtime is IAM-authed (only the
    Gateway's role may invoke it), so we bootstrap our workload identity
    token from the Identity data plane instead - permitted by this agent's
    execution role (bedrock-agentcore:GetWorkloadAccessToken)."""
    if _workload_token:
        return _workload_token
    workload_name = os.environ.get("WORKLOAD_NAME", "")
    if not workload_name:
        return None
    from bedrock_agentcore.services.identity import IdentityClient
    resp = IdentityClient(region=CFG.region).get_workload_access_token(workload_name)
    return resp["workloadAccessToken"]


def _gateway_token() -> str:
    token = _resolve_workload_token()
    if token:
        BedrockAgentCoreContext.set_workload_access_token(token)

    @requires_access_token(
        provider_name=CFG.gateway_provider_name,
        scopes=[CFG.gateway_scope],
        auth_flow="M2M",
    )
    def _with_token(*, access_token: str) -> str:
        return access_token

    return _with_token()


def _pull_credit_report(full_name: str) -> dict:
    """Call get_credit_report via the Gateway (which holds the Experian API
    key as a target credential - the key never touches this process)."""
    client = MCPClient(
        lambda: streamablehttp_client(
            CFG.gateway_url,
            headers={"Authorization": f"Bearer {_gateway_token()}"},
        )
    )
    with client:
        tools = client.list_tools_sync()
        name = next(
            (t.tool_name for t in tools if t.tool_name.endswith("get_credit_report")),
            None,
        )
        if name is None:
            raise RuntimeError(
                "get_credit_report is not in the gateway catalog. "
                "Is the experian-mock target registered (Lab 3)?")
        result = client.call_tool_sync(
            tool_use_id="credit-pull", name=name,
            arguments={"full_name": full_name},
        )
        text = result["content"][0]["text"]
        return json.loads(text)


# ---------------------------------------------------------------------------
# The tool
# ---------------------------------------------------------------------------

@mcp.tool()
def assess_credit(applicant_id: str, requested_amount: float,
                  term_months: int = 36) -> dict:
    """Assess an applicant's credit for a requested loan. Pulls a bureau
    report (re-using one fresher than 30 days), applies lending policy
    (tier, rate band, cap), runs underwriting math (income normalization,
    DTI, affordability, payment scenarios at 24/36/48 months), records the
    assessment on the ledger, and returns it.

    Requires an ACCEPTED government_id (the pull uses the verified name, not
    chat input) and a bank statement analysis for income verification.
    """
    resp = _table.get_item(Key={"applicant_id": applicant_id})
    app = _plain(resp.get("Item") or {})
    if not app:
        return {"error": "No application ledger record for this applicant."}

    docs = app.get("documents", {})
    id_doc = docs.get("government_id", {})
    if id_doc.get("status") != "ACCEPTED":
        return {"error": "Cannot assess credit before an accepted government ID. "
                         "The credit pull must use verified identity, not chat input."}
    verified_name = id_doc.get("extracted", {}).get("full_name", "")

    stmt = docs.get("bank_statement", {})
    stmt_x = stmt.get("extracted", {})
    if not stmt_x.get("recurring_deposit_amount"):
        return {"error": "Cannot underwrite without an analyzed bank statement "
                         "showing income deposits."}

    # --- Credit pull (with freshness reuse) ---
    credit = app.get("credit", {})
    pulled_at = credit.get("pulled_at")
    fresh = False
    if pulled_at:
        age = _now() - datetime.fromisoformat(pulled_at)
        fresh = age < timedelta(days=CFG.credit_freshness_days)
    if fresh:
        report = credit["report"]
        log.info("re-using credit report from %s (fresh)", pulled_at)
    else:
        report = _pull_credit_report(verified_name)
        log.info("pulled fresh credit report: score=%s", report.get("score"))

    # --- Policy: plain code ---
    policy = apply_policy(report)
    if policy["tier"] == "DECLINE":
        assessment = {**policy, "max_affordable": 0, "scenarios": [],
                      "assessed_at": _now().isoformat(timespec="seconds")}
    else:
        # --- Heuristics: Code Interpreter sandbox ---
        period_days = 90
        try:
            start = datetime.strptime(stmt_x["period_start"], "%m/%d/%Y")
            end = datetime.strptime(stmt_x["period_end"], "%m/%d/%Y")
            period_days = max((end - start).days, 1)
        except (KeyError, ValueError):
            pass
        uw = run_underwriting(
            requested_amount=requested_amount,
            term_months=term_months,
            annual_rate=representative_rate(policy["rate_band"]),
            stated_annual_income=app.get("intake", {}).get("stated_annual_income"),
            net_deposit_amount=stmt_x["recurring_deposit_amount"],
            deposit_count=stmt_x.get("recurring_deposit_count", 6),
            period_days=period_days,
            monthly_obligations=report.get("monthly_obligations", 0),
        )
        assessment = {
            **policy,
            "monthly_income_estimate": uw.monthly_income_estimate,
            "dti": uw.dti,
            "max_affordable": min(uw.max_affordable, policy["policy_cap"]),
            "scenarios": [s.model_dump() for s in uw.scenarios],
            "notes": uw.notes,
            "assessed_at": _now().isoformat(timespec="seconds"),
        }

    # --- Persist: score summary + assessment; raw report stays server-side ---
    _table.update_item(
        Key={"applicant_id": applicant_id},
        UpdateExpression="SET credit = :c, updated_at = :t",
        ExpressionAttributeValues={
            ":c": _to_ddb({
                "score": report.get("score"),
                "pulled_at": pulled_at if fresh else _now().isoformat(timespec="seconds"),
                "report": report,
                "assessment": assessment,
            }),
            ":t": _now().isoformat(timespec="seconds"),
        },
    )
    return assessment


class WorkloadTokenMiddleware(BaseHTTPMiddleware):
    """Capture the WorkloadAccessToken header the Runtime sends with every
    request; _gateway_token() hands it to the Identity SDK at fetch time.
    Without it, requires_access_token cannot prove WHO this workload is."""

    async def dispatch(self, request, call_next):
        global _workload_token
        token = request.headers.get("WorkloadAccessToken")
        if token:
            _workload_token = token
        else:  # diagnostic: what DID we get? (names only, never values)
            log.info("no WorkloadAccessToken; header names: %s",
                     sorted(request.headers.keys()))
        return await call_next(request)


if __name__ == "__main__":
    app = mcp.streamable_http_app()
    app.add_middleware(WorkloadTokenMiddleware)
    uvicorn.run(app, host="0.0.0.0", port=8000)
