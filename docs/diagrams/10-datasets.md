# Datasets with ground truth

The testbench measures against public datasets that come with their answers. Two shapes: a
retrieval dataset (corpus, queries, relevance judgements) and the QASPER papers that feed the
ingestion pipeline.

```mermaid
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#eef2f8", "primaryTextColor": "#1b1f24", "primaryBorderColor": "#5b6b82", "lineColor": "#7d8590", "textColor": "#1b1f24", "edgeLabelBackground": "#eef2f8", "noteBkgColor": "#fff4ce", "noteTextColor": "#1b1f24", "noteBorderColor": "#c9a227", "classText": "#1b1f24", "clusterBkg": "#f6f8fa", "clusterBorder": "#8b949e", "fontSize": "14px"}}}%%
classDiagram
  direction LR
  class RetrievalLoader {
    <<abstract>>
    +info : DatasetInfo
    +load(split, max_queries) RetrievalDataset*
  }
  class BeirLoader {
    +info : DatasetInfo
    +load(split, max_queries) RetrievalDataset
  }
  class RetrievalDataset {
    +info : DatasetInfo
    +split : str
    +documents : tuple~Document~
    +queries : tuple~Query~
    +qrels : dict, query_id to doc_id to grade
    +sampled : bool
    +document_by_id(doc_id) Document
    +relevant_doc_ids(query_id, min_relevance) set~str~
    +describe() dict
  }
  class Document {
    +doc_id : str
    +title : str
    +text : str
    +metadata : dict~str, str~
  }
  class Query {
    +query_id : str
    +text : str
    +metadata : dict~str, str~
  }
  class DatasetInfo {
    +key : str
    +name : str
    +homepage : str
    +license : str
    +source : str
  }
  class QasperLoader {
    +info : DatasetInfo
    +load(split, max_papers) QasperDataset
  }
  class QasperDataset {
    +info : DatasetInfo
    +split : str
    +papers : tuple~QasperPaper~
    +sampled : bool
    +documents() list~ParsedDocument~
    +describe() dict
  }
  class QasperPaper {
    +paper_id : str
    +title : str
    +abstract : str
    +sections : tuple of (title, text)
    +questions : tuple~QasperQuestion~
    +to_document() ParsedDocument
  }
  class QasperQuestion {
    +question_id : str
    +question : str
  }
  class ParsedDocument
  RetrievalLoader <|-- BeirLoader : BEIR datasets, SciFact first, from Hugging Face or fixtures
  RetrievalLoader ..> RetrievalDataset : load() returns
  RetrievalDataset *-- Document : documents, the corpus
  RetrievalDataset *-- Query : queries
  RetrievalDataset --> DatasetInfo : info, with licence and source
  QasperLoader ..> QasperDataset : load() returns
  QasperDataset *-- QasperPaper : papers
  QasperPaper *-- QasperQuestion : questions
  QasperDataset --> DatasetInfo : info
  QasperPaper ..> ParsedDocument : to_document(), into the ingest pipeline
  note for RetrievalDataset "qrels are the ground truth: for each query, the relevant documents and their grade. Every retrieval metric is computed against them"
```

## How to read it

- A retrieval dataset is three tables and a contract: every qrel points to an existing query
  and an existing document, checked by a validator when the dataset is built.
- `sampled` is true when `LLM_TESTBENCH_SAMPLE=1` cut the dataset down. A number computed on
  a sampled dataset is a smoke test, never a result to publish (ADR 003).
- `RetrievalLoader` is an abstract base class, the one real inheritance tree of the project
  besides the errors: every BEIR dataset loads the same way, so the base class is the right
  tool here. `QasperLoader` is not a retrieval loader: QASPER gives papers and questions,
  not relevance judgements, so it has its own dataset type.
- `DatasetInfo` carries the licence and the source. Both are printed by the notebooks before
  anything is downloaded.
- `to_document` is the bridge to [07 from document to vector](07-document-to-vector.md):
  a paper becomes a `ParsedDocument` with one section per paper section.

## In the code

[eval/types.py](../../src/llm_testbench/eval/types.py),
[eval/loaders/base.py](../../src/llm_testbench/eval/loaders/base.py),
[eval/loaders/beir.py](../../src/llm_testbench/eval/loaders/beir.py),
[eval/loaders/qasper.py](../../src/llm_testbench/eval/loaders/qasper.py).

## In the notebooks

Notebook 00 (corpus, queries, qrels, nDCG), notebook 02 part 5 for the embeddings benchmark.
