#!/usr/bin/env python3
"""Upload the task data to a Hugging Face dataset repo. DRY RUN BY DEFAULT: prints exactly what would be uploaded and where; nothing leaves the machine
unless you pass --yes. Needs `pip install huggingface_hub` and HF_TOKEN in the environment (never on the command line, never in git).
  python3 scripts/publish_hf.py                      # dry run
  HF_TOKEN=... python3 scripts/publish_hf.py --yes   # upload (launch day, after the owner's OK)
Layout: <repo>/<env>/tasks.jsonl for every env that has one, plus LICENSE-DATA and a generated dataset card (CC BY 4.0, with the same non-affiliation and
simplified-rules notes as the READMEs). The upload STRIPS every answer field (gold answers and actions, forbidden actions, expected feasibility, binding constraints, traps, solver and design notes;
see STRIP_TOP / STRIP_META / STRIP_EXTRA): the dataset holds prompts, worlds and parameters only. Grade with the repository's graders."""
import argparse, glob, json, os, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARD = """---
license: cc-by-4.0
language: [en, hi]
pretty_name: Navital Gym tasks
tags: [agents, evaluation, india, tool-use]
---
# Navital Gym: task data

Task prompts and structured parameters for the environments in https://github.com/Navitallabs/navital-gym (code: Apache-2.0; this data: CC BY 4.0, attribution "Navital Labs, Navital Gym").
Environments: {envs}.

**Simplified rules, synthetic data.** Every task uses a documented, simplified version of Indian practice and synthetic data; nothing here states current law, railway, bank or tax rules. Not affiliated with or endorsed by NPCI, RBI, GSTN / CBIC, IRCTC / Indian Railways or any bank or government body. Not financial or tax advice.
**No answers here.** Gold answers, expected actions, expected feasibility and solver notes are not part of this dataset; grade with the graders in the repository (`navital-gym run`).
Each env's README in the repository states its rules, sources and "as of" date. Run the tasks with `pip install navital-gym` and `navital-gym run --env <name> --agent <agent>`.
"""

STRIP_TOP = ("gold_answer", "gold_actions", "forbidden_actions", "expected_feasible", "binding_constraint", "traps", "grader_notes")
STRIP_META = ("gold_answer", "forbidden_actions", "binding_sets", "design_intent_binding", "design_intent_feasible", "design_notes", "oracle_plan_cost", "solver_note", "review_status")
STRIP_EXTRA = {"support": ("family", "kind")}       # support scenario names ("return_ineligible", "cancel_after_ship") state the expected decision

def strip_row(row: dict, env: str) -> dict:
    """One task row without any answer field (top level and meta)."""
    r = {k: v for k, v in row.items() if k not in STRIP_TOP and k not in STRIP_EXTRA.get(env, ())}
    if isinstance(r.get("meta"), dict):
        r["meta"] = {k: v for k, v in r["meta"].items() if k not in STRIP_META and k not in STRIP_EXTRA.get(env, ())}
    return r

def strip_file(src: str, dst: str, env: str) -> int:
    n = 0
    with open(src) as f, open(dst, "w") as o:
        for line in f:
            if line.strip():
                o.write(json.dumps(strip_row(json.loads(line), env), ensure_ascii=False) + "\n"); n += 1
    return n

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
    stage = tempfile.mkdtemp(prefix="navital-hf-")        # stripped copies: the upload never reads the original task files
    for dest in [d for d in files if d.endswith(".jsonl")]:
        out = os.path.join(stage, dest.replace("/", "__")); n = strip_file(files[dest], out, dest.split("/")[0]); files[dest] = (out, n)
    files["LICENSE-DATA"] = (files["LICENSE-DATA"], "-")
    banned = set(STRIP_TOP) | set(STRIP_META)
    for dest, (src, n) in files.items():
        if dest.endswith(".jsonl"):
            ban = banned | set(STRIP_EXTRA.get(dest.split("/")[0], ()))
            for line in open(src):
                row = json.loads(line)
                left = (set(row) | set(row.get("meta") or {})) & ban
                if left: sys.exit(f"{dest}: answer fields left after stripping: {sorted(left)}")
    print(f"target dataset repo: {a.repo}  ({'UPLOAD' if a.yes else 'dry run'}); answer fields stripped: {', '.join(sorted(banned))}")
    for dest, (src, n) in files.items():
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
    for dest, (src, _n) in files.items():
        api.upload_file(path_or_fileobj=src, path_in_repo=dest, repo_id=a.repo, repo_type="dataset")
    print("uploaded")

if __name__ == "__main__":
    main()
