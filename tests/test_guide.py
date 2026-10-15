"""The published /guide day guide, venue directions, tagline and registration status."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from agenteng.a2a import agent_card
from agenteng.catalogue import load_catalogue
from agenteng.cli import main
from agenteng.config import Settings
from agenteng.models import Catalogue, Request
from agenteng.output import make_console
from agenteng.render import render_result
from agenteng.service import Service

ROOT = Path(__file__).resolve().parents[1]
LONDON = "agenteng-london-2026"
SECTIONS = [
    "arriving",
    "getting-here",
    "registration",
    "social-area",
    "speaker-area",
    "lunch",
    "qna",
    "photography",
    "phones",
    "seating",
    "help",
    "after",
]
WALK = "https://www.youtube.com/watch?v=GPmvi7qjiwA"
HELP_LINKS = {
    "https://x.com/Shashikant86",
    "https://www.linkedin.com/in/shashikantjagtap",
    "https://x.com/AgentEngHQ",
    "https://www.linkedin.com/company/agent-engineering-hq/",
}


def at(day: str, hour: int = 12):
    return Service(
        Settings(), clock=lambda: datetime.fromisoformat(f"{day}T{hour:02d}:00:00+01:00")
    )


def run(*args):
    return CliRunner().invoke(main, list(args), env={"AGENTENG_OUTPUT": "json"})


def text(service, **request):
    console = make_console(record=True, width=100)
    render_result(service.lookup(Request(**request)), request["operation"], console)
    return console.export_text()


def test_guide_has_every_site_section_in_order(service):
    result = service.lookup(Request(operation="guide"))
    assert result.status == "ok"
    assert [s["id"] for s in result.data["sections"]] == SECTIONS
    assert result.data["url"] == "https://agentengineering.world/guide"
    facts = {f["label"]: f["value"] for f in result.data["facts"]}
    assert facts == {
        "Venue": "Everyman Canary Wharf, Crossrail Place, London E14 5AR",
        "Date": "Fri 16 October 2026",
        "Doors": "08:00",
        "Arrive": "8:30 to 8:45",
        "Be seated by": "8:50",
        "Programme starts": "9:00 sharp",
    }
    assert result.data["intro"].startswith(
        "There are many Agent conferences. This one is truly yours."
    )
    assert {s.id for s in result.sources} >= {"guide", "guide-help", "london-venue-directions"}


def test_guide_section_argument_aliases_and_list():
    service = at("2026-10-15")
    arriving = run("guide", "arriving")
    data = json.loads(arriving.output)["data"]
    assert arriving.exit_code == 0
    assert data["section"] == "arriving"
    assert "9:00 AM sharp" in " ".join(data["sections"][0]["paragraphs"])
    for alias, wanted in [
        ("directions", "getting-here"),
        ("Lunch and drinks", "lunch"),
        ("q-a", "qna"),
        ("registration-and-badges", "registration"),
    ]:
        assert json.loads(run("guide", alias).output)["data"]["section"] == wanted
    assert json.loads(run("guide", "--section", "help").output)["data"]["section"] == "help"
    listing = service.lookup(Request(operation="guide", section="list"))
    assert [s["id"] for s in listing.data["sections"]] == ["facts", *SECTIONS]
    assert json.loads(run("guide", "--list").output)["data"]["sections"][0]["id"] == "facts"
    missing = run("guide", "karaoke")
    assert missing.exit_code == 1
    assert "arriving" in json.loads(missing.output)["answer"]


def test_guide_is_london_only():
    assert run("guide", "--london").exit_code == 0
    assert run("guide", "--sf").exit_code == 1
    assert run("guide", "--event", "sf-code-engineering-2026").exit_code == 1


@pytest.mark.parametrize(
    "day, phase, lead",
    [
        ("2026-10-10", "before", "See you on 16 October at Everyman, Canary Wharf."),
        ("2026-10-15", "eve", "See you tomorrow at Everyman"),
        ("2026-10-16", "today", "See you today at Everyman"),
        ("2026-10-17", "after", "Thanks for coming to Agent Engineering London."),
    ],
)
def test_guide_lead_follows_the_london_date(day, phase, lead):
    data = at(day).lookup(Request(operation="guide")).data
    assert data["phase"] == phase
    assert data["lead"].startswith(lead)


def test_help_contacts_are_only_what_the_guide_publishes(service):
    data = service.lookup(Request(operation="guide", section="help")).data
    assert {link["url"] for link in data["help"]["online"]} == HELP_LINKS
    people = {p["name"]: p["role"] for p in data["help"]["on_site"]}
    assert people == {
        "James": "Associate",
        "Gloria": "Associate",
        "Shashi": None,
        "Everyman staff": None,
    }


def test_venue_has_published_directions_and_times(service):
    data = service.lookup(Request(operation="venue", event_id=LONDON)).data
    assert data["venue"] == "Everyman Canary Wharf, Crossrail Place, London E14 5AR"
    assert data["best_way_in"].startswith("Canary Wharf Elizabeth line station.")
    assert "Jubilee, DLR or car" in data["best_way_in"]
    assert data["walk_video_url"] == WALK
    assert data["registration"] == "Registration is on the left as you walk in."
    assert (data["doors"], data["arrive"], data["seated_by"], data["programme_starts"]) == (
        "08:00",
        "8:30 to 8:45",
        "8:50",
        "9:00 sharp",
    )
    assert {link["url"] for link in data["help"]["online"]} == HELP_LINKS
    sf = service.lookup(Request(operation="venue", event_id="sf-code-engineering-2026")).data
    assert "best_way_in" not in sf


def test_about_and_event_carry_the_tagline(service):
    about = service.lookup(Request(operation="about")).data
    assert about["truly_yours"]["tagline"] == (
        "There are many Agent conferences. This one is truly yours."
    )
    assert about["truly_yours"]["title"] == "Why this one is truly yours"
    assert about["truly_yours"]["text"].startswith("Most agent conferences answer to sponsors.")
    assert about["links"]["day_guide"] == "https://agentengineering.world/guide"
    event = service.lookup(Request(operation="event", event_id=LONDON)).data[0]
    assert event["tagline"].endswith("This one is truly yours.")
    assert event["registration_status"] == "fully_booked"


def test_rich_cards(service):
    guide = text(service, operation="guide")
    assert "Day guide: quick facts" in guide and "Need help on the day" in guide
    assert "Be seated by" in guide and WALK in guide
    venue = text(service, operation="venue", event_id=LONDON)
    assert "Best way in:" in venue and "Times" in venue and "Programme starts" in venue
    tickets = text(service, operation="tickets", event_id=LONDON)
    assert "fully booked" in tickets and "agenteng guide" in tickets
    assert "£" not in tickets and "Register:" not in tickets and "luma.com" not in tickets
    event = text(service, operation="event", event_id=LONDON)
    assert "Register:" not in event and "From £" not in event and "truly yours" in event
    about = text(service, operation="about")
    assert "Why this one is truly yours" in about


def test_guide_over_protocol_descriptions():
    card = agent_card(Service(Settings()))
    skills = {s.id: s for s in card.skills}
    assert "guide" in skills["agenteng-event-day"].description
    assert any('"operation":"guide"' in e for e in skills["agenteng-event-day"].examples)
    assert not any('"tickets"' in e for s in card.skills for e in s.examples)


def test_guide_text_has_no_em_dashes_and_is_cited():
    raw = (ROOT / "src/agenteng/data/catalogue.json").read_text()
    assert "\N{EM DASH}" not in raw
    catalogue = load_catalogue()
    assert catalogue.guide and catalogue.guide.event_id == LONDON
    data = catalogue.model_dump(mode="json")
    data["guide"]["source_ids"] = ["invented"]
    with pytest.raises(ValueError):
        Catalogue.model_validate(data)


def test_menu_lists_the_day_guide():
    source = (ROOT / "src/agenteng/interactive.py").read_text()
    assert '"guide"' in source and "Day guide" in source


def test_guide_rejected_sections_for_other_operations():
    with pytest.raises(ValueError):
        Request(operation="hq", section="arriving")
    assert Request(operation="guide", section="arriving").section == "arriving"
