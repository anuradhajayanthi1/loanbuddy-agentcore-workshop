# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Heuristic underwriting math - runs in the AgentCore Code Interpreter.

This is the OTHER half of the policy-vs-heuristic split: normalizing messy
per-applicant deposit data, DTI, affordability, and payment scenarios. The
model writes the code at runtime and executes it in a managed sandbox that
has NO AWS credentials - data in, numbers out, nothing else reachable.

Why not LLM mental math? Ask a bare model for a 36-month amortized payment
and compare. Money math belongs in a calculator, and the sandbox is the
calculator.
"""
import logging

from pydantic import BaseModel, Field
from strands import Agent
from strands_tools.code_interpreter import AgentCoreCodeInterpreter

from config import CFG

log = logging.getLogger("credit-analyst.underwriting")

DTI_CEILING = 0.43          # total monthly obligations / gross monthly income
PAYMENT_CEILING = 0.15      # new loan payment / gross monthly income
SCENARIO_TERMS = [24, 36, 48]


class Scenario(BaseModel):
    term_months: int
    monthly_payment: float
    total_interest: float


class UnderwritingResult(BaseModel):
    monthly_income_estimate: float = Field(
        description="Gross monthly income estimated from verified deposits (and stated income as a cross-check)")
    dti: float = Field(description="Debt-to-income ratio including the proposed loan payment at the requested term")
    max_affordable: float = Field(description="Maximum loan amount that keeps DTI and payment ratios within ceilings")
    scenarios: list[Scenario] = Field(description="Payment scenarios at 24/36/48 months for min(requested, max_affordable)")
    notes: list[str] = Field(default_factory=list, description="Anything odd about the income data")


UNDERWRITER_PERSONA = """\
You are an underwriting analyst. You NEVER compute numbers in your head: you
write Python and execute it with the code interpreter tool, then report the
executed results. Show your reasoning in code, not prose."""


def run_underwriting(*, requested_amount: float, term_months: int,
                     annual_rate: float, stated_annual_income: float | None,
                     net_deposit_amount: float, deposit_count: int,
                     period_days: int, monthly_obligations: float) -> UnderwritingResult:
    ci = AgentCoreCodeInterpreter(region=CFG.region)
    agent = Agent(model=CFG.model_id, system_prompt=UNDERWRITER_PERSONA,
                  tools=[ci.code_interpreter])
    task = f"""
Underwrite a personal loan using Python (write code, execute it, use the
printed results). Inputs:

- requested_amount = {requested_amount}
- term_months = {term_months}
- annual_rate = {annual_rate}   (representative APR as a decimal)
- stated_annual_income = {stated_annual_income}  (applicant's claim; cross-check only)
- verified NET payroll deposits from bank statement: {deposit_count} deposits
  of ~{net_deposit_amount} each over {period_days} days
- monthly_obligations = {monthly_obligations}  (existing debt, from credit bureau)

Compute:
1. Gross monthly income: annualize the net deposits from their observed
   frequency, then estimate gross using a 0.76 net-to-gross factor. Note if
   this disagrees with stated income by more than 25%.
2. Standard amortized monthly payment for the requested amount/term/rate.
3. DTI = (monthly_obligations + proposed payment) / gross monthly income.
4. max_affordable: the largest principal where BOTH
   (obligations + payment) / income <= {DTI_CEILING} AND
   payment / income <= {PAYMENT_CEILING} at the requested term (solve the
   amortization formula for principal; floor to the nearest 100).
5. Scenario table: for principal = min(requested_amount, max_affordable),
   monthly payment and total interest at terms {SCENARIO_TERMS}.
"""
    agent(task)
    result = agent.structured_output(
        UnderwritingResult,
        "Report the underwriting results exactly as computed by your executed code.",
    )
    log.info("underwriting: income=%.0f dti=%.2f max=%.0f",
             result.monthly_income_estimate, result.dti, result.max_affordable)
    return result
