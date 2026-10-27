"""Private held-out sets (~/.navital-gym/heldout/<env>.jsonl, never committed) must not appear anywhere in the tracked tree. Skipped where the sets do not exist
(a clean clone, CI); on the machine that holds them it fails if any held-out task id or prompt has leaked into a tracked file."""
import glob, json, os, subprocess, unittest
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
HELD = os.path.expanduser(os.environ.get("NAVITAL_HELDOUT_DIR", "~/.navital-gym/heldout"))

class HeldoutNotInRepo(unittest.TestCase):
    def test_no_heldout_id_or_prompt_in_a_tracked_file(self):
        files = sorted(glob.glob(os.path.join(HELD, "*.jsonl")))
        if not files: self.skipTest("no private held-out sets on this machine")
        needles = []
        for f in files:
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        row = json.loads(line); needles += [row["id"], row["prompt"]]
        tracked = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout.decode().split("\0")
        hits = []
        for rel in filter(None, tracked):
            p = os.path.join(ROOT, rel)
            if not os.path.isfile(p) or rel.endswith((".png", ".ipynb_checkpoints")): continue
            try:
                with open(p, encoding="utf-8") as fh: text = fh.read()
            except (UnicodeDecodeError, OSError): continue
            hits += [f"{rel}: {n[:30]!r}" for n in needles if n in text]
        self.assertEqual(hits, [], "private held-out content found in the repo")

if __name__ == "__main__":
    unittest.main()
