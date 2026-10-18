"""LLM-as-judge for faithfulness/helpfulness. Use a different model family than the one under
test (JUDGE_MODEL). Calibrate: hand-label 40 cases in evals/judge_calibration.jsonl and report
agreement in the README (target >= 85%)."""

from __future__ import annotations

import json
from typing import Any

from agent.llm import complete
from core.config import settings

JUDGE_PROMPT = """You grade answers from a restaurant operations assistant.

Rubric for this case: {rubric}

User question: {question}
Tool results the assistant saw (ground truth): {evidence}
Assistant answer: {answer}

Score 1-5 for each:
- faithfulness: every claim is supported by the tool results; no invented numbers or people
- helpfulness: answers what was asked, concise, actionable

Return JSON only: {{"faithfulness": n, "helpfulness": n, "reason": "<one sentence>"}}"""


def judge(question: str, answer: str, evidence: list[Any], rubric: str) -> dict[str, Any]:
    resp = complete([{"role": "user", "content": JUDGE_PROMPT.format(
        rubric=rubric or "faithful and helpful", question=question,
        evidence=json.dumps(evidence, ensure_ascii=False)[:8000], answer=answer)}],
        model=settings().judge_model, json_mode=True, metadata={"node": "judge"})
    try:
        return json.loads(resp.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        return {"faithfulness": 0, "helpfulness": 0, "reason": "judge returned invalid JSON"}
