---
title: "Getting started"
weight: 10
---

::alert[All commands in this workshop run in **us-east-1**. If a console page looks empty, check the region selector first — it is the most common support question in any workshop.]{header="Region check"}

Pick your path:

## A. At an AWS-hosted event

Your account is provided, and the environment is **already seeded**: the UI
is live, the users exist, and the sample documents are generated. The
**Event outputs** panel on your event page shows the UI URL and both logins.

You need a terminal: **CloudShell works** (open the AWS console from your
event page, then the CloudShell icon in the top bar). Set up in four
commands:

```bash
aws s3 cp $(aws cloudformation describe-stacks --stack-name loanbuddy-workshop \
  --query "Stacks[0].Outputs[?OutputKey=='CodeBundle'].OutputValue" --output text) .
unzip -q loanbuddy-code.zip -d loanbuddy-workshop && cd loanbuddy-workshop
pip install --quiet bedrock-agentcore-starter-toolkit==0.3.10
./scripts/make-env.sh && source workshop-env.sh
```

That fetches the code bundle from the event's assets bucket, installs the
AgentCore CLI, and generates your **workshop card** (`workshop-card.txt`)
and environment file from the pre-deployed stack.

Skip to step "Load your lab environment" below — bootstrap already ran for
you at provisioning time.

## B. In your own account

Use a fresh, disposable account you can administer, with **Amazon Bedrock
model access** enabled for Anthropic Claude Sonnet in us-east-1 (Bedrock
console -> Model access). On your machine: AWS CLI v2, Python 3.10+, and:

```bash
pip install bedrock-agentcore-starter-toolkit==0.3.10
```

Get the code and bootstrap (about 6 minutes; deploys the CloudFormation
stack, seeds users, generates sample documents, publishes the UI):

```bash
git clone https://gitlab.aws.dev/anjayan/agentcore-loanbuddy-workshop.git loanbuddy-workshop
cd loanbuddy-workshop
export AWS_REGION=us-east-1
./scripts/bootstrap.sh
```

## Load your lab environment (both paths)

Run this **once in every terminal you open**, all day:

```bash
source workshop-env.sh
echo "$UI_URL"
```

If the echo prints a CloudFront URL, you are wired up. Your quick-reference
**workshop card** lives at `workshop-card.txt` in this directory — every
URL, login, and ID for the day (`cat workshop-card.txt` any time).

## Two rules that prevent every common mishap

1. **Copy code blocks without the fences.** Copy what is between the
   ` ``` ` lines, never the fence lines themselves.
2. **Variables die with the terminal.** New terminal = `source
   workshop-env.sh` again. Values born during labs (agent ARN, memory ID)
   each come with a one-line command that re-fetches them.

Continue to **Lab 0** to inspect what was built for you.
