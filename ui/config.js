// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0
// LoanBuddy UI configuration.
// scripts/bootstrap.sh writes the real values; this placeholder ships in git.
window.LOANBUDDY = {
  region: "us-east-1",
  // Which deployment am I? Shown in the header so attendees in shared rooms
  // never chat with someone else's bank.
  badge: "REPLACED_BY_BOOTSTRAP_BADGE",
  userPoolId: "REPLACED_BY_BOOTSTRAP",
  spaClientId: "REPLACED_BY_BOOTSTRAP",
  // URL-encoded ARN of the supervisor agent runtime (set after Lab 1's deploy
  // by scripts/wire-ui.sh). Until then the UI shows a friendly "not deployed
  // yet" message - which is exactly what Lab 0 wants you to see.
  agentArnEncoded: "",
};
