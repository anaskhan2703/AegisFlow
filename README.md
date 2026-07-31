# AegisFlow SOAR Platform

A security analytics and SOAR (Security Orchestration, Automation, and Response)
simulation platform integrating threat intelligence feeds, AI-assisted alert
analysis, and automated incident response workflows.

Built to demonstrate security engineering, threat intelligence, incident
response, identity risk management, AI-assisted security analysis, and
full-stack development — using entirely free/open-source tools and simulated
security data.

## Status

🚧 Phase 1 — Foundation. Core services are scaffolded and networked via Docker
Compose; feature modules land in later phases. See `PROGRESS.md` for the
current build status.

## Architecture

- **Backend:** FastAPI (Python) — REST API, threat intel enrichment, AI
  analyst, identity risk scoring, SOAR playbook orchestration
- **Frontend:** React + TypeScript + Tailwind CSS — SOC-style dashboard
- **Database:** PostgreSQL
- **AI:** Provider-agnostic interface — local Ollama models (Llama 3.1 /
  Mistral) or Google Gemini free tier
- **Monitoring:** Prometheus + Grafana (added in Phase 8)

See `docs/architecture.md` for the full design.

## Quick Start

```bash
cp .env.example .env       # then edit values as needed
docker compose up
```

- Backend: http://localhost:8000 (API docs at `/docs`)
- Frontend: http://localhost:3000
- Database: `localhost:5432`

## Project Structure

```
aegisflow/
├── backend/     # FastAPI app
├── frontend/    # React + TS + Tailwind app
├── database/    # init scripts, seed data generator
├── monitoring/  # Prometheus + Grafana config
├── docs/        # architecture, API docs, screenshots
└── docker-compose.yml
```

## Security Considerations

This project uses simulated/dummy security data and is intended as a
portfolio and learning platform — it does not connect to real enterprise
EDR/SIEM systems. Threat intelligence enrichment uses free-tier public APIs
(VirusTotal, AbuseIPDB) with a built-in simulator fallback when those APIs
are unavailable or rate-limited.

## License

MIT
