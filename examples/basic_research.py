"""Build a rectangular world, customize obstacles, deploy agents, and run 100 ticks."""

from swarm_nav import (
    DynamicProfiles, Simulation, build_environment, deploy_swarm, generate_obstacles,
)


def main():
    environment = build_environment(width=600, height=400, depth=200, seed=42)
    obstacles = generate_obstacles(
        environment, count=20, width_range=(5, 12), height_range=(40, 180), margin=30,
    )
    environment.add_obstacles(obstacles)
    environment.update_obstacle(obstacles[0].id, height=150)
    swarm = deploy_swarm(environment, agent_count=15, position=(10, 200, 100))
    simulation = Simulation(
        environment, swarm,
        profile_policy=DynamicProfiles(low_threshold=0.2, high_threshold=0.7),
    )
    state = simulation.step(100)
    print(state["metrics"])


if __name__ == "__main__":
    main()
