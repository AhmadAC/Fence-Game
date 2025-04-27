"""
Contains helper functions for drawing UI elements like health bars, cooldowns,
text rendering, font initialization, and loading assets like animated GIFs.
"""
import pygame
import math
import sys
import os
try:
    import imageio
    import numpy as np
except ImportError:
    # (Error message remains the same)
    print("\n--- WARNING ---")
    print("Modules 'imageio' or 'numpy' not found.")
    print("Please install them: pip install imageio numpy")
    print("GIF loading functionality will be unavailable.")
    print("-------------\n")
    imageio = None
    np = None

# Import constants explicitly
from constants import (
    WIDTH, HEIGHT, MAX_HP, HP_BAR_WIDTH, HP_BAR_HEIGHT, HP_BAR_OFFSET_Y,
    FIREBALL_COOLDOWN_MS, P1_COOLDOWN_OFFSET_X, P2_COOLDOWN_OFFSET_X,
    COOLDOWN_INDICATOR_Y,
    RED, GREEN, DARK_GREY, YELLOW, CYAN, ORANGE, WHITE,
    DEFAULT_FONT_NAMES, MONO_FONT_NAMES, IMPACT_FONT_NAMES,
    FIREBALL_UI_FRAME_DURATION_MS, FIREBALL_UI_SPRITE_SCALE # <-- Keep sprite scale for radius calculation
)

# --- Font Initialization ---
# (init_fonts function remains the same - unchanged)
def init_fonts(font_sizes, font_names):
    initialized_fonts = {}
    font_loader = None
    sys_font_loader = None
    use_freetype = False
    try:
        import pygame.freetype
        pygame.freetype.init()
        font_loader = pygame.freetype.Font
        sys_font_loader = pygame.freetype.SysFont
        use_freetype = True
    except ImportError:
        print("pygame.freetype not available, falling back to pygame.font.")
        try:
            if not pygame.font.get_init(): pygame.font.init()
            font_loader = pygame.font.Font
            sys_font_loader = pygame.font.SysFont
        except Exception as e:
            print(f"FATAL: Could not initialize pygame.font: {e}")
            sys.exit(1)
    def load_single_font(size, names):
        try:
            if use_freetype: return font_loader(None, size)
        except Exception as e: pass
        for name in names:
            try: return sys_font_loader(name, size)
            except Exception as e: continue
        print(f"Warning: Could not load any suitable font for size {size} using names {names}.")
        return None
    for key, size in font_sizes.items():
         name_list_key = 'default'
         if 'timer' in key or 'mono' in key: name_list_key = 'mono'
         elif 'win' in key or 'impact' in key: name_list_key = 'impact'
         font_name_list = font_names.get(name_list_key, font_names.get('default', []))
         initialized_fonts[key] = load_single_font(size, font_name_list)
         if initialized_fonts[key] is None: print(f"Failed to load font for key '{key}' with size {size}")
    return initialized_fonts

# --- Drawing Helpers ---
# (draw_health_bar function remains the same - unchanged)
def draw_health_bar(surface, x, y, current_hp, max_hp):
    if current_hp < 0: current_hp = 0
    fill_ratio = current_hp / max_hp if max_hp > 0 else 0
    bar_x = x - HP_BAR_WIDTH // 2
    bar_y = y - HP_BAR_OFFSET_Y - HP_BAR_HEIGHT // 2
    bg_rect = pygame.Rect(bar_x, bar_y, HP_BAR_WIDTH, HP_BAR_HEIGHT)
    pygame.draw.rect(surface, RED, bg_rect)
    if fill_ratio > 0:
        fg_width = int(HP_BAR_WIDTH * fill_ratio)
        fg_rect = pygame.Rect(bar_x, bar_y, fg_width, HP_BAR_HEIGHT)
        pygame.draw.rect(surface, GREEN, fg_rect)

# --- REVISED: draw_cooldown_indicator ---
def draw_cooldown_indicator(surface, player_id, player_data, current_time_ticks, ui_frames):
    """
    Draws the cooldown progress arc when recharging, and the animated GIF when ready.
    Args:
        player_id (int): ID of the player (1 or 2).
        player_data (dict | None): The dictionary containing state for the specific player.
        current_time_ticks (int): Current game time.
        ui_frames (list): List of pygame.Surface frames for the GIF animation.
    """
    # --- Basic Validation ---
    if not player_data or not isinstance(player_data, dict):
        return

    # --- Calculate Cooldown Status ---
    last_used = player_data.get("last_fireball_time", 0)
    if not isinstance(last_used, (int, float)): last_used = 0

    elapsed = current_time_ticks - last_used
    cooldown = FIREBALL_COOLDOWN_MS
    is_ready = (elapsed >= cooldown) if cooldown > 0 else True

    # --- Determine Position and Size ---
    center_x = WIDTH // 2
    offset_x = P1_COOLDOWN_OFFSET_X if player_id == 1 else P2_COOLDOWN_OFFSET_X
    indicator_center = (center_x + offset_x, COOLDOWN_INDICATOR_Y)

    # Use GIF size for radius if available, otherwise a default
    indicator_radius = 15 # Default radius
    if ui_frames and FIREBALL_UI_SPRITE_SCALE:
         # Base radius on the *target* scale defined in constants
         indicator_radius = int(FIREBALL_UI_SPRITE_SCALE[0] / 2)
    arc_width = 4 # Thickness of the cooldown arc

    # --- Draw Based on State ---
    if is_ready:
        # --- Ability is Ready: Draw Animated GIF (if loaded) ---
        if ui_frames:
            num_frames = len(ui_frames)
            current_frame_surf = None
            frame_rect = None

            # Get animation state
            anim_index = player_data.get("cooldown_anim_frame_index", 0)
            last_update = player_data.get("cooldown_anim_last_update", 0)

            # Update frame
            time_since_last_frame = current_time_ticks - last_update
            if time_since_last_frame > FIREBALL_UI_FRAME_DURATION_MS:
                anim_index = (anim_index + 1) % num_frames
                player_data["cooldown_anim_frame_index"] = anim_index
                player_data["cooldown_anim_last_update"] = current_time_ticks

            # Get the surface
            if 0 <= anim_index < num_frames:
                 current_frame_surf = ui_frames[anim_index]
            else: # Fallback within frames
                 current_frame_surf = ui_frames[0]
                 player_data["cooldown_anim_frame_index"] = 0

            # Blit the selected frame
            if current_frame_surf:
                 # Ensure rect is recalculated based on potentially variable frame sizes?
                 # Or assume all frames are scaled to the same size. Let's assume consistent size.
                 frame_rect = current_frame_surf.get_rect(center=indicator_center)
                 surface.blit(current_frame_surf, frame_rect.topleft)
        # else:
            # Optional: Draw a static "ready" indicator if GIF failed but you still want something
            # pygame.draw.circle(surface, YELLOW, indicator_center, indicator_radius)
            # For now, draw nothing if GIF failed and it's ready, as per previous request

    else:
        # --- Cooling Down: Draw Progress Arc ---
        progress = min(1.0, elapsed / cooldown) if cooldown > 0 else 1.0

        # 1. Draw Background Circle (always visible during cooldown)
        pygame.draw.circle(surface, DARK_GREY, indicator_center, indicator_radius)

        # 2. Draw Progress Arc (Cyan)
        start_angle = math.pi / 2 # Top of the circle
        # For pygame.draw.arc, angle increases counter-clockwise.
        # To make it visually fill clockwise, the end angle should be calculated this way:
        end_angle = start_angle + (progress * 2 * math.pi)

        # Ensure angles are slightly different to avoid drawing nothing/full circle issues
        if abs(start_angle - end_angle) > 0.01 and progress < 0.999: # Don't draw full cyan circle
            arc_rect = pygame.Rect(0, 0, indicator_radius * 2, indicator_radius * 2)
            arc_rect.center = indicator_center
            try:
                 # Draw the arc from the fixed start angle to the calculated end angle
                 pygame.draw.arc(surface, CYAN, arc_rect, start_angle, end_angle, arc_width)
            except ValueError:
                 pass # Ignore errors from drawing tiny/invalid arcs


# (render_text_with_bg function remains the same - unchanged)
def render_text_with_bg(surface, font, text, fg_color, bg_color=(0,0,0,180), center_pos=(WIDTH//2, HEIGHT//2), padding=(10, 6)):
    if not font: return None
    text_surf, text_rect = None, None
    try:
        if hasattr(font, 'render_to'): text_surf, text_rect = font.render(text, fgcolor=fg_color)
        else:
            text_surf = font.render(text, True, fg_color)
            if text_surf: text_rect = text_surf.get_rect()
    except Exception as e: print(f"Font render error: {e}"); return None
    if not text_surf or not text_rect: return None
    text_rect.center = center_pos
    if len(bg_color) < 4 or bg_color[3] > 0:
        bg_rect = text_rect.inflate(padding[0]*2, padding[1]*2)
        try:
            bg_surf = pygame.Surface(bg_rect.size, pygame.SRCALPHA); bg_surf.fill(bg_color)
            surface.blit(bg_surf, bg_rect.topleft)
        except Exception as e: print(f"Error creating BG surf: {e}")
    surface.blit(text_surf, text_rect)
    return text_rect

# --- Asset Loading Helpers ---
# (load_gif_frames function remains the same - unchanged)
def load_gif_frames(gif_path, scale_to=None):
    frames = []
    if imageio is None or np is None: print("ERROR: imageio/numpy missing."); return []
    if not os.path.exists(gif_path): print(f"ERROR: GIF not found: {gif_path}"); return []
    try:
        gif_reader = imageio.get_reader(gif_path)
        for frame_data in gif_reader:
            if not isinstance(frame_data, np.ndarray): continue
            if frame_data.ndim == 3:
                 if frame_data.shape[2] == 4: mode = "RGBA"
                 elif frame_data.shape[2] == 3: mode = "RGB"
                 else: continue
                 surface = pygame.image.frombuffer(frame_data.tobytes(), (frame_data.shape[1], frame_data.shape[0]), mode)
                 if scale_to and isinstance(scale_to, tuple) and len(scale_to) == 2:
                     try:
                         target_w, target_h = int(scale_to[0]), int(scale_to[1])
                         if target_w > 0 and target_h > 0: surface = pygame.transform.smoothscale(surface, (target_w, target_h))
                     except Exception as e: print(f"Warning: Could not scale frame - {e}")
                 frames.append(surface.convert_alpha())
        gif_reader.close()
    except Exception as e: print(f"ERROR loading/processing GIF '{gif_path}': {e}"); return []
    return frames