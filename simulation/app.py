from flask import Flask, render_template, jsonify, request, send_file
import numpy as np
import csv
import io
import json
import os
import datetime
import threading
import time
from environment import Environment
from exploration_map import ExplorationMap
from pathfinding import PathFinder, PathfindingComparator
from experiments import run_experiments_when_complete, experiment_progress, train_hp_agents, run_hp_evaluation
from utils import (create_random_agents, apply_boids_rules, create_random_obstacles,
                   ENV_WIDTH, ENV_HEIGHT, ENV_DEPTH, NUM_AGENTS,
                   NUM_OBSTACLES, OBSTACLE_AVOIDANCE_RADIUS,
                   EXPLORATION_RADIUS, get_exploration_weight, get_obstacle_avoidance_weight,
                   update_agent_profiles_based_on_threat, get_swarm_profile_distribution,
                   calculate_swarm_fitness, get_swarm_fitness_summary,
                   assign_random_targets, get_fitness_statistics)
from profiles import NEUTRAL, OFFENSIVE, get_profile
from agent import Agent
import math

app = Flask(__name__)

# Simulation state
class SimulationState:
    def __init__(self):
        self.env = None
        self.agents = []
        self.obstacles = []
        self.exploration_map = None
        self.pathfinder = None
        self.initialized = False
        self.optimal_pos = None
        self.last_pathfinding_results = None
        self.simulation_time = 0.0
        self.experiments_running = False
        self.experiment_results = None
        self.experiment_csv = None
        self.nest_position = None
        self.manual_path = []
        # Multi-test aggregation
        self.all_test_results = []  # Results from all tests
        self.current_test_number = 0
        self.total_tests = 0
        self.hp_rl_results = None
        self.experiment_json = None
        # Lock for thread-safe simulation updates
        self.lock = threading.Lock()

    def init_simulation(self):
        self.env = Environment(ENV_WIDTH, ENV_HEIGHT, ENV_DEPTH)
        
        # Initialize nest first so agents can spawn from it
        self._init_nest_position()
        
        # Create agents at nest position instead of center
        self.agents = self._create_agents_at_nest(NUM_AGENTS)
        
        self.obstacles = create_random_obstacles(NUM_OBSTACLES, ENV_WIDTH, ENV_HEIGHT, ENV_DEPTH)
        self.env.add_obstacles(self.obstacles)
        
        self.exploration_map = ExplorationMap(ENV_WIDTH, ENV_HEIGHT, self.obstacles)
        self.env.set_exploration_map(self.exploration_map)
        self.pathfinder = PathFinder(self.exploration_map)
        
        for agent in self.agents:
            agent.exploration_map = self.exploration_map
            
        self.initialized = True
        self.optimal_pos = None
        self.last_pathfinding_results = None
        self.simulation_time = 0.0
        self.experiments_running = False
        self.experiment_results = None
        self.experiment_csv = None
        self.manual_path = []
        
        # Assign initial targets for fitness evaluation
        assign_random_targets(self.agents, ENV_WIDTH, ENV_HEIGHT, self.simulation_time)
    
    def _create_agents_at_nest(self, n):
        """Create n agents at the nest position with random velocities"""
        agents = []
        nest_pos = np.array([self.nest_position['x'], self.nest_position['y'], self.nest_position['z']])
        
        for _ in range(n):
            # All agents start from nest position
            pos = nest_pos.copy()
            # Random velocities pointing outward from nest
            vel = (np.random.rand(3) - 0.5) * 2.0
            agents.append(Agent(pos, vel, max_speed=2.0, max_force=0.03, profile=NEUTRAL))
        return agents
    
    def _init_nest_position(self):
        """Initialize nest position at a random edge"""
        import random
        edge = random.choice(['left', 'right', 'top', 'bottom'])
        if edge == 'left':
            self.nest_position = {'x': 10, 'y': random.uniform(50, ENV_HEIGHT - 50), 'z': ENV_DEPTH / 2}
        elif edge == 'right':
            self.nest_position = {'x': ENV_WIDTH - 10, 'y': random.uniform(50, ENV_HEIGHT - 50), 'z': ENV_DEPTH / 2}
        elif edge == 'top':
            self.nest_position = {'x': random.uniform(50, ENV_WIDTH - 50), 'y': ENV_HEIGHT - 10, 'z': ENV_DEPTH / 2}
        else:  # bottom
            self.nest_position = {'x': random.uniform(50, ENV_WIDTH - 50), 'y': 10, 'z': ENV_DEPTH / 2}

sim_state = SimulationState()

@app.route('/')
def index():
    if not sim_state.initialized:
        sim_state.init_simulation()
    return render_template('index.html')


@app.route('/health')
def health():
    """Lightweight readiness endpoint for local checks and deployments."""
    return jsonify({'status': 'ok', 'version': '0.5'})

@app.route('/init', methods=['POST'])
def init():
    with sim_state.lock:
        sim_state.init_simulation()
    return jsonify({'status': 'ok'})

def _advance_simulation_step():
    """Advance internal simulation state by one step and return the same
    dictionary structure previously returned by the `/step` endpoint.

    NOTE: caller must hold `sim_state.lock` if concurrent access is possible.
    """
    if not sim_state.initialized:
        sim_state.init_simulation()

    # Update agent profiles
    update_agent_profiles_based_on_threat(sim_state.agents)

    # Apply boids rules
    apply_boids_rules(sim_state.agents, default_profile=OFFENSIVE)

    # Apply forces
    for agent in sim_state.agents:
        agent_profile = agent.profile if agent.profile else OFFENSIVE
        exploration_weight = get_exploration_weight(agent_profile)
        obstacle_avoidance_weight = get_obstacle_avoidance_weight(agent_profile)

        border_force = sim_state.env.apply_borders(agent)
        obstacle_force = sim_state.env.apply_obstacle_avoidance(agent,
                                                      OBSTACLE_AVOIDANCE_RADIUS,
                                                      obstacle_avoidance_weight)
        explore_force = agent.explore_behavior(exploration_weight)

        agent.apply_force(border_force)
        agent.apply_force(obstacle_force)
        agent.apply_force(explore_force)

    # Update agents and map
    for agent in sim_state.agents:
        agent.update()
        sim_state.exploration_map.mark_explored(agent.position, EXPLORATION_RADIUS)
        sim_state.exploration_map.mark_explored_3d(agent.position, EXPLORATION_RADIUS)

    # Update simulation time
    sim_state.simulation_time += 0.05  # Assuming ~20 FPS (50ms per step)

    # Prepare response data
    agents_data = []
    for agent in sim_state.agents:
        agents_data.append({
            'x': float(agent.position[0]),
            'y': float(agent.position[1]),
            'z': float(agent.position[2]),
            'profile': agent.profile.name if agent.profile else 'Unknown'
        })

    obstacles_data = []
    for obs in sim_state.obstacles:
        obstacles_data.append({
            'x': float(obs['position'][0]),
            'y': float(obs['position'][1]),
            'z': float(obs['position'][2]),
            'w': float(obs['width']),
            'h': float(obs['height'])
        })

    explored_grid = sim_state.exploration_map.explored_grid.astype(int).tolist()
    threat_map = sim_state.exploration_map.threat_map.tolist()

    progress = sim_state.exploration_map.get_exploration_percentage()
    distribution = get_swarm_profile_distribution(sim_state.agents)

    if progress >= 100.0 and sim_state.optimal_pos is None:
        sim_state.optimal_pos, min_threat = sim_state.exploration_map.find_optimal_position()

    return {
        'agents': agents_data,
        'obstacles': obstacles_data,
        'explored_grid': explored_grid,
        'threat_map': threat_map,
        'stats': {
            'progress': progress,
            'distribution': distribution
        },
        'optimal_pos': sim_state.optimal_pos.tolist() if sim_state.optimal_pos is not None else None,
        'dimensions': {
            'width': ENV_WIDTH,
            'height': ENV_HEIGHT,
            'depth': ENV_DEPTH,
            'resolution': sim_state.exploration_map.resolution
        }
    }

@app.route('/step')
def step():
    """HTTP endpoint wrapper around internal simulation step."""
    with sim_state.lock:
        data = _advance_simulation_step()
    return jsonify(data)


def _background_simulator():
    """Background thread that advances the simulation continuously on the server.

    - Waits for sim_state to be initialized before starting.
    - Skips stepping while experiments are running to avoid interference.
    - Runs as a daemon thread.
    """
    while True:
        try:
            if not sim_state.initialized:
                time.sleep(0.1)
                continue
            # Avoid stepping while heavy experiment batch is running
            if getattr(sim_state, 'experiments_running', False):
                time.sleep(0.05)
                continue

            with sim_state.lock:
                _advance_simulation_step()

            # Match client-side step timing (50 ms)
            time.sleep(0.05)
        except Exception as e:
            print(f"Background simulator error: {e}")
            time.sleep(0.5)

# Start the background loop by default. Tests and embedding applications can
# disable it before importing this module with SWARM_BACKGROUND_SIMULATION=0.
bg_thread = None
if os.environ.get('SWARM_BACKGROUND_SIMULATION', '1') != '0':
    bg_thread = threading.Thread(target=_background_simulator, daemon=True)
    bg_thread.start()

@app.route('/pathfinding', methods=['POST'])
def pathfinding():
    """Run pathfinding from start to goal using both algorithms"""
    if not sim_state.initialized:
        return jsonify({'error': 'Simulation not initialized'}), 400
    
    data = request.json
    if not data or 'start' not in data or 'goal' not in data:
        return jsonify({'error': 'Missing start or goal position'}), 400
    
    try:
        start_pos = np.array([data['start']['x'], data['start']['y']])
        goal_pos = np.array([data['goal']['x'], data['goal']['y']])
        
        print(f"Pathfinding request: start={start_pos}, goal={goal_pos}")
        
        # Run all four algorithms
        dijkstra_path, dijkstra_cost = sim_state.pathfinder.dijkstra(start_pos, goal_pos)
        astar_path, astar_cost = sim_state.pathfinder.astar(start_pos, goal_pos)
        safety_path, safety_cost = sim_state.pathfinder.safety_first(start_pos, goal_pos)
        balanced_path, balanced_cost = sim_state.pathfinder.balanced(start_pos, goal_pos)
        
        # Convert paths to serializable format
        dijkstra_path_data = [{'x': float(p[0]), 'y': float(p[1])} for p in dijkstra_path]
        astar_path_data = [{'x': float(p[0]), 'y': float(p[1])} for p in astar_path]
        safety_path_data = [{'x': float(p[0]), 'y': float(p[1])} for p in safety_path]
        balanced_path_data = [{'x': float(p[0]), 'y': float(p[1])} for p in balanced_path]
        
        # Store results for CSV export
        sim_state.last_pathfinding_results = {
            'start': start_pos,
            'goal': goal_pos,
            'timestamp': datetime.datetime.now(),
            'algorithms': {
                'dijkstra': {'path': dijkstra_path, 'cost': dijkstra_cost},
                'astar': {'path': astar_path, 'cost': astar_cost},
                'safety_first': {'path': safety_path, 'cost': safety_cost},
                'balanced': {'path': balanced_path, 'cost': balanced_cost}
            }
        }
        
        return jsonify({
            'dijkstra': {
                'path': dijkstra_path_data,
                'cost': float(dijkstra_cost),
                'nodes': len(dijkstra_path)
            },
            'astar': {
                'path': astar_path_data,
                'cost': float(astar_cost),
                'nodes': len(astar_path)
            },
            'safety_first': {
                'path': safety_path_data,
                'cost': float(safety_cost),
                'nodes': len(safety_path)
            },
            'balanced': {
                'path': balanced_path_data,
                'cost': float(balanced_cost),
                'nodes': len(balanced_path)
            }
        })
        
    except Exception as e:
        print(f"Pathfinding error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/optimal_position')
def get_optimal_position():
    """Get the optimal position with minimum threat"""
    if not sim_state.initialized:
        return jsonify({'error': 'Simulation not initialized'}), 400
    
    optimal_pos, min_threat = sim_state.exploration_map.find_optimal_position()
    
    return jsonify({
        'position': {
            'x': float(optimal_pos[0]),
            'y': float(optimal_pos[1])
        },
        'threat': float(min_threat)
    })

@app.route('/export_pathfinding_csv')
def export_pathfinding_csv():
    """Export the last pathfinding results to CSV"""
    if not sim_state.initialized or not sim_state.last_pathfinding_results:
        return jsonify({'error': 'No pathfinding results available'}), 400
    
    results = sim_state.last_pathfinding_results
    
    # Create CSV data in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'Algorithm', 'Cost', 'Nodes', 'Path_Length', 
        'Start_X', 'Start_Y', 'Goal_X', 'Goal_Y', 'Timestamp'
    ])
    
    # Write data for each algorithm
    for algo_name, algo_data in results['algorithms'].items():
        path = algo_data['path']
        path_length = len(path)
        
        writer.writerow([
            algo_name.replace('_', ' ').title(),
            f"{algo_data['cost']:.4f}",
            path_length,
            path_length,
            f"{results['start'][0]:.2f}",
            f"{results['start'][1]:.2f}",
            f"{results['goal'][0]:.2f}",
            f"{results['goal'][1]:.2f}",
            results['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    # Write detailed path data
    writer.writerow([])  # Empty row separator
    writer.writerow(['Detailed Path Coordinates'])
    writer.writerow(['Algorithm', 'Step', 'X', 'Y'])
    
    for algo_name, algo_data in results['algorithms'].items():
        path = algo_data['path']
        for i, point in enumerate(path):
            writer.writerow([
                algo_name.replace('_', ' ').title(),
                i + 1,
                f"{point[0]:.4f}",
                f"{point[1]:.4f}"
            ])
    
    # Prepare file for download
    output.seek(0)
    csv_data = output.getvalue()
    output.close()
    
    # Create filename with timestamp
    timestamp = results['timestamp'].strftime('%Y%m%d_%H%M%S')
    filename = f'pathfinding_results_{timestamp}.csv'
    
    # Create BytesIO object for file download
    csv_bytes = io.BytesIO()
    csv_bytes.write(csv_data.encode('utf-8'))
    csv_bytes.seek(0)
    
    return send_file(
        csv_bytes,
        as_attachment=True,
        download_name=filename,
        mimetype='text/csv'
    )

@app.route('/fitness_statistics')
def get_fitness_stats():
    """Get current fitness statistics for all agents"""
    if not sim_state.initialized:
        return jsonify({'error': 'Simulation not initialized'}), 400
    
    try:
        stats = get_fitness_statistics(sim_state.agents, sim_state.simulation_time)
        return jsonify(stats)
    except Exception as e:
        print(f"Fitness statistics error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/fitness_profile_summary')
def get_fitness_profile_summary():
    """Get summary of current fitness weights by profile in the swarm"""
    if not sim_state.initialized:
        return jsonify({'error': 'Simulation not initialized'}), 400
    
    try:
        summary = get_swarm_fitness_summary(sim_state.agents)
        return jsonify({
            'status': 'success',
            'profile_summary': summary,
            'total_agents': len(sim_state.agents)
        })
    except Exception as e:
        print(f"Fitness profile summary error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/assign_targets', methods=['POST'])
def assign_targets():
    """Assign new random targets to all agents"""
    if not sim_state.initialized:
        return jsonify({'error': 'Simulation not initialized'}), 400
    
    data = request.json or {}
    time_limit = data.get('time_limit', 300.0)
    
    try:
        assign_random_targets(sim_state.agents, ENV_WIDTH, ENV_HEIGHT, 
                            sim_state.simulation_time, time_limit)
        
        return jsonify({
            'status': 'success',
            'message': f'Assigned new targets to {len(sim_state.agents)} agents',
            'time_limit': time_limit
        })
    except Exception as e:
        print(f"Assign targets error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/export_fitness_csv')
def export_fitness_csv():
    """Export current fitness statistics to CSV"""
    if not sim_state.initialized:
        return jsonify({'error': 'Simulation not initialized'}), 400
    
    try:
        stats = get_fitness_statistics(sim_state.agents, sim_state.simulation_time)
        
        # Create CSV data in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Agent_ID', 'Profile', 'Total_Fitness', 'Swarm_Adherence', 
            'Opportunity_Value', 'Target_Distance', 'Penalties',
            'Formation_Violations', 'Threat_Violations', 'Time_Violations',
            'Position_X', 'Position_Y', 'Position_Z', 'Target_X', 'Target_Y', 'Target_Z'
        ])
        
        # Write agent data
        for agent_data in stats['agents']:
            components = agent_data['fitness_components']
            target = agent_data['assigned_target']
            
            writer.writerow([
                agent_data['id'],
                agent_data['profile'],
                f"{components['total_fitness']:.4f}",
                f"{components['swarm_adherence']:.4f}",
                f"{components['opportunity_value']:.4f}",
                f"{components['target_distance']:.4f}",
                f"{components['penalties']:.4f}",
                components['violations']['formation'],
                components['violations']['threat'],
                components['violations']['time'],
                f"{agent_data['position'][0]:.2f}",
                f"{agent_data['position'][1]:.2f}",
                f"{agent_data['position'][2]:.2f}",
                f"{target[0]:.2f}" if target else 'None',
                f"{target[1]:.2f}" if target else 'None',
                f"{target[2]:.2f}" if target else 'None'
            ])
        
        # Write swarm summary
        writer.writerow([])  # Empty row separator
        writer.writerow(['Swarm Summary'])
        swarm_metrics = stats['swarm_metrics']
        writer.writerow(['Average Fitness', f"{swarm_metrics['avg_fitness']:.4f}"])
        writer.writerow(['Min Fitness', f"{swarm_metrics['min_fitness']:.4f}"])
        writer.writerow(['Max Fitness', f"{swarm_metrics['max_fitness']:.4f}"])
        writer.writerow(['Fitness Std Dev', f"{swarm_metrics['fitness_std']:.4f}"])
        writer.writerow(['Total Formation Violations', swarm_metrics['total_violations']['formation']])
        writer.writerow(['Total Threat Violations', swarm_metrics['total_violations']['threat']])
        writer.writerow(['Total Time Violations', swarm_metrics['total_violations']['time']])
        writer.writerow(['Simulation Time', f"{sim_state.simulation_time:.2f}"])
        
        # Add profile summary to CSV
        profile_summary = get_swarm_fitness_summary(sim_state.agents)
        writer.writerow([])  # Empty row
        writer.writerow(['Profile Distribution and Weights'])
        for profile_name, info in profile_summary.items():
            writer.writerow([f'{profile_name} Count', info['count']])
            writer.writerow([f'{profile_name} w1', info['weights']['w1']])
            writer.writerow([f'{profile_name} w2', info['weights']['w2']])
            writer.writerow([f'{profile_name} w3', info['weights']['w3']])
        
        # Prepare file for download
        output.seek(0)
        csv_data = output.getvalue()
        output.close()
        
        # Create filename with timestamp
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'fitness_statistics_{timestamp}.csv'
        
        # Create BytesIO object for file download
        csv_bytes = io.BytesIO()
        csv_bytes.write(csv_data.encode('utf-8'))
        csv_bytes.seek(0)
        
        return send_file(
            csv_bytes,
            as_attachment=True,
            download_name=filename,
            mimetype='text/csv'
        )
        
    except Exception as e:
        print(f"Export fitness CSV error: {e}")
        return jsonify({'error': str(e)}), 500

def save_aggregated_results(all_results, total_tests):
    """Save aggregated results from all tests to a single CSV file"""
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'aggregated_experiments_{total_tests}tests_{timestamp}.csv'
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # Write clean header (no metadata - ready for algorithm parsing)
        writer.writerow([
            'Test_Number', 'Experiment_ID', 'Profile',
            'Start_X', 'Start_Y', 'Goal_X', 'Goal_Y', 'Euclidean_Distance',
            'Dijkstra_Success', 'Dijkstra_Path_Length', 'Dijkstra_Cost',
            'AStar_Success', 'AStar_Path_Length', 'AStar_Cost',
            'Safety_Success', 'Safety_Path_Length', 'Safety_Cost',
            'Balanced_Success', 'Balanced_Path_Length', 'Balanced_Cost'
        ])
        
        # Write all experiment data with numeric values
        for exp in all_results:
            test_num = exp.get('test_number', 1)
            
            # Handle inf costs - replace with -1 for failed paths
            dijk_cost = exp['results']['dijkstra']['cost']
            astar_cost = exp['results']['astar']['cost']
            safety_cost = exp['results']['safety_first']['cost']
            balanced_cost = exp['results']['balanced']['cost']
            
            row = [
                test_num,
                exp['experiment_id'],
                exp['profile'],
                round(exp['start_x'], 2),
                round(exp['start_y'], 2),
                round(exp['goal_x'], 2),
                round(exp['goal_y'], 2),
                round(exp['euclidean_distance'], 2),
                
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
    
    print(f"Aggregated results saved to: {filename}")
    return filename


def _sanitize_for_json(obj):
    """Recursively convert non-JSON-safe values (numpy types, inf, nan) to
    JSON-safe Python primitives. Replaces non-finite floats with None.
    """
    # Primitives
    if obj is None:
        return None
    if isinstance(obj, (str, bool)):
        return obj

    # Numbers (including numpy scalars)
    try:
        if isinstance(obj, (int, float)):
            # Replace non-finite floats with None
            if isinstance(obj, float) and not math.isfinite(obj):
                return None
            return obj
    except Exception:
        pass

    # Numpy scalar types
    try:
        import numpy as _np
        if isinstance(obj, (_np.integer, _np.floating)):
            v = obj.item()
            if isinstance(v, float) and not math.isfinite(v):
                return None
            return v
    except Exception:
        pass

    # Containers
    if isinstance(obj, dict):
        return {str(k): _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]

    # Fallback: try to convert to primitive
    try:
        return float(obj)
    except Exception:
        try:
            return str(obj)
        except Exception:
            return None

@app.route('/run_experiments', methods=['POST'])
def run_experiments():
    """Run automated pathfinding experiments (thread-safe).

    The server flag `sim_state.experiments_running` is held true for the
    entire duration of experiment execution + post-processing (CSV, HP-RL
    training/eval) so the background simulator will pause while experiments
    are processed.
    """
    if not sim_state.initialized:
        return jsonify({'error': 'Simulation not initialized'}), 400

    data = request.get_json() or {}
    num_experiments = data.get('num_experiments', 100)
    exploration_3d_pct = data.get('exploration_3d_pct', 0.0)
    test_number = data.get('test_number', 1)
    total_tests = data.get('total_tests', 1)

    # Reserve the experiments slot
    with sim_state.lock:
        if sim_state.experiments_running:
            return jsonify({'error': 'Experiments already running'}), 400
        sim_state.current_test_number = test_number
        sim_state.total_tests = total_tests
        if test_number == 1:
            sim_state.all_test_results = []
        sim_state.experiments_running = True

    try:
        # Execute experiments (long-running) without holding the lock
        results, csv_filename, summary = run_experiments_when_complete(
            sim_state.exploration_map, sim_state.pathfinder, num_experiments, exploration_3d_pct
        )

        # Add test metadata
        for r in results:
            r['test_number'] = test_number

        # Post-process and store results under lock
        with sim_state.lock:
            sim_state.all_test_results.extend(results)
            sim_state.experiment_results = results

            # Save aggregated CSV on last test
            if test_number >= total_tests:
                aggregated_csv = save_aggregated_results(sim_state.all_test_results, total_tests)
                sim_state.experiment_csv = aggregated_csv
            else:
                sim_state.experiment_csv = csv_filename

        # Run HP-RL training/evaluation only after results are stored
        if test_number >= total_tests:
            try:
                print("Training Boids HP-RL agents...")
                train_hp_agents(sim_state.agents, sim_state.exploration_map, num_episodes=300)

                print("Evaluating Boids HP-RL policies (greedy)...")
                avg_agent_rewards, avg_swarm_reward, hp_policies, per_profile_summary = run_hp_evaluation(sim_state.exploration_map, sim_state.agents, num_episodes=20)

                with sim_state.lock:
                    sim_state.hp_rl_results = {
                        'avg_agent_rewards': avg_agent_rewards,
                        'avg_swarm_reward': avg_swarm_reward,
                        'policies': hp_policies,
                        'per_profile': per_profile_summary,
                        'agent_profiles': [a.profile.name if a.profile else 'Neutral' for a in sim_state.agents]
                    }
                    # Persist aggregated JSON including HP-RL optimal per-profile weights
                    try:
                        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                        json_filename = f'aggregated_experiments_{total_tests}tests_{timestamp}.json'
                        payload = {
                            'aggregated_results': sim_state.all_test_results,
                            'hp_rl_results': sim_state.hp_rl_results
                        }
                        # Sanitize payload to remove NaN/Infinity and numpy scalars
                        safe_payload = _sanitize_for_json(payload)
                        with open(json_filename, 'w', encoding='utf-8') as jf:
                            json.dump(safe_payload, jf, indent=2)
                        with sim_state.lock:
                            sim_state.experiment_json = json_filename
                        print(f"Aggregated JSON saved to: {json_filename}")
                    except Exception as je:
                        print(f"Failed to save aggregated JSON: {je}")
            except Exception as e:
                print(f"HP-RL training/eval error: {e}")
                with sim_state.lock:
                    sim_state.hp_rl_results = None

        with sim_state.lock:
            sim_state.experiments_running = False

        return jsonify({
            'status': 'success',
            'message': f'Test {test_number}/{total_tests} completed! {len(results)} experiments run.',
            'csv_filename': sim_state.experiment_csv,
            'summary': summary,
            'results_count': len(results),
            'total_accumulated': len(sim_state.all_test_results)
        })

    except Exception as e:
        with sim_state.lock:
            sim_state.experiments_running = False
        print(f"Experiments error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/experiments_status')
def experiments_status():
    """Get current experiment status"""
    if not sim_state.initialized:
        return jsonify({'error': 'Simulation not initialized'}), 400
    
    progress = sim_state.exploration_map.get_exploration_percentage()
    
    return jsonify({
        'exploration_complete': progress >= 100.0,
        'exploration_progress': progress,
        'experiments_running': sim_state.experiments_running,
        'experiments_completed': sim_state.experiment_results is not None,
        'csv_available': sim_state.experiment_csv is not None,
        'json_available': sim_state.experiment_json is not None,
        'json_filename': sim_state.experiment_json
    })


@app.route('/hp_rl_results')
def get_hp_rl_results():
    """Return Boids hyperparameter-RL evaluation results (if available)"""
    if not sim_state.initialized:
        return jsonify({'error': 'Simulation not initialized'}), 400
    if sim_state.hp_rl_results is None:
        return jsonify({'error': 'HP-RL results not available'}), 400
    return jsonify(sim_state.hp_rl_results)


@app.route('/experiment_json')
def get_experiment_json():
    """Return aggregated experiment results and HP-RL results as JSON."""
    if not sim_state.initialized:
        return jsonify({'error': 'Simulation not initialized'}), 400

    # If we have a saved JSON file, try to load and return it
    if sim_state.experiment_json and os.path.exists(sim_state.experiment_json):
        try:
            with open(sim_state.experiment_json, 'r', encoding='utf-8') as jf:
                payload = json.load(jf)
            return jsonify(payload)
        except Exception as e:
            print(f"Failed to read experiment_json file: {e}")

    # Fallback: assemble payload from in-memory state
    with sim_state.lock:
        payload = {
            'aggregated_results': sim_state.all_test_results or [],
            'hp_rl_results': sim_state.hp_rl_results
        }
    return jsonify(payload)


@app.route('/download_experiment_json')
def download_experiment_json():
    """Download the aggregated experiment JSON file if available."""
    if not sim_state.initialized:
        return jsonify({'error': 'Simulation not initialized'}), 400
    if sim_state.experiment_json and os.path.exists(sim_state.experiment_json):
        try:
            return send_file(
                sim_state.experiment_json,
                as_attachment=True,
                download_name=os.path.basename(sim_state.experiment_json),
                mimetype='application/json'
            )
        except Exception as e:
            print(f"Download experiment JSON error: {e}")
            return jsonify({'error': str(e)}), 500

    # If file not present, return current payload
    return get_experiment_json()

@app.route('/experiment_progress')
def get_experiment_progress():
    """Get real-time experiment progress for progress bar"""
    return jsonify({
        'current': experiment_progress['current'],
        'total': experiment_progress['total'],
        'running': experiment_progress['running'],
        'phase': experiment_progress['phase'],
        'percentage': (experiment_progress['current'] / experiment_progress['total'] * 100) if experiment_progress['total'] > 0 else 0
    })

@app.route('/download_experiment_csv')
def download_experiment_csv():
    """Download the experiment results CSV file"""
    if not sim_state.initialized or not sim_state.experiment_csv:
        return jsonify({'error': 'No experiment results available'}), 400
    
    try:
        return send_file(
            sim_state.experiment_csv,
            as_attachment=True,
            download_name=sim_state.experiment_csv,
            mimetype='text/csv'
        )
    except Exception as e:
        print(f"Download experiment CSV error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/experiment_summary')
def experiment_summary():
    """Get summary of experiment results"""
    if not sim_state.initialized or not sim_state.experiment_results:
        return jsonify({'error': 'No experiment results available'}), 400
    
    try:
        from experiments import PathfindingExperiments
        experiments = PathfindingExperiments(sim_state.exploration_map, sim_state.pathfinder)
        summary = experiments.get_experiment_summary(sim_state.experiment_results)
        
        return jsonify({
            'status': 'success',
            'summary': summary,
            'total_experiments': len(sim_state.experiment_results)
        })
        
    except Exception as e:
        print(f"Experiment summary error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/run_pathfinding_comparison', methods=['POST'])
def run_pathfinding_comparison():
    """Run comprehensive pathfinding algorithm comparison across profile scenarios"""
    if not sim_state.initialized:
        return jsonify({'error': 'Simulation not initialized'}), 400
    
    data = request.json or {}
    start_pos = data.get('start')
    goal_pos = data.get('goal')
    
    if not start_pos or not goal_pos:
        return jsonify({'error': 'Missing start or goal position'}), 400
    
    try:
        start_world = np.array([start_pos['x'], start_pos['y']])
        goal_world = np.array([goal_pos['x'], goal_pos['y']])
        
        print(f"\nStarting pathfinding comparison...")
        print(f"Start: {start_world}, Goal: {goal_world}")
        
        # Create comparator
        comparator = PathfindingComparator(sim_state.exploration_map)
        
        # Run comparison
        all_results = comparator.run_comparison(start_world, goal_world, num_tests=1)
        
        # Generate CSV
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = f'pathfinding_comparison_{timestamp}.csv'
        csv_file = comparator.generate_comparison_csv(all_results, csv_filename)
        
        # Store for download
        sim_state.comparison_csv = csv_filename
        
        # Prepare summary response
        summary_data = {}
        for scenario in ['offensive', 'neutral', 'defensive', 'dynamic']:
            summary_data[scenario] = {}
            scenario_results = comparator.results[scenario]
            
            for algo_name in ['dijkstra', 'astar', 'safety_first', 'balanced']:
                algo_results = [r for r in scenario_results if r['algorithm'] == algo_name]
                if algo_results:
                    best = min(algo_results, key=lambda x: x['total_cost'])
                    summary_data[scenario][algo_name] = {
                        'cost': float(best['total_cost']),
                        'path_length': int(best['path_length']),
                        'avg_threat': float(best['avg_threat']),
                        'threat_exposure': float(best['threat_exposure_ratio'])
                    }
        
        return jsonify({
            'status': 'success',
            'message': f'Comparison completed. Results: {csv_filename}',
            'csv_filename': csv_filename,
            'summary': summary_data
        })
        
    except Exception as e:
        print(f"Pathfinding comparison error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/download_comparison_csv')
def download_comparison_csv():
    """Download the pathfinding comparison CSV file"""
    if not sim_state.initialized or not hasattr(sim_state, 'comparison_csv') or not sim_state.comparison_csv:
        return jsonify({'error': 'No comparison results available'}), 400
    
    try:
        return send_file(
            sim_state.comparison_csv,
            as_attachment=True,
            download_name=sim_state.comparison_csv,
            mimetype='text/csv'
        )
    except Exception as e:
        print(f"Download comparison CSV error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_nest_position')
def get_nest_position():
    """Get the current nest position for agent deployment"""
    if not sim_state.initialized:
        return jsonify({'error': 'Simulation not initialized'}), 400
    
    pos = sim_state.nest_position
    return jsonify({
        'x': float(pos['x']),
        'y': float(pos['y']),
        'z': float(pos['z'])
    })

@app.route('/deploy_agent', methods=['POST'])
def deploy_agent():
    """Deploy a new agent from the nest position"""
    if not sim_state.initialized:
        return jsonify({'error': 'Simulation not initialized'}), 400
    
    try:
        # Create a new agent at the nest position with random initial velocity
        pos = sim_state.nest_position
        position = np.array([pos['x'], pos['y'], pos['z']])
        velocity = np.random.uniform(-1, 1, 3)
        velocity = velocity / np.linalg.norm(velocity) * 0.5  # Normalize and scale

        new_agent = Agent(position, velocity, max_speed=2.0, max_force=0.03, profile=NEUTRAL)
        new_agent.exploration_map = sim_state.exploration_map

        with sim_state.lock:
            sim_state.agents.append(new_agent)
            agent_count = len(sim_state.agents)

        return jsonify({
            'success': True,
            'agent_count': agent_count,
            'position': position.tolist()
        })
    except Exception as e:
        print(f"Deploy agent error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/set_manual_path', methods=['POST'])
def set_manual_path():
    """Set a manual path for swarm navigation"""
    if not sim_state.initialized:
        return jsonify({'error': 'Simulation not initialized'}), 400
    
    try:
        data = request.get_json()
        waypoints = data.get('waypoints', [])
        
        # Convert waypoints to numpy arrays and set under lock
        manual = [np.array([w['x'], w['y'], w['z']]) for w in waypoints]
        with sim_state.lock:
            sim_state.manual_path = manual
        
        return jsonify({
            'success': True,
            'waypoint_count': len(manual)
        })
    except Exception as e:
        print(f"Set manual path error: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(
        host=os.environ.get('SWARM_HOST', '127.0.0.1'),
        port=int(os.environ.get('SWARM_PORT', '5000')),
        debug=os.environ.get('SWARM_DEBUG', '0') == '1',
        use_reloader=False,
    )
