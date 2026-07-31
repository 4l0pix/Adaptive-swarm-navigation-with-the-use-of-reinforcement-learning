"""High-level smoke tests for the thesis simulation artifact."""

from __future__ import annotations

import math
import os
import sys
import unittest
from pathlib import Path

import numpy as np


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SIMULATION_ROOT = REPOSITORY_ROOT / "simulation"
sys.path.insert(0, str(SIMULATION_ROOT))
os.environ["SWARM_BACKGROUND_SIMULATION"] = "0"

import app as simulation_app  # noqa: E402


class SimulationSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        np.random.seed(7)
        simulation_app.app.config.update(TESTING=True)
        cls.client = simulation_app.app.test_client()

    def setUp(self) -> None:
        np.random.seed(7)
        response = self.client.post("/init")
        self.assertEqual(response.status_code, 200)

    def test_health_contract(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok", "version": "0.5"})

    def test_command_center_renders(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Adaptive Swarm Navigation", response.data)
        self.assertIn(b"Swarm Command Center", response.data)

    def test_step_returns_complete_world_state(self) -> None:
        response = self.client.get("/step")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()

        self.assertEqual(len(payload["agents"]), 15)
        self.assertEqual(len(payload["obstacles"]), 45)
        self.assertEqual(payload["dimensions"]["width"], 500)
        self.assertEqual(payload["dimensions"]["height"], 500)
        self.assertEqual(payload["dimensions"]["depth"], 500)
        self.assertGreaterEqual(payload["stats"]["progress"], 0)
        self.assertEqual(
            sum(payload["stats"]["distribution"].values()),
            len(payload["agents"]),
        )

    def test_all_pathfinders_return_serializable_results(self) -> None:
        # Planning is intentionally restricted to discovered space. Model the
        # post-exploration phase before exercising the route-comparison API.
        with simulation_app.sim_state.lock:
            simulation_app.sim_state.exploration_map.explored_grid[:] = True
            simulation_app.sim_state.exploration_map.explored_grid_3d[:] = True

        response = self.client.post(
            "/pathfinding",
            json={
                "start": {"x": 40, "y": 40},
                "goal": {"x": 160, "y": 160},
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()

        for name in ("dijkstra", "astar", "safety_first", "balanced"):
            with self.subTest(algorithm=name):
                result = payload[name]
                self.assertGreater(result["nodes"], 0)
                self.assertTrue(result["path"])
                self.assertTrue(math.isfinite(result["cost"]))


if __name__ == "__main__":
    unittest.main()
