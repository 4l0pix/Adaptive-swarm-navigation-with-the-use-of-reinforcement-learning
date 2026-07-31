import numpy as np
from utils import MAP_RESOLUTION, THREAT_DETECTION_RADIUS, ENV_DEPTH

# 3D Exploration grid resolution
EXPLORATION_3D_RESOLUTION = 25  # 25x25x25 grid

class ExplorationMap:
    """Shared memory system tracking explored areas and obstacle threats"""

    def __init__(self, width, height, obstacles):
        self.width = width
        self.height = height
        self.depth = ENV_DEPTH  # Z dimension
        self.resolution = MAP_RESOLUTION
        self.obstacles = obstacles

        # Create grid for exploration tracking (True = explored) - 2D for threat map
        self.explored_grid = np.zeros((self.resolution, self.resolution), dtype=bool)
        
        # 3D exploration grid for pathfinding (True = explored/traversable)
        self.explored_grid_3d = np.zeros((EXPLORATION_3D_RESOLUTION, EXPLORATION_3D_RESOLUTION, EXPLORATION_3D_RESOLUTION), dtype=bool)
        self.cell_size_3d = width / EXPLORATION_3D_RESOLUTION  # Assuming cubic cells

        # Create threat intensity map (0 = safe, higher = more dangerous)
        self.threat_map = self._compute_threat_map()

        # Grid cell size
        self.cell_size_x = width / self.resolution
        self.cell_size_y = height / self.resolution

    def _compute_threat_map(self):
        """Compute threat intensity based on obstacle proximity"""
        threat_map = np.zeros((self.resolution, self.resolution))

        # Create coordinate grids
        x_coords = np.linspace(0, self.width, self.resolution)
        y_coords = np.linspace(0, self.height, self.resolution)

        for i, x in enumerate(x_coords):
            for j, y in enumerate(y_coords):
                threat = 0
                # Calculate threat from all obstacles
                for obs in self.obstacles:
                    obs_x, obs_y = obs['position'][0], obs['position'][1]
                    dist = np.sqrt((x - obs_x)**2 + (y - obs_y)**2)

                    if dist < THREAT_DETECTION_RADIUS:
                        # Each obstacle is a heat source with base intensity of 1.0
                        # Heat decreases with distance but obstacle center is always 1.0
                        heat_intensity = 1.0 - (dist / THREAT_DETECTION_RADIUS)
                        threat += heat_intensity

                threat_map[j, i] = threat

        # Don't normalize - let values accumulate for overlapping areas
        # This allows individual obstacles to show as red (1.0)
        # and overlapping areas to exceed 1.0 and appear purple
        return threat_map

    def mark_explored(self, position, radius):
        """Mark area around position as explored (2D)"""
        x, y = position[0], position[1]

        # Convert position to grid coordinates
        grid_x = int(x / self.cell_size_x)
        grid_y = int(y / self.cell_size_y)

        # Mark nearby cells as explored
        radius_cells = int(radius / min(self.cell_size_x, self.cell_size_y))

        for i in range(max(0, grid_x - radius_cells),
                      min(self.resolution, grid_x + radius_cells + 1)):
            for j in range(max(0, grid_y - radius_cells),
                          min(self.resolution, grid_y + radius_cells + 1)):
                self.explored_grid[j, i] = True
    
    def mark_explored_3d(self, position, radius):
        """Mark 3D area around position as explored (for 3D pathfinding)"""
        x, y, z = position[0], position[1], position[2] if len(position) > 2 else self.depth / 2
        
        # Convert to 3D grid coordinates
        grid_x = int(x / self.cell_size_3d)
        grid_y = int(y / self.cell_size_3d)
        grid_z = int(z / self.cell_size_3d)
        
        # Radius in cells
        radius_cells = int(radius / self.cell_size_3d)
        
        for i in range(max(0, grid_x - radius_cells),
                      min(EXPLORATION_3D_RESOLUTION, grid_x + radius_cells + 1)):
            for j in range(max(0, grid_y - radius_cells),
                          min(EXPLORATION_3D_RESOLUTION, grid_y + radius_cells + 1)):
                for k in range(max(0, grid_z - radius_cells),
                              min(EXPLORATION_3D_RESOLUTION, grid_z + radius_cells + 1)):
                    # Check if within spherical radius
                    dx = i - grid_x
                    dy = j - grid_y
                    dz = k - grid_z
                    if dx*dx + dy*dy + dz*dz <= radius_cells * radius_cells:
                        self.explored_grid_3d[i, j, k] = True
    
    def is_explored_3d(self, x, y, z):
        """Check if a 3D position has been explored"""
        grid_x = int(x / self.cell_size_3d)
        grid_y = int(y / self.cell_size_3d)
        grid_z = int(z / self.cell_size_3d)
        
        # Clamp to grid bounds
        grid_x = max(0, min(EXPLORATION_3D_RESOLUTION - 1, grid_x))
        grid_y = max(0, min(EXPLORATION_3D_RESOLUTION - 1, grid_y))
        grid_z = max(0, min(EXPLORATION_3D_RESOLUTION - 1, grid_z))
        
        return self.explored_grid_3d[grid_x, grid_y, grid_z]
    
    def get_3d_exploration_percentage(self):
        """Calculate percentage of 3D space explored"""
        total_cells = EXPLORATION_3D_RESOLUTION ** 3
        explored_cells = np.sum(self.explored_grid_3d)
        return (explored_cells / total_cells) * 100

    def get_exploration_percentage(self):
        """Calculate percentage of area explored"""
        total_cells = self.resolution * self.resolution
        explored_cells = np.sum(self.explored_grid)
        return (explored_cells / total_cells) * 100

    def get_unexplored_direction(self, position):
        """Get direction towards nearest unexplored area"""
        x, y = position[0], position[1]
        grid_x = int(x / self.cell_size_x)
        grid_y = int(y / self.cell_size_y)

        # Find nearest unexplored cell
        unexplored_cells = np.argwhere(~self.explored_grid)

        if len(unexplored_cells) == 0:
            return np.zeros(2)  # All explored

        # Calculate distances to unexplored cells
        distances = np.sqrt((unexplored_cells[:, 1] - grid_x)**2 +
                           (unexplored_cells[:, 0] - grid_y)**2)
        nearest_idx = np.argmin(distances)
        nearest_cell = unexplored_cells[nearest_idx]

        # Convert back to world coordinates
        target_x = (nearest_cell[1] + 0.5) * self.cell_size_x
        target_y = (nearest_cell[0] + 0.5) * self.cell_size_y

        # Return direction vector
        direction = np.array([target_x - x, target_y - y])
        dist = np.linalg.norm(direction)
        if dist > 0:
            direction = direction / dist

        return direction

    def get_visualization_data(self):
        """Get data for visualization (explored areas with threat colors)"""
        # Create RGB visualization
        vis_data = np.zeros((self.resolution, self.resolution, 3))

        for i in range(self.resolution):
            for j in range(self.resolution):
                if self.explored_grid[j, i]:
                    threat = self.threat_map[j, i]
                    # Color scheme: blue (safe) -> yellow -> orange -> red (single obstacle) -> purple (overlapping)
                    if threat < 0.25:
                        # Blue to yellow (low threat)
                        t = threat * 4  # Scale to 0-1
                        vis_data[j, i] = [t, t, 1 - t]  # Blue -> Yellow
                    elif threat < 0.5:
                        # Yellow to orange (medium threat)
                        t = (threat - 0.25) * 4  # Scale to 0-1
                        vis_data[j, i] = [1, 1 - t * 0.5, 0]  # Yellow -> Orange
                    elif threat < 1.0:
                        # Orange to red (high threat - single obstacle)
                        t = (threat - 0.5) * 2  # Scale to 0-1
                        vis_data[j, i] = [1, (1 - t) * 0.5, 0]  # Orange -> Red
                    else:
                        # Red to purple (overlapping obstacles)
                        # threat >= 1.0 indicates overlapping heat sources
                        overlap_intensity = min(threat - 1.0, 1.0)  # Cap at 1.0 for max purple
                        vis_data[j, i] = [1, 0, overlap_intensity]  # Red -> Purple
                else:
                    # Unexplored areas are dark gray
                    vis_data[j, i] = [0.2, 0.2, 0.2]

        return vis_data
    
    def find_optimal_position(self):
        """Find the position with lowest threat value in explored areas"""
        if not np.any(self.explored_grid):
            return None, None  # No explored areas
        
        # Create a masked threat map (only explored areas)
        masked_threat = np.where(self.explored_grid, self.threat_map, np.inf)
        
        # Find minimum threat position
        min_idx = np.unravel_index(np.argmin(masked_threat), masked_threat.shape)
        min_threat = masked_threat[min_idx]
        
        # Convert grid coordinates to world coordinates
        world_x = (min_idx[1] + 0.5) * self.cell_size_x
        world_y = (min_idx[0] + 0.5) * self.cell_size_y
        
        return np.array([world_x, world_y]), min_threat

