"""Adapters for the thesis planners, which return XY routes through discovered space."""

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from simulation.pathfinding import PathFinder

from .config import vector
from .environment import Environment


@dataclass(frozen=True)
class PathResult:
    planner: str
    path: tuple[tuple[float, float], ...]
    objective_cost: float | None

    @property
    def success(self):
        return bool(self.path)

    @property
    def node_count(self):
        return len(self.path)

    @property
    def geometric_length(self):
        return float(sum(np.linalg.norm(np.subtract(b, a)) for a, b in zip(self.path, self.path[1:])))


class Planner(Protocol):
    def plan(self, environment: Environment, start, goal) -> PathResult: ...


@dataclass(frozen=True)
class ThesisPlanner:
    """Original planner behavior; objective costs differ between algorithms.

    These are XY paths with any-altitude exploration gating, not collision-checked
    3D trajectories. Speed modifiers apply only to the local planner instance.
    """

    name: str = "balanced"
    profile: str = "dynamic"

    def __post_init__(self):
        if self.name not in ("dijkstra", "astar", "safety_first", "balanced"):
            raise ValueError("Unknown planner")
        if self.profile not in ("dynamic", "offensive", "neutral", "defensive"):
            raise ValueError("Unknown planner profile")

    def plan(self, environment, start, goal):
        start = vector("start", start, length=2)
        goal = vector("goal", goal, length=2)
        for point in (start, goal):
            if not (0 <= point[0] < environment.width and 0 <= point[1] < environment.height):
                raise ValueError("Planning endpoints must be inside the XY world bounds")
        finder = PathFinder(environment.exploration_map)
        if self.profile != "dynamic":
            speed = finder.PROFILE_SPEED_MODIFIERS[self.profile]
            finder.PROFILE_SPEED_MODIFIERS = dict.fromkeys(finder.PROFILE_SPEED_MODIFIERS, speed)
        if not all(finder.is_position_explored_3d(*finder.world_to_grid(p)) for p in (start, goal)):
            return PathResult(self.name, (), None)
        path, cost = getattr(finder, self.name)(np.array(start), np.array(goal))
        return PathResult(self.name, tuple(tuple(float(v) for v in p) for p in path),
                          float(cost) if np.isfinite(cost) else None)
