"""Plain-English event-day questions default to the upcoming London conference."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agenteng.config import Settings
from agenteng.models import Request
from agenteng.service import Service

LONDON = "agenteng-london-2026"
FULLY_BOOKED = "We are fully booked and it will be busy, but there will be seats for everyone."


@pytest.fixture
def eve():
    return Service(Settings(), clock=lambda: datetime(2026, 10, 15, 13, tzinfo=UTC))


def ask(service, query, operation="ask"):
    return service.lookup(Request(operation=operation, query=query))


@pytest.mark.parametrize("operation", ["ask", "chat"])
@pytest.mark.parametrize(
    "query",
    ["When do doors open?", "When do doors open in London?", "What time does it start?"],
)
def test_doors_and_times(eve, query, operation):
    result = ask(eve, query, operation)
    assert result.status == "ok"
    assert result.answer.startswith("Doors 08:00. Arrive 8:30 to 8:45, be seated by 8:50")
    assert "9:00 sharp" in result.answer
    assert [s["id"] for s in result.data["sections"]] == ["arriving"]
    assert {s.id for s in result.sources} == {"guide", "guide-arriving"}


@pytest.mark.parametrize(
    "query", ["How do I get to the venue?", "How do I get to Everyman?", "Directions to the venue"]
)
def test_directions(eve, query):
    result = ask(eve, query)
    assert result.answer.startswith("Everyman Canary Wharf, Crossrail Place, London E14 5AR.")
    assert "Canary Wharf Elizabeth line station" in result.answer
    assert "https://www.youtube.com/watch?v=GPmvi7qjiwA" in result.answer
    assert [s["id"] for s in result.data["sections"]] == ["getting-here"]
    assert {s.id for s in result.sources} == {"london-venue-directions", "guide-getting-here"}


@pytest.mark.parametrize("query", ["Where is registration?", "Where is registration in London?"])
def test_registration_location(eve, query):
    result = ask(eve, query)
    assert result.answer.startswith(
        "Registration is on the left-hand side when you arrive at Everyman."
    )
    assert "badge and lanyard" in result.answer
    assert result.answer.count("Registration is on the left") == 1
    assert [s["id"] for s in result.data["sections"]] == ["registration"]
    assert "guide-registration" in {s.id for s in result.sources}


@pytest.mark.parametrize(
    "query",
    ["Are tickets available?", "Can I still buy a ticket?", "Is London sold out?", "ticket prices"],
)
def test_ticket_questions_are_fully_booked(eve, query):
    result = ask(eve, query)
    assert result.status == "ok"
    assert FULLY_BOOKED in result.answer
    assert result.data["registration_status"] == "fully_booked"
    assert result.data["current_offers"] == []
    assert "london-ticket-terms" not in {s.id for s in result.sources}
    assert all(s.kind != "tickets" for s in result.sources)


def test_unrelated_how_do_i_get_questions_are_not_directions(eve):
    assert "Best way in" not in ask(eve, "How do I get an invoice?").answer


def test_agenda_wording_is_soft_for_fully_booked(eve):
    result = eve.lookup(Request(operation="agenda", event_id=LONDON))
    assert "subject to registration" not in result.answer
    assert "fully booked" in result.answer
    assert "fully booked" in ask(eve, "What's the agenda?").answer


def test_san_francisco_still_works_when_named(eve):
    sf = ask(eve, "San Francisco tickets")
    assert sf.data["event_id"] == "sf-code-engineering-2026"
    assert "fully booked" not in sf.answer
    when = ask(eve, "When is the SF event?")
    assert {e["city"] for e in when.data} == {"San Francisco"}
    venue = ask(eve, "How do I get to the San Francisco venue?")
    assert "Everyman" not in venue.answer


def test_no_default_after_the_conference():
    after = Service(Settings(), clock=lambda: datetime(2026, 10, 17, 12, tzinfo=UTC))
    assert after.default_conference() is None
    assert not ask(after, "When do doors open?").answer.startswith("Doors 08:00")


def test_on_the_day_still_defaults():
    today = Service(Settings(), clock=lambda: datetime(2026, 10, 16, 7, 30, tzinfo=UTC))
    assert today.default_conference().id == LONDON
    assert ask(today, "Where is registration?").answer.startswith("Registration is on the left")
