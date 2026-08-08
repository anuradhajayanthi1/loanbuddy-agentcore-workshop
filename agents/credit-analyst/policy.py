# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Lending policy: PLAIN CODE, on purpose.

These rules must produce identical results for identical inputs, every run,
and be reviewable in a diff. If this logic ran through the Code Interpreter,
the model would re-derive policy per applicant - two applicants with scores
719 and 721 might tier identically one day and differently the next.

Rule of thumb the workshop teaches:
  repo code   = rules you are accountable for
  sandbox code = computation you couldn't have written in advance
"""

# (min_score, tier, rate_band, policy_cap)
TIERS = [
    (720, "PRIME",      "9.5-11.0%",  25_000),
    (660, "NEAR_PRIME", "12.5-15.0%", 15_000),
    (580, "SUBPRIME",   "17.5-21.0%", 8_000),
    (0,   "DECLINE",    None,         0),
]

MAX_DELINQUENCIES = 4          # hard stop
MAX_UTILIZATION_PCT = 90       # hard stop


def apply_policy(report: dict) -> dict:
    """Map a credit report to tier / rate band / policy cap."""
    score = int(report.get("score", 0))
    flags: list[str] = []

    if int(report.get("delinquencies_24mo", 0)) > MAX_DELINQUENCIES:
        return {"tier": "DECLINE", "rate_band": None, "policy_cap": 0,
                "flags": ["Too many recent delinquencies."]}
    if int(report.get("utilization_pct", 0)) > MAX_UTILIZATION_PCT:
        return {"tier": "DECLINE", "rate_band": None, "policy_cap": 0,
                "flags": ["Credit utilization exceeds policy maximum."]}

    if int(report.get("delinquencies_24mo", 0)) > 0:
        flags.append(f"{report['delinquencies_24mo']} delinquency(ies) in 24 months.")
    if int(report.get("utilization_pct", 0)) > 50:
        flags.append(f"High utilization ({report['utilization_pct']}%).")

    for min_score, tier, band, cap in TIERS:
        if score >= min_score:
            return {"tier": tier, "rate_band": band, "policy_cap": cap,
                    "flags": flags}
    raise AssertionError("unreachable")


def representative_rate(rate_band: str) -> float:
    """Midpoint of the band, as a decimal, for scenario math."""
    lo, hi = rate_band.replace("%", "").split("-")
    return (float(lo) + float(hi)) / 2 / 100
