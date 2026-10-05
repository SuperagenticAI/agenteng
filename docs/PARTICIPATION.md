# 💡 Shape a future event

Have a talk, workshop or event idea? Start with a local draft, preview it and
choose how to share it. [Offline drafting](#offline-drafts) works immediately;
the [private intake pilot](#optional-private-pilot) requires organizer setup and access.

AgentEng helps people propose talks, workshops, future-event topics and feedback for **Agent Engineering HQ** in **London or San Francisco**. Every private submission belongs to this one organizing group. Open-source deployments use their own separate private store.

London 2026 has an invited programme and no public CFP. No San Francisco public CFP is announced in the bundled catalogue. A future-event idea is possible input for organizers, not an application for an existing speaking slot. Receiving an idea does not guarantee review, a response, acceptance, publication or an event.

## Offline drafts

```sh
agenteng engage --city London --output draft.json
agenteng proposal draft --city 'San Francisco' --kind talk --interactive --output talk.json
agenteng proposal preview talk.json
agenteng proposal export talk.json --format markdown --output talk.md
```

`engage` asks a few questions for a future-event idea. The `draft` command also accepts explicit title, abstract, audience, outcomes, speaker name and optional contact fields. Incomplete drafts are allowed; preview returns missing fields. The default target is a possible future event. `--event EVENT_ID` selects a specific published event, which requires an actual open organizer-approved call for submission.

Drafts use versioned JSON and can be edited locally. CLI-created draft/export files have private permissions and never replace an existing file. No attachment or reference URL is fetched. MCP/A2A drafting returns structured text without writing files on the client machine. Optional contact details remain part of the exact draft preview.

Drafting, validation, export and intake do not call a model. If you enter a draft in an external LLM client, that client's own processing and privacy policy apply. The server's optional RLM is disabled by default and is not used for private proposals.

## Optional private pilot

Intake is **disabled by default**. The SQLite implementation is a bounded pilot for one organizer on a persistent private store. It does not provide public signup, verified-email identity, OAuth, automatic email notifications, a browser review dashboard or automatic program publication.

To operate it, configure:

- `AGENTENG_ENABLE_INTAKE=1`.
- `AGENTENG_INBOX`: private persistent SQLite file, outside the public catalogue and release directories.
- `AGENTENG_INTAKE_PRIVACY_NOTICE`: the operator's approved notice explaining recipient, intended use, retention, deletion contact and backup handling.
- `AGENTENG_INTAKE_RETENTION_DAYS`: active-record retention from receipt, default 90 days.
- `AGENTENG_INTAKE_CAPACITY`: maximum retained submissions, credentials and previews, default 1,000 each.

Use an encrypted persistent volume, restrict directory access to the organizer/runtime account and provide a backup/restore and backup-deletion policy. The application restricts the SQLite file to owner access; it does not encrypt SQLite itself. Retention purges run during store operations; schedule `agenteng inbox purge` daily so an idle store also expires records. Keep private bodies and authorization headers out of proxy, tracing and request logs.

**Do not enable this store on an ephemeral Cloud Run filesystem or replicate it across independent containers.** The supplied Cloud Run configuration is for public discovery and drafting. A private deployment needs persistent storage and a single shared store, or a separately implemented managed database.

### Participant access

On the private store host, the organizer issues a distinct credential for each participant:

```sh
agenteng inbox issue-access --days 90 --output participant-access.txt
```

The credential file is created with private permissions and the token is not printed. Share it with that participant through a private channel. Store it outside the repository. Tokens are hashed in the database, bounded in number and expire after the selected period. Expiry limits receipt access as well as submission; choose access duration appropriate to the pilot. `agenteng inbox revoke-access participant-access.txt` revokes access and outstanding previews. This pilot credential proves possession, not a verified personal identity.

Participants configure `AGENTENG_PARTICIPANT_TOKEN` in their own environment or client's supported secret settings. It is distinct from `AGENTENG_OPERATOR_TOKEN`, which authorizes optional model inference.

### Submit, inspect and withdraw

```sh
agenteng --remote https://YOUR_RUNNING_HOST proposal submit talk.json
agenteng --remote https://YOUR_RUNNING_HOST proposal status RECEIPT
agenteng --remote https://YOUR_RUNNING_HOST proposal withdraw RECEIPT
```

Submission first prepares a private preview and then asks for contributor confirmation. Preparation stores only a caller-bound draft hash, policy hash and expiring reference; it does not store the full draft as a submission. The reference lasts ten minutes and authorizes only that caller, draft and policy. An unchanged retry returns the same receipt within that window. A receipt is returned only after the database transaction commits. Status never exposes another participant's record.

Withdrawal requires confirmation and erases active proposal content. A minimal owner-scoped receipt/history tombstone remains until the original retention deadline. Withdrawal does not itself promise removal of backups or undo an independently agreed publication; those are handled under the operator's disclosed policy. Expired records and their history are deleted together.

Each participant can have five pending previews and make up to twenty submissions in a rolling day. Store capacity limits and the HTTP body/process limits apply as well. Enforce appropriate network-edge quotas for your deployment. Private responses are not cacheable and HTTP validation errors omit input values.

### Organizer review

Only the organizer with private filesystem access runs these commands:

```sh
agenteng inbox list
agenteng inbox review RECEIPT --status under_review
agenteng inbox review RECEIPT --status needs_information
agenteng inbox review RECEIPT --status accepted
agenteng inbox review RECEIPT --status declined
```

The list shows up to 100 recent records and contains private material; use a private terminal. Human status changes appear in the author's history. Acceptance is an organizer decision, not automatic scheduling or consent to publish. A withdrawn submission cannot be accepted through this interface. No organizer administration API is exposed remotely.

### Calls for specific events

Future-event drafts can enter an enabled general idea inbox. A draft targeting a specific event requires an organizer-configured call through `AGENTENG_CALLS`, a bounded JSON list. Each record contains `event_id`, timezone-aware `opens_at`, timezone-aware `closes_at`, and allowed `kinds` (`talk`, `workshop`, `event_idea`, `feedback`). The event must exist in the public catalogue and match the draft city; past/cancelled events are not open for intake.

The server checks the opening/closing window again inside the submission transaction. Changes to call/privacy configuration invalidate previously prepared previews. Configured calls cannot override the catalogue's invited-only speaking policy. No active call or deadline is included in the default configuration.
