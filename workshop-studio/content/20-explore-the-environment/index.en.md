---
title: "Lab 0: Explore the environment"
weight: 20
---

Everything bootstrap built is infrastructure that is **not** AgentCore:
Cognito, S3, CloudFront, DynamoDB, a mock credit-bureau API, and pre-scoped
IAM roles. Every following lab is pure AgentCore work. Before building,
spend ten minutes feeling the starting state.

## 1. The product shell, with no brain

Open the UI (`echo $UI_URL`, or read it off your workshop card) and sign in
as `alice` (password on the card). Note the amber **account badge** on the
login card — if you ever have two workshop tabs open, the badge tells you
whose bank you are talking to.

Send any message. You get:

> *"The LoanBuddy agent isn't deployed yet - that's Lab 1."*

The product is live and you are authenticated; the brain is missing. That is
the gap the next lab closes.

## 2. The mock company registry

Open `$REGISTRY_URL` and search **Mercy General**. In Lab 5, an agent will
drive this exact page with a real browser — remember what the results table
looks like. (There is also a mock Experian credit API in your stack; you
will meet it in Lab 3, right before you wrap it as a tool.)

## 3. The least-privilege matrix

Read one of the pre-scoped agent IAM roles before you meet the agent that
wears it:

```bash
aws iam get-role-policy --role-name loanbuddy-doc-coordinator-role \
  --policy-name doc-coordinator-boundaries --query 'PolicyDocument.Statement[].Sid'
```

Three statements: read documents, write document metadata, use Browser. Note
what is **absent**: no Experian access, no Memory. The document agent you
will deploy in Lab 4 physically cannot call the credit bureau. Keep that
thought.

## 4. Meet the code

Skim these two files in your clone:

- `agents/supervisor/prompts.py` — what the loan officer **tries** to do
- `agents/supervisor/agent.py` — note the env-var gates (`MEMORY_ID`,
  `GATEWAY_URL`): the code is complete, and the labs light it up with
  configuration

**Exit state**: a live UI with no agent, seeded users, mock third parties,
and pre-scoped IAM roles. If you ever fall behind, `scripts/checkpoint.sh
<lab-number>` rebuilds everything through that lab.
