---
title: "Lab 1: Runtime + inbound Identity (25 min)"
weight: 30
---

Deploy the supervisor to AgentCore Runtime behind a JWT authorizer, and
establish the pattern that carries the whole workshop: **the user's identity
claim becomes the applicant ID that scopes everything downstream.**

## 0. Before you start (every lab, every terminal)

All lab commands use `$VARIABLES` so you never copy values by hand. Load them:

```bash
cd ~/loanbuddy-workshop          # the folder you cloned into
source workshop-env.sh
echo "$SUPERVISOR_ROLE"          # must print an IAM role ARN - if empty, stop and re-source
```

## 1. Configure the agent

```bash
cd agents/supervisor
agentcore configure -e agent.py -n loanbuddy_supervisor \
  -er "$SUPERVISOR_ROLE" -rf requirements.txt \
  -dm -rha "Authorization" \
  --authorizer-config "{\"customJWTAuthorizer\":{\"discoveryUrl\":\"$DISCOVERY_URL\",\"allowedClients\":[\"$SPA_CLIENT_ID\"]}}" \
  --non-interactive
```

Three flags worth understanding (not just pasting):

- `--authorizer-config` — the **inbound Identity boundary**. The Runtime
  validates every caller's JWT against your Cognito pool *before your code
  runs*. No token, no entry.
- `-rha "Authorization"` — allowlists the Authorization header through to
  your container. Validation happens at the front door either way, but your
  code needs the token to read the `sub` claim. Forget this flag and every
  user becomes anonymous (a bug you'd meet in Lab 2 as everyone sharing one
  application).
- `-dm` — disables CLI-managed memory. We build Memory deliberately in Lab 2.

## 2. Deploy

```bash
agentcore deploy -env TABLE_NAME="$TABLE" -env DOCS_BUCKET="$DOCS_BUCKET"
agentcore status        # wait for: Ready
```

::alert[If you see **"Platform mismatch: current system is linux/amd64 but Bedrock AgentCore requires linux/arm64"**, that is expected in CloudShell — it is informational. The default `agentcore deploy` does a remote ARM64 build in CodeBuild, so the deployment is correct. Just wait for it to finish.]{header="Expected warning"}

::alert[**First invoke returns HTTP 500 in a brand-new account?** The first Claude invocation triggers an AWS Marketplace subscription that finishes asynchronously (~2 min). Bootstrap warms this up, but if you land inside that window, wait ~2 minutes and re-invoke — no redeploy needed. If a 500 persists past a few minutes, confirm `agentcore status` is **Ready**; if needed, clean-redeploy: `rm -f .bedrock_agentcore.yaml`, then re-run `agentcore configure` and `agentcore deploy`.]{header="Troubleshooting 500s"}

Capture the new runtime's ARN (works from any directory):

```bash
export AGENT_ARN=$(aws bedrock-agentcore-control list-agent-runtimes \
  --query "agentRuntimes[?starts_with(agentRuntimeName,'loanbuddy_supervisor')].agentRuntimeArn | [0]" \
  --output text)
echo "$AGENT_ARN"       # must print an ARN - if blank or None, the deploy isn't finished
```

## 3. Prove the boundary

```bash
ENC=$(python3 -c "import urllib.parse,os; print(urllib.parse.quote(os.environ['AGENT_ARN'], safe=''))")
URL="https://bedrock-agentcore.$AWS_REGION.amazonaws.com/runtimes/$ENC/invocations?qualifier=DEFAULT"
SID="lab1-$(date +%s)-0123456789abcdefghij"    # session ids need 33+ chars

# 1) No token -> 401
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$URL" \
  -H "Content-Type: application/json" \
  -H "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: $SID" -d '{"prompt":"hi"}'

# 2) Garbage token -> 403
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$URL" \
  -H "Authorization: Bearer garbage.token.here" -H "Content-Type: application/json" \
  -H "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: $SID" -d '{"prompt":"hi"}'

# 3) Real token -> the loan officer answers
TOKEN=$("$WORKSHOP_ROOT/scripts/get-token.sh" alice)
curl -s -X POST "$URL" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: $SID" \
  -d '{"prompt":"Hi! I would like to apply for a $15,000 personal loan."}'
```

## 4. Identity propagation — the concept that matters

Decode Alice's token (`echo $TOKEN | cut -d. -f2 | base64 -D` on macOS, `-d`
on Linux): the `sub` claim is her stable user ID. Now read
`applicant_from_request()` in `agent.py` — the agent takes the applicant ID
from the *validated token*, never from conversation. Then check the ledger:

```bash
aws dynamodb scan --table-name "$TABLE" --query 'Items[].applicant_id.S'
```

Her application is keyed by that `sub`. **Identity is established once at
the front door and flows through every downstream boundary. The agent never
asks who you are.**

## 5. Wire the UI

```bash
"$WORKSHOP_ROOT/scripts/wire-ui.sh" "$AGENT_ARN"
```

Open the UI, sign in as alice, chat. Then open browser dev tools (Network
tab) and watch the `Bearer` token ride each `/runtimes/...` call — there is
no backend server here — the SPA calls the Runtime's data-plane endpoint
directly (it supports CORS), token straight from Cognito to the front door.

**Exit state**: authenticated humans chat with a deployed loan officer. But
sign out and back in — the agent greets you like a stranger, every time.
(Structured intake fields do land in the DynamoDB ledger, but the agent has
no recollection of the *conversation* and deliberately doesn't pretend to.)
That pain is Lab 2's job.

Catch-up: `scripts/checkpoint.sh 1`
