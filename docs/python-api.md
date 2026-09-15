# Python research API

`swarm_nav` exposes the environment, obstacle generation, deployment, simulation,
profile control, and planning as importable Python components. Importing it does
not start Flask or a background loop. Install the library from this repository:

```bash
python -m pip install -e .
```

Use `python -m pip install -e '.[web]'` to include the existing browser sandbox.
Python 3.11 or newer is required.

## Build a world one function at a time

```python
from swarm_nav import (
    DynamicProfiles, Simulation, build_environment, deploy_swarm, generate_obstacles,
)

world = build_environment(width=600, height=400, depth=200, seed=42)
obstacles = generate_obstacles(
    world,
    count=20,
    width_range=(5, 12),
    height_range=(40, 180),
    placement="random_non_overlapping",
    margin=30,
    clearance=5,
)
world.add_obstacles(obstacles)

world.update_obstacle(obstacles[0].id, height=150, width=8)

swarm = deploy_swarm(
    world,
    agent_count=15,
    position=(10, 200, 100),
    initial_profile="neutral",
    max_speed=2.0,
    max_force=0.03,
)
simulation = Simulation(world, swarm, profile_policy=DynamicProfiles())
state = simulation.step(100)
print(state["metrics"])
```

`generate_obstacles` returns immutable `Obstacle` objects and advances only the
world's obstacle random generator. It does not add the obstacles. Add each batch
before generating the next so collision checks and generated ids include it.
An impossible placement raises `ValueError` without adding a partial batch.

`world.add_obstacles`, `world.update_obstacle`, and `world.remove_obstacle` update
the threat field while retaining discovered cells and references held by agents.
Attribute edits validate bounds; they do not enforce non-overlap or relocate
existing agents. Make edits before deployment or check the consequences of a
mid-run change in your experiment.

### Place an obstacle explicitly

```python
from swarm_nav import Obstacle

world.add_obstacles([
    Obstacle(id="tower", position=(300, 200, 0), width=10, height=180),
])
world.update_obstacle("tower", position=(350, 200, 0), height=160)
world.remove_obstacle("tower")
```

The current model is a vertical column rooted at `z=0`. Position gives its XY
center; `width` is the horizontal avoidance radius (half-width), and `height`
is its vertical extent. Non-overlap generation uses conservative square XY
footprints. Threat retains the thesis model: it depends on XY distance to obstacle
centers, not height or width. A change to width/height affects avoidance and
deployment checks, while relocating an obstacle also changes the threat field.
World units are abstract simulation units.

### Deployment modes

- `deployment="edge_nest"`: choose a free position near an XY boundary.
- `deployment="center"`: start at the world center; fail if it is obstructed.
- `deployment="random"`: sample each agent independently in free space.
- `position=(x, y, z)`: use an explicit origin, overriding the deployment mode.
- `spread=10`: sample offsets in a cube of half-side 10 around that origin.

Positions must be inside the world and outside obstacles. The default `spread=0`
releases agents from one shared origin, matching the thesis deployment concept;
agent-agent separation at deployment is not enforced. A custom deployment can
construct a `Swarm` from an environment, list of original `Agent` objects, and
`SwarmConfig`; each agent must reference that environment's exploration map.

## Configure a complete run

Every builder accepts either a configuration object or keyword arguments.
Configuration objects are immutable and reject invalid bounds, dimensions,
counts, and ranges.

```python
from swarm_nav import (
    EnvironmentConfig, ObstacleConfig, SimulationConfig, SwarmConfig, build_simulation,
)

config = SimulationConfig(
    seed=42,
    environment=EnvironmentConfig(width=600, height=400, depth=200),
    obstacles=ObstacleConfig(count=20, height_range=(40, 180)),
    swarm=SwarmConfig(agent_count=30, position=(5, 200, 100)),
)
simulation = build_simulation(config)
simulation.step(100)
```

`SimulationConfig.seed` is the run seed and overrides the nested environment
seed. With the individual builders, `EnvironmentConfig.seed` is authoritative.
Obstacle generation and deployment have independent random streams. Each agent
also owns a random generator available as `agent.rng` to learning policies.

Construct a fresh environment and swarm for each independent run. A `Simulation`
uses the supplied world/swarm directly, while copying the supplied policy and
dynamics so their internal state belongs to that run. Sharing a world or swarm
between simulations deliberately shares its mutable state; it is not a supported
way to create independent repetitions.

## Dynamic profiles and custom research policies

```python
from swarm_nav import DynamicProfiles, FixedProfile, build_simulation

adaptive = build_simulation(profile_policy=DynamicProfiles(
    low_threshold=0.2, high_threshold=0.7, sensing_radius=15,
))
control = build_simulation(profile_policy=FixedProfile("neutral"))
```

Dynamic profiles use offensive below the low threshold, defensive above the high
threshold, and neutral otherwise. The policy reads local threat at the beginning
of each tick. The engine applies the selected profile's actual Boids weights to
each agent, including after a transition.

A new research policy implements one method:

```python
from dataclasses import dataclass
from swarm_nav import FixedProfile, build_simulation

@dataclass(frozen=True)
class CautiousPolicy:
    threshold: float = 0.4

    def select(self, agent, threat, step):
        name = "defensive" if threat > self.threshold else "neutral"
        return FixedProfile(name).select(agent, threat, step)

simulation = build_simulation(profile_policy=CautiousPolicy())
```

Return a `Profile` with custom cohesion, alignment, separation, exploration, and
avoidance settings to introduce a new behavior. A learning policy may update its
own state inside `select`; use `agent.rng` for random decisions. The engine
copies the returned profile and synchronizes its movement weights every tick.
Policies needing a different observation model can inspect the agent/map or use
a custom dynamics implementation. The policy is called once per agent per tick;
it is not a joint-action or Gymnasium/MARL training interface.

For a new motion model, implement `Dynamics.advance(environment, swarm, *,
exploration_radius, avoidance_radius)` and pass `dynamics=YourDynamics()` to
`Simulation` or `build_simulation`. The engine owns the step counter and map
updates; the dynamics implementation owns motion. Such objects must be copyable
with `copy.deepcopy`.

## Step, inspect, and save

```python
state = simulation.step()                 # Exactly one tick
state = simulation.step(100)              # Exactly 100 more ticks
state = simulation.snapshot()             # Read only
state = simulation.snapshot(include_maps=True)

simulation.save(
    "artifacts/research-run-42",
    code_revision="your-git-commit-sha",
    metadata={"study": "profile-comparison"},
)
```

`save` creates a new directory containing `manifest.json` and `state.json`. It
refuses to overwrite an existing run. The manifest records environment and swarm
configuration, actual initial agents and obstacles, policy/dynamics descriptions,
software versions, step count, and supplied metadata. Provide the code revision
explicitly, along with any custom policy state, training checkpoints, or mid-run
commands needed to explain your experiment. These artifacts describe a run;
automatic checkpoint restoration and event replay are not implemented.

Snapshots contain detached values, so editing a snapshot cannot move an agent.
`threat_at_last_decision` is the threat measured before the last movement, not a
fresh sensor reading at the returned position. Coverage is reported separately
for the 2D planning map and the 3D discovery grid. The latter has shape `(x,y,z)`;
the 2D grids use `(y,x)` indexing.

## Use the existing path planners

```python
from swarm_nav import ThesisPlanner

result = ThesisPlanner("balanced", profile="dynamic").plan(world, (10, 20), (400, 300))
print(result.success, result.node_count, result.geometric_length, result.objective_cost)
```

Available names are `dijkstra`, `astar`, `safety_first`, and `balanced`. The profile
can be `dynamic`, `offensive`, `neutral`, or `defensive`. Each call creates its own
planner settings, so comparisons do not modify another experiment.

These preserve the original XY search algorithms, including their heuristics and
iteration limits. They gate cells using exploration at any altitude; they do not
produce collision-checked 3D flight paths or guarantee optimality for every cost
model. Both endpoints must be in bounds and discovered. An unavailable route has
an empty path and `objective_cost=None`. Each algorithm uses its own objective;
cost values are not a shared evaluation metric. Use geometric length and a common
external risk evaluator for comparisons. Length is measured along returned grid
centers, while node count is the number of waypoints.

## Baseline and compatibility

Version 0.6 provides a new research execution baseline. The browser sandbox keeps
its existing v0.5 workflow. The library reuses its Boids, avoidance, exploration,
profile definitions, and planners, with these explicit differences:

- Reproducible random streams per world, deployment, and agent.
- Configurable rectangular worlds and per-axis 3D grid cell sizes.
- Bounded obstacle generation and validated deployment into free space.
- Profile transitions refresh the cached movement weights.
- The default dynamics clamp and reflect agents at world boundaries.
- Explicit step control; no background simulation or automatic HTTP updates.

Velocity remains world units per tick. `tick_seconds` advances the reported clock
(default 0.05 seconds); it does not rescale the legacy integration equations.
Changing this value alone is not a physical timestep experiment. Avoidance is a
soft force and cannot guarantee collision-free movement.

Reconstruct a run from the same configuration, seed, components, builder call
order, and dependency versions to reproduce it. The included tests check matching
trajectories even when unrelated runs are interleaved. They do not claim bitwise
agreement across different NumPy versions or reproduction of the archived v0.5
experimental batch.
