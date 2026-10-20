# PHASE 7 — Residual security and compliance (week 16, shared with phase 8)

Most of it was handled in phase 4 (tool security, AgentDojo) and in phase 5 (audit,
logging). What remains:

- OWASP LLM Top 10 applied to the complete architecture;
- indirect injection through a poisoned **document** in the corpus (the poisoned documents
  come from the in-house corpus of phase 2.5);
- exfiltration via the citations;
- output filtering — ours, and for comparison **Bedrock Guardrails** (PII, denied
  topics, contextual grounding) on the same attack set: block rate, false positives,
  added latency, cost; optional, decided at the phase plan;
- PII detection and masking (Presidio);
- automated red teaming (garak, promptfoo redteam) in CI.

Then `docs/ai-act.md`: a compliance exercise **applied to a hypothetical enterprise
deployment** — the testbench has no users, so set the frame explicitly, then
the risk classification under the EU AI Act, the documentation and logging obligations,
and GDPR minimization. The defensibility grid of phase 5B attaches to it. The goal is for me
to be able to hold this conversation in an interview, not to produce a
regulatory dossier.
