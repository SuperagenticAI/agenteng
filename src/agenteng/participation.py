"""Local drafts and an opt-in, single-organizer private intake pilot.

No mail, model calls, publication or external recipient selection. SQLite needs
a persistent, encrypted operator-managed volume; it is not a Cloud Run store.
"""

from __future__ import annotations

from contextlib import closing, contextmanager
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
from typing import Annotated, Literal

from pydantic import AwareDatetime, ConfigDict, Field, HttpUrl, model_validator

from .contracts import Model

CITIES = ("London", "San Francisco")
ORGANIZER = "Agent Engineering HQ"
DISCLAIMER = (
    "Received for possible consideration by Agent Engineering HQ. This does not guarantee "
    "review by a deadline, a response, acceptance, publication or an event."
)
WRITE_OPERATIONS = {"proposal_prepare", "proposal_submit", "proposal_withdraw"}
PRIVATE_OPERATIONS = WRITE_OPERATIONS | {"proposal_status"}
DRAFT_OPERATIONS = {"proposal_draft", "proposal_preview", "proposal_export"}


class Draft(Model):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    schema_version: Literal[1] = 1
    kind: Literal["talk", "workshop", "event_idea", "feedback"] = "talk"
    city: Literal["London", "San Francisco"]
    event_id: str | None = Field(default=None, max_length=128)
    future_event: bool = True
    title: str = Field(default="", max_length=160)
    abstract: str = Field(default="", max_length=6000)
    audience: str = Field(default="", max_length=500)
    outcomes: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(
        default_factory=list, max_length=5
    )
    speaker_name: str = Field(default="", max_length=120)
    contact_email: str = Field(default="", max_length=254)
    public_links: list[HttpUrl] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def target(self):
        if self.future_event and self.event_id:
            raise ValueError("Choose a future event idea or a specific event_id, not both")
        if not self.future_event and not self.event_id:
            raise ValueError("A specific-event draft requires event_id")
        if self.contact_email:
            import re

            if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", self.contact_email):
                raise ValueError("Invalid contact email")
        return self

    def missing(self):
        required = ["title", "abstract", "audience"]
        if self.kind in {"talk", "workshop"}:
            required += ["speaker_name", "outcomes"]
        return [name for name in required if not getattr(self, name)]

    def markdown(self):
        # Plain text export: no fetching, execution or assumptions about acceptance.
        lines = [
            "# " + (self.title or "Untitled idea"),
            "",
            f"Organizer: {ORGANIZER}",
            f"City: {self.city}",
            f"Kind: {self.kind}",
            "Target: " + ("Possible future event" if self.future_event else self.event_id),
            "",
            self.abstract,
            "",
            "Audience: " + self.audience,
            "",
            "Learning outcomes:",
            *["- " + x for x in self.outcomes],
            "",
            "Speaker: " + self.speaker_name,
            "Contact (optional): " + self.contact_email,
            *["Reference: " + str(x) for x in self.public_links],
            "",
            "Draft only; nothing has been sent.",
        ]
        return "\n".join(lines) + "\n"


class Call(Model):
    event_id: str
    opens_at: AwareDatetime
    closes_at: AwareDatetime
    kinds: list[Literal["talk", "workshop", "event_idea", "feedback"]] = Field(min_length=1)

    @model_validator(mode="after")
    def window(self):
        if self.closes_at <= self.opens_at:
            raise ValueError("Call closes_at must follow opens_at")
        return self


class IntakeError(ValueError):
    """Safe user-facing failures; never contains private body or credentials."""


def canonical(draft: Draft):
    return json.dumps(draft.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class Inbox:
    """Transactional private store. Raw caller/preview secrets are never stored."""

    def __init__(self, path: str, *, clock=None, retention_days=90, capacity=1000):
        self.path = Path(path).expanduser().absolute()
        self.clock = clock or (lambda: datetime.now(UTC))
        self.retention_days = retention_days
        self.capacity = capacity
        if retention_days < 1 or capacity < 1:
            raise ValueError("Retention and capacity must be positive")
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.path.is_symlink() or (self.path.exists() and not self.path.is_file()):
            raise ValueError("Private inbox must be a regular file")
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        os.close(fd)
        self.path.chmod(0o600)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS callers (
                    token_hash TEXT PRIMARY KEY, owner TEXT UNIQUE NOT NULL,
                    expires REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS previews (
                    reference_hash TEXT PRIMARY KEY, owner TEXT NOT NULL,
                    draft_hash TEXT NOT NULL, policy_hash TEXT NOT NULL,
                    expires REAL NOT NULL, receipt TEXT
                );
                CREATE TABLE IF NOT EXISTS submissions (
                    receipt TEXT PRIMARY KEY, owner TEXT NOT NULL, body TEXT NOT NULL,
                    status TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL,
                    delete_after REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS history (
                    receipt TEXT NOT NULL REFERENCES submissions(receipt) ON DELETE CASCADE,
                    status TEXT NOT NULL, changed REAL NOT NULL
                );
            """)
            if "policy" not in {row[1] for row in db.execute("PRAGMA table_info(submissions)")}:
                db.execute("ALTER TABLE submissions ADD COLUMN policy TEXT NOT NULL DEFAULT ''")

    @contextmanager
    def connect(self):
        with closing(sqlite3.connect(self.path, timeout=5, isolation_level=None)) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA secure_delete=ON")
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
            except BaseException:
                db.rollback()
                raise
            else:
                db.commit()

    def purge(self, db, now):
        db.execute("DELETE FROM submissions WHERE delete_after <= ?", (now,))
        db.execute("DELETE FROM previews WHERE expires <= ?", (now,))
        db.execute("DELETE FROM callers WHERE expires <= ?", (now,))

    def issue_caller(self, days=30):
        if not 1 <= days <= 365:
            raise ValueError("Caller access lasts 1–365 days")
        token, owner = "ae_participant_" + secrets.token_urlsafe(32), secrets.token_hex(16)
        with self.connect() as db:
            now = self.clock().timestamp()
            self.purge(db, now)
            if db.execute("SELECT count(*) FROM callers").fetchone()[0] >= self.capacity:
                raise IntakeError("Caller capacity reached")
            db.execute(
                "INSERT INTO callers VALUES (?, ?, ?)",
                (digest(token), owner, now + days * 86400),
            )
        return token

    def owner(self, db, token, now):
        if not token or len(token) > 512:
            raise IntakeError("A participant credential issued by the organizer is required")
        row = db.execute(
            "SELECT owner FROM callers WHERE token_hash = ? AND expires > ?",
            (digest(token), now),
        ).fetchone()
        if not row:
            raise IntakeError("A valid participant credential is required")
        return row[0]

    def prepare(self, draft, token, policy):
        reference = secrets.token_urlsafe(32)
        with self.connect() as db:
            now = self.clock().timestamp()
            self.purge(db, now)
            owner = self.owner(db, token, now)
            pending = db.execute(
                "SELECT count(*) FROM previews WHERE owner = ? AND receipt IS NULL", (owner,)
            ).fetchone()[0]
            if (
                pending >= 5
                or db.execute("SELECT count(*) FROM previews").fetchone()[0] >= self.capacity
            ):
                raise IntakeError("Preview limit reached; wait for existing previews to expire")
            expires = now + 600
            db.execute(
                "INSERT INTO previews VALUES (?, ?, ?, ?, ?, NULL)",
                (digest(reference), owner, digest(canonical(draft)), digest(policy), expires),
            )
        return {"preview_reference": reference, "expires_at": datetime.fromtimestamp(expires, UTC)}

    def submit(self, draft, token, reference, policy, check):
        with self.connect() as db:
            now = self.clock().timestamp()
            self.purge(db, now)
            owner = self.owner(db, token, now)
            preview = db.execute(
                "SELECT * FROM previews WHERE reference_hash = ? AND owner = ?",
                (digest(reference), owner),
            ).fetchone()
            if (
                not preview
                or preview["draft_hash"] != digest(canonical(draft))
                or preview["policy_hash"] != digest(policy)
            ):
                raise IntakeError("Preview expired or does not match this caller, draft and policy")
            if preview["receipt"]:
                # Retry returns the same durable receipt, without duplicating or changing data.
                return self.read(db, preview["receipt"], owner)
            check(draft)
            if db.execute("SELECT count(*) FROM submissions").fetchone()[0] >= self.capacity:
                raise IntakeError("Private inbox is at capacity; nothing was submitted")
            recent = db.execute(
                "SELECT count(*) FROM submissions WHERE owner = ? AND created > ?",
                (owner, now - 86400),
            ).fetchone()[0]
            if recent >= 20:
                raise IntakeError("Daily submission limit reached")
            receipt = secrets.token_hex(16)
            db.execute(
                "INSERT INTO submissions (receipt, owner, body, status, created, updated, delete_after, policy) "
                "VALUES (?, ?, ?, 'received', ?, ?, ?, ?)",
                (
                    receipt,
                    owner,
                    canonical(draft),
                    now,
                    now,
                    now + self.retention_days * 86400,
                    policy,
                ),
            )
            db.execute(
                "UPDATE previews SET receipt = ? WHERE reference_hash = ?",
                (receipt, digest(reference)),
            )
            db.execute("INSERT INTO history VALUES (?, 'received', ?)", (receipt, now))
            return self.read(db, receipt, owner)

    def read(self, db, receipt, owner):
        row = db.execute(
            "SELECT * FROM submissions WHERE receipt = ? AND owner = ?", (receipt, owner)
        ).fetchone()
        if not row:
            raise IntakeError("Submission not found for this caller")
        return {
            "receipt": row["receipt"],
            "submission_status": row["status"],
            "created_at": datetime.fromtimestamp(row["created"], UTC),
            "updated_at": datetime.fromtimestamp(row["updated"], UTC),
            "delete_after": datetime.fromtimestamp(row["delete_after"], UTC),
            "draft": json.loads(row["body"]) if row["body"] else None,
            "organizer": ORGANIZER,
            "notice": DISCLAIMER,
            "accepted_policy": json.loads(row["policy"]) if row["policy"] else None,
            "history": [
                {"status": x["status"], "changed_at": datetime.fromtimestamp(x["changed"], UTC)}
                for x in db.execute(
                    "SELECT status, changed FROM history WHERE receipt=? ORDER BY rowid", (receipt,)
                )
            ],
        }

    def status(self, receipt, token, *, withdraw=False):
        with self.connect() as db:
            now = self.clock().timestamp()
            self.purge(db, now)
            owner = self.owner(db, token, now)
            current = self.read(db, receipt, owner)
            if withdraw and current["submission_status"] != "withdrawn":
                # Erase active content and retain only an owner-scoped tombstone until expiry.
                db.execute(
                    "UPDATE submissions SET status='withdrawn', body='', updated=? "
                    "WHERE receipt=? AND owner=?",
                    (now, receipt, owner),
                )
                db.execute("INSERT INTO history VALUES (?, 'withdrawn', ?)", (receipt, now))
            return self.read(db, receipt, owner)

    def review(self, receipt, status):
        allowed = {"under_review", "needs_information", "accepted", "declined"}
        if status not in allowed:
            raise IntakeError("Unsupported organizer decision")
        with self.connect() as db:
            now = self.clock().timestamp()
            self.purge(db, now)
            row = db.execute(
                "SELECT owner, status FROM submissions WHERE receipt=?", (receipt,)
            ).fetchone()
            if not row or row["status"] == "withdrawn":
                raise IntakeError("Active submission not found")
            db.execute(
                "UPDATE submissions SET status=?, updated=? WHERE receipt=?", (status, now, receipt)
            )
            if row["status"] != status:
                db.execute("INSERT INTO history VALUES (?, ?, ?)", (receipt, status, now))
            return self.read(db, receipt, row["owner"])

    def listing(self):
        with self.connect() as db:
            self.purge(db, self.clock().timestamp())
            rows = db.execute(
                "SELECT receipt, owner FROM submissions ORDER BY created DESC LIMIT 100"
            ).fetchall()
            return [self.read(db, row["receipt"], row["owner"]) for row in rows]

    def maintenance(self):
        with self.connect() as db:
            self.purge(db, self.clock().timestamp())

    def revoke(self, token):
        with self.connect() as db:
            row = db.execute(
                "SELECT owner FROM callers WHERE token_hash=?", (digest(token),)
            ).fetchone()
            if not row:
                raise IntakeError("Participant credential not found")
            db.execute("DELETE FROM previews WHERE owner=?", (row[0],))
            db.execute("DELETE FROM callers WHERE token_hash=?", (digest(token),))


class Participation:
    def __init__(self, service):
        self.service = service
        self.settings = service.settings
        self.inbox = None
        if self.settings.enable_intake:
            if not self.settings.inbox_path or not self.settings.intake_privacy_notice:
                raise ValueError(
                    "Private intake requires a persistent inbox path and privacy notice"
                )
            self.inbox = Inbox(
                self.settings.inbox_path,
                clock=service.clock,
                retention_days=self.settings.intake_retention_days,
                capacity=self.settings.intake_capacity,
            )

    def calls(self):
        if not self.settings.calls_path:
            return []
        path = Path(self.settings.calls_path)
        if path.stat().st_size > 65536:
            raise IntakeError("Call configuration is too large")
        calls = [Call.model_validate(x) for x in json.loads(path.read_text())]
        if len({x.event_id for x in calls}) != len(calls):
            raise IntakeError("Call configuration contains duplicate events")
        for call in calls:
            event = self.service.events.get(call.event_id)
            if (
                not event
                or event.city not in CITIES
                or (
                    event.speaker_submission_status == "invited_only"
                    and {"talk", "workshop"}.intersection(call.kinds)
                )
            ):
                raise IntakeError("Call configuration conflicts with the published event policy")
        return calls

    def policy(self):
        return json.dumps(
            {
                "organizer": ORGANIZER,
                "privacy_notice": self.settings.intake_privacy_notice,
                "retention_days": self.settings.intake_retention_days,
                "notice": DISCLAIMER,
                "catalogue_version": self.service.catalogue.version,
                "calls": [x.model_dump(mode="json") for x in self.calls()],
            },
            sort_keys=True,
        )

    def check(self, draft):
        if draft.missing():
            raise IntakeError("Complete the required draft fields before submission")
        if draft.future_event:
            return
        event = self.service.events.get(draft.event_id)
        if not event or event.city != draft.city:
            raise IntakeError("The draft city does not match a published event")
        if event.speaker_submission_status == "invited_only" and draft.kind in {"talk", "workshop"}:
            raise IntakeError(
                "This event has an invited programme; propose a possible future event instead"
            )
        now = self.service.clock()
        call = next((x for x in self.calls() if x.event_id == draft.event_id), None)
        if (
            not call
            or not call.opens_at <= now < call.closes_at
            or draft.kind not in call.kinds
            or self.service.state(event) in {"past", "cancelled"}
        ):
            raise IntakeError("No open organizer-approved call accepts this draft")

    def execute(self, request, token):
        op, draft = request.operation, request.draft
        if op in DRAFT_OPERATIONS:
            artifact = (
                draft.markdown()
                if request.draft_format == "markdown"
                else draft.model_dump_json(indent=2) + "\n"
            )
            return self.service.result(
                "Local draft only; nothing has been sent. "
                "London 2026 has an invited programme; future-event ideas are welcome for possible consideration.",
                {
                    "draft": draft.model_dump(mode="json"),
                    "missing_fields": draft.missing(),
                    "organizer": ORGANIZER,
                    "sent": False,
                },
                artifact=artifact if op in {"proposal_draft", "proposal_export"} else None,
            )
        if not self.inbox:
            return self.service.result(
                "Hosted intake is disabled. Export a draft or use organizer contact guidance.",
                status="unavailable",
            )
        try:
            if op == "proposal_prepare":
                self.check(draft)
                policy = self.policy()
                prepared = self.inbox.prepare(draft, token, policy)
                return self.service.result(
                    "Review the exact draft, recipient and privacy terms. Nothing has been submitted. "
                    "Only submit after the contributor explicitly confirms this preview.",
                    {
                        **prepared,
                        "draft": draft.model_dump(mode="json"),
                        "organizer": ORGANIZER,
                        "visibility": "private organizer inbox",
                        "privacy_notice": self.settings.intake_privacy_notice,
                        "retention_days": self.settings.intake_retention_days,
                        "notice": DISCLAIMER,
                        "submitted": False,
                        "confirmation_required": True,
                        "target": "Possible future event in " + draft.city
                        if draft.future_event
                        else self.service.event_data(self.service.events[draft.event_id]),
                    },
                )
            if op == "proposal_submit":
                if not request.confirmed:
                    raise IntakeError(
                        "Explicit contributor confirmation of the prepared preview is required"
                    )
                data = self.inbox.submit(
                    draft, token, request.preview_reference, self.policy(), self.check
                )
            else:
                if op == "proposal_withdraw" and not request.confirmed:
                    raise IntakeError(
                        "Explicit confirmation is required to withdraw this submission"
                    )
                data = self.inbox.status(request.receipt, token, withdraw=op == "proposal_withdraw")
            return self.service.result(
                "Submission withdrawn; active proposal content erased."
                if op == "proposal_withdraw"
                else f"Submission status: {data['submission_status']}. "
                + (
                    "Acceptance does not automatically schedule or publish a talk."
                    if data["submission_status"] == "accepted"
                    else DISCLAIMER
                ),
                data,
            )
        except IntakeError as exc:
            return self.service.result(str(exc), status="unavailable")
        except (OSError, sqlite3.Error, ValueError):
            return self.service.result(
                "Private intake is unavailable; no new receipt can be confirmed. Retry the same preview safely.",
                status="unavailable",
            )
