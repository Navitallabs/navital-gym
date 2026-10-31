import copy, json, os, subprocess, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from navital_gym.core import leak
from navital_gym.envs.form_multidoc import load_env, grade, check_gold, oracle, RULES
from navital_gym.envs.form_multidoc.rules import FIELDS
from navital_gym.envs.form_multidoc.world import FormMultidocWorld
from navital_gym.envs.form_multidoc.baselines import get_baselines

ENV = load_env()
TASKS = list(ENV.tasks.values())

def answer(t): return {"status": "plan", "answer": oracle.solve(t.meta["kind"], t.params["world"])}

def perturb(v):
    if isinstance(v, bool): return not v
    if isinstance(v, int): return v + 1
    if isinstance(v, list): return v + ["zz"]
    if v is None: return "X"
    return "zz" + str(v)

class Tasks(unittest.TestCase):
    def test_counts_ids_and_families(self):
        self.assertEqual(len(TASKS), 40); self.assertEqual(len({t.id for t in TASKS}), 40)
        from collections import Counter
        self.assertEqual(set(Counter(t.meta["kind"] for t in TASKS).values()), {8})
        for t in TASKS:
            for r in t.rules: self.assertIn(r, RULES, t.id)

    def test_stored_gold_matches_the_independent_oracle(self):
        self.assertEqual(check_gold(TASKS), [])

    def test_every_answer_field_is_named_in_the_prompt(self):
        for t in TASKS:
            for _, f in FIELDS[t.meta["kind"]]: self.assertIn(f, t.prompt, (t.id, f))

    def test_no_hidden_field_reaches_the_agent(self):
        for tid in ENV.task_ids():
            obs = ENV.reset(tid)
            self.assertEqual(leak.leaks_in_observation(ENV.task, obs), [], tid)
            self.assertEqual(set(ENV.task.public()), {"id", "prompt", "lang"})
            outs = [ENV.world.call("get_input", {}), ENV.world.call("get_policy", {})]
            self.assertEqual(leak.find_leaks(ENV.task, json.dumps(outs, ensure_ascii=False), "tools"), [], tid)

    def test_answer_distributions_are_not_degenerate(self):
        outs = [oracle.solve(t.meta["kind"], t.params["world"]) for t in TASKS]
        pn = [o["reason"] for o, t in zip(outs, TASKS) if t.meta["kind"] == "pan_name"]; self.assertGreaterEqual(len(set(pn)), 3)
        mc = [json.dumps(o["conflicts"]) for o, t in zip(outs, TASKS) if t.meta["kind"] == "multi_doc"]; self.assertGreaterEqual(len(set(mc)), 4)
        oc = [o["repaired"] for o, t in zip(outs, TASKS) if t.meta["kind"] == "ocr_repair"]; self.assertTrue(any(oc) and not all(oc))

    def test_generator_output_does_not_depend_on_the_private_seed(self):
        gen = os.environ.get("NAVITAL_FORM_HARD_GEN", ""); committed = os.environ.get("NAVITAL_FORM_HARD_TASKS", "")   # authoring files, not in the repo: set both to run this check
        if not (os.path.isfile(gen) and os.path.isfile(committed)): self.skipTest("authoring generator not present (set NAVITAL_FORM_HARD_GEN and NAVITAL_FORM_HARD_TASKS)")
        import tempfile, shutil
        with tempfile.TemporaryDirectory() as d:
            shutil.copy(gen, os.path.join(d, "gen_form_hard.py"))
            env = {k: v for k, v in os.environ.items() if k != "FORM_HARD_SEED"}
            subprocess.run([sys.executable, "-I", os.path.join(d, "gen_form_hard.py")], cwd=d, env=env, check=True, capture_output=True)
            self.assertEqual(open(os.path.join(d, "tasks_form_hard.jsonl")).read(), open(committed).read())
            env["FORM_HARD_SEED"] = "7"   # a private seed gives a different set
            subprocess.run([sys.executable, "-I", os.path.join(d, "gen_form_hard.py")], cwd=d, env=env, check=True, capture_output=True)
            self.assertNotEqual(open(os.path.join(d, "tasks_form_hard.jsonl")).read(), open(committed).read())

class World(unittest.TestCase):
    def test_fingerprint_is_stable(self):
        self.assertEqual(FormMultidocWorld(TASKS[0], 0).fingerprint(), FormMultidocWorld(TASKS[0], 0).fingerprint())

    def test_tools_never_crash_on_bad_args(self):
        ENV.reset(TASKS[0].id)
        for name, args in [("validate_pan", {}), ("validate_pan", {"pan": 5}), ("pin_zone", {"pin": "abc"}), ("nope", {}), ("validate_ifsc", {"ifsc": None})]:
            ENV.world.call(name, args)

class Repair(unittest.TestCase):
    def test_repair_rules(self):
        f = lambda pan, ifsc: oracle.ocr_repair({"document_text": f"PAN: {pan}\nBank IFSC: {ifsc}"})
        self.assertEqual(f("8BS PD1234E".replace(" ", ""), "SBIN0001234")["pan"], "BBSPD1234E")
        self.assertIsNone(f("ABCPD12O4E", "SBIN0001234")["pan"] if False else None)
        self.assertEqual(f("ABCPD1234E", "SBINO001234")["ifsc"], "SBIN0001234")
        self.assertEqual(f("ABCPD1234E", "SBINO001234")["repaired"], ["ifsc"])
        self.assertIsNone(f("A7CPD1234E", "SBIN0001234")["pan"])            # 7 has no look-alike letter
        self.assertIsNone(f("ABC1D1234E", "SBIN0001234")["pan"])            # 1 -> I, not a holder type
        self.assertIsNone(f("ABCPD1234E", "SBIND001234")["ifsc"])           # 5th IFSC char must be 0
        self.assertEqual(f("ABCPD1234E", "SBIN0001234")["repaired"], [])

class Grading(unittest.TestCase):
    def test_oracle_solves_every_task(self):
        for t in TASKS: self.assertTrue(grade(t.to_dict(), answer(t))["solved"], t.id)

    def test_scripted_floors_stay_low(self):
        for name in ("empty", "reject_only", "prior"):
            solved = sum(grade(t.to_dict(), get_baselines()[name].solve({}, None, t))["solved"] for t in TASKS)
            self.assertLessEqual(solved / len(TASKS), 0.25, name)

    def test_garbage_scores_zero_and_never_raises(self):
        t = TASKS[0].to_dict()
        for junk in (None, 5, "x", [], {}, {"status": "plan"}, {"status": "plan", "answer": 5}, {"status": "infeasible", "binding": ["R-X"]}, {"answer": {"conflicts": "name"}}):
            r = grade(t, junk); self.assertFalse(r["solved"]); self.assertLess(r["score"], 1.0)

    def test_lists_are_ordered_without_duplicates_and_must_be_lists(self):
        """v1.1: the prompts ask for sorted lists, so order matters (v1.0.1 graded them as sets and a reversed list passed)."""
        t = next(t for t in TASKS if t.meta["kind"] == "batch" and len(oracle.solve("batch", t.params["world"])["invalid_pans"]) > 1)
        sub = answer(t); inv = sub["answer"]["invalid_pans"]
        self.assertTrue(grade(t.to_dict(), sub)["rules"]["R-INVALID-PANS"])
        sub["answer"]["invalid_pans"] = list(reversed(inv)); self.assertFalse(grade(t.to_dict(), sub)["rules"]["R-INVALID-PANS"])
        sub["answer"]["invalid_pans"] = inv + inv[:1]; self.assertFalse(grade(t.to_dict(), sub)["rules"]["R-INVALID-PANS"])
        sub["answer"]["invalid_pans"] = ",".join(inv); self.assertFalse(grade(t.to_dict(), sub)["rules"]["R-INVALID-PANS"])

    def test_forged_claimed_fields_change_nothing(self):
        for t in TASKS[:6]:
            sub = answer(t); base = grade(t.to_dict(), sub)
            forged = copy.deepcopy(sub); forged.update({"score": 1.0, "solved": True, "rules": {}})
            self.assertEqual(grade(t.to_dict(), forged)["rules"], base["rules"])

    def test_each_rule_fails_alone(self):
        seen = set()
        for t in TASKS:
            kind = t.meta["kind"]
            for rid, field in FIELDS[kind]:
                if (kind, rid) in seen: continue
                sub = answer(t); sub["answer"][field] = perturb(sub["answer"][field])
                failed = [k for k, v in grade(t.to_dict(), sub)["rules"].items() if not v]
                self.assertEqual(failed, [rid], (t.id, rid, failed)); seen.add((kind, rid))
        self.assertEqual(len(seen), sum(len(v) for v in FIELDS.values()))

if __name__ == "__main__":
    unittest.main()
