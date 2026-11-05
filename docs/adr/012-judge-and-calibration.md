# ADR 012 — The judge, its calibration, and a spend cap

- **Date**: 2026-11-05
- **Status**: accepted

## Context

Phase 2.3 asks for an LLM judge "done right": explicit rubrics, discrete scoring,
justification before the score, a judge that is not the generator, and a calibration
against 50 examples labelled by hand. On 2026-11-05 Christophe also set the budget of the
whole phase 2 baseline: the lean option, about $5, under a hard cap of $10.

## Decisions

**1. Code measures what code can, the judge only the rest.** Refusals, citations and the
presence of the reference answer are computed (`eval/metrics/generation.py`), on the
generator fed with the gold passages so that retrieval is out of the picture
(`eval/generation.py`). The judge is kept for the two properties that need reading:
groundedness (is every claim in the excerpts) and relevance (does the answer address the
question).

**2. One rubric per property, a yes-or-no verdict, the reasons first.** Each rubric is a
versioned prompt (`prompts/judge_groundedness.md`, `prompts/judge_relevance.md`) that says
what to check and what to ignore: length and style (verbosity bias), citation markers
(format bias), what the judge knows from elsewhere. The output schema puts the
justification before the verdict. Rejected: a 1-to-5 scale, which no two graders read the
same way and which fifty items cannot calibrate; one prompt for both properties, where a
supported answer drags its relevance up. The relevance judge is not shown the excerpts.

**3. The judge is a cheaper model from another provider, and the calibration decides
whether that is good enough.** Generator `anthropic/claude-sonnet-5-5`, judge
`openai/gpt-5.6-luna`; `openai/gpt-5.6-terra` grades the calibration items only, as the
arm that says what the cheaper judge loses. Rejected for cost: the stronger judge
everywhere (about ten times the price).

**4. Acceptance rule, written before any label exists.** A judge is used on a rubric if
its Cohen's kappa with the human labels is at least 0.6 on that rubric. Below: the rubric
prompt is revised (new version, re-measured, twice at most), then the stronger judge is
tried; if nothing reaches 0.6, the metric is reported as not measured rather than quoted
from an unreliable judge.

**5. The calibration set is made of real answers, and of both verdicts.** 50 answers from
the archived generation run. On gold context nearly all of them are supported and on topic,
and agreement on a one-sided set measures nothing; so 10 are shown against another passage
of the same article and 10 against another question. The human labels all 50 blind, in a
terminal (`make eval-annotate`), and those labels are the truth; the swaps only guarantee
that both verdicts occur. An item stores example ids, not dataset text; labels are
appended, never rewritten.

**6. A hard cap in dollars.** `config/eval_suites.toml` sets `budget.cap_usd = 10`. Every
paid run goes through `eval/spend.py`: a versioned ledger (`data/results/spend.jsonl`), a
check before each call, a refusal on a model without a known price, and the amount written
even when the run stops on an error.

**7. Non-determinism is measured, not assumed away.** A generation arm asks part of its
questions several times; the record reports the share whose refusal flips and the share
whose wording changes (phase 2.4).

## Consequences

- Sizes follow the budget: 100 questions (half unanswerable), 50 of them asked three
  times. A rate is known to about ±0.10 on 50 questions; the interval is printed with it.
- One annotator: there is no measure of how consistent the human is with himself, and
  kappa on 50 items has an uncertainty of its own (about ±0.2). The swapped items are
  easier to catch than a real unsupported claim, so the kappa measured is an upper bound
  on what the judge does on subtle cases. To be said wherever the number is shown.
- SQuAD 2.0 only for now; QASPER and HotpotQA answers join the calibration set if their
  generation arms change what the judge has to read (long passages, several excerpts).
- The self-preference check (an OpenAI generator graded by an Anthropic judge) is not paid
  for until the first calibration says the judge is usable at all.
