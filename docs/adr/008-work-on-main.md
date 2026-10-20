# ADR 008 — All work on `main`, no phase branch or PR

- **Date**: 2026-10-16
- **Status**: accepted

## Context

The brief planned "one phase = one branch = one PR with a serious description". In
practice, branches lived for weeks (PR #3 opened on 2026-09-03, merged on
2026-10-16), documentation amendments piled up in them, and a side docs branch
(PR #2) had to be merged before the other. A single author, no third-party reviewer: the PR
served as a milestone, not as a review. Christophe asks for everything to be on `main`.

## Options considered

1. **Keep branch + PR per phase** — visible milestone on GitHub, PR description as the
   phase narrative, and above all phase 2.7 can **block a merge** on regression. Cons:
   long-lived branches, divergence, merges delayed by weeks, ceremony without a reviewer.
2. **Everything on `main`** — a single project state, no divergence, CI runs on every push.
   Cons: nothing *blocks* a regression from getting in anymore; the phase narrative must find
   another home.

## Decision

Option 2. Small, described commits, pushed when local CI passes; GitHub CI already runs
on `push: [main]`. A phase's narrative goes into its closing entry in `JOURNAL.md`.

For phase 2.7, the blocking moves upstream: a `pre-push` hook runs the evaluation gate in
sample mode and refuses the push beyond the threshold; the same gate in GitHub CI turns
red on `main` if the hook was bypassed (`--no-verify`).

## Consequences

- No more divergence or delayed merge; `STATE.md` always describes the state of `main`.
- **Accepted loss**: a local hook can be bypassed, and a red CI on `main` records instead
  of preventing. In an interview, the evaluation gate must be presented as what it is, and
  compared honestly to branch protection in a team (merge blocked by a required check) —
  that is the configuration to recommend as soon as there is more than one contributor.
- If some day an external review (client, contributor) enters the repository, go back to PRs with
  `main` protection; this ADR will then be superseded.
