"""scripts/verify_submission.py: one good submission passes, and each kind of tampering fails with a reason. The submission is built here from the public oracle
(upi easy split), recorded the way a model run is saved, so no model, key or run file is needed."""
import copy, json, os, shutil, sys, tempfile, unittest
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "scripts"))
import verify_submission
from navital_gym.core.grader import summarize
from navital_gym.core.version import code_id
from navital_gym.envs.upi import load_env, get_baselines

NAME = "upi-testmodel-easy"

def build(dirpath):
    env = load_env(splits=("easy",))
    oracle = get_baselines()["oracle"]
    tasks, transcripts, results = {}, {}, {}
    for tid in sorted(env.tasks):
        obs = env.reset(tid)
        calls = []
        def call(name, args=None):
            res = env.world.call(name, args)
            calls.append((f"c{len(calls)}", name, args or {}, res)); return res
        sub = oracle.solve(obs, call, env.task)
        sc = env.grade(env.task, sub); sc.meta = {"error": None, "turns": len(calls) + 1}
        results[tid] = [sc]; tasks[tid] = [sc.to_dict()]
        msgs = [{"role": "user", "content": obs["prompt"] + "\n\n(tools and format instructions)"},
                {"role": "assistant", "content": "", "tool_calls": [{"id": i, "name": n, "args": a} for i, n, a, _ in calls]}]
        msgs += [{"role": "tool", "tool_call_id": i, "name": n, "content": json.dumps(r)} for i, n, _, r in calls]
        msgs.append({"role": "assistant", "content": json.dumps(sub)})
        transcripts[tid] = [msgs]
    agent = "scripted:testmodel"
    run = {agent: {"k": 1, "navital_gym_commit": code_id(), "graded_with": code_id(), "settings": {"model": "testmodel", "provider": "test"}, "summary": summarize(results, env.tasks), "tasks": tasks}}
    os.makedirs(dirpath, exist_ok=True)
    json.dump(run, open(os.path.join(dirpath, NAME + ".json"), "w")); json.dump({agent: transcripts}, open(os.path.join(dirpath, NAME + ".transcripts.json"), "w"))
    json.dump({"model": "testmodel", "provider": "test", "date": "2026-10-27", "submitter": "tests"}, open(os.path.join(dirpath, "submission.json"), "w"))
    return os.path.join(dirpath, NAME + ".json")

class VerifySubmission(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(); cls.good = build(os.path.join(cls.tmp, "good"))
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def tampered(self, name, edit_run=None, edit_tr=None):
        d = os.path.join(self.tmp, name); shutil.copytree(os.path.dirname(self.good), d)
        rp, tp = os.path.join(d, NAME + ".json"), os.path.join(d, NAME + ".transcripts.json")
        run, tr = json.load(open(rp)), json.load(open(tp))
        if edit_run: edit_run(next(iter(run.values())))
        if edit_tr: edit_tr(next(iter(tr.values())))
        with open(rp, "w") as f: json.dump(run, f)
        with open(tp, "w") as f: json.dump(tr, f)
        return verify_submission.verify(rp)

    def test_good_file_passes(self):
        ok, reasons, notes = verify_submission.verify(self.good)
        self.assertTrue(ok, reasons)
        self.assertTrue(any(n.startswith(f"replayed at {code_id()}") for n in notes), notes)

    def test_run_from_an_older_prompt_is_rejected(self):
        def edit(tr):
            for runs in tr.values():
                m = runs[0][0]; m["content"] = m["content"].replace(m["content"].split("\n\n(tools")[0], "an older, different question"); break
        ok, reasons, _ = self.tampered("oldprompt", edit_tr=edit)
        self.assertFalse(ok); self.assertTrue(any("public prompt" in r for r in reasons), reasons)

    def test_claimed_score_edited(self):
        def edit(d):
            t = next(t for t, r in d["tasks"].items() if not r[0]["solved"]) if any(not r[0]["solved"] for r in d["tasks"].values()) else next(iter(d["tasks"]))
            r = d["tasks"][t][0]; r["solved"] = not r["solved"]
        ok, reasons, _ = self.tampered("claim", edit_run=edit)
        self.assertFalse(ok); self.assertTrue(any("public grader gives" in r for r in reasons), reasons)

    def test_final_answer_edited_in_transcript(self):
        def edit(tr):
            tid = next(iter(tr)); tr[tid][0][-1]["content"] = json.dumps({"status": "plan", "answer": {}})
        ok, reasons, _ = self.tampered("answer", edit_tr=edit)
        self.assertFalse(ok); self.assertTrue(any("public grader gives" in r for r in reasons), reasons)

    def test_tool_result_edited_in_transcript(self):
        def edit(tr):
            for runs in tr.values():
                for m in runs[0]:
                    if m.get("role") == "tool": m["content"] = json.dumps({"policy": "edited"}); return
        ok, reasons, _ = self.tampered("tool", edit_tr=edit)
        self.assertFalse(ok); self.assertTrue(any("edited transcript" in r for r in reasons), reasons)

    def test_forged_summary_numbers_are_caught_even_outside_pass_at_1(self):
        def edit(d): d["summary"]["by_split"]["easy"]["mean_score"] = 1.0; d["summary"]["format_fail"] = 0.5
        ok, reasons, _ = self.tampered("summary", edit_run=edit)
        self.assertFalse(ok); self.assertTrue(any(r.startswith("summary/") for r in reasons), reasons)

    def test_error_or_repair_flags_are_not_taken_from_the_file(self):
        def edit(d):
            for runs in d["tasks"].values():
                runs[0]["meta"]["error"] = "HTTP 429"; break
        ok, reasons, _ = self.tampered("err", edit_run=edit)
        self.assertFalse(ok); self.assertTrue(any("errors are not accepted" in r for r in reasons), reasons)
        def edit2(d):
            for runs in d["tasks"].values():
                runs[0]["meta"]["repaired"] = True; break
        ok, reasons, _ = self.tampered("rep", edit_run=edit2)
        self.assertFalse(ok); self.assertTrue(any("claims repaired=True" in r for r in reasons), reasons)

    def test_task_outside_the_public_split(self):
        def edit(d):
            d["tasks"]["IN-UPI-HELDOUT-1"] = copy.deepcopy(next(iter(d["tasks"].values())))
        ok, reasons, _ = self.tampered("heldout", edit_run=edit)
        self.assertFalse(ok); self.assertTrue(any("outside the public split" in r for r in reasons), reasons)

    def test_missing_task_is_not_the_full_split(self):
        def edit(d): d["tasks"].pop(next(iter(d["tasks"])))
        ok, reasons, _ = self.tampered("missing", edit_run=edit)
        self.assertFalse(ok); self.assertTrue(any("missing" in r for r in reasons), reasons)

    def test_exporter_counts_only_verified_submissions_as_community(self):
        import subprocess
        subs = os.path.join(self.tmp, "subs"); empty = os.path.join(self.tmp, "norun"); os.makedirs(empty, exist_ok=True)
        shutil.copytree(os.path.dirname(self.good), os.path.join(subs, "good-model"), dirs_exist_ok=True)
        self.tampered("claim2", edit_run=lambda d: d["tasks"].pop(next(iter(d["tasks"]))))
        shutil.copytree(os.path.join(self.tmp, "claim2"), os.path.join(subs, "bad-model"), dirs_exist_ok=True)
        out = os.path.join(self.tmp, "lb.json")
        subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "export_leaderboard.py"), out, "--runs", empty, "--submissions", subs], check=True, capture_output=True)
        doc = json.load(open(out))
        self.assertEqual([(e["origin"], e["model"], e["self_reported"], e["split"]) for e in doc["entries"]], [("community", "testmodel", True, "easy")])
        self.assertEqual([e["origin"] for e in doc["excluded"]], ["community"]); self.assertIn("failed verification", doc["excluded"][0]["reason"])

if __name__ == "__main__":
    unittest.main()
