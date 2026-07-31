#!/usr/bin/env bash
# LoanBuddy workshop bootstrap: everything that is NOT an AgentCore primitive.
# Idempotent - safe to re-run.
set -eo pipefail

STACK="${STACK:-loanbuddy-workshop}"
PREFIX="${PREFIX:-loanbuddy}"
REGION="${AWS_REGION:-us-east-1}"
PROFILE_ARG=()
[[ -n "${AWS_PROFILE:-}" ]] && PROFILE_ARG=(--profile "$AWS_PROFILE")

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ALICE_PASSWORD="LoanBuddy-alice-2026!"
BOB_PASSWORD="LoanBuddy-bob-2026!"

say() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

# ---------------------------------------------------------------------------
say "Deploying CloudFormation stack: $STACK ($REGION)"
aws cloudformation deploy "${PROFILE_ARG[@]}" --region "$REGION" \
  --stack-name "$STACK" \
  --template-file "$ROOT/infra/template.yaml" \
  --parameter-overrides "ResourcePrefix=$PREFIX" \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset

out() {
  aws cloudformation describe-stacks "${PROFILE_ARG[@]}" --region "$REGION" \
    --stack-name "$STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

USER_POOL_ID=$(out UserPoolId)
SPA_CLIENT_ID=$(out SpaClientId)
M2M_CLIENT_ID=$(out M2MClientId)
DOCS_BUCKET=$(out DocsBucket)
UI_BUCKET=$(out UiBucket)
UI_URL=$(out UiUrl)
REGISTRY_URL=$(out RegistryUrl)
DISCOVERY_URL=$(out CognitoDiscoveryUrl)
TOKEN_ENDPOINT=$(out CognitoTokenEndpoint)
GATEWAY_SCOPE=$(out GatewayScope)
EXPERIAN_URL=$(out ExperianApiUrl)
TABLE=$(out LoanApplicationsTable)

# ---------------------------------------------------------------------------
say "Seeding Cognito users (alice, bob)"
for u in alice bob; do
  pass_var="$(echo "$u" | tr '[:lower:]' '[:upper:]')_PASSWORD"
  aws cognito-idp admin-create-user "${PROFILE_ARG[@]}" --region "$REGION" \
    --user-pool-id "$USER_POOL_ID" --username "$u" \
    --message-action SUPPRESS >/dev/null 2>&1 || true   # exists on re-run
  aws cognito-idp admin-set-user-password "${PROFILE_ARG[@]}" --region "$REGION" \
    --user-pool-id "$USER_POOL_ID" --username "$u" \
    --password "${!pass_var}" --permanent
done

# ---------------------------------------------------------------------------
say "Generating sample documents (fresh dates) and staging to S3"
PYBIN="$ROOT/.venv/bin/python"; [[ -x "$PYBIN" ]] || PYBIN=python3
"$PYBIN" -c "import PIL" 2>/dev/null || "$PYBIN" -m pip install -q "Pillow>=12.1.1,<13"
"$PYBIN" "$ROOT/infra/seed/generate_docs.py" "$ROOT/infra/seed/sample-docs"
aws s3 sync "${PROFILE_ARG[@]}" --region "$REGION" --quiet \
  "$ROOT/infra/seed/sample-docs" "s3://$DOCS_BUCKET/sample-docs/"

# ---------------------------------------------------------------------------
say "Publishing UI and mock registry"
ACCOUNT_ID=$(aws sts get-caller-identity "${PROFILE_ARG[@]}" --query Account --output text)
sed -e "s|REPLACED_BY_BOOTSTRAP_REGION|$REGION|" \
    -e "s|\"us-east-1\"|\"$REGION\"|" \
    -e "s|REPLACED_BY_BOOTSTRAP_BADGE|account $ACCOUNT_ID|" \
    -e "s|userPoolId: \"REPLACED_BY_BOOTSTRAP\"|userPoolId: \"$USER_POOL_ID\"|" \
    -e "s|spaClientId: \"REPLACED_BY_BOOTSTRAP\"|spaClientId: \"$SPA_CLIENT_ID\"|" \
    "$ROOT/ui/config.js" > /tmp/loanbuddy-config.js
aws s3 cp "${PROFILE_ARG[@]}" --region "$REGION" --quiet /tmp/loanbuddy-config.js "s3://$UI_BUCKET/config.js"
aws s3 cp "${PROFILE_ARG[@]}" --region "$REGION" --quiet "$ROOT/ui/index.html" "s3://$UI_BUCKET/index.html"
aws s3 cp "${PROFILE_ARG[@]}" --region "$REGION" --quiet "$ROOT/ui/app.js" "s3://$UI_BUCKET/app.js"
aws s3 cp "${PROFILE_ARG[@]}" --region "$REGION" --quiet "$ROOT/ui/styles.css" "s3://$UI_BUCKET/styles.css"
aws s3 cp "${PROFILE_ARG[@]}" --region "$REGION" --quiet \
  "$ROOT/infra/seed/registry-site/index.html" "s3://$UI_BUCKET/registry/index.html"

# ---------------------------------------------------------------------------
say "Warming up Bedrock model access (first Claude invoke in a fresh account"
say "triggers an async AWS Marketplace subscription that takes ~2 minutes)"
# Fire-and-forget: the first invoke initiates the subscription even if it
# returns an error; by the time the attendee reaches Lab 1 it has completed,
# so their first agent invoke won't 500 on a pending subscription.
MODEL_ID="${MODEL_ID:-us.anthropic.claude-sonnet-4-5-20250929-v1:0}"
aws bedrock-runtime converse "${PROFILE_ARG[@]}" --region "$REGION" \
  --model-id "$MODEL_ID" \
  --messages '[{"role":"user","content":[{"text":"warmup"}]}]' \
  >/dev/null 2>&1 && echo "  model access ready" \
  || echo "  subscription initiated (may take ~2 min to activate - this is expected)"

say "Writing workshop-env.sh and workshop-card.txt"
"$ROOT/scripts/make-env.sh"
say "Done. Your workshop card:"
cat "$ROOT/workshop-card.txt"
echo
echo "Next: run 'source workshop-env.sh' in every lab terminal you open."
