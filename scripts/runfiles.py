"""One place that reads the saved run files for every results script (make_results, update_readme_results, export_leaderboard uses its own stricter reader).
Row kinds by file name:   <env>-<slug>-s<N>.json   a stratified sample of N standard tasks
                          <env>-<slug>-full.json   the whole standard split (incl. support's experimental)
                          <env>-<slug>-easy.json   the whole easy split
A row is `complete` only if it has all the tasks it should (N, or every task of that split) and is not a run still in progress (`partial`)."""
import glob, importlib, json, os, re, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_cache = {}
from decimal import Decimal, ROUND_HALF_UP
def r2(x):
    """Two decimals, half-up (0.975 -> 0.98), the same on every page; Python's own format() would print 0.97 for some of these."""
    return str(Decimal(repr(round(float(x), 6))).quantize(Decimal("0.01"), ROUND_HALF_UP))

def first_run_partial(tasks, summary):
    """Partial credit (mean rule score) over the FIRST run of every answered task: the same basis as pass@1. The grader's own mean_score averages all k runs,
    which differs only for k>1 rows; pages show this value so that RESULTS, README and the leaderboard agree."""
    runs = [r[0]["score"] for r in tasks.values() if r and not (r[0].get("meta") or {}).get("error")]
    return sum(runs) / len(runs) if runs else summary["mean_score"]
def truncated_tasks(tasks, ids=None):
    """Tasks (first run, like pass@1) whose model output hit the output-token limit (finish_reason "length", meta.truncated). They are scored as
    failed, never skipped; this count says how many of a row's failures may be a cut-off rather than a wrong answer."""
    return sum(1 for tid, r in tasks.items() if (ids is None or tid in ids) and r and ((r[0].get("meta") or {}).get("truncated") or 0) > 0)

def env_tasks(env, easy=False):
    key = (env, easy)
    if key not in _cache:
        mod = importlib.import_module(f"navital_gym.envs.{env}")
        import inspect
        params = inspect.signature(mod.load_env).parameters
        kw = {}
        if easy:
            kw["splits"] = ("easy",)
        if env == "support" and not easy:
            kw["include_experimental"] = True
        _cache[key] = mod.load_env(**kw).tasks
    return _cache[key]

def kind_of(path):
    b = os.path.basename(path)[:-5]
    m = re.search(r"-s(\d+)$", b)
    if m: return "sample", int(m.group(1))
    if b.endswith("-full"): return "full", None
    if b.endswith("-easy"): return "easy", None
    return None, None

def rows(root=ROOT, runs_dir=None):
    runs_dir = runs_dir or os.path.join(root, "runs")
    for path in sorted(glob.glob(os.path.join(runs_dir, "*.json"))):
        if path.endswith((".transcripts.json", ".stale.json", "spend-ledger.json")):
            continue
        kind, n = kind_of(path)
        if kind is None:
            continue
        env = os.path.basename(path).split("-")[0]
        for agent, d in json.load(open(path)).items():
            s, st = d["summary"], d.get("settings", {})
            if kind == "sample": need = n
            else: need = len(env_tasks(env, easy=(kind == "easy")))
            yield {"env": env, "kind": kind, "tier": "easy" if kind == "easy" else "standard", "model": st.get("model", agent), "provider": st.get("provider", "scripted"),
                   "summary": s, "n": s.get("answered", s["tasks"]), "need": need, "complete": (not d.get("partial")) and s.get("answered", s["tasks"]) >= need, "commit": d.get("navital_gym_commit"), "graded": d.get("graded_with"),
                   "usd": sum(sc.get("meta", {}).get("usd", 0) for r in d["tasks"].values() for sc in r), "date": time.strftime("%Y-%m-%d", time.gmtime(os.path.getmtime(path))),
                   "file": os.path.basename(path), "tasks": d["tasks"]}


def load_env_for(path):
    """The env a run file was made with: easy files load the easy split; support loads core+experimental; everything else loads its default (core)."""
    env = os.path.basename(path).split("-")[0]
    mod = importlib.import_module(f"navital_gym.envs.{env}")
    kw = {}
    if os.path.basename(path)[:-5].endswith("-easy"):
        kw["splits"] = ("easy",)
    elif env == "support":
        kw["include_experimental"] = True
    return mod.load_env(**kw)
