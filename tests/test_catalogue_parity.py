"""Website catalogue parity and local engagement helpers."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from click.testing import CliRunner

from agenteng.cli import main
from agenteng.config import Settings
from agenteng.models import Request
from agenteng.service import Service

LONDON = "agenteng-london-2026"


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTENG_CONFIG_DIR", str(tmp_path))
    return Service(Settings.from_env())


def test_speaker_detail_includes_website_fields(service):
    result = service.lookup(Request(operation="speaker", speaker_id="samuel-colvin"))
    assert result.status == "ok"
    data = result.data
    assert data["company_url"].startswith("https://")
    assert data["links"]["github"]
    assert data["projects"]
    assert "harness" in data["disciplines"]
    assert data["abstract"] and "Constrained Optimization" in data["talk_title"]
    assert data["location"]["city"] == "London"


def test_talks_search_returns_full_abstract(service):
    result = service.lookup(
        Request(operation="talks", event_id=LONDON, query="bigger context window")
    )
    assert result.status == "ok"
    assert len(result.data) >= 1
    talk = result.data[0]
    assert talk["abstract"]
    assert talk["speaker_id"] == "tobie-morgan-hitchcock"


def test_faq_venue_sponsors_conduct_themes(service):
    faq = service.lookup(Request(operation="faq", query="code of conduct"))
    assert faq.status == "ok" and faq.data
    venue = service.lookup(Request(operation="venue", event_id=LONDON))
    assert venue.status == "ok"
    assert "Everyman" in venue.data["venue"]
    assert venue.data["venue_tour_url"].startswith("https://")
    sponsors = service.lookup(Request(operation="sponsors"))
    assert sponsors.status == "ok"
    assert {s["id"] for s in sponsors.data["sponsors"]} >= {"arize-ai", "cocoindex"}
    assert sponsors.data["support_options"]
    conduct = service.lookup(Request(operation="conduct"))
    assert conduct.status == "ok"
    assert conduct.data["report_email"] == "conduct@super-agentic.ai"
    assert "\N{EM DASH}" not in conduct.data["summary"]
    themes = service.lookup(Request(operation="themes"))
    assert themes.status == "ok" and len(themes.data) == 4


@pytest.mark.parametrize(
    ("query", "faq_id"),
    [("travel", "faq-20"), ("accommodation", "faq-20"), ("visa", "faq-21")],
)
def test_travel_and_visa_faqs_are_searchable_with_source_attribution(service, query, faq_id):
    result = service.lookup(Request(operation="faq", event_id=LONDON, query=query))
    assert result.status == "ok"
    assert [row["id"] for row in result.data] == [faq_id]
    assert result.data[0]["source_ids"] == [faq_id]
    assert [source.id for source in result.sources] == [faq_id]
    assert str(result.sources[0].url) == "https://agentengineering.world/#faq"


def test_now_and_next(service, tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTENG_CONFIG_DIR", str(tmp_path))
    live = Service(
        Settings.from_env(),
        clock=lambda: datetime(2026, 10, 16, 9, 20, tzinfo=ZoneInfo("Europe/London")),
    )
    now = live.lookup(Request(operation="now", event_id=LONDON))
    assert now.status == "ok"
    assert now.data["session"]["speaker_id"] == "sergey-ignatov"
    nxt = live.lookup(Request(operation="next", event_id=LONDON))
    assert nxt.status == "ok"
    assert nxt.data["session"]["speaker_id"] == "meryem-arik"


def test_discover_has_no_em_dash(service):
    result = service.lookup(Request(operation="discover"))
    assert "\N{EM DASH}" not in result.data["conference_name"]
    assert ":" in result.data["conference_name"]


def test_cli_speaker_and_talk_json(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTENG_CONFIG_DIR", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(main, ["--json", "speaker", "sergey-ignatov"])
    assert result.exit_code == 0
    assert "Lead ACP maintainer" in result.output
    assert "\N{EM DASH}" not in result.output
    result = runner.invoke(main, ["--json", "talk", "sergey-ignatov"])
    assert result.exit_code == 0
    assert "Agentic Coding and ACP" in result.output
    result = runner.invoke(
        main, ["--json", "agenda", LONDON, "--format", "ics", "--output", str(tmp_path / "a.ics")]
    )
    assert result.exit_code == 0
    assert (tmp_path / "a.ics").read_text().startswith("BEGIN:VCALENDAR")
