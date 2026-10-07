from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from agenteng.calendar import calendar
from agenteng.catalogue import load_catalogue
from agenteng.config import Settings
from agenteng.models import Catalogue, Request
from agenteng.service import Service

LONDON = "agenteng-london-2026"


def test_export_has_evidence_and_honest_dates(service):
    c = service.catalogue
    assert (len(c.events), len(c.speakers), len(c.sessions)) == (11, 18, 25)
    past = [e for e in c.events if e.date_precision == "month"]
    assert len(past) == 8
    assert all(e.start is None and e.end is None for e in past)
    assert len(service.lookup(Request(operation="events", upcoming=True)).data) == 2


def test_unknown_references_rejected():
    data = load_catalogue().model_dump(mode="json")
    data["sessions"][0]["source_ids"] = ["invented"]
    with pytest.raises(ValidationError):
        Catalogue.model_validate(data)


@pytest.mark.parametrize(
    "now,amount",
    [
        ("2026-09-12T23:59:59+01:00", None),  # Early bird is sold out.
        ("2026-09-13T00:00:00+01:00", 149),
        ("2026-10-08T23:59:59+01:00", 149),
        ("2026-10-09T00:00:00+01:00", 199),
        ("2026-10-17T00:00:00+01:00", None),
    ],
)
def test_ticket_boundaries(now, amount):
    s = Service(clock=lambda: datetime.fromisoformat(now))
    result = s.lookup(Request(operation="tickets", event_id=LONDON))
    offers = result.data["current_offers"]
    assert (offers[0]["amount"] if offers else None) == amount
    assert result.data["live_availability_verified"] is False
    assert result.sources


def test_timezone_state_and_unknown_month(service):
    event = service.events["sf-code-engineering-2026"]
    s = Service(clock=lambda: datetime.fromisoformat("2026-10-28T00:30:00+00:00"))
    assert s.state(event) == "upcoming"  # Still 17:30 in SF.
    month = next(e for e in s.catalogue.events if e.date_precision == "month")
    s.clock = lambda: datetime.fromisoformat(month.date + "-01T12:00:00+00:00")
    assert s.state(month) == "unknown"


def test_search_scope_and_recordings(service):
    result = service.lookup(Request(operation="search", query="harness", event_id=LONDON))
    assert result.sources and all(s.event_id == LONDON for s in result.sources)
    recordings = service.lookup(Request(operation="recordings", city="London"))
    assert recordings.status == "ok"
    assert all(row["url"].startswith("https://www.youtube.com/") for row in recordings.data)


def test_ics_utc_and_no_invented_sf_times(service):
    result = service.lookup(Request(operation="agenda", event_id=LONDON, format="ics"))
    assert result.artifact.startswith("BEGIN:VCALENDAR\r\n")
    assert "DTSTART:20261016T070000Z" in result.artifact
    assert all(len(line.encode()) <= 75 for line in result.artifact.split("\r\n"))
    missing = service.lookup(
        Request(operation="agenda", event_id="sf-code-engineering-2026", format="ics")
    )
    assert missing.status == "unavailable" and missing.artifact is None
    e = service.events[LONDON].model_copy(update={"title": "A, B; C\\D\n" + "漢" * 100})
    text = calendar(e, [], service.clock())
    assert r"A\, B\; C\\D\n" in text
    assert all(len(line.encode()) <= 75 for line in text.split("\r\n"))


def test_staleness_is_explicit(service):
    service.clock = lambda: datetime(2027, 1, 1, tzinfo=UTC)
    assert service.lookup(Request(operation="events")).stale


@pytest.mark.parametrize(
    "payload",
    [
        {"operation": "tickets"},
        {"operation": "events", "upcoming": True, "past": True},
        {"operation": "ask", "query": ""},
        {"operation": "events", "engine": "rlm"},
        {"operation": "events", "attendee_email": "x@example.com"},
    ],
)
def test_invalid_requests_rejected(payload):
    with pytest.raises(ValidationError):
        Request.model_validate(payload)


@pytest.mark.asyncio
async def test_models_off_by_default_and_auto_uses_lookup(service):
    class ForbiddenProvider:
        def complete(self, *args, **kwargs):
            raise AssertionError("Lookup must never call a model")

    service.provider = ForbiddenProvider()
    for engine in ["lookup", "auto"]:
        assert (
            await service.execute(Request(operation="ask", query="memory", engine=engine))
        ).engine == "lookup"
    for engine in ["standard", "rlm"]:
        result = await service.execute(Request(operation="ask", query="memory", engine=engine))
        assert result.status == "unavailable" and "disabled" in result.answer


@pytest.mark.asyncio
async def test_request_cannot_enable_or_authorize_a_model():
    s = Service(Settings(enable_rlm=True, operator_token="secret"))
    result = await s.execute(Request(operation="ask", query="memory", engine="rlm"), token="wrong")
    assert result.status == "unavailable" and "credential" in result.answer


def test_model_free_question_routing(service):
    price = service.lookup(Request(operation="ask", query="What are London ticket prices?"))
    assert price.data["current_offers"][0]["amount"] == 149
    agenda = service.lookup(Request(operation="ask", query="London agenda"))
    assert len(agenda.data) == 17
    when = service.lookup(Request(operation="ask", query="When is the next London conference?"))
    assert len(when.data) == 1 and when.data[0]["date"] == "2026-10-16"
    ambiguous = service.lookup(Request(operation="ask", query="ticket prices"))
    assert ambiguous.status == "unavailable" and "event_id" in ambiguous.answer


@pytest.mark.parametrize("change", [{"timezone": "Invalid/Timezone"}, {"date": "20261016"}])
def test_invalid_date_metadata_rejected(change):
    from agenteng.models import Event

    event = load_catalogue().events[0].model_dump(mode="json")
    event.update(change)
    with pytest.raises(ValidationError):
        Event.model_validate(event)


def test_participation_guidance_is_sourced_and_creates_no_submission(service):
    result = service.lookup(Request(operation="participate"))
    assert result.data["organizer_email"] == "events@agentengineering.world"
    assert result.data["automated_submission_available"] is False
    assert "guaranteed" in result.answer
    assert [s.id for s in result.sources] == ["contact"]
    routed = service.lookup(Request(operation="ask", query="How can I propose a talk?"))
    assert routed.model_dump() == result.model_dump()


def test_participation_missing_contact_and_unimplemented_submit(service):
    service.sources.pop("contact")
    assert service.lookup(Request(operation="participate")).status == "unavailable"
    with pytest.raises(ValidationError):
        Request(operation="submit")


@pytest.mark.parametrize(
    "query", ["Who's speaking in London?", "Who's speaking at AgentEng London?"]
)
def test_speaking_questions_return_speaker_records(service, query):
    result = service.lookup(Request(operation="ask", query=query))
    assert result.status == "ok"
    expected = service.lookup(Request(operation="speakers", city="London"))
    assert result.data == expected.data
    assert len(result.data) > 5


def test_speaking_question_preserves_company_filter(service):
    company = service.lookup(Request(operation="speakers", city="London")).data[0]["company"]
    result = service.lookup(
        Request(operation="ask", query=f"Who's speaking from {company} in London?")
    )
    expected = service.lookup(Request(operation="speakers", city="London", query=company))
    assert result.data == expected.data
