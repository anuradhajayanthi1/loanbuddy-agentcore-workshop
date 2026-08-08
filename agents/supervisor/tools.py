# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Supervisor's local tools: the DDB application ledger + presigned uploads.

These are LOCAL Strands tools, compiled into the agent. Contrast with the
Gateway tools (analyze_document, check_docs_complete, assess_credit) which
the supervisor discovers over MCP in Lab 3+. The workshop teaches both kinds
side by side.

The applicant identity is NEVER a tool argument the model controls - it is
set per-request from the validated JWT (see agent.py) via a ContextVar, so a
prompt-injected "look up applicant alice" has nothing to grab onto.
"""
import contextvars
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.config import Config as BotoConfig
from strands import tool

from config import CFG

# Set by the entrypoint from the validated JWT before each turn.
CURRENT_APPLICANT: contextvars.ContextVar[str] = contextvars.ContextVar("applicant")

_ddb = boto3.resource("dynamodb", region_name=CFG.region)
_table = _ddb.Table(CFG.table_name)
# SigV4 explicitly: presigned URLs then carry X-Amz-Signature, which is what
# the chat UI's upload detection looks for (SigV2-style URLs vary by runtime).
_s3 = boto3.client("s3", region_name=CFG.region,
                   config=BotoConfig(signature_version="s3v4"))

REQUIRED_DOCS = ["government_id", "paystub", "bank_statement"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _applicant() -> str:
    return CURRENT_APPLICANT.get()


@tool
def get_or_create_application() -> dict[str, Any]:
    """Load this applicant's loan application ledger record, creating a fresh
    one (status STARTED) if this is their first conversation. Call this first
    in every conversation to know where the application stands."""
    applicant_id = _applicant()
    resp = _table.get_item(Key={"applicant_id": applicant_id})
    item = resp.get("Item", {})
    # Initialize (or HEAL) the record. Healing matters: other writers touch
    # this item with upserting UpdateItems, which can create a bare record -
    # nested SET expressions like documents.#d then fail on the missing map.
    defaults = {
        "applicant_id": applicant_id,
        "status": "STARTED",
        "created_at": _now(),
        "loan_type": "personal",
        "intake": {},
        "documents": {d: {"status": "MISSING"} for d in REQUIRED_DOCS},
        "credit": {},
    }
    missing = {k: v for k, v in defaults.items() if k not in item}
    if missing:
        item = {**defaults, **item, "applicant_id": applicant_id}
        _table.put_item(Item=item)
    # Serialize Decimals etc. into plain strings for the model.
    return _plain(item)


@tool
def update_intake(full_name: str | None = None,
                  requested_amount: int | None = None,
                  loan_purpose: str | None = None,
                  stated_annual_income: int | None = None,
                  employer_name: str | None = None,
                  preferred_term_months: int | None = None) -> str:
    """Record intake details on the application ledger as the applicant
    provides them. Pass only the fields you learned; others are preserved."""
    updates = {k: v for k, v in {
        "full_name": full_name,
        "requested_amount": requested_amount,
        "loan_purpose": loan_purpose,
        "stated_annual_income": stated_annual_income,
        "employer_name": employer_name,
        "preferred_term_months": preferred_term_months,
    }.items() if v is not None}
    if not updates:
        return "Nothing to record."
    expr = ", ".join(f"intake.#k{i} = :v{i}" for i in range(len(updates)))
    names = {f"#k{i}": k for i, k in enumerate(updates)}
    values = {f":v{i}": v for i, v in enumerate(updates.values())}
    values[":t"] = _now()
    _table.update_item(
        Key={"applicant_id": _applicant()},
        UpdateExpression=f"SET {expr}, updated_at = :t",
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )
    return f"Recorded: {', '.join(updates)}."


@tool
def set_status(status: str) -> str:
    """Move the application to a new status. Allowed values: STARTED,
    DOCS_PENDING, UNDER_REVIEW, DECISION."""
    allowed = {"STARTED", "DOCS_PENDING", "UNDER_REVIEW", "DECISION"}
    if status not in allowed:
        return f"Invalid status {status!r}. Allowed: {sorted(allowed)}"
    _table.update_item(
        Key={"applicant_id": _applicant()},
        UpdateExpression="SET #s = :s, updated_at = :t",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": status, ":t": _now()},
    )
    return f"Application status is now {status}."


@tool
def request_upload_url(doc_type: str) -> dict[str, str]:
    """Generate a presigned upload URL for a document the applicant needs to
    provide. doc_type must be one of: government_id, paystub, bank_statement.
    Returns the URL (give the UI this via your reply - the chat upload button
    uses it) and the S3 key to pass to analyze_document after upload."""
    if doc_type not in REQUIRED_DOCS:
        return {"error": f"Unknown doc_type {doc_type!r}. Use one of {REQUIRED_DOCS}."}
    key = f"docs/{_applicant()}/{doc_type}-{uuid.uuid4().hex[:8]}.png"
    url = _s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": CFG.docs_bucket, "Key": key, "ContentType": "image/png"},
        ExpiresIn=900,
    )
    return {"upload_url": url, "s3_key": key, "doc_type": doc_type}


def record_session(session_id: str) -> None:
    """Persist the current runtime session id on the ledger so the NEXT
    session can locate this session's memory summary namespace.
    (Called by the entrypoint, not by the model.)"""
    _table.update_item(
        Key={"applicant_id": _applicant()},
        UpdateExpression="SET last_session_id = :s, updated_at = :t",
        ExpressionAttributeValues={":s": session_id, ":t": _now()},
    )


def get_last_session_id() -> str | None:
    resp = _table.get_item(
        Key={"applicant_id": _applicant()},
        ProjectionExpression="last_session_id",
    )
    return resp.get("Item", {}).get("last_session_id")


def _plain(obj: Any) -> Any:
    """Convert DynamoDB Decimals to int/float for JSON-friendliness."""
    from decimal import Decimal
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_plain(v) for v in obj]
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj
