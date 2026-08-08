# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Doc Coordinator's view of the application ledger.

This agent's IAM role permits GetItem/UpdateItem on the applications table
and read-only access to docs/* in S3 - nothing else. It writes ONLY the
documents section; intake/credit belong to other principals.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3

from config import CFG

_ddb = boto3.resource("dynamodb", region_name=CFG.region)
_table = _ddb.Table(CFG.table_name)
_s3 = boto3.client("s3", region_name=CFG.region)

REQUIRED_DOCS = ["government_id", "paystub", "bank_statement"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _to_ddb(obj: Any) -> Any:
    """DynamoDB rejects floats; convert to Decimal recursively."""
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


def get_application(applicant_id: str) -> dict | None:
    resp = _table.get_item(Key={"applicant_id": applicant_id})
    item = resp.get("Item")
    return _plain(item) if item else None


def fetch_document(s3_key: str) -> bytes:
    obj = _s3.get_object(Bucket=CFG.docs_bucket, Key=s3_key)
    return obj["Body"].read()


def record_document(applicant_id: str, doc_type: str, status: str,
                    s3_key: str, extracted: dict, issues: list[str],
                    employer_verification: dict | None = None) -> None:
    entry: dict[str, Any] = {
        "status": status,
        "s3_key": s3_key,
        "extracted": extracted,
        "issues": issues,
        "analyzed_at": _now(),
    }
    if employer_verification is not None:
        entry["employer_verification"] = employer_verification
    # Ensure the documents map exists before the nested SET (a bare record
    # can exist if another writer upserted the item first).
    _table.update_item(
        Key={"applicant_id": applicant_id},
        UpdateExpression="SET documents = if_not_exists(documents, :empty)",
        ExpressionAttributeValues={":empty": {}},
    )
    _table.update_item(
        Key={"applicant_id": applicant_id},
        UpdateExpression="SET documents.#d = :e, updated_at = :t",
        ExpressionAttributeNames={"#d": doc_type},
        ExpressionAttributeValues={":e": _to_ddb(entry), ":t": _now()},
    )


def docs_gap_report(applicant_id: str) -> dict:
    """The checklist diff: required docs (by loan policy) vs ledger state."""
    app = get_application(applicant_id)
    if app is None:
        return {"error": "No application found for this applicant."}
    docs = app.get("documents", {})
    accepted, missing, needs_resubmission = [], [], []
    for doc in REQUIRED_DOCS:  # policy table: personal loans need all three
        entry = docs.get(doc, {"status": "MISSING"})
        status = entry.get("status", "MISSING")
        if status == "ACCEPTED":
            accepted.append(doc)
        elif status in ("NEEDS_RESUBMISSION", "MISMATCH_FLAGGED"):
            needs_resubmission.append({"doc": doc, "status": status,
                                       "issues": entry.get("issues", [])})
        else:
            missing.append(doc)
    return {
        "complete": not missing and not needs_resubmission,
        "accepted": accepted,
        "missing": missing,
        "needs_resubmission": needs_resubmission,
    }
