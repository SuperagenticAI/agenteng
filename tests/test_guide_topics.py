"""Plain-English guide topics, time questions, retired ticket text and ask cards."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from click.testing import CliRunner

from agenteng.cli import main
from agenteng.config import Settings
from agenteng.models import Request
from agenteng.output import make_console
from agenteng.render import render_result
from agenteng.service import Service

LONDON = "agenteng-london-2026"


@pytest.fixture
def eve():
    return Service(Settings(), clock=lambda: datetime(2026, 10, 15, 13, tzinfo=UTC))


def ask(service, query, operation="ask"):
    return service.lookup(Request(operation=operation, query=query))


@pytest.mark.parametrize(
    "query, section, phrase",
    [
        ("Is there coffee?", "lunch", "Tea and coffee are available throughout the day."),
        ("Where is lunch?", "lunch", "Lunch is Everyman's special pizzas"),
        ("What's for lunch?", "lunch", "pizza"),
        ("Are there drinks?", "lunch", "drinks"),
        ("Can I ask a question?", "qna", "One question per person, per talk"),
        ("How does Q&A work?", "qna", "dedicated Q&A time"),
        ("Who do I contact for help?", "help", "https://x.com/AgentEngHQ"),
        ("I need help", "help", "Find James, Gloria, Shashi or the Everyman staff."),
        ("What's on after?", "after", "Details will be shared during the day"),
        ("Is there an after party?", "after", "Drinks are buy your own"),
        ("Where do speakers go?", "speaker-area", "dedicated speaker area"),
        ("Is there a speaker room?", "speaker-area", "close to registration"),
        ("Can I take photos?", "photography", "official photography"),
        ("Can I use my laptop?", "phones", "Laptops are absolutely fine"),
        ("Should my phone be on silent?", "phones", "phone on silent"),
        ("Where is the bar?", "social-area", "The bar is the social area"),
        ("Where can I network?", "social-area", "networking"),
        ("Will there be seats?", "seating", "there will be seats for everyone"),
    ],
)
@pytest.mark.parametrize("operation", ["ask", "chat"])
def test_guide_topics(eve, query, section, phrase, operation):
    result = ask(eve, query, operation)
    assert result.status == "ok"
    assert result.data["section"] == section
    assert phrase in result.answer
    assert [s.id for s in result.sources] == [f"guide-{section}"]


@pytest.mark.parametrize("query", ["Where is lunch?", "Where is the bar?", "Where do speakers go?"])
def test_where_questions_never_list_events(eve, query):
    assert "published event(s)" not in ask(eve, query).answer


def test_after_party_is_the_guide_not_sponsorship(eve):
    result = ask(eve, "Is there an after party?")
    assert "support-after-party" not in {s.id for s in result.sources}


def test_wifi_stays_honest(eve):
    result = ask(eve, "Is there wifi?")
    assert "wifi" not in result.answer.casefold()
    assert "section" not in (result.data if isinstance(result.data, dict) else {})
    assert not any("wifi" in s.text.casefold() for s in result.sources)


def test_next_talk_and_now(eve):
    nxt = ask(eve, "What is the next talk?")
    assert nxt.answer == "Next: Doors, registration, tea and pastries."
    assert ask(eve, "What's next?").answer.startswith("Next:")
    now = ask(eve, "What's on now?")
    assert now.answer == "Nothing is on right now in the published agenda."


@pytest.mark.parametrize(
    "query, title",
    [
        ("Who is speaking at 10:00?", "Inference Engineering for Long-Running Agents"),
        ("What's on at 9:20?", "Agentic Coding in 2026"),
        ("Who is talking at 15.55?", "Memory Is Not a Bigger Context Window"),
    ],
)
def test_speaking_at_time(eve, query, title):
    result = ask(eve, query)
    assert result.status == "ok"
    assert result.data["session"]["title"].startswith(title)


def test_speaker_name_leads_with_the_card(eve):
    result = ask(eve, "Who is Alexander Korchagin?")
    assert result.data["id"] == "alexander-korchagin"
    assert result.sources[0].id == "speaker-alexander-korchagin"
    assert ask(eve, "Tell me about Korchagin").data["id"] == "alexander-korchagin"
    timed = ask(eve, "What time does Tobie Morgan Hitchcock's session start?")
    assert "15:50" in timed.answer


def test_unrelated_help_is_not_the_help_section(eve):
    result = ask(eve, "Can you help me with zyzzyva?")
    assert not isinstance(result.data, dict) or result.data.get("section") != "help"


def test_retired_ticket_text_is_never_cited_or_searched(eve):
    assert "london-ticket-terms" in eve.retired_sources
    # The site now publishes fully booked wording for faq-3, so it stays live.
    assert "faq-3" not in eve.retired_sources
    assert "faq-6" not in eve.retired_sources  # invoices stay practical
    for request in [
        Request(operation="event", event_id=LONDON),
        Request(operation="events"),
        Request(operation="speaker", speaker_id="andrey-breslav"),
        Request(operation="search", query="tickets Luma price"),
        Request(operation="ask", query="What is the next talk?"),
        Request(operation="ask", query="How do I get tickets?"),
        Request(operation="faq"),
    ]:
        result = eve.lookup(request)
        cited = {s.id for s in result.sources}
        assert "london-ticket-terms" not in cited, request
        if isinstance(result.data, list) and result.data and "excerpt" in result.data[0]:
            assert not any("£" in row["excerpt"] for row in result.data)
    booked = eve.lookup(Request(operation="ask", query="Can I still get a ticket?"))
    assert "fully booked" in booked.answer.lower()
    sf = eve.lookup(Request(operation="tickets", event_id="sf-code-engineering-2026"))
    assert sf.sources


def card(service, query):
    console = make_console(record=True, width=100)
    render_result(ask(service, query), "ask", console)
    return console.export_text()


@pytest.mark.parametrize(
    "query, expected",
    [
        ("Where is registration?", "Day guide: Registration and badges"),
        ("When do doors open?", "Quick facts"),
        ("How do I get to the venue?", "Walk video"),
        ("Who do I contact for help?", "AgentEngHQ"),
        ("What is the next talk?", "Next"),
        ("What's on now?", "Next up"),
        ("Who is speaking at 10:00?", "Meryem Arik"),
        ("Who is Alexander Korchagin?", "JetBrains"),
        ("Is London sold out?", "fully booked"),
        ("memory tools", "Tools"),
        ("How do I propose a talk?", "events@agentengineering.world"),
        ("Is there wifi?", "Published source excerpts"),
    ],
)
def test_ask_cards_have_no_raw_json(eve, query, expected):
    text = card(eve, query)
    assert expected in text
    assert '": ' not in text and "{\n" not in text


def test_ask_json_output_unchanged():
    out = CliRunner().invoke(main, ["--json", "ask", "Where is registration?"])
    payload = json.loads(out.output)
    assert payload["data"]["registration"] == "Registration is on the left as you walk in."
    assert set(payload) >= {"status", "answer", "data", "sources"}


def test_after_social_answer_is_only_the_published_wording(eve):
    for query in ["What's on after?", "Is there an after party?", "Where is the after party?"]:
        result = eve.lookup(Request(operation="ask", query=query))
        assert result.answer == "Details will be shared during the day. Drinks are buy your own."
        assert [s.id for s in result.sources] == ["guide-after"]
