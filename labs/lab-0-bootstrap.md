# Lab 0 — Bootstrap (15 min)

Everything in this lab is infrastructure that is NOT AgentCore: Cognito, S3,
CloudFront, DynamoDB, a mock credit-bureau API, and pre-scoped IAM roles.
You run one script and inspect what it made. Every following lab is pure
AgentCore work.

## 1. Prerequisites

- AWS CLI v2 with a profile that can administer your workshop account
- Python 3.10+, plus the AgentCore CLI:

```bash
pip install bedrock-agentcore-starter-toolkit==0.3.10
export AGENTCORE_SUPPRESS_RECOMMENDATION=1
```

- Amazon Bedrock model access enabled for Anthropic Claude Sonnet in your
  region (Bedrock console -> Model access)

## 2. Bootstrap

```bash
export AWS_PROFILE=<your-profile>
export AWS_REGION=us-east-1
./scripts/bootstrap.sh
```

Takes about 6 minutes (CloudFront dominates). It prints your **workshop
card**, saved to `workshop-card.txt` in the workshop root — your
quick-reference for every URL, login, and ID all day (`cat
workshop-card.txt` any time).

## 3. Set your lab environment

Bootstrap wrote `workshop-env.sh` with everything the labs need (endpoints,
IDs, role ARNs, and the `out` helper). Run this once per terminal session:

```bash
source workshop-env.sh
echo "$UI_URL"
```

## 4. Inspect what exists — and what doesn't

1. **Open the UI** — URL on your workshop card (or `echo $UI_URL`) — and
   sign in as `alice` (password on the card). Send a message. You'll get:
   *"The LoanBuddy agent isn't deployed yet - that's Lab 1."* The product
   shell is live; the brain is missing.
2. **The mock registry**: `echo $REGISTRY_URL`, open it, search "Mercy General".
   Lab 5's Browser agent will drive this exact page. (There's also a mock
   credit-bureau API in your stack — you'll meet it in Lab 3, right before
   you wrap it as a tool.)
3. **The least-privilege matrix** — read one role before you meet the agent
   that wears it:

```bash
aws iam get-role-policy --role-name loanbuddy-doc-coordinator-role \
  --policy-name doc-coordinator-boundaries --query 'PolicyDocument.Statement[].Sid'
```

Note what's absent: no Experian access, no Memory. The doc agent physically
cannot call the credit bureau. Keep that thought for Lab 4.

## 5. Meet the code

Skim these two files — the loan officer's persona, and the entrypoint whose
env-var gates (`MEMORY_ID`, `GATEWAY_URL`) the labs light up one by one:

```bash
cat agents/supervisor/prompts.py    # what the loan officer TRIES to do
cat agents/supervisor/agent.py      # note the MEMORY_ID / GATEWAY_URL gates
```

The application is complete; your job across labs 1–6 is to give it the
AgentCore primitives it's written against.

**Exit state**: live UI with no agent, seeded users, mock third parties, and
pre-scoped IAM roles. Fell behind later? `scripts/checkpoint.sh <lab>`
rebuilds everything through that lab.
