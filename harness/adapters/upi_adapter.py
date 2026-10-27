import os, sys
# NAVITAL_GYM_ROOT lets the harness run against another checkout (e.g. a feature worktree) before the env lands on main.
sys.path.insert(0, os.environ.get("NAVITAL_GYM_ROOT") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from navital_gym.envs.upi import grade
