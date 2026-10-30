import glob, json, os, subprocess, sys, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import publish_hf as H

class PublishHF(unittest.TestCase):
    def test_no_answer_field_survives_in_any_env(self):
        n = 0
        for p in sorted(glob.glob(os.path.join(ROOT, "navital_gym", "envs", "*", "tasks*.jsonl"))):
            env = p.split(os.sep)[-2]
            for line in open(p):
                if not line.strip(): continue
                r = H.strip_row(json.loads(line), env); n += 1
                ban = set(H.STRIP_TOP) | set(H.STRIP_META) | set(H.STRIP_EXTRA.get(env, ()))
                self.assertFalse((set(r) | set(r.get("meta") or {})) & ban, (p, r["id"]))
                self.assertIn("prompt", r); self.assertIn("id", r)
        self.assertGreater(n, 300)

    def test_support_scenario_names_are_stripped(self):
        r = json.loads(open(os.path.join(ROOT, "navital_gym", "envs", "support", "tasks.jsonl")).readline())
        s = H.strip_row(r, "support")
        self.assertNotIn("family", s); self.assertNotIn("kind", s.get("meta", {}))

    def test_dry_run_prints_the_stripped_list_and_uploads_nothing(self):
        out = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "publish_hf.py")], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("dry run only", out.stdout); self.assertIn("gold_answer", out.stdout)

if __name__ == "__main__":
    unittest.main()
