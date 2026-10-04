"""Load and validate the local immutable public snapshot."""

from importlib.resources import files

from .models import Catalogue


def load_catalogue(path: str | None = None) -> Catalogue:
    if path:
        from pathlib import Path

        payload = Path(path).read_text()
    else:
        payload = files("agenteng").joinpath("data/catalogue.json").read_text()
    return Catalogue.model_validate_json(payload)
