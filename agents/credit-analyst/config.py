# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    region: str = os.environ.get("AWS_REGION", "us-east-1")
    table_name: str = os.environ.get("TABLE_NAME", "loanbuddy-applications")

    # This agent is a Gateway CLIENT too: it calls get_credit_report through
    # the same Gateway that fronts it, with its own OAuth credential.
    gateway_url: str = os.environ.get("GATEWAY_URL", "")
    gateway_provider_name: str = os.environ.get("GATEWAY_PROVIDER_NAME", "")
    gateway_scope: str = os.environ.get("GATEWAY_SCOPE", "loanbuddy-gateway/invoke")

    model_id: str = os.environ.get(
        "MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    )

    # Re-use a credit pull if it is fresher than this (mirrors real lenders
    # avoiding repeated hard pulls; also makes the day-3 return snappy).
    credit_freshness_days: int = int(os.environ.get("CREDIT_FRESHNESS_DAYS", "30"))


CFG = Config()
