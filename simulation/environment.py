import numpy as np

class Environment:
    def __init__(self, width=100, height=100, depth=100):
        self.width = width
        self.height = height
        self.depth = depth
        self.obstacles = []
        self.exploration_map = None
        self.pathfinding_mode = False

    def set_exploration_map(self, exploration_map):
        """Set the shared exploration map"""
        self.exploration_map = exploration_map

    def add_obstacles(self, obstacles):
        """Add obstacles to the environment"""
        self.obstacles = obstacles

    def apply_borders(self, agent, margin=5):
        """Bounce agents back when they approach borders"""
        force = np.zeros(3)

        # X boundaries
        if agent.position[0] < margin:
            force[0] = agent.max_speed
        elif agent.position[0] > self.width - margin:
            force[0] = -agent.max_speed

        # Y boundaries
        if agent.position[1] < margin:
            force[1] = agent.max_speed
        elif agent.position[1] > self.height - margin:
            force[1] = -agent.max_speed

        # Z boundaries
        if agent.position[2] < margin:
            force[2] = agent.max_speed
        elif agent.position[2] > self.depth - margin:
            force[2] = -agent.max_speed

        return force

    def apply_obstacle_avoidance(self, agent, avoidance_radius=15, avoidance_force=0.5):
        """Make agents avoid obstacles"""
        force = np.zeros(3)

        for obs in self.obstacles:
            obs_pos = obs['position']
            obs_width = obs['width']
            obs_height = obs['height']

            # Check if agent is within obstacle height range
            if agent.position[2] < obs_height:
                # Calculate distance in XY plane to obstacle center
                diff_xy = agent.position[:2] - obs_pos[:2]
                dist_xy = np.linalg.norm(diff_xy)

                # If within avoidance radius, apply repulsion force
                if dist_xy < avoidance_radius + obs_width:
                    if dist_xy > 0:
                        # Push away in XY plane
                        repulsion = diff_xy / dist_xy
                        strength = (avoidance_radius + obs_width - dist_xy) / avoidance_radius
                        force[:2] += repulsion * strength * avoidance_force

                        # Push upward if too close
                        if dist_xy < obs_width * 2:
                            force[2] += avoidance_force * 0.5

        return force
