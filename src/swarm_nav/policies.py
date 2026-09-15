"""Replaceable formation control independent of the simulator and UI."""

from copy import deepcopy
from dataclasses import dataclass
from typing import Protocol

from simulation.agent import Agent
from simulation.profiles import Profile, PROFILES

from .config import positive

_PROFILE_TEMPLATES = deepcopy(PROFILES)


class ProfilePolicy(Protocol):
    def select(self, agent: Agent, threat: float, step: int) -> Profile:
        """Return movement/fitness parameters for this agent and simulation step."""
        ...


@dataclass(frozen=True)
class DynamicProfiles:
    low_threshold: float = 0.2
    high_threshold: float = 0.7
    sensing_radius: float = 15

    def __post_init__(self):
        positive("low_threshold", self.low_threshold, zero=True)
        positive("high_threshold", self.high_threshold)
        positive("sensing_radius", self.sensing_radius, zero=True)
        if self.low_threshold >= self.high_threshold:
            raise ValueError("low_threshold must be below high_threshold")

    def select(self, agent, threat, step):
        name = ("offensive" if threat < self.low_threshold else
                "defensive" if threat > self.high_threshold else "neutral")
        return deepcopy(_PROFILE_TEMPLATES[name])


@dataclass(frozen=True)
class FixedProfile:
    name: str = "neutral"

    def __post_init__(self):
        if self.name not in _PROFILE_TEMPLATES:
            raise ValueError(f"Unknown profile: {self.name}")

    def select(self, agent, threat, step):
        return deepcopy(_PROFILE_TEMPLATES[self.name])
