# PHASE 8 — Packaging (week 16, started from week 4)

**Testbench README**: what the project measures → the architecture (one diagram) → **the master
results table**, technique by technique, with the gap to the literature, cost and latency
(including the "regeneration from scratch" row of phase 3 and the "cost of
governance" row of phase 6), and the classical ML / LLM decision tree of phase 5B → the
decisions and trade-offs → what broke and what I learned from it → what I would do
differently at 100× scale → the limits of the setup (no users, synthetic
traffic). The phases not done (10 if NO-GO) get their "not done, and
why" paragraph there.

**Two technical posts** drawn from the JOURNAL: "the evaluation harness I built, and
why standard metrics lie"; "self-host vs API: the full calculation, with my
numbers".

**One targeted open source contribution** in the ecosystem actually used.

**CV**: held by the program (`~/Roadmaps/program/docs/01-career-strategy.md` §7) and prepared
by module R4 of the Research Engineer roadmap; this testbench provides the numbers for the
"production and operations" block, not a separate CV (2026-10-19).

**Interview preparation**: timed AI system design, a build vs buy argument on three
building blocks, and **three incident stories in quantified situation-action-result
format**. They will not come from users — there are none — but from the construction itself:
a regression detected by the evaluation gate, a cost drift, a miscalibrated judge, a
quantization that silently degrades, a pipeline that rebuilds everything instead of the
increment. They are real incidents; they are kept up to date in `JOURNAL.md` as they happen,
never reconstructed after the fact.

**To verify at that point**: the reasoning about the word "pipeline" in job postings
(2026-10-15) rests on general knowledge of 2026 job postings, not on a reread corpus —
confront it with real postings.
