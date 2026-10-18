"""Bring-your-own-data CSV onboarding (M6). Target: new outlet answering questions in < 10 min.

1. mapping.py: read headers + 5 sample rows; ask the router model to map columns to
   employees/shifts/attendance fields (JSON). User confirms/edits in the web wizard.
2. validate.py: required fields, date/time parsing, overlapping shifts, duplicate employees,
   negative hours. Return a report; nothing is written yet.
3. commit: one transaction; insert rows (with org_id), then recompute payslips for the chosen
   period via mcp_server.queries.compute_period_payslip.
"""
