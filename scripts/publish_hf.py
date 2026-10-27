#!/usr/bin/env python3
"""Upload the task data to a Hugging Face dataset repo. DRY RUN BY DEFAULT: prints exactly what would be uploaded and where; nothing leaves the machine
unless you pass --yes. Needs `pip install huggingface_hub` and HF_TOKEN in the environment (never on the command line, never in git).
  python3 scripts/publish_hf.py                      # dry run
  HF_TOKEN=... python3 scripts/publish_hf.py --yes   # upload (launch day, after the owner's OK)
Layout: <repo>/<env>/tasks.jsonl for every env that has one, plus LICENSE-DATA and a generated dataset card (CC BY 4.0, with the same non-affiliation and
simplified-rules notes as the READMEs). Tasks carry their hidden fields (expected feasibility, binding rules, gold answers): publishing them is the
owner's decision."""
import argparse, glob, json, os, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARD = """---
license: cc-by-4.0
language: [en, hi]
pretty_name: Navital Gym tasks
tags: [agents, evaluation, india, tool-use]
---
# Navital Gym: task data

Task prompts, structured parameters and labels for the environments in https://github.com/Navitallabs/navital-gym (code: Apache-2.0; this data: CC BY 4.0, attribution "Navital Labs, Navital Gym").
Environments: {envs}.

**Simplified rules, synthetic data.** Every task uses a documented, simplified version of Indian practice and synthetic data; nothing here states current law, railway, bank or tax rules. Not affiliated with or endorsed by NPCI, RBI, GSTN / CBIC, IRCTC / Indian Railways or any bank or government body. Not financial or tax advice.
Each env's README in the repository states its rules, sources and "as of" date. Run the tasks with `pip install navital-gym` and `navital-gym run --env <name> --agent <agent>`.
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="NavitalLabs/navital-gym-tasks"); ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    files = {}
    for p in sorted(glob.glob(os.path.join(ROOT, "navital_gym", "envs", "*", "tasks*.jsonl")), key=lambda x: (x.count("tasks_source"), x)):
        env, name = p.split(os.sep)[-2], os.path.basename(p)
        if name == "tasks.jsonl":
            files[f"{env}/tasks.jsonl"] = p
        elif name == "tasks_source.jsonl" and f"{env}/tasks.jsonl" not in files:       # UPI keeps its tasks under this name
            files[f"{env}/tasks.jsonl"] = p
    files["LICENSE-DATA"] = os.path.join(ROOT, "LICENSE-DATA")
    envs = sorted({k.split("/")[0] for k in files if "/" in k})
    print(f"target dataset repo: {a.repo}  ({'UPLOAD' if a.yes else 'dry run'})")
    for dest, src in files.items():
        n = sum(1 for _ in open(src)) if src.endswith(".jsonl") else "-"
        print(f"  {dest:28} {os.path.getsize(src):>9} bytes  {n} rows")
    if not a.yes:
        print("dry run only; pass --yes to upload"); return
    token = os.environ.get("HF_TOKEN")
    if not token:
        sys.exit("HF_TOKEN is not set")
    from huggingface_hub import HfApi
    api = HfApi(token=token)
    api.create_repo(a.repo, repo_type="dataset", exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        card = os.path.join(td, "README.md"); open(card, "w").write(CARD.format(envs=", ".join(envs)))
        api.upload_file(path_or_fileobj=card, path_in_repo="README.md", repo_id=a.repo, repo_type="dataset")
    for dest, src in files.items():
        api.upload_file(path_or_fileobj=src, path_in_repo=dest, repo_id=a.repo, repo_type="dataset")
    print("uploaded")

if __name__ == "__main__":
    main()
