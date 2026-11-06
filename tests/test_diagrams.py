"""The hand-drawn diagrams in ``docs/diagrams/`` must match the code.

A drawn diagram drifts silently: a class is renamed, a method removed, and the picture keeps
lying. This test parses every Mermaid block of ``docs/diagrams/*.md`` and checks it against
the AST of ``src/llm_testbench``, offline and without importing anything:

- ``classDiagram``: every drawn class exists in ``src/``; every member listed in its box is
  defined on that class or on one of its bases from the package; every endpoint of a relation
  and every ``note for`` target is a class declared in the same diagram (Mermaid silently
  creates a box for an undeclared name, which would hide a typo). A class annotated
  ``<<external>>`` is third-party and only has to be declared.
- ``flowchart``: every label that looks like a source path (``llm/client.py``) exists under
  ``src/llm_testbench``.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "llm_testbench"
DIAGRAMS_DIR = ROOT / "docs" / "diagrams"
DIAGRAMS = sorted(p for p in DIAGRAMS_DIR.glob("*.md") if p.name != "README.md")

MERMAID_BLOCK = re.compile(r"```mermaid\n(.*?)```", re.S)
IDENT = r"[A-Za-z_][A-Za-z0-9_]*"
CLASS_HEADER = re.compile(rf"^\s*class\s+({IDENT})(?:~[^~]*~)?\s*(\{{)?\s*$")
INLINE_MEMBER = re.compile(rf"^\s*({IDENT})\s*:\s*(.+)$")
MEMBER = re.compile(rf"^\s*[+\-#~]?\s*({IDENT})")
ANNOTATION = re.compile(r"^\s*<<(\w+)>>\s*$")
RELATION = re.compile(
    rf"^\s*({IDENT})\s+(?:<\||<|\*|o)?(?:--|\.\.)(?:\|>|>|\*|o)?\s+({IDENT})(?:\s*:.*)?$"
)
NOTE_FOR = re.compile(rf"^\s*note\s+for\s+({IDENT})\s+")
SOURCE_PATH = re.compile(r"((?:[a-z_]+/)*[a-z_]+\.py)")


@dataclass
class DrawnClass:
    name: str
    annotations: set[str] = field(default_factory=set)
    members: set[str] = field(default_factory=set)


@dataclass
class ClassDiagram:
    classes: dict[str, DrawnClass] = field(default_factory=dict)
    referenced: set[str] = field(default_factory=set)


def parse_class_diagram(text: str) -> ClassDiagram:
    diagram = ClassDiagram()
    current: DrawnClass | None = None
    for raw in text.splitlines():
        line = raw.split("%%")[0].rstrip()
        if not line.strip():
            continue
        if current is not None:
            if line.strip() == "}":
                current = None
            elif (m := ANNOTATION.match(line)) is not None:
                current.annotations.add(m.group(1).lower())
            elif (m := MEMBER.match(line)) is not None:
                current.members.add(m.group(1))
            continue
        if (m := CLASS_HEADER.match(line)) is not None:
            drawn = diagram.classes.setdefault(m.group(1), DrawnClass(m.group(1)))
            if m.group(2):
                current = drawn
        elif (m := RELATION.match(line)) is not None:
            diagram.referenced.update((m.group(1), m.group(2)))
        elif (m := NOTE_FOR.match(line)) is not None:
            diagram.referenced.add(m.group(1))
        elif (m := INLINE_MEMBER.match(line)) is not None:
            drawn = diagram.classes.setdefault(m.group(1), DrawnClass(m.group(1)))
            member = m.group(2).strip()
            if (a := ANNOTATION.match(member)) is not None:
                drawn.annotations.add(a.group(1).lower())
            elif (mm := MEMBER.match(member)) is not None:
                drawn.members.add(mm.group(1))
    return diagram


@dataclass
class CodeClass:
    module: str
    bases: list[str]
    members: set[str]


def _base_names(node: ast.ClassDef) -> list[str]:
    names: list[str] = []
    for base in node.bases:
        if isinstance(base, ast.Subscript):
            base = base.value
        if isinstance(base, ast.Name):
            names.append(base.id)
        elif isinstance(base, ast.Attribute):
            names.append(base.attr)
    return names


def _members(node: ast.ClassDef) -> set[str]:
    members: set[str] = set()
    for item in node.body:
        if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
            members.add(item.name)
            for sub in ast.walk(item):
                targets: list[ast.expr] = []
                if isinstance(sub, ast.Assign):
                    targets = sub.targets
                elif isinstance(sub, ast.AnnAssign):
                    targets = [sub.target]
                for target in targets:
                    if (
                        isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "self"
                    ):
                        members.add(target.attr)
        elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            members.add(item.target.id)
        elif isinstance(item, ast.Assign):
            members.update(t.id for t in item.targets if isinstance(t, ast.Name))
    return members


def index_code() -> dict[str, list[CodeClass]]:
    index: dict[str, list[CodeClass]] = {}
    for path in sorted(SRC.rglob("*.py")):
        module = path.relative_to(SRC).with_suffix("").as_posix().replace("/", ".")
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                index.setdefault(node.name, []).append(
                    CodeClass(module, _base_names(node), _members(node))
                )
    return index


def members_of(name: str, index: dict[str, list[CodeClass]], seen: set[str]) -> set[str]:
    """Members of every class named ``name``, plus those inherited from bases of the package."""
    if name in seen:
        return set()
    seen.add(name)
    members: set[str] = set()
    for cls in index.get(name, []):
        members |= cls.members
        for base in cls.bases:
            members |= members_of(base, index, seen)
    return members


CODE = index_code()


def mermaid_blocks(path: Path) -> list[str]:
    return MERMAID_BLOCK.findall(path.read_text(encoding="utf-8"))


def check_class_diagram(text: str) -> list[str]:
    diagram = parse_class_diagram(text)
    problems: list[str] = []
    for name in sorted(diagram.referenced - diagram.classes.keys()):
        problems.append(f"'{name}' is used in a relation or note but not declared with 'class'")
    for drawn in diagram.classes.values():
        if "external" in drawn.annotations:
            continue
        if drawn.name not in CODE:
            problems.append(f"class '{drawn.name}' does not exist in src/llm_testbench")
            continue
        missing = sorted(drawn.members - members_of(drawn.name, CODE, set()))
        if missing:
            problems.append(f"'{drawn.name}' has no member(s) {missing}")
    return problems


def check_flowchart(text: str) -> list[str]:
    return [
        f"source path '{rel}' does not exist under src/llm_testbench"
        for rel in sorted(set(SOURCE_PATH.findall(text)))
        if not (SRC / rel).is_file()
    ]


@pytest.mark.parametrize("path", DIAGRAMS, ids=lambda p: p.name)
def test_diagram_matches_code(path: Path) -> None:
    blocks = mermaid_blocks(path)
    assert blocks, f"{path.name} has no ```mermaid block"
    problems: list[str] = []
    for block in blocks:
        lines = [
            ln
            for ln in block.strip().splitlines()
            if ln.strip() and not ln.lstrip().startswith("%%")
        ]
        kind = lines[0].split()[0] if lines else ""
        if kind == "classDiagram":
            problems += check_class_diagram(block)
        elif kind.startswith("flowchart") or kind == "graph":
            problems += check_flowchart(block)
        else:
            problems.append(f"unsupported diagram type '{kind}'")
    assert not problems, f"{path.name}:\n  " + "\n  ".join(problems)


@pytest.mark.skipif(not DIAGRAMS, reason="no diagram drawn yet")
def test_readme_lists_every_diagram() -> None:
    readme = (DIAGRAMS_DIR / "README.md").read_text(encoding="utf-8")
    missing = [p.name for p in DIAGRAMS if f"({p.name})" not in readme]
    assert not missing, f"docs/diagrams/README.md does not link {missing}"


def test_parser_on_a_toy_diagram() -> None:
    """The parser itself, on the syntax the diagrams use."""
    toy = """classDiagram
      direction LR
      class LLMClient {
        <<facade>>
        +complete(request) Completion
        -_breakers : dict
      }
      class AsyncAnthropic {
        <<external>>
      }
      class Usage
      class StructuredResult~T~ {
        +value : T
      }
      Usage : +input_tokens
      LLMClient --> Usage : returns
      AnthropicProvider ..|> LLMProvider
      note for LLMClient "the facade"
    """
    diagram = parse_class_diagram(toy)
    assert diagram.classes["LLMClient"].members == {"complete", "_breakers"}
    assert diagram.classes["LLMClient"].annotations == {"facade"}
    assert diagram.classes["AsyncAnthropic"].annotations == {"external"}
    assert diagram.classes["Usage"].members == {"input_tokens"}
    assert diagram.classes["StructuredResult"].members == {"value"}
    assert diagram.referenced == {"LLMClient", "Usage", "AnthropicProvider", "LLMProvider"}
    problems = check_class_diagram(toy)
    undeclared = "is used in a relation or note but not declared with 'class'"
    assert f"'AnthropicProvider' {undeclared}" in problems
    assert f"'LLMProvider' {undeclared}" in problems
    assert not [p for p in problems if "LLMClient" in p or "Usage" in p], problems
