"""Stdio bridge for clients that need a hosted AgentEng service through a CLI."""

import httpx

from .config import Settings
from .discovery import validate_origin
from .models import Result


class RemoteService:
    def __init__(self, url, *, transport=None):
        self.url = validate_origin(url)
        self.transport = transport
        self.settings = Settings(public_url=self.url)

    async def execute(self, request, *, token=None):
        headers = {"Authorization": "Bearer " + token} if token else {}
        async with httpx.AsyncClient(timeout=50, transport=self.transport) as client:
            response = await client.post(
                self.url + "/v1/query",
                json=request.model_dump(mode="json", exclude_defaults=True),
                headers=headers,
            )
            response.raise_for_status()
            return Result.model_validate(response.json())
