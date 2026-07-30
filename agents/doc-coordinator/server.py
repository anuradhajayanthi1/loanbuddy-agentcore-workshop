"""Doc Coordinator - an agent deployed as an MCP server on AgentCore Runtime.

From the supervisor's seat, this whole runtime is just two tools in the
Gateway catalog. That an entire multi-specialist agent sits behind
analyze_document is an implementation detail hidden by the tool boundary.

Returns FINDINGS, never documents: the supervisor (and therefore the
conversation context) never sees raw document bytes. Data minimization is
enforced by the tool contract and by IAM (only this agent's role can read
docs/*).
"""
import logging

from mcp.server.fastmcp import FastMCP

import ledger
from employer_check import verify_employer as _verify_employer
from specialists import DOC_SPECS, run_specialist

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("doc-coordinator")

# AgentCore Runtime (protocol MCP) expects a stateless streamable-HTTP MCP
# server on 0.0.0.0:8000 at /mcp.
mcp = FastMCP(
    "loanbuddy-doc-coordinator",
    instructions="Document collection and validation for loan applications.",
    host="0.0.0.0",
    port=8000,
    stateless_http=True,
)


@mcp.tool()
def analyze_document(applicant_id: str, s3_key: str, doc_type: str) -> dict:
    """Analyze an uploaded loan document. Fetches the document from S3,
    extracts structured fields, validates them against lending policy, and
    records the outcome on the application ledger.

    Args:
        applicant_id: The applicant this document belongs to.
        s3_key: S3 key of the uploaded document (from request_upload_url).
        doc_type: One of government_id, paystub, bank_statement.

    Returns findings only: status (ACCEPTED / NEEDS_RESUBMISSION /
    MISMATCH_FLAGGED), extracted fields, and any issues - never the document
    itself.
    """
    if doc_type not in DOC_SPECS:
        return {"error": f"Unknown doc_type {doc_type!r}. Known: {sorted(DOC_SPECS)}"}
    app = ledger.get_application(applicant_id)
    if app is None:
        return {"error": "No application ledger record for this applicant."}
    if not s3_key.startswith(f"docs/{applicant_id}/"):
        # Defense in depth; IAM scoping is the real boundary.
        return {"error": "Document key does not belong to this applicant."}

    log.info("analyze: applicant=%s type=%s key=%s", applicant_id, doc_type, s3_key)
    image = ledger.fetch_document(s3_key)
    extracted, issues = run_specialist(doc_type, image, app)

    employer_verification = None
    if doc_type == "paystub" and not issues:
        employer = extracted.get("employer_name", "")
        if employer:
            employer_verification = _verify_employer(employer)
            if employer_verification.get("skipped"):
                employer_verification = None
            elif not employer_verification.get("verified"):
                issues.append(
                    f"MISMATCH_FLAG: employer '{employer}' could not be "
                    f"verified in the state business registry.")

    if not issues:
        status = "ACCEPTED"
    elif any(i.startswith("MISMATCH_FLAG") for i in issues):
        status = "MISMATCH_FLAGGED"
    else:
        status = "NEEDS_RESUBMISSION"

    ledger.record_document(applicant_id, doc_type, status, s3_key,
                           extracted, issues, employer_verification)
    result = {"doc_type": doc_type, "status": status, "issues": issues,
              "extracted": extracted}
    if employer_verification:
        result["employer_verification"] = employer_verification
    return result


@mcp.tool()
def check_docs_complete(applicant_id: str) -> dict:
    """Report which documents this loan application still needs. Returns the
    gap between lending policy requirements and the ledger: accepted docs,
    missing docs, and docs needing resubmission (with reasons). Call this to
    decide what to ask the applicant for - never guess from conversation."""
    report = ledger.docs_gap_report(applicant_id)
    log.info("gap report: applicant=%s -> %s", applicant_id, report)
    return report


@mcp.tool()
def verify_employer(applicant_id: str, employer_name: str) -> dict:
    """Verify an employer exists in the state business registry (live browser
    check). Use when the applicant corrects or disputes their employer name.
    Returns found/status/registered_since and a verified verdict."""
    result = _verify_employer(employer_name)
    log.info("verify_employer: %s -> %s", employer_name, result)
    return result


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
