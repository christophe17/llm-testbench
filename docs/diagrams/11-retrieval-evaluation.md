# Measuring retrieval

One system under measurement (an *arm*) is a retriever asked every query of a dataset; what
comes out is a run: each metric with its interval, and the score of every query.

```mermaid
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#eef2f8", "primaryTextColor": "#1b1f24", "primaryBorderColor": "#5b6b82", "lineColor": "#7d8590", "textColor": "#1b1f24", "edgeLabelBackground": "#eef2f8", "noteBkgColor": "#fff4ce", "noteTextColor": "#1b1f24", "noteBorderColor": "#c9a227", "classText": "#1b1f24", "clusterBkg": "#f6f8fa", "clusterBorder": "#8b949e", "fontSize": "14px"}}}%%
classDiagram
  direction LR
  class Retriever {
    <<Protocol>>
    +describe() dict
    +retrieve(query, k) Retrieval
  }
  class BM25Retriever {
    +build_seconds : float
    +describe() dict
    +retrieve(query, k) Retrieval
  }
  class DenseRetriever {
    +describe() dict
    +retrieve(query, k) Retrieval
  }
  class Retrieval {
    +documents : tuple~RetrievedDocument~
    +cost_usd : float
    +timings_ms : dict, step to milliseconds
    +doc_ids : list~str~
  }
  class RetrievedDocument {
    +doc_id : str
    +score : float
    +rank : int
  }
  class PgVectorStore {
    +search_documents(spec, vector, k, exact, ef_search, candidates) list~DocumentHit~
  }
  class ArmConfig {
    +name : str
    +dataset : str
    +retriever : bm25 or dense
    +search : exact or hnsw
    +ef_search : int
    +references : tuple~Reference~
    +keys(sample) tuple of index key and source key
  }
  class RetrievalRun {
    +arm : str
    +dataset : dict
    +retriever : dict
    +index : IndexBuild
    +sample_mode : bool
    +metrics : dict, name to MetricSummary
    +latency_ms : dict
    +queries : tuple~QueryResult~
    +references : tuple~Reference~
    +publishable : bool
    +per_query(metric) dict
    +gap(reference) float
  }
  class MetricSummary {
    +mean : float
    +low : float
    +high : float
  }
  class QueryResult {
    +query_id : str
    +metrics : dict~str, float~
    +ranking : tuple~str~
    +latency_ms : float
  }
  class IndexBuild {
    +index_key : str
    +documents : int
    +chunks : int
    +cost_usd : float
    +seconds : float
  }
  class Reference {
    +label : str
    +value : float
    +source : str
    +metric : str
  }
  BM25Retriever ..|> Retriever : lexical, in memory
  DenseRetriever ..|> Retriever : pgvector, best chunk per document
  Retriever ..> Retrieval : retrieve() returns
  Retrieval *-- RetrievedDocument : documents, each document once
  DenseRetriever --> PgVectorStore : exact search or HNSW
  ArmConfig ..> Retriever : run_arm() builds the retriever and its index
  ArmConfig *-- Reference : references, the published scores
  RetrievalRun *-- MetricSummary : metrics, mean and 95% interval
  RetrievalRun *-- QueryResult : queries, one score per query
  RetrievalRun --> IndexBuild : index, what it took to have it
  RetrievalRun *-- Reference : references, copied from the arm
```

## How to read it

- **A retriever answers with documents**, never with chunks: the datasets judge documents.
  `DenseRetriever` folds chunks into documents in SQL (`search_documents`), and records
  how the index was read (`exact` or `hnsw`, `ef_search`) in `describe()`.
- **`ArmConfig` is a line of `config/eval_suites.toml`**; `run_arm` (a function of
  `eval/suite.py`, not drawn) builds the index the arm reads, then calls `run_retrieval`
  (`eval/runner.py`), which returns the `RetrievalRun`.
- **A run keeps the score of every query**: that is what lets two runs be compared query by
  query later (`eval/compare.py`), and what a table of averages cannot do.
- A run on fixtures has `sample_mode` set and `publishable` false: it is never archived.

Code: `src/llm_testbench/retrieval/`, `eval/runner.py`, `eval/runs.py`, `eval/suite.py`,
`eval/metrics/retrieval.py`, `eval/stats.py`. Notebook: phase 2, notebook 1, parts 3.1 to
3.5 and 4.1.
