"""Deployment with per-agent profiles and random generators."""

from dataclasses import dataclass

import numpy as np

from simulation.agent import Agent

from .config import SwarmConfig, resolve
from .environment import Environment
from .policies import FixedProfile


@dataclass
class Swarm:
    environment: Environment
    agents: list[Agent]
    config: SwarmConfig


def deploy_swarm(environment: Environment, config: SwarmConfig | None = None,
                 **options) -> Swarm:
    """Create a swarm in free space. Explicit positions take precedence over deployment mode."""
    config = resolve(config, SwarmConfig, options)
    rng = environment.deployment_rng
    bounds = environment.dimensions
    explicit = config.position is not None
    if explicit:
        origin = np.array(config.position, dtype=float)
        if not environment.contains(origin) or environment.occupied(origin):
            raise ValueError("Deployment position must be in bounds and outside obstacles")
    elif config.deployment == "center":
        origin = bounds / 2
    elif config.deployment == "edge_nest":
        origin = None
        for _ in range(10000):
            candidate = rng.uniform(0.1 * bounds, 0.9 * bounds)
            axis = int(rng.integers(2))
            candidate[axis] = bounds[axis] * (0.02 if rng.random() < 0.5 else 0.98)
            if not environment.occupied(candidate):
                origin = candidate
                break
        if origin is None:
            raise ValueError("Could not find a free edge nest")
    else:
        origin = None

    agents = []
    for _ in range(config.agent_count):
        for _ in range(10000):
            position = (rng.uniform(np.zeros(3), bounds) if origin is None else
                        origin + rng.uniform(-config.spread, config.spread, size=3))
            if environment.contains(position) and not environment.occupied(position):
                break
            if origin is not None and config.spread == 0:
                raise ValueError("Deployment position is obstructed; choose a different position")
        else:
            raise ValueError("Could not deploy all agents in free space")
        velocity = rng.uniform(-1, 1, 3)
        speed = np.linalg.norm(velocity)
        if speed > config.max_speed:
            velocity *= config.max_speed / speed
        agent_rng = np.random.default_rng(int(rng.integers(0, 2**63)))
        agent = Agent(position, velocity, config.max_speed, config.max_force,
                      FixedProfile(config.initial_profile).select(None, 0, 0), rng=agent_rng)
        agent.exploration_map = environment.exploration_map
        agents.append(agent)
    return Swarm(environment, agents, config)
