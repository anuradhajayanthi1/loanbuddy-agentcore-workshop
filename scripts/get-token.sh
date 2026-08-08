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

case "$USER" in
  alice) PASS="LoanBuddy-alice-2026!" ;;
  bob)   PASS="LoanBuddy-bob-2026!" ;;
  *) echo "unknown workshop user: $USER" >&2; exit 1 ;;
esac

CLIENT_ID=$(aws cloudformation describe-stacks "${PROFILE_ARG[@]}" --region "$REGION" \
  --stack-name "$STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='SpaClientId'].OutputValue" --output text)

aws cognito-idp initiate-auth "${PROFILE_ARG[@]}" --region "$REGION" \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id "$CLIENT_ID" \
  --auth-parameters "USERNAME=$USER,PASSWORD=$PASS" \
  --query 'AuthenticationResult.AccessToken' --output text
