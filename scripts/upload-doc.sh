#!/usr/bin/env bash
# Upload a loan document on behalf of a workshop user, the CLI way.
# (The UI's upload button is the product path - this is the deterministic
# fallback, and handy for scripting.)
#
# Usage:
#   scripts/upload-doc.sh alice government_id infra/seed/sample-docs/alice-id.png
#
# Prints the exact chat message to paste so the agent analyzes the document.
set -euo pipefail

USER="${1:?usage: upload-doc.sh <alice|bob> <government_id|paystub|bank_statement> <file>}"
DOC_TYPE="${2:?missing doc type: government_id | paystub | bank_statement}"
FILE="${3:?missing file path}"
STACK="${STACK:-loanbuddy-workshop}"
REGION="${AWS_REGION:-us-east-1}"
PROFILE_ARG=()
[[ -n "${AWS_PROFILE:-}" ]] && PROFILE_ARG=(--profile "$AWS_PROFILE")

case "$DOC_TYPE" in
  government_id|paystub|bank_statement) ;;
  *) echo "invalid doc type: $DOC_TYPE" >&2; exit 1 ;;
esac
[[ -f "$FILE" ]] || { echo "no such file: $FILE" >&2; exit 1; }

out() {
  aws cloudformation describe-stacks "${PROFILE_ARG[@]}" --region "$REGION" \
    --stack-name "$STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}
POOL_ID="${USER_POOL_ID:-$(out UserPoolId)}"
BUCKET="${DOCS_BUCKET:-$(out DocsBucket)}"

# The applicant id is the user's Cognito sub - same identity propagation
# rule the agent uses, applied from the CLI.
SUB=$(aws cognito-idp admin-get-user "${PROFILE_ARG[@]}" --region "$REGION" \
  --user-pool-id "$POOL_ID" --username "$USER" \
  --query "UserAttributes[?Name=='sub'].Value" --output text)

KEY="docs/$SUB/${DOC_TYPE}-cli$(date +%s).png"
aws s3 cp "${PROFILE_ARG[@]}" --region "$REGION" --quiet "$FILE" "s3://$BUCKET/$KEY"

echo "Uploaded: s3://$BUCKET/$KEY"
echo
echo "Paste this into the chat as $USER:"
echo "------------------------------------------------------------"
echo "I've uploaded my ${DOC_TYPE//_/ }. Its s3_key is $KEY. Please analyze it."
echo "------------------------------------------------------------"
