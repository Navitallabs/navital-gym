"""Adapter: GST Desk grader -> harness contract grade(task_dict, submission)."""
import sys
import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..") if "adapters" in __file__ else os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from navital_gym.envs import gst
_env = gst.make_env([])
def grade(task, submission):
    return _env.contract_grade(task, submission)
