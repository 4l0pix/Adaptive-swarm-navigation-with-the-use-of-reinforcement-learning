"""
Boids behavior profiles for different operational scenarios.
Each profile adjusts cohesion, alignment, and separation weights.
"""

class Profile:
    def __init__(self, name, cohesion, alignment, separation, description,
                 exploration_weight=1.0, obstacle_avoidance_weight=0.2,
                 cohesion_radius=50, alignment_radius=50, separation_radius=25):
        self.name = name
        self.cohesion = cohesion
        self.alignment = alignment
        self.separation = separation
        self.description = description
        
        # Profile-specific behavioral parameters
        self.exploration_weight = exploration_weight
        self.obstacle_avoidance_weight = obstacle_avoidance_weight
        self.cohesion_radius = cohesion_radius
        self.alignment_radius = alignment_radius
        self.separation_radius = separation_radius
        
        # Fitness function weights specific to this profile
        self.fitness_w1 = 1.0  # Swarm dynamics weight
        self.fitness_w2 = 1.0  # Opportunity weight
        self.fitness_w3 = 0.5  # Distance penalty weight
        
        # Penalty coefficients specific to this profile
        self.penalty_pf = 2.0  # Formation violation penalty
        self.penalty_pt = 5.0  # Threat violation penalty
        self.penalty_ptau = 3.0  # Time violation penalty

    def __repr__(self):
        return (f"{self.name}: cohesion={self.cohesion}, "
                f"alignment={self.alignment}, separation={self.separation}")


# Offensive Profile: Exploration and area coverage
OFFENSIVE = Profile(
    name="Offensive",
    cohesion=0.5,      # Low - agents spread out to explore
    alignment=1.2,     # High - maintain coordinated movement
    separation=2.0,    # High - prevent collisions while allowing freedom
    description="Low threat, high opportunity. Maximizes exploration and target engagement.",
    exploration_weight=1.5,        # High exploration priority
    obstacle_avoidance_weight=0.2, # Normal obstacle avoidance
    cohesion_radius=50,
    alignment_radius=50,
    separation_radius=25
)

# Set offensive-specific fitness parameters
OFFENSIVE.fitness_w1 = 0.8  # Moderate swarm dynamics
OFFENSIVE.fitness_w2 = 2.0  # High opportunity seeking
OFFENSIVE.fitness_w3 = 1.0  # Task completion important
OFFENSIVE.penalty_pf = 1.5  # Lower formation penalty (spread out acceptable)
OFFENSIVE.penalty_pt = 3.0  # Moderate threat penalty (risk-taking acceptable)
OFFENSIVE.penalty_ptau = 2.0  # Lower time penalty (speed priority)

# Neutral Profile: Balanced general purpose
NEUTRAL = Profile(
    name="Neutral",
    cohesion=1.0,      # Balanced - stay together but flexible
    alignment=1.0,     # Balanced - coordinated but adaptable
    separation=1.2,    # Balanced - safe maneuvering
    description="Moderate threat. General purpose scouting, monitoring, and communication.",
    exploration_weight=1.0,        # Balanced exploration
    obstacle_avoidance_weight=0.2, # Normal obstacle avoidance
    cohesion_radius=50,
    alignment_radius=50,
    separation_radius=25
)

# Set neutral-specific fitness parameters (balanced approach)
NEUTRAL.fitness_w1 = 1.0  # Equal swarm dynamics
NEUTRAL.fitness_w2 = 1.0  # Equal opportunity seeking
NEUTRAL.fitness_w3 = 0.5  # Moderate task focus
NEUTRAL.penalty_pf = 2.0  # Standard formation penalty
NEUTRAL.penalty_pt = 5.0  # Standard threat penalty
NEUTRAL.penalty_ptau = 3.0  # Standard time penalty

# Defensive Profile: Protection and survival
DEFENSIVE = Profile(
    name="Defensive",
    cohesion=5.0,       # Strong but reasonable - works with MAX_FORCE=1.0
    alignment=3.0,      # Strong coordinated movement
    separation=0.1,     # Minimal separation, allow tight formations
    description="High threat. Prioritizes survivability and mission-critical protection.",
    exploration_weight=0.05,       # Minimal exploration, formation priority
    obstacle_avoidance_weight=0.05, # Minimal avoidance to maintain formation
    cohesion_radius=150,           # Large radius to pull distant agents
    alignment_radius=100,          # Large coordination range
    separation_radius=5            # Small separation radius for tight formations
)

# Set defensive-specific fitness parameters
DEFENSIVE.fitness_w1 = 2.5  # High swarm cohesion priority
DEFENSIVE.fitness_w2 = 0.3  # Low risk-taking
DEFENSIVE.fitness_w3 = 0.2  # Task completion less critical than safety
DEFENSIVE.penalty_pf = 5.0  # High formation penalty (tight formation required)
DEFENSIVE.penalty_pt = 10.0  # Very high threat penalty (safety critical)
DEFENSIVE.penalty_ptau = 4.0  # Higher time penalty (thorough over fast)

# Profile dictionary for easy access
PROFILES = {
    "offensive": OFFENSIVE,
    "neutral": NEUTRAL,
    "defensive": DEFENSIVE
}

def get_profile(name):
    """Get a profile by name (case-insensitive)"""
    return PROFILES.get(name.lower(), NEUTRAL)

def list_profiles():
    """Print all available profiles"""
    print("\nAvailable Profiles:")
    print("-" * 60)
    for profile in PROFILES.values():
        print(f"\n{profile}")
        print(f"  {profile.description}")
