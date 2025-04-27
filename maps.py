# maps.py
import pygame # Needed for pygame.Rect potentially, though we only return data now
import random
import math # For potential angle calculations if needed later, not strictly used now


# --- Constants specific to map generation ---
FENCE_THICKNESS = 10 # Default thickness for CIRCULAR fences
MIN_RADIUS_STEP = 40  # Min distance between circles centerlines
MAX_RADIUS_STEP = 60  # Max distance between circles centerlines
RADIUS_VARIATION = 5  # How much each radius can deviate
NUM_CIRCLES = 5       # Number of concentric circles
GAP_PROBABILITY = 0.3 # Probability a potential gap exists (lower = more walls)
CONNECT_PROBABILITY = 0.4 # Probability a potential connection exists
PLAYER_START_OFFSET = 15 # Distance from wall for starting positions
# NEW: Buffer space to add to player size for gap calculation
GAP_CLEARANCE_BUFFER = 8 # Add this many pixels to player width for smoother passage

def get_random_circular_maze_layout(WIDTH, HEIGHT, player_collision_width):
    """
    Generates a somewhat randomized layout data for a circular maze
    and suggested player starting positions, ensuring gaps are large
    enough for player passage. Gaps are doubled in width compared to the base requirement.
    Radial fences (connecting concentric circles) are twice the width of the player.

    Args:
        WIDTH (int): The width of the game area.
        HEIGHT (int): The height of the game area.
        player_collision_width (int): The width (or effective diameter)
                                      of the player's collision shape.
                                      Used to ensure gaps are passable and for radial fence thickness.

    Returns:
        dict: A dictionary containing:
              'fences' (list): List of fence tuples (x, y, width, height).
              'start_pos' (list): List of two tuples (x, y) for player starts.
    """
    fence_data = []
    start_positions = []
    cx, cy = WIDTH // 2, HEIGHT // 2
    th = FENCE_THICKNESS # Original thickness, primarily for CIRCULAR fences now

    # --- Calculate required sizes based on player ---
    # Ensure gaps are wide enough for the player plus some clearance
    base_required_gap_size = player_collision_width + GAP_CLEARANCE_BUFFER
    # For corridor width checks, we need space for the player *between* fences
    min_corridor_width = player_collision_width + 30 # Minimum space between opposing fence faces

    # --- NEW: Define Radial Fence Thickness ---
    # Radial fences are twice the player width
    radial_fence_thickness = player_collision_width * 2
    # Ensure minimum thickness for radial fences (at least 1 pixel)
    radial_fence_thickness = max(1, radial_fence_thickness)

    print(f"Player collision width: {player_collision_width}, Buffer: {GAP_CLEARANCE_BUFFER}")
    print(f"Base required gap opening size: {base_required_gap_size}")
    print(f"Minimum corridor width (space between fences): {min_corridor_width}")
    print(f"Circular fence thickness: {th}")
    print(f"Radial fence thickness: {radial_fence_thickness}")


    # --- Generate Randomized Radii ---
    radii = []
    current_radius = 0
    for i in range(NUM_CIRCLES):
        base_step = random.uniform(MIN_RADIUS_STEP, MAX_RADIUS_STEP)

        # Ensure first radius isn't too small
        if i == 0:
            base_step = max(base_step, base_required_gap_size * 0.75) # Ensure center area isn't tiny
            # The first 'corridor' is between center and first fence inner edge
            # Use original 'th' here as it relates to the circular fence boundary
            min_step_for_player_center = (player_collision_width / 2) + (th / 2) + 5
            base_step = max(base_step, min_step_for_player_center)

        # Ensure distance between radii allows for minimum corridor width
        # This check still uses the original circular fence thickness 'th'
        if i > 0:
            min_step_needed = min_corridor_width + th
             # print(f"  Checking radius step: Base={base_step:.1f}, Min needed for corridor={min_step_needed:.1f}")
            base_step = max(base_step, min_step_needed)

        current_radius += base_step
        radius = max(10, current_radius + random.uniform(-RADIUS_VARIATION, RADIUS_VARIATION))

        # Prevent circles getting *too* close from variation, check against prev radius centerline
        # Still use original 'th' for this check
        if i > 0:
            min_radius_for_corridor = radii[-1] + min_corridor_width + th
            if radius < min_radius_for_corridor:
                 # print(f"  Adjusting radius {i}: {radius:.1f} was too close to {radii[-1]:.1f}. Setting to {min_radius_for_corridor:.1f}")
                radius = min_radius_for_corridor

        radii.append(int(radius))

    # Make sure radii don't exceed bounds
    max_allowed_radius = min(WIDTH, HEIGHT) // 2 - th - 20 # Leave some margin (using original th for buffer)
    original_num_radii = len(radii)
    radii = [r for r in radii if r < max_allowed_radius]
    if len(radii) < original_num_radii:
         print(f"Warning: Removed {original_num_radii - len(radii)} radii exceeding screen bounds.")

    if not radii:
        print("Error: Could not generate any valid radii within bounds. Aborting map generation potentially.")
        fallback_radius = max(30, int(base_required_gap_size * 1.5))
        if fallback_radius < max_allowed_radius:
             radii = [fallback_radius]
             print(f"Using a single fallback radius: {fallback_radius}")
        else:
             print("Fallback radius also too large. Cannot generate map.")
             return {'fences': [], 'start_pos': [(cx,cy), (cx, cy)]}


    if len(radii) < 2:
         print("Warning: Not enough radii generated/kept for connections. Map will be simple (or just one ring).")
         if len(radii) == 1:
              # Use original 'th' for the spacing check
              min_step_needed = min_corridor_width + th
              radii.append(radii[0] + max(int(min_step_needed * 1.2), 50))
              if radii[-1] >= max_allowed_radius:
                    radii.pop()
                    print("Could not add a second radius within bounds.")


    print(f"Generated {len(radii)} radii: {radii}")

    # --- Helper functions ---
    _fence_data_list = []
    def add_fence_data(x, y, w, h):
        w = max(1, int(w))
        h = max(1, int(h))
        x = int(x)
        y = int(y)
        rect = pygame.Rect(x, y, w, h)
        # Use original 'th' for boundary check buffer, as it's a general buffer
        if rect.right > -th*2 and rect.left < WIDTH + th*2 and rect.bottom > -th*2 and rect.top < HEIGHT + th*2:
             _fence_data_list.append((rect.x, rect.y, rect.width, rect.height))


    # Modified to accept and use radial_th for the connecting fences' thickness
    def add_radial_fence(conn_seg_index, r_outer, r_inner, cx, cy, th_circular, radial_th):
        """
        Helper to calculate and add a radial fence segment with specified thickness.

        Args:
            conn_seg_index (int): Quadrant index (0=T, 1=R, 2=B, 3=L).
            r_outer (int): Radius of the outer circle centerline.
            r_inner (int): Radius of the inner circle centerline.
            cx (int): Center X coordinate.
            cy (int): Center Y coordinate.
            th_circular (int): Thickness of the *circular* fences (used for edge calculations).
            radial_th (int): Thickness to use for *this radial* fence.
        """
        # Calculate the length based on the inner/outer edges defined by CIRCULAR thickness
        r_outer_edge = r_outer + th_circular // 2
        r_inner_edge = r_inner - th_circular // 2
        length = r_outer_edge - r_inner_edge # Length from outer edge of outer fence to inner edge of inner fence

        if length <= 0:
             return

        x, y, w, h = 0, 0, 0, 0

        # Calculate position and dimensions based on the REQUIRED radial thickness
        if conn_seg_index == 0: # Top radial wall (Vertical)
            start_y = cy - r_outer_edge # Outer edge y (using circular edge)
            end_y = cy - r_inner_edge   # Inner edge y (using circular edge)
            wall_len = abs(start_y - end_y)
            if wall_len < 1: return
            # Position centered horizontally, use radial_th for width
            x = cx - radial_th // 2
            y = min(start_y, end_y)
            w = radial_th
            h = wall_len

        elif conn_seg_index == 1: # Right radial wall (Horizontal)
            start_x = cx + r_inner_edge # Inner edge x (using circular edge)
            end_x = cx + r_outer_edge   # Outer edge x (using circular edge)
            wall_len = abs(start_x - end_x)
            if wall_len < 1: return
            # Position centered vertically, use radial_th for height
            x = min(start_x, end_x)
            y = cy - radial_th // 2
            w = wall_len
            h = radial_th

        elif conn_seg_index == 2: # Bottom radial wall (Vertical)
            start_y = cy + r_inner_edge # Inner edge y (using circular edge)
            end_y = cy + r_outer_edge   # Outer edge y (using circular edge)
            wall_len = abs(start_y - end_y)
            if wall_len < 1: return
            # Position centered horizontally, use radial_th for width
            x = cx - radial_th // 2
            y = min(start_y, end_y)
            w = radial_th
            h = wall_len

        elif conn_seg_index == 3: # Left radial wall (Horizontal)
            start_x = cx - r_outer_edge # Outer edge x (using circular edge)
            end_x = cx - r_inner_edge   # Inner edge x (using circular edge)
            wall_len = abs(start_x - end_x)
            if wall_len < 1: return
            # Position centered vertically, use radial_th for height
            x = min(start_x, end_x)
            y = cy - radial_th // 2
            w = wall_len
            h = radial_th

        # print(f"Adding radial fence: Seg={conn_seg_index}, r_out={r_outer}, r_in={r_inner} -> ({x},{y},{w},{h}) with radial_th={radial_th}")
        add_fence_data(x, y, w, h)


    # --- Generate Randomized Fences ---
    gaps = {i: [] for i in range(len(radii))}

    for i in range(len(radii)):
        r = radii[i]
        r_inner = radii[i-1] if i > 0 else 0

        # --- Decide on gaps for this circle (r) ---
        # (Gap decision logic remains the same)
        possible_segments = [0, 1, 2, 3]
        random.shuffle(possible_segments)
        num_gaps_target = 1
        if len(radii) > 1:
             num_gaps_target = random.randint(1, 2)

        current_gaps = []
        for seg_index in possible_segments:
             if random.random() < GAP_PROBABILITY:
                  current_gaps.append(seg_index)

        gaps_needed = num_gaps_target - len(current_gaps)
        potential_gap_locations = [idx for idx in possible_segments if idx not in current_gaps]
        random.shuffle(potential_gap_locations)
        for _ in range(gaps_needed):
            if potential_gap_locations:
                 current_gaps.append(potential_gap_locations.pop())
            else:
                 break

        if not current_gaps and possible_segments:
             current_gaps.append(random.choice(possible_segments))

        gaps[i] = current_gaps

        # --- Add Circular Wall Segments (based on gaps) ---
        # These segments use the ORIGINAL thickness 'th'
        gap_offset_from_center = base_required_gap_size # Offset to achieve 2*base_required_gap_size opening
        print(f"Ring {i} (r={r}): Base gap size={base_required_gap_size}, Doubled gap size={base_required_gap_size*2}, Offset from center={gap_offset_from_center}")

        # Top segment (Uses original 'th')
        y_pos_top = cy - r - th // 2
        if 0 not in current_gaps:
            add_fence_data(cx - r - th // 2, y_pos_top, (r + th // 2)*2, th)
        else:
            left_x_start = cx - r - th // 2
            left_x_end = cx - gap_offset_from_center
            left_width = left_x_end - left_x_start
            if left_width > 0:
                add_fence_data(left_x_start, y_pos_top, left_width, th)
            right_x_start = cx + gap_offset_from_center
            right_x_end = cx + r + th // 2
            right_width = right_x_end - right_x_start
            if right_width > 0:
                add_fence_data(right_x_start, y_pos_top, right_width, th)

        # Right segment (Uses original 'th')
        x_pos_right = cx + r - th // 2
        if 1 not in current_gaps:
            add_fence_data(x_pos_right, cy - r - th // 2, th, (r + th // 2)*2)
        else:
            top_y_start = cy - r - th // 2
            top_y_end = cy - gap_offset_from_center
            top_height = top_y_end - top_y_start
            if top_height > 0:
                add_fence_data(x_pos_right, top_y_start, th, top_height)
            bottom_y_start = cy + gap_offset_from_center
            bottom_y_end = cy + r + th // 2
            bottom_height = bottom_y_end - bottom_y_start
            if bottom_height > 0:
                add_fence_data(x_pos_right, bottom_y_start, th, bottom_height)

        # Bottom segment (Uses original 'th')
        y_pos_bottom = cy + r - th // 2
        if 2 not in current_gaps:
             add_fence_data(cx - r - th // 2, y_pos_bottom, (r + th // 2)*2, th)
        else:
            left_x_start = cx - r - th // 2
            left_x_end = cx - gap_offset_from_center
            left_width = left_x_end - left_x_start
            if left_width > 0:
                add_fence_data(left_x_start, y_pos_bottom, left_width, th)
            right_x_start = cx + gap_offset_from_center
            right_x_end = cx + r + th // 2
            right_width = right_x_end - right_x_start
            if right_width > 0:
                add_fence_data(right_x_start, y_pos_bottom, right_width, th)

        # Left segment (Uses original 'th')
        x_pos_left = cx - r - th // 2
        if 3 not in current_gaps:
            add_fence_data(x_pos_left, cy - r - th // 2, th, (r + th // 2)*2)
        else:
            top_y_start = cy - r - th // 2
            top_y_end = cy - gap_offset_from_center
            top_height = top_y_end - top_y_start
            if top_height > 0:
                add_fence_data(x_pos_left, top_y_start, th, top_height)
            bottom_y_start = cy + gap_offset_from_center
            bottom_y_end = cy + r + th // 2
            bottom_height = bottom_y_end - bottom_y_start
            if bottom_height > 0:
                add_fence_data(x_pos_left, bottom_y_start, th, bottom_height)


        # --- Add Connecting Walls (Radial) between r and r_inner ---
        # These will use the NEW radial_fence_thickness
        if i > 0:
            r_outer = r
            # --- Heuristic Check: Prevent placing adjacent radial walls if they'd be too close ---
            # This check should probably consider the radial_fence_thickness now?
            # Approx space = chord_dist - radial_fence_thickness (instead of th)
            chord_dist_at_inner = math.sqrt(2) * r_inner
            min_dist_between_adj_radials = chord_dist_at_inner - radial_fence_thickness
            place_only_opposite_radials = False
            # Check against player width as the minimum clearance required
            if min_dist_between_adj_radials < player_collision_width + 5: # Need player width + buffer
                 place_only_opposite_radials = True
                 # print(f"Ring {i-1}-{i}: Forcing opposite radial walls (dist={min_dist_between_adj_radials:.1f} < req_clearance) at r_inner={r_inner} due to radial_th={radial_fence_thickness}")


            possible_connections = [0, 1, 2, 3]
            random.shuffle(possible_connections)
            connections_added_indices = []

            for conn_seg_index in possible_connections:
                 if place_only_opposite_radials and connections_added_indices:
                     is_adjacent = False
                     for added_idx in connections_added_indices:
                          if abs(conn_seg_index - added_idx) == 1 or abs(conn_seg_index - added_idx) == 3:
                               is_adjacent = True
                               break
                     if is_adjacent:
                          # print(f"  Skipping adjacent radial {conn_seg_index} due to rule.")
                          continue

                 gap_in_outer = conn_seg_index in gaps[i]
                 gap_in_inner = conn_seg_index in gaps[i-1]

                 # Add connection based on probability, only if it doesn't block gaps
                 if random.random() < CONNECT_PROBABILITY and not gap_in_outer and not gap_in_inner:
                     # <<< CHANGE HERE: Pass radial_fence_thickness >>>
                     # Pass original 'th' as th_circular for edge calculations
                     add_radial_fence(conn_seg_index, r_outer, r_inner, cx, cy, th, radial_fence_thickness)
                     connections_added_indices.append(conn_seg_index)

            # print(f"Ring {i-1}-{i}: Added {len(connections_added_indices)} radial connections at indices {connections_added_indices}.")


    # --- Generate Player Start Positions ---
    # (Start position logic remains the same)
    if len(radii) == 0:
        print("Error: No radii available for start positions.")
        return {'fences': _fence_data_list, 'start_pos': [(cx, cy), (cx, cy)]}

    r_outermost = radii[-1]
    r_outer_zone_inner = radii[-2] if len(radii) >= 2 else radii[-1] * 0.6
    r_inner_zone_outer = radii[0]

    def find_safe_start(r_min, r_max, quadrant, attempts=20):
        r_min = max(0, r_min)
        r_max = max(r_min + player_collision_width + 5, r_max)

        for _ in range(attempts):
            q_angle_start = quadrant * math.pi / 2
            angle_offset = math.radians(10)
            angle = random.uniform(q_angle_start + angle_offset, q_angle_start + math.pi / 2 - angle_offset)

            safe_r_min = r_min + PLAYER_START_OFFSET
            safe_r_max = r_max - PLAYER_START_OFFSET
            if safe_r_max <= safe_r_min:
                 r = (r_min + r_max) / 2
            else:
                 r = random.uniform(safe_r_min, safe_r_max)

            x = cx + r * math.cos(angle)
            y = cy - r * math.sin(angle)

            player_half_width = player_collision_width / 2
            potential_start_rect = pygame.Rect(x - player_half_width, y - player_half_width, player_collision_width, player_collision_width)
            is_colliding = False
            for fence_coords in _fence_data_list:
                fence_rect = pygame.Rect(fence_coords)
                if potential_start_rect.colliderect(fence_rect.inflate(2, 2)):
                    is_colliding = True
                    break
            if not is_colliding:
                return (int(x), int(y))

        print(f"Warning: Could not find a guaranteed safe start position in quadrant {quadrant} between {r_min:.0f}-{r_max:.0f}. Using approximate middle.")
        r_mid = (r_min + r_max) / 2
        q_angle_mid = (quadrant + 0.5) * math.pi / 2
        x = cx + r_mid * math.cos(q_angle_mid)
        y = cy - r_mid * math.sin(q_angle_mid)
        player_half_width = player_collision_width / 2
        potential_start_rect = pygame.Rect(x - player_half_width, y - player_half_width, player_collision_width, player_collision_width)
        is_colliding = False
        for fence_coords in _fence_data_list:
             fence_rect = pygame.Rect(fence_coords)
             if potential_start_rect.colliderect(fence_rect.inflate(2, 2)):
                 is_colliding = True
                 print(f"Fallback position ({int(x)}, {int(y)}) also collides! Placing at center as last resort.")
                 return(cx, cy)

        return (int(x), int(y))

    quadrant1 = random.randint(0, 3)
    quadrant2 = (quadrant1 + 2) % 4

    p1_start = find_safe_start(r_outer_zone_inner, r_outermost, quadrant1)
    start_positions.append(p1_start)

    p2_start = find_safe_start(0, r_inner_zone_outer, quadrant2)
    start_positions.append(p2_start)

    fence_data = _fence_data_list

    print(f"Generated layout data for {len(fence_data)} fence segments.")
    print(f"Generated start positions: {start_positions}")

    return {
        'fences': fence_data,
        'start_pos': start_positions
    }


# --- Example Usage (for testing within this file) ---
if __name__ == '__main__':
    pygame.init()

    SCREEN_WIDTH = 800
    SCREEN_HEIGHT = 600
    # --- !! CRITICAL !! Adjust this to match your actual player's collision box width/diameter ---
    PLAYER_COLLISION_WIDTH_EXAMPLE = 28 # Example player size (adjust as needed)
    # ---

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(f"Random Maze Test (Player Width: {PLAYER_COLLISION_WIDTH_EXAMPLE}, Space to Regen)")

    # Generate the layout
    map_data = get_random_circular_maze_layout(SCREEN_WIDTH, SCREEN_HEIGHT, PLAYER_COLLISION_WIDTH_EXAMPLE)
    fences = map_data['fences']
    starts = map_data['start_pos']

    # Create Pygame Rects for drawing
    fence_rects = [pygame.Rect(f) for f in fences]
    # Make start markers represent player size roughly for visual confirmation
    start_rects = [pygame.Rect(s[0]-PLAYER_COLLISION_WIDTH_EXAMPLE//2, s[1]-PLAYER_COLLISION_WIDTH_EXAMPLE//2, PLAYER_COLLISION_WIDTH_EXAMPLE, PLAYER_COLLISION_WIDTH_EXAMPLE) for s in starts]

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE: # Regenerate on spacebar
                     print("\n" + "="*30)
                     print("--- Regenerating Map ---")
                     print("="*30)
                     map_data = get_random_circular_maze_layout(SCREEN_WIDTH, SCREEN_HEIGHT, PLAYER_COLLISION_WIDTH_EXAMPLE)
                     fences = map_data['fences']
                     starts = map_data['start_pos']
                     fence_rects = [pygame.Rect(f) for f in fences]
                     start_rects = [pygame.Rect(s[0]-PLAYER_COLLISION_WIDTH_EXAMPLE//2, s[1]-PLAYER_COLLISION_WIDTH_EXAMPLE//2, PLAYER_COLLISION_WIDTH_EXAMPLE, PLAYER_COLLISION_WIDTH_EXAMPLE) for s in starts]

        # Drawing
        screen.fill((30, 30, 30)) # Dark gray background
        for fence in fence_rects:
            pygame.draw.rect(screen, (200, 200, 200), fence) # Light Gray fences

        # Draw Player start positions/sizes
        if start_rects:
            # Use Surface for alpha transparency
            s1 = pygame.Surface((PLAYER_COLLISION_WIDTH_EXAMPLE, PLAYER_COLLISION_WIDTH_EXAMPLE), pygame.SRCALPHA)
            s1.fill((0, 255, 0, 128)) # Semi-transparent Green
            screen.blit(s1, (start_rects[0].x, start_rects[0].y))
            pygame.draw.circle(screen, (255, 255, 255), starts[0], 3) # White center dot

        if len(start_rects) > 1:
            s2 = pygame.Surface((PLAYER_COLLISION_WIDTH_EXAMPLE, PLAYER_COLLISION_WIDTH_EXAMPLE), pygame.SRCALPHA)
            s2.fill((0, 0, 255, 128)) # Semi-transparent Blue
            screen.blit(s2, (start_rects[1].x, start_rects[1].y))
            pygame.draw.circle(screen, (255, 255, 255), starts[1], 3) # White center dot


        pygame.display.flip()

    pygame.quit()