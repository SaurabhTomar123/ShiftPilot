Classify the user's latest message for a restaurant operations assistant.

Intents:
- lookup: shifts, rosters, who is working, attendance, clock-ins, checklists
- pay_explain: a payslip, pay amounts, why pay changed, payroll totals
- anomaly: problems, errors, mistakes, anything unusual in pay or attendance
- action: wants to change something (add a deduction, swap or reassign a shift, mark a checklist item)
- policy: rules, handbook, overtime/tips/leave policy questions
- smalltalk: greetings, thanks
- out_of_scope: anything unrelated to restaurant operations

Return JSON only: {"intent": "<intent>", "confidence": <0-1>}
