"""Offline, attributed tool listings shared by all AgentEng transports."""

from __future__ import annotations

from datetime import datetime
from importlib.resources import files
import re
from typing import Literal, TYPE_CHECKING

from pydantic import Field, HttpUrl, field_validator, model_validator

from .contracts import Model

if TYPE_CHECKING:
    from .models import Request, Result

DisciplineID = Literal[
    "prompt",
    "context",
    "harness",
    "eval",
    "memory",
    "inference",
    "loop",
    "agentic",
    "code",
    "protocol",
    "graph",
    "search",
]
ToolKind = Literal[
    "agent",
    "framework",
    "cli",
    "ide",
    "extension",
    "sandbox",
    "connector",
    "protocol",
    "registry",
    "model",
    "runtime",
    "hosting",
    "database",
    "search",
    "evaluation",
    "observability",
    "security",
    "browser",
    "app",
    "embedding",
    "documentation",
]
TOOL_OPERATIONS = frozenset({"disciplines", "tools", "tool"})
DISCIPLINES = {
    "prompt": "Prompt Engineering",
    "context": "Context Engineering",
    "harness": "Harness Engineering",
    "eval": "Eval Engineering",
    "memory": "Memory Engineering",
    "inference": "Inference Engineering",
    "loop": "Loop Engineering",
    "agentic": "Agentic Engineering",
    "code": "Code Engineering",
    "protocol": "Protocol Engineering",
    "graph": "Graph Engineering",
    "search": "Search Engineering",
}


def clean_text(value: str) -> str:
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Directory text cannot contain control characters")
    return value


class Tool(Model):
    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=128)
    name: str = Field(min_length=1, max_length=160)
    aliases: list[str] = Field(default_factory=list, max_length=30)
    source_ids: list[str] = Field(min_length=1, max_length=30)
    derived_from: str | None = Field(default=None, max_length=128)
    categories: list[str] = Field(min_length=1, max_length=30)
    disciplines: list[DisciplineID] = Field(min_length=1, max_length=12)
    kind: ToolKind
    website_url: HttpUrl | None = None
    repository_url: HttpUrl | None = None
    docs_url: HttpUrl | None = None
    status: Literal["listed", "hold", "deprecated"] = "listed"
    verification: Literal["source_listed", "identity_checked"] = "source_listed"

    @field_validator("name")
    @classmethod
    def valid_name(cls, value):
        return clean_text(value)

    @field_validator("aliases", "source_ids", "categories")
    @classmethod
    def valid_labels(cls, values):
        if len(values) != len(set(values)):
            raise ValueError("Duplicate directory labels")
        for value in values:
            if not value.strip() or len(value) > 160:
                raise ValueError("Invalid directory label")
            clean_text(value)
        return values

    @field_validator("website_url", "repository_url", "docs_url")
    @classmethod
    def safe_link(cls, value):
        if value and (value.username or value.password):
            raise ValueError("Directory links cannot contain credentials")
        return value

    @model_validator(mode="after")
    def valid_listing(self):
        if not (self.website_url or self.repository_url):
            raise ValueError("Listings need a public website or repository")
        if len(self.disciplines) != len(set(self.disciplines)):
            raise ValueError("Duplicate discipline tags")
        return self


class DirectorySource(Model):
    url: HttpUrl
    commit: str = Field(pattern=r"^[a-f0-9]{40}$")
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    updated_at: datetime
    entry_count: int = Field(ge=1, le=10000)

    @model_validator(mode="after")
    def valid_source(self):
        if self.updated_at.utcoffset() is None:
            raise ValueError("Source timestamp must include its timezone")
        if self.url.username or self.url.password:
            raise ValueError("Source URL cannot contain credentials")
        expected = (
            "https://github.com/SuperagenticAI/superradar/blob/"
            + self.commit
            + "/superradar-tools.json"
        )
        if str(self.url) != expected:
            raise ValueError("Directory source must pin the allowed repository and commit")
        return self


class ToolDirectory(Model):
    schema_version: Literal[1] = 1
    version: str = Field(min_length=1, max_length=128)
    source: DirectorySource
    tools: list[Tool] = Field(min_length=1, max_length=10000)

    @model_validator(mode="after")
    def valid_references(self):
        identifiers = [tool.id for tool in self.tools]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Duplicate tool IDs")
        owners = {tool.id: tool.id for tool in self.tools}
        for tool in self.tools:
            if tool.derived_from:
                parent = next((t for t in self.tools if t.id == tool.derived_from), None)
                if (
                    not parent
                    or parent is tool
                    or not set(tool.source_ids) <= set(parent.source_ids)
                ):
                    raise ValueError("Invalid derived listing provenance")
                continue
            for alias in tool.source_ids:
                if alias in owners and owners[alias] != tool.id:
                    raise ValueError("Ambiguous source ID alias")
                owners[alias] = tool.id
        if len({sid for t in self.tools for sid in t.source_ids}) != self.source.entry_count:
            raise ValueError("Source coverage does not match the declared entry count")
        return self

    def metadata(self):
        return {
            "version": self.version,
            "source": self.source.model_dump(mode="json"),
            "listing_count": len(self.tools),
            "ordering": "alphabetical",
            "note": "Names and links are attributed to SuperRadar. Discipline tags are AgentEng "
            "classifications. Listing is not endorsement, integration or a popularity ranking; "
            "source_listed details have not been independently verified.",
        }

    def lookup(self, request: Request, now: datetime, max_age_hours: int) -> Result:
        from .models import Result, Source

        metadata = self.metadata()
        status = "ok"
        if request.operation == "disciplines":
            rows = [
                {
                    "id": key,
                    "name": name,
                    "tool_count": sum(
                        key in t.disciplines and t.status == "listed" for t in self.tools
                    ),
                    "total_tool_count": sum(key in t.disciplines for t in self.tools),
                }
                for key, name in DISCIPLINES.items()
            ]
            data = {
                "items": rows,
                "categories": sorted({c for t in self.tools for c in t.categories}),
                "kinds": sorted({t.kind for t in self.tools}),
                "directory": metadata,
            }
            answer = "12 agent-engineering disciplines. Tools can appear in several disciplines."
        elif request.operation == "tool":
            tool = next((t for t in self.tools if request.tool_id == t.id), None)
            if tool is None:
                tool = next(
                    (
                        t
                        for t in self.tools
                        if not t.derived_from and request.tool_id in t.source_ids
                    ),
                    None,
                )
            data = {"tool": tool.model_dump(mode="json") if tool else None, "directory": metadata}
            answer = (
                f"{tool.name}: public listing and links."
                if tool
                else "Unknown tool ID. Use tools to find IDs."
            )
            status = "ok" if tool else "not_found"
        else:
            wanted = re.findall(r"[\w]+", request.query.casefold())
            rows = []
            for tool in self.tools:
                if request.tool_status != "all" and tool.status != request.tool_status:
                    continue
                if request.discipline and request.discipline not in tool.disciplines:
                    continue
                if request.kind and request.kind != tool.kind:
                    continue
                if request.category and not any(
                    request.category.casefold() == c.casefold() for c in tool.categories
                ):
                    continue
                searchable = " ".join(
                    [
                        tool.id,
                        tool.name,
                        *tool.aliases,
                        *tool.source_ids,
                        *tool.categories,
                        *tool.disciplines,
                        tool.kind,
                    ]
                ).casefold()
                if all(term in searchable for term in wanted):
                    rows.append(tool)
            rows.sort(key=lambda t: (t.name.casefold(), t.id))
            page = rows[request.offset : request.offset + request.limit]
            next_offset = request.offset + len(page)
            data = {
                "items": [t.model_dump(mode="json") for t in page],
                "total": len(rows),
                "offset": request.offset,
                "limit": request.limit,
                "next_offset": next_offset if next_offset < len(rows) else None,
                "directory": metadata,
            }
            answer = f"{len(page)} of {len(rows)} matching listings."
        return Result(
            answer=answer,
            data=data,
            status=status,
            catalogue_version=self.version,
            evaluated_at=now,
            published_at=self.source.updated_at,
            stale=(now - self.source.updated_at).total_seconds() > max_age_hours * 3600,
            sources=[
                Source(
                    id="superradar-tools",
                    url=self.source.url,
                    kind="tool_directory",
                    text="Public names and links from SuperRadar; AgentEng supplies discipline tags. "
                    "Source status and metadata are not independently verified adoption claims.",
                )
            ],
        )


def load_tool_directory() -> ToolDirectory:
    return ToolDirectory.model_validate_json(
        files("agenteng").joinpath("data/tools.json").read_text()
    )
