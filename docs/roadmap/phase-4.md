# PHASE 4 — Multi-source agents (weeks 9–11) ⭐ ON PAR WITH RAG

In my past engagements, my agents queried SQL databases, business APIs, structured data
and images. It is my engineering ground and the segment that commoditizes the least
quickly. It is not an appendix to RAG. Each connector plugs into the phase 1
`Source` interface.

**4.1 Orchestration foundation.** First a **homemade state machine**, then the same thing with
LangGraph, and explain to me honestly what the framework brings and what it hides. Tool
schemas, strict Pydantic validation, tool errors returned in an actionable way.
Guardrails: step and token budget, loop detection, global timeout, graceful
degradation to an honest partial answer. Parallelization of independent calls.

**Agent framework benchmark**: the same reference agent ported to **smolagents,
OpenAI Agents SDK and CrewAI**, measured on the same harness — accuracy on the same tasks,
tokens, latency, lines of code. Reason to exist: the ATS/keyword filter of job postings, and a
quantified comparison that almost nobody publishes. Anti-stacking guard: these ports are
**comparison deliverables**, not production code — `src/` keeps a single implementation
(homemade + LangGraph), the ports live in the benchmark material. Budget: about one
day per framework, do not dig further. **Optional, if the question comes back (PD-18)**:
**Bedrock AgentCore** as an additional port — AWS's managed agent runtime against our
self-hosted agent, same harness, same one-day budget; decided at the phase plan, just as
phase 6 compares self-hosting and API.

**4.2 SQL — the hardest block, measured on Spider and BIRD Mini-Dev.** The full schema
does not fit in the context: schema catalog and **retrieval over the schema** (RAG
applied to metadata, a bridge with phase 3). Safety pipeline before execution: parsing
of the generated query (sqlglot), allowlist of tables and columns, DDL/DML ban, forced `LIMIT`,
prior `EXPLAIN` to reject overly expensive queries, timeout, read-only Postgres
role, row-level security. Correction loop on SQL error, with a budget. Traps to
handle explicitly: plausible but wrong joins, an empty result interpreted as "there are
none", aggregations and `NULL`, dates and time zones. **Absolute rule: the model never
recomputes a number, it returns the result of the query.** Metric: execution
accuracy, not text comparison.

**4.3 Business APIs.** Tools derived from an OpenAPI spec rather than written by hand.
Pagination, rate limits, idempotency, retries. Strict read / write separation with
**mandatory human confirmation on side effects**. Propagation of the user identity all the
way to the API, demonstrated on simulated identities (tau2-bench provides some): no shared key
that gives every right to everyone.

**4.4 Structured data and time series.** Never a large table as raw text to the
model: deterministic aggregation tools, or code execution in a sandbox (no network,
limited resources and duration). Arithmetic is done by code, never by the model.

**4.5 Images and non-text documents** — measured on DocVQA and ChartQA (sampled), and
CORD/FUNSD for extraction. **Structured** extraction with an enforced Pydantic schema, never a
free description. Field-by-field accuracy.

**4.6 Routing between sources — the real architecture decision.** Documents, database, API, or
several? Compare an explicit router and an agent that decides on its own, and **measure
both**. Handle hybrid questions and the case where two sources contradict each other: an
explicit priority policy or flagging the conflict, never a silent choice.

**4.7 Tool security.** Indirect injection via the **data returned by a tool** —
a poisoned text field in the database, a hostile API response: this is the real threat to an
agent. **AgentDojo** benchmark. Strict instructions / data separation, tool allowlist per
context, sandboxing, user permissions propagated end to end, audit log of the
actions. Craft the attacks, show that they work, fix, retest, re-measure.

**4.8 MCP server and composition.** Expose our tools via MCP, then make it consume **several
servers**: dynamic discovery, permission governance, behavior when a server
becomes unavailable or returns garbage. Many know how to expose an MCP server; very
few know how to orchestrate several of them cleanly. Also position the **A2A**
(agent-to-agent) protocol relative to MCP — as a reasoned discussion in the notebook, not as
an implementation.

**4.9 Extended evaluation** — measured on BFCL and tau2-bench. The ground truth is no longer
a passage, which changes the metrics: trajectories (tools called, order, arguments, number
of steps, cost per successful task), SQL execution accuracy, per-field accuracy in
extraction, routing confusion matrix, faithfulness of the cited numbers. **Extend the phase 2
harness, do not create a second harness.**

**4.10 Agent memory.** Intra-session conversational memory and long-term cross-session
memory — it is retrieval applied to the history of exchanges, so a direct
reuse of phase 3, not an exotic building block. What to retain, where to store it, when to
inject it, and **the measured effect**: gain on multi-turn tasks (tau2-bench) versus the
token cost of each strategy. Along the way, situate the "context engineering" vocabulary and
the landscape (mem0, LangGraph checkpointing) — as knowledge; our implementation stays our own.

**Mandatory seniority point**: deliberately implement a case where the agent is **the wrong
answer** — a deterministic query does better, faster, cheaper — measure it,
document it.

**Notebooks**: (1) an agent without a framework, the mechanics laid bare — then the same agent
ported to LangGraph, smolagents, OpenAI Agents SDK and CrewAI, compared by the numbers on the
same harness: what each framework brings, hides and costs; (2) text-to-SQL, from the schema to
the safe query; (3) tools, APIs and side effects; (4) structured data and images — extracting
without hallucinating; (5) multi-source routing and contradictory sources; (6) evaluating an
agent: trajectories, execution, extraction; (7) agent memory: what to retain, where, at what
cost.
