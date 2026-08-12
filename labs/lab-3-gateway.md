# Lab 3 — Gateway + Outbound Identity (25 min)

Create the tool plane: an MCP Gateway that turns arbitrary backends into a
single authenticated tool catalog, plus the outbound half of Identity — the
token vault that lets an agent hold credentials that appear nowhere in its
code.

In every new terminal, run:

```bash
cd ~/loanbuddy-workshop && source workshop-env.sh
```

## 0. Meet the raw API you're about to wrap

Your stack includes a mock Experian bureau — a "third-party" API with its own
key. Call it the way a bare integration would:

```bash
# no key -> the bureau refuses you
curl -s -X POST "$EXPERIAN_URL" -H 'Content-Type: application/json' \
  -d '{"full_name":"Alice Anderson"}'

# with the key -> Alice's credit report
curl -s -X POST "$EXPERIAN_URL" -H 'Content-Type: application/json' \
  -H "x-api-key: $EXPERIAN_API_KEY" \
  -d '{"full_name":"Alice Anderson"}'
```

This is the "before" picture: every consumer of this API needs the URL, the
key, the JSON shape, and its own error handling — and every one of them is a
place the key can leak. Keep the key in your head for the next ten minutes;
by step 2 it will live somewhere no agent can leak it from.

## 1. Create the Gateway

```bash
agentcore gateway create-mcp-gateway --region "$AWS_REGION" \
  --name loanbuddy-gateway --role-arn "$GATEWAY_ROLE" \
  --authorizer-config "{\"customJWTAuthorizer\":{\"discoveryUrl\":\"$DISCOVERY_URL\",\"allowedClients\":[\"$M2M_CLIENT_ID\"]}}"

export GW_ID=$(aws bedrock-agentcore-control list-gateways \
  --query "items[?name=='loanbuddy-gateway'].gatewayId | [0]" --output text)
export GW_ARN="arn:aws:bedrock-agentcore:$AWS_REGION:$(aws sts get-caller-identity --query Account --output text):gateway/$GW_ID"
export GATEWAY_URL="https://$GW_ID.gateway.bedrock-agentcore.$AWS_REGION.amazonaws.com/mcp"
export GW_ROLE="$GATEWAY_ROLE"
```

Note the authorizer: the Gateway has its own front door. Human logins (SPA
client) don't get in — only machine tokens from the M2M client. Different
principal, different door.

## 2. Register the Experian mock as an OpenAPI target

The bureau "API" you probed in Lab 0 becomes a typed MCP tool. The OpenAPI
spec in `infra/experian-openapi.json` isn't boilerplate — the operation
description is *what the supervisor's LLM reads to decide when to call it*.

```bash
EXPERIAN_BASE="${EXPERIAN_URL%/credit-report}"
SPEC_JSON=$(python3 -c "
import json
spec = json.load(open('infra/experian-openapi.json'))
spec['servers'][0]['url'] = '$EXPERIAN_BASE'
print(json.dumps(json.dumps(spec)))")

agentcore gateway create-mcp-gateway-target --region "$AWS_REGION" \
  --gateway-arn "$GW_ARN" --gateway-url "$GATEWAY_URL" --role-arn "$GW_ROLE" \
  --name experian-mock --target-type openApiSchema \
  --target-payload "{\"inlinePayload\": $SPEC_JSON}" \
  --credentials "{\"api_key\":\"$EXPERIAN_API_KEY\",\"credential_location\":\"HEADER\",\"credential_parameter_name\":\"x-api-key\"}"
```

That `--credentials` flag stores the bureau API key **on the Gateway
target**. Tool callers never see or send it; the Gateway injects it on the
way out. One place to rotate it, zero places to leak it.

## 3. Prove the tool plane (raw MCP, no agent yet)

```bash
SECRET=$(aws cognito-idp describe-user-pool-client --user-pool-id "$USER_POOL_ID" \
  --client-id "$M2M_CLIENT_ID" --query 'UserPoolClient.ClientSecret' --output text)
M2M_TOKEN=$(curl -s -X POST "$TOKEN_ENDPOINT" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -u "$M2M_CLIENT_ID:$SECRET" \
  -d "grant_type=client_credentials&scope=${GATEWAY_SCOPE/\//%2F}" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

# list tools
curl -s -X POST "$GATEWAY_URL" -H "Authorization: Bearer $M2M_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | python3 -m json.tool | grep '"name"'

# call the credit tool through the gateway (no API key in sight)
curl -s -X POST "$GATEWAY_URL" -H "Authorization: Bearer $M2M_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"experian-mock___get_credit_report","arguments":{"full_name":"Alice Anderson"}}}'

# and without a token -> 401
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$GATEWAY_URL" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/list","params":{}}'
```

The `experian-mock___` prefix is Gateway routing made visible — you'll read
it straight out of traces in Lab 6.

## 4. Outbound Identity: the credential provider

The supervisor needs an M2M token like the one you just built by hand — but
its code must never hold the client secret. Register the credentials in the
Identity token vault:

```bash
agentcore identity create-credential-provider --name loanbuddy-gateway-access \
  --type cognito --client-id "$M2M_CLIENT_ID" --client-secret "$SECRET" \
  --discovery-url "$DISCOVERY_URL" -r "$AWS_REGION"
```

Now read `gateway_access_token()` in `agents/supervisor/agent.py`: a
`@requires_access_token(provider_name=..., auth_flow="M2M")` decorator, and
the token arrives as an argument. At runtime the SDK presents the agent's
*workload identity* to the vault; the vault runs the OAuth dance and returns
a token. **The "where's the secret?" test**: `grep -ri secret
agents/supervisor/` — nothing. It can't be leaked, logged, or
prompt-injected out of the model's context, because it never enters it.

## 5. Connect the supervisor

```bash
cd agents/supervisor
agentcore deploy -env TABLE_NAME="$TABLE" -env DOCS_BUCKET="$DOCS_BUCKET" \
  -env MEMORY_ID="$MEMORY_ID" \
  -env GATEWAY_URL="$GATEWAY_URL" \
  -env GATEWAY_PROVIDER_NAME=loanbuddy-gateway-access \
  -env GATEWAY_SCOPE="$GATEWAY_SCOPE"
cd ../..
```

In the UI, ask alice: *"Can you run a quick credit check for me?"* The
supervisor discovers `get_credit_report` over MCP, calls it
mid-conversation, and gives you a preliminary read on your credit (it will
note the formal assessment comes after documents — that's its lending
process talking). Contrast with `get_or_create_application` in `tools.py` —
local tools are compiled in, Gateway tools are *discovered*. (The supervisor
touching the bureau directly is deliberately temporary — Lab 4 introduces a
specialist and takes this job away from it.)

**Exit state**: an authenticated tool plane with one typed tool, and a
supervisor that fetches its gateway credential from the vault at call time.

Catch-up: `scripts/checkpoint.sh 3`
