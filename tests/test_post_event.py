"""After AgentEng London 2026 (16 October 2026): date-driven past-event behaviour."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import click
import pytest

from agenteng import interactive
from agenteng.config import Settings
from agenteng.discovery import discovery
from agenteng.models import Request
from agenteng.output import make_console
from agenteng.render import render_result
from agenteng.service import Service

LONDON = "agenteng-london-2026"


@pytest.fixture
def after():
    return Service(Settings(), clock=lambda: datetime(2026, 10, 17, 11, tzinfo=UTC))


@pytest.fixture
def before():
    return Service(Settings(), clock=lambda: datetime(2026, 10, 15, 13, tzinfo=UTC))


def card(service, operation, **kwargs):
    console = make_console(record=True, width=100)
    render_result(service.lookup(Request(operation=operation, **kwargs)), operation, console)
    return console.export_text()


def ask(service, query):
    return service.lookup(Request(operation="ask", query=query))


def test_registration_note_is_past_with_no_guide_pointer(after, before):
    result = after.lookup(Request(operation="tickets", event_id=LONDON))
    assert result.answer == "AgentEng London 2026: The event was fully booked."
    assert result.data["registration_note"] == "The event was fully booked."
    assert result.data["day_guide_url"] is None
    assert not {s.id for s in result.sources} & {"guide", "guide-seating"}
    event = after.lookup(Request(operation="event", event_id=LONDON)).data[0]
    assert event["registration_note"] == "The event was fully booked."
    text = card(after, "tickets", event_id=LONDON)
    assert "The event was fully booked." in text and "agenteng guide" not in text
    # Before the event the guide pointer stays.
    assert "Day guide:" in before.lookup(Request(operation="tickets", event_id=LONDON)).answer


def test_regenerated_faq_drops_removed_answers(after):
    questions = " ".join(f.question for f in after.catalogue.faqs).casefold()
    for gone in ["team", "approval step", "refund", "food is provided"]:
        assert gone not in questions
    answers = " ".join(f.answer for f in after.catalogue.faqs).casefold()
    assert "dietary" not in answers


def test_agenda_answer_names_the_date(after, before):
    result = after.lookup(Request(operation="agenda", event_id=LONDON))
    assert result.answer.endswith("This is the published agenda from 16 October 2026.")
    pre = before.lookup(Request(operation="agenda", event_id=LONDON))
    assert "fully booked" in pre.answer
    assert ask(after, "Show the AgentEng London 2026 programme").answer == result.answer


def test_discovery_prompt(after, before):
    assert "Show the AgentEng London 2026 programme" in discovery(after)["suggested_questions"]
    assert "Show the public agenda for AgentEng London" in discovery(before)["suggested_questions"]


def _ctx():
    return click.Context(
        click.Command("ae"), obj={"remote": None, "catalogue": None, "as_json": False}
    )


@pytest.mark.parametrize("archived", [True, False])
def test_menu_labels(monkeypatch, archived):
    seen = []
    monkeypatch.setattr(interactive, "_guide_archived", lambda ctx: archived)
    monkeypatch.setattr(
        interactive, "_select", lambda m, c, **k: seen.append([x.title for x in c]) or "quit"
    )
    interactive.run_menu(_ctx())
    if archived:
        assert "Day guide (archive)" in seen[0]
        assert not any("now/next" in t for t in seen[0])
    else:
        assert "Day guide: London, Fri 16 Oct 2026" in seen[0]
        assert "Live now/next board (venue screen)" in seen[0]


def test_event_submenu_for_past_london(monkeypatch):
    seen = []
    monkeypatch.setattr(
        interactive, "_select", lambda m, c, **k: seen.append([x.title for x in c]) or None
    )
    interactive._event_submenu(_ctx(), {"id": LONDON, "city": "London", "state": "past"})
    assert "Day guide (archive)" in seen[0]
    assert "What's on now / next" not in seen[0]


def test_venue_hides_times_and_help_when_past(after, before):
    data = after.lookup(Request(operation="venue", event_id=LONDON)).data
    for key in ("doors", "arrive", "seated_by", "programme_starts", "help"):
        assert key not in data
    text = card(after, "venue", event_id=LONDON)
    assert "Times" not in text and "Need help on the day" not in text
    assert "Day guide (archive):" in text
    pre = before.lookup(Request(operation="venue", event_id=LONDON)).data
    assert pre["doors"] == "08:00" and pre["help"]


def test_event_link_is_event_page_when_past(after, before):
    text = card(after, "event", event_id=LONDON)
    assert "Event page: https://luma.com/agentenglondon" in text
    assert "Register:" not in text and "agenteng guide for the day guide" not in text
    pre = card(before, "event", event_id=LONDON)
    assert "Event page:" not in pre and "agenteng guide" in pre


def test_guide_lead_is_past_tense(after):
    data = after.lookup(Request(operation="guide")).data
    assert data["phase"] == "after"
    assert data["lead"] == "Thanks for coming to Agent Engineering London."
    assert "Day guide (archive): quick facts" in card(after, "guide")


def test_doors_question_answers_in_the_past(after, before):
    result = ask(after, "When do doors open?")
    assert result.answer == (
        "AgentEng London 2026 took place on 16 October 2026 at Everyman Canary Wharf, "
        "Crossrail Place, London E14 5AR. Doors opened at 08:00 and the programme started at 9:00."
    )
    assert ask(before, "When do doors open?").answer.startswith("Doors 08:00.")


def test_ask_routing_falls_back_to_the_past_conference(after):
    talk = ask(after, "Who is talking about memory?")
    assert "presented" in talk.answer and "Held on 16 October 2026" in talk.answer
    assert "is presenting" not in talk.answer
    assert ask(after, "Can I still get a ticket?").answer.endswith("The event was fully booked.")
    lunch = ask(after, "Where is lunch?")
    assert lunch.answer.startswith("AgentEng London 2026 took place on 16 October 2026")
    sf = ask(after, "When is the San Francisco event?")
    assert {s.id for s in sf.sources} == {"sf-harness-engineering-2026", "sf-code-engineering-2026"}
    assert after.default_conference() is None
    assert after.past_conference().id == LONDON


def test_no_em_dashes_in_post_event_answers(after):
    payload = json.dumps(
        [
            after.lookup(Request(operation=op, event_id=LONDON)).model_dump(mode="json")
            for op in ("tickets", "venue", "agenda", "event")
        ]
    )
    assert "\u2014" not in payload


def test_time_answers_are_past_tense(after, before):
    at_ten = ask(after, "Who is speaking at 10:00?")
    assert at_ten.answer == (
        "At 10:00 on 16 October 2026: Inference Engineering for Long-Running Agents "
        "(presented by Meryem Arik)."
    )
    assert [s.id for s in at_ten.sources] == ["london-session-3"]
    for query in ["What is the next talk?", "What's on now?"]:
        answer = ask(after, query).answer
        assert answer.startswith("AgentEng London 2026 ended on 16 October 2026.")
        assert "https://agentengineering.world/london-2026/agenda" in answer
        assert "agenteng agenda agenteng-london-2026" in answer
    for op in ("now", "next"):
        answer = after.lookup(Request(operation=op, event_id=LONDON)).answer
        assert not answer.startswith(("Now:", "Next:")), op
    early = ask(after, "Who is speaking at 7:00?")
    assert early.status == "not_found" and "Nothing was scheduled at 07:00" in early.answer
    text = card(after, "now", event_id=LONDON, at=datetime(2026, 10, 16, 9, tzinfo=UTC))
    assert "At 10:00 on 16 October 2026" in text and "Now" not in text.split("\n")[0]
    # Before the event the live wording stays.
    assert ask(before, "Who is speaking at 10:00?").answer.startswith("Now:")
    assert ask(before, "What is the next talk?").answer.startswith("Next:")
