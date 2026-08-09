#!/usr/bin/env bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
# Fetch a Cognito access token for a workshop user (Lab 1's proof tests).
# Usage: scripts/get-token.sh alice
set -eo pipefail

USER="${1:?usage: get-token.sh <alice|bob>}"
STACK="${STACK:-loanbuddy-workshop}"
REGION="${AWS_REGION:-us-east-1}"
PROFILE_ARG=()
[[ -n "${AWS_PROFILE:-}" ]] && PROFILE_ARG=(--profile "$AWS_PROFILE")

out() {
  aws cloudformation describe-stacks "${PROFILE_ARG[@]}" --region "$REGION" \
    --stack-name "$STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

# Passwords are generated per-deployment by bootstrap and read from the
# stack outputs - nothing hardcoded in the repo.
case "$USER" in
  alice) PASS=$(out AlicePassword) ;;
  bob)   PASS=$(out BobPassword) ;;
  *) echo "unknown workshop user: $USER" >&2; exit 1 ;;
esac

CLIENT_ID=$(out SpaClientId)

aws cognito-idp initiate-auth "${PROFILE_ARG[@]}" --region "$REGION" \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id "$CLIENT_ID" \
  --auth-parameters "USERNAME=$USER,PASSWORD=$PASS" \
  --query 'AuthenticationResult.AccessToken' --output text
