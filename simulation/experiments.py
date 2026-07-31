"""
Automated pathfinding experiments module.
Runs batch pathfinding experiments when exploration is complete.
Tests all algorithms across different profile scenarios (Offensive, Neutral, Defensive, Dynamic).
"""
import numpy as np
import csv
import datetime
import os
from pathfinding import PathFinder
from utils import ENV_WIDTH, ENV_HEIGHT

# Global experiment progress tracking
experiment_progress = {
    'current': 0,
    'total': 0,
    'running': False,
    'phase': 'idle'  # idle, running, complete
}

class PathfindingExperiments:
    """Handles automated pathfinding experiments with profile scenarios"""
    
    def __init__(self, exploration_map, pathfinder, num_experiments=100, exploration_3d_pct=0.0):
        self.exploration_map = exploration_map
        self.pathfinder = pathfinder
        self.num_experiments = num_experiments
        self.exploration_3d_pct = exploration_3d_pct  # 3D exploration percentage when experiments started
        
        # Profile scenario configurations
        self.profile_scenarios = {
            'offensive': {
                'speed_modifiers': {'offensive': 1.0, 'neutral': 1.0, 'defensive': 1.0},
                'description': 'All areas use Offensive profile (1.0x speed)'
            },
            'neutral': {
                'speed_modifiers': {'offensive': 0.75, 'neutral': 0.75, 'defensive': 0.75},
                'description': 'All areas use Neutral profile (0.75x speed)'
            },
            'defensive': {
                'speed_modifiers': {'offensive': 0.5, 'neutral': 0.5, 'defensive': 0.5},
                'description': 'All areas use Defensive profile (0.5x speed)'
            },
            'dynamic': {
                'speed_modifiers': {'offensive': 1.0, 'neutral': 0.75, 'defensive': 0.5},
                'description': 'Dynamic profile switching based on threat'
            }
        }
        
    def generate_random_points(self, num_points):
        """Generate random start and goal points within environment bounds"""
        points = []
        
        # Add some margin to avoid edge cases
        margin = 20
        min_x, max_x = margin, ENV_WIDTH - margin
        min_y, max_y = margin, ENV_HEIGHT - margin
        
        for _ in range(num_points):
            # Generate random coordinates
            x = np.random.uniform(min_x, max_x)
            y = np.random.uniform(min_y, max_y)
            points.append(np.array([x, y]))
            
        return points
    
    def apply_profile_scenario(self, scenario_name):
        """Apply speed modifier overrides for a specific profile scenario"""
        modifiers = self.profile_scenarios[scenario_name]['speed_modifiers']
        self.pathfinder.PROFILE_SPEED_MODIFIERS = modifiers.copy()
    
    def restore_dynamic_modifiers(self):
        """Restore default dynamic profile modifiers"""
        self.pathfinder.PROFILE_SPEED_MODIFIERS = {
            'offensive': 1.0,
            'neutral': 0.75,
            'defensive': 0.5
        }
    
    def run_single_experiment(self, start_pos, goal_pos, experiment_id, profile_scenario):
        """Run pathfinding algorithms for a single start-goal pair under a specific profile"""
        print(f"Running experiment {experiment_id + 1}/{self.num_experiments} - Profile: {profile_scenario.upper()}")
        
        # Apply profile scenario
        self.apply_profile_scenario(profile_scenario)
        
        # Run all four pathfinding algorithms
        results = {}
        
        try:
            # Dijkstra
            dijkstra_path, dijkstra_cost = self.pathfinder.dijkstra(start_pos, goal_pos)
            results['dijkstra'] = {
                'path_length': len(dijkstra_path),
                'cost': dijkstra_cost,
                'success': len(dijkstra_path) > 0
            }
        except Exception as e:
            print(f"Dijkstra error in experiment {experiment_id}: {e}")
            results['dijkstra'] = {'path_length': 0, 'cost': float('inf'), 'success': False}
        
        try:
            # A*
            astar_path, astar_cost = self.pathfinder.astar(start_pos, goal_pos)
            results['astar'] = {
                'path_length': len(astar_path),
                'cost': astar_cost,
                'success': len(astar_path) > 0
            }
        except Exception as e:
            print(f"A* error in experiment {experiment_id}: {e}")
            results['astar'] = {'path_length': 0, 'cost': float('inf'), 'success': False}
        
        try:
            # Safety-first
            safety_path, safety_cost = self.pathfinder.safety_first(start_pos, goal_pos)
            results['safety_first'] = {
                'path_length': len(safety_path),
                'cost': safety_cost,
                'success': len(safety_path) > 0
            }
        except Exception as e:
            print(f"Safety-first error in experiment {experiment_id}: {e}")
            results['safety_first'] = {'path_length': 0, 'cost': float('inf'), 'success': False}
        
        try:
            # Balanced
            balanced_path, balanced_cost = self.pathfinder.balanced(start_pos, goal_pos)
            results['balanced'] = {
                'path_length': len(balanced_path),
                'cost': balanced_cost,
                'success': len(balanced_path) > 0
            }
        except Exception as e:
            print(f"Balanced error in experiment {experiment_id}: {e}")
            results['balanced'] = {'path_length': 0, 'cost': float('inf'), 'success': False}
        
        return results
    
    def run_all_experiments(self):
        """Run complete batch of pathfinding experiments"""
        global experiment_progress
        print(f"Starting automated pathfinding experiments ({self.num_experiments} pairs x 4 profiles)")
        
        # Initialize progress tracking
        total_tests = self.num_experiments * len(self.profile_scenarios)  # experiments x profiles
        experiment_progress['current'] = 0
        experiment_progress['total'] = total_tests
        experiment_progress['running'] = True
        experiment_progress['phase'] = 'running'
        
        # Generate random start and goal points
        start_points = self.generate_random_points(self.num_experiments)
        goal_points = self.generate_random_points(self.num_experiments)
        
        # Store all experiment results
        experiment_results = []
        
        # Run experiments for each profile scenario
        test_counter = 0
        for i in range(self.num_experiments):
            start_pos = start_points[i]
            goal_pos = goal_points[i]
            
            # Calculate Euclidean distance between start and goal
            euclidean_distance = np.linalg.norm(goal_pos - start_pos)
            
            # Run pathfinding for all 4 profile scenarios
            for profile_name, profile_config in self.profile_scenarios.items():
                # Update progress
                test_counter += 1
                experiment_progress['current'] = test_counter
                
                # Run pathfinding algorithms with this profile
                results = self.run_single_experiment(start_pos, goal_pos, i, profile_name)
                
                # Store experiment data
                experiment_data = {
                    'experiment_id': i + 1,
                    'profile': profile_name.capitalize(),
                    'profile_description': profile_config['description'],
                    'start_x': start_pos[0],
                    'start_y': start_pos[1],
                    'goal_x': goal_pos[0],
                    'goal_y': goal_pos[1],
                    'euclidean_distance': euclidean_distance,
                    'results': results
                }
                
                experiment_results.append(experiment_data)
        
        # Restore dynamic modifiers after all experiments
        self.restore_dynamic_modifiers()
        
        # Mark as complete
        experiment_progress['running'] = False
        experiment_progress['phase'] = 'complete'
        
        # Save results to CSV
        csv_filename = self.save_results_to_csv(experiment_results)
        
        print(f"Experiments completed! Results saved to: {csv_filename}")
        return experiment_results, csv_filename
    
    def save_results_to_csv(self, experiment_results):
        """Save experiment results to CSV file"""
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'pathfinding_experiments_{timestamp}.csv'
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header first (no metadata rows - clean CSV for algorithms)
            writer.writerow([
                'Experiment_ID', 'Profile', 
                'Start_X', 'Start_Y', 'Goal_X', 'Goal_Y', 'Euclidean_Distance',
                'Exploration_3D_Pct',
                'Dijkstra_Success', 'Dijkstra_Path_Length', 'Dijkstra_Cost',
                'AStar_Success', 'AStar_Path_Length', 'AStar_Cost',
                'Safety_Success', 'Safety_Path_Length', 'Safety_Cost',
                'Balanced_Success', 'Balanced_Path_Length', 'Balanced_Cost'
            ])
            
            # Write experiment data with numeric values (1/0 for success instead of True/False)
            for exp in experiment_results:
                # Handle inf costs - replace with -1 for failed paths
                dijk_cost = exp['results']['dijkstra']['cost']
                astar_cost = exp['results']['astar']['cost']
                safety_cost = exp['results']['safety_first']['cost']
                balanced_cost = exp['results']['balanced']['cost']
                
                row = [
                    exp['experiment_id'],
                    exp['profile'],
                    round(exp['start_x'], 2),
                    round(exp['start_y'], 2),
                    round(exp['goal_x'], 2),
                    round(exp['goal_y'], 2),
                    round(exp['euclidean_distance'], 2),
                    round(self.exploration_3d_pct, 2),
                    
                    1 if exp['results']['dijkstra']['success'] else 0,
                    exp['results']['dijkstra']['path_length'],
                    round(dijk_cost, 4) if dijk_cost != float('inf') else -1,
                    
                    1 if exp['results']['astar']['success'] else 0,
                    exp['results']['astar']['path_length'],
                    round(astar_cost, 4) if astar_cost != float('inf') else -1,
                    
                    1 if exp['results']['safety_first']['success'] else 0,
                    exp['results']['safety_first']['path_length'],
                    round(safety_cost, 4) if safety_cost != float('inf') else -1,
                    
                    1 if exp['results']['balanced']['success'] else 0,
                    exp['results']['balanced']['path_length'],
                    round(balanced_cost, 4) if balanced_cost != float('inf') else -1
                ]
                writer.writerow(row)
        
        return filename
    
    def get_experiment_summary(self, experiment_results):
        """Generate summary statistics from experiment results"""
        if not experiment_results:
            return {}
        
        algorithms = ['dijkstra', 'astar', 'safety_first', 'balanced']
        summary = {}
        
        for alg in algorithms:
            # Success rate
            successful = sum(1 for exp in experiment_results if exp['results'][alg]['success'])
            success_rate = (successful / len(experiment_results)) * 100
            
            # Average cost (excluding failures)
            costs = [exp['results'][alg]['cost'] for exp in experiment_results 
                    if exp['results'][alg]['success'] and exp['results'][alg]['cost'] != float('inf')]
            avg_cost = np.mean(costs) if costs else float('inf')
            
            # Average path length
            lengths = [exp['results'][alg]['path_length'] for exp in experiment_results 
                      if exp['results'][alg]['success']]
            avg_length = np.mean(lengths) if lengths else 0
            
            summary[alg] = {
                'success_rate': success_rate,
                'avg_cost': avg_cost,
                'avg_path_length': avg_length,
                'total_experiments': len(experiment_results)
            }
        
        return summary

def run_experiments_when_complete(exploration_map, pathfinder, num_experiments=100, exploration_3d_pct=0.0):
    """Main function to run experiments - runs regardless of exploration status"""
    progress = exploration_map.get_exploration_percentage()
    print(f"Running {num_experiments} experiments at {progress:.1f}% 2D exploration, {exploration_3d_pct:.1f}% 3D exploration...")
    
    # Create experiment runner with specified number of experiments
    experiments = PathfindingExperiments(exploration_map, pathfinder, num_experiments, exploration_3d_pct)
    
    # Run all experiments
    results, csv_filename = experiments.run_all_experiments()
    
    # Generate summary
    summary = experiments.get_experiment_summary(results)
    
    return results, csv_filename, summary


# ---------------- Boids hyperparameter RL (tabular multi-agent) ----------------
def train_hp_agents(agents, exploration_map, num_episodes=300, max_steps=200):
    """Train agents to select boids hyperparameters (ws, wa, wc) using tabular Q-learning.

    Agents choose discretized multipliers relative to their current profile defaults.
    Training is run in a fast, internal simulation loop (uses apply_boids_rules + agent.update()).
    """
    from utils import apply_boids_rules, ENV_DEPTH
    goal = np.array([ENV_WIDTH/2, ENV_HEIGHT/2, ENV_DEPTH/2])

    # Report HP training progress to global experiment_progress
    global experiment_progress
    experiment_progress['running'] = True
    experiment_progress['phase'] = 'hp-training'
    experiment_progress['total'] = num_episodes
    experiment_progress['current'] = 0

    for episode in range(num_episodes):
        # periodic terminal progress print
        if episode % max(1, num_episodes // 20) == 0:
            pct = (episode / num_episodes) * 100
            print(f"HP Training: Episode {episode}/{num_episodes} ({pct:.1f}%)")
        experiment_progress['current'] = episode + 1
        # Reset agents
        for agent in agents:
            agent.position = np.random.rand(3) * np.array([ENV_WIDTH, ENV_HEIGHT, ENV_DEPTH])
            agent.velocity = (np.random.rand(3) - 0.5) * agent.max_speed
            agent.prev_state_hp = None
            agent.prev_action_hp = None
            agent.total_reward_hp = 0.0

        for step in range(max_steps):
            # Agents pick HP actions (ε-greedy)
            for agent in agents:
                s = agent.get_hp_state()
                a = agent.choose_hp_action(greedy=False)
                agent.apply_hp_action(a)
                # store prev for Q update
                agent.prev_state_hp = s
                agent.prev_action_hp = a

            # Apply boids update step and physics
            apply_boids_rules(agents)
            for agent in agents:
                agent.update()
                # Update threat reading from map if available
                if exploration_map:
                    gx = int(agent.position[0] / exploration_map.cell_size_x)
                    gy = int(agent.position[1] / exploration_map.cell_size_y)
                    if 0 <= gx < exploration_map.resolution and 0 <= gy < exploration_map.resolution:
                        agent.current_threat_level = exploration_map.threat_map[gx, gy]

            # Compute rewards and update Q-tables for HP
            all_reached = True
            for agent in agents:
                dist = np.linalg.norm(agent.position - goal)
                threat = agent.current_threat_level if hasattr(agent, 'current_threat_level') else 0.0
                # Reward combines minimal threat exposure and short path (per-step distance penalty)
                reward = -5.0 * threat - 0.01 * dist - 0.05
                if dist < 10:
                    reward += 200.0
                next_s = agent.get_hp_state()
                agent.update_q_hp(reward, next_s)
                agent.total_reward_hp += reward
                if np.linalg.norm(agent.position - goal) >= 10:
                    all_reached = False

            if all_reached:
                break

    # Return nothing; policies stored inside agents.q_table_hp
    experiment_progress['running'] = False
    experiment_progress['phase'] = 'idle'
    print("HP-RL training completed")


def run_hp_evaluation(exploration_map, agents, num_episodes=20, max_steps=200):
    """Evaluate learned HP policies (greedy) and return average rewards + policy tables."""
    from utils import apply_boids_rules, ENV_DEPTH
    goal = np.array([ENV_WIDTH/2, ENV_HEIGHT/2, ENV_DEPTH/2])

    # Report HP evaluation progress
    global experiment_progress
    experiment_progress['running'] = True
    experiment_progress['phase'] = 'hp-evaluation'
    experiment_progress['total'] = num_episodes
    experiment_progress['current'] = 0

    agent_rewards = {i: [] for i in range(len(agents))}
    swarm_rewards = []

    for ep in range(num_episodes):
        if ep % max(1, num_episodes // 20) == 0:
            pct = (ep / num_episodes) * 100
            print(f"HP Evaluation: Episode {ep}/{num_episodes} ({pct:.1f}%)")
        experiment_progress['current'] = ep + 1
        # Reset agents
        for agent in agents:
            agent.position = np.random.rand(3) * np.array([ENV_WIDTH, ENV_HEIGHT, ENV_DEPTH])
            agent.velocity = (np.random.rand(3) - 0.5) * agent.max_speed
            agent.total_reward_hp = 0.0

        for step in range(max_steps):
            # Greedy HP action selection and apply
            for agent in agents:
                a = agent.choose_hp_action(greedy=True)
                agent.apply_hp_action(a)

            # Apply boids and physics
            apply_boids_rules(agents)
            for agent in agents:
                agent.update()
                if exploration_map:
                    gx = int(agent.position[0] / exploration_map.cell_size_x)
                    gy = int(agent.position[1] / exploration_map.cell_size_y)
                    if 0 <= gx < exploration_map.resolution and 0 <= gy < exploration_map.resolution:
                        agent.current_threat_level = exploration_map.threat_map[gx, gy]

            # Rewards
            all_reached = True
            for agent in agents:
                dist = np.linalg.norm(agent.position - goal)
                threat = agent.current_threat_level if hasattr(agent, 'current_threat_level') else 0.0
                reward = -5.0 * threat - 0.01 * dist - 0.05
                if dist < 10:
                    reward += 200.0
                agent.total_reward_hp += reward
                if dist >= 10:
                    all_reached = False

            if all_reached:
                break

        # record episode rewards
        for i, agent in enumerate(agents):
            agent_rewards[i].append(agent.total_reward_hp)
        swarm_rewards.append(sum(agent.total_reward_hp for agent in agents))

    avg_agent_rewards = {i: float(np.mean(vals)) if vals else 0.0 for i, vals in agent_rewards.items()}
    avg_swarm_reward = float(np.mean(swarm_rewards)) if swarm_rewards else 0.0

    # Collect optimal HP policies (tabular summaries)
    policies = {i: agent.get_hp_optimal_policy_table() for i, agent in enumerate(agents)}

    # Aggregate per-profile averages (multipliers + absolute weights)
    from profiles import OFFENSIVE, NEUTRAL, DEFENSIVE
    profile_defaults = {
        'Offensive': {'cohesion': OFFENSIVE.cohesion, 'alignment': OFFENSIVE.alignment, 'separation': OFFENSIVE.separation},
        'Neutral': {'cohesion': NEUTRAL.cohesion, 'alignment': NEUTRAL.alignment, 'separation': NEUTRAL.separation},
        'Defensive': {'cohesion': DEFENSIVE.cohesion, 'alignment': DEFENSIVE.alignment, 'separation': DEFENSIVE.separation}
    }

    per_profile = {k: {'count': 0, 'sum_ms': 0.0, 'sum_ma': 0.0, 'sum_mc': 0.0} for k in profile_defaults}

    for i, agent in enumerate(agents):
        prof_name = agent.profile.name if agent.profile else 'Neutral'
        # pick top policy entry for this agent
        top = None
        agent_policy = policies.get(i, {})
        for s, info in agent_policy.items():
            if top is None or info['q_value'] > top['q_value']:
                top = info
        if not top:
            continue
        ms, ma, mc = top['multipliers']
        if prof_name not in per_profile:
            per_profile[prof_name] = {'count': 0, 'sum_ms': 0.0, 'sum_ma': 0.0, 'sum_mc': 0.0}
        per_profile[prof_name]['count'] += 1
        per_profile[prof_name]['sum_ms'] += ms
        per_profile[prof_name]['sum_ma'] += ma
        per_profile[prof_name]['sum_mc'] += mc

    # Compute averages and absolute weights
    per_profile_summary = {}
    for prof, vals in per_profile.items():
        if vals['count'] > 0:
            avg_ms = vals['sum_ms'] / vals['count']
            avg_ma = vals['sum_ma'] / vals['count']
            avg_mc = vals['sum_mc'] / vals['count']
        else:
            avg_ms = avg_ma = avg_mc = 1.0  # fallback multiplier
        defaults = profile_defaults.get(prof, profile_defaults['Neutral'])
        per_profile_summary[prof] = {
            'avg_multipliers': [avg_ms, avg_ma, avg_mc],
            'avg_weights': [
                round(defaults['cohesion'] * avg_ms, 4),
                round(defaults['alignment'] * avg_ma, 4),
                round(defaults['separation'] * avg_mc, 4)
            ],
            'count': vals['count']
        }

    experiment_progress['running'] = False
    experiment_progress['phase'] = 'idle'
    print("HP-RL evaluation completed")
    return avg_agent_rewards, avg_swarm_reward, policies, per_profile_summary