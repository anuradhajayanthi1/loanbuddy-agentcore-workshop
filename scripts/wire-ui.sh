#!/usr/bin/env bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
# Point the deployed UI at the supervisor agent runtime (end of Lab 1).
# Usage: scripts/wire-ui.sh <agent-runtime-arn>
set -eo pipefail

ARN="${1:?usage: wire-ui.sh <agent-runtime-arn>}"
STACK="${STACK:-loanbuddy-workshop}"
REGION="${AWS_REGION:-us-east-1}"
PROFILE_ARG=()
[[ -n "${AWS_PROFILE:-}" ]] && PROFILE_ARG=(--profile "$AWS_PROFILE")

out() {
  aws cloudformation describe-stacks "${PROFILE_ARG[@]}" --region "$REGION" \
    --stack-name "$STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}
UI_BUCKET=$(out UiBucket)

# URL-encode the ARN for the invocation path (: -> %3A, / -> %2F)
ENCODED=$(printf '%s' "$ARN" | sed -e 's/:/%3A/g' -e 's/\//%2F/g')

aws s3 cp "${PROFILE_ARG[@]}" --region "$REGION" --quiet "s3://$UI_BUCKET/config.js" /tmp/lb-config.js
sed -i.bak "s|agentArnEncoded: \"[^\"]*\"|agentArnEncoded: \"$ENCODED\"|" /tmp/lb-config.js
aws s3 cp "${PROFILE_ARG[@]}" --region "$REGION" --quiet /tmp/lb-config.js "s3://$UI_BUCKET/config.js"

# Bust the CloudFront cache so re-wiring takes effect without a stale
# config.js lingering at the edge (matters on any re-run after Lab 1).
aws cloudfront create-invalidation "${PROFILE_ARG[@]}" \
  --distribution-id "$(out DistributionId)" --paths "/config.js" >/dev/null 2>&1 || true

echo "UI wired to $ARN"
echo "Open: $(out UiUrl)  (hard-refresh or new tab if it was already open)"
