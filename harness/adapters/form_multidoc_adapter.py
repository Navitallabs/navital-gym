import os, sys
sys.path.insert(0, os.environ.get("NAVITAL_GYM_ROOT") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from navital_gym.envs.form_multidoc import grade
