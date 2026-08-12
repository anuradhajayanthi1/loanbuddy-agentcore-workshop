---
title: "Lab 5: Code Interpreter + Browser (20 min)"
weight: 70
---

The two built-in AgentCore primitives are already wired into the subagent
code you deployed in Lab 4. This lab is about *watching them work* and
learning the design rule for when each is appropriate. Notice the symmetry:
Doc Coordinator gets Browser, Credit Analyst gets Code Interpreter, the
supervisor gets neither — built-in tools attach to the domain that needs
them, not to the orchestrator by default.

In every new terminal, run:

```bash
cd ~/loanbuddy-workshop && source workshop-env.sh
```

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

The Code Interpreter session **only runs during a credit assessment**, and
`assess_credit` will refuse until **all three of Alice's documents are
ACCEPTED** (it needs the verified ID for the credit pull and the analyzed
bank statement for income). So there is a strict order here. If you skip
ahead, the agent politely refuses and no session ever starts — that is
expected, not a bug.

### 2a. Confirm the prerequisite — all docs ACCEPTED

```bash
ALICE=$(aws cognito-idp admin-get-user --user-pool-id "$USER_POOL_ID" --username alice \
  --query "UserAttributes[?Name=='sub'].Value" --output text)
aws dynamodb get-item --table-name "$TABLE" --key "{\"applicant_id\":{\"S\":\"$ALICE\"}}" \
  --query 'Item.documents.M.{id:government_id.M.status.S,paystub:paystub.M.status.S,statement:bank_statement.M.status.S}'
```

You need all three to read **`ACCEPTED`**. If `paystub` or `statement` shows
`MISSING`, finish them first (2b). If **all three** show `MISSING` (including
`government_id`), the Lab 4 upload step was skipped — use 2b for all three
documents (`government_id` uses `alice-id.png`). If all three are
`ACCEPTED`, jump to 2c.

### 2b. Complete any missing documents

**Workshop (hosted event) users: use the CLI helper** — the sample docs
live in your CloudShell clone, and the UI's upload button can only pick
files from your own computer. Run it, then paste the line it prints
**exactly as printed** — it contains a real S3 key (a UUID and timestamp).
Do **not** type a shortened or example path; the agent needs the complete
key:

```bash
./scripts/upload-doc.sh alice paystub infra/seed/sample-docs/alice-paystub.png
```

It prints a block like:

```
Paste this into the chat as alice:
------------------------------------------------------------
I've uploaded my paystub. Its s3_key is docs/<real-uuid>/paystub-cli<real-timestamp>.png. Please analyze it.
------------------------------------------------------------
```

Copy that **whole middle line (with the real key)** into the chat. Wait for
the agent's **ACCEPTED** reply (~40–60s for the paystub — it also runs the
Browser employer check, see section 3). Repeat for the statement:

```bash
./scripts/upload-doc.sh alice bank_statement infra/seed/sample-docs/alice-statement-90d.png
```

(Own-account users working from a laptop can instead use the **UI upload
button**: send *"I'd like to upload my paystub"*, click the Upload control,
pick the file — the UI captures the real S3 key automatically.)

Re-run the 2a check until all three read `ACCEPTED`.

### 2c. Start the tail, then run the assessment

The Code Interpreter session is short-lived — to see it, start watching the
Credit Analyst log **before** you trigger the assessment. In one terminal:

```bash
RT=$(aws bedrock-agentcore-control list-agent-runtimes \
  --query "agentRuntimes[?starts_with(agentRuntimeName,'loanbuddy_credit_analyst')].agentRuntimeId | [0]" \
  --output text)
aws logs tail "/aws/bedrock-agentcore/runtimes/${RT}-DEFAULT" --follow --format short
```

Then, in the UI as **alice**, send:

```text
Please run my credit assessment for $15,000 over 36 months.
```

~90 seconds later the chat shows a PRIME tier, a rate band, and a **scenario
table** (payments at 24/36/48 months). The log is noisy — these are the
lines to spot:

```text
[credit-analyst] pulled fresh credit report: score=780
Initialized CodeInterpreter with session='session-a2f89e2472b6', identifier='aws.codeinterpreter.v1'
I'll underwrite this personal loan application step-by-step using Python. Let me execute the calculations now.
Tool #1: code_interpreter
Starting code interpreter session...
✅ Session started: 01KZJT6CGS0D36SV2MAX9DQCB8
Tool #2: code_interpreter
   ...
Tool #6: code_interpreter
## Underwriting Analysis Complete
- **DTI: 17.11%** (max allowed: 43%) ✓
### RECOMMENDATION: APPROVE
Tool #7: UnderwritingResult
[credit-analyst.underwriting] underwriting: income=7807 dti=0.17 max=36100
```

That's the model **writing Python and executing it in a sandbox session** —
the sandbox has **zero AWS credentials** (data in, numbers out). The
`✅ Session started: 01K...` ID is the session you'll find in the AgentCore
console (Built-in tools -> Code Interpreter) — refresh during this window to
catch it ACTIVE; sessions terminate seconds after the run, and a
**Terminated** entry is your proof it ran, not a failure.

### 2d. Confirm it ran

The `dti` and `scenarios` fields exist **only** because the sandbox computed
them, so their presence is proof the Code Interpreter ran:

```bash
aws dynamodb get-item --table-name "$TABLE" --key "{\"applicant_id\":{\"S\":\"$ALICE\"}}" \
  --query 'Item.credit.M.assessment.M.{tier:tier.S,dti:dti.N,scenarios:scenarios.L}'
```

Expected output (trimmed):

```json
{
    "tier": "PRIME",
    "dti": "0.1711",
    "scenarios": [
        { "M": { "term_months": {"N": "24"}, "monthly_payment": {"N": "693.91"}, ... } },
        { "M": { "term_months": {"N": "36"}, "monthly_payment": {"N": "485.77"}, ... } },
        { "M": { "term_months": {"N": "48"}, "monthly_payment": {"N": "382.24"}, ... } }
    ]
}
```

(`null` here means the assessment hasn't run yet — go back to 2c.)

Then the sanity check that motivates the whole primitive: ask any bare LLM to
compute a 36-month amortized payment at 10.25% in its head, and compare
against the sandbox's answer. Money math belongs in a calculator.

## 3. Watch Browser verify an employer

Bob's paystub names an employer his bank statement abbreviates and the state
registry has never heard of. Sign in as **bob** and run intake if needed:

```text
$15,000 debt consolidation, 36 months, I make $124,000 at Apex Fabrication Co
```

Then upload his ID and paystub the same way as section 2b, pasting each
printed line with its real key:

```bash
./scripts/upload-doc.sh bob government_id infra/seed/sample-docs/bob-id.png
./scripts/upload-doc.sh bob paystub infra/seed/sample-docs/bob-paystub.png
```

During paystub analysis, the Doc Coordinator starts an AgentCore **Browser**
session, drives the registry site you saw in Lab 0 — types the employer
name, clicks Search, reads the results table — and comes back with
`found: false`. The paystub lands as **MISMATCH_FLAGGED**, and the
supervisor raises it *as a conversation, not a rejection*: "could you
confirm the exact legal business name?"

**Answer the flag in character** — the agent genuinely waits for Bob's
response before proceeding (flags are conversations, and conversations have
two sides). Send:

```text
That's the only name on my paperwork - please go ahead with my assessment.
```

It records the answer and moves on.

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
