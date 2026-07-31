# Profile Parameters & Performance Metrics

## 1. PROFILE PARAMETERS

### 1.1 Boids Behavior Weights (per profile)

| Parameter | Offensive | Neutral | Defensive | Description |
|-----------|-----------|---------|-----------|-------------|
| `cohesion` | 0.5 | 1.0 | 5.0 | Steer towards average position of neighbors |
| `alignment` | 1.2 | 1.0 | 3.0 | Steer towards average velocity of neighbors |
| `separation` | 2.0 | 1.2 | 0.1 | Steer away from neighbors too close |

### 1.2 Behavioral Parameters (per profile)

| Parameter | Offensive | Neutral | Defensive | Description |
|-----------|-----------|---------|-----------|-------------|
| `exploration_weight` | 1.5 | 1.0 | 0.05 | Priority for exploring unexplored areas |
| `obstacle_avoidance_weight` | 0.2 | 0.2 | 0.05 | Strength of obstacle avoidance force |
| `cohesion_radius` | 50 | 50 | 150 | Detection radius for cohesion behavior |
| `alignment_radius` | 50 | 50 | 100 | Detection radius for alignment behavior |
| `separation_radius` | 25 | 25 | 5 | Detection radius for separation behavior |

### 1.3 Fitness Function Weights (per profile)

| Parameter | Offensive | Neutral | Defensive | Description |
|-----------|-----------|---------|-----------|-------------|
| `fitness_w1` | 0.8 | 1.0 | 2.5 | Swarm dynamics weight (Aᵢ(t)) |
| `fitness_w2` | 2.0 | 1.0 | 0.3 | Opportunity value weight (ρ(qᵢ)) |
| `fitness_w3` | 1.0 | 0.5 | 0.2 | Distance penalty weight (dᵢ(t)) |

### 1.4 Penalty Coefficients (per profile)

| Parameter | Offensive | Neutral | Defensive | Description |
|-----------|-----------|---------|-----------|-------------|
| `penalty_pf` | 1.5 | 2.0 | 5.0 | Formation violation penalty (pf) |
| `penalty_pt` | 3.0 | 5.0 | 10.0 | Threat violation penalty (pt) |
| `penalty_ptau` | 2.0 | 3.0 | 4.0 | Time violation penalty (pτ) |

### 1.5 Pathfinding Speed Modifiers (per profile scenario)

| Scenario | Speed Modifier | Description |
|----------|---------------|-------------|
| Offensive | 1.0 | Full speed, minimal formation constraint |
| Neutral | 0.75 | Moderate speed reduction for coordination |
| Defensive | 0.5 | Significant speed reduction for tight formation |

---

## 2. SIMULATION CONSTANTS

### 2.1 Agent Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `MAX_SPEED` | 5.0 | Maximum agent velocity |
| `MAX_FORCE` | 1.0 | Maximum steering force |
| `NUM_AGENTS` | 15 | Number of agents in swarm |

### 2.2 Environment Dimensions

| Parameter | Value | Description |
|-----------|-------|-------------|
| `ENV_WIDTH` | 500 | Environment width |
| `ENV_HEIGHT` | 500 | Environment height |
| `ENV_DEPTH` | 500 | Environment depth (3D) |
| `BORDER_MARGIN` | 5 | Margin from environment edges |

### 2.3 Obstacle Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `NUM_OBSTACLES` | 45 | Number of obstacles |
| `OBSTACLE_MIN_HEIGHT` | 450 | Minimum obstacle height |
| `OBSTACLE_MAX_HEIGHT` | 500 | Maximum obstacle height |
| `OBSTACLE_WIDTH` | 5 | Width of rectangular obstacles |
| `OBSTACLE_AVOIDANCE_RADIUS` | 10 | Detection distance for obstacles |
| `OBSTACLE_AVOIDANCE_FORCE` | 0.2 | Strength of avoidance force |

### 2.4 Exploration Map Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `MAP_RESOLUTION` | 50 | Grid resolution (50×50) |
| `EXPLORATION_RADIUS` | 7 | Radius marked as explored around agent |
| `THREAT_DETECTION_RADIUS` | 35 | Distance for calculating threat intensity |
| `UNEXPLORED_AVOIDANCE_WEIGHT` | 1 | Weight for steering towards unexplored areas |

### 2.5 Dynamic Profile Switching Thresholds

| Parameter | Value | Description |
|-----------|-------|-------------|
| `HIGH_THREAT_THRESHOLD` | 0.7 | Switch to Defensive if threat > this |
| `LOW_THREAT_THRESHOLD` | 0.2 | Switch to Offensive if threat < this |
| `THREAT_RADIUS_CHECK` | 15 | Radius around agent to check for threat |

---

## 3. PERFORMANCE METRICS

### 3.1 Agent-Level Fitness Function

**Formula:**
```
Fᵢ(t) = w₁·Aᵢ(t) + w₂·ρ(qᵢ) - w₃·dᵢ(t) - Pᵢ(t)
```

| Component | Symbol | Description |
|-----------|--------|-------------|
| Swarm Adherence | Aᵢ(t) | How well agent follows ideal boids behavior (0-1) |
| Opportunity Value | ρ(qᵢ) | Inverse of threat level: 1/(1 + threat) |
| Target Distance | dᵢ(t) | Normalized Euclidean distance to assigned target |
| Penalty Term | Pᵢ(t) | pf·Iform + pt·Ithreat + pτ·Itime |

### 3.2 Violation Indicators

| Indicator | Description |
|-----------|-------------|
| Iform | Formation violation (1 if isolated, 0 otherwise) |
| Ithreat | Threat violation (1 if in high threat without defensive profile) |
| Itime | Time violation (1 if task exceeds time limit) |

### 3.3 Swarm-Level Metrics

| Metric | Description |
|--------|-------------|
| `avg_fitness` | Mean fitness across all agents |
| `min_fitness` | Minimum individual fitness |
| `max_fitness` | Maximum individual fitness |
| `fitness_std` | Standard deviation of fitness values |
| `total_violations` | Aggregated formation/threat/time violations |
| `swarm_size` | Number of agents |

### 3.4 Exploration Metrics

| Metric | Description |
|--------|-------------|
| `exploration_percentage` | Percentage of grid cells explored (0-100%) |
| `threat_map` | 2D grid of threat intensities |
| `optimal_position` | Position with lowest threat in explored areas |

### 3.5 Pathfinding Experiment Metrics

| Metric | Description |
|--------|-------------|
| `success_rate` | Percentage of successful pathfinding runs |
| `path_length` | Number of nodes in computed path |
| `path_cost` | Total traversal cost considering threat + formation |
| `euclidean_distance` | Straight-line distance between start and goal |

### 3.6 Pathfinding Cost Calculations

| Algorithm | Cost Formula |
|-----------|--------------|
| **Dijkstra** | `base_cost × formation_multiplier + threat × 5.0` |
| **A*** | Same as Dijkstra + Euclidean heuristic |
| **Safety-First** | `0.1 × formation_multiplier + threat × 50.0` |
| **Balanced** | `(0.5 × distance + 0.5 × threat × 10) × formation_multiplier` |

---

## 4. PROFILE DISTRIBUTION TRACKING

| Metric | Description |
|--------|-------------|
| `profile_counts` | Count of agents per profile type (Offensive/Neutral/Defensive) |
| `profile_colors` | Visual color coding: Green (Offensive), Blue (Neutral), Red (Defensive) |

---

## 5. REINFORCEMENT LEARNING HYPERPARAMETERS & METRICS

### 5.1 Hyperparameters (HP‑RL)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `hp_bins` | 5 | Number of discrete bins per boids weight (cohesion/alignment/separation) |
| `hp_multipliers` | [0.0, 0.5, 1.0, 1.5, 2.0] | Discrete multipliers applied to profile defaults |
| `hp_alpha` | 0.05 | Q‑learning learning rate (tabular HP) |
| `hp_gamma` | 0.95 | Discount factor |
| `hp_epsilon` | 0.2 | Exploration rate during HP training (ε‑greedy) |
| `train_hp_episodes` | 300 | Default number of HP training episodes (see `experiments.py`) |
| `eval_hp_episodes` | 20 | Default number of HP evaluation episodes |

### 5.2 Reward / Objective (HP‑RL)

- Reward combines: threat penalty, distance penalty, per‑step cost, and a goal bonus.
- Default coefficients used in training/eval:
  - Threat penalty multiplier: 5.0
  - Distance penalty multiplier: 0.01
  - Step penalty: 0.05
  - Goal bonus: +200.0

### 5.3 Output Metrics

| Metric | Description |
|--------|-------------|
| `avg_agent_rewards` | Average episodic reward per agent (evaluation episodes) |
| `avg_swarm_reward` | Sum or mean of agent rewards across swarm |
| `per_profile.avg_multipliers` | Average learned multipliers (ms, ma, mc) per profile |
| `per_profile.avg_weights` | Average absolute boids weights (profile_default × avg_multiplier) per profile |
| `policy_table` | Sample of tabular policy entries (state → multipliers → Q‑value) |

### 5.4 Interpretation

- Optimal policy balances **minimal threat exposure** and **shorter path** (goal-focused). Lower average threat and higher swarm reward indicate safer, efficient behaviors.
- Use `per_profile.avg_weights` chart (UI) to pick recommended boids weights per profile for deployment.

---
