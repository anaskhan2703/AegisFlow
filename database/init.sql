-- AegisFlow database initialization
-- Phase 1: placeholder only. Full schema (users, alerts, threat_indicators,
-- risk_scores, ai_reports, playbooks, incidents, audit_logs) is created via
-- Alembic migrations in Phase 2 — this file just confirms the DB is reachable
-- and ready to receive migrations.

SELECT 'AegisFlow database initialized' AS status;
