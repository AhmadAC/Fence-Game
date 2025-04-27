"""
Stores all constant values used throughout the game.
Includes a helper function to find resources in both development and bundled states.
"""
import pygame # Often useful for pygame.Color, but not strictly needed here
import os
import sys # <-- ADDED for resource_path helper

# --- Helper Function for PyInstaller Compatibility ---
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        # Using getattr avoids AttributeError if not running in bundle
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    except Exception:
        # Fallback to the directory of this script (constants.py)
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)
# ----------------------------------------------------

# --- Screen & Colors ---
WIDTH, HEIGHT = 800, 600
BLACK = (0, 0, 0)
WHITE = (255, 255, 255) # P1 Color
RED = (255, 0, 0)       # P2 Color
GREEN = (0, 255, 0)     # Health color
GREY = (100, 100, 100)  # Closed fence color
DARK_GREY = (60, 60, 60)  # Open fence color / Cooldown BG
YELLOW = (255, 255, 0)  # Projectile color / Timer color
ORANGE = (255, 165, 0)  # Win message color / Fireball color / UI Fallback
CYAN = (0, 255, 255)    # Scoreboard color / Cooldown FG
PURPLE = (128, 0, 128)  # Fireball alternate color (unused currently)

# --- Player ---
PLAYER_RADIUS = 15
PLAYER_COLLISION_WIDTH = PLAYER_RADIUS * 2 # Used for map generation checks
PLAYER_SPEED = 4
MAX_HP = 10 # Reset HP to this value
HP_BAR_WIDTH = 40
HP_BAR_HEIGHT = 8
HP_BAR_OFFSET_Y = 25 # Offset above player center for health bar
INTERACTION_DISTANCE = 35 # Max distance to interact with fence

# --- Player-Wall Proximity (used in collision.py) ---
PLAYER_WALL_PROXIMITY_THRESHOLD = 5 # pixels

# --- Projectiles ---
PROJECTILE_RADIUS = 3
PROJECTILE_SPEED = 8
SHOOT_COOLDOWN_MS = 300
NORMAL_PROJECTILE_DAMAGE = 1

# --- Fireball (Special Projectile) ---
FIREBALL_RADIUS = PLAYER_RADIUS # Collision radius
FIREBALL_SPEED = PROJECTILE_SPEED * 0.75
FIREBALL_COOLDOWN_MS = 5000
FIREBALL_DAMAGE_FACTOR = 1.0 / 3.0
FIREBALL_FALLBACK_RADIUS = 10 # Used if GIF load fails
FIREBALL_FALLBACK_COLOR = ORANGE
# --- ADDED FOR PROJECTILE ANIMATION ---
FIREBALL_FRAME_DURATION_MS = 80 # How long each frame of the *projectile* GIF lasts (in ms)
# ---------------------------------------
FIREBALL_SPRITE_SCALE = None # Optional scaling for the *projectile* GIF (e.g., (30, 30))

# --- Fences ---
COOLDOWN_DURATION_MS = 5000 # Fence interaction cooldown

# --- UI & Fonts ---
TIMER_FONT_SIZE = 18
SCORE_FONT_SIZE = 48
WIN_FONT_SIZE = 90
PROMPT_FONT_SIZE = 36
EXIT_FONT_SIZE = 30

DEFAULT_FONT_NAMES = ['arial', 'calibri', 'sans']
MONO_FONT_NAMES = ['consolas', 'courier new', 'monospace']
IMPACT_FONT_NAMES = ['impact', 'arial black', 'sans']

# --- Cooldown Indicator (Fireball UI) ---
P1_COOLDOWN_OFFSET_X = -200
P2_COOLDOWN_OFFSET_X = 200
COOLDOWN_INDICATOR_Y = 25

# --- Cooldown Indicator GIF Settings ---
FIREBALL_UI_GIF_RELATIVE_PATH = os.path.join("sprites", "fire2.gif")
FIREBALL_UI_GIF_PATH = resource_path(FIREBALL_UI_GIF_RELATIVE_PATH)
FIREBALL_UI_SPRITE_SCALE = (35, 35)
FIREBALL_UI_FRAME_DURATION_MS = 80 # How long each frame of the *UI* GIF lasts
FIREBALL_UI_FALLBACK_COLOR = ORANGE
FIREBALL_UI_FALLBACK_RADIUS = 15
