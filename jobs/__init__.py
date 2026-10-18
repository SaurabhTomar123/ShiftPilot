"""Background jobs (M4). Must be idempotent (safe to re-run).

- jobs/anomaly_scan.py: nightly; call read.list_anomalies per outlet as the owner, store new
  findings, notify the outlet manager (WhatsApp template) with the evidence text.
- jobs/morning_brief.py: 09:00 IST; staffing gaps today (get_shifts vs. template), pending
  approvals (/actions), open anomalies. One message per manager.
Scheduler: APScheduler (in-process) or Arq (Redis) — REDIS_URL is already configured.
"""
