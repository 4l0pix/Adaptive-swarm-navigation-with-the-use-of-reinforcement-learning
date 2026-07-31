import numpy as np
from agent import Agent
from profiles import *

# ===== SIMULATION CONSTANTS =====

# Agent parameters
MAX_SPEED = 5.0   # Reduced for better control
MAX_FORCE = 1.0   # Increased to work with profile multipliers
PROFILE=NEUTRAL
# Environment dimensions
ENV_WIDTH = 500
ENV_HEIGHT = 500
ENV_DEPTH = 500

# Border parameters
BORDER_MARGIN = 5


# Obstacle parameters
NUM_OBSTACLES = 45
OBSTACLE_MIN_HEIGHT = 450
OBSTACLE_MAX_HEIGHT = 500
OBSTACLE_WIDTH = 5  # Width and depth of rectangular obstacles
OBSTACLE_AVOIDANCE_RADIUS = 10  # How far agents detect obstacles
OBSTACLE_AVOIDANCE_FORCE = 0.2  # Strength of avoidance force

# Exploration map parameters
MAP_RESOLUTION = 50  # Grid resolution for exploration map (50x50 grid)
EXPLORATION_RADIUS = 7  # Radius around agent that counts as explored
THREAT_DETECTION_RADIUS = 35  # Distance for calculating obstacle threat intensity
UNEXPLORED_AVOIDANCE_WEIGHT = 1  # Weight for steering towards unexplored areas

# Note: Profile-specific parameters are now defined in profiles.py within the Profile class

# Dynamic profile switching thresholds
HIGH_THREAT_THRESHOLD = 0.7   # Switch to defensive if threat > this value
LOW_THREAT_THRESHOLD = 0.2    # Switch to offensive if threat < this value
THREAT_RADIUS_CHECK = 15      # Radius around agent to check for threat

# Profile color coding for agents
PROFILE_COLORS = {
    'Offensive': 'green',   # Green for exploration/offensive
    'Neutral': 'blue',     # Blue for neutral/balanced
    'Defensive': 'red'     # Red for defensive/danger
}

# Simulation parameters
NUM_AGENTS = 15



# ===== HELPER FUNCTIONS =====

def create_random_agents(n, width, height, depth, max_speed=MAX_SPEED, initial_profile=None):
    """Create n agents starting from the same position with random velocities"""
    from profiles import NEUTRAL
    agents = []
    # Start all agents from the center of the environment
    start_pos = np.array([width/2, height/2, depth/2])
    
    for _ in range(n):
        # All agents start from same position
        pos = start_pos.copy()
        # But with different random velocities
        vel = (np.random.rand(3) - 0.5) * max_speed
        # Initialize with neutral profile by default
        profile = initial_profile if initial_profile else NEUTRAL
        agents.append(Agent(pos, vel, max_speed=max_speed, max_force=MAX_FORCE, profile=profile))
    return agents

def apply_boids_rules(agents, default_profile=None):
    """Apply the three boids rules to all agents using their individual profiles.

    If an agent has explicit boids weight overrides (`boids_cohesion`,
    `boids_alignment`, `boids_separation`) those are used instead of the
    shared Profile values. This allows per-agent hyperparameter tuning
    without mutating the global Profile objects.
    """
    for agent in agents:
        # Use agent's individual profile or fall back to default
        profile = agent.profile if agent.profile else default_profile
        if profile is None:
            continue  # Skip if no profile available

        # Prefer per-agent boids weight overrides when present
        cohesion_w = getattr(agent, 'boids_cohesion', profile.cohesion)
        alignment_w = getattr(agent, 'boids_alignment', profile.alignment)
        separation_w = getattr(agent, 'boids_separation', profile.separation)

        cohesion = agent.cohesion(agents, radius=profile.cohesion_radius) * cohesion_w
        alignment = agent.alignment(agents, radius=profile.alignment_radius) * alignment_w
        separation = agent.separation(agents, radius=profile.separation_radius) * separation_w

        agent.apply_force(cohesion)
        agent.apply_force(alignment)
        agent.apply_force(separation)

def get_exploration_weight(profile):
    """Get exploration weight from profile"""
    return profile.exploration_weight

def get_obstacle_avoidance_weight(profile):
    """Get obstacle avoidance weight from profile"""
    return profile.obstacle_avoidance_weight

def update_agent_profiles_based_on_threat(agents):
    """Update all agent profiles based on their current threat levels"""
    from profiles import OFFENSIVE, NEUTRAL, DEFENSIVE
    
    profiles_dict = {
        'OFFENSIVE': OFFENSIVE,
        'NEUTRAL': NEUTRAL,
        'DEFENSIVE': DEFENSIVE
    }
    
    for agent in agents:
        agent.update_profile_based_on_threat(profiles_dict)
        
def get_swarm_profile_distribution(agents):
    """Get count of agents per profile type"""
    distribution = {'Offensive': 0, 'Neutral': 0, 'Defensive': 0}
    
    for agent in agents:
        if agent.profile:
            distribution[agent.profile.name] += 1
            
    return distribution

def calculate_swarm_fitness(agents, current_time):
    """Calculate fitness metrics for the entire swarm"""
    if not agents:
        return {}
    
    individual_fitness = []
    total_violations = {'formation': 0, 'threat': 0, 'time': 0}
    
    # Calculate fitness for each agent
    for agent in agents:
        fitness = agent.calculate_fitness(agents, current_time)
        individual_fitness.append(fitness)
        
        # Aggregate violations
        total_violations['formation'] += agent.formation_violations
        total_violations['threat'] += agent.threat_violations
        total_violations['time'] += agent.time_violations
    
    # Calculate swarm-level metrics
    avg_fitness = np.mean(individual_fitness)
    min_fitness = np.min(individual_fitness)
    max_fitness = np.max(individual_fitness)
    fitness_std = np.std(individual_fitness)
    
    return {
        'individual_fitness': individual_fitness,
        'avg_fitness': avg_fitness,
        'min_fitness': min_fitness,
        'max_fitness': max_fitness,
        'fitness_std': fitness_std,
        'total_violations': total_violations,
        'swarm_size': len(agents)
    }

def get_swarm_fitness_summary(agents):
    """Get summary of fitness weights currently active in the swarm"""
    profile_counts = {}
    
    for agent in agents:
        if agent.profile:
            profile_name = agent.profile.name
            if profile_name not in profile_counts:
                profile_counts[profile_name] = {
                    'count': 0,
                    'weights': {
                        'w1': agent.profile.fitness_w1,
                        'w2': agent.profile.fitness_w2,
                        'w3': agent.profile.fitness_w3
                    },
                    'penalties': {
                        'pf': agent.profile.penalty_pf,
                        'pt': agent.profile.penalty_pt,
                        'ptau': agent.profile.penalty_ptau
                    }
                }
            profile_counts[profile_name]['count'] += 1
    
    return profile_counts

def assign_random_targets(agents, env_width, env_height, current_time, time_limit=300.0):
    """Assign random exploration targets to agents for fitness evaluation"""
    for agent in agents:
        # Generate random target within environment bounds
        target_x = np.random.uniform(50, env_width - 50)
        target_y = np.random.uniform(50, env_height - 50)
        target_z = agent.position[2]  # Keep same altitude
        
        target_pos = [target_x, target_y, target_z]
        agent.assign_target(target_pos, current_time, time_limit)

def get_fitness_statistics(agents, current_time):
    """Get detailed fitness statistics for analysis"""
    stats = {
        'agents': [],
        'swarm_metrics': calculate_swarm_fitness(agents, current_time)
    }
    
    for i, agent in enumerate(agents):
        components = agent.get_fitness_components(agents, current_time)
        agent_stats = {
            'id': i,
            'position': agent.position.tolist(),
            'profile': agent.profile.name if agent.profile else 'None',
            'fitness_components': components,
            'assigned_target': agent.assigned_target.tolist() if agent.assigned_target is not None else None
        }
        stats['agents'].append(agent_stats)
    
    return stats

def create_random_obstacles(n, width, height, depth,
                           min_height=OBSTACLE_MIN_HEIGHT,
                           max_height=OBSTACLE_MAX_HEIGHT,
                           obstacle_width=OBSTACLE_WIDTH):
    """Create n random vertical obstacles (buildings)"""
    obstacles = []
    for _ in range(n):
        x = np.random.uniform(10, width - 10)
        y = np.random.uniform(10, depth - 10)
        z_base = 0
        obstacle_height = np.random.uniform(min_height, max_height)

        obstacles.append({
            'position': np.array([x, y, z_base]),
            'width': obstacle_width,
            'height': obstacle_height
        })
    return obstacles
