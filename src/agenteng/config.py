"""Operator policy: requesting an engine never enables it."""

import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit


def validate_origin(url: str) -> str:
    """Validate the origin shared by discovery, HTTP host checks and MCP."""
    parsed = urlsplit(url)
    if (
        not url
        or any(character.isspace() for character in url)
        or parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("Use an HTTP(S) origin without credentials, path, query or fragment")
    # Accessing port rejects malformed or out-of-range ports before serving requests.
    parsed.port
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Remote servers require HTTPS")
    return url.rstrip("/")


@dataclass(frozen=True)
class Settings:
    public_url: str = "https://a2a.agentengineering.world"
    catalogue_path: str | None = None
    enable_standard: bool = False
    enable_chat: bool = False
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

    def __post_init__(self):
        try:
            public_url = validate_origin(self.public_url)
        except ValueError:
            raise ValueError(
                "Invalid AGENTENG_PUBLIC_URL: set its value to an HTTPS origin such as "
                "https://a2a.agentengineering.world, without quotes, credentials or a path. "
                "HTTP is allowed only for local development."
            ) from None
        object.__setattr__(self, "public_url", public_url)

    @classmethod
    def from_env(cls):
        return cls(
            public_url=os.getenv("AGENTENG_PUBLIC_URL", cls.public_url).rstrip("/"),
            catalogue_path=os.getenv("AGENTENG_CATALOGUE"),
            enable_standard=os.getenv("AGENTENG_ENABLE_STANDARD") == "1",
            enable_chat=os.getenv("AGENTENG_ENABLE_CHAT") == "1",
            enable_rlm=os.getenv("AGENTENG_ENABLE_RLM") == "1",
            operator_token=os.getenv("AGENTENG_OPERATOR_TOKEN", ""),
            model_api_key=os.getenv("AGENTENG_MODEL_API_KEY", ""),
            model_base_url=os.getenv("AGENTENG_MODEL_BASE_URL", cls.model_base_url),
            model=os.getenv("AGENTENG_MODEL", ""),
            allowed_origins=tuple(
                x.strip()
                for x in os.getenv(
                    "AGENTENG_ALLOWED_ORIGINS", "https://agentengineering.world"
                ).split(",")
                if x.strip()
            ),
        )
