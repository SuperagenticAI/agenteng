from dataclasses import replace
import asyncio
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
import json
import sqlite3

from click.testing import CliRunner
import httpx
import pytest
from pydantic import ValidationError

from agenteng.cli import main
from agenteng.config import Settings
from agenteng.models import Request
from agenteng.participation import Draft, Inbox, IntakeError
from agenteng.service import Service
from agenteng.server import create_app


@pytest.fixture
def pilot(tmp_path):
    now = [datetime(2026, 10, 4, 12, tzinfo=UTC)]
    settings = replace(
        Settings(),
        enable_intake=True,
        inbox_path=str(tmp_path / "private" / "inbox.sqlite3"),
        intake_privacy_notice="Only the Agent Engineering HQ organizer receives this proposal. "
        "Contact events@agentengineering.world for deletion; active records expire after 90 days.",
    )
    service = Service(settings, clock=lambda: now[0])
    token = service.participation.inbox.issue_caller(days=90)
    draft = Draft(
        city="London",
        title="Reliable coding agents",
        abstract="A practical evaluation workshop.",
        audience="Agent builders",
        outcomes=["Build a regression suite"],
        speaker_name="Example Speaker",
    )
    return service, token, draft, now


async def prepare(service, token, draft):
    result = await service.execute(Request(operation="proposal_prepare", draft=draft), token=token)
    assert result.status == "ok", result.answer
    assert result.data["submitted"] is False
    return result.data["preview_reference"]


async def submit(service, token, draft, reference, *, confirmed=True):
    return await service.execute(
        Request(
            operation="proposal_submit",
            draft=draft,
            preview_reference=reference,
            confirmed=confirmed,
        ),
        token=token,
    )


@pytest.mark.asyncio
async def test_model_free_drafts_and_disabled_intake(service):
    class Forbidden:
        def complete(self, *args, **kwargs):
            raise AssertionError("Private ideas must never be sent to models")

    service.provider = Forbidden()
    draft = Draft(city="San Francisco", title="Useful topic")
    for op in ["proposal_draft", "proposal_preview", "proposal_export"]:
        result = await service.execute(Request(operation=op, draft=draft))
        assert result.status == "ok" and result.data["sent"] is False
        assert "abstract" in result.data["missing_fields"]
    result = await service.execute(Request(operation="proposal_prepare", draft=draft))
    assert result.status == "unavailable" and "disabled" in result.answer


@pytest.mark.asyncio
async def test_confirmation_owner_payload_binding_and_restart(pilot):
    service, token, draft, _ = pilot
    reference = await prepare(service, token, draft)
    assert (await submit(service, token, draft, reference, confirmed=False)).status == "unavailable"
    other = service.participation.inbox.issue_caller()
    assert (await submit(service, other, draft, reference)).status == "unavailable"
    changed = draft.model_copy(update={"title": "Different idea"})
    assert (await submit(service, token, changed, reference)).status == "unavailable"
    assert service.participation.inbox.listing() == []
    restarted = Service(service.settings, clock=service.clock)
    result = await submit(restarted, token, draft, reference)
    assert result.status == "ok" and result.data["submission_status"] == "received"
    repeated = await submit(restarted, token, draft, reference)
    assert repeated.data["receipt"] == result.data["receipt"]
    assert len(restarted.participation.inbox.listing()) == 1
    assert restarted.catalogue.model_dump() == service.catalogue.model_dump()
    assert len(result.data["history"]) == 1


@pytest.mark.asyncio
async def test_concurrent_retry_and_storage_failure_never_fabricate_receipts(pilot, monkeypatch):
    service, token, draft, _ = pilot
    reference = await prepare(service, token, draft)
    results = await asyncio.gather(
        submit(service, token, draft, reference), submit(service, token, draft, reference)
    )
    assert all(result.status == "ok" for result in results)
    assert results[0].data["receipt"] == results[1].data["receipt"]
    assert len(service.participation.inbox.listing()) == 1

    def failed(*args):
        raise sqlite3.OperationalError("Simulated private persistence failure")

    monkeypatch.setattr(service.participation.inbox, "submit", failed)
    failure = await submit(service, token, draft, reference)
    assert failure.status == "unavailable" and not failure.data
    assert "private persistence failure" not in failure.answer


@pytest.mark.asyncio
async def test_status_is_owner_scoped_withdrawal_erases_content(pilot):
    service, token, draft, _ = pilot
    result = await submit(service, token, draft, await prepare(service, token, draft))
    receipt = result.data["receipt"]
    other = service.participation.inbox.issue_caller()
    for operation in ["proposal_status", "proposal_withdraw"]:
        denied = await service.execute(
            Request(
                operation=operation, receipt=receipt, confirmed=operation == "proposal_withdraw"
            ),
            token=other,
        )
        assert denied.status == "unavailable" and "Speaker" not in denied.answer
    service.participation.inbox.review(receipt, "under_review")
    status = await service.execute(
        Request(operation="proposal_status", receipt=receipt), token=token
    )
    assert [x["status"] for x in status.data["history"]] == ["received", "under_review"]
    request = Request(operation="proposal_withdraw", receipt=receipt, confirmed=True)
    withdrawn = await service.execute(request, token=token)
    assert withdrawn.data["submission_status"] == "withdrawn" and withdrawn.data["draft"] is None
    assert (await service.execute(request, token=token)).data == withdrawn.data
    with sqlite3.connect(service.settings.inbox_path) as db:
        assert db.execute("SELECT body FROM submissions").fetchone()[0] == ""
    with pytest.raises(IntakeError):
        service.participation.inbox.review(receipt, "accepted")


@pytest.mark.asyncio
async def test_policy_changes_expiry_and_revocation(pilot):
    service, token, draft, now = pilot
    reference = await prepare(service, token, draft)
    changed = Service(
        replace(service.settings, intake_privacy_notice="Changed privacy policy"),
        clock=service.clock,
    )
    assert (await submit(changed, token, draft, reference)).status == "unavailable"
    now[0] += timedelta(minutes=10)
    assert (await submit(service, token, draft, reference)).status == "unavailable"
    reference = await prepare(service, token, draft)
    service.participation.inbox.revoke(token)
    assert (await submit(service, token, draft, reference)).status == "unavailable"
    assert service.participation.inbox.listing() == []


@pytest.mark.asyncio
async def test_invited_programme_and_call_closure_are_enforced(pilot, tmp_path):
    service, token, draft, now = pilot
    london = draft.model_copy(update={"future_event": False, "event_id": "agenteng-london-2026"})
    denied = await service.execute(Request(operation="proposal_prepare", draft=london), token=token)
    assert denied.status == "unavailable" and "invited" in denied.answer
    sf = draft.model_copy(
        update={
            "city": "San Francisco",
            "future_event": False,
            "event_id": "sf-code-engineering-2026",
        }
    )
    assert (
        await service.execute(Request(operation="proposal_prepare", draft=sf), token=token)
    ).status == "unavailable"
    calls = tmp_path / "calls.json"
    closes = now[0] + timedelta(minutes=1)
    calls.write_text(
        json.dumps(
            [
                {
                    "event_id": sf.event_id,
                    "opens_at": (now[0] - timedelta(days=1)).isoformat(),
                    "closes_at": closes.isoformat(),
                    "kinds": ["talk"],
                }
            ]
        )
    )
    service = Service(replace(service.settings, calls_path=str(calls)), clock=service.clock)
    reference = await prepare(service, token, sf)
    now[0] = closes
    assert (await submit(service, token, sf, reference)).status == "unavailable"
    assert service.participation.inbox.listing() == []


@pytest.mark.asyncio
async def test_incomplete_drafts_preview_limits_and_capacity(pilot):
    service, token, draft, _ = pilot
    incomplete = await service.execute(
        Request(operation="proposal_prepare", draft=Draft(city="London")), token=token
    )
    assert incomplete.status == "unavailable"
    for _ in range(5):
        await prepare(service, token, draft)
    assert (
        await service.execute(Request(operation="proposal_prepare", draft=draft), token=token)
    ).status == "unavailable"
    service.participation.inbox.capacity = 1
    other = "not-a-participant-credential"
    assert (
        await service.execute(Request(operation="proposal_status", receipt="0" * 32), token=other)
    ).status == "unavailable"


@pytest.mark.asyncio
async def test_retention_and_private_file_permissions(pilot):
    service, token, draft, now = pilot
    await submit(service, token, draft, await prepare(service, token, draft))
    path = service.participation.inbox.path
    assert path.stat().st_mode & 0o777 == 0o600
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT token_hash FROM callers").fetchone()[0] != token
    now[0] += timedelta(days=90)
    service.participation.inbox.maintenance()
    with sqlite3.connect(path) as db:
        for table in ["callers", "previews", "submissions", "history"]:
            assert db.execute("SELECT count(*) FROM " + table).fetchone()[0] == 0


def test_store_rejects_symlinks_and_missing_policy(tmp_path):
    path = tmp_path / "linked.sqlite3"
    path.symlink_to(tmp_path / "other.sqlite3")
    with pytest.raises(ValueError):
        Inbox(str(path))
    with pytest.raises(ValueError):
        Service(
            replace(Settings(), enable_intake=True, inbox_path=str(tmp_path / "private.sqlite3"))
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"city": "Paris"},
        {"city": "London", "organizer": "Other group"},
        {"city": "London", "event_id": "agenteng-london-2026"},
        {"city": "London", "future_event": False},
        {"city": "London", "contact_email": "broken"},
    ],
)
def test_drafts_enforce_scope_and_contract(payload):
    with pytest.raises(ValidationError):
        Draft.model_validate(payload)


def test_private_cli_export_never_overwrites(tmp_path):
    runner = CliRunner()
    draft = tmp_path / "draft.json"
    args = [
        "proposal",
        "draft",
        "--city",
        "London",
        "--title",
        "Useful idea",
        "--output",
        str(draft),
    ]
    assert runner.invoke(main, args).exit_code == 0
    original = draft.read_bytes()
    assert draft.stat().st_mode & 0o777 == 0o600
    assert runner.invoke(main, args).exit_code != 0 and draft.read_bytes() == original
    exported = runner.invoke(main, ["proposal", "export", str(draft)])
    assert exported.exit_code == 0 and "nothing has been sent" in exported.output
    assert runner.invoke(main, ["proposal", "submit", str(draft)], input="y\n").exit_code != 0
    guided = runner.invoke(
        main,
        ["engage", "--city", "San Francisco"],
        input="Useful idea\nA practical workshop\nAgent builders\n",
    )
    assert guided.exit_code == 0 and "Useful idea" in guided.output


def test_cli_confirmed_submission_review_and_decline(pilot, tmp_path):
    service, token, draft, _ = pilot
    runner = CliRunner()
    env = {
        "AGENTENG_ENABLE_INTAKE": "1",
        "AGENTENG_INBOX": service.settings.inbox_path,
        "AGENTENG_INTAKE_PRIVACY_NOTICE": service.settings.intake_privacy_notice,
        "AGENTENG_PARTICIPANT_TOKEN": token,
    }
    file = tmp_path / "draft.json"
    file.write_text(draft.model_dump_json())
    declined = runner.invoke(main, ["proposal", "submit", str(file)], env=env, input="n\n")
    assert declined.exit_code != 0 and service.participation.inbox.listing() == []
    sent = subprocess.run(
        [sys.executable, "-m", "agenteng", "--json", "proposal", "submit", str(file)],
        env={**os.environ, **env},
        input="y\n",
        capture_output=True,
        text=True,
    )
    assert sent.returncode == 0, sent.stderr
    receipt = json.loads(sent.stdout)["data"]["receipt"]
    assert "privacy_notice" in sent.stderr
    review = runner.invoke(main, ["inbox", "review", receipt, "--status", "accepted"], env=env)
    assert review.exit_code == 0 and json.loads(review.stdout)["submission_status"] == "accepted"
    status = runner.invoke(main, ["--json", "proposal", "status", receipt], env=env)
    assert json.loads(status.stdout)["data"]["submission_status"] == "accepted"
    assert "Example Speaker" not in service.catalogue.model_dump_json()


@pytest.mark.asyncio
async def test_real_mcp_private_pilot_advertises_writes_and_checks_confirmation(pilot):
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    service, token, draft, _ = pilot
    app = create_app(service)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app),
            follow_redirects=True,
            headers={"Authorization": "Bearer " + token},
        ) as http:
            async with streamable_http_client("http://localhost/mcp/", http_client=http) as (
                read,
                write,
                _,
            ):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = (await session.list_tools()).tools
                    assert [tool.name for tool in tools] == ["agenteng"]
                    assert tools[0].annotations.readOnlyHint is False
                    assert tools[0].annotations.destructiveHint is True
                    payload = {
                        "operation": "proposal_prepare",
                        "draft": draft.model_dump(mode="json"),
                    }
                    preview = await session.call_tool("agenteng", {"request": payload})
                    assert preview.structuredContent["status"] == "ok"
                    payload.update(
                        operation="proposal_submit",
                        preview_reference=preview.structuredContent["data"]["preview_reference"],
                    )
                    unconfirmed = await session.call_tool("agenteng", {"request": payload})
                    assert unconfirmed.structuredContent["status"] == "unavailable"
                    payload["confirmed"] = True
                    sent = await session.call_tool("agenteng", {"request": payload})
                    assert sent.structuredContent["data"]["submission_status"] == "received"


@pytest.mark.asyncio
async def test_remote_stdio_bridge_uses_hosted_facts(pilot):
    from agenteng.remote import RemoteService

    service, token, draft, _ = pilot
    app = create_app(service)
    bridge = RemoteService("http://localhost", transport=httpx.ASGITransport(app))
    async with app.router.lifespan_context(app):
        result = await bridge.execute(
            Request(operation="proposal_prepare", draft=draft), token=token
        )
        assert result.status == "ok" and result.data["confirmation_required"] is True
        denied = await bridge.execute(Request(operation="proposal_prepare", draft=draft))
        assert denied.status == "unavailable"


@pytest.mark.asyncio
async def test_http_and_a2a_private_participation_and_redacted_validation(pilot):
    service, token, draft, _ = pilot
    app = create_app(service)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://localhost"
        ) as client:
            payload = {"operation": "proposal_prepare", "draft": draft.model_dump(mode="json")}
            denied = await client.post(
                "/v1/query", json=payload, headers={"Authorization": "Bearer operator-only"}
            )
            assert denied.json()["status"] == "unavailable"
            preview = await client.post(
                "/v1/query", json=payload, headers={"Authorization": "Bearer " + token}
            )
            assert preview.headers["cache-control"] == "no-store"
            assert preview.json()["data"]["confirmation_required"] is True
            submit_payload = {
                **payload,
                "operation": "proposal_submit",
                "confirmed": True,
                "preview_reference": preview.json()["data"]["preview_reference"],
            }
            rpc = {
                "jsonrpc": "2.0",
                "id": "private",
                "method": "SendMessage",
                "params": {
                    "message": {
                        "messageId": "private",
                        "role": "ROLE_USER",
                        "parts": [{"data": submit_payload}],
                    }
                },
            }
            response = await client.post(
                "/", json=rpc, headers={"A2A-Version": "1.0", "Authorization": "Bearer " + token}
            )
            assert (
                response.json()["result"]["message"]["parts"][1]["data"]["data"][
                    "submission_status"
                ]
                == "received"
            )
            card = (await client.get("/.well-known/agent-card.json")).json()
            assert (
                card["securitySchemes"]["participant"]["httpAuthSecurityScheme"]["scheme"]
                == "bearer"
            )
            broken = {
                **payload,
                "draft": {**payload["draft"], "contact_email": "PRIVATE_INVALID_CONTACT"},
            }
            invalid = await client.post("/v1/query", json=broken)
            assert invalid.status_code == 422 and "PRIVATE_INVALID_CONTACT" not in invalid.text
            assert "Example Speaker" not in (await client.get("/catalogue.json")).text
