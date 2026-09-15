"""Explicit simulation stepping and replaceable swarm dynamics."""

from copy import deepcopy
from dataclasses import asdict, dataclass, is_dataclass, replace
from importlib.metadata import version
import json
from pathlib import Path
import platform
from typing import Protocol

import numpy as np

from simulation.profiles import Profile
from simulation.utils import apply_boids_rules

from .config import SimulationConfig, integer, positive
from .environment import Environment, build_environment, generate_obstacles
from .policies import DynamicProfiles, ProfilePolicy
from .swarm import Swarm, deploy_swarm


class Dynamics(Protocol):
    def advance(self, environment: Environment, swarm: Swarm, *, exploration_radius: float,
                avoidance_radius: float) -> None:
        """Advance motion by one discrete tick; do not advance the clock or coverage."""
        ...


@dataclass(frozen=True)
class BoidsDynamics:
    """Original per-tick Boids forces with an enforced world boundary.

    Velocity is world units per tick. tick_seconds labels the simulation clock;
    changing it does not rescale the original discrete integration equations.
    """

    def advance(self, environment, swarm, *, exploration_radius, avoidance_radius):
        apply_boids_rules(swarm.agents)
        for agent in swarm.agents:
            profile = agent.profile
            agent.apply_force(environment.apply_borders(agent))
            agent.apply_force(environment.apply_obstacle_avoidance(
                agent, avoidance_radius, profile.obstacle_avoidance_weight))
            agent.apply_force(agent.explore_behavior(profile.exploration_weight))
        upper = np.nextafter(environment.dimensions, np.zeros(3))
        for agent in swarm.agents:
            agent.update()
            crossed = (agent.position < 0) | (agent.position > upper)
            agent.position = np.clip(agent.position, 0, upper)
            agent.velocity[crossed] *= -1


def component_description(component):
    description = {"implementation": f"{type(component).__module__}.{type(component).__qualname__}"}
    if is_dataclass(component):
        description["parameters"] = asdict(component)
    else:
        description["parameters"] = None
    return description


class Simulation:
    """One run with explicit ownership. No server, global RNG, or background thread."""

    def __init__(self, environment: Environment, swarm: Swarm, *,
                 profile_policy: ProfilePolicy | None = None, dynamics: Dynamics | None = None,
                 tick_seconds=0.05, exploration_radius=7, avoidance_radius=10):
        if swarm.environment is not environment:
            raise ValueError("Swarm must be deployed in this environment")
        for name, value in (("tick_seconds", tick_seconds), ("exploration_radius", exploration_radius),
                            ("avoidance_radius", avoidance_radius)):
            positive(name, value)
        self.environment = environment
        self.swarm = swarm
        # Stateful learning policies belong to this run, even if supplied as a shared template.
        self.profile_policy = deepcopy(profile_policy if profile_policy is not None else DynamicProfiles())
        self.dynamics = deepcopy(dynamics if dynamics is not None else BoidsDynamics())
        self.tick_seconds = tick_seconds
        self.exploration_radius = exploration_radius
        self.avoidance_radius = avoidance_radius
        self.step_count = 0
        self._initial_state = self.snapshot()

    @property
    def time(self):
        return self.step_count * self.tick_seconds

    def step(self, steps: int = 1) -> dict:
        """Advance exactly steps ticks, then return a detached JSON-safe snapshot."""
        integer("steps", steps, minimum=1)
        for _ in range(steps):
            for agent in self.swarm.agents:
                threat = agent.assess_threat_level(getattr(self.profile_policy, "sensing_radius", 15))
                profile = self.profile_policy.select(agent, threat, self.step_count)
                if not isinstance(profile, Profile):
                    raise TypeError("ProfilePolicy.select must return a Profile")
                agent.profile = deepcopy(profile)
                # The legacy Agent caches these weights; refresh when profiles change.
                agent.boids_cohesion = profile.cohesion
                agent.boids_alignment = profile.alignment
                agent.boids_separation = profile.separation
            self.dynamics.advance(self.environment, self.swarm,
                                  exploration_radius=self.exploration_radius,
                                  avoidance_radius=self.avoidance_radius)
            for agent in self.swarm.agents:
                mapping = self.environment.exploration_map
                mapping.mark_explored(agent.position, self.exploration_radius)
                mapping.mark_explored_3d(agent.position, self.exploration_radius)
            self.step_count += 1
        return self.snapshot()

    def snapshot(self, *, include_maps: bool = False) -> dict:
        """Read without advancing or calculating fitness (which mutates legacy counters)."""
        distribution = {}
        agents = []
        for index, agent in enumerate(self.swarm.agents):
            profile = agent.profile.name
            distribution[profile] = distribution.get(profile, 0) + 1
            agents.append({"id": index, "position": agent.position.tolist(),
                           "velocity": agent.velocity.tolist(), "profile": profile,
                           "threat_at_last_decision": float(agent.current_threat_level)})
        mapping = self.environment.exploration_map
        result = {"step": self.step_count, "time": self.time, "agents": agents,
                  "dimensions": self.environment.dimensions.tolist(),
                  "obstacles": [asdict(o) for o in self.environment.obstacle_specs],
                  "metrics": {"coverage_2d_percent": float(mapping.get_exploration_percentage()),
                              "coverage_3d_percent": float(mapping.get_3d_exploration_percentage()),
                              "profile_distribution": distribution}}
        if include_maps:
            result["maps"] = {"explored_2d": mapping.explored_grid.tolist(),
                              "explored_3d": mapping.explored_grid_3d.tolist(),
                              "threat": mapping.threat_map.tolist()}
        return result

    def manifest(self, *, code_revision: str | None = None, metadata: dict | None = None) -> dict:
        """Describe this run. Custom policy state and mid-run edits need caller metadata."""
        return {"schema_version": 1, "package_version": version("swarm-nav"),
                "python_version": platform.python_version(), "numpy_version": np.__version__,
                "code_revision": code_revision, "environment": asdict(self.environment.config),
                "swarm": asdict(self.swarm.config), "initial_state": deepcopy(self._initial_state),
                "profile_policy": component_description(self.profile_policy),
                "dynamics": component_description(self.dynamics),
                "tick_seconds": self.tick_seconds, "exploration_radius": self.exploration_radius,
                "avoidance_radius": self.avoidance_radius,
                "completed_steps": self.step_count, "metadata": deepcopy(metadata or {})}

    def save(self, directory, *, code_revision=None, metadata=None) -> Path:
        """Write a manifest and final state into a new directory; never overwrite a run."""
        manifest = json.dumps(self.manifest(code_revision=code_revision, metadata=metadata),
                              indent=2, allow_nan=False)
        state = json.dumps(self.snapshot(include_maps=True), indent=2, allow_nan=False)
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=False)
        (directory / "manifest.json").write_text(manifest + "\n", encoding="utf-8")
        (directory / "state.json").write_text(state + "\n", encoding="utf-8")
        return directory


def build_simulation(config: SimulationConfig | None = None, *,
                     profile_policy: ProfilePolicy | None = None,
                     dynamics: Dynamics | None = None) -> Simulation:
    """Compose a seeded run. SimulationConfig.seed overrides environment.seed."""
    config = config if config is not None else SimulationConfig()
    if not isinstance(config, SimulationConfig):
        raise TypeError("config must be a SimulationConfig")
    environment = build_environment(replace(config.environment, seed=config.seed))
    environment.add_obstacles(generate_obstacles(environment, config.obstacles))
    swarm = deploy_swarm(environment, config.swarm)
    return Simulation(environment, swarm, profile_policy=profile_policy, dynamics=dynamics,
                      tick_seconds=config.tick_seconds, exploration_radius=config.exploration_radius,
                      avoidance_radius=config.avoidance_radius)
