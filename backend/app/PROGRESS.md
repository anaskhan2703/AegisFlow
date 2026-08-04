# AegisFlow — Progress Log

## Phase 1 — Foundation
Status: ✅ Complete
- Repo scaffolded: full folder structure (backend/frontend/database/monitoring/docs)
- Docker Compose: db (Postgres 16), backend (FastAPI), frontend (React+TS+Tailwind) networked
- Services & ports:
  - backend → http://localhost:8000 (docs at /docs, health at /health)
  - frontend → http://localhost:3000
  - db → localhost:5432

## Phase 2 — Auth & DB schema
Status: ✅ Complete (verified locally against a live Postgres instance before delivery)
- 8 core tables via real Alembic autogenerate migration, JWT auth (access 30min / refresh 7day), bcrypt hashing, RBAC (admin/soc_analyst/viewer), 4 auth endpoints — all exercised live with curl.

## Phase 3 — Threat Intel module
Status: ✅ Complete (verified locally against a live Postgres 16 instance before delivery)
- Provider-abstraction pattern (ThreatIntelProvider ABC), deterministic hash-seeded simulator as default, real VirusTotal + AbuseIPDB free-tier clients, factory with automatic fallback to simulator on missing keys or provider failure. 24h cache window. Never raises.

## Phase 4 — Identity Risk engine
Status: ✅ Complete and verified working in the real Docker environment
- Regex-based indicator extraction with defang-handling, async correlator (extraction → cache check → threat intel lookup → severity-weighted scoring), 5 demo alert templates, 5 alert endpoints, 3 new Alert columns via migration `4a365bafd615`.

## Phase 5 — AI Analyst
Status: ✅ Core path verified end-to-end against the live Gemini API. No-key/failure→simulator fallback, RBAC 403 on viewer, and the two GET endpoints were designed and code-reviewed but not yet confirmed live at time of writing — worth a quick live check before treating as fully closed.

## Phase 6 — Playbook Automation
Status: ✅ Complete and verified end-to-end against a live Postgres 16 instance + a running FastAPI app

Key design decisions (all confirmed live):
1. **Trigger model**: automatic. Every alert create and status update re-evaluates all active, `trigger_type="automatic"` playbooks against that alert.
2. **Trigger conditions**: structured JSON (`{"field":..., "op":..., "value":...}`, ANDed list) with a fixed field allow-list and operator dict (`app/services/playbook_engine/rules.py`) — never an eval()-style mini-language. Verified an injection-style field (`__class__`) is rejected with 400 at creation time.
3. **Execution history**: `playbook_executions` table (migration `2387e5fbde4b`), one row per run, snapshots conditions + per-step results so the audit trail survives later playbook edits.

What was built: `app/models/playbook.py` (+trigger_conditions), `app/models/playbook_execution.py`, `app/services/playbook_engine/{rules,actions,engine}.py` (ACTION_REGISTRY: auto-executable `update_alert_status`/`flag_indicator`/`create_incident`/`notify_analyst`; manual-only `isolate_host`/`disable_account`/`block_ip`, always logged as "recommended, not auto-executed"), `app/schemas/playbook.py`, `app/api/v1/playbooks.py` (CRUD admin-only, run endpoint admin/soc_analyst, executions read any role — route ordering matters: `/executions/` before `/{playbook_id}`), hooks in `app/api/v1/alerts.py` after ingest and after status update (playbook failure can't corrupt the alert write — separate commit).

Live verification: all 3 migrations apply cleanly in sequence and phase6 alone up/down/up-cycles against a DB with a pre-existing playbook row; created a real 2-condition playbook, ingested an alert engineered to cross the threshold (correlation_score landed 91), confirmed automatic firing (status flip, Incident created, ThreatIndicator severity bumped, isolate_host correctly logged as not-executed); confirmed a non-matching alert produces zero executions; confirmed RBAC (viewer 403 on create/manual-run) and input validation (unknown action/field → 400) live.

⚠️ **Lessons carried forward:**
- Sandbox background processes need `setsid ... &` to survive across tool calls (plain `&`/`nohup` gets killed when the shell exits).
- Sandbox filesystem/Postgres data survives resets even when running processes don't — "server stopped responding" is a restart problem, not a data-loss problem.
- The threat_intel simulator always scores any indicator containing "evil"/"malware"/"phish"/"bad-"/"botnet" as 85–100/critical — reliable way to generate high-confidence demo alerts (used again in Phase 7 testing below).
- Manual playbook runs always execute regardless of conditions (conditions are recorded, not enforced) — deliberately different from the automatic path. A future "run playbook" UI should surface the conditions and whether they currently match, even though the click still goes through.

## Phase 7 — Incident Management API
Status: ✅ Complete and verified end-to-end against a live Postgres 16 instance + a running FastAPI app (no Docker in the build sandbox — Postgres 16 installed directly, real uvicorn process, real HTTP round-trips)

**Why this phase exists / renumbering note:** PROGRESS.md originally had Phase 7 = frontend dashboard. At kickoff we found the `Incident` model (from Phase 2) had zero API surface — no schemas, no router, nothing — even though Phase 6's playbooks already create Incident rows via the `create_incident` action. Decision made at kickoff: build the Incident CRUD/status API as its own phase before the frontend, so the dashboard has something real to render incidents from. Everything from here is renumbered one slot later than originally planned (old Phase 7 "Frontend dashboard" is now Phase 8; old Phase 8 "Grafana + polish" is now Phase 9).

Design decisions made at kickoff:
1. **No new migration needed.** The `incidents` table (and `audit_logs`) were already created in Phase 2's initial migration with every column the current `Incident` model uses — confirmed by diffing the model against `68f31eee722e_initial_schema_8_core_tables.py` before writing any code.
2. **Status transitions are unrestricted**, not a state machine — consistent with this project's existing preference (see Phase 6's condition-language decision) for simple, auditable logic over encoded rules. Safety comes from the audit trail, not a transition allow-list.
3. **First real use of `audit_logs`.** The table existed since Phase 2 but nothing wrote to it. Every incident creation and every status change now writes a row (`action="incident_created"` / `"incident_status_change"`, with before/after in `details`). Good interview point: shipped the audit trail on the resource that most needed one, not speculatively everywhere.
4. **Related-alert summary is nested, not a separate call.** `GET`/`POST`/`PATCH` responses include a small `related_alert` object (id, type, hostname, severity, correlation_score, status) so a frontend incident card/detail view doesn't need a second round-trip to `/api/v1/alerts/{id}`. Batched (not N+1) on the list endpoint.
5. **No ORM `relationship()`.** Every other cross-model lookup in this codebase (e.g. the Alert↔ThreatIndicator join in `api/v1/alerts.py`) is an explicit query, not a SQLAlchemy relationship — stayed consistent with that pattern rather than introducing the one relationship in the whole schema.

What was built:
- `app/schemas/incident.py` — `IncidentCreate`, `IncidentUpdate`, `IncidentResponse`, `IncidentListResponse`, `RelatedAlertSummary`.
- `app/api/v1/incidents.py`:
  - `POST /api/v1/incidents/` (admin/soc_analyst) — manual incident creation, independent of playbooks. 400 if `related_alert_id` or `assigned_to` doesn't match a real row (checked explicitly rather than letting a raw FK violation surface as a 500).
  - `GET /api/v1/incidents/` (any role) — list, filterable by `status` + `severity`, paginated, related alerts batch-fetched.
  - `GET /api/v1/incidents/{id}` (any role) — detail with nested related alert.
  - `PATCH /api/v1/incidents/{id}` (admin/soc_analyst) — partial update; a `status` change to `resolved`/`closed` stamps `resolved_at`, moving back to `open`/`in_progress` clears it; writes an `AuditLog` row only when status actually changed.
- `app/main.py` — wired in the incidents router.

Live verification performed this phase (actual Postgres 16 installed in-sandbox + actual running uvicorn, actual HTTP calls, no code-review-only steps):
- All 3 existing migrations (`68f31eee722e` → `4a365bafd615` → `2387e5fbde4b`) applied cleanly to a fresh DB with zero changes needed — confirming the "no new migration" design call was correct, not just assumed.
- Registered admin/soc_analyst/viewer users, got real JWTs.
- Generated a real demo C2 beacon alert (via the "evil-c2-domain.net" trick from Phase 6's lessons) — correlation_score landed at 97.
- Created an incident linked to that alert as soc_analyst (201, nested `related_alert` populated correctly); the same call as viewer correctly returned 403.
- Confirmed 400s on a bogus `related_alert_id` at create time and a bogus `assigned_to` at update time.
- Walked a real status lifecycle: `open → in_progress → resolved` (confirmed `resolved_at` gets stamped) `→ open` (confirmed `resolved_at` clears on reopen).
- Queried `audit_logs` directly in Postgres and confirmed 4 real rows: 1 `incident_created` + 3 `incident_status_change`, each with correct `from`/`to` in `details` — this is the first time that table has ever had a row written to it in the project.
- Confirmed `status=open` filtering returns the right count, viewer can `GET` detail (200) and gets a real 404 on a nonexistent id, and a standalone incident with no `related_alert_id` serializes with `related_alert: null` cleanly (not an error) alongside one that does have a link, in the same list call.
- Confirmed both new routes appear in `/openapi.json` (`/api/v1/incidents/`, `/api/v1/incidents/{incident_id}`).

## Phase 8 — Frontend dashboard (renumbered from Phase 7)
Status: ⬜ Not started

Confirmed direction from Phase 7 kickoff: deep alert-triage workflow first (alert list → detail → correlation/indicator view → AI report → manual playbook run), not a broad shallow overview of every module. Incidents now have a real API to build against as of Phase 7. Current frontend state: still exactly the Phase 1 scaffold (health-check ping only) — `react-router-dom` is already in `package.json` but unused; no other UI/data-fetching/charting libraries installed yet, no auth/token handling in the frontend at all. All of that is greenfield for this phase.

## Phase 9 — Grafana + polish (renumbered from Phase 8)
Status: ⬜ Not started

---

## Key learnings & principles (carried forward, updated)

- **Live validation over memory-generated code** — every phase so far has been verified against a real running stack before handoff, not just code review. Phase 6 and 7 both had no Docker in the build sandbox, so Postgres 16 was installed directly and a real uvicorn process run in-place; this has repeatedly caught things code review alone wouldn't (Phase 6: correlation_score is computed, not copied from the payload's `severity` field; Phase 7: confirmed zero new migration was actually needed rather than assuming it from the model diff alone).
- **Give Claude direct repo access at kickoff** — `codeload.github.com` tarball download is the reliable path when the GitHub API is rate-limited unauthenticated (`api.github.com/repos/.../git/trees` failed this way in Phase 7); go straight to codeload rather than retrying the API.
- **Structured data over embedded mini-languages** for anything user-editable that gates automated actions (Phase 6's trigger conditions).
- **Config/model/schema files are high-risk merge targets** — flagged explicitly, never silently overwritten.
- **Hand over complete files, not diffs**, for anything beyond a one-line change.
- **Conceptual grounding matters** — every phase opens with a short design discussion (and, where the plan itself has a gap or ambiguity like Phase 7's incidents question, a clarifying question) before any code is written.
- **Don't let unused-but-modeled tables stay unused** — `audit_logs` existed since Phase 2 with nothing writing to it; Phase 7 was the natural point to wire it up on the resource that most needed a trail, rather than leaving it as a fully speculative feature.

## Approach & patterns (carried forward)

- Phase-based build with a new chat per phase, `PROGRESS.md` + phase kickoff doc pasted in to start.
- Prefer giving Claude direct repo read access (public GitHub URL, or a specific branch) over pasting files, when available.
- Errors are pasted back for iterative fixing rather than speculated on.
- `PROGRESS.md` is the handoff artifact between phases.