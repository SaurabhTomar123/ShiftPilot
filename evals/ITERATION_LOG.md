# Eval iteration log

One entry per change that moved the numbers. This file is the story you tell in interviews and the blog post.

| Date | Change | Why (failure category) | Task success | Tool acc. | Security | p95 | ₹/conv |
|---|---|---|---|---|---|---|---|
| YYYY-MM-DD | Baseline: system_v1, router_v1, Sonnet main | — | | | | | |

## Failure taxonomy
Tag every failed case with one: `wrong_tool` · `wrong_args` · `missed_disambiguation` · `invented_number` · `over_refusal` · `under_refusal` · `formatting` · `retrieval_miss`.

## Entry template
### YYYY-MM-DD — <short title>
- **Observed:** which cases failed and how (link report JSON)
- **Hypothesis:**
- **Change:** prompt / tool / graph / model (file + version)
- **Result:** before → after on the full suite (3 runs, mean ± stdev)
