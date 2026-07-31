import numpy as np

class Agent:
    def __init__(self, position, velocity, max_speed=2.0, max_force=0.03, profile=None):
        self.position = np.array(position, dtype=float)
        self.velocity = np.array(velocity, dtype=float)
        self.acceleration = np.zeros(3)
        self.max_speed = max_speed
        self.max_force = max_force
        self.exploration_map = None  # Will be set by environment
        self.profile = profile  # Individual agent profile
        self.current_threat_level = 0.0  # Current threat at agent's position
        
        # Fitness function components
        self.assigned_target = None  # Target position for task completion
        self.task_start_time = 0.0   # When task was assigned
        self.task_time_limit = 300.0 # Time limit for task completion (seconds)
        self.formation_violations = 0
        self.threat_violations = 0
        self.time_violations = 0

        # Per-agent boids hyperparameters (override shared Profile without mutating it)
        self.boids_cohesion = self.profile.cohesion if self.profile else 1.0
        self.boids_alignment = self.profile.alignment if self.profile else 1.0
        self.boids_separation = self.profile.separation if self.profile else 1.0

        # Tabular hyperparameter-RL (discretized multipliers per-profile)
        # multipliers are applied relative to the agent.profile defaults
        self.hp_bins = 5
        self.hp_multipliers = [0.0, 0.5, 1.0, 1.5, 2.0]
        self.hp_action_count = self.hp_bins ** 3  # choices for (ws, wa, wc)
        self.q_table_hp = {}     # { state_str: np.array(self.hp_action_count) }
        self.prev_state_hp = None
        self.prev_action_hp = None
        self.total_reward_hp = 0.0
        self.hp_alpha = 0.05
        self.hp_gamma = 0.95
        self.hp_epsilon = 0.2  # exploration rate during HP training

    def apply_force(self, force):
        self.acceleration += force

    def update(self):
        self.velocity += self.acceleration
        speed = np.linalg.norm(self.velocity)
        if speed > self.max_speed:
            self.velocity = (self.velocity / speed) * self.max_speed
        self.position += self.velocity
        self.acceleration = np.zeros(3)

    def cohesion(self, agents, radius=50):
        """Steer towards average position of neighbors"""
        center = np.zeros(3)
        count = 0
        for agent in agents:
            dist = np.linalg.norm(self.position - agent.position)
            if 0 < dist < radius:
                center += agent.position
                count += 1
        if count > 0:
            center /= count
            return self.seek(center)
        return np.zeros(3)

    def alignment(self, agents, radius=50):
        """Steer towards average velocity of neighbors"""
        avg_vel = np.zeros(3)
        count = 0
        for agent in agents:
            dist = np.linalg.norm(self.position - agent.position)
            if 0 < dist < radius:
                avg_vel += agent.velocity
                count += 1
        if count > 0:
            avg_vel /= count
            # Fix division by zero bug
            avg_vel_mag = np.linalg.norm(avg_vel)
            if avg_vel_mag > 0:
                avg_vel = (avg_vel / avg_vel_mag) * self.max_speed
                steer = avg_vel - self.velocity
                if np.linalg.norm(steer) > self.max_force:
                    steer = (steer / np.linalg.norm(steer)) * self.max_force
                return steer
            else:
                return np.zeros(3)
        return np.zeros(3)

    def separation(self, agents, radius=25):
        """Steer away from neighbors that are too close"""
        steer = np.zeros(3)
        count = 0
        for agent in agents:
            dist = np.linalg.norm(self.position - agent.position)
            if 0 < dist < radius:
                diff = self.position - agent.position
                diff /= dist  # Weight by distance
                steer += diff
                count += 1
        if count > 0:
            steer /= count
            if np.linalg.norm(steer) > 0:
                steer = (steer / np.linalg.norm(steer)) * self.max_speed
                steer -= self.velocity
                if np.linalg.norm(steer) > self.max_force:
                    steer = (steer / np.linalg.norm(steer)) * self.max_force
        return steer

    def seek(self, target):
        """Steer towards a target position"""
        desired = target - self.position
        dist = np.linalg.norm(desired)
        if dist > 0:
            desired = (desired / dist) * self.max_speed
            steer = desired - self.velocity
            if np.linalg.norm(steer) > self.max_force:
                steer = (steer / np.linalg.norm(steer)) * self.max_force
            return steer
        return np.zeros(3)

    def explore_behavior(self, weight=0.3):
        """Steer towards unexplored areas using shared map"""
        if self.exploration_map is None:
            return np.zeros(3)

        # Get direction to unexplored area
        direction_2d = self.exploration_map.get_unexplored_direction(self.position)

        if np.linalg.norm(direction_2d) > 0:
            # Convert to 3D (keep current z velocity)
            target_3d = self.position.copy()
            target_3d[:2] += direction_2d * 20  # Look ahead 20 units

            return self.seek(target_3d) * weight

        return np.zeros(3)
    
    def assess_threat_level(self):
        """Assess current threat level at agent's position"""
        if self.exploration_map is None:
            return 0.0
            
        # Convert position to grid coordinates
        from utils import THREAT_RADIUS_CHECK
        grid_x = int(self.position[0] / self.exploration_map.cell_size_x)
        grid_y = int(self.position[1] / self.exploration_map.cell_size_y)
        
        # Check average threat in surrounding area
        threat_sum = 0.0
        threat_count = 0
        radius_cells = int(THREAT_RADIUS_CHECK / min(self.exploration_map.cell_size_x, 
                                                   self.exploration_map.cell_size_y))
        
        for i in range(max(0, grid_x - radius_cells),
                      min(self.exploration_map.resolution, grid_x + radius_cells + 1)):
            for j in range(max(0, grid_y - radius_cells),
                          min(self.exploration_map.resolution, grid_y + radius_cells + 1)):
                threat_sum += self.exploration_map.threat_map[j, i]
                threat_count += 1
        
        self.current_threat_level = threat_sum / threat_count if threat_count > 0 else 0.0
        return self.current_threat_level
    
    def update_profile_based_on_threat(self, profiles):
        """Dynamically update profile based on current threat level"""
        from utils import HIGH_THREAT_THRESHOLD, LOW_THREAT_THRESHOLD
        
        current_threat = self.assess_threat_level()
        
        if current_threat > HIGH_THREAT_THRESHOLD:
            self.profile = profiles['DEFENSIVE']
        elif current_threat < LOW_THREAT_THRESHOLD:
            self.profile = profiles['OFFENSIVE']
        else:
            self.profile = profiles['NEUTRAL']
            
        return self.profile
    
    def calculate_fitness(self, agents, current_time):
        """Calculate fitness using the comprehensive fitness function
        Fi(t) = w1*Ai(t) + w2*ρ(qi) - w3*di(t) - Pi(t)
        Uses profile-specific weights and penalty coefficients
        """
        if not self.profile:
            return 0.0  # No fitness if no profile assigned
        
        # Swarm dynamics adherence
        A_i = self.calculate_swarm_adherence(agents)
        
        # Opportunity value (inverse of threat)
        rho_qi = self.calculate_opportunity_value()
        
        # Distance to assigned target
        d_i = self.calculate_target_distance()
        
        # Penalty term
        P_i = self.calculate_penalties(agents, current_time)
        
        # Calculate fitness using profile-specific weights
        fitness = (self.profile.fitness_w1 * A_i + 
                  self.profile.fitness_w2 * rho_qi - 
                  self.profile.fitness_w3 * d_i - 
                  P_i)
        
        return fitness
    
    def calculate_swarm_adherence(self, agents):
        """Calculate adherence to swarm dynamics (Ai(t))
        Based on how well agent follows alignment, cohesion, separation
        """
        if len(agents) <= 1:
            return 1.0  # Perfect adherence if alone
        
        # Get ideal forces for current swarm state
        ideal_cohesion = self.cohesion(agents, radius=50)
        ideal_alignment = self.alignment(agents, radius=50) 
        ideal_separation = self.separation(agents, radius=25)
        
        # Calculate how well current velocity aligns with ideal behavior
        ideal_velocity = ideal_cohesion + ideal_alignment + ideal_separation
        
        if np.linalg.norm(ideal_velocity) == 0:
            return 1.0  # Perfect if no ideal direction
        
        # Normalize and compare with current velocity direction
        if np.linalg.norm(self.velocity) == 0:
            return 0.0  # Poor adherence if stationary
        
        ideal_dir = ideal_velocity / np.linalg.norm(ideal_velocity)
        current_dir = self.velocity / np.linalg.norm(self.velocity)
        
        # Dot product gives alignment (-1 to 1, normalize to 0 to 1)
        adherence = (np.dot(ideal_dir, current_dir) + 1.0) / 2.0
        
        return adherence
    
    def calculate_opportunity_value(self):
        """Calculate opportunity value ρ(qi) - inverse of threat intensity"""
        if self.exploration_map is None:
            return 0.5  # Neutral opportunity if no map
        
        # Get current threat level (0 to 1+)
        current_threat = self.assess_threat_level()
        
        # Opportunity is inverse of threat, normalized
        # High threat = low opportunity, low threat = high opportunity
        opportunity = 1.0 / (1.0 + current_threat)
        
        return opportunity
    
    def calculate_target_distance(self):
        """Calculate Euclidean distance di(t) to assigned target"""
        if self.assigned_target is None:
            return 0.0  # No penalty if no target assigned
        
        distance = np.linalg.norm(self.position - self.assigned_target)
        
        # Normalize distance by environment size for consistency
        from utils import ENV_WIDTH, ENV_HEIGHT
        max_distance = np.sqrt(ENV_WIDTH**2 + ENV_HEIGHT**2)
        normalized_distance = distance / max_distance
        
        return normalized_distance
    
    def calculate_penalties(self, agents, current_time):
        """Calculate penalty term Pi(t) = pf*Iform + pt*Ithreat + ptau*Itime
        Uses profile-specific penalty coefficients"""
        if not self.profile:
            return 0.0  # No penalties if no profile assigned
        
        # Formation violation indicator
        I_form = self.check_formation_violation(agents)
        
        # Threat zone violation indicator  
        I_threat = self.check_threat_violation()
        
        # Time limit violation indicator
        I_time = self.check_time_violation(current_time)
        
        # Calculate total penalty using profile-specific coefficients
        penalty = (self.profile.penalty_pf * I_form + 
                  self.profile.penalty_pt * I_threat + 
                  self.profile.penalty_ptau * I_time)
        
        return penalty
    
    def check_formation_violation(self, agents):
        """Check if agent violates formation requirements (Iform)"""
        if len(agents) <= 1:
            return 0  # No violation if alone
        
        # Count nearby agents within formation radius
        formation_radius = 75.0  # Expected formation distance
        nearby_count = 0
        
        for other_agent in agents:
            if other_agent != self:
                distance = np.linalg.norm(self.position - other_agent.position)
                if distance <= formation_radius:
                    nearby_count += 1
        
        # Formation violation if isolated (no nearby agents)
        if nearby_count == 0:
            self.formation_violations += 1
            return 1
        
        return 0
    
    def check_threat_violation(self):
        """Check if agent enters threat zone without defensive formation (Ithreat)"""
        current_threat = self.assess_threat_level()
        threat_threshold = 0.6  # High threat threshold
        
        # Violation if in high threat area without defensive profile
        if (current_threat > threat_threshold and 
            self.profile and self.profile.name != "Defensive"):
            self.threat_violations += 1
            return 1
        
        return 0
    
    def check_time_violation(self, current_time):
        """Check if agent exceeds task time limit (Itime)"""
        if self.assigned_target is None:
            return 0  # No violation if no task
        
        elapsed_time = current_time - self.task_start_time
        
        if elapsed_time > self.task_time_limit:
            self.time_violations += 1
            return 1
        
        return 0
    
    def assign_target(self, target_position, current_time, time_limit=300.0):
        """Assign a target position and task timing"""
        self.assigned_target = np.array(target_position)
        self.task_start_time = current_time
        self.task_time_limit = time_limit
    
    def get_fitness_components(self, agents, current_time):
        """Get detailed breakdown of fitness components for analysis"""
        A_i = self.calculate_swarm_adherence(agents)
        rho_qi = self.calculate_opportunity_value()
        d_i = self.calculate_target_distance()
        P_i = self.calculate_penalties(agents, current_time)
        
        total_fitness = (self.profile.fitness_w1 * A_i + 
                        self.profile.fitness_w2 * rho_qi - 
                        self.profile.fitness_w3 * d_i - 
                        P_i) if self.profile else 0.0
        
        return {
            'swarm_adherence': A_i,
            'opportunity_value': rho_qi,
            'target_distance': d_i,
            'penalties': P_i,
            'total_fitness': total_fitness,
            'violations': {
                'formation': self.formation_violations,
                'threat': self.threat_violations,
                'time': self.time_violations
            }
        }

    # ---------- Hyperparameter-RL helpers (tabular) ----------
    def _hp_state_to_str(self, state_tuple):
        return f"{state_tuple[0]}_{state_tuple[1]}_{state_tuple[2]}_{state_tuple[3]}_{state_tuple[4]}"

    def get_hp_state(self):
        """Discretize current state for HP-RL: (gx, gy, gz, threat_level, profile_idx)"""
        # grid discretization (500x500x500 -> 10x10x10)
        gx = min(9, max(0, int(self.position[0] / (500.0 / 10))))
        gy = min(9, max(0, int(self.position[1] / (500.0 / 10))))
        gz = min(9, max(0, int(self.position[2] / (500.0 / 10))))
        threat = min(1.0, self.current_threat_level)
        threat_idx = 0 if threat < 0.33 else 1 if threat < 0.66 else 2
        # profile index: offensive=0, neutral=1, defensive=2
        profile_name = self.profile.name.lower() if self.profile else 'neutral'
        profile_idx = 0 if profile_name == 'offensive' else 2 if profile_name == 'defensive' else 1
        return (gx, gy, gz, threat_idx, profile_idx)

    def _hp_action_idx_to_multipliers(self, idx):
        """Decode integer action idx to (ms, ma, mc) multipliers"""
        b = self.hp_bins
        ms_idx = idx // (b * b)
        rem = idx % (b * b)
        ma_idx = rem // b
        mc_idx = rem % b
        return (self.hp_multipliers[ms_idx], self.hp_multipliers[ma_idx], self.hp_multipliers[mc_idx])

    def choose_hp_action(self, greedy=False):
        state = self.get_hp_state()
        s = self._hp_state_to_str(state)
        if not greedy and np.random.rand() < self.hp_epsilon:
            return np.random.randint(self.hp_action_count)
        if s not in self.q_table_hp:
            self.q_table_hp[s] = np.zeros(self.hp_action_count)
        return int(np.argmax(self.q_table_hp[s]))

    def apply_hp_action(self, action_idx):
        """Apply hyperparameter action by updating per-agent boids weights"""
        ms, ma, mc = self._hp_action_idx_to_multipliers(action_idx)
        # Set weights relative to profile defaults (do not mutate shared profile)
        base_cohesion = self.profile.cohesion if self.profile else 1.0
        base_alignment = self.profile.alignment if self.profile else 1.0
        base_separation = self.profile.separation if self.profile else 1.0
        self.boids_cohesion = base_cohesion * ms
        self.boids_alignment = base_alignment * ma
        self.boids_separation = base_separation * mc

    def update_q_hp(self, reward, next_state):
        if self.prev_state_hp is None or self.prev_action_hp is None:
            return
        s_prev = self._hp_state_to_str(self.prev_state_hp)
        s_next = self._hp_state_to_str(next_state)
        if s_prev not in self.q_table_hp:
            self.q_table_hp[s_prev] = np.zeros(self.hp_action_count)
        if s_next not in self.q_table_hp:
            self.q_table_hp[s_next] = np.zeros(self.hp_action_count)
        current_q = self.q_table_hp[s_prev][self.prev_action_hp]
        max_next_q = np.max(self.q_table_hp[s_next])
        self.q_table_hp[s_prev][self.prev_action_hp] = current_q + self.hp_alpha * (reward + self.hp_gamma * max_next_q - current_q)

    def get_hp_optimal_policy_table(self):
        policy = {}
        for state_str, q_values in self.q_table_hp.items():
            best_a = int(np.argmax(q_values))
            ms, ma, mc = self._hp_action_idx_to_multipliers(best_a)
            # Convert multipliers into concrete weights for display
            # parse state_str back to tuple for profile index
            policy[state_str] = {
                'action_index': best_a,
                'multipliers': [ms, ma, mc],
                'q_value': float(q_values[best_a])
            }
        return policy
