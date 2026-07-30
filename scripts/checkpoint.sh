#!/usr/bin/env bash
# Bring the environment to the end-of-lab-N state, idempotently.
#
#   scripts/checkpoint.sh 3     # everything through Lab 3
#
# Use it to catch up if you joined late or a lab step went sideways.
# Requires: scripts/bootstrap.sh already run (Lab 0).
set -euo pipefail

LAB="${1:?usage: checkpoint.sh <1|2|3|4|5|6>}"
STACK="${STACK:-loanbuddy-workshop}"
REGION="${AWS_REGION:-us-east-1}"
export AGENTCORE_SUPPRESS_RECOMMENDATION=1
PROFILE_ARG=()
[[ -n "${AWS_PROFILE:-}" ]] && PROFILE_ARG=(--profile "$AWS_PROFILE")

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
say() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

out() {
  aws cloudformation describe-stacks "${PROFILE_ARG[@]}" --region "$REGION" \
    --stack-name "$STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

USER_POOL_ID=$(out UserPoolId)
SPA_CLIENT_ID=$(out SpaClientId)
M2M_CLIENT_ID=$(out M2MClientId)
DISCOVERY_URL=$(out CognitoDiscoveryUrl)
TABLE=$(out LoanApplicationsTable)
DOCS_BUCKET=$(out DocsBucket)
REGISTRY_URL=$(out RegistryUrl)
EXPERIAN_URL=$(out ExperianApiUrl)
GATEWAY_SCOPE=$(out GatewayScope)
SUPERVISOR_ROLE=$(out SupervisorRoleArn)
DOC_ROLE=$(out DocCoordinatorRoleArn)
CREDIT_ROLE=$(out CreditAnalystRoleArn)

acc() { aws bedrock-agentcore-control "$@" "${PROFILE_ARG[@]}" --region "$REGION"; }

memory_id() {
  acc list-memories --query "memories[?starts_with(id, 'loanbuddy_memory')].id | [0]" --output text 2>/dev/null | grep -v None || true
}
gateway_url() {
  acc list-gateways --query "items[?name=='loanbuddy-gateway'].gatewayId | [0]" --output text 2>/dev/null | grep -v None | while read -r gid; do
    acc get-gateway --gateway-identifier "$gid" --query gatewayUrl --output text
  done
}

supervisor_deploy() {  # args: extra -env flags
  say "Deploying supervisor"
  (cd "$ROOT/agents/supervisor" &&
    agentcore configure -e agent.py -n loanbuddy_supervisor -er "$SUPERVISOR_ROLE" \
      -rf requirements.txt -dm -rha "Authorization" \
      --authorizer-config "{\"customJWTAuthorizer\":{\"discoveryUrl\":\"$DISCOVERY_URL\",\"allowedClients\":[\"$SPA_CLIENT_ID\"]}}" \
      --non-interactive >/dev/null &&
    agentcore deploy -env TABLE_NAME="$TABLE" -env DOCS_BUCKET="$DOCS_BUCKET" "$@" | grep -E 'Agent ARN|deployed' || true)
}

supervisor_arn() {
  acc list-agent-runtimes --max-results 50 \
    --query "agentRuntimes[?starts_with(agentRuntimeName,'loanbuddy_supervisor')].agentRuntimeArn | [0]" --output text
}

# ---------------------------------------------------------------- Lab 1
if (( LAB >= 1 )); then
  supervisor_deploy
  say "Wiring UI to the supervisor"
  "$ROOT/scripts/wire-ui.sh" "$(supervisor_arn)"
fi

# ---------------------------------------------------------------- Lab 2
MEMORY_ID=""
if (( LAB >= 2 )); then
  MEMORY_ID=$(memory_id)
  if [[ -z "$MEMORY_ID" ]]; then
    say "Creating Memory resource (takes ~3 minutes)"
    agentcore memory create loanbuddy_memory \
      -d "LoanBuddy applicant memory" -r "$REGION" \
      --strategies '[{"semanticMemoryStrategy":{"name":"ApplicantFacts","namespaces":["/applicants/{actorId}/facts"]}},{"summaryMemoryStrategy":{"name":"SessionSummaries","namespaces":["/applicants/{actorId}/sessions/{sessionId}"]}}]' \
      --wait --max-wait 600 >/dev/null
    MEMORY_ID=$(memory_id)
  fi
  say "Memory: $MEMORY_ID"
fi

# ---------------------------------------------------------------- Lab 3
GATEWAY_URL=""
if (( LAB >= 3 )); then
  GATEWAY_URL=$(gateway_url)
  if [[ -z "$GATEWAY_URL" ]]; then
    say "Creating Gateway"
    agentcore gateway create-mcp-gateway --region "$REGION" --name loanbuddy-gateway \
      --authorizer-config "{\"customJWTAuthorizer\":{\"discoveryUrl\":\"$DISCOVERY_URL\",\"allowedClients\":[\"$M2M_CLIENT_ID\"]}}" >/dev/null
    GATEWAY_URL=$(gateway_url)
  fi
  say "Gateway: $GATEWAY_URL"

  GW_ID=$(acc list-gateways --query "items[?name=='loanbuddy-gateway'].gatewayId | [0]" --output text)
  GW_ARN="arn:aws:bedrock-agentcore:$REGION:$(aws sts get-caller-identity "${PROFILE_ARG[@]}" --query Account --output text):gateway/$GW_ID"
  GW_ROLE=$(acc get-gateway --gateway-identifier "$GW_ID" --query roleArn --output text)

  if ! acc list-oauth2-credential-providers --query "credentialProviders[?name=='loanbuddy-gateway-access']" --output text | grep -q loanbuddy; then
    say "Creating outbound OAuth credential provider"
    SECRET=$(aws cognito-idp describe-user-pool-client "${PROFILE_ARG[@]}" --region "$REGION" \
      --user-pool-id "$USER_POOL_ID" --client-id "$M2M_CLIENT_ID" \
      --query 'UserPoolClient.ClientSecret' --output text)
    agentcore identity create-credential-provider --name loanbuddy-gateway-access \
      --type cognito --client-id "$M2M_CLIENT_ID" --client-secret "$SECRET" \
      --discovery-url "$DISCOVERY_URL" -r "$REGION" >/dev/null
  fi

  if ! acc list-gateway-targets --gateway-identifier "$GW_ID" --query "items[?name=='experian-mock']" --output text | grep -q experian; then
    say "Registering experian-mock target"
    EXPERIAN_BASE="${EXPERIAN_URL%/credit-report}"
    SPEC_JSON=$(python3 - "$ROOT/infra/experian-openapi.json" "$EXPERIAN_BASE" <<'PYEOF'
import json, sys
spec = json.load(open(sys.argv[1]))
spec["servers"][0]["url"] = sys.argv[2]
print(json.dumps(json.dumps(spec)))
PYEOF
)
    agentcore gateway create-mcp-gateway-target --region "$REGION" \
      --gateway-arn "$GW_ARN" --gateway-url "$GATEWAY_URL" --role-arn "$GW_ROLE" \
      --name experian-mock --target-type openApiSchema \
      --target-payload "{\"inlinePayload\": $SPEC_JSON}" \
      --credentials '{"api_key":"workshop-experian-key-2026","credential_location":"HEADER","credential_parameter_name":"x-api-key"}' >/dev/null
  fi
fi

# ---------------------------------------------------------------- Lab 4+5
if (( LAB >= 4 )); then
  say "Deploying doc-coordinator"
  (cd "$ROOT/agents/doc-coordinator" &&
    agentcore configure -e server.py -n loanbuddy_doc_coordinator -er "$DOC_ROLE" \
      -rf requirements.txt -p MCP -dm \
      --authorizer-config "{\"customJWTAuthorizer\":{\"discoveryUrl\":\"$DISCOVERY_URL\",\"allowedClients\":[\"$M2M_CLIENT_ID\"]}}" \
      --non-interactive >/dev/null &&
    agentcore deploy -env TABLE_NAME="$TABLE" -env DOCS_BUCKET="$DOCS_BUCKET" \
      -env REGISTRY_URL="$REGISTRY_URL" | grep -cE 'deployed')

  say "Deploying credit-analyst"
  (cd "$ROOT/agents/credit-analyst" &&
    agentcore configure -e server.py -n loanbuddy_credit_analyst -er "$CREDIT_ROLE" \
      -rf requirements.txt -p MCP -dm \
      --authorizer-config "{\"customJWTAuthorizer\":{\"discoveryUrl\":\"$DISCOVERY_URL\",\"allowedClients\":[\"$M2M_CLIENT_ID\"]}}" \
      --non-interactive >/dev/null &&
    agentcore deploy -env TABLE_NAME="$TABLE" \
      -env GATEWAY_URL="$GATEWAY_URL" -env GATEWAY_PROVIDER_NAME=loanbuddy-gateway-access \
      -env GATEWAY_SCOPE="$GATEWAY_SCOPE" | grep -cE 'deployed')

  say "Registering subagent targets"
  python3 "$ROOT/scripts/register-subagent-targets.py" --region "$REGION"
fi

# ------------------------------------------------- supervisor final wiring
FINAL_ENV=()
(( LAB >= 2 )) && FINAL_ENV+=(-env MEMORY_ID="$MEMORY_ID")
(( LAB >= 3 )) && FINAL_ENV+=(-env GATEWAY_URL="$GATEWAY_URL" -env GATEWAY_PROVIDER_NAME=loanbuddy-gateway-access -env GATEWAY_SCOPE="$GATEWAY_SCOPE")
if (( LAB >= 2 )); then
  supervisor_deploy "${FINAL_ENV[@]}"
fi

say "Checkpoint for Lab $LAB complete."
(( LAB >= 6 )) && echo "Observability is on by default; see the GenAI Observability dashboard in CloudWatch."
exit 0
