---
title: "Lab 6: Observability (25 min)"
weight: 80
---

Everything works; now see it. Observability was enabled the whole time —
each `agentcore deploy` wired OTEL telemetry, and the
`aws-opentelemetry-distro` package in each agent's requirements
auto-instruments the model calls, AWS SDK calls, and HTTP calls. This lab is
about reading it.

> **Before you start**: `source workshop-env.sh` from the workshop root.

## 1. Generate a fresh golden-path trace

In the UI as **alice**, send one message:

```text
Give me a quick status check on my documents and my approved options.
```

This touches Memory, the ledger, the Gateway, and (if credit needs
refreshing) the Credit Analyst.

## 2. The span tree IS the architecture diagram

Open CloudWatch -> **GenAI Observability** -> **Bedrock AgentCore** (or the
dashboard URL every deploy printed). Find the latest `loanbuddy_supervisor`
session and open it. That page lists the session's **traces** (one per turn)
— **click a Trace ID** (pick a high-span row; those are the turns that did
document/credit work) to open the span tree. What you're looking at:

```
supervisor session (alice)
├── memory retrievals            <- Lab 2
├── model turns (tokens, latency per turn)
├── DynamoDB Get/UpdateItem      <- the ledger
├── GetResourceOauth2Token       <- Lab 3's vault fetch
└── gateway: InvokeTool.doc-coordinator___check_docs_complete   <- Lab 4
```

Run a document upload or a fresh assessment and the deep spans appear: the
Browser session inside `analyze_document`, the Code Interpreter session
inside `assess_credit`. Every lab you built is one layer of this tree.

For raw span access (useful for the exercises), spans land in the
`aws/spans` log group; one trace ID stitches supervisor -> gateway ->
subagents. Nobody wrote instrumentation code — cross-runtime correlation
came with the primitives.

## 3. Three exercises, three production jobs

**Debug** — upload `alice-statement-60d.png` again as bob's statement (or
any wrong doc). Find in the trace *where* NEEDS_RESUBMISSION was decided:
which specialist ran, how long extraction took, what the validation issues
were. This is how you'll debug real agent systems: span-first, logs second.

**Cost** — compare token counts across the three agents' model spans for
one full application. Notice the Doc Coordinator's vision extraction
dominates. That's an argument written in data: put a smaller model on the
supervisor's chat turns, spend on vision only where documents are read.

**Audit** — reconstruct Alice's journey from telemetry alone: when was
credit pulled, was it re-pulled on her return (look for the *absent*
`get_credit_report` span on day 2 — the freshness rule at work), and did any
span in Bob's sessions ever touch Alice's partition? In lending, "show me
everything the system did to this applicant" is a compliance question, and
the trace answers it. The red-team attempts from Labs 2 and 4 left evidence:
boundaries you can *prove held* beat boundaries you assert.

## 4. The latency ledger

Find one `analyze_document` call and decompose its ~20 seconds: model turns
vs S3 fetch vs Browser session vs DDB writes. The "price of encapsulation"
from Lab 4, itemized. If this were your product, what would you parallelize
first?

## 5. Make it yours (closing discussion)

- **Swap the mock for real Experian**: change the OpenAPI target's server
  URL and credential. Nothing else in the system changes — that's the
  Gateway contract lesson.
- **Add a W-2 doc type**: one entry in `DOC_SPECS`, one line in the required
  docs list. No new infrastructure — the agent-sizing lesson.
- **When would a specialist earn its own runtime?** When its permissions,
  change cadence, or scaling diverge — the reason Credit Analyst is separate
  and the ID specialist is not.

**Exit state**: a multi-day, multi-agent, auth-boundaried loan origination
system — with every primitive load-bearing and visible in one span tree.

Catch-up: `scripts/checkpoint.sh 6`
