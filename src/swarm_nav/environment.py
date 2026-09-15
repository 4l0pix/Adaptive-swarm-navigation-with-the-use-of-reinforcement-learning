"""World construction and explicit obstacle editing."""

from dataclasses import dataclass, replace

import numpy as np

from simulation.environment import Environment as ThesisEnvironment
from simulation.exploration_map import ExplorationMap

from .config import EnvironmentConfig, ObstacleConfig, positive, resolve, vector


@dataclass(frozen=True)
class Obstacle:
    """Vertical column: XY center, base Z, half-width, and vertical extent.

    The half-width convention follows the original avoidance force model.
    """

    id: str
    position: tuple[float, float, float]
    width: float
    height: float

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("obstacle id must be a nonempty string")
        object.__setattr__(self, "position", vector("position", self.position))
        positive("width", self.width)
        positive("height", self.height)
        if self.position[2] != 0:
            raise ValueError("The current obstacle model requires base z=0")

    def as_legacy(self):
        return {"position": np.array(self.position), "width": self.width, "height": self.height}


class Environment(ThesisEnvironment):
    """Bounded world with isolated RNG streams and a shared exploration map."""

    def __init__(self, config: EnvironmentConfig):
        super().__init__(config.width, config.height, config.depth)
        self.config = config
        obstacle_seed, deployment_seed = np.random.SeedSequence(config.seed).spawn(2)
        self.obstacle_rng = np.random.default_rng(obstacle_seed)
        self.deployment_rng = np.random.default_rng(deployment_seed)
        self._obstacles: tuple[Obstacle, ...] = ()
        self.exploration_map = ExplorationMap(
            self.width, self.height, [], depth=self.depth,
            resolution=config.map_resolution, resolution_3d=config.map_resolution_3d,
            threat_radius=config.threat_radius,
        )

    @property
    def obstacle_specs(self) -> tuple[Obstacle, ...]:
        return self._obstacles

    @property
    def dimensions(self):
        return np.array([self.width, self.height, self.depth])

    def _validate_obstacle(self, obstacle):
        if not isinstance(obstacle, Obstacle):
            raise TypeError("Use Obstacle instances")
        x, y, _ = obstacle.position
        if not (obstacle.width <= x <= self.width - obstacle.width and
                obstacle.width <= y <= self.height - obstacle.width and
                obstacle.height <= self.depth):
            raise ValueError(f"Obstacle {obstacle.id!r} extends outside the world")

    def _replace_obstacles(self, obstacles):
        obstacles = tuple(obstacles)
        for obstacle in obstacles:
            self._validate_obstacle(obstacle)
        ids = [o.id for o in obstacles]
        if len(set(ids)) != len(ids):
            raise ValueError("Obstacle ids must be unique")
        self._obstacles = obstacles
        self.obstacles = [o.as_legacy() for o in obstacles]
        # Retain map identity and discovered cells so deployed agents stay connected.
        self.exploration_map.obstacles = self.obstacles
        self.exploration_map.threat_map = self.exploration_map._compute_threat_map()

    def add_obstacles(self, obstacles):
        """Append validated obstacles; refresh threat values without erasing coverage."""
        self._replace_obstacles((*self._obstacles, *obstacles))

    def update_obstacle(self, obstacle_id: str, **attributes) -> Obstacle:
        """Replace position, width or height and immediately refresh the threat map."""
        if set(attributes) - {"position", "width", "height"}:
            raise ValueError("Editable attributes are position, width, and height")
        for index, obstacle in enumerate(self._obstacles):
            if obstacle.id == obstacle_id:
                updated = replace(obstacle, **attributes)
                candidates = list(self._obstacles)
                candidates[index] = updated
                self._replace_obstacles(candidates)
                return updated
        raise KeyError(obstacle_id)

    def remove_obstacle(self, obstacle_id: str):
        if not any(o.id == obstacle_id for o in self._obstacles):
            raise KeyError(obstacle_id)
        self._replace_obstacles(o for o in self._obstacles if o.id != obstacle_id)

    def contains(self, position):
        p = np.asarray(position)
        return bool(np.all(p >= 0) and np.all(p < self.dimensions))

    def occupied(self, position):
        p = np.asarray(position)
        return any(p[2] <= o.height and np.linalg.norm(p[:2] - o.position[:2]) <= o.width
                   for o in self._obstacles)


def build_environment(config: EnvironmentConfig | None = None, **options) -> Environment:
    """Create an empty world, e.g. build_environment(width=600, depth=200, seed=7)."""
    return Environment(resolve(config, EnvironmentConfig, options))


def generate_obstacles(environment: Environment, config: ObstacleConfig | None = None,
                       **options) -> tuple[Obstacle, ...]:
    """Generate a batch without adding it; call environment.add_obstacles(batch).

    Non-overlap uses conservative square XY footprints and includes existing
    obstacles. A failed placement raises rather than returning a partial batch.
    """
    config = resolve(config, ObstacleConfig, options)
    if config.count == 0:
        return ()
    max_width = config.width_range[1]
    if (2 * (config.margin + max_width) > min(environment.width, environment.height)
            or config.height_range[1] > environment.depth):
        raise ValueError("Obstacle dimensions and margin do not fit the environment")
    rng = environment.obstacle_rng
    result = []
    occupied_ids = {o.id for o in environment.obstacle_specs}
    next_id = 0
    for _ in range(config.max_attempts):
        width = float(rng.uniform(*config.width_range))
        height = float(rng.uniform(*config.height_range))
        position = (float(rng.uniform(config.margin + width, environment.width - config.margin - width)),
                    float(rng.uniform(config.margin + width, environment.height - config.margin - width)), 0.0)
        if config.placement == "random_non_overlapping" and any(
            abs(position[0] - other.position[0]) < width + other.width + config.clearance
            and abs(position[1] - other.position[1]) < width + other.width + config.clearance
            for other in (*environment.obstacle_specs, *result)
        ):
            continue
        while f"obstacle-{next_id}" in occupied_ids:
            next_id += 1
        result.append(Obstacle(f"obstacle-{next_id}", position, width, height))
        next_id += 1
        if len(result) == config.count:
            return tuple(result)
    raise ValueError(f"Could place only {len(result)}/{config.count} obstacles in {config.max_attempts} attempts")
