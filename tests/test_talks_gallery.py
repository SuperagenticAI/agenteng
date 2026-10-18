"""Talks gallery (site talks.ts), site restructure URLs and Code Engineering SF."""

import json

from click.testing import CliRunner

from agenteng.cli import main
from agenteng.models import Request
from agenteng.service import Service

SITE = "https://agentengineering.world"
LONDON = "agenteng-london-2026"
SF_CODE = "sf-code-engineering-2026"
RECAP = "sf-harness-engineering-2026-recap"
RECAP_SUMMARY = (
    "Recap of our Harness Engineering evening in San Francisco, attended by 300+ members."
)


def lookup(**kw):
    return Service().lookup(Request(**kw))


def run(*args):
    result = CliRunner().invoke(main, list(args), env={"AGENTENG_OUTPUT": "json"})
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_gallery_mirrors_site_order_without_a2a():
    rows = lookup(operation="gallery", limit=100).data
    assert [r["gallery"] for r in rows] == ["london"] * 10 + ["san-francisco"]
    assert rows[0]["slug"] == "london-2026-welcome"
    assert rows[0]["youtube_id"] == "iTV8VSrVJEk" and rows[0]["status"] == "recorded"
    assert {r["status_label"] for r in rows[1:10]} == {"Recording coming soon"}
    assert rows[-1]["youtube_id"] == "AP1RRbXZhsE"
    assert all(r["talk_url"] == f"{SITE}/gallery/{r['slug']}" for r in rows)
    assert not any(r.get("ai_generated") or r["event_id"] == SF_CODE for r in rows)
    assert all(r["youtube_id"] is None and "transcript" not in r for r in rows[1:10])


def test_gallery_a2a_opt_in_last_and_labelled():
    result = lookup(operation="gallery", include_a2a=True, limit=100)
    rows = result.data
    a2a = [i for i, r in enumerate(rows) if r.get("gallery_kind") == "a2a"]
    assert a2a == list(range(len(rows) - 10, len(rows)))
    assert all(rows[i]["ai_generated"] and rows[i]["label"] for i in a2a)
    assert "not created, reviewed or endorsed by our speakers" in result.answer
    online = lookup(operation="gallery", city="Online").data
    assert len(online) == 10 and all(r["ai_generated"] for r in online)


def test_talks_is_the_programme_listing():
    rows = lookup(operation="talks", limit=100).data
    assert not any(
        r.get("ai_generated") or r.get("gallery_kind") == "event-recording" for r in rows
    )
    assert sum(r["event_id"] == LONDON for r in rows) == 9
    code = [r for r in rows if r["event_id"] == SF_CODE]
    assert len(code) == 4
    assert all(r["talk_url"] == f"{SITE}/san-francisco" and r["gallery"] is None for r in code)
    assert lookup(operation="talks", city="Online").status == "not_found"
    assert lookup(operation="talks", include_a2a=True, limit=100).data == rows


def test_one_item_by_slug_from_either_command():
    welcome = run("gallery", "london-2026-welcome")["data"]
    assert welcome["video_url"] == "https://www.youtube.com/watch?v=iTV8VSrVJEk"
    out = run("talks", "london-2026-say-less-grade-harder")["data"]
    assert out["status"] == "recording-coming-soon" and out["abstract"]
    assert run("gallery", "london-2026-say-less-grade-harder")["data"]["slug"] == out["slug"]
    assert run("talks", "sydney-runkle")["data"]["talk_url"] == f"{SITE}/san-francisco"


def test_filters():
    out = run("talks", "--city", "San Francisco", "--topic", "Code")
    assert out["data"] and {r["event_id"] for r in out["data"]} >= {SF_CODE}
    assert run("gallery", "--city", "London")["data"][0]["slug"] == "london-2026-welcome"
    assert run("talks", "--event", LONDON, "--topic", "Memory")["data"]


def test_sf_code_engineering_speakers_and_event_card():
    speakers = run("speakers", "--event", SF_CODE)["data"]
    roles = {s["id"]: s["role"] for s in speakers}
    assert roles["seth-karten"] == "Research, Lead on Prime Agent & Continual Harness"
    assert roles["andrey-risukhin"] == "Recursive Self Improvement"
    event = run("event", SF_CODE)["data"][0]
    assert event["state"] == "upcoming"
    assert event["page_url"] == f"{SITE}/san-francisco"
    assert "gallery_url" not in event
    assert [p["name"] for p in event["lineup"]] == [
        "Seth Karten",
        "Ben Holmes",
        "Sydney Runkle",
        "Andrey Risukhin",
    ]
    london = run("event", LONDON)["data"][0]
    assert london["gallery_url"] == f"{SITE}/london-2026/videos"


def test_restructured_urls_and_no_talks_urls():
    service = Service()
    urls = {str(s.url) for s in service.catalogue.sources}
    urls |= {str(t.url) for t in service.catalogue.talks}
    for old in ("/speakers", "/agenda", "/guide", "/talks"):
        assert not any(u.startswith(SITE + old) for u in urls), old
    assert not any("/#venue" in u or "/#agenda" in u or "/#tickets" in u for u in urls)
    assert f"{SITE}/london-2026/agenda" in urls
    assert f"{SITE}/london-2026/videos" in urls
    text = service.catalogue.model_dump_json()
    assert "agentengineering.world/talks" not in text
    assert str(service.events[LONDON].page_url) == f"{SITE}/london-2026"
    links = service.catalogue.site_links
    assert str(links.gallery) == f"{SITE}/gallery"
    assert str(links.next_event.url) == f"{SITE}/san-francisco"
    assert str(links.previous_event.url) == f"{SITE}/london-2026"


def test_recordings_include_london_videos_and_welcome():
    result = lookup(operation="recordings")
    assert result.data[0]["url"] == f"{SITE}/london-2026/videos"
    urls = [r["url"] for r in result.data]
    assert "https://www.youtube.com/watch?v=iTV8VSrVJEk" in urls
    recap = next(r for r in result.data if r.get("slug") == RECAP)
    assert recap["kind"] == "event-recap" and recap["summary"] == RECAP_SUMMARY
    assert len(urls) == len(set(urls))
    assert "talk recordings are coming soon" in result.answer
    assert "agenteng gallery --city London" in result.answer


def test_a2a_rows_stay_out_of_general_search():
    result = lookup(operation="search", query="coding agent engineering")
    assert not any(s.kind == "a2a-talks" for s in result.sources)


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


PUBLIC_RECORDINGS = (
    "Yes. Recordings are public and published on "
    "https://agentengineering.world/london-2026/videos as they become available, "
    "starting with the welcome video."
)


def test_recorded_question_uses_public_faq():
    for question in (
        "Will talks be recorded?",
        "Are the talks recorded?",
        "Were the London talks recorded?",
    ):
        result = lookup(operation="ask", query=question)
        assert result.answer == PUBLIC_RECORDINGS, question
    assert lookup(operation="ask", query="Show the recordings").answer.startswith("9 published")


def test_no_ticket_holder_recording_wording():
    service = Service()
    text = service.catalogue.model_dump_json().casefold()
    assert "ticket holders" not in text
    faq = next(f for f in service.catalogue.faqs if f.question == "Will talks be recorded?")
    assert faq.answer == PUBLIC_RECORDINGS
    photo = next(s for s in service.catalogue.guide.sections if s.id == "photography")
    assert "Recordings are public" in " ".join(photo.model_dump_json() for _ in [0])


def test_sf_harness_video_is_an_event_recap():
    rows = lookup(operation="gallery", city="San Francisco").data
    assert len(rows) == 1
    recap = rows[0]
    assert recap["slug"] == RECAP and recap["gallery_kind"] == "event-recap"
    assert recap["title"] == "Harness Engineering San Francisco: event recap"
    assert recap["summary"] == RECAP_SUMMARY and recap["status_label"] == "Event recap"
    assert recap["talk_url"] == f"{SITE}/gallery/{RECAP}"
    old = lookup(operation="talk", session_id="sf-harness-engineering-2026-full-event")
    assert old.status == "ok" and old.data["slug"] == RECAP
    assert old.answer == "Event recap: Harness Engineering San Francisco: event recap."
    assert run("gallery", "sf-harness-engineering-2026-full-event")["data"]["slug"] == RECAP
    harness = [
        r
        for r in lookup(operation="talks", limit=100).data
        if r["event_id"] == "sf-harness-engineering-2026"
    ]
    assert len(harness) == 4
    assert not any(
        "recording_slug" in r or "recording" in (r.get("status_label") or "").lower()
        for r in harness
    )
    text = Service().catalogue.model_dump_json().casefold()
    assert "full-event" not in text and "full event" not in text


# The cancelled talk's words, reversed so the guard itself does not reintroduce them.
CANCELLED = [w[::-1] for w in ("sats", "oknehcib", "tnega eciov", "gnizimitpo-dna-gniggubed")]
CANCELLED_SLUG = "-".join(
    ["london-2026", *[w[::-1] for w in ("gniggubed", "dna", "gnizimitpo", "eciov", "stnega")]]
)
CANCELLED_SPEAKER = "-".join(w[::-1] for w in ("sats", "oknehcib"))


def test_cancelled_london_talk_is_gone():
    service = Service()
    text = service.catalogue.model_dump_json().casefold()
    for word in CANCELLED:
        assert word not in text, word
    london_talks = [s for s in service.catalogue.sessions if s.event_id == LONDON and s.speaker_id]
    assert len(london_talks) == 9
    assert (
        len([t for t in service.catalogue.talks if t.event_id == LONDON and t.kind == "talk"]) == 9
    )
    assert lookup(operation="talk", session_id=CANCELLED_SLUG).status == "not_found"
    assert lookup(operation="speaker", speaker_id=CANCELLED_SPEAKER).status == "not_found"


def test_bingo_has_no_cancelled_talk_terms():
    from agenteng import screens

    labels = {label.casefold() for label, _ in screens.BINGO_TERMS}
    assert not labels & {CANCELLED[2] + "s", "debugging"}
