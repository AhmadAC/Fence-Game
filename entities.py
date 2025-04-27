# entities.py
"""
Defines the core game entities: Fence and Projectile.
Includes adjustments for finding assets in bundled executables.
"""
import pygame
import math
import os # Standard library for OS-level operations like path manipulation

# Import all constants AND the resource_path helper function
from constants import *
try:
    from constants import resource_path
except ImportError:
    print("\n--- ERROR ---")
    print("Could not import 'resource_path' from 'constants.py'.")
    print("Ensure 'constants.py' is in the same directory and defines the function.")
    print("Using fallback path logic (may fail in bundles).")
    # Define a basic fallback if constants.py is broken or missing
    def resource_path(relative_path):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

# --- Attempt to import the GIF loading function ---
try:
    # Assuming drawcode.py is in the same directory or path
    from drawcode import load_gif_frames
except ImportError:
    print("\n--- ERROR ---")
    print("Could not import 'load_gif_frames' from 'drawcode.py'.")
    print("Ensure 'drawcode.py' is present.")
    print("Using fallback GIF loading function (will not load actual GIFs).")
    # Fallback function if drawcode is missing
    def load_gif_frames(path, scale_to=None):
        print(f"[Fallback] Attempting to load GIF frames from: {path}")
        if not os.path.exists(path):
            print(f"[Fallback] ERROR: GIF file not found at '{path}'")
        return [] # Return an empty list as load_gif_frames expects

# --- Define Fireball GIF Constants using resource_path ---
# Keep the relative path definition
FIREBALL_ASSET_RELATIVE_PATH = os.path.join("sprites", "fire2.gif")
# Use the imported resource_path function to get the correct absolute path
FIREBALL_GIF_PATH = resource_path(FIREBALL_ASSET_RELATIVE_PATH)
# Optional: Keep debug print for verification during development
# print(f"DEBUG [entities.py]: Calculated absolute path for projectile fireball GIF: {FIREBALL_GIF_PATH}")

# --- Other Fireball Constants (mostly imported from constants.py now) ---
# FIREBALL_FRAME_DURATION_MS = 80 # Now imported
# FIREBALL_SPRITE_SCALE = None # Example: (30, 30) If you want to scale it # Now imported? Check constants.py
# FIREBALL_FALLBACK_COLOR = ORANGE # Now imported
# FIREBALL_FALLBACK_RADIUS = 10 # Now imported
# FIREBALL_RADIUS = FIREBALL_FALLBACK_RADIUS # Now imported

# --- Fence Class (Remains Unchanged) ---
class Fence:
    def __init__(self, x, y, width, height, id):
        self.rect = pygame.Rect(int(x), int(y), int(width), int(height))
        self.id = id
        self.is_open = False
        self.closed_color = GREY
        self.open_color = DARK_GREY
        self.last_interactor = None
        self.last_interaction_time = 0

    def can_interact(self, player_id, current_time_ticks):
        if self.last_interactor is None: return True
        # Use COOLDOWN_DURATION_MS from constants
        if current_time_ticks - self.last_interaction_time < COOLDOWN_DURATION_MS:
            return self.last_interactor == player_id
        return True

    def toggle(self, player_id, current_time_ticks):
        if self.can_interact(player_id, current_time_ticks):
            self.is_open = not self.is_open
            self.last_interactor = player_id
            self.last_interaction_time = current_time_ticks
            return True
        return False

    def draw(self, surface, current_time_ticks, timer_font):
        color = self.open_color if self.is_open else self.closed_color
        pygame.draw.rect(surface, color, self.rect)
        if self.last_interactor is not None:
            elapsed = current_time_ticks - self.last_interaction_time
            # Use COOLDOWN_DURATION_MS from constants
            if elapsed < COOLDOWN_DURATION_MS:
                remaining_s = (COOLDOWN_DURATION_MS - elapsed) / 1000.0
                if timer_font:
                    timer_text = f"{remaining_s:.1f}"
                    text_surface, text_rect = None, None
                    try:
                        # Check if font object supports render_to (freetype) or render (font)
                        if hasattr(timer_font, 'render_to'):
                            # freetype.render returns tuple: (Surface, Rect)
                            text_surface, text_rect = timer_font.render(timer_text, fgcolor=YELLOW)
                        elif timer_font: # Assume standard pygame.font
                            text_surface = timer_font.render(timer_text, True, YELLOW)
                            if text_surface: text_rect = text_surface.get_rect()
                    except Exception: pass # Ignore font errors silently

                    if text_surface and text_rect:
                        text_rect.center = self.rect.center
                        bg_rect = text_rect.inflate(4, 2) # Small padding
                        # Use SRCALPHA for transparency
                        bg_surf = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
                        bg_surf.fill((0, 0, 0, 150)) # Semi-transparent black background
                        surface.blit(bg_surf, bg_rect.topleft)
                        surface.blit(text_surface, text_rect)

    def get_state(self):
        # Returns state needed for network sync
        return { "id": self.id,
                 "is_open": self.is_open,
                 "last_interactor": self.last_interactor,
                 "last_interaction_time": self.last_interaction_time,
                 # Send rect data too, in case map generation varies slightly (though unlikely now)
                 "rect": (self.rect.x, self.rect.y, self.rect.width, self.rect.height) }

    def set_state(self, state_dict):
        # Updates local state based on received network data
        self.is_open = state_dict.get("is_open", self.is_open)
        self.last_interactor = state_dict.get("last_interactor", self.last_interactor)
        self.last_interaction_time = state_dict.get("last_interaction_time", self.last_interaction_time)
        # Update rect based on received state if present
        rect_data = state_dict.get("rect")
        if rect_data and isinstance(rect_data, (list, tuple)) and len(rect_data) == 4:
            try:
                self.rect = pygame.Rect(int(rect_data[0]), int(rect_data[1]), int(rect_data[2]), int(rect_data[3]))
            except (ValueError, TypeError):
                print(f"Warning: Invalid rect data received for fence {self.id}: {rect_data}")

    def reset(self):
        # Resets fence to its initial state (closed, no interaction history)
        self.is_open = False
        self.last_interactor = None
        self.last_interaction_time = 0

# --- Projectile Class ---
class Projectile:
    next_id = 0
    fireball_frames = []
    fireball_assets_loaded = False

    @classmethod
    def load_fireball_assets(cls):
        """Loads the animated GIF frames for fireballs using the resolved path."""
        if cls.fireball_assets_loaded:
            return # Don't reload if already loaded

        # FIREBALL_GIF_PATH is now correctly resolved using resource_path
        print(f"Attempting to load fireball assets from: {FIREBALL_GIF_PATH}")
        if not os.path.exists(FIREBALL_GIF_PATH):
            print(f"--- ERROR --- File not found: '{FIREBALL_GIF_PATH}'")
            cls.fireball_frames = []
            cls.fireball_assets_loaded = False # Mark explicitly as not loaded
            return

        try:
            # Check if load_gif_frames exists (in case of import error)
            if 'load_gif_frames' in globals():
                 # FIREBALL_SPRITE_SCALE constant controls scaling, passed from constants.py
                 loaded_data = load_gif_frames(FIREBALL_GIF_PATH, scale_to=None) # Pass scale_to=None if not defined or desired

                 # Handle return format flexibility (expecting list or tuple(list, ...))
                 if isinstance(loaded_data, tuple) and len(loaded_data) > 0 and isinstance(loaded_data[0], list):
                     cls.fireball_frames = loaded_data[0]
                 elif isinstance(loaded_data, list):
                     cls.fireball_frames = loaded_data
                 else:
                     cls.fireball_frames = [] # Ensure it's a list

                 if cls.fireball_frames:
                     print(f"Successfully loaded {len(cls.fireball_frames)} fireball frames.")
                     cls.fireball_assets_loaded = True
                 else:
                     print(f"WARNING: Failed to load fireball frames from '{FIREBALL_GIF_PATH}'. load_gif_frames returned empty.")
                     cls.fireball_assets_loaded = False
            else:
                 print("ERROR: load_gif_frames function is not available. Cannot load fireball assets.")
                 cls.fireball_frames = []
                 cls.fireball_assets_loaded = False

        except Exception as e:
            print(f"--- ERROR during GIF loading ---")
            print(f"Path: {FIREBALL_GIF_PATH}")
            print(f"Error: {e}")
            import traceback
            traceback.print_exc() # Print full traceback for debugging
            cls.fireball_frames = []
            cls.fireball_assets_loaded = False


    def __init__(self, x, y, vx, vy, owner_id, proj_type="normal"):
        """Initializes a projectile (normal or fireball)."""

        # Attempt to load fireball assets ONCE if needed and not already loaded/failed
        if proj_type == "fireball" and not Projectile.fireball_assets_loaded:
            # Only try loading if the list is currently empty (avoids reloading after failure)
            if not Projectile.fireball_frames:
                Projectile.load_fireball_assets()

        self.id = Projectile.next_id
        Projectile.next_id += 1
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = float(vx), float(vy)
        self.owner_id = owner_id
        self.type = proj_type
        self.active = True # Projectiles start active

        # Animation state (used mainly for fireball)
        self.current_frame_index = 0
        self.last_frame_update_time = pygame.time.get_ticks() # Initialize timer
        self.image = None # Current visual representation (pygame.Surface)
        self.radius = 0   # Collision radius
        self.rect = None  # Pygame Rect for position and drawing/collision checks

        # --- Type-specific properties ---
        if self.type == "fireball":
            self.speed = FIREBALL_SPEED # Speed from constants
            # Use GIF frames if loaded successfully
            if Projectile.fireball_assets_loaded and Projectile.fireball_frames:
                try:
                    self.image = Projectile.fireball_frames[self.current_frame_index]
                    self.rect = self.image.get_rect(center=(int(self.x), int(self.y)))
                    # Set collision radius based on the loaded/scaled image rect's width
                    self.radius = self.rect.width // 2
                except IndexError:
                     print(f"Error: Fireball frame index {self.current_frame_index} out of bounds. Frames: {len(Projectile.fireball_frames)}")
                     self.image = None # Force fallback if frame index is bad
            else:
                self.image = None # Explicitly set image to None for fallback

            # If image loading failed or frames are empty, use fallback settings
            if self.image is None:
                self.radius = FIREBALL_FALLBACK_RADIUS # Use fallback radius from constants
                # Create a rect based on fallback radius
                self.rect = pygame.Rect(0, 0, self.radius * 2, self.radius * 2)
                self.rect.center = (int(self.x), int(self.y))
                # print(f"DEBUG: Fireball {self.id} using fallback radius {self.radius}") # Optional debug

        else: # Normal projectile ("normal" type)
            self.radius = PROJECTILE_RADIUS # Radius from constants
            self.speed = PROJECTILE_SPEED  # Speed from constants
            self.color = YELLOW            # Color from constants
            # Create rect based on normal projectile radius
            self.rect = pygame.Rect(int(self.x) - self.radius, int(self.y) - self.radius, self.radius * 2, self.radius * 2)
            self.image = None # Normal projectiles don't use sprite images

        # --- Final check: ensure radius and rect are valid ---
        if self.radius <= 0:
            print(f"Warning: Projectile {self.id} ({self.type}) initialized with zero/negative radius. Setting to fallback values.")
            # Use appropriate fallback radius based on type
            self.radius = FIREBALL_FALLBACK_RADIUS if self.type == "fireball" else PROJECTILE_RADIUS
            # Re-create rect with the fallback radius
            self.rect = pygame.Rect(int(self.x) - self.radius, int(self.y) - self.radius, self.radius * 2, self.radius * 2)
        elif self.rect is None: # If rect somehow wasn't created
             print(f"Warning: Projectile {self.id} ({self.type}) initialized without a rect. Creating one.")
             self.rect = pygame.Rect(int(self.x) - self.radius, int(self.y) - self.radius, self.radius * 2, self.radius * 2)


    def update(self):
        """Updates projectile position, animation, and checks for off-screen."""
        if not self.active:
            return # Don't update inactive projectiles

        # Update position based on velocity
        self.x += self.vx
        self.y += self.vy

        # Update rect position (important for drawing and collision)
        # Ensure rect exists before trying to update its center
        if self.rect:
            self.rect.center = (int(self.x), int(self.y))
        else:
             # This shouldn't happen if constructor logic is correct, but handle defensively
             print(f"Warning: Projectile {self.id} has no rect during update. Recreating.")
             self.rect = pygame.Rect(int(self.x) - self.radius, int(self.y) - self.radius, self.radius * 2, self.radius * 2)


        # --- Update animation for fireball (if assets are loaded) ---
        if self.type == "fireball" and Projectile.fireball_assets_loaded and Projectile.fireball_frames:
            now = pygame.time.get_ticks()
            # Use FIREBALL_FRAME_DURATION_MS from constants
            time_since_last_frame = now - self.last_frame_update_time
            if time_since_last_frame > FIREBALL_FRAME_DURATION_MS:
                num_frames = len(Projectile.fireball_frames)
                if num_frames > 0: # Avoid modulo by zero
                    self.current_frame_index = (self.current_frame_index + 1) % num_frames
                    try:
                        self.image = Projectile.fireball_frames[self.current_frame_index]
                        # Update the drawing rect based on the current frame's size, keeping center
                        if self.image and self.rect: # Ensure image and rect exist
                            current_center = self.rect.center # Store current center
                            self.rect = self.image.get_rect(center=current_center) # Recalculate rect
                    except IndexError:
                         print(f"Error: Fireball frame index {self.current_frame_index} out of bounds during update. Frames: {num_frames}")
                         # Optionally reset index or handle error
                         self.current_frame_index = 0
                         if num_frames > 0: self.image = Projectile.fireball_frames[0]

                self.last_frame_update_time = now
        # else: no animation needed for normal projectiles or fallback fireballs

        # --- Deactivate if off-screen ---
        # Check using the projectile's rect and screen dimensions from constants
        if self.rect and (self.rect.right < 0 or self.rect.left > WIDTH or
            self.rect.bottom < 0 or self.rect.top > HEIGHT):
            self.active = False
            # print(f"DEBUG: Projectile {self.id} deactivated (off-screen).") # Optional debug


    def draw(self, surface):
        """Draws the projectile on the given surface."""
        if not self.active:
            return # Don't draw inactive projectiles

        if self.type == "fireball":
            # Draw animated GIF frame if available and valid
            if self.image and self.rect: # Check image and rect exist
                surface.blit(self.image, self.rect.topleft)
            else:
                # Fallback drawing: draw a circle using fallback color and radius
                # Ensure rect exists for center position
                center_pos = (int(self.x), int(self.y)) if not self.rect else self.rect.center
                # Use FIREBALL_FALLBACK_COLOR and self.radius (which might be FIREBALL_FALLBACK_RADIUS)
                pygame.draw.circle(surface, FIREBALL_FALLBACK_COLOR, center_pos, self.radius)
        else:
            # Draw Normal Projectile: draw a circle using its color and radius
            # Ensure rect exists for center position
            center_pos = (int(self.x), int(self.y)) if not self.rect else self.rect.center
            pygame.draw.circle(surface, self.color, center_pos, self.radius)


    def get_state(self):
        """Returns a dictionary representing the projectile's state for network sync."""
        # Include all necessary attributes for reconstruction on the client
        return { "id": self.id,
                 "x": self.x, "y": self.y,
                 "vx": self.vx, "vy": self.vy,
                 "owner_id": self.owner_id,
                 "active": self.active,
                 "type": self.type,
                 "radius": self.radius } # Include radius for accurate state


    def set_state(self, state_dict):
        """Updates the projectile's state based on received network data."""
        # --- Basic attribute updates ---
        # Update type first, as it affects radius/visuals
        new_type = state_dict.get("type", self.type)
        type_changed = (new_type != self.type)
        self.type = new_type

        self.x = float(state_dict.get("x", self.x))
        self.y = float(state_dict.get("y", self.y))
        self.vx = float(state_dict.get("vx", self.vx))
        self.vy = float(state_dict.get("vy", self.vy))
        self.active = state_dict.get("active", self.active) # Crucial: update active status
        self.owner_id = state_dict.get("owner_id", self.owner_id)
        # ID shouldn't change, but include for safety/completeness? Usually set on creation.
        # self.id = state_dict.get("id", self.id)

        # Get radius from state, using current as fallback. Handle potential None.
        received_radius = state_dict.get("radius")
        current_radius = self.radius # Store current radius before potential changes

        # --- Re-initialize properties if type changed or essential attributes missing ---
        # Check if critical attributes like speed, radius, or rect are missing or invalid
        needs_reinit = (
             type_changed or
             not hasattr(self, 'speed') or
             not hasattr(self, 'radius') or self.radius <= 0 or
             not hasattr(self, 'rect') or self.rect is None
            )

        if needs_reinit:
            # print(f"DEBUG: Re-initializing projectile {self.id} state (type: {self.type}) due to state update.") # Optional debug
            # Re-run the relevant part of the __init__ logic based on the *new* type
            if self.type == "fireball":
                self.speed = FIREBALL_SPEED
                # Ensure assets are loaded if type changed to fireball
                if type_changed and not Projectile.fireball_assets_loaded:
                     if not Projectile.fireball_frames: Projectile.load_fireball_assets()

                if Projectile.fireball_assets_loaded and Projectile.fireball_frames:
                    # Reset animation state for consistency
                    self.current_frame_index = 0
                    self.last_frame_update_time = pygame.time.get_ticks() # Reset timer
                    try:
                        self.image = Projectile.fireball_frames[self.current_frame_index]
                        self.rect = self.image.get_rect(center=(int(self.x), int(self.y)))
                        # Set radius based on (potentially scaled) image rect
                        self.radius = self.rect.width // 2
                    except IndexError:
                         print(f"Error: Fireball frame index {self.current_frame_index} out of bounds during set_state re-init.")
                         self.image = None # Force fallback
                else:
                    self.image = None # Explicitly None for fallback

                # If image failed (or assets not loaded), use fallback radius/rect
                if self.image is None:
                    self.radius = FIREBALL_FALLBACK_RADIUS
                    self.rect = pygame.Rect(0, 0, self.radius * 2, self.radius * 2)
                    self.rect.center = (int(self.x), int(self.y))

            else: # Normal projectile re-initialization
                self.speed = PROJECTILE_SPEED
                self.radius = PROJECTILE_RADIUS
                self.color = YELLOW
                self.image = None # No image for normal projectile
                self.rect = pygame.Rect(int(self.x) - self.radius, int(self.y) - self.radius, self.radius * 2, self.radius * 2)

            # --- Final radius validation after re-init ---
            if self.radius <= 0:
                print(f"Warning: Projectile {self.id} ({self.type}) re-initialized with invalid radius during set_state. Setting fallback.")
                self.radius = FIREBALL_FALLBACK_RADIUS if self.type == "fireball" else PROJECTILE_RADIUS
                # Re-create rect with the fallback radius
                self.rect = pygame.Rect(int(self.x) - self.radius, int(self.y) - self.radius, self.radius * 2, self.radius * 2)
            elif self.rect is None: # Ensure rect exists
                 print(f"Warning: Projectile {self.id} ({self.type}) rect missing after re-init. Creating.")
                 self.rect = pygame.Rect(int(self.x) - self.radius, int(self.y) - self.radius, self.radius * 2, self.radius * 2)

        else:
            # --- Minimal update if type didn't change and core attrs exist ---
            # Update radius *only if* a valid one was received
            if received_radius is not None and float(received_radius) > 0:
                new_radius = float(received_radius)
                # Only update rect size if radius actually changes significantly (optional optimization)
                # if abs(new_radius - current_radius) > 0.1:
                self.radius = new_radius
                # Update rect size based on the new radius (important for non-sprite projectiles)
                if not self.image: # Only adjust rect size for circle-based projectiles
                    self.rect = pygame.Rect(int(self.x) - self.radius, int(self.y) - self.radius, self.radius * 2, self.radius * 2)

            # Always update rect position
            if self.rect: # Ensure rect exists
                 self.rect.center = (int(self.x), int(self.y))
                 # If it's a fireball with an image, ensure the visual rect matches the image size
                 # but keep the collision radius fixed based on self.radius
                 if self.type == "fireball" and self.image:
                      current_center = self.rect.center
                      self.rect = self.image.get_rect(center=current_center)
            else: # Rect was missing, create it
                 print(f"Warning: Projectile {self.id} rect missing during minimal set_state update. Creating.")
                 self.rect = pygame.Rect(int(self.x) - self.radius, int(self.y) - self.radius, self.radius * 2, self.radius * 2)
