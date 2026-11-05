"""The golden set as the harness reads it: a question-answering dataset over the corpus.

A golden question becomes a :class:`~llm_testbench.eval.qa.QAExample`: its verified quotes
are the gold passages, its reference answer the answer to find, its kind the label the
results are broken down by. The corpus to search is the in-house corpus, in one of two
texts:

- ``naive``: what the phase 2 extractor gets out of the PDFs. The system as built;
- ``reference``: the text a perfect parser would have produced. What the system would
  score if parsing were solved, so the difference between the two is what parsing costs.

The quotes were copied from the reference text. On the naive text a quote may be nowhere
to be found (a table row, a sentence a footnote was dropped into): that is not a flaw of
the golden set, it is the measurement.
"""

from typing import Literal

from llm_testbench.eval.corpus.build import Corpus
from llm_testbench.eval.golden.types import GoldenQuestion
from llm_testbench.eval.qa import Passage, QADataset, QAExample
from llm_testbench.eval.types import DatasetInfo
from llm_testbench.ingest.parsing import ParsedDocument

CorpusText = Literal["naive", "reference"]

GOLDEN_INFO = DatasetInfo(
    key="golden/arxiv-fresh",
    name="In-house golden set (fresh arXiv papers)",
    homepage="https://arxiv.org/",
    license="quoted papers: CC BY 4.0, listed in data/corpus/arxiv-fresh/manifest.json",
    source="data/golden/inhouse/questions.jsonl",
)


def golden_example(question: GoldenQuestion, titles: dict[str, str]) -> QAExample:
    quotes = [quote for quote in question.quotes if quote.found]
    return QAExample(
        example_id=question.question_id,
        question=question.question,
        passages=tuple(
            Passage(
                passage_id=f"{question.question_id}#quote-{number}",
                text=quote.text,
                title=titles.get(quote.doc_id, ""),
                document_id=quote.doc_id,
            )
            for number, quote in enumerate(quotes, start=1)
        )
        if question.answerable
        else (),
        answers=(question.answer,) if question.answerable else (),
        answerable=question.answerable,
        kind=question.category.value,
    )


def corpus_documents(corpus: Corpus, text: CorpusText) -> tuple[ParsedDocument, ...]:
    entries = corpus.manifest.documents
    if text == "reference":
        return tuple(corpus.reference(entry) for entry in entries)
    return tuple(corpus.extracted(entry) for entry in entries)


def golden_dataset(
    questions: list[GoldenQuestion], corpus: Corpus, *, text: CorpusText = "naive"
) -> QADataset:
    titles = {entry.doc_id: entry.title for entry in corpus.manifest.documents}
    return QADataset(
        info=GOLDEN_INFO,
        split=text,
        examples=tuple(golden_example(question, titles) for question in questions),
        corpus=corpus_documents(corpus, text),
    )
