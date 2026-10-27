"""Identity of the code that grades: the git tree id of navital_gym/ (same in any repo holding the same files, and unchanged when only docs change).
Anyone can check a published `graded_with` with `git rev-parse <tag-or-sha>:navital_gym` (first 12 characters). '-dirty' = uncommitted edits in the package."""
import os, subprocess

def code_id():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # .../navital_gym
    repo = os.path.dirname(root)
    try:
        tree = subprocess.check_output(["git", "rev-parse", "HEAD:navital_gym"], cwd=repo, text=True, stderr=subprocess.DEVNULL).strip()[:12]
        dirty = subprocess.check_output(["git", "status", "--porcelain", "--", "navital_gym"], cwd=repo, text=True, stderr=subprocess.DEVNULL).strip()
        return tree + ("-dirty" if dirty else "")
    except Exception:
        return None
