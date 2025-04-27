# entities.py
"""
Defines the core game entities: Fence and Projectile.
"""
import pygame
import math
import os # Standard library for OS-level operations like path manipulation
from constants import * # Import all constants

# --- Get the directory containing this script ---
script_dir = os.path.dirname(os.path.abspath(__file__))

# --- Attempt to import the GIF loading function ---
try:
    from drawcode import load_gif_frames
except ImportError:
    print("\n--- ERROR ---")
    print("Could not import 'load_gif_frames' from 'drawcode.py'.")
    print("Ensure 'drawcode.py' is in the same directory as 'entities.py' or accessible in the Python path.")
    print("Using fallback GIF loading function (will not load actual GIFs).")
    def load_gif_frames(path, scale_to=None):
        print(f"[Fallback] Attempting to load GIF frames from: {path}")
        if not os.path.exists(path):
             print(f"[Fallback] ERROR: GIF file not found at '{path}'")
        return []

# --- Define Fireball GIF Constants using OS-independent path ---
FIREBALL_ASSET_RELATIVE_PATH = os.path.join("sprites", "fire2.gif")
FIREBALL_GIF_PATH = os.path.join(script_dir, FIREBALL_ASSET_RELATIVE_PATH)
print(f"DEBUG: Calculated absolute path for fireball GIF: {FIREBALL_GIF_PATH}")

# --- Other Fireball Constants ---
FIREBALL_FRAME_DURATION_MS = 80
FIREBALL_SPRITE_SCALE = None # Example: (30, 30) If you want to scale it
FIREBALL_FALLBACK_COLOR = ORANGE
FIREBALL_FALLBACK_RADIUS = 10 # Radius for fallback circle and collision
# --- Ensure FIREBALL_RADIUS constant exists for consistent use ---
# (Add this line if FIREBALL_RADIUS wasn't explicitly defined in constants.py)
# Or just rely on FIREBALL_FALLBACK_RADIUS for collision size.
# Let's assume FIREBALL_FALLBACK_RADIUS is the intended collision radius for fireballs.
FIREBALL_RADIUS = FIREBALL_FALLBACK_RADIUS # Define collision radius


# --- Fence Class (Unchanged) ---
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
            if elapsed < COOLDOWN_DURATION_MS:
                remaining_s = (COOLDOWN_DURATION_MS - elapsed) / 1000.0
                if timer_font:
                    timer_text = f"{remaining_s:.1f}"
                    text_surface, text_rect = None, None
                    try:
                        if hasattr(timer_font, 'render_to'):
                            text_surface, text_rect = timer_font.render(timer_text, fgcolor=YELLOW)
                        elif timer_font:
                            text_surface = timer_font.render(timer_text, True, YELLOW)
                            if text_surface: text_rect = text_surface.get_rect()
                    except Exception: pass # Ignore font errors silently

                    if text_surface and text_rect:
                        text_rect.center = self.rect.center
                        bg_rect = text_rect.inflate(4, 2)
                        bg_surf = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
                        bg_surf.fill((0, 0, 0, 150))
                        surface.blit(bg_surf, bg_rect.topleft)
                        surface.blit(text_surface, text_rect)

    def get_state(self):
        return { "id": self.id, "is_open": self.is_open, "last_interactor": self.last_interactor,
                 "last_interaction_time": self.last_interaction_time,
                 "rect": (self.rect.x, self.rect.y, self.rect.width, self.rect.height) }

    def set_state(self, state_dict):
        self.is_open = state_dict.get("is_open", self.is_open)
        self.last_interactor = state_dict.get("last_interactor", self.last_interactor)
        self.last_interaction_time = state_dict.get("last_interaction_time", self.last_interaction_time)
        rect_data = state_dict.get("rect")
        if rect_data and len(rect_data) == 4: self.rect = pygame.Rect(*rect_data)

    def reset(self):
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
        if cls.fireball_assets_loaded: return
        print(f"Attempting to load fireball assets from: {FIREBALL_GIF_PATH}")
        if not os.path.exists(FIREBALL_GIF_PATH):
            print(f"--- ERROR --- File not found: '{FIREBALL_GIF_PATH}'")
            cls.fireball_frames = []
            cls.fireball_assets_loaded = False # Mark explicitly as not loaded
            return
        try:
            # --- Pass FIREBALL_SPRITE_SCALE to load_gif_frames ---
            cls.fireball_frames = load_gif_frames(FIREBALL_GIF_PATH, scale_to=FIREBALL_SPRITE_SCALE)
            # -----------------------------------------------------
            if cls.fireball_frames:
                print(f"Successfully loaded {len(cls.fireball_frames)} fireball frames.")
                cls.fireball_assets_loaded = True
            else:
                print(f"WARNING: Failed to load fireball frames from '{FIREBALL_GIF_PATH}'.")
                cls.fireball_assets_loaded = False
        except Exception as e:
            print(f"--- ERROR during GIF loading --- {e}")
            cls.fireball_frames = []
            cls.fireball_assets_loaded = False


    def __init__(self, x, y, vx, vy, owner_id, proj_type="normal"):
        if proj_type == "fireball" and not Projectile.fireball_assets_loaded:
             # Try loading only if not already attempted and failed, AND file exists
             if not Projectile.fireball_frames and os.path.exists(FIREBALL_GIF_PATH):
                 Projectile.load_fireball_assets()

        self.id = Projectile.next_id
        Projectile.next_id += 1
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = float(vx), float(vy)
        self.owner_id = owner_id
        self.type = proj_type
        self.active = True

        self.current_frame_index = 0
        self.last_frame_update_time = pygame.time.get_ticks()
        self.image = None # Current visual representation (Surface)
        self.radius = 0 # <-- Initialize radius attribute

        # --- Type-specific properties ---
        if self.type == "fireball":
            self.speed = FIREBALL_SPEED # Use constant
            # Use GIF frames if loaded successfully
            if Projectile.fireball_assets_loaded and Projectile.fireball_frames:
                self.image = Projectile.fireball_frames[self.current_frame_index]
                self.rect = self.image.get_rect(center=(int(self.x), int(self.y)))
                # --- FIX 1: Set radius based on the loaded/scaled image rect ---
                # Use width/2 assuming roughly circular/square frames after scaling
                self.radius = self.rect.width // 2
            else:
                # Fallback if GIF loading failed or assets aren't loaded
                # --- FIX 2: Explicitly set radius for fallback ---
                self.radius = FIREBALL_FALLBACK_RADIUS # Use the fallback radius constant
                self.rect = pygame.Rect(0, 0, self.radius * 2, self.radius * 2)
                self.rect.center = (int(self.x), int(self.y))
                self.image = None # Ensure image is None for fallback

        else: # Normal projectile
            self.radius = PROJECTILE_RADIUS # Use constant
            self.speed = PROJECTILE_SPEED  # Use constant
            self.color = YELLOW            # Use constant
            self.rect = pygame.Rect(int(self.x) - self.radius, int(self.y) - self.radius, self.radius * 2, self.radius * 2)
            self.image = None # Ensure image is None for normal

        # --- Final check: ensure radius is somewhat sensible ---
        if self.radius <= 0:
            print(f"Warning: Projectile {self.id} ({self.type}) initialized with zero/negative radius. Setting to fallback.")
            # Use fallback radius if calculation failed (e.g., 0-width image)
            self.radius = FIREBALL_FALLBACK_RADIUS if self.type == "fireball" else PROJECTILE_RADIUS
            # Update rect if radius was invalid
            self.rect = pygame.Rect(int(self.x) - self.radius, int(self.y) - self.radius, self.radius * 2, self.radius * 2)


    def update(self):
        if not self.active: return

        self.x += self.vx
        self.y += self.vy

        # Update rect position (radius remains constant after init)
        self.rect.center = (int(self.x), int(self.y))

        # --- Update animation for fireball ---
        if self.type == "fireball" and Projectile.fireball_assets_loaded and Projectile.fireball_frames:
            now = pygame.time.get_ticks()
            time_since_last_frame = now - self.last_frame_update_time
            if time_since_last_frame > FIREBALL_FRAME_DURATION_MS:
                self.current_frame_index = (self.current_frame_index + 1) % len(Projectile.fireball_frames)
                self.image = Projectile.fireball_frames[self.current_frame_index]
                # --- Update rect based on potentially new frame size ---
                # This keeps the visual representation accurate, but collision uses fixed self.radius
                current_center = self.rect.center # Store center
                self.rect = self.image.get_rect(center=current_center) # Recalculate rect, keep center
                self.last_frame_update_time = now
        # else: no animation for normal or fallback fireball

        # --- Deactivate if off-screen ---
        if (self.rect.right < 0 or self.rect.left > WIDTH or
            self.rect.bottom < 0 or self.rect.top > HEIGHT):
            self.active = False


    def draw(self, surface):
        if not self.active: return

        if self.type == "fireball":
            # Draw animation if loaded and image is valid
            if self.image: # Check if self.image is not None
                surface.blit(self.image, self.rect.topleft)
            else:
                # Fallback drawing if GIF failed or image is None
                pygame.draw.circle(surface, FIREBALL_FALLBACK_COLOR, self.rect.center, self.radius) # Use self.radius
        else:
            # Draw Normal Projectile
            pygame.draw.circle(surface, self.color, self.rect.center, self.radius) # Use self.radius


    def get_state(self):
        # Include radius in state for consistency, though it might be recalculated on set_state
        return { "id": self.id, "x": self.x, "y": self.y, "vx": self.vx, "vy": self.vy,
                 "owner_id": self.owner_id, "active": self.active, "type": self.type,
                 "radius": self.radius } # <-- Send radius


    def set_state(self, state_dict):
        # --- Basic update ---
        new_type = state_dict.get("type", self.type)
        type_changed = (new_type != self.type)
        self.type = new_type

        self.x = float(state_dict.get("x", self.x))
        self.y = float(state_dict.get("y", self.y))
        self.vx = float(state_dict.get("vx", self.vx))
        self.vy = float(state_dict.get("vy", self.vy))
        self.active = state_dict.get("active", self.active)
        self.owner_id = state_dict.get("owner_id", self.owner_id)
        self.id = state_dict.get("id", self.id)
        # Try to get radius from state, default to current if missing
        received_radius = state_dict.get("radius")

        # --- Re-initialize properties based on type if needed ---
        # Use presence of 'speed' or 'color' as indicator if full init happened before.
        # Add check for received_radius being None/zero as well? Let's re-init more often for safety.
        needs_reinit = type_changed or not hasattr(self, 'speed') or not hasattr(self, 'color') or not hasattr(self, 'rect') or self.radius <= 0

        if needs_reinit:
             # print(f"DEBUG: Re-initializing projectile {self.id} state (type: {self.type})") # Optional debug
             if self.type == "fireball":
                 self.speed = FIREBALL_SPEED
                 # Attempt to load assets IF they weren't loaded before AND type changed to fireball
                 if not Projectile.fireball_assets_loaded and os.path.exists(FIREBALL_GIF_PATH):
                      Projectile.load_fireball_assets()

                 if Projectile.fireball_assets_loaded and Projectile.fireball_frames:
                      # Reset animation state
                      self.current_frame_index = 0
                      self.last_frame_update_time = pygame.time.get_ticks() # Reset timer too
                      self.image = Projectile.fireball_frames[self.current_frame_index]
                      self.rect = self.image.get_rect(center=(int(self.x), int(self.y)))
                      # --- FIX 3: Set radius based on rect (set_state) ---
                      self.radius = self.rect.width // 2
                 else: # Use fallback setup
                      self.image = None
                      # --- FIX 4: Set radius for fallback (set_state) ---
                      self.radius = FIREBALL_FALLBACK_RADIUS
                      self.rect = pygame.Rect(0, 0, self.radius * 2, self.radius * 2)
                      self.rect.center = (int(self.x), int(self.y))

             else: # Normal projectile
                 self.speed = PROJECTILE_SPEED
                 self.radius = PROJECTILE_RADIUS
                 self.color = YELLOW
                 self.image = None
                 self.rect = pygame.Rect(int(self.x) - self.radius, int(self.y) - self.radius, self.radius * 2, self.radius * 2)

             # --- Final radius validation after re-init ---
             if self.radius <= 0:
                 print(f"Warning: Projectile {self.id} ({self.type}) re-initialized with invalid radius. Setting fallback.")
                 self.radius = FIREBALL_FALLBACK_RADIUS if self.type == "fireball" else PROJECTILE_RADIUS
                 self.rect = pygame.Rect(int(self.x) - self.radius, int(self.y) - self.radius, self.radius * 2, self.radius * 2)

        else:
             # If type didn't change and basic attrs exist, just update position-dependent things
             # Update radius *only if* a valid one was received, otherwise keep existing
             if received_radius is not None and received_radius > 0:
                  self.radius = float(received_radius)
             # Update rect position (and size based on image if fireball anim)
             self.rect.center = (int(self.x), int(self.y))
             if self.type == "fireball" and self.image:
                  # Keep collision radius fixed, but update visual rect
                  current_center = self.rect.center
                  self.rect = self.image.get_rect(center=current_center)