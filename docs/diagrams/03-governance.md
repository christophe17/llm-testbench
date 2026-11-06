# Governance, deny by default

Before any call, the client asks whether this class of data may go to this backend. The
answer is computed from dated facts about the backend and from rules per data class, and it
is traced whatever the outcome.

```mermaid
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#eef2f8", "primaryTextColor": "#1b1f24", "primaryBorderColor": "#5b6b82", "lineColor": "#7d8590", "textColor": "#1b1f24", "edgeLabelBackground": "#eef2f8", "noteBkgColor": "#fff4ce", "noteTextColor": "#1b1f24", "noteBorderColor": "#c9a227", "classText": "#1b1f24", "clusterBkg": "#f6f8fa", "clusterBorder": "#8b949e", "fontSize": "14px"}}}%%
classDiagram
  direction LR
  class GovernancePolicy {
    +rules : dict~DataClass, Requirement~
    +load(path) GovernancePolicy$
    +evaluate(data_class, backend, governance) GovernanceDecision
  }
  class Requirement {
    +allowed_regions : tuple~InferenceRegion~ | None
    +require_zero_retention : bool
    +forbid_training : bool
    +forbid_variable_subprocessors : bool
  }
  class DataClass {
    <<enumeration>>
    PUBLIC
    INTERNAL
    CONFIDENTIAL
    PERSONAL
    REGULATED
  }
  class BackendConfig {
    +governance : BackendGovernance
  }
  class BackendGovernance {
    +entity : str
    +country : str
    +inference_region : InferenceRegion
    +default_retention_days : int | None
    +zero_retention : bool | None
    +trains_on_inputs : bool | None
    +subprocessors : fixed or variable
    +certifications : tuple~str~
    +verified_on : date
  }
  class InferenceRegion {
    <<enumeration>>
    EU
    US
    SELF
    VARIABLE
  }
  class GovernanceDecision {
    +data_class : DataClass
    +backend : str
    +allowed : bool
    +reasons : tuple~str~
    +enforce()
  }
  class GovernanceViolation {
    +data_class : DataClass
    +backend : str
    +reasons : tuple~str~
  }
  GovernancePolicy *-- Requirement : rules, one per DataClass, all five required
  Requirement --> InferenceRegion : allowed_regions
  BackendConfig *-- BackendGovernance : governance, dated facts about the vendor
  BackendGovernance --> InferenceRegion : inference_region
  GovernancePolicy ..> GovernanceDecision : evaluate() returns, allowed or not
  GovernanceDecision --> DataClass : data_class
  GovernanceDecision ..> GovernanceViolation : enforce() raises when not allowed
  note for BackendGovernance "A fact the vendor does not state is None, and None never satisfies a requirement"
```

## How to read it

- Two inputs, one output. The rules say what a data class needs; the backend governance says
  what a vendor proves; `evaluate` compares them and writes down every reason for refusal.
- Deny by default appears twice. The policy must have a rule for all five classes, enforced by
  a validator at load time. And an unknown fact about a backend (`None`) can never satisfy a
  requirement: `zero_retention: None` fails `require_zero_retention`.
- The decision is a value, not an exception. The client traces it first, then calls
  `enforce`, so a refusal is visible in Langfuse with its reasons.
- `verified_on` is a date on the facts, not on the rule: the facts age, and the register
  says when they were last checked.
- The same evaluation runs for embeddings and for the judge, not only for generation
  (ADR 006).

## In the code

[llm/governance.py](../../src/llm_testbench/llm/governance.py), the rules in
[config/governance_policy.toml](../../config/governance_policy.toml), the facts in
[config/llm_backends.toml](../../config/llm_backends.toml).

## In the notebooks

Notebook 01, parts 3.4 and 4.5.
