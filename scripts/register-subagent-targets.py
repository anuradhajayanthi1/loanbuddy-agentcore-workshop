#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Register (or re-register) the subagent runtimes as mcpServer targets on
the LoanBuddy gateway, with OAuth client-credentials the Gateway presents to
each JWT-authorized runtime.

Why a script instead of the agentcore CLI: the CLI's create-mcp-gateway-target
only wires credentials for openApiSchema targets; mcpServer targets need an
explicit credential provider configuration.

Usage:
    python3 scripts/register-subagent-targets.py [--region us-east-1]

Idempotent: existing targets with the same names are replaced.
"""
import argparse
import sys
import time

import boto3

SUBAGENTS = {
    "doc-coordinator": "loanbuddy_doc_coordinator",
    "credit-analyst": "loanbuddy_credit_analyst",
}
GATEWAY_NAME = "loanbuddy-gateway"
PROVIDER_NAME = "loanbuddy-gateway-access"
SCOPE = "loanbuddy-gateway/invoke"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="us-east-1")
    args = ap.parse_args()
    client = boto3.client("bedrock-agentcore-control", region_name=args.region)
    account = boto3.client("sts", region_name=args.region).get_caller_identity()["Account"]

    # -- discover the gateway --
    gateways = client.list_gateways()["items"]
    gw = next((g for g in gateways if g["name"] == GATEWAY_NAME), None)
    if gw is None:
        print(f"Gateway '{GATEWAY_NAME}' not found - run Lab 3 first.")
        return 1
    gw_id = gw["gatewayId"]

    # -- discover the credential provider --
    providers = client.list_oauth2_credential_providers()["credentialProviders"]
    provider = next((p for p in providers if p["name"] == PROVIDER_NAME), None)
    if provider is None:
        print(f"Credential provider '{PROVIDER_NAME}' not found - run Lab 3 first.")
        return 1
    provider_arn = provider["credentialProviderArn"]

    # -- discover the subagent runtimes --
    runtimes = client.list_agent_runtimes(maxResults=50)["agentRuntimes"]
    existing = {t["name"]: t["targetId"]
                for t in client.list_gateway_targets(gatewayIdentifier=gw_id)["items"]}

    for target_name, runtime_prefix in SUBAGENTS.items():
        rt = next((r for r in runtimes
                   if r["agentRuntimeName"].startswith(runtime_prefix)), None)
        if rt is None:
            print(f"Runtime '{runtime_prefix}*' not found - deploy it first (Lab 4).")
            return 1
        rt_id = rt["agentRuntimeArn"].split("/")[-1]
        enc = (f"arn%3Aaws%3Abedrock-agentcore%3A{args.region}%3A{account}%3A"
               f"runtime%2F{rt_id}")
        endpoint = (f"https://bedrock-agentcore.{args.region}.amazonaws.com/"
                    f"runtimes/{enc}/invocations?qualifier=DEFAULT")

        if target_name in existing:
            client.delete_gateway_target(gatewayIdentifier=gw_id,
                                         targetId=existing[target_name])
            while True:
                try:
                    client.get_gateway_target(gatewayIdentifier=gw_id,
                                              targetId=existing[target_name])
                    time.sleep(3)
                except client.exceptions.ResourceNotFoundException:
                    break
            print(f"replaced existing target: {target_name}")

        resp = client.create_gateway_target(
            gatewayIdentifier=gw_id,
            name=target_name,
            targetConfiguration={"mcp": {"mcpServer": {"endpoint": endpoint}}},
            credentialProviderConfigurations=[{
                "credentialProviderType": "OAUTH",
                "credentialProvider": {
                    "oauthCredentialProvider": {
                        "providerArn": provider_arn,
                        "scopes": [SCOPE],
                        "grantType": "CLIENT_CREDENTIALS",
                    }
                },
            }],
        )
        tid = resp["targetId"]
        status = "CREATING"
        for _ in range(60):
            status = client.get_gateway_target(
                gatewayIdentifier=gw_id, targetId=tid)["status"]
            if status in ("READY", "FAILED"):
                break
            time.sleep(5)
        print(f"{target_name}: {status} (target {tid})")
        if status != "READY":
            return 1

    print("All subagent targets registered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
