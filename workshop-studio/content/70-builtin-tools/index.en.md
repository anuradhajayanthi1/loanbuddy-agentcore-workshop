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

**Easiest — the UI upload button:** tell the agent "I'd like to upload my
paystub", click the **Upload** control that appears, pick the file. The UI
captures the real S3 key for you automatically.

**Or the CLI helper.** Run it, then paste the line it prints **exactly as
printed** — it contains a real S3 key (a UUID and timestamp). Do **not** type
a shortened or example path; the agent needs the complete key:

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

Then, in the UI as **alice**: *"Please run my credit assessment for $15,000
over 36 months."*

~90 seconds later the chat shows a PRIME tier, a rate band, and a **scenario
table** (payments at 24/36/48 months). In the log terminal you'll see the
model **write Python and execute it in a sandbox session** — the sandbox has
**zero AWS credentials** (data in, numbers out). In the AgentCore console
(Built-in tools -> Code Interpreter), refresh during this window to catch the
ACTIVE session; the Observability panel there also records "Started sessions"
after the fact.

### 2d. Confirm it ran

The `dti` and `scenarios` fields exist **only** because the sandbox computed
them, so their presence is proof the Code Interpreter ran:

```bash
aws dynamodb get-item --table-name "$TABLE" --key "{\"applicant_id\":{\"S\":\"$ALICE\"}}" \
  --query 'Item.credit.M.assessment.M.{tier:tier.S,dti:dti.N,scenarios:scenarios.L}'
```

Then the sanity check that motivates the whole primitive: ask any bare LLM to
compute a 36-month amortized payment at 10.25% in its head, and compare
against the sandbox's answer. Money math belongs in a calculator.

## 3. Watch Browser verify an employer

Bob's paystub names an employer his bank statement abbreviates and the state
registry has never heard of. As **bob** (sign in as bob), run intake if
needed (*"$15,000 debt consolidation, 36 months, I make $124,000 at Apex
Fabrication Co"*), then upload his ID and paystub using the same method as
section 2b (UI upload button, or `./scripts/upload-doc.sh bob government_id
infra/seed/sample-docs/bob-id.png` and `... bob paystub
infra/seed/sample-docs/bob-paystub.png` — pasting each printed line with its
real key):

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
