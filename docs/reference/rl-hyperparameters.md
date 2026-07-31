# Reinforcement Learning — Hyperparameter Tuning (HP‑RL)

Purpose
- Document the tabular, model‑free RL module that learns Boids hyperparameters (cohesion, alignment, separation) per agent.
- Explain objective, state/action, reward, training/evaluation, API output and how to interpret the per‑profile recommended weights.

Scope
- This covers the HP‑RL (discretized multipliers) implemented in the 0.5 folder (tabular Q‑learning).

---

## 1 — Objective
Learn a policy \(\pi(s)\) that outputs multipliers for boids weights (ws, wa, wc) that minimize threat exposure and at the same time produce short paths to the goal. The ultimate product is a per‑profile recommendation for the three boids weights.

## 2 — Where to find the code
- Agent HP‑RL helpers: `agent.py` (methods: `get_hp_state`, `choose_hp_action`, `apply_hp_action`, `update_q_hp`, `get_hp_optimal_policy_table`)
- Training / evaluation: `experiments.py` (`train_hp_agents`, `run_hp_evaluation`)
- API wiring: `app.py` (automatically runs HP‑RL after experiments; GET `/hp_rl_results`)
- Frontend visualization: `static/js/main.js` (chart + modal), `templates/index.html`

## 3 — Design (concise)
- Algorithm: Tabular Q‑learning (per agent)
- State: discretized 5‑tuple (grid_x, grid_y, grid_z, threat_level, profile_index)
- Action: discrete index mapping to multiplier triple (ms, ma, mc) where multipliers ∈ {0.0, 0.5, 1.0, 1.5, 2.0}
- Reward: negative threat exposure + negative distance penalty + per‑step penalty + large goal bonus
- Output: per‑agent policy table (state → best multiplier triple), and aggregated per‑profile average multipliers and absolute weights

## 4 — Default hyperparameters
- hp_bins = 5 (per‑dimension discretization)
- hp_multipliers = [0.0, 0.5, 1.0, 1.5, 2.0]
- hp_alpha = 0.05 (learning rate)
- hp_gamma = 0.95 (discount factor)
- hp_epsilon = 0.2 (exploration during training)
- train_hp_episodes = 300 (default training episodes)
- eval_hp_episodes = 20 (evaluation episodes)
- Reward coefficients: threat: 5.0, distance: 0.01, step: 0.05, goal bonus: 200.0

## 5 — How training & evaluation work
- Training (`train_hp_agents`) runs a fast internal simulation loop where agents choose HP actions (ε‑greedy), apply the resulting multipliers to boids forces, step the simulation, then update Q‑values with per‑step reward.
- Evaluation (`run_hp_evaluation`) runs several episodes using greedy HP selection and records average agent rewards and per‑profile aggregated multipliers.
- After experiments finish, HP‑RL is trained automatically and results are stored at `sim_state.hp_rl_results`.

## 6 — API & UI
- GET `/hp_rl_results` — returns JSON with `avg_agent_rewards`, `avg_swarm_reward`, `policies` (per agent), and `per_profile` (aggregated multipliers + avg_weights).
- UI: Results modal → select `Boids HP RL (ws, wa, wc)` to view grouped bar chart of absolute weights per profile (Cohesion/Alignment/Separation).

Example API response (abridged):
```
{
  "avg_agent_rewards": {"0": -12.3, "1": -9.4},
  "avg_swarm_reward": -85.7,
  "per_profile": {
    "Defensive": {"avg_multipliers": [1.2,0.9,0.8], "avg_weights": [6.0,2.7,0.08], "count": 5},
    "Neutral": { ... },
    "Offensive": { ... }
  },
  "policies": { "0": {"0_0_0_1_1": {"multipliers": [1,0.5,1], "q_value": 12.3}, ...}, ...}
}
```

## 7 — Interpreting results
- `per_profile.avg_weights` are the recommended absolute boids weights per profile (use these to configure swarm behavior).
- Higher cohesion in Defensive suggests tighter formations; higher separation in Offensive suggests better dispersion.
- Combine `avg_agent_rewards` and `per_profile.avg_weights` to validate whether learned multipliers improved safety and path efficiency.

## 8 — Tuning suggestions
- Increase threat penalty to bias toward safer routes.
- Increase goal bonus to bias toward shorter paths.
- Increase `train_hp_episodes` for more stable policies (longer training).
- Consider reducing `hp_bins` (coarser actions) to speed up learning, then refine.

## 9 — Next steps (optional)
- Replace tabular HP policy with a continuous actor (policy network) for fine‑grained control.
- Add UI controls to launch/stop HP training and to export `per_profile` CSV.
- Add unit tests for HP training/eval functions.

---

For questions or to request a neural‑policy upgrade, open an issue or ask in the repository.