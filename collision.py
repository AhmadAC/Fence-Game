# collision.py
"""
Contains functions for detecting collisions between game objects.
"""
import pygame
import math

# Import needed constants
try:
    # Assuming PLAYER_RADIUS and INTERACTION_DISTANCE are defined in constants.py
    # Also assuming PLAYER_WALL_PROXIMITY_THRESHOLD might be defined there.
    from constants import PLAYER_RADIUS, INTERACTION_DISTANCE, PLAYER_WALL_PROXIMITY_THRESHOLD
except ImportError:
    print("Warning [collision.py]: Could not import constants. Using default values.")
    PLAYER_RADIUS = 15
    INTERACTION_DISTANCE = 35
    # Define a default proximity threshold if not found in constants
    PLAYER_WALL_PROXIMITY_THRESHOLD = 5 # How many extra pixels beyond player radius to check proximity to wall

# --- Player-Fence Collision (Unchanged) ---
def check_player_fence_collision(player_x, player_y, radius, fences_list):
    """Checks if a player circle collides with any closed fence."""
    try:
        player_rect = pygame.Rect(float(player_x) - float(radius),
                                  float(player_y) - float(radius),
                                  float(radius) * 2, float(radius) * 2)
    except (ValueError, TypeError):
        print("Warning: Invalid coords/radius in check_player_fence_collision.")
        return False
    for fence in fences_list:
        # Check if fence exists, has 'is_open' and 'rect', is closed, and collides
        if fence and hasattr(fence, 'is_open') and not fence.is_open and hasattr(fence, 'rect') and player_rect.colliderect(fence.rect):
            return True # Collision with a closed fence
    return False # No collision with any closed fence

# --- Projectile-Fence Collision (MODIFIED) ---
def get_colliding_fence(projectile, fences_list):
    """
    Checks if an active projectile hits a CLOSED fence.
    Returns the colliding Fence object or None if no collision.
    """
    # Basic validation for the projectile
    if not projectile or not hasattr(projectile, 'active') or not projectile.active or not hasattr(projectile, 'rect'):
        return None # Invalid or inactive projectile

    for fence in fences_list:
        # Check if fence exists, has 'is_open' and 'rect', is closed, and collides
        if fence and hasattr(fence, 'is_open') and not fence.is_open and hasattr(fence, 'rect') and projectile.rect.colliderect(fence.rect):
            return fence # Return the specific Fence object that was hit
        # --- End check ---
    return None # No collision with any CLOSED fence


# --- Player-Wall Proximity Check (NEW) ---
def is_player_close_to_fence(player_x, player_y, player_radius, fence):
    """Checks if a player circle is very close to a given fence rectangle."""
    if not fence or not hasattr(fence, 'rect'):
        # print("Debug: is_player_close_to_fence called with invalid fence.") # Optional debug
        return False # Cannot check against an invalid fence

    try:
        px, py, pr = float(player_x), float(player_y), float(player_radius)

        # Define the check area around the player, slightly larger than the player radius
        # This checks if the player is *just touching* or slightly overlapping the fence
        check_radius = pr + PLAYER_WALL_PROXIMITY_THRESHOLD

        # Create a bounding box for this larger check radius
        player_check_rect = pygame.Rect(
            px - check_radius,
            py - check_radius,
            check_radius * 2,
            check_radius * 2
        )

        # Use rect collision for simplicity and efficiency here
        # This checks if the expanded player area overlaps the fence rectangle
        is_close = player_check_rect.colliderect(fence.rect)
        # print(f"Debug: Player ({px:.1f},{py:.1f}) proximity to Fence {getattr(fence, 'id', 'N/A')}: {is_close}") # Optional debug
        return is_close

    except (ValueError, TypeError) as e:
        print(f"Warning: Invalid data type for player-fence proximity check: {e}. Player:({player_x},{player_y}), Fence:{fence}")
        return False # Treat error as not close

# --- Projectile-Player Collision (Unchanged) ---
def check_projectile_player_collision(projectile, p1_data, p2_data):
    """
    Checks if an active projectile hits a player it doesn't own.
    p1_data and p2_data are dictionaries like {"x": ..., "y": ..., "hp": ...}
    Returns the ID of the hit player (1 or 2) or None if no hit.
    """
    # --- Simplified Input Validation ---
    if not projectile or not hasattr(projectile, 'active') or not projectile.active:
        # print("Debug: check_projectile_player_collision - invalid/inactive projectile") # Optional
        return None
    # Expect necessary attributes on the projectile object
    if not hasattr(projectile, 'owner_id') or \
       not hasattr(projectile, 'x') or not hasattr(projectile, 'y') or \
       not hasattr(projectile, 'radius') or projectile.radius <= 0: # Added radius check
        print(f"Warning: Projectile object missing expected attributes or has invalid radius: {vars(projectile)}")
        return None # Cannot perform check

    # --- End Validation ---

    hit_player_id = None
    proj_x, proj_y, proj_r = projectile.x, projectile.y, projectile.radius

    # Check collision with Player 1
    if p1_data and isinstance(p1_data, dict) and projectile.owner_id != 1 and p1_data.get("hp", 0) > 0:
        p1x = p1_data.get("x")
        p1y = p1_data.get("y")
        if p1x is not None and p1y is not None:
            if check_circle_collision(proj_x, proj_y, proj_r, p1x, p1y, PLAYER_RADIUS):
                hit_player_id = 1
        # else: print("Warning: P1 data missing x or y for collision check.") # Less verbose

    # Check collision with Player 2 (only if P1 wasn't hit)
    if hit_player_id is None and p2_data and isinstance(p2_data, dict) and projectile.owner_id != 2 and p2_data.get("hp", 0) > 0:
         p2x = p2_data.get("x")
         p2y = p2_data.get("y")
         if p2x is not None and p2y is not None:
             if check_circle_collision(proj_x, proj_y, proj_r, p2x, p2y, PLAYER_RADIUS):
                 hit_player_id = 2
         # else: print("Warning: P2 data missing x or y for collision check.") # Less verbose

    # if hit_player_id: print(f"Debug: Projectile {projectile.id} hit player {hit_player_id}") # Optional
    return hit_player_id

# --- Circle-Circle Collision (Unchanged) ---
def check_circle_collision(x1, y1, r1, x2, y2, r2):
    """Checks if two circles overlap."""
    try:
        # Use squared distances to avoid slow square root calculation
        dist_sq = (float(x1) - float(x2))**2 + (float(y1) - float(y2))**2
        radii_sum_sq = (float(r1) + float(r2))**2
    except (ValueError, TypeError):
        print(f"Warning: Invalid numeric input for circle collision check: ({x1},{y1},{r1}) vs ({x2},{y2},{r2})")
        return False
    # Circles collide if the distance between centers is less than the sum of radii
    return dist_sq < radii_sum_sq

# --- Player-Fence Interaction Proximity (Unchanged) ---
def get_closest_fence_in_proximity(player_x, player_y, fences_list):
    """
    Finds the ID of the closest fence within INTERACTION_DISTANCE.
    Returns fence ID (int) or -1 if no fence is close enough or on error.
    Uses distance from player center to closest point on fence rect.
    """
    try:
        # Ensure player coordinates are valid numbers
        player_center_x = float(player_x)
        player_center_y = float(player_y)
    except (ValueError, TypeError):
        print("Warning: Invalid player coordinates in get_closest_fence_in_proximity.")
        return -1 # Return -1 on error, indicating no fence found

    min_dist_sq = float('inf')
    closest_fence_id = -1 # Default to -1 (no fence found)

    # Pre-calculate interaction distance squared
    interaction_dist_sq = INTERACTION_DISTANCE**2

    for fence in fences_list:
        # Basic validation for each fence object
        if not fence or not hasattr(fence, 'rect'):
            continue # Skip invalid fence entries

        # Find the point on the fence rectangle closest to the player's center
        closest_x = max(fence.rect.left, min(player_center_x, fence.rect.right))
        closest_y = max(fence.rect.top, min(player_center_y, fence.rect.bottom))

        # Calculate the squared distance from player center to this closest point
        distance_sq = (player_center_x - closest_x)**2 + (player_center_y - closest_y)**2

        # Check if this fence is within interaction range AND closer than the previous closest
        if distance_sq < interaction_dist_sq:
            if distance_sq < min_dist_sq:
                min_dist_sq = distance_sq
                # Get the fence ID, default to -1 if 'id' attribute doesn't exist
                closest_fence_id = getattr(fence, 'id', -1)

    return closest_fence_id