"""
Stores all constant values used throughout the game.
"""
import pygame # Often useful for pygame.Color, but not strictly needed here
import os # <-- ADDED for path joining

# --- Screen & Colors ---
WIDTH, HEIGHT = 800, 600
BLACK = (0, 0, 0)
WHITE = (255, 255, 255) # P1 Color
RED = (255, 0, 0)       # P2 Color
GREEN = (0, 255, 0)     # Health color
GREY = (100, 100, 100)  # Closed fence color / Cooldown BG OLD
DARK_GREY = (60, 60, 60)  # Open fence color / Cooldown BG NEW
YELLOW = (255, 255, 0)  # Projectile color / Timer color / Cooldown Ready OLD
ORANGE = (255, 165, 0)  # Win message color / Fireball color
CYAN = (0, 255, 255)    # Scoreboard color / Cooldown FG OLD
PURPLE = (128, 0, 128)  # Fireball alternate color

# --- Player ---
PLAYER_RADIUS = 15
PLAYER_COLLISION_WIDTH = PLAYER_RADIUS * 2 # Used for map generation checks
PLAYER_SPEED = 4
MAX_HP = 10 # Reset HP to this value
HP_BAR_WIDTH = 40
HP_BAR_HEIGHT = 8
HP_BAR_OFFSET_Y = 25 # Offset above player center for health bar
INTERACTION_DISTANCE = 35 # Max distance to interact with fence

# --- Projectiles ---
PROJECTILE_RADIUS = 3
PROJECTILE_SPEED = 8
SHOOT_COOLDOWN_MS = 300

# --- Fireball (Special Projectile) ---
FIREBALL_RADIUS = PLAYER_RADIUS # Same size as player projectile for collision check (visuals are GIF)
FIREBALL_SPEED = PROJECTILE_SPEED * 0.75 # Slightly faster than normal (adjust as needed) - adjusted from 0.5
FIREBALL_COOLDOWN_MS = 5000
FIREBALL_DAMAGE_FACTOR = 1.0 / 3.0 # Deals 1/3 of current HP as damage (rounded up)
# FIREBALL_ANIMATION_SPEED = 0.15 # Radians per update for pulse effect - REMOVED, using GIF timing
# FIREBALL_PULSE_AMOUNT = 4 # Max pixels added/subtracted to radius during pulse - REMOVED

# --- Fireball Projectile GIF Asset ---
# (Path setup moved to entities.py where it's primarily used)

# --- Fences ---
COOLDOWN_DURATION_MS = 5000 # Fence interaction cooldown

# --- UI & Fonts ---
TIMER_FONT_SIZE = 18
SCORE_FONT_SIZE = 48
WIN_FONT_SIZE = 90
PROMPT_FONT_SIZE = 36
EXIT_FONT_SIZE = 30

# List of font names for fallback (used by drawing.py)
DEFAULT_FONT_NAMES = ['arial', 'calibri', 'sans']
MONO_FONT_NAMES = ['consolas', 'courier new', 'monospace']
IMPACT_FONT_NAMES = ['impact', 'arial black', 'sans']

# --- Cooldown Indicator (Fireball UI) ---
P1_COOLDOWN_OFFSET_X = -200 # Relative to screen center X
P2_COOLDOWN_OFFSET_X = 200  # Relative to screen center X
COOLDOWN_INDICATOR_Y = 25   # Y position from top
# COOLDOWN_INDICATOR_RADIUS = 15 # REMOVED - determined by GIF size
# COOLDOWN_INDICATOR_WIDTH = 4 # REMOVED - determined by GIF

# --- NEW: Cooldown Indicator GIF Settings ---
# Assume using the same GIF as the projectile, but scaled for UI
# Path setup will be in GameState or drawcode where UI assets are loaded
script_dir = os.path.dirname(os.path.abspath(__file__)) # Get directory of constants.py
# IMPORTANT: Adjust this path if your 'sprites' folder is elsewhere relative to constants.py
FIREBALL_UI_GIF_RELATIVE_PATH = os.path.join("sprites", "fire2.gif")
FIREBALL_UI_GIF_PATH = os.path.join(script_dir, FIREBALL_UI_GIF_RELATIVE_PATH)
FIREBALL_UI_SPRITE_SCALE = (35, 35) # Target width/height for the UI GIF (adjust as needed)
FIREBALL_UI_FRAME_DURATION_MS = 80 # Animation speed for UI GIF (match projectile or set differently)
FIREBALL_UI_FALLBACK_COLOR = ORANGE # Color if GIF fails to load
FIREBALL_UI_FALLBACK_RADIUS = 15 # Radius if GIF fails

# Print the calculated path for debugging the UI GIF path
print(f"DEBUG [constants.py]: Calculated absolute path for UI fireball GIF: {FIREBALL_UI_GIF_PATH}")