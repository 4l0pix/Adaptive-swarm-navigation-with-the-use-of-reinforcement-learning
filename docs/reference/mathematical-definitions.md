# Mathematical Definitions

---

## 0. Core Concepts

### 0.1 What is Safety?

**Definition:** Safety $S$ is the inverse measure of threat exposure at a given position.

$$S(x,y) = \frac{1}{1 + T(x,y)}$$

**Properties:**
- $S \in (0, 1]$
- $S = 1$ when $T = 0$ (no threat → maximum safety)
- $S \to 0$ as $T \to \infty$ (high threat → minimum safety)

**Interpretation:** Safety quantifies how "protected" an agent is from nearby obstacles. A cell with $S = 0.5$ means the agent is exposed to threat intensity $T = 1.0$ (single obstacle at center).

---

### 0.2 Threat-to-Exposure Ratio

**Definition:** The threat-to-exposure ratio $\eta$ measures accumulated danger relative to distance traveled.

$$\eta = \frac{\sum_{i=1}^{n} T(x_i, y_i)}{n}$$

Where $(x_i, y_i)$ are the $n$ cells along the path.

**Alternatively, as path integral:**

$$\eta_{path} = \frac{\int_{\gamma} T(s) \, ds}{L(\gamma)}$$

Where:
- $\gamma$ = path from start to goal
- $L(\gamma)$ = path length
- $T(s)$ = threat at position $s$ along path

**Calculation in code:**
```
Total Threat Exposure = Σ T(cell) for each cell in path
Exposure Ratio = Total Threat Exposure / Path Length
```

---

### 0.3 Safety-First Algorithm

**Objective:** Find path $\gamma^*$ that minimizes threat exposure:

$$\gamma^* = \arg\min_{\gamma} \sum_{(x,y) \in \gamma} C_{Safety}(x,y)$$

**Cost Function:**

$$C_{Safety}(x,y) = \underbrace{0.1 \cdot M_f(x,y)}_{\text{minimal distance cost}} + \underbrace{50.0 \cdot T(x,y)}_{\text{heavy threat penalty}}$$

**Comparison of Weight Ratios:**

| Algorithm | Distance Weight | Threat Weight | Ratio (Threat:Distance) |
|-----------|----------------|---------------|------------------------|
| Dijkstra | 1.0 | 5.0 | 5:1 |
| Safety-First | 0.1 | 50.0 | **500:1** |

**Algorithm (Modified Dijkstra):**

```
Input: Start S, Goal G, Threat Map T
Output: Safest path γ*

1. Initialize: dist[S] = 0, dist[v] = ∞ ∀v ≠ S
2. Priority Queue: Q = {(0, S)}

3. While Q ≠ ∅:
   a. (cost, u) = extract_min(Q)
   b. If u = G: return reconstruct_path()
   c. For each neighbor v of u:
      new_cost = dist[u] + C_Safety(v)
      If new_cost < dist[v]:
         dist[v] = new_cost
         prev[v] = u
         Q.push((new_cost, v))

4. Return path by backtracking from G using prev[]
```

**Why it works:**
- The 500:1 threat-to-distance ratio means the algorithm will traverse ~500 extra cells to avoid a single high-threat cell
- Result: Longer paths that circumnavigate obstacles entirely

---

## 1. Threat Model

### Threat Intensity at Position (x, y)

$$T(x,y) = \sum_{k=1}^{N_{obs}} h_k(x,y)$$

Where heat contribution from obstacle $k$:

$$h_k(x,y) = \begin{cases} 1 - \frac{d_k}{R_T} & \text{if } d_k < R_T \\ 0 & \text{otherwise} \end{cases}$$

| Symbol | Definition | Value |
|--------|------------|-------|
| $d_k$ | Euclidean distance to obstacle $k$: $\sqrt{(x-x_k)^2 + (y-y_k)^2}$ | - |
| $R_T$ | Threat detection radius | 35 |
| $N_{obs}$ | Number of obstacles | 45 |

---

## 2. Safety

### Definition

$$\text{Safety}(x,y) = \frac{1}{1 + T(x,y)}$$

| Threat $T$ | Safety |
|------------|--------|
| 0 | 1.0 (maximum) |
| 1 | 0.5 |
| $\infty$ | 0 |

---

## 3. Pathfinding Cost Functions

### 3.1 Formation Speed Multiplier

$$M_f(x,y) = \frac{1}{S_p}$$

Where $S_p$ is the profile speed modifier:

| Profile | $S_p$ | $M_f$ |
|---------|-------|-------|
| Offensive | 1.0 | 1.0 |
| Neutral | 0.75 | 1.33 |
| Defensive | 0.5 | 2.0 |

### 3.2 Dijkstra Cost

$$C_{Dijkstra}(x,y) = 1.0 \cdot M_f(x,y) + 5.0 \cdot T(x,y)$$

### 3.3 A* Cost

$$C_{A^*}(x,y) = C_{Dijkstra}(x,y)$$

$$f(n) = g(n) + h(n)$$

Where $h(n) = \sqrt{(x-x_g)^2 + (y-y_g)^2}$ (Euclidean heuristic)

### 3.4 Safety-First Cost

$$C_{Safety}(x,y) = 0.1 \cdot M_f(x,y) + 50.0 \cdot T(x,y)$$

### 3.5 Balanced Cost

$$C_{Balanced}(x,y) = M_f(x,y) \cdot \left( 0.5 \cdot \frac{d_g}{d_{max}} + 0.5 \cdot 10 \cdot T(x,y) \right)$$

Where:
- $d_g$ = distance to goal
- $d_{max} = \sqrt{W^2 + H^2}$ (diagonal of environment)

---

## 4. Fitness Function

### Agent-Level Fitness

$$F_i(t) = w_1 \cdot A_i(t) + w_2 \cdot \rho(q_i) - w_3 \cdot d_i(t) - P_i(t)$$

### Components

| Term | Formula | Range |
|------|---------|-------|
| Swarm Adherence | $A_i(t) = \frac{\vec{v}_i \cdot \vec{v}_{ideal} + 1}{2}$ | [0, 1] |
| Opportunity Value | $\rho(q_i) = \frac{1}{1 + T(q_i)}$ | (0, 1] |
| Target Distance | $d_i(t) = \frac{\|\vec{p}_i - \vec{p}_{target}\|}{d_{max}}$ | [0, 1] |

### Penalty Term

$$P_i(t) = p_f \cdot I_{form} + p_t \cdot I_{threat} + p_\tau \cdot I_{time}$$

### Violation Indicators

$$I_{form} = \begin{cases} 1 & \text{if } |\{j : \|\vec{p}_i - \vec{p}_j\| \leq 75\}| = 0 \\ 0 & \text{otherwise} \end{cases}$$

$$I_{threat} = \begin{cases} 1 & \text{if } T(q_i) > 0.6 \land \text{profile} \neq \text{Defensive} \\ 0 & \text{otherwise} \end{cases}$$

$$I_{time} = \begin{cases} 1 & \text{if } t - t_{start} > \tau_{limit} \\ 0 & \text{otherwise} \end{cases}$$

---

## 5. Profile-Specific Weights

### Fitness Weights

| Profile | $w_1$ | $w_2$ | $w_3$ |
|---------|-------|-------|-------|
| Offensive | 0.8 | 2.0 | 1.0 |
| Neutral | 1.0 | 1.0 | 0.5 |
| Defensive | 2.5 | 0.3 | 0.2 |

### Penalty Coefficients

| Profile | $p_f$ | $p_t$ | $p_\tau$ |
|---------|-------|-------|----------|
| Offensive | 1.5 | 3.0 | 2.0 |
| Neutral | 2.0 | 5.0 | 3.0 |
| Defensive | 5.0 | 10.0 | 4.0 |

---

## 6. Dynamic Profile Switching

$$\text{Profile}(t) = \begin{cases} \text{Defensive} & \text{if } \bar{T}_r > \theta_{high} \\ \text{Offensive} & \text{if } \bar{T}_r < \theta_{low} \\ \text{Neutral} & \text{otherwise} \end{cases}$$

Where:
- $\bar{T}_r$ = average threat within radius $r$ of agent
- $\theta_{high} = 0.7$
- $\theta_{low} = 0.2$
- $r = 15$ units

---

## 7. Boids Rules

### Cohesion

$$\vec{F}_{coh} = w_{coh} \cdot \text{seek}\left( \frac{1}{n} \sum_{j \in N_r} \vec{p}_j \right)$$

### Alignment

$$\vec{F}_{align} = w_{align} \cdot \frac{\frac{1}{n} \sum_{j \in N_r} \vec{v}_j}{|\frac{1}{n} \sum_{j \in N_r} \vec{v}_j|} \cdot v_{max}$$

### Separation

$$\vec{F}_{sep} = w_{sep} \cdot \sum_{j \in N_r} \frac{\vec{p}_i - \vec{p}_j}{|\vec{p}_i - \vec{p}_j|}$$

Where $N_r = \{j : 0 < \|\vec{p}_i - \vec{p}_j\| < r\}$

### Profile Weights

| Profile | $w_{coh}$ | $w_{align}$ | $w_{sep}$ |
|---------|-----------|-------------|-----------|
| Offensive | 0.5 | 1.2 | 2.0 |
| Neutral | 1.0 | 1.0 | 1.2 |
| Defensive | 5.0 | 3.0 | 0.1 |

---

## 8. Reinforcement Learning (Hyperparameter Tuning)

### Objective
Find a policy $\pi$ that maps discretized states to Boids hyperparameter multipliers (cohesion, alignment, separation) so that agents minimize accumulated threat exposure while also minimizing path length to the goal.

### State and Action
- State $s_t$: discretized tuple \((g_x,g_y,g_z,\tau, p)\) where $g_\cdot$ are grid indices, $\tau$ is threat level bin, and $p$ is profile index.
- Action $a_t$: discrete index encoding multipliers $(m_s,m_a,m_c)\in M^3$ where $M=\{0.0,0.5,1.0,1.5,2.0\}$.

### Reward (per step)
A scalar reward designed to (1) penalize threat exposure and (2) penalize long trajectories, with a positive goal bonus:

$$R_t = -\lambda_T \cdot T(s_t) - \lambda_d \cdot d( p_t, g ) - c_{step} + B\cdot\mathbf{1}_{\{\text{at goal}\}}$$

Typical defaults used in experiments: $\lambda_T=5.0$, $\lambda_d=0.01$, $c_{step}=0.05$, $B=200.0$.

### Learning rule (Q‑learning)
Tabular Q‑learning is used for HP actions (per‑agent):

$$Q(s,a) \leftarrow Q(s,a) + \alpha\left(r + \gamma \max_{a'} Q(s',a') - Q(s,a)\right)$$

Where $\alpha$ is the learning rate and $\gamma$ the discount factor.

### Optimal policy interpretation
- Policy entries with high Q-values correspond to multiplier triples that reduce threat exposure and shorten expected remaining path length under the learned reward trade-off.
- For deployment, convert learned multipliers to absolute boids weights via: $w^{*}_{coh}=w^{default}_{coh}\times m_s$ (and similarly for alignment/separation).

### Evaluation metrics (RL)
- Agent average episodic reward: $\overline{R}_i$ (higher is better)
- Swarm average episodic reward: $\overline{R}_{swarm} = \frac{1}{N}\sum_i \overline{R}_i$
- Per‑profile average multipliers and absolute weights (used for the grouped bar chart)

---
