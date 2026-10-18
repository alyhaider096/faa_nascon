# Day 2 domain handoff

Prepared 18 October 2026 from the Day 1 baseline and the QA checkpoint.
This describes inspected code and local service checks. Deployed behavior remains
unverified. No shared backend was reset or modified to prepare this handoff.

## Completion and score reads

The mounted audit routes are in `app/api/domain_audit.py`:

| Operation | Interface | Result |
| --- | --- | --- |
| Current score and event history | `GET /audit/v1/score/{match_id}` | `status`, `home`, `away`, `version`, `events`, outcome/winner |
| League standings | `GET /audit/v1/standings/{league_id}` | `table`, `h2h`, `qualification_spots` |
| Append event | `POST /audit/v1/events` | 201 new event; 200 identical replay |
| Mobile match detail | `GET /api/v1/matches/{match_id}` | Authenticated projection plus `scoring_events` |
| Mobile standings | `GET /api/v1/leagues/{league_id}/standings` | Authenticated, tenant-scoped where registry exists |
| Mobile event append | `POST /api/v1/matches/{match_id}/events` | Scoped league organizer or super admin |

Use the existing event request shape. On an agreed disposable target, first read
the match and confirm it is `in_progress`; then completion is:

```json
{
  "event_id": "fatima-day2-match-m1-end-001",
  "match_id": "match-m1",
  "type": "match_end",
  "payload": {}
}
```

For example, with `$qaBase` explicitly configured in PowerShell:

```powershell
Invoke-RestMethod "$qaBase/audit/v1/score/match-m1"
$endBody = @{event_id='fatima-day2-match-m1-end-001'; match_id='match-m1'; type='match_end'; payload=@{}} | ConvertTo-Json -Depth 5
Invoke-RestMethod "$qaBase/audit/v1/events" -Method Post -ContentType 'application/json' -Body $endBody
Invoke-RestMethod "$qaBase/audit/v1/score/match-m1"
```

The new response contains event identity, sequence/match_version and signature;
read the projection for the resulting score/status. An exact retry with the same
event ID returns the original response and creates no second event/outbox record.
Changing the payload under that ID produces 409 `DUPLICATE_EVENT_ID`.
A different end event on an already completed match produces 409
`ILLEGAL_TRANSITION`. A tied sport that disallows draws requires a tiebreak winner.
Day 1 event signatures continue using DAY1_SALT; Day 2 QR response signing uses
DAY2_SALT in the QR implementation.

## Compensation after completion

```json
{
  "event_id": "fatima-day2-correction-001",
  "match_id": "match-m1",
  "type": "compensation",
  "payload": {"compensates": "EXISTING_SCORE_EVENT_ID", "reason": "review"}
}
```

Only a score, discipline or tiebreak event in the same match can be compensated,
once. The original payload/signature remains unchanged. The projection and
standings recompute; completion stays `completed`. Consumers must refresh on
version changes even after completion. A correction does not reopen a match or
reverse a `match_end` event.

## Postponement: service available, HTTP integration missing

Do not submit `match_postponed` to the event route: it is unsupported and returns
400 `VALIDATION_ERROR`. `app/domain/scheduling.py` exposes:

```python
# Existing synchronous SQLAlchemy session; caller authorizes and commits.
from backend.app.domain.scheduling import change_schedule_status
result = change_schedule_status(session, tenant_id, match_id, 'postponed')
```

The match must already have a `ScheduledMatch` row, created through `reschedule`
with authoritative venue, start/end UTC timestamps, teams, shared players, rest
constraints, venue windows and bracket dependencies. `register_league` creates
score-domain Match rows, not ScheduledMatch rows. Supplying a match ID alone does
not create the schedule row. Host code must authorize tenant/organizer ownership.
Use the caller's existing transaction; these services never commit themselves.

Permitted schedule transitions:

| From | To |
| --- | --- |
| upcoming | in_progress, postponed, cancelled |
| in_progress | completed, postponed, abandoned |
| postponed | upcoming, cancelled |
| completed / cancelled / abandoned | terminal |

Postponement marks transitive dependent fixtures for reevaluation, clears their
resolved slots and writes a `match_status_changed` domain-outbox notification.
It does **not** change `project_score(...)["status"]`. Local tests explicitly
confirm this distinction. Abdullah needs an authorized product route/orchestrator
and a shared effective-status reader for QR. A practical rule to agree on is that
postponed/cancelled/abandoned schedule status takes precedence over score status;
otherwise completion comes from the score projection. This is a proposed host
integration rule, not currently implemented behavior. Resumption must reconcile
the existing score stream rather than blindly appending another `match_start`.

## Overlay subscriptions and delivery gap

Current mounted socket: `/ws/v1/matches/{match_id}`, requiring a valid bearer
token via Authorization header or `?token=...`. It emits `hello`, then
`score_updated` with match_id, event_id and version. Fetch the score projection
after each update; the notification does not embed scores. Identical replays do
not broadcast a second update. Browser clients must avoid logging token URLs.

The Day 2 specification path `/ws/matches/{match_id}` is not currently mounted.
Guest overlay access also needs an agreed read-only authentication policy; the
existing socket requires authentication. Abdullah owns those integration changes.
The current in-process hub provides no demonstrated multi-process fan-out or
25-client latency result.

`append_and_notify` publishes after its platform transaction returns. Domain
services separately write `domain_outbox`. The existing worker reads platform
`outbox`; it is not proof of delivery from `domain_outbox`. Schedule changes
therefore need a committed domain-outbox consumer (or equivalent reliable host
integration). Do not assume media termination, VOD indexing or QR invalidation
already consume these records. Consumers should deduplicate by event/outbox ID,
refresh authoritative state and retry delivery without deleting pending records.

## Owner actions and acceptance

| Owner | Next action |
| --- | --- |
| Fatima | Supply tested domain transitions and regression evidence; verify integrated paths when reachable |
| Abdullah | Mount authorized postponement orchestration; settle effective status; connect committed notifications to QR/media; provide guest socket contract and required path |
| Ali | Consume agreed read/subscription interfaces; refresh scores by version; preserve guest read-only behavior |

Local evidence: `tests/domain/test_day2_handoff.py` and
`tests/reports/domain-handoff.xml` cover completion persistence, standings,
identical replay, immutable compensation, rollback without orphan notifications,
and the separate schedule/score state. SQLite results do not establish PostgreSQL
concurrency, live socket delivery, QR/VOD behavior or latency. Full regression
results are indexed in `tests/reports/EVIDENCE.md`.
