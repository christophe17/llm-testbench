# data/

Cache local des jeux de données publics. **Rien ici n'est versionné** (voir `.gitignore`) :
plusieurs jeux sont sous licence CC BY-SA (copyleft) et FUNSD-like interdisent la
redistribution — les loaders de `src/llm_testbench/eval/loaders/` téléchargent depuis les
sources officielles et cachent ici.

- `hf/` — cache Hugging Face (`datasets` + `huggingface_hub`)
- `bird/` — BIRD Mini-Dev (zip + bases SQLite extraites)
- `golden/` — (phase 2) golden set maison, **versionné explicitement**, avec CHANGELOG
