"""Operator policy: requesting an engine never enables it."""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    public_url: str = "https://a2a.agentengineering.world"
    catalogue_path: str | None = None
    enable_standard: bool = False
    enable_rlm: bool = False
    operator_token: str = field(default="", repr=False)
    model_api_key: str = field(default="", repr=False)
    model_base_url: str = "https://api.openai.com/v1"
    model: str = ""
    allowed_origins: tuple[str, ...] = ("https://agentengineering.world",)
    max_age_hours: int = 48
    max_model_calls: int = 6
    max_output_tokens: int = 1200
    max_reserved_tokens: int = 12000
    request_timeout: float = 45
    enable_intake: bool = False
    inbox_path: str | None = None
    calls_path: str | None = None
    intake_privacy_notice: str = ""
    intake_retention_days: int = 90
    intake_capacity: int = 1000

    @classmethod
    def from_env(cls):
        return cls(
            public_url=os.getenv("AGENTENG_PUBLIC_URL", cls.public_url).rstrip("/"),
            catalogue_path=os.getenv("AGENTENG_CATALOGUE"),
            enable_standard=os.getenv("AGENTENG_ENABLE_STANDARD") == "1",
            enable_rlm=os.getenv("AGENTENG_ENABLE_RLM") == "1",
            operator_token=os.getenv("AGENTENG_OPERATOR_TOKEN", ""),
            model_api_key=os.getenv("AGENTENG_MODEL_API_KEY", ""),
            model_base_url=os.getenv("AGENTENG_MODEL_BASE_URL", cls.model_base_url),
            model=os.getenv("AGENTENG_MODEL", ""),
            enable_intake=os.getenv("AGENTENG_ENABLE_INTAKE") == "1",
            inbox_path=os.getenv("AGENTENG_INBOX"),
            calls_path=os.getenv("AGENTENG_CALLS"),
            intake_privacy_notice=os.getenv("AGENTENG_INTAKE_PRIVACY_NOTICE", ""),
            intake_retention_days=int(os.getenv("AGENTENG_INTAKE_RETENTION_DAYS", "90")),
            intake_capacity=int(os.getenv("AGENTENG_INTAKE_CAPACITY", "1000")),
            allowed_origins=tuple(
                x.strip()
                for x in os.getenv(
                    "AGENTENG_ALLOWED_ORIGINS", "https://agentengineering.world"
                ).split(",")
                if x.strip()
            ),
        )
