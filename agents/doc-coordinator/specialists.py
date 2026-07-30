"""Per-doc-type specialists: one agent per document type, in-process.

WHY ISN'T THIS FOUR SEPARATELY-DEPLOYED AGENTS?
The specialists share one trust domain (read docs, write doc metadata), one
reason to change (lending doc policy), and near-identical pipelines. Agents
encapsulate CAPABILITIES; parameters and registry entries encode VARIATIONS.
Adding a W-2 specialist here is a new spec entry + prompt - no new runtime,
role, or deploy. The Credit Analyst, by contrast, IS separately deployed:
different credentials (Experian), different reason to change (credit policy).

Each specialist is a small Strands agent with a focused persona that reads
the document image and returns structured findings. The validation RULES are
deliberately plain Python, not model judgment - policy must be reproducible.
"""
from datetime import date, datetime, timedelta

from pydantic import BaseModel, Field
from strands import Agent

from config import CFG


# ---------------------------------------------------------------------------
# Extraction schemas - what each specialist pulls off the page
# ---------------------------------------------------------------------------

class IdExtraction(BaseModel):
    looks_like_government_id: bool = Field(
        description="Is this a government ID by FORMAT (license/passport/state "
                    "ID layout)? Workshopia training specimens count as IDs - "
                    "judge the document type, not its authenticity.")
    full_name: str = ""
    date_of_birth: str = Field("", description="MM/DD/YYYY as printed")
    id_number: str = ""
    expiry_date: str = Field("", description="MM/DD/YYYY as printed")


class PaystubExtraction(BaseModel):
    looks_like_paystub: bool = Field(
        description="Is this a paystub by FORMAT (earnings statement layout)? "
                    "Workshopia training specimens count - judge document "
                    "type, not authenticity.")
    employee_name: str = ""
    employer_name: str = ""
    pay_date: str = Field("", description="MM/DD/YYYY as printed")
    pay_frequency: str = Field("", description="e.g. BIWEEKLY, MONTHLY")
    gross_pay: float = 0.0
    net_pay: float = 0.0


class StatementExtraction(BaseModel):
    looks_like_bank_statement: bool = Field(
        description="Is this a bank statement by FORMAT (account/period/"
                    "transactions layout)? Workshopia training specimens "
                    "count - judge document type, not authenticity.")
    account_holder: str = ""
    period_start: str = Field("", description="MM/DD/YYYY as printed")
    period_end: str = Field("", description="MM/DD/YYYY as printed")
    ending_balance: float = 0.0
    recurring_deposit_amount: float = Field(
        0.0, description="Typical amount of the recurring payroll-like deposit")
    recurring_deposit_source: str = Field(
        "", description="Payer name on the recurring deposit, as printed")
    recurring_deposit_count: int = Field(
        0, description="How many times the recurring deposit appears")


# ---------------------------------------------------------------------------
# Validation rules - plain code, on purpose
# ---------------------------------------------------------------------------

def _parse(d: str) -> date | None:
    try:
        return datetime.strptime(d, "%m/%d/%Y").date()
    except ValueError:
        return None


def _names_match(a: str, b: str) -> bool:
    """Forgiving name comparison: all tokens of the shorter name appear in
    the longer one, case-insensitively."""
    ta, tb = set(a.lower().split()), set(b.lower().split())
    if not ta or not tb:
        return False
    small, big = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    return small.issubset(big)


def validate_id(x: IdExtraction, applicant_name: str | None) -> list[str]:
    issues = []
    if not x.looks_like_government_id:
        return ["The uploaded file does not appear to be a government ID."]
    exp = _parse(x.expiry_date)
    if exp is None:
        issues.append("Could not read the expiry date on the ID.")
    elif exp < date.today():
        issues.append(f"ID expired on {x.expiry_date}.")
    if applicant_name and not _names_match(x.full_name, applicant_name):
        issues.append(
            f"Name on ID ({x.full_name}) does not match the applicant profile "
            f"({applicant_name}).")
    return issues


def validate_paystub(x: PaystubExtraction, stated_employer: str | None,
                     stated_annual_income: float | None) -> list[str]:
    issues = []
    if not x.looks_like_paystub:
        return ["The uploaded file does not appear to be a paystub."]
    pd = _parse(x.pay_date)
    if pd is None:
        issues.append("Could not read the pay date.")
    elif pd < date.today() - timedelta(days=30):
        issues.append(f"Paystub is dated {x.pay_date}; we need one from the last 30 days.")
    if stated_employer and not _names_match(x.employer_name, stated_employer):
        issues.append(
            f"MISMATCH_FLAG: employer on paystub ({x.employer_name}) differs "
            f"from stated employer ({stated_employer}).")
    if stated_annual_income and x.gross_pay:
        periods = {"BIWEEKLY": 26, "WEEKLY": 52, "MONTHLY": 12, "SEMIMONTHLY": 24}
        n = periods.get(x.pay_frequency.upper().replace("-", ""), 26)
        implied = x.gross_pay * n
        if abs(implied - stated_annual_income) / stated_annual_income > 0.25:
            issues.append(
                f"MISMATCH_FLAG: paystub implies ~${implied:,.0f}/yr gross but "
                f"applicant stated ${stated_annual_income:,.0f}/yr.")
    return issues


def validate_statement(x: StatementExtraction, applicant_name: str | None) -> list[str]:
    issues = []
    if not x.looks_like_bank_statement:
        return ["The uploaded file does not appear to be a bank statement."]
    start, end = _parse(x.period_start), _parse(x.period_end)
    if not start or not end:
        issues.append("Could not read the statement period dates.")
    else:
        covered = (end - start).days
        if covered < 85:  # 90 with a little print-date slack
            issues.append(
                f"Statement covers only {covered} days "
                f"({x.period_start} - {x.period_end}); we need the most recent 90 days.")
        if end < date.today() - timedelta(days=35):
            issues.append(f"Statement ends {x.period_end}; too old - we need a recent one.")
    if applicant_name and not _names_match(x.account_holder, applicant_name):
        issues.append(
            f"MISMATCH_FLAG: account holder ({x.account_holder}) does not match "
            f"applicant ({applicant_name}).")
    return issues


# ---------------------------------------------------------------------------
# The registry: doc_type -> everything the coordinator needs
# ---------------------------------------------------------------------------

_WORKSHOPIA_CONTEXT = (
    " You operate in the fictional State of Workshopia, whose documents are "
    "training specimens by design. Classify documents by their FORMAT and "
    "layout; 'TRAINING SPECIMEN' markings are expected and do not change "
    "what kind of document it is.")


def _extract(persona: str, schema: type[BaseModel], image_bytes: bytes) -> BaseModel:
    agent = Agent(model=CFG.model_id, system_prompt=persona + _WORKSHOPIA_CONTEXT)
    return agent.structured_output(schema, [
        {"text": "Extract the requested fields from this document image."},
        {"image": {"format": "png", "source": {"bytes": image_bytes}}},
    ])


DOC_SPECS = {
    "government_id": {
        "persona": ("You are an identity-document examiner. Read government ID "
                    "cards precisely. Transcribe fields exactly as printed."),
        "schema": IdExtraction,
        "validate": lambda x, ledger: validate_id(
            x, ledger.get("intake", {}).get("full_name") or x.full_name),
    },
    "paystub": {
        "persona": ("You are a payroll-document examiner. Read paystubs "
                    "precisely. Transcribe names, dates and amounts exactly as printed."),
        "schema": PaystubExtraction,
        "validate": lambda x, ledger: validate_paystub(
            x,
            ledger.get("intake", {}).get("employer_name"),
            ledger.get("intake", {}).get("stated_annual_income")),
    },
    "bank_statement": {
        "persona": ("You are a bank-statement examiner. Read statements "
                    "precisely, including period dates and recurring deposits."),
        "schema": StatementExtraction,
        "validate": lambda x, ledger: validate_statement(
            x, ledger.get("intake", {}).get("full_name")),
    },
}


def run_specialist(doc_type: str, image_bytes: bytes, ledger: dict) -> tuple[dict, list[str]]:
    """Dispatch to the right specialist. Returns (extracted fields, issues)."""
    spec = DOC_SPECS[doc_type]
    extraction = _extract(spec["persona"], spec["schema"], image_bytes)
    issues = spec["validate"](extraction, ledger)
    return extraction.model_dump(), issues
