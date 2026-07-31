"""
Pathfinding algorithms for navigating through the threat map.
Implements multiple pathfinding strategies with formation-profile-aware cost calculation.

All algorithms consider:
- Threat levels affecting traversal cost
- Formation profiles (Offensive, Neutral, Defensive) affecting movement speed
- Dynamic switching between safety and speed based on local threat levels
"""
import numpy as np
import heapq
from collections import defaultdict
from profiles import OFFENSIVE, NEUTRAL, DEFENSIVE

class PathFinder:
    """Handles pathfinding through the exploration map's threat grid"""
    
    def __init__(self, exploration_map):
        self.exploration_map = exploration_map
        self.grid_size = exploration_map.resolution
        self.threat_map = exploration_map.threat_map
        
        # 3D pathfinding settings
        self.use_3d_exploration = True  # Block paths through unexplored 3D cells
        self.grid_size_3d = 25  # 3D grid resolution (matches frontend)
        
        # Threat tolerance threshold for balanced algorithm
        # Above this threshold, prioritize safety; below it, prioritize speed
        self.THREAT_TOLERANCE = 0.3
        
        # Formation profile movement speed modifiers
        # Based on how different profiles affect swarm velocity in threat areas
        self.PROFILE_SPEED_MODIFIERS = {
            'offensive': 1.0,    # Full speed, minimal formation constraint
            'neutral': 0.75,     # Moderate speed reduction for coordination
            'defensive': 0.5     # Significant speed reduction for tight formation
        }
        
    def world_to_grid(self, world_pos):
        """Convert world coordinates to grid coordinates"""
        grid_x = int(world_pos[0] / self.exploration_map.cell_size_x)
        grid_y = int(world_pos[1] / self.exploration_map.cell_size_y)
        return max(0, min(grid_x, self.grid_size - 1)), max(0, min(grid_y, self.grid_size - 1))
    
    def grid_to_world(self, grid_pos):
        """Convert grid coordinates to world coordinates"""
        world_x = (grid_pos[0] + 0.5) * self.exploration_map.cell_size_x
        world_y = (grid_pos[1] + 0.5) * self.exploration_map.cell_size_y
        return np.array([world_x, world_y])
    
    def get_neighbors(self, pos):
        """Get valid neighboring positions (8-connected)"""
        x, y = pos
        neighbors = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.grid_size and 0 <= ny < self.grid_size:
                    # Check if this position is traversable (explored in 3D)
                    if self.use_3d_exploration and not self.is_position_explored_3d(nx, ny):
                        continue  # Skip unexplored positions
                    neighbors.append((nx, ny))
        return neighbors
    
    def is_position_explored_3d(self, grid_x, grid_y, grid_z=None):
        """Check if a 2D grid position has been explored in 3D space
        
        For pathfinding, we check if at least one Z-level at this XY position
        has been explored, allowing agents to find paths through explored corridors.
        """
        # Convert 2D grid to world coordinates
        world_x = (grid_x + 0.5) * self.exploration_map.cell_size_x
        world_y = (grid_y + 0.5) * self.exploration_map.cell_size_y
        
        # Check if any Z-level at this XY has been explored
        if hasattr(self.exploration_map, 'explored_grid_3d'):
            # Convert to 3D grid coordinates
            cell_size_3d = self.exploration_map.cell_size_3d
            gx = int(world_x / cell_size_3d)
            gy = int(world_y / cell_size_3d)
            
            gx = max(0, min(self.grid_size_3d - 1, gx))
            gy = max(0, min(self.grid_size_3d - 1, gy))
            
            # Check all Z-levels at this XY position
            for gz in range(self.grid_size_3d):
                if self.exploration_map.explored_grid_3d[gx, gy, gz]:
                    return True
            return False
        
        # Fallback to 2D exploration check
        return self.exploration_map.explored_grid[grid_y, grid_x]
    
    def get_formation_profile_for_threat(self, threat_level):
        """Determine which formation profile the swarm would adopt at this threat level"""
        if threat_level < 0.3:
            return 'offensive'
        elif threat_level < 0.7:
            return 'neutral'
        else:
            return 'defensive'
    
    def get_formation_cost_multiplier(self, pos):
        """Calculate cost multiplier based on formation profile needed at this position
        
        Higher threat areas require defensive formations which slow movement.
        This represents the real cost of traversing that tile considering formation changes.
        """
        x, y = pos
        threat = self.threat_map[y, x]
        
        # Determine which profile swarm would use
        profile = self.get_formation_profile_for_threat(threat)
        speed_modifier = self.PROFILE_SPEED_MODIFIERS[profile]
        
        # Cost is inversely proportional to speed
        # Lower speed = higher traversal time = higher cost
        formation_cost_multiplier = 1.0 / speed_modifier
        
        return formation_cost_multiplier
    
    def get_cost(self, pos):
        """Get movement cost for a position (considers threat + formation speed penalty)
        
        This is used by Dijkstra - focuses on actual traversal cost.
        """
        x, y = pos
        threat = self.threat_map[y, x]
        
        # Base distance cost
        base_cost = 1.0
        
        # Formation-based speed penalty
        formation_multiplier = self.get_formation_cost_multiplier(pos)
        
        # Threat penalty (higher threat = additional cost)
        threat_penalty = threat * 5.0
        
        # Total cost = base cost affected by formation speed + threat danger
        return base_cost * formation_multiplier + threat_penalty
    
    def heuristic(self, pos, goal):
        """Euclidean distance heuristic for A*"""
        return np.sqrt((pos[0] - goal[0])**2 + (pos[1] - goal[1])**2)
    
    ##==============================================================================##
    ##                         DIJKSTRA ALGORITHM                                   ##
    ##==============================================================================##
    ## Finds shortest path considering formation-based movement costs               ##
    ## Cost = base_distance * formation_speed_multiplier + threat_penalty          ##
    ##==============================================================================##
    
    def dijkstra(self, start_world, goal_world):
        """Dijkstra's algorithm implementation with safety measures"""
        start = self.world_to_grid(start_world)
        goal = self.world_to_grid(goal_world)
        
        print(f"  Grid start: {start}, Grid goal: {goal}")
        
        # Safety check
        if start == goal:
            return [self.grid_to_world(start)], 0.0
        
        # Priority queue: (cost, position)
        pq = [(0, start)]
        distances = defaultdict(lambda: float('inf'))
        distances[start] = 0
        previous = {}
        visited = set()
        max_iterations = self.grid_size * self.grid_size  # Prevent infinite loops
        iterations = 0
        
        while pq and iterations < max_iterations:
            iterations += 1
            current_cost, current = heapq.heappop(pq)
            
            if current in visited:
                continue
                
            visited.add(current)
            
            if current == goal:
                print(f"  Found goal after {iterations} iterations")
                break
                
            for neighbor in self.get_neighbors(current):
                if neighbor in visited:
                    continue
                    
                new_cost = current_cost + self.get_cost(neighbor)
                
                if new_cost < distances[neighbor]:
                    distances[neighbor] = new_cost
                    previous[neighbor] = current
                    heapq.heappush(pq, (new_cost, neighbor))
        
        if iterations >= max_iterations:
            print(f"Dijkstra reached max iterations ({max_iterations})")
            return [], float('inf')
        
        # Reconstruct path
        if goal not in previous and goal != start:
            print(f"No path found to goal")
            return [], float('inf')
            
        path = []
        current = goal
        while current in previous:
            path.append(current)
            current = previous[current]
        path.append(start)
        path.reverse()
        
        # Convert to world coordinates
        world_path = [self.grid_to_world(pos) for pos in path]
        total_cost = distances[goal] if goal in distances else float('inf')
        
        print(f"  Path reconstructed: {len(path)} nodes")
        return world_path, total_cost
    
    ##==============================================================================##
    ##                            A* ALGORITHM                                      ##
    ##==============================================================================##
    ## Optimized shortest path using heuristic guidance                             ##
    ## Cost = base_distance * formation_speed_multiplier + threat_penalty          ##
    ## Heuristic = Euclidean distance to goal                                      ##
    ##==============================================================================##
    
    def astar(self, start_world, goal_world):
        """A* algorithm implementation with safety measures"""
        start = self.world_to_grid(start_world)
        goal = self.world_to_grid(goal_world)
        
        print(f"  Grid start: {start}, Grid goal: {goal}")
        
        # Safety check
        if start == goal:
            return [self.grid_to_world(start)], 0.0
        
        # Priority queue: (f_score, position)
        pq = [(0, start)]
        g_scores = defaultdict(lambda: float('inf'))
        g_scores[start] = 0
        f_scores = defaultdict(lambda: float('inf'))
        f_scores[start] = self.heuristic(start, goal)
        previous = {}
        visited = set()
        max_iterations = self.grid_size * self.grid_size  # Prevent infinite loops
        iterations = 0
        
        while pq and iterations < max_iterations:
            iterations += 1
            current_f, current = heapq.heappop(pq)
            
            if current in visited:
                continue
                
            visited.add(current)
            
            if current == goal:
                print(f"  Found goal after {iterations} iterations")
                break
                
            for neighbor in self.get_neighbors(current):
                if neighbor in visited:
                    continue
                    
                tentative_g = g_scores[current] + self.get_cost(neighbor)
                
                if tentative_g < g_scores[neighbor]:
                    previous[neighbor] = current
                    g_scores[neighbor] = tentative_g
                    f_scores[neighbor] = tentative_g + self.heuristic(neighbor, goal)
                    heapq.heappush(pq, (f_scores[neighbor], neighbor))
        
        if iterations >= max_iterations:
            print(f"A* reached max iterations ({max_iterations})")
            return [], float('inf')
        
        # Reconstruct path
        if goal not in previous and goal != start:
            print(f"No path found to goal")
            return [], float('inf')
            
        path = []
        current = goal
        while current in previous:
            path.append(current)
            current = previous[current]
        path.append(start)
        path.reverse()
        
        # Convert to world coordinates
        world_path = [self.grid_to_world(pos) for pos in path]
        total_cost = g_scores[goal] if goal in g_scores else float('inf')
        
        print(f"  Path reconstructed: {len(path)} nodes")
        return world_path, total_cost
    
    ##==============================================================================##
    ##                       SAFETY-FIRST ALGORITHM                                 ##
    ##==============================================================================##
    ## Prioritizes safest route over shortest distance                              ##
    ## Cost = minimal_base_cost * formation_multiplier + HEAVY_threat_penalty      ##
    ## Always considers formation speed reduction in threat areas                   ##
    ##==============================================================================##
    
    def get_safety_cost(self, pos):
        """Get safety-focused cost for a position (heavily penalizes threat areas)
        
        Still considers formation speed penalty but heavily weights threat avoidance.
        """
        x, y = pos
        threat = self.threat_map[y, x]
        
        # Minimal base cost (distance matters less)
        base_cost = 0.1
        
        # Formation speed penalty still applies
        formation_multiplier = self.get_formation_cost_multiplier(pos)
        
        # Very heavy threat penalty for safety
        threat_penalty = threat * 50.0
        
        return base_cost * formation_multiplier + threat_penalty
    
    ##==============================================================================##
    ##                    BALANCED ALGORITHM (50/50 APPROACH)                       ##
    ##==============================================================================##
    ## Balanced pathfinding with equal weighting of distance and safety             ##
    ## Cost = formation_multiplier * (0.5 * distance + 0.5 * safety)               ##
    ## Provides moderate path without extreme optimizations for either criterion   ##
    ##==============================================================================##
    
    def get_balanced_cost(self, pos, goal):
        """Balanced cost combining distance and safety with equal weighting
        
        Uses 50/50 split between shortest path and safety considerations,
        with formation-aware speed penalties applied to all traversal costs.
        """
        x, y = pos
        threat = self.threat_map[y, x]
        
        # Formation multiplier (increases cost in high-threat areas)
        formation_multiplier = self.get_formation_cost_multiplier(pos)
        
        # Distance component (normalized by max possible distance)
        max_distance = np.sqrt(self.grid_size**2 + self.grid_size**2)
        distance_to_goal = self.heuristic(pos, goal) / max_distance
        
        # Safety component (threat level)
        safety_cost = threat * 10.0
        
        # Balanced: 0.5 weight for distance + 0.5 weight for safety
        # Then multiply by formation speed penalty
        return (0.5 * distance_to_goal + 0.5 * safety_cost) * formation_multiplier
    
    def safety_first(self, start_world, goal_world):
        """Safety-first pathfinding prioritizing safest route over shortest"""
        start = self.world_to_grid(start_world)
        goal = self.world_to_grid(goal_world)
        
        print(f"  Safety-first - Grid start: {start}, Grid goal: {goal}")
        
        # Safety check
        if start == goal:
            return [self.grid_to_world(start)], 0.0
        
        # Priority queue: (cost, position)
        pq = [(0, start)]
        distances = defaultdict(lambda: float('inf'))
        distances[start] = 0
        previous = {}
        visited = set()
        max_iterations = self.grid_size * self.grid_size
        iterations = 0
        
        while pq and iterations < max_iterations:
            iterations += 1
            current_cost, current = heapq.heappop(pq)
            
            if current in visited:
                continue
                
            visited.add(current)
            
            if current == goal:
                print(f"  Safety-first found goal after {iterations} iterations")
                break
                
            for neighbor in self.get_neighbors(current):
                if neighbor in visited:
                    continue
                    
                new_cost = current_cost + self.get_safety_cost(neighbor)
                
                if new_cost < distances[neighbor]:
                    distances[neighbor] = new_cost
                    previous[neighbor] = current
                    heapq.heappush(pq, (new_cost, neighbor))
        
        if iterations >= max_iterations:
            print(f"Safety-first reached max iterations ({max_iterations})")
            return [], float('inf')
        
        # Reconstruct path
        if goal not in previous and goal != start:
            print(f"Safety-first: No path found to goal")
            return [], float('inf')
            
        path = []
        current = goal
        while current in previous:
            path.append(current)
            current = previous[current]
        path.append(start)
        path.reverse()
        
        # Convert to world coordinates
        world_path = [self.grid_to_world(pos) for pos in path]
        total_cost = distances[goal] if goal in distances else float('inf')
        
        print(f"  Safety-first path reconstructed: {len(path)} nodes")
        return world_path, total_cost
    
    def balanced(self, start_world, goal_world):
        """Balanced pathfinding with 50/50 weight for distance and safety
        
        Uses equal weighting between shortest path and threat avoidance,
        modulated by formation-profile-aware speed penalties.
        """
        start = self.world_to_grid(start_world)
        goal = self.world_to_grid(goal_world)
        
        print(f"  Balanced (50/50) - Grid start: {start}, Grid goal: {goal}")
        
        # Safety check
        if start == goal:
            return [self.grid_to_world(start)], 0.0
        
        # Priority queue: (f_score, position)
        pq = [(0, start)]
        g_scores = defaultdict(lambda: float('inf'))
        g_scores[start] = 0
        f_scores = defaultdict(lambda: float('inf'))
        f_scores[start] = self.heuristic(start, goal)
        previous = {}
        visited = set()
        max_iterations = self.grid_size * self.grid_size
        iterations = 0
        
        while pq and iterations < max_iterations:
            iterations += 1
            current_f, current = heapq.heappop(pq)
            
            if current in visited:
                continue
                
            visited.add(current)
            
            if current == goal:
                print(f"  Balanced found goal after {iterations} iterations")
                break
                
            for neighbor in self.get_neighbors(current):
                if neighbor in visited:
                    continue
                
                # Use balanced 50/50 cost calculation
                tentative_g = g_scores[current] + self.get_balanced_cost(neighbor, goal)
                
                if tentative_g < g_scores[neighbor]:
                    previous[neighbor] = current
                    g_scores[neighbor] = tentative_g
                    f_scores[neighbor] = tentative_g + self.heuristic(neighbor, goal)
                    heapq.heappush(pq, (f_scores[neighbor], neighbor))
        
        if iterations >= max_iterations:
            print(f"Balanced reached max iterations ({max_iterations})")
            return [], float('inf')
        
        # Reconstruct path
        if goal not in previous and goal != start:
            print(f"Balanced: No path found to goal")
            return [], float('inf')
            
        path = []
        current = goal
        while current in previous:
            path.append(current)
            current = previous[current]
        path.append(start)
        path.reverse()
        
        # Convert to world coordinates
        world_path = [self.grid_to_world(pos) for pos in path]
        total_cost = g_scores[goal] if goal in g_scores else float('inf')
        
        print(f"  Balanced path reconstructed: {len(path)} nodes")
        return world_path, total_cost


##==============================================================================##
##                   PATHFINDING COMPARISON SYSTEM                              ##
##==============================================================================##
## Comprehensive algorithm evaluation across formation profile scenarios        ##
##==============================================================================##

import csv
import datetime


class PathfindingComparator:
    """Compares pathfinding algorithms under different profile scenarios"""
    
    def __init__(self, exploration_map):
        self.exploration_map = exploration_map
        self.pathfinder = PathFinder(exploration_map)
        
        # Store results for each scenario
        self.results = {
            'offensive': [],
            'neutral': [],
            'defensive': [],
            'dynamic': []
        }
        
        # Profile configurations for cost multiplier overrides
        self.profile_configs = {
            'offensive': {
                'speed_modifiers': {
                    'offensive': 1.0,
                    'neutral': 1.0,
                    'defensive': 1.0
                },
                'description': 'All areas use Offensive profile speed (1.0x)'
            },
            'neutral': {
                'speed_modifiers': {
                    'offensive': 0.75,
                    'neutral': 0.75,
                    'defensive': 0.75
                },
                'description': 'All areas use Neutral profile speed (0.75x)'
            },
            'defensive': {
                'speed_modifiers': {
                    'offensive': 0.5,
                    'neutral': 0.5,
                    'defensive': 0.5
                },
                'description': 'All areas use Defensive profile speed (0.5x)'
            },
            'dynamic': {
                'speed_modifiers': {
                    'offensive': 1.0,
                    'neutral': 0.75,
                    'defensive': 0.5
                },
                'description': 'Dynamic profile switching based on threat (adaptive)'
            }
        }
        
    def apply_profile_scenario(self, scenario):
        """Apply speed modifier overrides for a specific scenario"""
        modifiers = self.profile_configs[scenario]['speed_modifiers']
        self.pathfinder.PROFILE_SPEED_MODIFIERS = modifiers.copy()
        
    def restore_dynamic_modifiers(self):
        """Restore dynamic profile modifiers"""
        self.pathfinder.PROFILE_SPEED_MODIFIERS = {
            'offensive': 1.0,
            'neutral': 0.75,
            'defensive': 0.5
        }
    
    def calculate_threat_weighted_cost(self, path):
        """Calculate average threat along a path"""
        if not path or len(path) < 2:
            return 0.0
        
        threat_values = []
        for pos in path:
            # Convert world coordinates to grid
            grid_pos = self.pathfinder.world_to_grid(pos)
            x, y = grid_pos
            threat = self.exploration_map.threat_map[y, x]
            threat_values.append(threat)
        
        return np.mean(threat_values) if threat_values else 0.0
    
    def calculate_path_metrics(self, path, cost, scenario, algorithm):
        """Calculate comprehensive metrics for a path"""
        if not path:
            return None
        
        # Path length in grid cells
        path_length = len(path)
        
        # Total world distance
        world_distance = 0.0
        for i in range(len(path) - 1):
            world_distance += np.linalg.norm(path[i+1] - path[i])
        
        # Threat exposure
        avg_threat = self.calculate_threat_weighted_cost(path)
        
        # Count cells in high-threat areas (>0.7)
        high_threat_cells = 0
        medium_threat_cells = 0
        low_threat_cells = 0
        for pos in path:
            grid_pos = self.pathfinder.world_to_grid(pos)
            x, y = grid_pos
            threat = self.exploration_map.threat_map[y, x]
            if threat >= 0.7:
                high_threat_cells += 1
            elif threat >= 0.3:
                medium_threat_cells += 1
            else:
                low_threat_cells += 1
        
        return {
            'scenario': scenario,
            'algorithm': algorithm,
            'path_length': path_length,
            'world_distance': world_distance,
            'total_cost': cost,
            'cost_per_node': cost / path_length if path_length > 0 else 0,
            'avg_threat': avg_threat,
            'high_threat_cells': high_threat_cells,
            'medium_threat_cells': medium_threat_cells,
            'low_threat_cells': low_threat_cells,
            'threat_exposure_ratio': high_threat_cells / path_length if path_length > 0 else 0
        }
    
    def run_comparison(self, start_world, goal_world, num_tests=1):
        """Run pathfinding comparison across all scenarios and algorithms"""
        print(f"\n{'='*80}")
        print(f"PATHFINDING ALGORITHM COMPARISON")
        print(f"{'='*80}")
        print(f"Start: {start_world}")
        print(f"Goal: {goal_world}")
        print(f"Tests per scenario: {num_tests}\n")
        
        all_results = []
        
        # Test each scenario
        scenarios = ['offensive', 'neutral', 'defensive', 'dynamic']
        
        for scenario in scenarios:
            scenario_results = []
            
            # Apply scenario profile modifiers
            if scenario != 'dynamic':
                self.apply_profile_scenario(scenario)
            else:
                self.restore_dynamic_modifiers()
            
            print(f"\n{'-'*80}")
            print(f"SCENARIO: {scenario.upper()}")
            print(f"Description: {self.profile_configs[scenario]['description']}")
            print(f"{'-'*80}")
            
            # Test each algorithm
            algorithms = [
                ('dijkstra', self.pathfinder.dijkstra),
                ('astar', self.pathfinder.astar),
                ('safety_first', self.pathfinder.safety_first),
                ('balanced', self.pathfinder.balanced)
            ]
            
            for algo_name, algo_func in algorithms:
                print(f"\n  Testing {algo_name.upper()}...")
                algo_costs = []
                algo_paths = []
                
                # Run multiple tests
                for test_num in range(num_tests):
                    try:
                        path, cost = algo_func(start_world, goal_world)
                        
                        if path:
                            algo_costs.append(cost)
                            algo_paths.append(path)
                            print(f"    Test {test_num + 1}: Path length={len(path)}, Cost={cost:.4f}")
                        else:
                            print(f"    Test {test_num + 1}: No path found")
                            
                    except Exception as e:
                        print(f"    Test {test_num + 1}: Error - {e}")
                
                # Calculate average metrics
                if algo_paths:
                    avg_cost = np.mean(algo_costs)
                    best_path_idx = np.argmin(algo_costs)
                    best_path = algo_paths[best_path_idx]
                    best_cost = algo_costs[best_path_idx]
                    
                    metrics = self.calculate_path_metrics(best_path, best_cost, scenario, algo_name)
                    if metrics:
                        scenario_results.append(metrics)
                        print(f"    BEST: Cost={best_cost:.4f}, Length={len(best_path)}, AvgThreat={metrics['avg_threat']:.4f}")
                
                all_results.extend(scenario_results)
            
            # Store scenario results
            self.results[scenario] = scenario_results
        
        # Restore dynamic modifiers
        self.restore_dynamic_modifiers()
        
        return all_results
    
    def generate_comparison_csv(self, all_results, output_filename=None):
        """Generate comprehensive CSV report"""
        if not output_filename:
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            output_filename = f'pathfinding_comparison_{timestamp}.csv'
        
        print(f"\n\nGenerating CSV report: {output_filename}")
        
        with open(output_filename, 'w', newline='', encoding='utf-8') as csvfile:
            # Write header with profile information
            csvfile.write('PATHFINDING ALGORITHM COMPARISON REPORT\n')
            csvfile.write('='*80 + '\n')
            csvfile.write(f'Generated: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
            csvfile.write(f'Test Scenarios: {len(self.profile_configs)}\n')
            csvfile.write(f'Algorithms Tested: 4 (Dijkstra, A*, Safety-First, Balanced)\n')
            csvfile.write('='*80 + '\n\n')
            
            # Write profile scenario descriptions
            csvfile.write('PROFILE SCENARIOS TESTED:\n')
            csvfile.write('-'*80 + '\n')
            for scenario, config in self.profile_configs.items():
                csvfile.write(f"{scenario.upper()}:\n")
                csvfile.write(f"  Description: {config['description']}\n")
                csvfile.write(f"  Speed Modifiers: Offensive={config['speed_modifiers']['offensive']}x, "
                            f"Neutral={config['speed_modifiers']['neutral']}x, "
                            f"Defensive={config['speed_modifiers']['defensive']}x\n")
                csvfile.write('\n')
            
            csvfile.write('\n')
            csvfile.write('='*80 + '\n')
            csvfile.write('DETAILED PATHFINDING RESULTS\n')
            csvfile.write('='*80 + '\n')
            
            # Determine fieldnames
            if all_results:
                fieldnames = ['scenario', 'profile_description', 'algorithm', 'path_length', 'world_distance',
                            'total_cost', 'cost_per_node', 'avg_threat',
                            'high_threat_cells', 'medium_threat_cells', 'low_threat_cells',
                            'threat_exposure_ratio']
            else:
                fieldnames = [
                    'scenario', 'profile_description', 'algorithm', 'path_length', 'world_distance',
                    'total_cost', 'cost_per_node', 'avg_threat',
                    'high_threat_cells', 'medium_threat_cells', 'low_threat_cells',
                    'threat_exposure_ratio'
                ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            # Write header
            writer.writeheader()
            
            # Write data rows
            for result in all_results:
                # Get profile description for this scenario
                profile_desc = self.profile_configs[result['scenario']]['description']
                
                writer.writerow({
                    'scenario': result['scenario'].upper(),
                    'profile_description': profile_desc,
                    'algorithm': result['algorithm'].upper(),
                    'path_length': result['path_length'],
                    'world_distance': f"{result['world_distance']:.2f}",
                    'total_cost': f"{result['total_cost']:.4f}",
                    'cost_per_node': f"{result['cost_per_node']:.4f}",
                    'avg_threat': f"{result['avg_threat']:.4f}",
                    'high_threat_cells': result['high_threat_cells'],
                    'medium_threat_cells': result['medium_threat_cells'],
                    'low_threat_cells': result['low_threat_cells'],
                    'threat_exposure_ratio': f"{result['threat_exposure_ratio']:.4f}"
                })
            
            # Add comprehensive analysis sections
            self._write_analysis_sections(csvfile)
            
        print(f"CSV report saved: {output_filename}")
        return output_filename
    
    def _write_analysis_sections(self, csvfile):
        """Write all analysis sections to CSV"""
        # Analysis 1: Cheapest algorithm per profile
        csvfile.write('\n\n')
        csvfile.write('='*80 + '\n')
        csvfile.write('ANALYSIS 1: CHEAPEST ALGORITHM PER PROFILE SCENARIO\n')
        csvfile.write('='*80 + '\n')
        csvfile.write('Scenario,Winner Algorithm,Lowest Cost,Path Length,Cost Efficiency,Runner-up,Runner-up Cost\n')
        
        for scenario in ['offensive', 'neutral', 'defensive', 'dynamic']:
            scenario_results = self.results[scenario]
            if not scenario_results:
                continue
            
            sorted_results = sorted(scenario_results, key=lambda x: x['total_cost'])
            
            if len(sorted_results) >= 2:
                winner = sorted_results[0]
                runner_up = sorted_results[1]
                
                csvfile.write(f"{scenario.upper()},"
                            f"{winner['algorithm'].upper()},"
                            f"{winner['total_cost']:.4f},"
                            f"{winner['path_length']},"
                            f"{winner['cost_per_node']:.4f},"
                            f"{runner_up['algorithm'].upper()},"
                            f"{runner_up['total_cost']:.4f}\n")
        
        # Analysis 2: Profile constraint impact
        csvfile.write('\n\n')
        csvfile.write('='*80 + '\n')
        csvfile.write('ANALYSIS 2: PROFILE CONSTRAINT IMPACT ON PATH COSTS\n')
        csvfile.write('='*80 + '\n')
        csvfile.write('Algorithm,Offensive Cost,Neutral Cost,Defensive Cost,Defensive vs Offensive Increase %,Formation Penalty Impact\n')
        
        for algo_name in ['dijkstra', 'astar', 'safety_first', 'balanced']:
            costs_by_scenario = {}
            for scenario in ['offensive', 'neutral', 'defensive']:
                scenario_results = self.results[scenario]
                algo_results = [r for r in scenario_results if r['algorithm'] == algo_name]
                if algo_results:
                    costs_by_scenario[scenario] = algo_results[0]['total_cost']
            
            if 'offensive' in costs_by_scenario and 'defensive' in costs_by_scenario:
                cost_increase_pct = ((costs_by_scenario['defensive'] - costs_by_scenario['offensive']) / 
                                    costs_by_scenario['offensive'] * 100)
                
                if cost_increase_pct > 50:
                    impact = "HIGH"
                elif cost_increase_pct > 25:
                    impact = "MODERATE"
                else:
                    impact = "LOW"
                
                csvfile.write(f"{algo_name.upper()},"
                            f"{costs_by_scenario.get('offensive', 'N/A'):.4f},"
                            f"{costs_by_scenario.get('neutral', 'N/A'):.4f},"
                            f"{costs_by_scenario.get('defensive', 'N/A'):.4f},"
                            f"{cost_increase_pct:.2f}%,"
                            f"{impact}\n")
        
        # Analysis 3: Dynamic vs static
        csvfile.write('\n\n')
        csvfile.write('='*80 + '\n')
        csvfile.write('ANALYSIS 3: DYNAMIC VS STATIC PROFILE PERFORMANCE\n')
        csvfile.write('='*80 + '\n')
        csvfile.write('Algorithm,Dynamic Cost,Best Static Cost,Best Static Profile,Cost Advantage %,Performance Verdict\n')
        
        for algo_name in ['dijkstra', 'astar', 'safety_first', 'balanced']:
            dynamic_results = self.results['dynamic']
            dynamic_algo = [r for r in dynamic_results if r['algorithm'] == algo_name]
            
            if not dynamic_algo:
                continue
            
            dynamic_cost = dynamic_algo[0]['total_cost']
            
            static_costs = {}
            for scenario in ['offensive', 'neutral', 'defensive']:
                scenario_results = self.results[scenario]
                algo_results = [r for r in scenario_results if r['algorithm'] == algo_name]
                if algo_results:
                    static_costs[scenario] = algo_results[0]['total_cost']
            
            if static_costs:
                best_static_profile = min(static_costs, key=static_costs.get)
                best_static_cost = static_costs[best_static_profile]
                
                advantage_pct = ((best_static_cost - dynamic_cost) / best_static_cost * 100)
                
                if advantage_pct > 5:
                    verdict = "DYNAMIC BETTER"
                elif advantage_pct < -5:
                    verdict = "STATIC BETTER"
                else:
                    verdict = "COMPARABLE"
                
                csvfile.write(f"{algo_name.upper()},"
                            f"{dynamic_cost:.4f},"
                            f"{best_static_cost:.4f},"
                            f"{best_static_profile.upper()},"
                            f"{advantage_pct:.2f}%,"
                            f"{verdict}\n")
        
        # Analysis 4: Threat exposure
        csvfile.write('\n\n')
        csvfile.write('='*80 + '\n')
        csvfile.write('ANALYSIS 4: THREAT EXPOSURE TRADE-OFFS\n')
        csvfile.write('='*80 + '\n')
        csvfile.write('Algorithm,Avg Path Cost,Avg Threat Level,High Threat Cells,Threat Exposure Ratio,Risk vs Cost Profile\n')
        
        for algo_name in ['dijkstra', 'astar', 'safety_first', 'balanced']:
            all_algo_results = []
            for scenario in ['offensive', 'neutral', 'defensive', 'dynamic']:
                scenario_results = self.results[scenario]
                algo_results = [r for r in scenario_results if r['algorithm'] == algo_name]
                all_algo_results.extend(algo_results)
            
            if all_algo_results:
                avg_cost = np.mean([r['total_cost'] for r in all_algo_results])
                avg_threat = np.mean([r['avg_threat'] for r in all_algo_results])
                avg_high_threat = np.mean([r['high_threat_cells'] for r in all_algo_results])
                avg_exposure = np.mean([r['threat_exposure_ratio'] for r in all_algo_results])
                
                if avg_exposure < 0.1:
                    risk_profile = "LOW RISK / HIGH COST"
                elif avg_exposure < 0.3:
                    risk_profile = "MODERATE RISK / MODERATE COST"
                else:
                    risk_profile = "HIGH RISK / LOW COST"
                
                csvfile.write(f"{algo_name.upper()},"
                            f"{avg_cost:.4f},"
                            f"{avg_threat:.4f},"
                            f"{avg_high_threat:.2f},"
                            f"{avg_exposure:.4f},"
                            f"{risk_profile}\n")
        
        # Analysis 5: Cost efficiency
        csvfile.write('\n\n')
        csvfile.write('='*80 + '\n')
        csvfile.write('ANALYSIS 5: COST EFFICIENCY COMPARISON (Cost Per Node)\n')
        csvfile.write('='*80 + '\n')
        csvfile.write('Algorithm,Offensive Efficiency,Neutral Efficiency,Defensive Efficiency,Dynamic Efficiency,Most Efficient Scenario\n')
        
        for algo_name in ['dijkstra', 'astar', 'safety_first', 'balanced']:
            efficiency_by_scenario = {}
            for scenario in ['offensive', 'neutral', 'defensive', 'dynamic']:
                scenario_results = self.results[scenario]
                algo_results = [r for r in scenario_results if r['algorithm'] == algo_name]
                if algo_results:
                    efficiency_by_scenario[scenario] = algo_results[0]['cost_per_node']
            
            if efficiency_by_scenario:
                most_efficient = min(efficiency_by_scenario, key=efficiency_by_scenario.get)
                
                csvfile.write(f"{algo_name.upper()},"
                            f"{efficiency_by_scenario.get('offensive', 'N/A'):.4f},"
                            f"{efficiency_by_scenario.get('neutral', 'N/A'):.4f},"
                            f"{efficiency_by_scenario.get('defensive', 'N/A'):.4f},"
                            f"{efficiency_by_scenario.get('dynamic', 'N/A'):.4f},"
                            f"{most_efficient.upper()}\n")
        
        # Analysis 6: Recommendations
        csvfile.write('\n\n')
        csvfile.write('='*80 + '\n')
        csvfile.write('ANALYSIS 6: OVERALL RECOMMENDATIONS\n')
        csvfile.write('='*80 + '\n')
        
        csvfile.write('\nBest Algorithm by Scenario:\n')
        for scenario in ['offensive', 'neutral', 'defensive', 'dynamic']:
            scenario_results = self.results[scenario]
            if scenario_results:
                best = min(scenario_results, key=lambda x: x['total_cost'])
                csvfile.write(f"{scenario.upper()}: {best['algorithm'].upper()} "
                            f"(Cost: {best['total_cost']:.4f}, Threat: {best['avg_threat']:.4f})\n")
        
        csvfile.write('\nSafest Algorithm (Lowest Threat Exposure):\n')
        all_results_flat = []
        for scenario_results in self.results.values():
            all_results_flat.extend(scenario_results)
        
        if all_results_flat:
            safest = min(all_results_flat, key=lambda x: x['threat_exposure_ratio'])
            csvfile.write(f"{safest['algorithm'].upper()} in {safest['scenario'].upper()} profile "
                        f"(Exposure: {safest['threat_exposure_ratio']:.4f}, Cost: {safest['total_cost']:.4f})\n")
        
        csvfile.write('\nMost Cost-Efficient Algorithm:\n')
        if all_results_flat:
            most_efficient = min(all_results_flat, key=lambda x: x['cost_per_node'])
            csvfile.write(f"{most_efficient['algorithm'].upper()} in {most_efficient['scenario'].upper()} profile "
                        f"(Efficiency: {most_efficient['cost_per_node']:.4f} cost/node)\n")
    
    def print_summary(self, all_results):
        """Print summary comparison table"""
        print(f"\n\n{'='*100}")
        print(f"COMPARISON SUMMARY")
        print(f"{'='*100}\n")
        
        for scenario in ['offensive', 'neutral', 'defensive', 'dynamic']:
            print(f"\n{scenario.upper()} PROFILE SCENARIO")
            print(f"{self.profile_configs[scenario]['description']}")
            print(f"{'-'*100}")
            print(f"{'Algorithm':<15} {'Path Length':<15} {'Total Cost':<15} {'Cost/Node':<15} {'Avg Threat':<15}")
            print(f"{'-'*100}")
            
            scenario_results = self.results[scenario]
            
            for algo_name in ['dijkstra', 'astar', 'safety_first', 'balanced']:
                algo_results = [r for r in scenario_results if r['algorithm'] == algo_name]
                
                if algo_results:
                    best_result = min(algo_results, key=lambda x: x['total_cost'])
                    
                    print(f"{algo_name:<15} "
                          f"{best_result['path_length']:<15} "
                          f"{best_result['total_cost']:<15.4f} "
                          f"{best_result['cost_per_node']:<15.4f} "
                          f"{best_result['avg_threat']:<15.4f}")
            
            print()


def run_pathfinding_comparison(exploration_map, start_world, goal_world, output_csv=None):
    """Convenience function to run full comparison"""
    comparator = PathfindingComparator(exploration_map)
    
    # Run comparison
    all_results = comparator.run_comparison(start_world, goal_world, num_tests=1)
    
    # Generate CSV
    csv_file = comparator.generate_comparison_csv(all_results, output_csv)
    
    # Print summary
    comparator.print_summary(all_results)
    
    return comparator, csv_file