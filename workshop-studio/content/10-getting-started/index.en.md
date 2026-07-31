---
title: "Getting started"
weight: 10
---

This workshop runs **both at AWS-hosted events** (using an account provided
for you) **and in your own AWS account**. The steps are the same either way.

::alert[Everything runs in **us-east-1**. If a console page looks empty, check the region selector first — it is the most common workshop support question.]{header="Region check"}

## 1. Get into an account with a terminal

**At an AWS-hosted event:** open the AWS console from your event dashboard
("Open AWS console"), then launch **CloudShell** (the `>_` icon in the top
navigation bar). CloudShell already has the AWS CLI, git, and Python.

**In your own account:** use a fresh AWS account you can administer, from
your laptop terminal (AWS CLI v2 configured) or CloudShell.

## 2. Enable Bedrock model access

In the **Amazon Bedrock console -> Model access**, enable **Anthropic Claude
Sonnet** in us-east-1. (At some hosted events this is pre-enabled — if the
list already shows access granted, continue.)

## 3. Get the code and bootstrap

```bash
git clone https://github.com/anuradhajayanthi1/security-agent.git loanbuddy-workshop
cd loanbuddy-workshop
pip install bedrock-agentcore-starter-toolkit==0.3.10
export AWS_REGION=us-east-1
./scripts/bootstrap.sh
```

Takes about 6 minutes (CloudFront dominates). Bootstrap deploys the base
CloudFormation stack, seeds the `alice` and `bob` logins, generates
freshly-dated sample documents, publishes the UI, and writes two files you
will use all day:

- **`workshop-card.txt`** — every URL, login, and ID (`cat workshop-card.txt`)
- **`workshop-env.sh`** — the environment for your lab terminals

## 4. Load your lab environment

Run this **once in every terminal you open**:

```bash
source workshop-env.sh
echo "$UI_URL"
```

If the echo prints a CloudFront URL, you are wired up. (Re-run
`./scripts/make-env.sh` to regenerate these files from the stack any time.)

## 5. Two rules that prevent every common mishap

1. **Copy code blocks without the fences.** Copy what is between the
   ` ``` ` lines, never the fence lines themselves.
2. **Variables die with the terminal.** New terminal = `source
   workshop-env.sh` again. Values born during labs (agent ARN, memory ID)
   each come with a one-line command that re-fetches them.

Continue to **Lab 0** to inspect what bootstrap built.
