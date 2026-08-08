# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Supervisor configuration.

Everything the labs wire up arrives as an environment variable set at deploy
time. Missing values mean "that lab hasn't happened yet" - the agent degrades
gracefully so Lab 1 can deploy before Memory or the Gateway exist.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    region: str = os.environ.get("AWS_REGION", "us-east-1")

    # Lab 0 (bootstrap stack)
    table_name: str = os.environ.get("TABLE_NAME", "loanbuddy-applications")
    docs_bucket: str = os.environ.get("DOCS_BUCKET", "")

    # Lab 2: AgentCore Memory
    memory_id: str = os.environ.get("MEMORY_ID", "")

    # Lab 3: Gateway + outbound Identity
    gateway_url: str = os.environ.get("GATEWAY_URL", "")
    gateway_provider_name: str = os.environ.get("GATEWAY_PROVIDER_NAME", "")
    gateway_scope: str = os.environ.get("GATEWAY_SCOPE", "loanbuddy-gateway/invoke")

    model_id: str = os.environ.get(
        "MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    )

    @property
    def memory_enabled(self) -> bool:
        return bool(self.memory_id)

    @property
    def gateway_enabled(self) -> bool:
        return bool(self.gateway_url and self.gateway_provider_name)


CFG = Config()
