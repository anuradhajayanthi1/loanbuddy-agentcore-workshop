---
title: "Getting started"
weight: 10
---

## 1. Environment

You need a terminal with:

- AWS CLI v2, configured for your workshop account (see below)
- Python 3.10+ and Node.js 18+
- The AgentCore CLI:

```bash
pip install bedrock-agentcore-starter-toolkit==0.3.10
export AGENTCORE_SUPPRESS_RECOMMENDATION=1
```

::alert[All commands in this workshop assume **us-east-1**. If a console page looks empty, check the region selector first — it is the most common support question in any workshop.]{header="Region check"}

### At an AWS-hosted event

Your temporary account is provided by Workshop Studio (use the **Open AWS
console** link on this page's event dashboard) and the base infrastructure
CloudFormation stack is pre-deployed. You still run the bootstrap script
below — it seeds users, generates sample documents, and publishes the UI.

### In your own account

Use a fresh, disposable account you can administer. Enable **Amazon Bedrock
model access** for Anthropic Claude Sonnet in us-east-1 (Bedrock console ->
Model access) before proceeding.

## 2. Get the code

```bash
git clone https://gitlab.aws.dev/anjayan/agentcore-loanbuddy-workshop.git loanbuddy-workshop
cd loanbuddy-workshop
```

## 3. Bootstrap

```bash
export AWS_REGION=us-east-1
./scripts/bootstrap.sh
```

About 6 minutes on first run (CloudFront dominates; at hosted events the
stack pre-exists and this is faster). It finishes by printing your
**workshop card** — every URL, login, and ID you will use today — and
writing `workshop-env.sh`.

## 4. Load your lab environment

Run this **once in every terminal you open**, all day:

```bash
source workshop-env.sh
echo "$UI_URL"
```

If the echo prints a CloudFront URL, you are wired up.

## 5. Two rules that prevent every common mishap

1. **Copy code blocks without the fences.** Copy what is between the
   ` ``` ` lines, never the fence lines themselves.
2. **Variables die with the terminal.** New terminal = `source
   workshop-env.sh` again. Values born during labs (agent ARN, memory ID)
   each come with a one-line command that re-fetches them.

Continue to **Lab 0** to inspect what bootstrap built.
