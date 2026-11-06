# Measuring answers: three contexts, one runner, one judge

The same questions are answered from the gold passages, from the chunks the system
retrieves, or from nothing. What code can score is scored by code; the judge reads the
rest.

```mermaid
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#eef2f8", "primaryTextColor": "#1b1f24", "primaryBorderColor": "#5b6b82", "lineColor": "#7d8590", "textColor": "#1b1f24", "edgeLabelBackground": "#eef2f8", "noteBkgColor": "#fff4ce", "noteTextColor": "#1b1f24", "noteBorderColor": "#c9a227", "classText": "#1b1f24", "clusterBkg": "#f6f8fa", "clusterBorder": "#8b949e", "fontSize": "14px"}}}%%
classDiagram
  direction LR
  class QADataset {
    +info : DatasetInfo
    +examples : tuple~QAExample~
    +subsample_seed : int
    +corpus : tuple~ParsedDocument~
    +describe() dict
  }
  class QAExample {
    +example_id : str
    +question : str
    +passages : tuple~Passage~
    +answers : tuple~str~
    +answerable : bool
    +scope : dict~str, str~
    +kind : str
    +evidence(source_key) list~Evidence~
  }
  class Passage {
    +passage_id : str
    +text : str
    +document_id : str
  }
  class ContextProvider {
    <<Protocol>>
    +retrieved : bool
    +describe() dict
    +applies_to(example) bool
    +context(example) Context
  }
  class GoldContext {
    +applies_to(example) bool
    +context(example) Context
  }
  class RetrievedContext {
    +applies_to(example) bool
    +context(example) Context
  }
  class NoContext {
    +applies_to(example) bool
    +context(example) Context
  }
  class Context {
    +evidence : tuple~Evidence~
    +cost_usd : float
    +latency_ms : float
  }
  class DocumentSource {
    +embed_query(text, data_class) EmbeddingResult
    +search_vector(vector, k, filters) list~Evidence~
  }
  class GenerationRun {
    +arm : str
    +context : str
    +retrieval : dict
    +max_output_tokens : int
    +metrics : dict, name to RateSummary
    +stability : Stability
    +answers : tuple~AnswerResult~
    +scored() list~AnswerResult~
  }
  class AnswerResult {
    +example_id : str
    +answer : str
    +refused : bool
    +cited : tuple~int~
    +metrics : dict~str, float~
    +retrieved : tuple~str~
    +truncated : bool
  }
  class Judge {
    +model : ModelRef
    +grade(rubric, question, answer, evidence) Verdict
  }
  class Verdict {
    +rubric : Rubric
    +label : bool
    +justification : str
    +prompt_version : str
    +cost_usd : float
  }
  QADataset *-- QAExample : examples
  QAExample *-- Passage : passages, the gold context
  GoldContext ..|> ContextProvider : the passages of the dataset
  RetrievedContext ..|> ContextProvider : what the search returns
  NoContext ..|> ContextProvider : closed book
  ContextProvider ..> Context : context() returns
  RetrievedContext --> DocumentSource : the API's own search, inside the example's scope
  GenerationRun *-- AnswerResult : answers, one per question and repeat
  QAExample ..> AnswerResult : run_generation() asks and scores
  Judge ..> Verdict : grade() returns
  AnswerResult ..> Judge : graded on groundedness and relevance
```

## How to read it

- **One runner, three providers.** `run_generation` (`eval/generation.py`, a function,
  not drawn) asks each example through the API's prompt and parser, with the evidence a
  `ContextProvider` hands over. `GoldContext` leaves out an example without a gold
  passage (`applies_to`); the two others ask every question.
- **An end-to-end answer records what was retrieved** (`retrieved`) and, in its
  `metrics`, whether the gold passages were among it (`context_recall`,
  `context_complete`, computed by `score_context`). `attribution` then splits the
  failures between the search and the generator.
- **`truncated`** is set when the generation stopped on its output cap: the answer is cut
  or empty, and stays in the rates.
- **The judge is outside the runner**: it grades answers already produced, one rubric at a
  time. Its agreement with human labels (`eval/calibration.py`, `eval/agreement.py`)
  decides whether its verdicts are used at all.

Code: `src/llm_testbench/eval/qa.py`, `eval/context.py`, `eval/generation.py`,
`eval/metrics/generation.py`, `eval/judge.py`, `eval/calibration.py`, `eval/bias.py`.
Notebooks: phase 2, notebook 1 (parts 4.2 and 4.3), notebook 2, notebook 3.
