# game_state.py
"""
Defines the main GameState class which manages the overall game logic,
entities, map loading, updates, drawing orchestration, and network state.
Can be run standalone for local testing or imported by main.py.
"""

import pygame
import math
import sys
import traceback # For detailed error reporting
import os

# --- Try Importing Custom Modules ---
MODULE_LOAD_ERRORS = []
try:
    import constants
    # Specifically check for PLAYER_RADIUS which is needed in update logic
    if not hasattr(constants, 'PLAYER_RADIUS'):
        raise ImportError("constants.py is missing PLAYER_RADIUS definition")
    print("Successfully imported constants.")
except ImportError as e: MODULE_LOAD_ERRORS.append(('constants', e))
try:
    # Ensure Projectile class handles its radius correctly (as per previous fixes)
    from entities import Fence, Projectile
    print("Successfully imported entities.")
except ImportError as e: MODULE_LOAD_ERRORS.append(('entities', e))
try:
    # --- MODIFIED IMPORT ---
    # Import the new/updated collision functions
    from collision import (check_player_fence_collision,
                           # Removed: check_projectile_fence_collision,
                           get_colliding_fence,           # Added
                           is_player_close_to_fence,    # Added
                           check_circle_collision,
                           get_closest_fence_in_proximity,
                           check_projectile_player_collision)
    print("Successfully imported collision functions.")
except ImportError as e: MODULE_LOAD_ERRORS.append(('collision', e))
try:
    from drawcode import (init_fonts, draw_health_bar,
                         draw_cooldown_indicator, render_text_with_bg,
                         load_gif_frames)
    print("Successfully imported drawcode functions.")
except ImportError as e: MODULE_LOAD_ERRORS.append(('drawcode', e))
try:
    from maps import get_random_circular_maze_layout
    print("Successfully imported maps functions.")
except ImportError as e: MODULE_LOAD_ERRORS.append(('maps', e))

# --- Exit if core modules are missing ---
if MODULE_LOAD_ERRORS:
    print(f"\n--- ERROR: Failed to import necessary game modules ---")
    for module_name, error in MODULE_LOAD_ERRORS:
        print(f"Missing/Error importing module: {module_name}.py - {error}")
    print("\nPlease ensure 'constants.py', 'entities.py', 'collision.py',")
    print("'drawcode.py', and 'maps.py' exist in the same directory or Python path.")
    print("-------------------------------------------------------\n")
    sys.exit(1)
# --- End Imports ---


# --- GameState Class ---
class GameState:
    def __init__(self):
        """Initializes the game state, loads the map, and sets up initial objects."""
        print("Initializing GameState...")
        # Directly use imported constants where needed
        self.width = constants.WIDTH
        self.height = constants.HEIGHT

        self.players = {} # Populated in reset
        self.fences = [] # Populated in _load_map
        self.projectiles = []
        self.game_over = False
        self.winner = None
        self.scores = {1: 0, 2: 0}
        self.start_positions = None # Will hold the *validated* start positions

        # Font objects (will be initialized by drawing module)
        self.fonts = {} # Dictionary to hold initialized fonts
        self._fonts_initialized = False

        # Load UI Assets
        self.fireball_ui_frames = []
        self._load_ui_assets()

        # Load map and validate start positions first
        try:
            self._load_map()
        except Exception as e:
             print(f"\n--- CRITICAL ERROR DURING MAP INITIALIZATION ---")
             print(f"{e}")
             traceback.print_exc()
             print("Exiting due to map load failure.")
             sys.exit(1)

        # Then reset the game state using the loaded map data
        self.reset()
        print("GameState initialization complete.")

    def _load_ui_assets(self):
        """Loads assets specifically for the UI, like the cooldown indicator GIF."""
        print("Loading UI assets...")
        # Ensure constant is defined before using it
        ui_gif_path = getattr(constants, 'FIREBALL_UI_GIF_PATH', None)
        ui_sprite_scale = getattr(constants, 'FIREBALL_UI_SPRITE_SCALE', None)

        if not ui_gif_path:
             print("--- WARNING ---")
             print("FIREBALL_UI_GIF_PATH not found in constants.py. Cannot load UI GIF.")
             self.fireball_ui_frames = []
             return

        # Ensure ui_gif_path is absolute if needed, relative paths can be tricky
        # Example: If constants.py defines it relative to the project root
        # base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Adjust if needed
        # ui_gif_path = os.path.join(base_path, ui_gif_path)

        if not os.path.exists(ui_gif_path):
             print(f"--- WARNING ---")
             print(f"UI Fireball GIF not found at the specified path: '{ui_gif_path}'")
             print(f"Cooldown indicator may use fallback or show nothing when ready.")
             self.fireball_ui_frames = []
        else:
             # Attempt to load using the function from drawcode
             try:
                 # Ensure load_gif_frames returns only the frames list
                 loaded_data = load_gif_frames(
                     ui_gif_path,
                     scale_to=ui_sprite_scale # Pass scale target
                 )
                 # Adjust based on what load_gif_frames actually returns
                 if isinstance(loaded_data, tuple) and len(loaded_data) > 0:
                     self.fireball_ui_frames = loaded_data[0] # Assuming frames are the first element
                 elif isinstance(loaded_data, list):
                      self.fireball_ui_frames = loaded_data # Assuming it returns just the list
                 else:
                     self.fireball_ui_frames = [] # Fallback

                 if self.fireball_ui_frames:
                     print(f"Successfully loaded {len(self.fireball_ui_frames)} UI fireball frames.")
                 else:
                      print(f"WARNING: load_gif_frames returned no frames for '{ui_gif_path}'.")
             except Exception as e:
                 print(f"--- ERROR during UI GIF loading ---")
                 print(f"An error occurred while trying to load '{ui_gif_path}':")
                 print(f"{e}")
                 traceback.print_exc()
                 print(f"Using fallback drawing for UI cooldown indicator.")
                 self.fireball_ui_frames = []

    def _init_fonts_if_needed(self):
        """Initializes fonts using the drawing module if not already done."""
        if not self._fonts_initialized:
            print("Initializing fonts via drawing module...")
            try:
                self.fonts = init_fonts(
                    font_sizes={
                        'score': constants.SCORE_FONT_SIZE,
                        'timer': constants.TIMER_FONT_SIZE,
                        'win': constants.WIN_FONT_SIZE,
                        'prompt': constants.PROMPT_FONT_SIZE,
                        'exit': constants.EXIT_FONT_SIZE
                    },
                    font_names={
                         'default': constants.DEFAULT_FONT_NAMES,
                         'mono': constants.MONO_FONT_NAMES,
                         'impact': constants.IMPACT_FONT_NAMES
                    }
                )
                self._fonts_initialized = True
                if not all(self.fonts.values()):
                    print("Warning: One or more fonts failed to load.")
            except Exception as e:
                 print(f"FATAL ERROR during font initialization: {e}")
                 traceback.print_exc()
                 print("Continuing without fonts...")
                 self._fonts_initialized = True # Mark as 'done' even if failed


    def _find_free_spawn_position(self, start_x, start_y, radius, fences):
        """
        Checks if a start position is valid (not colliding with fences).
        If it collides, searches nearby for a free spot using collision functions.
        Returns a tuple (x, y) of a valid position.
        """
        original_pos = (int(start_x), int(start_y))
        player_r = int(radius)

        # Clamp initial position within bounds first
        clamped_x = max(player_r, min(self.width - player_r, original_pos[0]))
        clamped_y = max(player_r, min(self.height - player_r, original_pos[1]))
        clamped_pos = (clamped_x, clamped_y)

        # Check if the clamped position is already free
        if not check_player_fence_collision(clamped_x, clamped_y, player_r, fences):
            return clamped_pos

        # If not free, search outwards in a spiral
        search_step = max(1, player_r // 2) # How far to step out each iteration
        max_search_radius = player_r * 6    # How far out to search max
        num_directions = 8                  # Check N, NE, E, SE, S, SW, W, NW

        for current_radius in range(search_step, max_search_radius + 1, search_step):
            for i in range(num_directions):
                angle = (2 * math.pi / num_directions) * i
                dx = math.cos(angle) * current_radius
                dy = math.sin(angle) * current_radius
                test_x = int(clamped_pos[0] + dx)
                test_y = int(clamped_pos[1] + dy)

                # Clamp the test position within bounds
                test_x = max(player_r, min(self.width - player_r, test_x))
                test_y = max(player_r, min(self.height - player_r, test_y))

                # Check if this test position is free
                if not check_player_fence_collision(test_x, test_y, player_r, fences):
                    # print(f"Found free spawn at ({test_x},{test_y}) for original {original_pos}") # Optional Debug
                    return (test_x, test_y)

        # If no free spot found after searching, return the original (clamped) position as a fallback
        print(f"Warning: Could not find clear spawn near {original_pos}. Using fallback {clamped_pos}.")
        return clamped_pos


    def _load_map(self):
        """Loads map layout using maps module, creates Fence entities, validates start positions."""
        print("Loading map layout via maps module...")
        try:
            # Get map data (fences and suggested start positions)
            map_data = get_random_circular_maze_layout(self.width, self.height, constants.PLAYER_COLLISION_WIDTH)

            fence_layout_data = map_data.get('fences', [])
            generated_starts = map_data.get('start_pos', [])

            # Create Fence objects from layout data
            self.fences = []
            fence_id_counter = 0
            for item in fence_layout_data:
                 if isinstance(item, (list, tuple)) and len(item) == 4:
                    try:
                         x, y, w, h = int(item[0]), int(item[1]), int(item[2]), int(item[3])
                         # Ensure fences have positive dimensions
                         if w > 0 and h > 0:
                             self.fences.append(Fence(x, y, w, h, id=fence_id_counter))
                             fence_id_counter += 1
                         else:
                             print(f"Warning: Skipping fence layout item with zero/negative size: {item}")
                    except (ValueError, TypeError) as e:
                         print(f"Warning: Skipping invalid fence layout item: {item}. Error: {e}")
                 else:
                    print(f"Warning: Skipping invalid fence layout item format: {item}")
            print(f"Created {len(self.fences)} Fence objects from map layout.")

            # Validate the suggested start positions
            validated_starts = []
            default_used = False
            if isinstance(generated_starts, list) and len(generated_starts) >= 2:
                print("Validating suggested start positions...")
                for i in range(2): # Expecting two start positions
                    pos = generated_starts[i]
                    if isinstance(pos, (list, tuple)) and len(pos) == 2 and \
                       all(isinstance(coord, (int, float)) for coord in pos):
                        # Find a guaranteed free position near the suggestion
                        free_pos = self._find_free_spawn_position(pos[0], pos[1], constants.PLAYER_RADIUS, self.fences)
                        validated_starts.append(free_pos)
                    else:
                        print(f"Warning: Invalid start format {pos} for P{i+1}. Using default.")
                        validated_starts.append(None) # Mark as needing default
                        default_used = True
            else:
                print("Warning: Map didn't return 2 valid start suggestions. Using defaults.")
                default_used = True

            # If defaults were needed or validation failed, use/find default positions
            if default_used or len(validated_starts) < 2 or None in validated_starts:
                 print("Using/validating default start positions...")
                 default_pos1 = (self.width * 0.25, self.height * 0.5)
                 default_pos2 = (self.width * 0.75, self.height * 0.5)
                 final_starts = []

                 # Use validated position if available, otherwise find free spot near default
                 pos1 = validated_starts[0] if len(validated_starts) > 0 and validated_starts[0] else None
                 final_starts.append(pos1 if pos1 else self._find_free_spawn_position(default_pos1[0], default_pos1[1], constants.PLAYER_RADIUS, self.fences))

                 pos2 = validated_starts[1] if len(validated_starts) > 1 and validated_starts[1] else None
                 final_starts.append(pos2 if pos2 else self._find_free_spawn_position(default_pos2[0], default_pos2[1], constants.PLAYER_RADIUS, self.fences))

                 self.start_positions = final_starts
            else:
                 # Both suggested positions were validated successfully
                 self.start_positions = validated_starts

            print(f"Final validated start positions: P1={self.start_positions[0]}, P2={self.start_positions[1]}")

        except ImportError:
             print("ERROR: Could not import 'get_random_circular_maze_layout' from 'maps.py'.")
             raise # Re-raise to stop execution
        except TypeError as e:
             print(f"ERROR: Unexpected data structure from maps.py or during processing. Error: {e}")
             traceback.print_exc()
             raise # Re-raise
        except Exception as e:
             print(f"ERROR: Unexpected error during map loading: {e}")
             traceback.print_exc()
             raise # Re-raise


    def reset(self):
        """Resets game state (players, fences, projectiles) using the validated start positions."""
        print("Resetting game state...")

        # Ensure start positions are available before resetting players
        if not self.start_positions or len(self.start_positions) < 2:
             print("CRITICAL ERROR: Validated start positions unavailable during reset! Finding fallback positions.")
             # Define and find fallback positions *again* just in case _load_map failed silently earlier
             fallback_start1 = (self.width // 4, self.height // 2)
             fallback_start2 = (self.width * 3 // 4, self.height // 2)
             # Use _find_free_spawn_position to ensure they aren't inside walls
             start_pos1 = self._find_free_spawn_position(fallback_start1[0], fallback_start1[1], constants.PLAYER_RADIUS, self.fences)
             start_pos2 = self._find_free_spawn_position(fallback_start2[0], fallback_start2[1], constants.PLAYER_RADIUS, self.fences)
             self.start_positions = [start_pos1, start_pos2] # Store the found fallback positions
             print(f"  -> Fallback start positions used: {self.start_positions}")
        else:
             # Use the previously validated start positions
             start_pos1, start_pos2 = self.start_positions

        # Initialize player states
        self.players = {
             1: {"x": float(start_pos1[0]), "y": float(start_pos1[1]), "hp": constants.MAX_HP,
                 "last_shot_time": 0, "last_fireball_time": 0,
                 "color": constants.WHITE, "last_dx": 1, "last_dy": 0, # Start facing right
                 "cooldown_anim_frame_index": 0, "cooldown_anim_last_update": 0 },
             2: {"x": float(start_pos2[0]), "y": float(start_pos2[1]), "hp": constants.MAX_HP,
                 "last_shot_time": 0, "last_fireball_time": 0,
                 "color": constants.RED, "last_dx": -1, "last_dy": 0, # Start facing left
                 "cooldown_anim_frame_index": 0, "cooldown_anim_last_update": 0 }
        }
        # Reset fences to initial state
        for fence in self.fences:
            fence.reset()
        # Clear projectiles and reset ID counter
        self.projectiles = []
        Projectile.next_id = 0
        # Reset game over flags
        self.game_over = False
        self.winner = None
        print("Game state reset complete.")


    def update(self, p1_input, p2_input, current_time_ticks):
        """Updates the game state based on player inputs and time."""
        if self.game_over: return # Don't update if game is over

        inputs = {1: p1_input, 2: p2_input}

        # --- Player Movement ---
        for p_id, player in self.players.items():
            if player["hp"] <= 0: continue # Skip dead players

            input_data = inputs.get(p_id, {})
            keys = input_data.get('keys', {})
            move_dx, move_dy = 0, 0

            # Determine movement direction based on input keys
            if keys.get('a'): move_dx -= 1
            if keys.get('d'): move_dx += 1
            if keys.get('w'): move_dy -= 1
            if keys.get('s'): move_dy += 1

            # Store the last non-zero movement direction for shooting/abilities
            if move_dx != 0 or move_dy != 0:
                player["last_dx"], player["last_dy"] = move_dx, move_dy
            # If player stops moving, player["last_dx"/"last_dy"] retains the last facing direction

            # Calculate potential movement delta, normalize for diagonal movement
            potential_dx = move_dx * constants.PLAYER_SPEED
            potential_dy = move_dy * constants.PLAYER_SPEED
            if move_dx != 0 and move_dy != 0:
                 # Normalize diagonal speed (multiply by 1/sqrt(2))
                 norm_factor = 0.70710678118 # Approx 1/sqrt(2)
                 potential_dx *= norm_factor
                 potential_dy *= norm_factor

            # Calculate potential new position
            potential_x = player["x"] + potential_dx
            potential_y = player["y"] + potential_dy

            # Clamp potential position within screen bounds (using player radius)
            player_r = constants.PLAYER_RADIUS
            potential_x = max(player_r, min(self.width - player_r, potential_x))
            potential_y = max(player_r, min(self.height - player_r, potential_y))

            # Store current position for collision checks
            old_x, old_y = player["x"], player["y"]
            new_x, new_y = old_x, old_y # Start assuming no movement possible

            # Check collision with the other player
            other_p_id = 3 - p_id # Get the ID of the other player (1 -> 2, 2 -> 1)
            other_player = self.players.get(other_p_id)
            can_collide_other = other_player and other_player.get("hp", 0) > 0 # Can only collide if other player exists and is alive

            # --- Axis-by-axis collision check for smoother movement against obstacles ---
            # Try moving horizontally (X-axis)
            temp_x = potential_x
            collision_x = False
            # Check X-move against other player
            if can_collide_other and check_circle_collision(temp_x, old_y, player_r, other_player["x"], other_player["y"], player_r):
                collision_x = True
            # Check X-move against fences (only if no player collision)
            if not collision_x and check_player_fence_collision(temp_x, old_y, player_r, self.fences):
                collision_x = True
            # If no collision on X-axis, accept the horizontal movement
            if not collision_x:
                new_x = temp_x

            # Try moving vertically (Y-axis) - using the potentially updated new_x
            temp_y = potential_y
            collision_y = False
            # Check Y-move against other player (at the potentially new X position)
            if can_collide_other and check_circle_collision(new_x, temp_y, player_r, other_player["x"], other_player["y"], player_r):
                collision_y = True
            # Check Y-move against fences (at the potentially new X position, only if no player collision)
            if not collision_y and check_player_fence_collision(new_x, temp_y, player_r, self.fences):
                 collision_y = True
            # If no collision on Y-axis, accept the vertical movement
            if not collision_y:
                new_y = temp_y

            # Update player position with the final resolved coordinates
            player["x"] = new_x
            player["y"] = new_y


        # --- Player Actions (Shooting, Interacting) ---
        projectiles_this_frame = [] # Store projectiles created this frame for immediate checks (fireballs mainly)
        for p_id, player in self.players.items():
            if player["hp"] <= 0: continue # Skip dead players

            input_data = inputs.get(p_id, {})
            action_interact = input_data.get('action_interact', False)
            action_shoot = input_data.get('action_shoot', False)
            action_fireball = input_data.get('action_fireball', False)

            # --- Interact with fences ---
            if action_interact:
                # Use get_closest_fence_in_proximity to find interactable fence
                # Note: The function signature was simplified in the previous step to only take player x, y, and fences list
                closest_fence_id = get_closest_fence_in_proximity(
                    player["x"], player["y"], self.fences
                )

                if closest_fence_id != -1: # -1 indicates no fence in range
                    # Find the actual Fence object using the ID
                    fence_to_toggle = next((f for f in self.fences if hasattr(f, 'id') and f.id == closest_fence_id), None)
                    if fence_to_toggle:
                        # Attempt to toggle the fence (checks internal cooldown)
                        toggled = fence_to_toggle.toggle(player_id=p_id, current_time_ticks=current_time_ticks)
                        # if toggled: print(f"Player {p_id} toggled fence {closest_fence_id}") # Optional debug

            # --- Shoot normal projectile ---
            if action_shoot and current_time_ticks - player["last_shot_time"] > constants.SHOOT_COOLDOWN_MS:
                player["last_shot_time"] = current_time_ticks # Update cooldown timer
                # Use the last stored facing direction
                direction_x, direction_y = player["last_dx"], player["last_dy"]
                if direction_x == 0 and direction_y == 0: continue # Should not happen if last_dx/dy logic is correct

                # Normalize the direction vector
                magnitude = math.hypot(direction_x, direction_y)
                if magnitude > 0: # Avoid division by zero
                    norm_dx = direction_x / magnitude
                    norm_dy = direction_y / magnitude

                    # Calculate projectile velocity
                    proj_vx = norm_dx * constants.PROJECTILE_SPEED
                    proj_vy = norm_dy * constants.PROJECTILE_SPEED

                    # Calculate spawn position just outside the player radius + projectile radius
                    offset_dist = constants.PLAYER_RADIUS + constants.PROJECTILE_RADIUS + 2 # Small buffer
                    spawn_x = player["x"] + norm_dx * offset_dist
                    spawn_y = player["y"] + norm_dy * offset_dist

                    # Create and add the projectile
                    new_proj = Projectile(spawn_x, spawn_y, proj_vx, proj_vy, owner_id=p_id, proj_type="normal")
                    self.projectiles.append(new_proj)
                    # print(f"Player {p_id} fired normal projectile {new_proj.id}") # Optional debug

            # --- Shoot fireball ---
            if action_fireball and current_time_ticks - player["last_fireball_time"] > constants.FIREBALL_COOLDOWN_MS:
                player["last_fireball_time"] = current_time_ticks # Update cooldown timer
                # Use the last stored facing direction
                direction_x, direction_y = player["last_dx"], player["last_dy"]
                if direction_x == 0 and direction_y == 0: continue # Should not happen

                # Normalize the direction vector
                magnitude = math.hypot(direction_x, direction_y)
                if magnitude > 0: # Avoid division by zero
                    norm_dx = direction_x / magnitude
                    norm_dy = direction_y / magnitude

                    # Calculate fireball velocity
                    proj_vx = norm_dx * constants.FIREBALL_SPEED
                    proj_vy = norm_dy * constants.FIREBALL_SPEED

                    # Get fireball's collision radius (ensure constant exists and is correct)
                    try:
                        # Assumes FIREBALL_RADIUS is the *collision* radius defined in constants
                        fireball_radius = constants.FIREBALL_RADIUS
                    except AttributeError:
                        print("Warning: constants.FIREBALL_RADIUS not found. Using fallback from Projectile class.")
                        # Fallback to the value used within the Projectile class if constant missing
                        fireball_radius = getattr(constants, 'FIREBALL_FALLBACK_RADIUS', 10) # Or directly use the default value


                    # Calculate spawn position just outside player + fireball radius
                    offset_dist = constants.PLAYER_RADIUS + fireball_radius + 2 # Small buffer
                    spawn_x = player["x"] + norm_dx * offset_dist
                    spawn_y = player["y"] + norm_dy * offset_dist

                    # Create the Fireball Projectile instance
                    new_fireball = Projectile(spawn_x, spawn_y, proj_vx, proj_vy, owner_id=p_id, proj_type="fireball")
                    self.projectiles.append(new_fireball)
                    projectiles_this_frame.append(new_fireball) # Add for immediate hit check below
                    # print(f"Player {p_id} fired fireball {new_fireball.id}") # Optional debug

        # --- Immediate Fireball Collision Check (Optional but good for feel) ---
        # Checks if a fireball hit someone *immediately* upon spawning (if players are overlapping)
        if not self.game_over: # Only perform if game isn't already over
            p1_data_for_check = self.players.get(1)
            p2_data_for_check = self.players.get(2)
            for fireball in projectiles_this_frame:
                # Check only fireballs created this frame that are still active
                if fireball.type == "fireball" and fireball.active:
                    target_player_id = 3 - fireball.owner_id # The other player is the intended target

                    # Check if the fireball immediately collided with ANY player
                    immediate_hit_id = check_projectile_player_collision(
                        fireball, p1_data_for_check, p2_data_for_check
                    )

                    # If it immediately hit the *intended target* player
                    if immediate_hit_id == target_player_id:
                        target_player = self.players.get(target_player_id)
                        if target_player:
                            # print(f"DEBUG: Immediate fireball hit P{target_player_id} on spawn!") # Debug
                            # Apply damage (using factor from constants)
                            try:
                                damage = math.ceil(target_player["hp"] * constants.FIREBALL_DAMAGE_FACTOR)
                            except AttributeError:
                                print("Warning: FIREBALL_DAMAGE_FACTOR not in constants. Using default damage 1.")
                                damage = 1
                            target_player["hp"] -= damage
                            print(f"Player {target_player_id} hit immediately by P{fireball.owner_id}'s fireball! HP: {target_player['hp']}/{constants.MAX_HP}")

                            # Check for game over immediately due to this hit
                            if target_player["hp"] <= 0:
                                target_player["hp"] = 0 # Clamp HP at 0
                                self.game_over = True
                                self.winner = fireball.owner_id
                                self.scores[self.winner] = self.scores.get(self.winner, 0) + 1
                                print(f"GAME OVER (Immediate Hit)! Player {self.winner} wins! Score: P1={self.scores.get(1,0)}, P2={self.scores.get(2,0)}")
                                # Deactivate the fireball immediately since it hit
                                fireball.active = False
                                # Game is over, no need to check other immediate hits
                                break

                            # If game not over, still deactivate the fireball (it hit)
                            fireball.active = False
                            # Note: It will be processed by the removal loop later

        # --- Projectile Update & Main Collision Loop ---
        projectiles_to_remove = set() # Use a set for efficient ID management
        if not self.game_over: # Don't process projectile movement/collision if game ended from immediate hit
            # Iterate backwards to allow safe removal while iterating
            for i in range(len(self.projectiles) - 1, -1, -1):
                proj = self.projectiles[i]

                # Skip projectiles already marked inactive (e.g., from immediate hit)
                if not proj.active:
                    projectiles_to_remove.add(proj.id)
                    continue

                # Update projectile position, animation state, and check if it went off-screen
                proj.update()

                # If proj.update() set active to False (e.g., went off-screen)
                if not proj.active:
                    projectiles_to_remove.add(proj.id)
                    # print(f"Projectile {proj.id} deactivated (off-screen).") # Debug
                    continue # Move to the next projectile

                # --- MODIFIED FENCE COLLISION LOGIC ---
                collided_fence = get_colliding_fence(proj, self.fences)
                if collided_fence:
                    # A collision with a closed fence occurred. Now check player proximity.
                    owner_player_state = self.players.get(proj.owner_id)

                    owner_is_near = False # Assume owner is not near by default
                    if owner_player_state:
                        try:
                            # Check if the owner player is close to the specific fence hit
                            owner_is_near = is_player_close_to_fence(
                                owner_player_state['x'],
                                owner_player_state['y'],
                                constants.PLAYER_RADIUS, # Player's collision radius
                                collided_fence           # The specific fence object hit
                            )
                        except KeyError:
                            print(f"Warning: Owner player {proj.owner_id} state missing 'x' or 'y' for proximity check.")
                        except Exception as e:
                            print(f"Error checking player {proj.owner_id} proximity to fence {collided_fence.id}: {e}")

                    # Deactivate the projectile ONLY if the owner is NOT near the wall hit
                    if not owner_is_near:
                        proj.active = False
                        projectiles_to_remove.add(proj.id)
                        # print(f"Projectile {proj.id} deactivated: Hit fence {collided_fence.id} and owner {proj.owner_id} is NOT near.") # Debug
                        continue # Move to the next projectile
                    else:
                         # Owner IS near the fence, let the projectile pass through *this time*
                         # print(f"Projectile {proj.id} continues: Hit fence {collided_fence.id} BUT owner {proj.owner_id} IS near.") # Debug
                         # Do nothing here, the loop continues, projectile remains active
                         pass
                # --- END MODIFIED FENCE COLLISION LOGIC ---


                # Check collision with players (this handles standard projectile travel hits)
                # Only check player collision if it didn't hit a fence and get deactivated (or allowed through)
                if proj.active: # Check active status again
                    hit_player_id = check_projectile_player_collision(
                        proj, self.players.get(1), self.players.get(2)
                    )

                    if hit_player_id is not None:
                        # Projectile hit a player
                        target_player = self.players.get(hit_player_id)
                        if target_player: # Ensure target player data exists
                            # Apply damage based on projectile type
                            damage = 0
                            if proj.type == "fireball":
                                try: damage = math.ceil(target_player["hp"] * constants.FIREBALL_DAMAGE_FACTOR)
                                except AttributeError: damage = 1 # Fallback damage
                            else: # Normal projectile
                                try: damage = constants.NORMAL_PROJECTILE_DAMAGE
                                except AttributeError: damage = 1 # Fallback damage

                            target_player["hp"] -= damage
                            print(f"Player {hit_player_id} hit by P{proj.owner_id}'s {proj.type}! HP: {target_player['hp']}/{constants.MAX_HP}")

                            # Check for game over
                            if target_player["hp"] <= 0:
                                target_player["hp"] = 0 # Clamp HP
                                self.game_over = True
                                self.winner = proj.owner_id # The owner of the projectile wins
                                self.scores[self.winner] = self.scores.get(self.winner, 0) + 1
                                print(f"GAME OVER! Player {self.winner} wins! Score: P1={self.scores.get(1,0)}, P2={self.scores.get(2,0)}")

                                # Deactivate the projectile that got the kill
                                proj.active = False
                                projectiles_to_remove.add(proj.id)

                                # --- IMPORTANT: Clear ALL active projectiles on game over ---
                                # Add all remaining active projectile IDs to the removal set
                                for p_other in self.projectiles:
                                    if p_other.active:
                                        projectiles_to_remove.add(p_other.id)
                                # ---------------------------------------------------------
                                break # Exit the projectile processing loop as game is over

                        # If game didn't end, deactivate the projectile because it hit a player
                        if proj.active: # Check again in case game over happened
                             proj.active = False
                             projectiles_to_remove.add(proj.id)
                             # print(f"Projectile {proj.id} deactivated (hit player {hit_player_id}).") # Debug
                        # Continue checking other projectiles unless game over

        # Filter out inactive projectiles after all updates and checks are done
        if projectiles_to_remove:
            # Create a new list containing only the projectiles whose IDs are NOT in the removal set
            self.projectiles[:] = [p for p in self.projectiles if p.id not in projectiles_to_remove]
            # print(f"Removed {len(projectiles_to_remove)} projectiles. Remaining: {len(self.projectiles)}") # Debug


    def draw(self, surface, current_time_ticks):
        """Orchestrates drawing the entire game state onto the surface."""
        self._init_fonts_if_needed() # Ensure fonts are loaded
        surface.fill(constants.BLACK) # Clear screen

        # Draw Fences
        timer_font = self.fonts.get('timer') # Get the font for cooldown timers
        for fence in self.fences:
            # Fence draw method handles open/closed color and cooldown text
            fence.draw(surface, current_time_ticks, timer_font)

        # Draw Projectiles
        for proj in self.projectiles:
             # Projectile draw method handles animation or fallback circle
             if proj.active: # Only draw active projectiles
                 proj.draw(surface)

        # Draw Players and Health Bars
        for p_id, player in self.players.items():
            if player.get("hp", 0) > 0: # Only draw alive players
                try:
                    pos = (int(player["x"]), int(player["y"]))
                    color = player.get("color", constants.WHITE) # Use player color or default
                    radius = constants.PLAYER_RADIUS
                    pygame.draw.circle(surface, color, pos, radius)
                    # Draw health bar above the player
                    draw_health_bar(surface, player["x"], player["y"], player["hp"], constants.MAX_HP)
                except (ValueError, TypeError) as e:
                    # Catch potential errors if player data is corrupted
                    print(f"Warning: Error drawing player {p_id}: {e} - Data: {player}")

        # Draw Scoreboard
        score_font = self.fonts.get('score')
        if score_font:
            try:
                score_text = f"P1: {self.scores.get(1, 0)}  -  P2: {self.scores.get(2, 0)}"
                # Render score text without background at the top center
                render_text_with_bg(
                    surface, score_font, score_text, constants.CYAN,
                    bg_color=(0,0,0,0), # Transparent background
                    center_pos=(self.width // 2, 25), # Position near top center
                    padding=(0,0) # No padding needed without background
                )
            except Exception as e: print(f"Warning: Error rendering score: {e}")

        # Draw Cooldown Indicators (for Fireball)
        try:
            # Get player data safely
            p1_data = self.players.get(1)
            p2_data = self.players.get(2)
            # Draw indicator for Player 1 if data exists
            if p1_data:
                draw_cooldown_indicator(surface, 1, p1_data, current_time_ticks, self.fireball_ui_frames)
            # Draw indicator for Player 2 if data exists
            if p2_data:
                draw_cooldown_indicator(surface, 2, p2_data, current_time_ticks, self.fireball_ui_frames)
        except Exception as e:
             # Catch potential errors in the drawing function or data access
             print(f"Error calling draw_cooldown_indicator: {e}")
             traceback.print_exc()

        # Draw Game Over Screen (if applicable)
        if self.game_over and self.winner is not None:
             win_font = self.fonts.get('win')
             prompt_font = self.fonts.get('prompt')
             exit_font = self.fonts.get('exit')
             last_rect = None # Keep track of last text rect for positioning

             # Render "Player X Wins!" text
             if win_font:
                last_rect = render_text_with_bg(
                    surface, win_font, f"Player {self.winner} Wins!",
                    constants.ORANGE, center_pos=(self.width // 2, self.height // 2 - 30)
                )

             # Render "Press ENTER to Play Again" text below the win message
             if prompt_font:
                 prompt_y = (last_rect.bottom + 40) if last_rect else (self.height // 2 + 40)
                 last_rect = render_text_with_bg(
                     surface, prompt_font, "Press ENTER to Play Again",
                     constants.WHITE, center_pos=(self.width // 2, prompt_y)
                 )

             # Render "Press ESC to Exit" text near the bottom
             if exit_font:
                 render_text_with_bg(
                     surface, exit_font, "Press ESC to Exit",
                     constants.WHITE, center_pos=(self.width // 2, self.height - 30)
                 )


    # --- Network State Methods ---
    def get_network_state(self):
        """Gets a serializable state for network transmission."""
        # Get states of only active projectiles
        active_proj_states = [p.get_state() for p in self.projectiles if p.active]
        # Get states of all fences
        fence_states = [f.get_state() for f in self.fences]
        # Create a simplified player state suitable for network (excluding local-only data)
        serializable_players = {}
        for p_id, p_data in self.players.items():
             serializable_players[str(p_id)] = { # Use string keys for JSON compatibility
                 k: v for k, v in p_data.items()
                 # Exclude client-side only data like color and animation state
                 if k not in ['color', 'cooldown_anim_frame_index', 'cooldown_anim_last_update']
            }
        # Assemble the full network state dictionary
        return {
            "players": serializable_players,
            "fences": fence_states,
            "projectiles": active_proj_states,
            "game_over": self.game_over,
            "winner": self.winner,
            "scores": self.scores,
            "next_proj_id": Projectile.next_id # Sync projectile ID counter
        }

    def set_network_state(self, network_state):
        """Updates the local game state based on received network data."""
        if not isinstance(network_state, dict):
             print("Warning: Invalid network state received (not a dict). Discarding.")
             return

        # Update Scores (with type checking)
        received_scores = network_state.get("scores")
        if isinstance(received_scores, dict):
             try:
                 # Convert keys/values to int robustly
                 self.scores = {int(k): int(v) for k, v in received_scores.items()}
             except (ValueError, TypeError): print("Warning: Invalid score data format received.")
        # else: Don't update scores if format is wrong

        # Update Game Over State
        self.game_over = network_state.get("game_over", self.game_over) # Keep local if missing
        self.winner = network_state.get("winner", self.winner)         # Keep local if missing

        # Update Players (robustly handle missing data and type errors)
        received_players = network_state.get("players", {})
        if isinstance(received_players, dict):
            for p_id_str, p_state in received_players.items():
                try:
                    p_id_int = int(p_id_str) # Convert string key back to int
                    # Check if player ID exists locally and received state is a dict
                    if p_id_int in self.players and isinstance(p_state, dict):
                         player_local = self.players[p_id_int]
                         # Update each attribute, falling back to local value if missing/invalid in network state
                         player_local["x"] = float(p_state.get("x", player_local.get("x", 0)))
                         player_local["y"] = float(p_state.get("y", player_local.get("y", 0)))
                         player_local["hp"] = int(p_state.get("hp", player_local.get("hp", 0)))
                         player_local["last_shot_time"] = int(p_state.get("last_shot_time", player_local.get("last_shot_time", 0)))
                         player_local["last_fireball_time"] = int(p_state.get("last_fireball_time", player_local.get("last_fireball_time", 0)))
                         player_local["last_dx"] = int(p_state.get("last_dx", player_local.get("last_dx", 0)))
                         player_local["last_dy"] = int(p_state.get("last_dy", player_local.get("last_dy", 0)))
                except (ValueError, TypeError, KeyError) as e:
                    print(f"Warning: Failed to update player data for ID '{p_id_str}'. Error: {e}. Data: {p_state}")
        # else: Don't update players if format is wrong

        # Update Fences
        received_fences = network_state.get("fences", [])
        if isinstance(received_fences, list):
            # Create a map of server fence states by ID for quick lookup
            server_fence_map = {fs.get('id'): fs for fs in received_fences if isinstance(fs, dict) and 'id' in fs}
            # Update local fences based on server state
            for fence in self.fences:
                if hasattr(fence, 'id') and fence.id in server_fence_map:
                    try:
                        fence.set_state(server_fence_map[fence.id])
                    except Exception as e:
                        print(f"Warning: Failed to set state for fence {fence.id}. Error: {e}")
        # else: Don't update fences if format is wrong

        # Update Projectiles (crucial for synchronization)
        if self.game_over:
             # If server says game is over, client should have no active projectiles
             if self.projectiles: # Only clear if needed
                 # print("Clearing local projectiles due to server game over state.") # Debug
                 self.projectiles = []
        else:
            # Game is not over according to server, sync projectiles
            received_projectiles = network_state.get("projectiles", [])
            if not isinstance(received_projectiles, list):
                print("Warning: Invalid projectiles format received. Clearing local projectiles.")
                received_projectiles = [] # Treat invalid format as no projectiles
                self.projectiles = []     # Clear local ones too for safety

            # Create a map of server projectile states by ID
            server_proj_map = {ps.get('id'): ps for ps in received_projectiles
                               if isinstance(ps, dict) and ps.get('id') is not None}
            # Create a map of current local active projectiles by ID
            current_proj_map = {p.id: p for p in self.projectiles if p.active}

            new_projectile_list = [] # Build the updated list of projectiles
            processed_server_ids = set() # Track IDs processed from server data
            max_server_id = -1 # Track the highest projectile ID seen from server

            # --- Step 1: Update or keep existing local projectiles ---
            for proj_id, proj in current_proj_map.items():
                if proj_id in server_proj_map:
                    # Projectile exists both locally and on server: update state
                    proj_state = server_proj_map[proj_id]
                    try:
                        proj.set_state(proj_state)
                        # Only keep it if the server state confirms it's still active
                        if proj.active:
                            new_projectile_list.append(proj)
                        # else: print(f"Projectile {proj_id} removed (inactive on server).") # Debug
                    except Exception as e:
                         print(f"Warning: Failed to set state for projectile {proj_id}. Error: {e}")
                         # Decide whether to keep the projectile in its old state or remove it?
                         # Removing might be safer if state update fails.
                    processed_server_ids.add(proj_id) # Mark as processed
                    max_server_id = max(max_server_id, proj_id)
                # else:
                    # Projectile exists locally but not on server -> remove it
                    # print(f"Projectile {proj_id} removed (not found on server).") # Debug
                    pass # Implicitly removed by not adding to new_projectile_list

            # --- Step 2: Add new projectiles from server ---
            for proj_id, proj_state in server_proj_map.items():
                 if proj_id not in processed_server_ids:
                     # This is a projectile that exists on server but not locally
                     try:
                         # Create a new projectile instance (use dummy initial values)
                         # The 'type' is needed for correct initialization within set_state
                         proj_type = proj_state.get("type", "normal") # Default type if missing
                         # Need to ensure the Projectile class can be initialized minimally
                         # and fully populated by set_state. Let's assume it can.
                         new_proj = Projectile(0, 0, 0, 0, 0, proj_type=proj_type)
                         new_proj.id = proj_id # Crucial: Set ID *before* set_state
                         new_proj.set_state(proj_state)
                         # Only add if the received state indicates it's active
                         if new_proj.active:
                             new_projectile_list.append(new_proj)
                             # print(f"Added new projectile {proj_id} from server.") # Debug
                         max_server_id = max(max_server_id, proj_id)
                     except Exception as e:
                         print(f"Warning: Failed to create/set new projectile {proj_id} from state {proj_state}. Error: {e}")

            # Replace the old projectile list with the synchronized one
            self.projectiles = new_projectile_list

            # --- Step 3: Synchronize the next projectile ID counter ---
            # This prevents ID collisions if client and server create projectiles concurrently
            server_next_id = network_state.get("next_proj_id")
            try:
                 # The next ID should be at least one higher than the highest ID seen
                 next_id_candidate = max(Projectile.next_id, max_server_id + 1)
                 # If server provided a next_id, use the maximum of local candidate and server's suggestion
                 if server_next_id is not None:
                     next_id_to_set = max(next_id_candidate, int(server_next_id))
                 else:
                     next_id_to_set = next_id_candidate
                 # Update the class variable
                 Projectile.next_id = next_id_to_set
            except (ValueError, TypeError):
                 # Fallback if server_next_id is invalid format
                 Projectile.next_id = max(Projectile.next_id, max_server_id + 1)


# --- Standalone Execution Block (for local testing) ---
if __name__ == "__main__":
    print("Running game_state.py in standalone local test mode...")
    print("(This mode uses local keyboard input for both players)")

    pygame.init()

    # Setup screen and clock
    screen = pygame.display.set_mode((constants.WIDTH, constants.HEIGHT))
    pygame.display.set_caption("Game State Standalone Test (Local Play)")
    clock = pygame.time.Clock()

    # Initialize Game State (catch critical errors here)
    try:
        the_game_state = GameState()
        print("\nGameState initialized successfully for local test.")
        # Preload projectile assets if desired (should load on demand now)
        # You might want to explicitly load fireball assets here if testing locally
        # to ensure they are ready before the first shot.
        try:
            if not Projectile.fireball_assets_loaded:
                 Projectile.load_fireball_assets()
        except Exception as asset_e:
            print(f"Warning: Failed to preload fireball assets: {asset_e}")

    except Exception as e:
        print(f"\n--- CRITICAL ERROR DURING GAME INITIALIZATION ---")
        print(f"{e}")
        traceback.print_exc()
        pygame.quit()
        sys.exit(1)

    # Print controls for local testing
    print("\n--- Controls (Standalone Test) ---")
    print("Player 1 (White): WASD (Move), E (Interact), Space (Shoot), R (Fireball)")
    print("Player 2 (Red):   Arrow Keys (Move), / (Interact), RShift (Shoot), RCtrl (Fireball)")
    print("Reset Game:       Enter (when game is over)")
    print("Exit Game:        ESC")
    print("------------------------------------\n")

    running = True
    while running:
        current_time = pygame.time.get_ticks() # Get current time for updates

        # --- Input Handling for Standalone Mode ---
        # Reset input states each frame
        p1_input = {'keys': {}, 'action_interact': False, 'action_shoot': False, 'action_fireball': False}
        p2_input = {'keys': {}, 'action_interact': False, 'action_shoot': False, 'action_fireball': False}

        # Process Pygame events
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False # Handle window close
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: running = False # Handle ESC key for exit

                # Handle reset only if game is over
                elif the_game_state.game_over:
                    if event.key == pygame.K_RETURN:
                        the_game_state.reset()
                        # Optionally preload assets again on reset if needed
                        # if not Projectile.fireball_assets_loaded: Projectile.load_fireball_assets()

                # Handle actions only if game is *not* over
                else:
                    # Player 1 Actions (Single press actions)
                    if event.key == pygame.K_e: p1_input['action_interact'] = True
                    if event.key == pygame.K_SPACE: p1_input['action_shoot'] = True
                    if event.key == pygame.K_r: p1_input['action_fireball'] = True
                    # Player 2 Actions (Single press actions)
                    if event.key == pygame.K_SLASH: p2_input['action_interact'] = True
                    if event.key == pygame.K_RSHIFT: p2_input['action_shoot'] = True
                    if event.key == pygame.K_RCTRL: p2_input['action_fireball'] = True

        # Handle Held Keys (Movement) only if game is not over
        if not the_game_state.game_over:
            keys = pygame.key.get_pressed() # Get state of all keys currently held down
            # Player 1 Movement Keys
            p1_input['keys']['w'] = keys[pygame.K_w]
            p1_input['keys']['s'] = keys[pygame.K_s]
            p1_input['keys']['a'] = keys[pygame.K_a]
            p1_input['keys']['d'] = keys[pygame.K_d]
            # Player 2 Movement Keys
            p2_input['keys']['w'] = keys[pygame.K_UP]
            p2_input['keys']['s'] = keys[pygame.K_DOWN]
            p2_input['keys']['a'] = keys[pygame.K_LEFT]
            p2_input['keys']['d'] = keys[pygame.K_RIGHT]

        # --- Game Update ---
        try:
            # Call the main update function with the gathered inputs
            the_game_state.update(p1_input, p2_input, current_time)
        except Exception as e:
            # Catch errors during update to prevent crash
            print("\n--- ERROR DURING GAME UPDATE ---")
            print(f"{e}")
            traceback.print_exc()
            running = False # Stop the loop on update error

        # --- Drawing ---
        try:
            # Call the main draw function to render the game state
            the_game_state.draw(screen, current_time)
        except Exception as e:
             # Catch errors during drawing
             print("\n--- ERROR DURING GAME DRAWING ---")
             print(f"{e}")
             traceback.print_exc()
             running = False # Stop the loop on draw error

        # Update the display
        pygame.display.flip()

        # Limit frame rate
        clock.tick(60) # Aim for 60 FPS

    # Cleanup on exit
    print("\nExiting standalone test mode.")
    pygame.quit()
    sys.exit()