"""Stdio bridge for clients that need a hosted AgentEng service through a CLI."""

import httpx

from .config import Settings
from .discovery import validate_origin
from .models import Result


class RemoteService:
    def __init__(self, url, *, transport=None):
        self.url = validate_origin(url)
        self.transport = transport
        # Broad remote tools conservatively advertise potential writes. The
        # remote operator still controls actual intake and authorization.
        self.settings = Settings(public_url=self.url, enable_intake=True)

    async def execute(self, request, *, token=None):
        headers = {"Authorization": "Bearer " + token} if token else {}
        async with httpx.AsyncClient(timeout=50, transport=self.transport) as client:
            response = await client.post(
                self.url + "/v1/query", json=request.model_dump(mode="json"), headers=headers
            )
            response.raise_for_status()
            return Result.model_validate(response.json())
