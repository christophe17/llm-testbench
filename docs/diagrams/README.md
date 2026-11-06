# Diagrams

Hand-drawn class diagrams of `src/`, one per concept, written in Mermaid so that GitHub and
VS Code render them without tooling. Each one shows 7 to 12 classes and only the members that
matter for the concept; the full inventory of a subpackage is not a diagram, it is a listing
(`make uml-inventory` produces one, for the author, in `build/`).

They are a map for the guided readings of the notebooks: open the diagram, locate the class,
then follow the notebook's link to its source.

**They cannot drift silently.** `tests/test_diagrams.py` parses every diagram and checks,
against the AST of `src/`, that each drawn class exists, that each member listed in a box is
defined on that class or one of its bases, that each relation endpoint is a declared class, and
that each source path named in the layers diagram exists. Renaming a method without updating
its diagram breaks `make test`. What the test cannot check is the meaning of an arrow: that
part is reviewed like prose.

## Index

| Diagram | Concept | Notebook |
|---|---|---|
| [00 the layers](00-layers.md) | which subpackage depends on which, where the outside world comes in | all |
| [01 anatomy of a call](01-call-anatomy.md) | the request and response types of a model call | 01 |
| [02 the client and its providers](02-client-and-providers.md) | `LLMClient`, the `LLMProvider` protocol and its two implementations, the registry | 01 |
| [03 governance](03-governance.md) | deny by default: rules per data class against dated facts per backend | 01 |
| [04 the guards around a call](04-guards.md) | retry, circuit breaker, timeout, budget, cache, cost, in the client's order | 01 |
| [05 prompts and structured output](05-prompts-and-structured-output.md) | versioned prompts with fingerprints, schema-constrained answers with bounded repair | 01, 02 |
| [06 the error tree](06-error-tree.md) | the `LLMError` hierarchy, what is retryable, how it maps to HTTP | 01 |
| [07 from document to vector](07-document-to-vector.md) | parsing, chunking, embedding, the pgvector store, the index registry | 02 |
| [08 sources, evidence, citations](08-sources-evidence-citations.md) | the `Source` protocol, `Evidence` with full provenance, `Citation` | 02 |
| [09 the chat path](09-chat-path.md) | retrieval, prompt, generation, citation parsing, JSON and SSE | 02 |
| [10 datasets with ground truth](10-datasets.md) | retrieval datasets with qrels, the QASPER papers | 00, 02 |
| [11 measuring retrieval](11-retrieval-evaluation.md) | the `Retriever` protocol, an arm, a run with its intervals and per-query scores | phase 2: 01 |
| [12 measuring answers](12-generation-and-judge.md) | three contexts for one generation runner, what an answer records, the judge | phase 2: 01, 02, 03 |
| [13 corpus and golden set](13-corpus-and-golden-set.md) | the manifest and its freshness, two texts per document, a question from draft to frozen | phase 2: 03, 04 |

## Notation

UML class diagram notation, restricted to what the code actually has.

- A box is a class. Inside: attributes as `name : type`, then methods as
  `name(arguments) return_type`. A `$` at the end marks a class method, a `*` an abstract
  method. Only the members relevant to the diagram are listed; the test guarantees that the
  listed ones exist, not that the list is complete.
- `<<Protocol>>` is a `typing.Protocol`: a class satisfies it by having the right methods,
  without inheriting. `<<enumeration>>` is a `StrEnum`. `<<external>>` is a third-party class,
  drawn for context only.
- `A --|> B` or `B <|-- A`: A inherits from B. Rare in this code base on purpose.
- `A ..|> B`: A satisfies protocol B. The dashed line is the UML "realization".
- `A *-- B : field`: A owns a collection of B, in attribute `field`.
- `A --> B : label`: A holds a reference to B, or calls it; the label says which attribute or
  method.
- `A ..> B : label`: A produces or consumes B without holding it, typically a return value or
  a parameter.

## Adding or changing a diagram

1. One concept per file, numbered in reading order, 12 classes at most. If it needs more, it
   is two concepts.
2. Draw only the members the reader needs for this concept. The code is one click away.
3. Below the picture: how to read it (the non-obvious arrows), where in the code, where in the
   notebooks.
4. Run `make test`: the diagram test fails on any class or member that does not exist.
5. Add the file to the index above; the test checks that too.
