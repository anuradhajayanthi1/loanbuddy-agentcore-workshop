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

::alert[If an AWS CLI command fails with **"Error retrieving credentials from container-role ... 500"**, that's a transient CloudShell credential blip, not a workshop error. Retry once; if it persists, use **Actions -> Restart AWS CloudShell** (or re-open CloudShell from the event dashboard), then `source workshop-env.sh` again.]{header="CloudShell credential 500?"}

## 2. Bedrock model access (usually automatic)

Bedrock now enables models on first use — there is no manual model-access
page to click through. The **first** Claude invocation in a brand-new
account kicks off a one-time AWS Marketplace subscription that activates
after ~2 minutes. The bootstrap in the next step **warms this up for you**,
so by the time you reach Lab 1 it is ready. (If you ever see a 500 or a
"subscription pending" error on a very first invoke, just wait ~2 minutes
and retry.)

## 3. Get the code and bootstrap

```bash
git clone https://github.com/anuradhajayanthi1/loanbuddy-agentcore-workshop.git loanbuddy-workshop
cd loanbuddy-workshop
python3 -m venv .venv
.venv/bin/pip install bedrock-agentcore-starter-toolkit==0.3.10
export AWS_REGION=us-east-1
./scripts/bootstrap.sh
```

(The `agentcore` CLI lives in that `.venv` inside your home directory, so it
survives CloudShell restarts; `workshop-env.sh` puts it on PATH whenever you
`source` it.)

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

## 5. Three rules that prevent every common mishap

1. **Copy code blocks without the fences.** Copy what is between the
   ` ``` ` lines, never the fence lines themselves.
2. **Variables die with the terminal.** New terminal = `source
   workshop-env.sh` again. Values born during labs (agent ARN, memory ID)
   each come with a one-line command that re-fetches them.
3. **CloudShell times out when idle** (~20 minutes). Your files survive;
   your terminal doesn't. After a timeout, run
   `cd ~/loanbuddy-workshop && source workshop-env.sh` and continue where
   you left off.

Continue to **Lab 0** to inspect what bootstrap built.
