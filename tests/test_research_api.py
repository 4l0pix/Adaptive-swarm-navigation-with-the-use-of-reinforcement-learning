"""Behavioral contracts for independent, repeatable research runs."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

from swarm_nav import (
    DynamicProfiles, EnvironmentConfig, FixedProfile, Obstacle, ObstacleConfig,
    Simulation, SimulationConfig, SwarmConfig, ThesisPlanner,
    build_environment, build_simulation, deploy_swarm, generate_obstacles,
)


class ResearchAPITests(unittest.TestCase):
    def config(self, seed=7):
        return SimulationConfig(
            seed=seed,
            environment=EnvironmentConfig(width=160, height=100, depth=60,
                                          map_resolution=16, map_resolution_3d=10),
            obstacles=ObstacleConfig(count=4, width_range=(2, 4), height_range=(20, 50)),
            swarm=SwarmConfig(agent_count=4, position=(3, 50, 30)),
        )

    def test_repeatability_with_interleaved_runs_and_global_random_noise(self):
        first = build_simulation(self.config())
        second = build_simulation(self.config())
        unrelated = build_simulation(self.config(123))
        for _ in range(12):
            first.step()
            unrelated.step(2)
            np.random.random(30)
            second.step()
        self.assertEqual(first.snapshot(include_maps=True), second.snapshot(include_maps=True))
        self.assertNotEqual(first.snapshot(), unrelated.snapshot())

    def test_default_ten_tick_reference_baseline(self):
        # v0.6 reference scenario: seed 42, 15 agents, 45 columns, 500-cube.
        sim = build_simulation()
        state = sim.step(10)
        np.testing.assert_allclose(state["agents"][0]["position"],
                                   [494.186042619847, 59.363571892212, 287.888616806899],
                                   rtol=0, atol=1e-8)
        np.testing.assert_allclose(state["agents"][0]["velocity"],
                                   [0.482645377173, -1.166094359812, -0.044888877924],
                                   rtol=0, atol=1e-8)
        self.assertEqual(state["metrics"]["profile_distribution"], {"Offensive": 15})
        self.assertEqual(int(sim.environment.exploration_map.explored_grid.sum()), 7)
        self.assertEqual(int(sim.environment.exploration_map.explored_grid_3d.sum()), 3)

    def test_library_import_does_not_load_flask_or_start_threads(self):
        code = "import sys, threading; import swarm_nav; assert 'flask' not in sys.modules; assert len(threading.enumerate()) == 1"
        subprocess.run([sys.executable, "-c", code], check=True)

    def test_random_obstacle_attributes_and_non_overlap(self):
        world = build_environment(width=160, height=100, depth=60, seed=9)
        batch = generate_obstacles(world, count=15, width_range=(2, 4), height_range=(10, 60), clearance=2)
        self.assertEqual(world.obstacle_specs, ())
        world.add_obstacles(batch)
        for i, obstacle in enumerate(batch):
            self.assertTrue(2 <= obstacle.width <= 4)
            self.assertTrue(10 <= obstacle.height <= 60)
            for other in batch[i + 1:]:
                separation = obstacle.width + other.width + 2
                self.assertTrue(abs(obstacle.position[0] - other.position[0]) >= separation or
                                abs(obstacle.position[1] - other.position[1]) >= separation)
        next_batch = generate_obstacles(world, count=2, width_range=(2, 3), height_range=(10, 20))
        world.add_obstacles(next_batch)
        self.assertEqual(len({o.id for o in world.obstacle_specs}), 17)

    def test_obstacle_edit_refreshes_map_without_losing_coverage(self):
        world = build_environment(width=100, height=80, depth=60, map_resolution=20)
        world.add_obstacles([Obstacle("tower", (20, 20, 0), 4, 30)])
        swarm = deploy_swarm(world, position=(5, 5, 50))
        mapping = world.exploration_map
        mapping.mark_explored((5, 5, 50), 7)
        explored = mapping.explored_grid.copy()
        threat = mapping.threat_map.copy()
        world.update_obstacle("tower", position=(70, 60, 0), width=6, height=45)
        self.assertIs(swarm.agents[0].exploration_map, mapping)
        np.testing.assert_array_equal(mapping.explored_grid, explored)
        self.assertFalse(np.array_equal(mapping.threat_map, threat))
        with self.assertRaises(ValueError):
            world.update_obstacle("tower", height=100)
        self.assertEqual(world.obstacle_specs[0].height, 45)
        world.remove_obstacle("tower")
        self.assertFalse(mapping.threat_map.any())

    def test_impossible_obstacles_do_not_partially_mutate_world(self):
        world = build_environment(width=30, height=30, depth=30)
        with self.assertRaises(ValueError):
            generate_obstacles(world, count=4, width_range=(10, 10), height_range=(20, 20),
                               margin=0, max_attempts=10)
        self.assertEqual(world.obstacle_specs, ())

    def test_non_cubic_map_coordinates_and_planning_gate(self):
        world = build_environment(width=200, height=100, depth=40, map_resolution_3d=10)
        mapping = world.exploration_map
        mapping.mark_explored_3d((190, 95, 38), 1)
        self.assertTrue(mapping.explored_grid_3d[9, 9, 9])
        self.assertTrue(mapping.is_explored_3d(190, 95, 38))
        self.assertAlmostEqual(float(mapping.get_3d_exploration_percentage()), 0.1)
        planner = ThesisPlanner("dijkstra")
        self.assertTrue(planner.plan(world, (190, 95), (190, 95)).success)
        self.assertFalse(planner.plan(world, (10, 10), (190, 95)).success)

    def test_deploy_rejects_obstacle_and_out_of_bounds(self):
        world = build_environment(width=100, height=100, depth=60)
        world.add_obstacles([Obstacle("tower", (50, 50, 0), 10, 60)])
        for position in ((50, 50, 20), (-1, 20, 20), (100, 20, 20)):
            with self.subTest(position=position), self.assertRaises(ValueError):
                deploy_swarm(world, position=position)
        swarm = deploy_swarm(world, deployment="random", agent_count=20)
        self.assertTrue(all(world.contains(a.position) and not world.occupied(a.position) for a in swarm.agents))

    def test_dynamic_profiles_update_actual_boids_weights(self):
        sim = build_simulation(self.config(), profile_policy=DynamicProfiles())
        for threat, expected in ((0.1, "Offensive"), (0.5, "Neutral"), (0.9, "Defensive")):
            sim.environment.exploration_map.threat_map[:] = threat
            sim.step()
            for agent in sim.swarm.agents:
                self.assertEqual(agent.profile.name, expected)
                self.assertEqual(agent.boids_cohesion, agent.profile.cohesion)
                self.assertEqual(agent.boids_alignment, agent.profile.alignment)
                self.assertEqual(agent.boids_separation, agent.profile.separation)

    def test_custom_policy_is_owned_by_run_and_can_change_decisions(self):
        class AlternatingPolicy:
            calls = 0

            def select(self, agent, threat, step):
                self.calls += 1
                return FixedProfile("offensive" if step % 2 == 0 else "defensive").select(agent, threat, step)

        policy = AlternatingPolicy()
        sim = build_simulation(self.config(), profile_policy=policy)
        sim.step()
        self.assertEqual(sim.swarm.agents[0].profile.name, "Offensive")
        sim.step()
        self.assertEqual(sim.swarm.agents[0].profile.name, "Defensive")
        self.assertEqual(policy.calls, 0)
        self.assertEqual(sim.profile_policy.calls, 8)

    def test_dynamics_extension_and_snapshot_purity(self):
        class NoMotion:
            def advance(self, environment, swarm, **options):
                pass

        sim = build_simulation(self.config(), dynamics=NoMotion())
        positions = [a.position.copy() for a in sim.swarm.agents]
        snapshot = sim.step(3)
        self.assertEqual(snapshot["step"], 3)
        self.assertAlmostEqual(snapshot["time"], 0.15)
        for agent, initial in zip(sim.swarm.agents, positions):
            np.testing.assert_array_equal(agent.position, initial)
        snapshot["agents"][0]["position"][0] = -100
        self.assertEqual(sim.step_count, 3)
        self.assertGreaterEqual(sim.snapshot()["agents"][0]["position"][0], 0)
        json.dumps(sim.snapshot(include_maps=True), allow_nan=False)

    def test_swarm_profiles_are_not_shared(self):
        one = build_simulation(self.config())
        two = build_simulation(self.config())
        one.swarm.agents[0].profile.cohesion = 999
        self.assertNotEqual(one.swarm.agents[1].profile.cohesion, 999)
        self.assertNotEqual(two.swarm.agents[0].profile.cohesion, 999)

    def test_seeded_deployment_independent_of_obstacle_rng_consumption(self):
        one = build_environment(seed=71)
        two = build_environment(seed=71)
        generate_obstacles(one, count=20)
        a = deploy_swarm(one)
        b = deploy_swarm(two)
        np.testing.assert_array_equal(a.agents[0].position, b.agents[0].position)
        np.testing.assert_array_equal(a.agents[0].velocity, b.agents[0].velocity)

    def test_manifest_and_save_never_overwrite(self):
        sim = build_simulation(self.config())
        initial = sim.snapshot()
        sim.step(2)
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "run-7"
            sim.save(folder, code_revision="test-revision", metadata={"purpose": "regression"})
            manifest = json.loads((folder / "manifest.json").read_text())
            self.assertEqual(manifest["environment"]["seed"], 7)
            self.assertEqual(manifest["code_revision"], "test-revision")
            self.assertEqual(manifest["initial_state"]["agents"], initial["agents"])
            self.assertEqual(json.loads((folder / "state.json").read_text())["step"], 2)
            with self.assertRaises(FileExistsError):
                sim.save(folder)

    def test_invalid_configs_are_rejected(self):
        cases = [lambda: EnvironmentConfig(depth=-1), lambda: EnvironmentConfig(seed=True),
                 lambda: EnvironmentConfig(width=float("nan")), lambda: ObstacleConfig(count=1.5),
                 lambda: ObstacleConfig(width_range=(4, 2)), lambda: SwarmConfig(agent_count=0),
                 lambda: DynamicProfiles(low_threshold=0.8, high_threshold=0.2),
                 lambda: SimulationConfig(tick_seconds=0)]
        for case in cases:
            with self.assertRaises(ValueError):
                case()
        with self.assertRaises(TypeError):
            build_environment(EnvironmentConfig(), width=10)
        sim = build_simulation(self.config())
        with self.assertRaises(ValueError):
            sim.step(0)
        with self.assertRaises(ValueError):
            Simulation(build_environment(), sim.swarm)

    def test_all_planners_and_profile_isolation(self):
        world = build_environment(width=100, height=80, depth=60, map_resolution=10)
        world.exploration_map.explored_grid_3d[:] = True
        for name in ("dijkstra", "astar", "safety_first", "balanced"):
            result = ThesisPlanner(name).plan(world, (10, 10), (60, 50))
            self.assertTrue(result.success)
            self.assertGreater(result.node_count, 1)
            self.assertGreater(result.geometric_length, 0)
            self.assertIsNotNone(result.objective_cost)
        before = ThesisPlanner("dijkstra").plan(world, (10, 10), (60, 50))
        ThesisPlanner("dijkstra", "defensive").plan(world, (10, 10), (60, 50))
        self.assertEqual(before, ThesisPlanner("dijkstra").plan(world, (10, 10), (60, 50)))


if __name__ == "__main__":
    unittest.main()
