---
title: "Getting started"
weight: 10
---

::alert[This is a **self-paced, bring-your-own-account** workshop. Use a fresh AWS account you can administer and are comfortable creating resources in. Everything runs in **us-east-1** — if a console page looks empty, check the region selector first.]{header="Before you begin"}

## 1. Prerequisites

- A disposable AWS account you can administer
- **Amazon Bedrock model access** enabled for Anthropic Claude Sonnet in
  us-east-1 (Bedrock console -> Model access -> enable Claude Sonnet)
- On your machine: AWS CLI v2 (configured), Python 3.10+, Node.js 18+, git
- The AgentCore CLI:

```bash
pip install bedrock-agentcore-starter-toolkit==0.3.10
export AGENTCORE_SUPPRESS_RECOMMENDATION=1
```

## 2. Get the code and bootstrap

```bash
git clone https://gitlab.aws.dev/anjayan/agentcore-loanbuddy-workshop.git loanbuddy-workshop
cd loanbuddy-workshop
export AWS_REGION=us-east-1
./scripts/bootstrap.sh
```

Takes about 6 minutes (CloudFront dominates). Bootstrap deploys the
CloudFormation stack, seeds the `alice` and `bob` logins, generates
freshly-dated sample documents, publishes the UI, and writes two files you
will use all day:

- **`workshop-card.txt`** — every URL, login, and ID for the workshop
  (`cat workshop-card.txt` any time)
- **`workshop-env.sh`** — the environment for your lab terminals

## 3. Load your lab environment

Run this **once in every terminal you open**:

```bash
source workshop-env.sh
echo "$UI_URL"
```

If the echo prints a CloudFront URL, you are wired up. (Re-running
`./scripts/make-env.sh` regenerates these files from the stack at any time.)

## 4. Two rules that prevent every common mishap

1. **Copy code blocks without the fences.** Copy what is between the
   ` ``` ` lines, never the fence lines themselves.
2. **Variables die with the terminal.** New terminal = `source
   workshop-env.sh` again. Values born during labs (agent ARN, memory ID)
   each come with a one-line command that re-fetches them.

Continue to **Lab 0** to inspect what bootstrap built.
