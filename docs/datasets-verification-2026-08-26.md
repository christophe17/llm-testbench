# Testbench dataset verification — 2026-08-26

Web verification (name, version, license, size, retrieval method) of each entry in the table
of section 4 of `CLAUDE.md` as of this date (table now in `docs/roadmap/README.md`). Tooling context: Hugging Face loading scripts are
deprecated (`datasets` ≥ 3.x no longer runs them) — the criterion "loads cleanly today"
means: HF repository in native Parquet, or versioned direct download.

## Retrieval and embeddings

### BEIR — SciFact, NFCorpus, FiQA-2018
- **Hosting**: HF org `BeIR` (converted to native Parquet ~2026): `BeIR/scifact` + `BeIR/scifact-qrels` (same for nfcorpus, fiqa). Also: UKP Darmstadt zips, `beir` package v2.2.0, `ir_datasets`.
- **License**: CC BY-SA 4.0 on the HF cards — but the BEIR README states that they do not guarantee upstream licenses. To note in the ADR.
- **Sizes**: SciFact 5,183 docs / 1,109 queries (300 test) / 1,258 near-binary qrels / 4.55 MB. NFCorpus 3,633 docs / 323 test queries / ~134k graded qrels / 3.25 MB. FiQA 57,638 docs / 648 test queries / 28 MB.
- **Loading**: `load_dataset("BeIR/scifact", "corpus")` — script-free. The qrels are in a separate repository: the loader joins 3 repositories.
- **Issues**: no blocker.

### MTEB
- `mteb` package v2.20.2 (2026-08-25), very active. **Breaking v2 API** vs v1 (`mteb.get_benchmark(...)` / `mteb.evaluate(...)`) — older tutorials are outdated.
- **French: yes** — built-in benchmark `MTEB(fra, v1)`, 22 tasks (Ciancone et al. 2024, arXiv:2405.20468).
- Code license Apache-2.0; the task datasets are downloaded from HF on demand.

## QA / multi-hop / unanswerable / raw documents

### HotpotQA — OK
- HF `hotpotqa/hotpot_qa`, configs `distractor` and `fullwiki`, native Parquet. CC BY-SA 4.0. 90,447 train / 7,405 val, ~1.27 GB. Test answers hidden → evaluate on validation.

### SQuAD 2.0 — OK, the cleanest
- HF `rajpurkar/squad_v2`, native Parquet. CC BY-SA 4.0. 130,319 train / 11,873 val (~50k unanswerable), 46.5 MB. No boolean flag: unanswerable = empty `answers.text` list.

### QASPER — OK with one caveat
- HF `allenai/qasper` (allenai.org redirects to HF). CC BY 4.0. 1,585 full papers / ~5,049 questions / ~26 MB, with evidence spans.
- **Trap**: the main repository only contains the `qasper.py` script → `load_dataset` fails with `datasets` ≥ 3. Load via `revision="refs/convert/parquet"` (branch verified present) or vendor the JSONL.

### MuSiQue — fragile
- Canonical: GitHub `StonyBrookNLP/musique`, data via **Google Drive** (gdown quotas = known failure). CC BY 4.0. ~25k questions (ans variant). Community HF mirror `dgslibisey/MuSiQue` (Parquet, unofficial provenance, no license tag, no test split).

### 2WikiMultihopQA — fragile
- Canonical: GitHub `Alab-NII/2wikimultihop`, data in a **Dropbox zip**. Apache-2.0. 192,606 examples. Unmaintained since ~2021. Community HF mirror `framolfese/2WikiMultihopQA` (Parquet, unverified provenance); `xanhho/...` script-based → broken.

### Natural Questions — impractical in full
- HF `google-research-datasets/natural_questions`. CC BY-SA 3.0. **45 GB downloaded / ~100 GB generated** for the full config; each example embeds a tokenized Wikipedia page. The "no answer" signal is indirect (fewer than 2 annotators out of 5 find an answer — logic to implement yourself). Only the `dev` config is practical. **Proposed decision: SQuAD 2.0 covers the "no answer" need, NQ removed from the testbench.**

## Text-to-SQL and agents

### Spider 1.0 — OK with accepted contamination
- Questions+SQL: HF `xlangai/spider` (Parquet, 7,000 train / 1,030 dev). **The SQLite databases are only on Google Drive** (link from the Yale site) → plan a cached copy. CC BY-SA 4.0. ~200 DBs. Eval repo frozen since 2020; gated test; massive and documented training contamination (precisely one of the testbench's subjects). Spider 2.0 = a different benchmark (Snowflake/BigQuery, paid accounts) — out of scope.

### BIRD — go through Mini-Dev
- Full: 12,751 questions / 95 DBs / **33.4 GB**. Dev 1,534 examples, direct zips (Alibaba OSS, slow from the EU).
- **Mini-Dev** (`github.com/bird-bench/mini_dev`, HF `birdsql/bird_mini_dev`): 500 SELECT instances on 11 DBs (+270 CRUD) — **ships the databases in SQLite, MySQL AND PostgreSQL**, which reduces the planned sqlglot conversion work (still useful for Spider). CC BY-SA 4.0. Maintained.

### τ-bench — DEPRECATED, replace
- `sierra-research/tau-bench` carries an explicit deprecation warning. Successor: **`sierra-research/tau2-bench`** (τ²→τ³: banking, voice, 75+ task fixes). MIT, Python ≥3.12 <3.14 (compatible). It is a complete harness (LLM agent + LLM-simulated user → double cost), not a dataset. The published numbers of the 2024 τ-bench paper are no longer comparable after the fixes.

### BFCL — V4, Python conflict
- Monorepo `ShishirPatil/gorilla`, `pip install bfcl-eval` (not `bfcl`). Apache-2.0. **Python 3.10 pin** → separate uv environment mandatory (the only hard conflict with our 3.12). The V4 web_search category requires a paid SerpAPI key. Scores comparable only at an identical BFCL version.

### AgentDojo — OK
- `pip install agentdojo` v0.1.35 (2025-10-27), MIT, Python 3.10–3.12. 4 suites (workspace, Slack, banking, travel), 97 tasks / 27 injections → 629 cases. Pre-1.0 API, unstable by nature.

**Cross-cutting note**: τ²/τ³, BFCL and AgentDojo are harnesses to install and drive, not loadable datasets — they do not fit the phase 0 loader interface and will be integrated as external runners in phase 4.

## Tables and numerical reasoning

- **TAT-QA** — the best of the lot: GitHub `NExTplusplus/TAT-QA` + HF `next-tat/TAT-QA`, raw JSON without a script, CC BY 4.0, 16,552 questions / 17 MB, test ground truth published since 2024.
- **WikiTableQuestions** — v1.0.2 (2016). HF repository `stanfordnlp/wikitablequestions` script-only → go through the GitHub `ppasupat/WikiTableQuestions` (everything in the repository). License: **CC BY-SA 4.0** according to the original repository (the HF card says CC BY 4.0 — mirror error).
- **HybridQA** — 69,611 questions, data scattered across 3 sources (repo + WikiTables-WithLinks + S3), script-based HF repository. CC BY 4.0 / MIT. Usable but costly to integrate — optional.
- **FinQA** — GitHub `czyssrs/FinQA`, MIT, ~8.3k questions (paper figure), unmaintained since 2022. **Trap**: pre-2022 bug in `table_row_to_text` that inflated published accuracies — compare only to post-fix numbers.

## Images

- **DocVQA (Task 1)** — official RRC site: registration mandatory **and broken TLS certificate observed today**. Go through the non-gated HF mirrors: `pixparse/docvqa-single-page-questions` (complete, 12.4 GB, test answers absent) or `lmms-lab/DocVQA` (val+test, light). Non-standard original license; the mirrors' licenses (MIT/Apache) are self-assigned — to flag in the README. Evaluate on validation.
- **ChartQA** — HF `ahmed-masry/ChartQA`, Parquet, 32,719 questions / 1.45 GB. **GPL-3.0 license** (copyleft on data, legally shaky — acceptable for a testbench, to flag). Separate the human vs augmented splits in the results, as the literature does.
- **CORD v2** — HF `naver-clova-ix/cord-v2`, Parquet, CC BY 4.0, 2.31 GB. **Only 1,000 receipts published** out of the paper's 11,000+ → partial comparability with the published numbers.
- **FUNSD** — direct zip on the official site, no registration. 199 forms (very small). **Custom non-commercial license**, RVL-CDIP images with license responsibility passed on to the user: never redistribute the images in the repo. Noisy annotations documented (FUNSD-r exists).

## Flag summary

| Flag | Datasets concerned |
|---|---|
| Clean HF loading today | BEIR×3, HotpotQA, SQuAD 2.0, TAT-QA, ChartQA, CORD v2, BIRD Mini-Dev, Spider (questions), DocVQA mirrors |
| Fragile retrieval path (Drive/Dropbox/script) | MuSiQue, 2WikiMultihopQA, QASPER (parquet branch), HybridQA, WikiTableQuestions, Spider (DBs), FUNSD (direct zip: ok) |
| License to flag | ChartQA (GPL-3.0), FUNSD (non-commercial), DocVQA (unclear), BEIR (not guaranteed upstream), WTQ (share-alike + wrong HF card) |
| Volumes | NQ 145 GB (removed), full BIRD 33 GB (→ Mini-Dev), DocVQA 12.4 GB (→ val sample), the rest < 2.5 GB |
| Replacement | τ-bench → **tau2-bench (τ³)**; NQ → SQuAD 2.0 is enough |

## Recommended starter subset (phase 0)

**A single reference loader: BEIR/SciFact.** 5,183 docs, 300 test queries, near-binary qrels,
4.55 MB, native Parquet on HF, abundant published scores (BM25 nDCG@10 ≈ 0.67–0.69 in the BEIR
literature) — the simplest objective reference point to validate against. NFCorpus is smaller on disk (3.25 MB) but
its ~134k graded qrels complicate harness validation; FiQA is 6× bigger.
