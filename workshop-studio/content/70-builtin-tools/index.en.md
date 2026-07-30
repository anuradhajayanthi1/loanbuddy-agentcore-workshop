---
title: "Lab 5: Code Interpreter + Browser"
weight: 70
---

The two built-in AgentCore primitives are already wired into the subagent
code you deployed in Lab 4. This lab is about *watching them work* and
learning the design rule for when each is appropriate. Notice the symmetry:
Doc Coordinator gets Browser, Credit Analyst gets Code Interpreter, the
supervisor gets neither — built-in tools attach to the domain that needs
them, not to the orchestrator by default.

> **Before you start**: `source workshop-env.sh` from the workshop root.

## 1. The policy-vs-heuristic split (read this table twice)

Open `agents/credit-analyst/policy.py` and `underwriting.py` side by side:

| | `policy.py` | `underwriting.py` |
|---|---|---|
| Logic | score >= 720 -> PRIME | normalize 6 irregular deposits into monthly income |
| Written by | engineers, in the repo | the LLM, at runtime |
| Runs | in the agent process | in the Code Interpreter sandbox |
| Varies run-to-run? | that's a bug | that's the point |

**Use the sandbox for computation you couldn't have written in advance; use
the repo for rules you're accountable for.** If tier thresholds ran through
the LLM, two applicants scoring 719 and 721 might tier identically today and
differently tomorrow. If deposit normalization were hardcoded, it would
break on the first applicant with unusual pay patterns.

## 2. Watch Code Interpreter underwrite Alice

In the UI as **alice** (docs complete from Lab 4): *"Please run my credit
assessment for the $15,000 over 36 months."*

~90 seconds later: PRIME tier, a rate band, and a **scenario table** —
payments at 24/36/48 months. While it runs, tail the analyst:

```bash
aws logs tail "/aws/bedrock-agentcore/runtimes/$(aws bedrock-agentcore-control \
  list-agent-runtimes --query "agentRuntimes[?starts_with(agentRuntimeName,'loanbuddy_credit_analyst')].agentRuntimeArn | [0]" \
  --output text | awk -F/ '{print $NF}')-DEFAULT" --since 5m --follow
```

You'll see the model *write pandas code* and execute it in a sandbox
session. That sandbox has **zero AWS credentials** — data in, numbers out.
Ask a follow-up: *"what about 48 months?"* — instant, because the scenario
table already came back with the assessment (design choice: precompute the
what-ifs, don't re-round-trip).

Then the sanity check that motivates the whole primitive: ask any bare LLM
to compute a 36-month amortized payment at 10.25% in its head, and compare
against the sandbox's answer. Money math belongs in a calculator.

## 3. Watch Browser verify an employer

Bob's paystub names an employer his bank statement abbreviates and the state
registry has never heard of. As **bob**: run intake if needed (*"$15,000
debt consolidation, 36 months, I make $124,000 at Apex Fabrication Co"*),
then upload `bob-id.png` and `bob-paystub.png`.

During paystub analysis, the Doc Coordinator starts an AgentCore **Browser**
session, drives the registry site you saw in Lab 0 — types the employer
name, clicks Search, reads the results table — and comes back with
`found: false`. The paystub lands as **MISMATCH_FLAGGED**, and the
supervisor raises it *as a conversation, not a rejection*: "could you
confirm the exact legal business name?"

**Answer the flag in character** — the agent genuinely waits for Bob's
response before proceeding (flags are conversations, and conversations have
two sides). Something like: *"That's the only name on my paperwork — please
go ahead with my assessment."* It records the answer and moves on.

Design notes worth reading in `employer_check.py`:
- The browser runs in a managed, isolated session — a hostile webpage has no
  agent environment to steal from.
- The verdict is computed **in plain code** from structured fields the agent
  transcribes off the results table. Page prose is never followed as
  instructions — untrusted-content discipline.
- When would you use Browser for real? Only when there's no API. It's the
  integration of last resort — and last resort comes up constantly (legacy
  portals, government sites, partners you don't control).

## 4. Bob's counteroffer (both primitives, one decision)

Upload `bob-statement-90d.png`, then ask for his assessment. Watch what the
sandbox catches: his paystub claims ~$124k/year, but his verified deposits
project to ~$61k — a >50% variance the underwriting code flags. Combined
with his 585 score (SUBPRIME) and 74% utilization, he gets a counteroffer
around $2,100 instead of $15,000 — same code path as Alice, different data.

**Exit state**: every capability from the original design is live. One thing
left: *seeing* the whole machine at once.

Catch-up: `scripts/checkpoint.sh 5`
