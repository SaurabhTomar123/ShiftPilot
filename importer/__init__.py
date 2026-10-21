"""Onboarding imports (architecture v3 section 19).

employees_csv: the fixed employee CSV template, parsed and validated without touching the database.
api.v2.imports stages a file, reports row-level errors and commits every row in one transaction.
Fuzzy or AI-assisted column mapping is a later enhancement, not part of the MVP.
"""
