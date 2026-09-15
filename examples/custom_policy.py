"""Plug a new profile policy into the same environment and Boids dynamics."""

from dataclasses import dataclass

from swarm_nav import FixedProfile, build_simulation


@dataclass(frozen=True)
class CautiousPolicy:
    threshold: float = 0.4

    def select(self, agent, threat, step):
        name = "defensive" if threat > self.threshold else "neutral"
        return FixedProfile(name).select(agent, threat, step)


if __name__ == "__main__":
    simulation = build_simulation(profile_policy=CautiousPolicy())
    print(simulation.step(100)["metrics"])
