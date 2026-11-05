# Judge calibration set

What the LLM judge is calibrated against (ADR 012): generated answers, each labelled by
hand on two questions.

- `items.jsonl` — the items, drawn by `make eval-calibration-set` from the archived
  generation run. An item names the examples its question, its passages and its answer come
  from (`question_from`, `passages_from`, `answer_from`) and holds the generated answer. No
  dataset text is stored: it is read back from SQuAD 2.0 (CC BY-SA 4.0) by the loader.
  `kind` says whether the passage or the question was swapped; the annotation tool never
  shows it.
- `labels.jsonl` — the human labels, written by `make eval-annotate`, one line per item as
  it is answered. Relabelling an item appends a line; the last one wins.

Labelling rules, as shown by the tool:

- **Supported** — yes when every claim of the answer is stated in the excerpts or follows
  directly from them; no when at least one claim is not there or is contradicted. Outside
  knowledge does not count, and a citation marker is not a proof.
- **Relevant** — yes when the answer gives the kind of thing the question asks for, about
  the thing it asks about, even partially; no when it answers something else. Whether the
  answer is right or supported does not count here.

## Changelog

- 2026-11-05 — v1: items drawn from the generation run of that day (seed 0).
