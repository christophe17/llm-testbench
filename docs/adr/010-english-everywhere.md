# ADR 010 — Everything in English

- **Date**: 2026-10-20
- **Status**: accepted

## Context

Until 2026-10-20 the repository was bilingual by rule (ADR 003, `CLAUDE.md` §2.B.5): prose,
docstrings and teaching notebooks in French because the first reader is the learner,
identifiers and code in English. The program's language rule (PD-5, "everything in
English") exempted this repository as "a French brief written for one reader". The
repository is public and is the proof shown to freelance clients and employers, Switzerland
included, who read English. Christophe asks that there be no French in the project.

## Options considered

1. **Keep the bilingual rule** — the learner reads the teaching material in their first
   language. Cons: a public repository that most of its readers cannot read, a mixed-language
   codebase (French messages and docstrings around English identifiers), an exception to keep
   alive in the program.
2. **Everything in English** — one language for every reader, consistent with the rest of
   the program. Cons: the learner reads the notebooks and guides in a second language; a
   one-off translation of about a hundred thousand words, where wording can drift from the
   original.

## Decision

Option 2. No French anywhere in the repository: prose, roadmap, ADRs, guides, notebooks,
docstrings, comments, error and log messages, test data, configuration notes, prompts and
file names. Translation is faithful (same content, same structure), not a rewrite.

- Prompts get a new version (`chat_answer`, `structured_output_*` → v2); the refusal
  sentinel becomes "I cannot answer this question from the provided documents."
- Files with French names are renamed; in-repository references follow.
- Git history is kept as is: commit messages before 2026-10-20 remain in French. Rewriting
  a pushed public `main` is not worth breaking every clone and link.
- The conversation with Claude may stay in French; it is not part of the repository.

## Consequences

- ADR 003's language clause is superseded; `CLAUDE.md` §2.B.5 says what holds today.
- Lifts the exception PD-5 granted this repository: to be carried over into the program
  (`~/Roadmaps/program`, PD-5 and `docs/02-shared-rules.md`).
- Generation runs made with v1 prompts are not comparable with v2 runs; a number that
  depends on a prompt says which version produced it.
- The French originals remain readable in history (`git show ceab409:<old path>`) if a
  translation is ever in doubt.
