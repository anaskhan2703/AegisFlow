# AegisFlow

A SOAR (Security Orchestration, Automation, and Response) platform that simulates a real SOC workflow end to end: an alert comes in, gets enriched with threat intelligence, triaged by an AI analyst, matched against automated playbooks, and escalated into a tracked incident — all with full RBAC and an audit trail.

Built as a portfolio project to demonstrate backend architecture, secure API design, and full-stack delivery on a system that mirrors what a security engineering team actually operates, rather than a toy CRUD app.

**Stack:** FastAPI · PostgreSQL · SQLAlchemy · React + TypeScript + Tailwind · Docker Compose · Gemini API (with a deterministic simulator fallback) · VirusTotal / AbuseIPDB

---

## Why this exists

Most portfolio projects show a form talking to a database. AegisFlow tries to show something closer to what a SOC analyst tool actually has to get right: layered trust boundaries (RBAC across admin/analyst/viewer roles), decisions that have to be explainable after the fact (every incident status change and playbook run is written to an audit trail), and integrations that have to degrade gracefully when a third-party API is down, rate-limited, or simply not configured (every external dependency — threat intel, AI triage — has a deterministic fallback so the system is fully demoable without any paid API keys).

## What it does

**Alert ingestion & correlation.** Alerts carry raw indicators (IPs, domains, hashes, file paths). A regex-based extractor pulls indicators out (handling defanged formats like `hxxp://` and `1.2.3[.]4`), each one gets a threat intelligence lookup, and a severity-weighted correlation score decides how serious the alert is.

**Threat intelligence enrichment.** Real lookups against VirusTotal and AbuseIPDB free tiers, behind a provider-abstraction layer with a 24-hour cache. If no API key is configured, or a provider fails, it falls back to a deterministic hash-seeded simulator — same interface, so the rest of the system never has to know which one answered.

**AI-assisted triage.** Each alert can get a structured AI analyst report (summary, likely MITRE ATT&CK technique, recommended next actions) via the Gemini API, with the same fallback pattern as threat intel: no key or a failed call drops to a rule-based simulator that produces a structurally identical report.

**Playbook automation.** Admins define playbooks as structured JSON — condition lists (`field`, `operator`, `value`) evaluated against a fixed allow-list, never a free-text or `eval()`-style rule language, so a malformed or malicious condition is rejected at creation time, not at execution time. Every alert create/update automatically re-evaluates active playbooks; steps like `update_alert_status` and `create_incident` auto-execute, while higher-risk actions like `isolate_host` or `block_ip` are logged as *recommended* rather than run — the kind of human-in-the-loop boundary a real SOC tool needs. Every run, automatic or manual, is recorded with a full snapshot of the conditions and per-step results.

**Incident management.** Incidents can be created manually or automatically by a playbook, linked back to their originating alert, and tracked through an unrestricted status lifecycle (deliberately not a rigid state machine — the audit log is the source of truth, not a transition allow-list). Every creation and status change writes to `audit_logs`.

**Role-based access control.** Three roles (admin / soc_analyst / viewer) enforced identically on the backend and mirrored in the frontend — the UI hides controls a role can't use, but that's a UX nicety layered on top of real 403s, not a substitute for them.

## Architecture

**Frontend** — React + TypeScript (Vite), talks to the backend over a typed REST client.

**Backend** — FastAPI, organized by domain: Auth/RBAC, Alerts, Threat Intel, AI Triage, Playbooks, Incidents.

**Data layer** — PostgreSQL via SQLAlchemy (sync sessions) + Alembic migrations.

**External integrations** — VirusTotal, AbuseIPDB, and Gemini, each behind a provider-abstraction layer with a deterministic simulator fallback, so no external dependency is required to run or demo the system.

**Alert lifecycle:** ingest → indicator extraction → threat intel enrichment → correlation scoring → automatic playbook evaluation → optional incident creation, with on-demand AI triage available at any point.

Alert flow: **ingest → indicator extraction → threat intel enrichment → correlation scoring → automatic playbook evaluation → (optional) incident creation**, with AI triage available on-demand at any point in that lifecycle.

## Design decisions worth asking about

A few choices made deliberately, with the reasoning, since these tend to be better interview conversations than the feature list itself:

- **Structured playbook conditions over a mini rule-language.** It would've been faster to let admins write a condition as a small expression string. Instead conditions are `{field, operator, value}` objects validated against a fixed allow-list — slower to build, but it closes off an entire class of injection risk and keeps every condition auditable and diffable.
- **No ORM `relationship()` anywhere in the schema.** Every cross-model lookup (alert ↔ threat indicator, incident ↔ alert) is an explicit query. One extra line per lookup, in exchange for never having to reason about lazy-loading behavior or N+1 surprises hiding behind an attribute access.
- **Everything external has a fallback, and the fallback is deterministic.** Threat intel and AI triage both degrade to a rule-based/hash-seeded simulator rather than erroring out. This wasn't just for demo convenience — it's the same pattern a real system needs for provider outages, and it means the whole platform can be evaluated end-to-end with zero paid API keys.
- **RBAC enforcement lives on the backend; the frontend just reflects it.** The UI's role gating was verified against real 403 responses from every mutating endpoint, not assumed from reading the backend code — the two were built and tested as separate claims, not one trusted to imply the other.
- **Audit logging was added where it was actually needed, not everywhere speculatively.** `audit_logs` existed in the schema from the start but stayed unused until incident management needed it — a conscious choice to wire up traceability where the workflow demanded it rather than instrumenting every table "just in case."

## Running it

```bash
git clone https://github.com/anaskhan2703/AegisFlow.git
cd AegisFlow
cp .env.example .env   # fill in DB creds; VirusTotal/AbuseIPDB/Gemini keys are optional — simulator fallback covers all of them
docker compose up --build
```

- Frontend: `http://localhost:3000`
- Backend + interactive API docs: `http://localhost:8000/docs`
- Database: `localhost:5432`

Register a user (defaults to `viewer`), or promote one to `admin`/`soc_analyst` directly in Postgres to exercise the full playbook/incident workflows. A "Generate demo alerts" action in the dashboard seeds realistic sample data without needing any external API keys.

## Project status

Phases 1–8 are complete: auth/RBAC, threat intel enrichment, alert correlation, AI-assisted triage, playbook automation, incident management, and the full React dashboard (alert triage, playbook builder, incident management, overview dashboard). See `PROGRESS.md` for the phase-by-phase build log, including what was live-verified vs. code-reviewed at each stage.

Still ahead: Prometheus/Grafana monitoring and a final polish pass.

## License

MIT
