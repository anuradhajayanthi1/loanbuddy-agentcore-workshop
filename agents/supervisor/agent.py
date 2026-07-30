"""LoanBuddy supervisor - the loan officer.

The only agent the applicant ever talks to. Owns the conversation, the
application ledger, and Memory. Delegates document work and credit work to
specialists it discovers as tools through the AgentCore Gateway.

Labs light this file up progressively via environment variables:
  Lab 1: deployed bare       (no MEMORY_ID, no GATEWAY_URL)
  Lab 2: + MEMORY_ID         (AgentCore Memory: facts + session summaries)
  Lab 3: + GATEWAY_URL/GATEWAY_PROVIDER_NAME (tools over MCP, OAuth outbound)
"""
import base64
import json
import logging

from bedrock_agentcore.identity.auth import requires_access_token
from bedrock_agentcore.memory.client import MemoryClient
from bedrock_agentcore.memory.integrations.strands.config import (
    AgentCoreMemoryConfig,
    RetrievalConfig,
)
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.tools.mcp import MCPClient

import tools
from config import CFG
from prompts import LOAN_OFFICER_PROMPT, NO_MEMORY_ADDENDUM

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("supervisor")

app = BedrockAgentCoreApp()

FACTS_NAMESPACE = "/applicants/{actorId}/facts"
SUMMARY_NAMESPACE = "/applicants/{actorId}/sessions/{sessionId}"


# ---------------------------------------------------------------------------
# Identity: the applicant IS the validated JWT's sub claim.
# ---------------------------------------------------------------------------

def applicant_from_request(context) -> str:
    """Extract the applicant id from the JWT the Runtime already validated.

    The Runtime's JWT authorizer rejects unauthenticated calls before this
    code runs, so decoding without re-verifying the signature here is safe -
    we are reading a claim from a token that has already been verified at the
    front door. (For Lab 1's IAM-auth CLI smoke test there is no bearer
    token; we fall back to a fixed test actor.)
    """
    headers = context.request_headers or {}
    auth = headers.get("Authorization") or headers.get("authorization") or ""
    if auth.startswith("Bearer "):
        payload_b64 = auth.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        claims = json.loads(base64.b64decode(payload_b64))
        return claims["sub"]
    return "cli-test-user"


# ---------------------------------------------------------------------------
# Lab 3: outbound Identity - fetch an OAuth token for the Gateway.
# The client secret lives in the Identity token vault. It is NOWHERE in this
# code, this container, or this repo. Grep all you like.
# ---------------------------------------------------------------------------

def gateway_access_token() -> str:
    @requires_access_token(
        provider_name=CFG.gateway_provider_name,
        scopes=[CFG.gateway_scope],
        auth_flow="M2M",
    )
    def _with_token(*, access_token: str) -> str:
        return access_token

    return _with_token()


def open_gateway_client() -> MCPClient:
    token = gateway_access_token()
    return MCPClient(
        lambda: streamablehttp_client(
            CFG.gateway_url,
            headers={"Authorization": f"Bearer {token}"},
        )
    )


# ---------------------------------------------------------------------------
# Lab 2: Memory - facts survive forever, summaries are per-session.
# ---------------------------------------------------------------------------

def build_session_manager(actor_id: str, session_id: str) -> AgentCoreMemorySessionManager:
    return AgentCoreMemorySessionManager(
        AgentCoreMemoryConfig(
            memory_id=CFG.memory_id,
            actor_id=actor_id,
            session_id=session_id,
            retrieval_config={
                FACTS_NAMESPACE: RetrievalConfig(
                    top_k=10,
                    relevance_score=0.3,
                    initialization_query="loan application applicant profile and preferences",
                ),
            },
        ),
        region_name=CFG.region,
    )


def previous_session_summary(actor_id: str) -> str | None:
    """Fetch the summary of the applicant's PREVIOUS sitting.

    The summary namespace contains the old session id, which a fresh session
    cannot know - so the ledger records last_session_id (see tools.record_
    session). Ledger and Memory referencing each other is the point: ledger
    is ground truth, Memory is continuity.
    """
    last = tools.get_last_session_id()
    if not last:
        return None
    client = MemoryClient(region_name=CFG.region)
    namespace = f"/applicants/{actor_id}/sessions/{last}"
    records = client.retrieve_memories(
        memory_id=CFG.memory_id, namespace=namespace,
        query="loan application progress", top_k=3,
    )
    texts = [r.get("content", {}).get("text", "") for r in records]
    return "\n".join(t for t in texts if t) or None


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

@app.entrypoint
def invoke(payload, context):
    prompt = payload.get("prompt", "")
    actor_id = applicant_from_request(context)
    session_id = context.session_id or "local-dev-session"
    tools.CURRENT_APPLICANT.set(actor_id)
    log.info("turn: actor=%s session=%s", actor_id, session_id)

    local_tools = [
        tools.get_or_create_application,
        tools.update_intake,
        tools.set_status,
        tools.request_upload_url,
    ]

    system_prompt = LOAN_OFFICER_PROMPT
    if not CFG.memory_enabled:
        # Lab 1 state: no recollection, so no "welcome back" theater. The
        # resume behavior in step 1 unlocks with Memory in Lab 2.
        system_prompt += NO_MEMORY_ADDENDUM
    session_manager = None
    if CFG.memory_enabled:
        session_manager = build_session_manager(actor_id, session_id)
        summary = previous_session_summary(actor_id)
        if summary:
            system_prompt += (
                "\n\n## Where you left off with this applicant last time\n"
                + summary
            )
        tools.record_session(session_id)

    def run(agent_tools):
        agent = Agent(
            model=CFG.model_id,
            system_prompt=system_prompt,
            tools=agent_tools,
            session_manager=session_manager,
        )
        return str(agent(prompt))

    if CFG.gateway_enabled:
        gateway = open_gateway_client()
        with gateway:
            gateway_tools = gateway.list_tools_sync()
            log.info("gateway tools: %s", [t.tool_name for t in gateway_tools])
            return run(local_tools + gateway_tools)
    return run(local_tools)


if __name__ == "__main__":
    app.run()
