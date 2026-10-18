"""Talks gallery (site talks.ts), site restructure URLs and Code Engineering SF."""

import json

from click.testing import CliRunner

from agenteng.cli import main
from agenteng.models import Request
from agenteng.service import Service

SITE = "https://agentengineering.world"
LONDON = "agenteng-london-2026"
SF_CODE = "sf-code-engineering-2026"


def lookup(**kw):
    return Service().lookup(Request(**kw))


def run(*args):
    result = CliRunner().invoke(main, list(args), env={"AGENTENG_OUTPUT": "json"})
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_gallery_order_and_no_a2a_by_default():
    rows = lookup(operation="talks", limit=100).data
    kinds = [r.get("gallery_kind") for r in rows]
    assert "a2a" not in kinds
    assert rows[0]["event_id"] == SF_CODE
    assert not any(r.get("ai_generated") for r in rows)


def test_london_talks_are_recording_coming_soon():
    rows = lookup(operation="talks", city="London", limit=100).data
    gallery = [r for r in rows if r.get("slug")]
    assert len(gallery) == 10
    assert {r["status_label"] for r in gallery} == {"Recording coming soon"}
    assert all(r["youtube_id"] is None and "transcript" not in r for r in gallery)
    assert all(r["talk_url"] == f"{SITE}/talks/{r['slug']}" for r in gallery)


def test_a2a_opt_in_last_and_labelled():
    result = lookup(operation="talks", include_a2a=True, limit=100)
    rows = result.data
    a2a = [i for i, r in enumerate(rows) if r.get("gallery_kind") == "a2a"]
    assert len(a2a) == 10
    assert a2a == list(range(len(rows) - 10, len(rows)))
    assert all(rows[i]["ai_generated"] and rows[i]["label"] for i in a2a)
    assert "not created, reviewed or endorsed by our speakers" in result.answer
    online = lookup(operation="talks", city="Online").data
    assert len(online) == 10 and all(r["ai_generated"] for r in online)


def test_talk_by_slug_and_recording():
    talk = lookup(operation="talk", session_id="sf-harness-engineering-2026-full-event")
    assert talk.status == "ok"
    assert talk.data["youtube_id"] == "AP1RRbXZhsE"
    assert talk.data["video_url"] == "https://www.youtube.com/watch?v=AP1RRbXZhsE"
    out = run("talks", "london-2026-say-less-grade-harder")
    assert out["data"]["status"] == "recording-coming-soon"
    assert out["data"]["session_id"]
    assert out["data"]["abstract"]


def test_topic_filter_and_cli_options():
    out = run("talks", "--city", "San Francisco", "--topic", "Code")
    assert out["data"] and all(r["event_id"] == SF_CODE for r in out["data"])
    out = run("talks", "--event", LONDON, "--topic", "Memory")
    assert out["data"]


def test_sf_code_engineering_speakers_and_event_card():
    speakers = run("speakers", "--event", SF_CODE)["data"]
    roles = {s["id"]: s["role"] for s in speakers}
    assert roles["seth-karten"] == "Research, Lead on Prime Agent & Continual Harness"
    assert roles["andrey-risukhin"] == "Recursive Self Improvement"
    event = run("event", SF_CODE)["data"][0]
    assert event["state"] == "upcoming"
    assert event["page_url"] == f"{SITE}/san-francisco"
    assert [p["name"] for p in event["lineup"]] == [
        "Seth Karten",
        "Ben Holmes",
        "Sydney Runkle",
        "Andrey Risukhin",
    ]


def test_restructured_urls():
    service = Service()
    urls = {str(s.url) for s in service.catalogue.sources}
    for old in ("/speakers", "/agenda", "/guide"):
        assert not any(u.startswith(SITE + old) for u in urls), old
    assert not any("/#venue" in u or "/#agenda" in u or "/#tickets" in u for u in urls)
    assert f"{SITE}/london-2026/agenda" in urls
    assert str(service.events[LONDON].page_url) == f"{SITE}/london-2026"
    links = service.catalogue.site_links
    assert str(links.next_event.url) == f"{SITE}/san-francisco"
    assert str(links.previous_event.url) == f"{SITE}/london-2026"


def test_recordings_include_gallery_and_pending_note():
    result = lookup(operation="recordings")
    assert any(r.get("slug") == "sf-harness-engineering-2026-full-event" for r in result.data)
    assert "London 2026 recordings are coming soon" in result.answer


def test_site_disciplines_factory_and_decision():
    result = lookup(operation="disciplines")
    items = result.data["items"]
    assert [d["id"] for d in items][-2:] == ["factory", "decision"]
    assert len(items) == 14
    extra = [d for d in items if not d["in_directory"]]
    assert {d["id"] for d in extra} == {"factory", "decision"}
    assert all(d["tool_count"] is None and d["note"] == "no tool listings yet" for d in extra)
    assert all(d["tool_count"] > 0 for d in items if d["in_directory"])
    assert result.answer.startswith("14 agent-engineering disciplines")
    assert "Factory Engineering and Decision Engineering: no tool listings yet." in result.answer


def test_themes_stay_london_tracks_and_alias():
    themes = run("themes")["data"]
    assert len(themes) == 4
    assert run("themes", "--disciplines")["data"] == run("disciplines")["data"]
    assert (
        run("--themes")["data"] == run("--list-disciplines")["data"] == run("disciplines")["data"]
    )


def test_next_event_prompt_and_coming_label():
    from agenteng.discovery import discovery

    service = Service()
    data = discovery(service)
    assert "Find the next Agent Engineering Conference in London" not in data["suggested_questions"]
    assert (
        "What is the next Agent Engineering event in San Francisco?" in data["suggested_questions"]
    )
    assert data["next_event"]["label"] == "coming April 2027"
    assert set(data["next_event"]) == {"name", "when", "url", "label"}
    answer = service.lookup(
        Request(operation="ask", query="What is the next Agent Engineering event in San Francisco?")
    ).answer
    assert "Agent Engineering San Francisco is coming April 2027" in answer
    assert "27 October 2026" in answer


def test_no_em_dashes_in_new_output():
    text = json.dumps(
        lookup(operation="talks", include_a2a=True, limit=100).model_dump(mode="json")
    )
    assert "\N{EM DASH}" not in text
