"""Generation metrics that need no judge: what the answer says about itself.

Given the gold context, an answer can be scored on four things by plain code:

- **refusal**: on an unanswerable question the only right answer is the refusal sentence
  (*correct refusal*); on an answerable one, refusing is a failure (*over-refusal*). The two
  rates pull against each other: a prompt that refuses everything scores 100% on the first
  and 100% on the second, which is why they are never reported one without the other;
- **citations**: an answer must cite, and only numbers that exist. A cited number with no
  evidence behind it is an invented source;
- **the reference answer**: is it in the generated text (``contains_answer``), and how much
  of the text is it (``answer_f1``, the SQuAD token F1). A generative model wraps "1911" in
  a sentence: F1 punishes the wrapping, containment does not. Both are shown; neither says
  whether the rest of the sentence is true, which is the judge's job (groundedness).

Each metric is defined on a subset of the examples (a refusal rate has no meaning on a
question that was answered, a citation rate none on a refusal): an example carries only the
metrics that apply to it, and a rate is averaged over those.
"""

import re
import string
from collections import Counter
from collections.abc import Sequence

from llm_testbench.generation.answer import ParsedAnswer

_ARTICLES = re.compile(r"\b(a|an|the)\b")
_CITATION = re.compile(r"\[\d+(?:\s*,\s*\d+)*\]")
_PUNCTUATION = str.maketrans("", "", string.punctuation)


def normalize_answer(text: str) -> str:
    """SQuAD's normalization (lowercase, no punctuation, no articles, single spaces), after
    removing our citation markers, which are not part of what is said."""
    text = _CITATION.sub(" ", text).lower().translate(_PUNCTUATION)
    return " ".join(_ARTICLES.sub(" ", text).split())


def token_f1(prediction: str, reference: str) -> float:
    predicted, expected = normalize_answer(prediction).split(), normalize_answer(reference).split()
    if not predicted or not expected:
        return float(predicted == expected)
    common = sum((Counter(predicted) & Counter(expected)).values())
    if common == 0:
        return 0.0
    precision, recall = common / len(predicted), common / len(expected)
    return 2 * precision * recall / (precision + recall)


def answer_f1(prediction: str, references: Sequence[str]) -> float:
    """Best token F1 over the reference wordings, as SQuAD scores it."""
    return max((token_f1(prediction, reference) for reference in references), default=0.0)


def contains_answer(prediction: str, references: Sequence[str]) -> bool:
    """One reference wording appears, whole and in order, in the generated answer."""
    normalized = f" {normalize_answer(prediction)} "
    return any(
        f" {normalize_answer(reference)} " in normalized
        for reference in references
        if normalize_answer(reference)
    )


def score_answer(
    parsed: ParsedAnswer, *, answerable: bool, references: Sequence[str]
) -> dict[str, float]:
    """The metrics that apply to this answer, each 0 or 1 except ``answer_f1``."""
    scores: dict[str, float] = {}
    if answerable:
        scores["over_refusal"] = float(parsed.refused)
        scores["contains_answer"] = float(
            not parsed.refused and contains_answer(parsed.text, references)
        )
        scores["answer_f1"] = 0.0 if parsed.refused else answer_f1(parsed.text, references)
    else:
        scores["correct_refusal"] = float(parsed.refused)
    if not parsed.refused:
        scores["cited"] = float(bool(parsed.citations))
        scores["invented_citation"] = float(bool(parsed.unknown_indexes))
    return scores
