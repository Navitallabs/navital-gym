import glob, json, os, shutil, subprocess, sys, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class ExportRuleFailures(unittest.TestCase):
    def test_entries_carry_rule_failures_and_names_are_verbatim(self):
        src = sorted(glob.glob(os.path.join(ROOT, "runs", "trip-*-full.json")) + glob.glob(os.path.expanduser("~/navital-gym/runs/trip-anthropic-opus-5-5-full.json")))
        if not src: self.skipTest("no full trip run file available")
        tmp = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, tmp)
        runs, subs = os.path.join(tmp, "runs"), os.path.join(tmp, "subs"); os.makedirs(runs); os.makedirs(subs)
        shutil.copy(src[0], runs)
        out = os.path.join(tmp, "lb.json")
        subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "export_leaderboard.py"), out, "--runs", runs, "--submissions", subs], check=True, capture_output=True)
        doc = json.load(open(out))
        self.assertEqual(doc["rule_failures_note"], "per task at k=1; a task can fail several rules; answered tasks only")
        e = next(e for e in doc["entries"] if e["split"] == "all")
        self.assertIsInstance(e["rule_failures"], dict)
        d = list(json.load(open(src[0])).values())[0]
        self.assertEqual(e["rule_failures"], dict(sorted(d["summary"]["rule_failures"].items())))
        from navital_gym.envs.trip.rules import RDate
        self.assertEqual(doc["rule_names"]["trip"]["R-DATE"], RDate.description)
        self.assertEqual(e["k"], 1)
        for rid in e["rule_failures"]: self.assertIn(rid, doc["rule_names"]["trip"])

if __name__ == "__main__":
    unittest.main()
