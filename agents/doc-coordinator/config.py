import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    region: str = os.environ.get("AWS_REGION", "us-east-1")
    table_name: str = os.environ.get("TABLE_NAME", "loanbuddy-applications")
    docs_bucket: str = os.environ.get("DOCS_BUCKET", "")
    registry_url: str = os.environ.get("REGISTRY_URL", "")
    # Vision-capable model for the specialists
    model_id: str = os.environ.get(
        "MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    )

    @property
    def browser_enabled(self) -> bool:
        """Lab 5 sets REGISTRY_URL; before that, employer checks are skipped."""
        return bool(self.registry_url)


CFG = Config()
