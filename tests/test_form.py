import copy, json, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from navital_gym.core import leak
from navital_gym.envs.form import load_env, grade, check_gold, oracle, RULES
from navital_gym.envs.form.rules import FIELDS
from navital_gym.envs.form.world import FormWorld

ENV = load_env()
TASKS = list(ENV.tasks.values())

def answer(t): return {"status": "plan", "answer": oracle.solve(t.meta["kind"], t.params["world"])}

def perturb(v):
    if isinstance(v, bool): return not v
    if isinstance(v, int): return v + 1
    if v is None: return "X"
    return "zz" + str(v)

class Tasks(unittest.TestCase):
    def test_counts_ids_and_rules(self):
        self.assertEqual(len(TASKS), 50)
        self.assertEqual(len({t.id for t in TASKS}), 50)
        for t in TASKS:
            for r in t.rules:
                self.assertIn(r, RULES, t.id)

    def test_stored_gold_matches_the_independent_oracle(self):
        self.assertEqual(check_gold(TASKS), [])

    def test_no_hidden_field_reaches_the_agent(self):
        for tid in ENV.task_ids():
            obs = ENV.reset(tid)
            self.assertEqual(leak.leaks_in_observation(ENV.task, obs), [], tid)
            self.assertEqual(set(ENV.task.public()), {"id", "prompt", "lang"})
            outs = [ENV.world.call("get_input", {}), ENV.world.call("get_policy", {})]
            self.assertEqual(leak.find_leaks(ENV.task, json.dumps(outs, ensure_ascii=False), "tools"), [], tid)
            self.assertNotIn("gold", json.dumps(outs).lower())

class World(unittest.TestCase):
    def test_fingerprint_is_stable(self):
        # Form Desk carries no seeded randomness: the world is the task's own input, so seeds do not change it.
        t = TASKS[0]
        self.assertEqual(FormWorld(t, 0).fingerprint(), FormWorld(t, 0).fingerprint())

    def test_tools_never_crash_on_bad_args(self):
        ENV.reset(TASKS[0].id)
        for name, args in [("validate_pan", {}), ("validate_pan", {"pan": 5}), ("pin_zone", {"pin": "abc"}), ("pin_zone", {"pin": "900001"}), ("nope", {}), ("validate_mobile", {"number": None})]:
            self.assertIn("error", ENV.world.call(name, args)) if name in ("pin_zone", "nope") or args == {} else ENV.world.call(name, args)

class Mobile(unittest.TestCase):
    def test_only_a_leading_country_or_trunk_prefix_is_stripped(self):
        n = oracle.normalise_mobile
        self.assertEqual(n("+91 98765 43210"), "9876543210"); self.assertEqual(n("09876543210"), "9876543210"); self.assertEqual(n("98765-43210"), "9876543210")
        for bad in ("98765432109", "1234509876543210", "0919876543210", "5876543210"):
            self.assertFalse(oracle.MOB_RE.match(n(bad)), bad)   # an 11-digit typo is invalid, never repaired by keeping the last 10 digits
        ENV.reset(TASKS[0].id)
        self.assertFalse(ENV.world.call("validate_mobile", {"number": "98765432109"})["valid"])

class Grading(unittest.TestCase):
    def test_oracle_solves_every_task(self):
        for t in TASKS:
            r = grade(t.to_dict(), answer(t))
            self.assertTrue(r["solved"], (t.id, r))

    def test_scripted_cheats_do_not_solve(self):
        from navital_gym.envs.form.baselines import get_baselines
        for name in ("empty", "shotgun"):
            solved = sum(grade(t.to_dict(), get_baselines()[name].solve({}, None, t))["solved"] for t in TASKS)
            self.assertLessEqual(solved, 5, name)

    def test_garbage_scores_zero_and_never_raises(self):
        t = TASKS[0].to_dict()
        for junk in (None, 5, "x", [], {}, {"status": "plan"}, {"status": "plan", "answer": 5}, {"status": "infeasible", "binding": ["R-X"]}, {"answer": {"full_name": ["a"]}}):
            r = grade(t, junk)
            self.assertFalse(r["solved"]); self.assertLess(r["score"], 1.0)

    def test_infeasible_claims_never_solve(self):
        for t in TASKS[:10]:
            self.assertFalse(grade(t.to_dict(), {"status": "infeasible", "binding": []})["solved"])

    def test_forged_claimed_fields_change_nothing(self):
        for t in TASKS[:6]:
            sub = answer(t); base = grade(t.to_dict(), sub)
            forged = copy.deepcopy(sub); forged.update({"score": 1.0, "solved": True, "rules": {}}); forged["answer"]["score"] = 1.0
            self.assertEqual(grade(t.to_dict(), forged)["rules"], base["rules"])
            wrong = copy.deepcopy(sub); wrong["score"] = 1.0; wrong["solved"] = True
            k = next(iter(sub["answer"])); wrong["answer"][k] = perturb(sub["answer"][k])
            self.assertFalse(grade(t.to_dict(), wrong)["solved"])

    def test_inputs_are_not_mutated_and_key_order_is_irrelevant(self):
        t = TASKS[3]; td = t.to_dict(); before = json.dumps(td, sort_keys=True)
        sub = answer(t); sub_before = json.dumps(sub, sort_keys=True)
        a = grade(td, sub)
        rev = {"answer": dict(reversed(list(sub["answer"].items()))), "status": "plan"}
        self.assertEqual(a, grade(td, rev))
        self.assertEqual(before, json.dumps(td, sort_keys=True)); self.assertEqual(sub_before, json.dumps(sub, sort_keys=True))

    def test_each_rule_fails_alone(self):
        seen = set()
        for t in TASKS:
            kind = t.meta["kind"]
            for rid, field in FIELDS[kind]:
                if (kind, rid) in seen: continue
                sub = answer(t); sub["answer"][field] = perturb(sub["answer"][field])
                r = grade(t.to_dict(), sub)
                failed = [k for k, v in r["rules"].items() if not v]
                self.assertEqual(failed, [rid], (t.id, rid, failed))
                seen.add((kind, rid))
        self.assertEqual(len(seen), sum(len(v) for v in FIELDS.values()))

    def test_invalid_values_must_be_null_not_repaired(self):
        t = next(t for t in TASKS if t.meta["kind"] == "kyc_fill" and oracle.solve("kyc_fill", t.params["world"])["pan"] is None)
        sub = answer(t); sub["answer"]["pan"] = "ABCPD1234E"
        self.assertFalse(grade(t.to_dict(), sub)["rules"]["R-PAN"])
        del sub["answer"]["pan"]
        self.assertFalse(grade(t.to_dict(), sub)["rules"]["R-PAN"])

if __name__ == "__main__":
    unittest.main()
