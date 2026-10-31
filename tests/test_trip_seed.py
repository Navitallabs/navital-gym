"""T-111 (Codex): load_env(seed=N) builds a seeded world, so the grader must judge the plan against THAT world. Written before the fix: red on 02582e3."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from navital_gym.envs.trip import load_env
from navital_gym.envs.trip.solver import Solver
from navital_gym.envs.trip.world import TripWorld

class Seed(unittest.TestCase):
    def test_a_plan_with_a_train_that_does_not_exist_in_the_seeded_world_does_not_solve(self):
        e0, e1 = load_env(), load_env(seed=1)
        t = e0.tasks["IN-TRIP-002"]; plan = Solver(t).solve()
        self.assertTrue(e0.grade(t, plan).solved)
        e1.reset("IN-TRIP-002")
        absent = [l["id"] for d in plan["days"] for l in d["legs"] if l["mode"] == "rail" and TripWorld(e1.task, 1).train(l["id"]) is None]
        self.assertTrue(absent, "the probe needs a train that seed 1 does not have")
        self.assertFalse(e1.grade(e1.task, plan).solved, "seed-1 world has no train %s" % absent)

    def test_the_solver_solves_in_its_own_seed(self):
        e1 = load_env(seed=1); t = e1.tasks["IN-TRIP-002"]
        plan = Solver(t, seed=1).solve() if "seed" in Solver.__init__.__code__.co_varnames else None
        self.assertIsNotNone(plan, "Solver must accept a seed")
        self.assertTrue(e1.grade(t, plan).solved)

    def test_seed_zero_is_unchanged(self):
        e0 = load_env(); t = e0.tasks["IN-TRIP-002"]
        self.assertTrue(e0.grade(t, Solver(t).solve()).solved)

if __name__ == "__main__":
    unittest.main()
