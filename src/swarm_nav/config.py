"""Validated, immutable inputs for a research run."""

from dataclasses import dataclass, field
from math import isfinite


def positive(name, value, *, zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    invalid = value < 0 if zero else value <= 0
    if invalid:
        raise ValueError(f"{name} must be {'nonnegative' if zero else 'positive'}")


def integer(name, value, *, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


def vector(name, values, *, length=3):
    result = tuple(values)
    if len(result) != length or any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v)
        for v in result
    ):
        raise ValueError(f"{name} must contain {length} finite numbers")
    return result


@dataclass(frozen=True)
class EnvironmentConfig:
    width: float = 500
    height: float = 500
    depth: float = 500
    seed: int = 42
    map_resolution: int = 50
    map_resolution_3d: int = 25
    threat_radius: float = 35

    def __post_init__(self):
        for name in ("width", "height", "depth", "threat_radius"):
            positive(name, getattr(self, name))
        for name in ("map_resolution", "map_resolution_3d"):
            integer(name, getattr(self, name), minimum=1)
        integer("seed", self.seed)


@dataclass(frozen=True)
class ObstacleConfig:
    count: int = 45
    width_range: tuple[float, float] = (5, 5)
    height_range: tuple[float, float] = (450, 500)
    placement: str = "random_non_overlapping"
    margin: float = 10
    clearance: float = 0
    max_attempts: int = 10000

    def __post_init__(self):
        integer("count", self.count)
        integer("max_attempts", self.max_attempts, minimum=1)
        for name in ("margin", "clearance"):
            positive(name, getattr(self, name), zero=True)
        for name in ("width_range", "height_range"):
            interval = vector(name, getattr(self, name), length=2)
            if not 0 < interval[0] <= interval[1]:
                raise ValueError(f"{name} must be an ordered positive interval")
            object.__setattr__(self, name, interval)
        if self.placement not in ("random", "random_non_overlapping"):
            raise ValueError("placement must be random or random_non_overlapping")


@dataclass(frozen=True)
class SwarmConfig:
    agent_count: int = 15
    deployment: str = "edge_nest"
    position: tuple[float, float, float] | None = None
    spread: float = 0
    initial_profile: str = "neutral"
    max_speed: float = 2
    max_force: float = 0.03

    def __post_init__(self):
        integer("agent_count", self.agent_count, minimum=1)
        positive("spread", self.spread, zero=True)
        positive("max_speed", self.max_speed)
        positive("max_force", self.max_force)
        if self.position is not None:
            object.__setattr__(self, "position", vector("position", self.position))
        if self.deployment not in ("edge_nest", "center", "random"):
            raise ValueError("deployment must be edge_nest, center, or random")
        if self.initial_profile not in ("offensive", "neutral", "defensive"):
            raise ValueError("unknown initial_profile")


@dataclass(frozen=True)
class SimulationConfig:
    seed: int = 42
    environment: EnvironmentConfig = field(default_factory=EnvironmentConfig)
    obstacles: ObstacleConfig = field(default_factory=ObstacleConfig)
    swarm: SwarmConfig = field(default_factory=SwarmConfig)
    tick_seconds: float = 0.05
    exploration_radius: float = 7
    avoidance_radius: float = 10

    def __post_init__(self):
        integer("seed", self.seed)
        for name in ("tick_seconds", "exploration_radius", "avoidance_radius"):
            positive(name, getattr(self, name))
        for name, cls in (("environment", EnvironmentConfig), ("obstacles", ObstacleConfig),
                          ("swarm", SwarmConfig)):
            if not isinstance(getattr(self, name), cls):
                raise TypeError(f"{name} must be a {cls.__name__}")


def resolve(config, cls, kwargs):
    if config is not None:
        if kwargs:
            raise TypeError("Pass either a configuration object or keyword options")
        if not isinstance(config, cls):
            raise TypeError(f"config must be a {cls.__name__}")
        return config
    return cls(**kwargs)
