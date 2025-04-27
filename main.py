# main.py
import pygame
import sys
import socket
import threading
import time
import json
from constants import *
import game_state # Assuming game_state.py exists and works
import traceback

# --- Pyperclip Check ---
PYPERCLIP_AVAILABLE = False
try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
    print("Pyperclip library found and imported successfully.")
except ImportError:
    print("Warning: Pyperclip library not found (pip install pyperclip).")
    print("Paste functionality will rely solely on pygame.scrap (if available).")

# --- Pygame Init ---
pygame.init()
pygame.font.init()

# --- Pygame Scrap Init ---
SCRAP_INITIALIZED = False
try:
    pygame.scrap.init()
    SCRAP_INITIALIZED = pygame.scrap.get_init()
    if SCRAP_INITIALIZED:
        print("Clipboard (pygame.scrap) module initialized successfully.")
    else:
        print("Warning: pygame.scrap module initialized but status check failed.")
        print("Paste functionality will rely on pyperclip (if available).")
except pygame.error as e:
    print(f"Warning: pygame.scrap module could not be initialized: {e}")
    print("Paste functionality will rely on pyperclip (if available).")
except AttributeError:
    print(f"Warning: pygame.scrap module not found or available on this system.")
    print("Paste functionality will rely on pyperclip (if available).")
except Exception as e:
    print(f"Warning: An unexpected error occurred during pygame.scrap init: {e}")
    print("Paste functionality will rely on pyperclip (if available).")

# --- Constants & Globals ---
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREY = (128, 128, 128)

SERVER_IP_BIND = '0.0.0.0'
SERVER_PORT_TCP = 5555
DISCOVERY_PORT_UDP = 5556
BUFFER_SIZE = 4096
BROADCAST_INTERVAL_S = 1.0
CLIENT_SEARCH_TIMEOUT_S = 5.0
SERVICE_NAME = "fence_game_lan_v3" # Consider changing if significant changes

screen = None
clock = None
font_small = None
font_medium = None
font_large = None
app_running = True

# Networking Globals (Server)
server_tcp_socket = None
server_udp_socket = None
client_connection = None
client_address = None
client_input_buffer = {}
client_lock = threading.Lock()
broadcast_thread = None
client_handler_thread = None

# Networking Globals (Client)
client_tcp_socket = None

# --- Helper Functions ---

def get_local_ip():
    """Attempts to find the best local IP address for LAN communication."""
    best_ip = '127.0.0.1'
    try:
        host_name = socket.gethostname()
        addr_info = socket.getaddrinfo(host_name, None)
        candidate_ips = []
        # Prioritize common private IPv4 ranges
        for item in addr_info:
            if item[0] == socket.AF_INET: # Ensure IPv4
                ip = item[4][0]
                candidate_ips.append(ip)
                if ip.startswith(('192.168.', '10.', '172.')):
                    # Test connectivity (basic check)
                    s_test = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    try:
                         s_test.connect((ip, 1)) # Try connecting to a dummy port
                         best_ip = ip
                         s_test.close()
                         return best_ip # Found a good private IP, return it
                    except OSError: s_test.close() # Connection refused, likely good IP
                    except Exception: s_test.close() # Other errors

        # If no private IP found, try other non-loopback IPs
        for ip in candidate_ips:
            if ip != '127.0.0.1':
                s_test = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                     s_test.connect((ip, 1))
                     best_ip = ip
                     s_test.close()
                     return best_ip
                except OSError: s_test.close()
                except Exception: s_test.close()

        # If still only 127.0.0.1, try a more robust fallback
        if best_ip == '127.0.0.1':
             s_fallback = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
             try:
                 # Connect to a public IP (doesn't actually send data)
                 s_fallback.connect(('10.255.255.255', 1)) # Google DNS, common choice
                 best_ip = s_fallback.getsockname()[0]
             except Exception:
                 # Final fallback: gethostbyname (can be unreliable)
                 try: best_ip = socket.gethostbyname(socket.gethostname())
                 except Exception: best_ip = '127.0.0.1' # Give up
             finally: s_fallback.close()

    except socket.gaierror:
        # Handle case where getaddrinfo fails
        s_final = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s_final.connect(('10.255.255.255', 1))
            best_ip = s_final.getsockname()[0]
        except Exception: best_ip = '127.0.0.1'
        finally: s_final.close()

    return best_ip

def encode_data(data):
    """Encodes Python dictionary to JSON bytes."""
    try: return json.dumps(data).encode('utf-8')
    except TypeError as e:
        print(f"Encoding Error: Could not serialize data. Error: {e}")
        print(f"Problematic Data Snippet: {str(data)[:200]}") # Log snippet
        return None
    except Exception as e: print(f"Unexpected Encoding Error: {e}"); return None

def decode_data(byte_data):
    """Decodes JSON bytes to Python dictionary."""
    if not byte_data: return None
    try: return json.loads(byte_data.decode('utf-8'))
    except json.JSONDecodeError as e:
        print(f"Decoding Error: Invalid JSON received. Error: {e}")
        print(f"Problematic Data Snippet: {byte_data[:200]}") # Log snippet
        return None
    except UnicodeDecodeError as e:
        print(f"Decoding Error: Invalid UTF-8 data received. Error: {e}")
        print(f"Problematic Data Snippet (raw bytes): {byte_data[:200]}") # Log raw bytes
        return None
    except Exception as e: print(f"Unexpected Decoding Error: {e}"); return None

# --- Server Functions ---

def broadcast_presence(server_lan_ip):
    """Broadcasts server presence over UDP for LAN discovery."""
    global app_running, server_udp_socket
    print(f"Starting presence broadcast on UDP port {DISCOVERY_PORT_UDP}")
    broadcast_message = encode_data({
        "service": SERVICE_NAME, "tcp_ip": server_lan_ip, "tcp_port": SERVER_PORT_TCP })
    if not broadcast_message: print("Error: Could not encode broadcast message. Broadcast aborted."); return

    try:
        server_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        server_udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        server_udp_socket.settimeout(0.5) # Non-blocking sends
    except socket.error as e: print(f"Error creating UDP broadcast socket: {e}"); server_udp_socket = None; return

    broadcast_address = ('<broadcast>', DISCOVERY_PORT_UDP) # '<broadcast>' for all interfaces
    print(f"Broadcasting service '{SERVICE_NAME}' for {server_lan_ip}:{SERVER_PORT_TCP}...")
    while app_running:
        try: server_udp_socket.sendto(broadcast_message, broadcast_address)
        except socket.error: pass # Ignore send errors if network is busy/unavailable temporarily
        except Exception as e: print(f"Unexpected error during broadcast send: {e}")
        time.sleep(BROADCAST_INTERVAL_S)

    print("Stopping presence broadcast.")
    if server_udp_socket: server_udp_socket.close(); server_udp_socket = None

def handle_client_connection(conn, addr):
    """Handles receiving data from a single connected client in a separate thread."""
    global client_input_buffer, app_running, client_lock, client_connection
    print(f"Client connected via TCP: {addr}")
    conn.settimeout(5.0) # Set a timeout for recv
    partial_data = b"" # Buffer for incomplete messages

    while app_running:
        try:
            chunk = conn.recv(BUFFER_SIZE)
            if not chunk: print(f"Client {addr} disconnected (received empty data)."); break # Client closed connection

            partial_data += chunk
            # Process all complete messages (newline delimited) in the buffer
            while b'\n' in partial_data:
                message, partial_data = partial_data.split(b'\n', 1)
                if not message: continue # Skip empty lines if any

                decoded = decode_data(message)
                if decoded and "input" in decoded:
                    with client_lock:
                        # Only update if not already disconnected (avoids race condition)
                        if not client_input_buffer.get("disconnect"):
                            client_input_buffer = decoded["input"] # Store latest input

        except socket.timeout: continue # No data received within timeout, loop again
        except socket.error as e:
            if app_running: print(f"Socket error with client {addr}: {e}. Assuming disconnect.")
            break # Assume client disconnected on error
        except Exception as e: print(f"Unexpected error handling client {addr}: {e}"); break

    print(f"Stopping client handler thread for {addr}.")
    if app_running:
        # Signal main loop that client disconnected
        with client_lock: client_input_buffer = {"disconnect": True}

    # Cleanup connection gracefully
    try: conn.shutdown(socket.SHUT_RDWR)
    except (socket.error, OSError): pass # Ignore errors if already closed
    try: conn.close()
    except (socket.error, OSError): pass
    with client_lock:
        if client_connection is conn: client_connection = None # Clear global ref if it's this one


def run_server_mode():
    """Runs the game in server (host) mode."""
    global app_running, screen, clock, font_small, font_large
    global client_connection, client_address, client_input_buffer
    global server_tcp_socket, broadcast_thread, client_handler_thread, client_lock

    try: the_game_state = game_state.GameState()
    except Exception as e: print(f"FATAL: Failed to initialize GameState: {e}"); app_running = False; return

    pygame.display.set_caption("Fence Game - HOST (Player 1 - White)")
    server_lan_ip = get_local_ip()
    print(f"Server LAN IP detected as: {server_lan_ip}")
    print("-" * 30); print(f"INFO: For external players, forward TCP port {SERVER_PORT_TCP} to {server_lan_ip}."); print("-" * 30)

    # Start broadcasting presence on LAN
    broadcast_thread = threading.Thread(target=broadcast_presence, args=(server_lan_ip,), daemon=True)
    broadcast_thread.start()

    # Setup TCP listening socket
    server_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Allow reusing address quickly
    try:
        server_tcp_socket.bind((SERVER_IP_BIND, SERVER_PORT_TCP))
        server_tcp_socket.listen(1) # Listen for one connection
        server_tcp_socket.settimeout(1.0) # Non-blocking accept
        print(f"Server TCP listening on {SERVER_IP_BIND}:{SERVER_PORT_TCP}")
    except socket.error as e: print(f"FATAL: Failed to bind server TCP socket on port {SERVER_PORT_TCP}: {e}"); app_running = False; return

    # Wait for a client connection
    print("Waiting for a client to connect via TCP...")
    client_connection = None
    while client_connection is None and app_running:
        try:
            # Handle Pygame events (like closing the window) while waiting
            for event in pygame.event.get():
                if event.type == pygame.QUIT: app_running = False; break
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: app_running = False; break
            if not app_running: break

            # Display waiting screen
            screen.fill(BLACK)
            wait_text = font_large.render("Waiting for player 2...", True, WHITE)
            ip_text = font_small.render(f"Your LAN IP: {server_lan_ip} (Port: {SERVER_PORT_TCP})", True, WHITE)
            info_text = font_small.render("Others on LAN use 'Join Game (LAN)'", True, WHITE)
            info2_text = font_small.render("Others online need Public IP + 'Join Game (Internet)'", True, WHITE)
            screen.blit(wait_text, wait_text.get_rect(center=(WIDTH//2, HEIGHT//2 - 60)))
            screen.blit(ip_text, ip_text.get_rect(center=(WIDTH//2, HEIGHT//2 + 20)))
            screen.blit(info_text, info_text.get_rect(center=(WIDTH//2, HEIGHT//2 + 60)))
            screen.blit(info2_text, info2_text.get_rect(center=(WIDTH//2, HEIGHT//2 + 90)))
            pygame.display.flip(); clock.tick(10) # Lower tick rate while waiting

            # Try to accept a connection
            client_conn_candidate, client_addr_candidate = server_tcp_socket.accept()
            # Use lock to safely assign connection globally
            with client_lock:
                 client_connection = client_conn_candidate
                 client_address = client_addr_candidate
                 client_input_buffer = {} # Reset input buffer for new client
        except socket.timeout: continue # No connection attempt, loop again
        except socket.error as e:
            if app_running: print(f"Error accepting connection: {e}")
            app_running = False; break # Fatal error accepting
        except Exception as e: print(f"Unexpected error during client wait loop: {e}"); app_running = False; break

    if not app_running or client_connection is None:
        print("Exiting server mode (app closed or no client).");
        if server_tcp_socket: server_tcp_socket.close()
        return # Exit if window closed or no client connected

    # Client connected, start game loop
    print(f"Client connected: {client_address}. Starting game...")
    # Start the client handler thread
    client_handler_thread = threading.Thread(target=handle_client_connection, args=(client_connection, client_address), daemon=True)
    client_handler_thread.start()

    # --- Server Game Loop ---
    while app_running:
        current_time_ticks = pygame.time.get_ticks()

        # --- Get P1 (Local Host) Input ---
        local_p1_input = {'keys': {}, 'action_interact': False, 'action_shoot': False, 'action_fireball': False}
        reset_requested_by_p1 = False # Server doesn't reset on its own key, waits for client msg
        for event in pygame.event.get():
            if event.type == pygame.QUIT: app_running = False; break
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: app_running = False; break
                # P1 doesn't reset directly, P2 sends reset command
                # elif the_game_state.game_over and event.key == pygame.K_RETURN: reset_requested_by_p1 = True; pass
                elif not the_game_state.game_over:
                    if event.key == pygame.K_e: local_p1_input['action_interact'] = True
                    if event.key == pygame.K_SPACE: local_p1_input['action_shoot'] = True
                    if event.key == pygame.K_r: local_p1_input['action_fireball'] = True
        if not the_game_state.game_over:
            keys = pygame.key.get_pressed()
            local_p1_input['keys'] = {'w': keys[pygame.K_w], 's': keys[pygame.K_s], 'a': keys[pygame.K_a], 'd': keys[pygame.K_d]}
        else: local_p1_input['keys'] = {} # No movement input when game over


        # --- Get P2 (Remote Client) Input ---
        remote_p2_input_copy = {'keys': {}, 'action_interact': False, 'action_shoot': False, 'action_fireball': False}
        client_disconnected = False; reset_requested_by_p2 = False
        with client_lock:
            if client_input_buffer: # Check if handler thread put new input
                if client_input_buffer.get("disconnect"): client_disconnected = True; client_input_buffer = {}; app_running = False
                elif the_game_state.game_over and client_input_buffer.get("action_reset", False): reset_requested_by_p2 = True; client_input_buffer = {} # Check for reset action
                elif not the_game_state.game_over: remote_p2_input_copy = client_input_buffer.copy(); client_input_buffer = {} # Copy input if game running
        if client_disconnected: break # Exit loop if client disconnected

        # --- Update Game State ---
        if reset_requested_by_p2: the_game_state.reset() # Reset game if P2 requested
        elif not the_game_state.game_over:
            try: the_game_state.update(local_p1_input, remote_p2_input_copy, current_time_ticks)
            except Exception as e: print(f"CRITICAL ERROR during game_state.update: {e}"); traceback.print_exc(); app_running = False; break

        # --- Send Game State to Client ---
        if client_connection:
            network_state = the_game_state.get_network_state()
            encoded_state = encode_data(network_state)
            if encoded_state:
                try: client_connection.sendall(encoded_state + b'\n') # Add newline delimiter
                except socket.error as e:
                    if app_running: print(f"Send failed (client likely disconnected): {e}")
                    # Assume disconnect on send failure, signal handler via buffer
                    with client_lock: client_input_buffer = {"disconnect": True}
                    app_running = False; break # Stop server game loop
            else: print("Error: Failed to encode network state. Cannot send.")

        # --- Draw Game ---
        screen.fill(BLACK)
        try: the_game_state.draw(screen, current_time_ticks)
        except Exception as e: print(f"CRITICAL ERROR during game_state.draw: {e}"); traceback.print_exc(); app_running = False; break
        pygame.display.flip(); clock.tick(60) # Target 60 FPS

    # --- Cleanup Server Resources ---
    print("Cleaning up server resources...")
    app_running = False # Ensure broadcast thread stops
    temp_conn = None
    with client_lock: # Safely grab connection reference if it exists
        if client_connection: temp_conn = client_connection; client_connection = None
    if temp_conn: # Close connection if it existed
         try: temp_conn.shutdown(socket.SHUT_RDWR)
         except (socket.error, OSError): pass
         try: temp_conn.close()
         except (socket.error, OSError): pass
    if server_tcp_socket: server_tcp_socket.close(); server_tcp_socket = None
    if broadcast_thread and broadcast_thread.is_alive(): broadcast_thread.join(timeout=1.0)
    if client_handler_thread and client_handler_thread.is_alive(): client_handler_thread.join(timeout=1.0)

# --- Client Functions ---

def find_server(screen_surf, font_small_obj, font_large_obj):
    """Listens for server broadcasts on LAN to find a game."""
    global app_running, clock
    print(f"Searching for server on LAN via UDP port {DISCOVERY_PORT_UDP}...")
    pygame.display.set_caption("Fence Game - Searching LAN...")
    search_text = font_large_obj.render("Searching for server on LAN...", True, WHITE)
    listen_socket = None
    found_server_ip, found_server_port = None, None

    # Setup UDP listening socket
    try:
        listen_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_socket.bind(('', DISCOVERY_PORT_UDP)) # Bind to receive broadcasts
        listen_socket.settimeout(0.5) # Non-blocking receive
        print(f"Listening for broadcasts on UDP port {DISCOVERY_PORT_UDP}")
    except socket.error as e:
        print(f"Error binding UDP listen socket {DISCOVERY_PORT_UDP}: {e}")
        print("Check if another application (or another instance of this game) is already using this port.")
        # Show error on screen
        screen_surf.fill(BLACK)
        err1 = font_small_obj.render(f"Error: Could not listen on UDP port {DISCOVERY_PORT_UDP}.", True, RED)
        err2 = font_small_obj.render("Another app using the port?", True, RED)
        screen_surf.blit(err1, err1.get_rect(center=(WIDTH//2, HEIGHT // 2 - 20)))
        screen_surf.blit(err2, err2.get_rect(center=(WIDTH//2, HEIGHT // 2 + 10)))
        pygame.display.flip(); time.sleep(4) # Show error for a few seconds
        return None, None # Cannot search

    start_time = time.time()
    my_ip = get_local_ip() # Get own IP to ignore self-broadcasts

    # Search loop
    while time.time() - start_time < CLIENT_SEARCH_TIMEOUT_S and app_running:
        # Handle Pygame events during search
        for event in pygame.event.get():
             if event.type == pygame.QUIT: app_running = False; break
             if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: print("Search cancelled by user."); app_running = False; break
        if not app_running: break

        # Update search screen
        screen_surf.fill(BLACK)
        screen_surf.blit(search_text, search_text.get_rect(center=(WIDTH//2, HEIGHT//2)))
        pygame.display.flip(); clock.tick(10)

        # Try to receive a broadcast
        try:
            data, addr = listen_socket.recvfrom(BUFFER_SIZE)
            # Ignore broadcasts from self (important if host runs on same machine)
            if addr[0] == my_ip: continue

            message = decode_data(data)
            # Validate the message structure and service name
            if (message and
                message.get("service") == SERVICE_NAME and
                isinstance(message.get("tcp_ip"), str) and
                isinstance(message.get("tcp_port"), int)):
                ip, port = message["tcp_ip"], message["tcp_port"]
                print(f"Found potential server: {ip}:{port} from {addr[0]}")
                found_server_ip, found_server_port = ip, port; break # Found one, stop searching
        except socket.timeout: continue # No broadcast received, loop again
        except socket.error as e: print(f"UDP Socket error during search: {e}"); time.sleep(0.1) # Avoid busy-looping on error
        except Exception as e: print(f"Error processing UDP broadcast: {e}")

    listen_socket.close() # Close the listening socket

    # Handle search timeout
    if not found_server_ip and app_running:
        print(f"No server found on LAN broadcasting '{SERVICE_NAME}' within {CLIENT_SEARCH_TIMEOUT_S}s.")
        # Show "Not Found" message
        screen_surf.fill(BLACK)
        fail_text_line1 = font_large_obj.render("Server not found!", True, RED)
        fail_text_line2 = font_small_obj.render("Ensure host is running and on the same LAN.", True, WHITE)
        screen_surf.blit(fail_text_line1, fail_text_line1.get_rect(center=(WIDTH//2, HEIGHT//2 - 30)))
        screen_surf.blit(fail_text_line2, fail_text_line2.get_rect(center=(WIDTH//2, HEIGHT//2 + 40)))
        pygame.display.flip()
        # Wait a bit so user sees the message
        wait_start = time.time()
        while time.time() - wait_start < 3.0 and app_running:
             for event in pygame.event.get(): # Still allow quitting
                 if event.type == pygame.QUIT: app_running = False
             if not app_running: break
             time.sleep(0.1)

    return found_server_ip, found_server_port

def get_server_id_input(screen_surf, font_prompt, font_input, font_info, clock_obj):
    """Displays an input box for the user to enter Server IP:Port."""
    global app_running, SCRAP_INITIALIZED, PYPERCLIP_AVAILABLE
    input_text = ""
    input_active = True
    cursor_visible = True
    last_cursor_toggle = time.time()
    # Define input box visually
    input_rect = pygame.Rect(WIDTH // 4, HEIGHT // 2 - 10, WIDTH // 2, 50)
    input_border_color = WHITE
    input_bg_color = GREY
    input_text_color = BLACK
    cursor_color = BLACK

    print("Prompting user for Server IP Address (or IP:Port)...")
    pygame.key.set_repeat(500, 50) # Enable key repeat for backspace

    paste_info_msg = None # To show feedback on paste attempts
    paste_msg_start_time = 0

    while input_active and app_running:
        current_time = time.time()
        # Blinking cursor effect
        if current_time - last_cursor_toggle > 0.5: cursor_visible = not cursor_visible; last_cursor_toggle = current_time

        # --- Event Handling ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT: app_running = False; input_active = False
            if event.type == pygame.KEYDOWN:
                paste_info_msg = None # Clear paste message on new key press
                if event.key == pygame.K_ESCAPE: print("Input cancelled by user."); input_active = False; input_text = None # Cancel
                elif event.key == pygame.K_RETURN:
                    if input_text.strip(): print(f"User entered Server ID: {input_text.strip()}"); input_active = False # Confirm
                    else: print("User pressed Enter with empty input."); input_text = "" # Ignore empty confirm
                elif event.key == pygame.K_BACKSPACE: input_text = input_text[:-1]
                elif event.key == pygame.K_v and (event.mod & pygame.KMOD_CTRL or event.mod & pygame.KMOD_META): # Ctrl+V or Cmd+V
                    pasted_content = None; paste_method_used = "None"
                    # Try pygame.scrap first if available
                    if SCRAP_INITIALIZED:
                        try:
                            clipboard_data = pygame.scrap.get(pygame.SCRAP_TEXT) # Request text
                            if clipboard_data:
                                # Decode bytes if necessary, clean null chars
                                cleaned_text = ""
                                if isinstance(clipboard_data, bytes):
                                    try: cleaned_text = clipboard_data.decode('utf-8', errors='ignore')
                                    except UnicodeDecodeError: # Try fallback encoding
                                         try: cleaned_text = clipboard_data.decode('latin-1', errors='ignore')
                                         except: cleaned_text = "" # Give up decoding
                                elif isinstance(clipboard_data, str): cleaned_text = clipboard_data
                                cleaned_text = cleaned_text.replace('\x00', '').strip() # Remove null bytes and whitespace
                                if cleaned_text: pasted_content = cleaned_text; paste_method_used = "pygame.scrap"
                                else: print("pygame.scrap clipboard was empty/non-text after cleaning.")
                            else: print("pygame.scrap clipboard returned no data.")
                        except pygame.error as e: print(f"pygame.scrap paste failed: {e}")
                        except Exception as e: print(f"Unexpected error during pygame.scrap paste: {e}")

                    # Try pyperclip as fallback if available and scrap failed
                    if pasted_content is None and PYPERCLIP_AVAILABLE:
                        try:
                            clipboard_text = pyperclip.paste()
                            if isinstance(clipboard_text, str):
                                cleaned_text = clipboard_text.replace('\x00', '').strip() # Clean null bytes/whitespace
                                if cleaned_text: pasted_content = cleaned_text; paste_method_used = "pyperclip"
                                else: print("pyperclip paste result was empty/whitespace after cleaning.")
                            else: print("pyperclip paste did not return a string.")
                        except Exception as e: print(f"pyperclip paste failed: {e}") # Catch potential pyperclip errors

                    # Append pasted content if successful
                    if pasted_content is not None: input_text += pasted_content; print(f"Pasted using {paste_method_used}.")
                    # Provide feedback if paste failed but a method was available
                    elif SCRAP_INITIALIZED or PYPERCLIP_AVAILABLE: print("Paste failed or clipboard empty/unusable."); paste_info_msg = "Paste Failed / Empty"; paste_msg_start_time = current_time
                    # Provide feedback if no clipboard system worked
                    else: print("Paste failed: No clipboard system available."); paste_info_msg = "Clipboard Unavailable"; paste_msg_start_time = current_time

                # Allow typical IP address characters
                elif event.unicode.isalnum() or event.unicode in ['.', ':']: input_text += event.unicode

        # --- Drawing ---
        screen_surf.fill(BLACK)
        # Prompt text
        prompt_surf = font_prompt.render("Enter Host IP Address or IP:Port", True, WHITE)
        prompt_rect = prompt_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 60))
        screen_surf.blit(prompt_surf, prompt_rect)

        # Info text (controls)
        info_surf = font_info.render("(Enter=Confirm, Esc=Cancel, Ctrl+V=Paste)", True, GREY)
        info_rect = info_surf.get_rect(center=(WIDTH // 2, HEIGHT - 40))
        screen_surf.blit(info_surf, info_rect)

        # Input box background and border
        pygame.draw.rect(screen_surf, input_bg_color, input_rect, border_radius=5)
        pygame.draw.rect(screen_surf, input_border_color, input_rect, 2, border_radius=5)

        # Render the input text
        text_surf = font_input.render(input_text, True, input_text_color)
        # Position text inside the box, handle overflow by clipping
        text_rect = text_surf.get_rect(midleft=(input_rect.left + 10, input_rect.centery))
        clip_area = input_rect.inflate(-12, -12) # Area text can be drawn in
        # If text is wider than the box, align right end to the box's right edge
        if text_rect.right > clip_area.right: text_rect.right = clip_area.right
        screen_surf.set_clip(clip_area) # Only draw text within the clip area
        screen_surf.blit(text_surf, text_rect)
        screen_surf.set_clip(None) # Reset clipping

        # Draw blinking cursor at the end of the text (within bounds)
        if cursor_visible:
            cursor_x = text_rect.right + 2
            # Ensure cursor stays within the visible input area
            if cursor_x < clip_area.left: cursor_x = clip_area.left + 2
            if cursor_x > clip_area.right: cursor_x = clip_area.right - 1
            cursor_y = input_rect.centery
            pygame.draw.line(screen_surf, cursor_color, (cursor_x, cursor_y - 15), (cursor_x, cursor_y + 15), 2)

        # Display paste feedback message temporarily
        if paste_info_msg and current_time - paste_msg_start_time < 2.0:
            msg_surf = font_info.render(paste_info_msg, True, RED if "Fail" in paste_info_msg else YELLOW)
            msg_rect = msg_surf.get_rect(center=(WIDTH // 2, input_rect.bottom + 30))
            screen_surf.blit(msg_surf, msg_rect)
        elif paste_info_msg: paste_info_msg = None # Message timed out

        pygame.display.flip(); clock_obj.tick(30) # Lower tick rate for input screen

    pygame.key.set_repeat(0, 0) # Disable key repeat after input
    return input_text.strip() if input_text is not None else None # Return cleaned input or None if cancelled


def run_client_mode(target_ip_port=None):
    """Runs the game in client (join) mode."""
    global app_running, screen, clock, font_small, font_large, client_tcp_socket

    try: the_game_state = game_state.GameState()
    except Exception as e: print(f"FATAL: Failed to initialize GameState on client: {e}"); app_running = False; return

    server_ip_connect = None
    server_port_connect = SERVER_PORT_TCP # Default port

    # Determine server address: use provided target, or search LAN
    if target_ip_port: # User chose "Join Internet" and provided an address
        print(f"Attempting direct connection to: {target_ip_port}")
        # Parse IP and Port if provided (e.g., "1.2.3.4:5555")
        if ':' in target_ip_port:
             parts = target_ip_port.rsplit(':', 1); ip_part = parts[0]; port_part = parts[1]
             try:
                 port_num = int(port_part)
                 # Basic port validation
                 if 0 < port_num < 65536: server_ip_connect = ip_part; server_port_connect = port_num; print(f"Parsed IP: {server_ip_connect}, Port: {server_port_connect}")
                 else: print(f"Warning: Invalid port number '{port_part}' in input. Using default {SERVER_PORT_TCP}."); server_ip_connect = ip_part
             except ValueError: print(f"Warning: Could not parse port from '{port_part}'. Assuming input is just IP."); server_ip_connect = target_ip_port # Treat as IP only
        else: server_ip_connect = target_ip_port # No colon, assume it's just the IP
    else: # User chose "Join LAN", search automatically
        pygame.display.set_caption("Fence Game - Searching LAN...")
        server_ip_connect, found_port = find_server(screen, font_small, font_large)
        if found_port: server_port_connect = found_port # Use port found via broadcast

    # Exit if no server address could be determined
    if not server_ip_connect:
        if app_running: print("Exiting client mode (no server address).")
        return
    if not app_running: print("Exiting client mode (app closed during search/input)."); return

    # --- Connect to Server ---
    client_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    connection_successful = False; error_message = "Unknown Error"
    try:
        print(f"Attempting TCP connection to {server_ip_connect}:{server_port_connect}...")
        # Display connecting screen
        pygame.display.set_caption(f"Fence Game - Connecting...")
        screen.fill(BLACK)
        conn_text = font_large.render(f"Connecting to Host...", True, WHITE)
        conn_details = font_small.render(f"({server_ip_connect}:{server_port_connect})", True, GREY)
        screen.blit(conn_text, conn_text.get_rect(center=(WIDTH//2, HEIGHT//2 - 20)))
        screen.blit(conn_details, conn_details.get_rect(center=(WIDTH//2, HEIGHT//2 + 30)))
        pygame.display.flip()

        client_tcp_socket.settimeout(10.0) # Generous timeout for connection attempt
        client_tcp_socket.connect((server_ip_connect, server_port_connect))
        client_tcp_socket.settimeout(5.0) # Shorter timeout for game communication
        print("TCP Connection successful!"); connection_successful = True
    except socket.gaierror as e: print(f"Connection Error: Address-related error - {e}"); error_message = f"Invalid Address or Hostname!"
    except socket.timeout: print(f"Connection Error: Connection timed out."); error_message = f"Connection Timed Out!"
    except socket.error as e: print(f"Connection Error: {e}"); error_message = f"Connection Failed! ({e.strerror})" # Use strerror for readable error
    except Exception as e: print(f"Unexpected Connection Error: {e}"); error_message = "An Unexpected Error Occurred!"

    # Handle connection failure
    if not connection_successful:
        # Show failure message
        screen.fill(BLACK)
        fail_text1 = font_large.render(f"Connection Failed", True, RED)
        fail_text2 = font_small.render(error_message, True, WHITE)
        fail_text3 = font_small.render(f"Host: {server_ip_connect}:{server_port_connect}", True, GREY)
        screen.blit(fail_text1, fail_text1.get_rect(center=(WIDTH//2, HEIGHT//2 - 50)))
        screen.blit(fail_text2, fail_text2.get_rect(center=(WIDTH//2, HEIGHT//2 + 0)))
        screen.blit(fail_text3, fail_text3.get_rect(center=(WIDTH//2, HEIGHT//2 + 40)))
        pygame.display.flip(); time.sleep(4) # Show message
        if client_tcp_socket: client_tcp_socket.close(); client_tcp_socket = None
        return

    # --- Client Game Loop ---
    pygame.display.set_caption("Fence Game - CLIENT (Player 2 - Red)")
    last_received_state = None # Store the most recent full state from server
    partial_data = b"" # Buffer for incomplete messages

    while app_running:
        current_time_ticks = pygame.time.get_ticks()

        # --- Get P2 (Local Client) Input ---
        local_p2_input = {'keys': {}, 'action_interact': False, 'action_shoot': False, 'action_fireball': False, 'action_reset': False}
        # Check game over status based on the *locally known* state
        is_game_over_locally = the_game_state.game_over

        for event in pygame.event.get():
            if event.type == pygame.QUIT: app_running = False; break
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: app_running = False; break
                # Only allow reset input if the local game state shows game over
                elif is_game_over_locally and event.key == pygame.K_RETURN: print("Sending reset request to server..."); local_p2_input['action_reset'] = True; continue # Set reset flag, skip other inputs
                # Handle game actions only if game is not over locally
                elif not is_game_over_locally:
                    if event.key == pygame.K_e: local_p2_input['action_interact'] = True
                    if event.key == pygame.K_SPACE: local_p2_input['action_shoot'] = True
                    if event.key == pygame.K_r: local_p2_input['action_fireball'] = True

        # Get movement keys only if game not over and not requesting reset
        if not is_game_over_locally and not local_p2_input['action_reset']:
            keys = pygame.key.get_pressed()
            local_p2_input['keys'] = {'w': keys[pygame.K_w], 's': keys[pygame.K_s], 'a': keys[pygame.K_a], 'd': keys[pygame.K_d]}
        else: local_p2_input['keys'] = {} # Clear movement if game over or resetting

        # --- Send Input to Server ---
        if client_tcp_socket:
            client_input_data = {"input": local_p2_input} # Wrap input in dict structure expected by server
            encoded_input = encode_data(client_input_data)
            if encoded_input:
                try: client_tcp_socket.sendall(encoded_input + b'\n') # Add newline delimiter
                except socket.error as e:
                    if app_running: print(f"Send failed (server disconnected?): {e}")
                    app_running = False; break # Assume disconnect
            else: print("Error: Failed to encode client input. Cannot send.")

        # --- Receive Game State from Server ---
        received_new_state_this_frame = False
        if client_tcp_socket:
            try:
                # Non-blocking read using timeout
                chunk = client_tcp_socket.recv(BUFFER_SIZE)
                if not chunk: # Server closed connection
                    if app_running: print("Server disconnected (received empty data).")
                    app_running = False; break
                partial_data += chunk
                # Process all complete messages in buffer
                processed_a_message = False
                while b'\n' in partial_data:
                    message, partial_data = partial_data.split(b'\n', 1)
                    if not message: continue # Skip empty lines

                    decoded_state = decode_data(message)
                    if decoded_state:
                        # Store the latest valid state received
                        last_received_state = decoded_state
                        received_new_state_this_frame = True
                        processed_a_message = True
                    #else: print("Received invalid state data.") # Already printed by decode_data

            except socket.timeout: pass # No data received, normal operation
            except socket.error as e:
                if app_running: print(f"Receive error (server disconnected?): {e}")
                app_running = False; break # Assume disconnect
            except Exception as e:
                if app_running: print(f"Error processing data from server: {e}")
                app_running = False; break # Unexpected error
        else: # Should not happen if connection succeeded, but good safety check
             if app_running: print("Error: Client socket is None in game loop.")
             app_running = False; break

        # --- Update Local Game State (from received data) ---
        if last_received_state: # Only update if we have ever received a state
             try: the_game_state.set_network_state(last_received_state)
             except Exception as e:
                 print(f"CRITICAL: Error applying network state: {e}")
                 print(f"Problematic state data: {str(last_received_state)[:500]}") # Log state snippet
                 traceback.print_exc(); app_running = False; break # Stop on critical error

        # --- Draw Game (based on latest applied state) ---
        screen.fill(BLACK)
        try: the_game_state.draw(screen, current_time_ticks)
        except Exception as e: print(f"CRITICAL ERROR during client game_state.draw: {e}"); traceback.print_exc(); app_running = False; break
        pygame.display.flip(); clock.tick(60)

    # --- Cleanup Client Resources ---
    print("Cleaning up client resources...")
    if client_tcp_socket:
        try: client_tcp_socket.shutdown(socket.SHUT_RDWR) # Signal closing
        except (socket.error, OSError): pass # Ignore errors if already closed
        try: client_tcp_socket.close()
        except (socket.error, OSError): pass
        client_tcp_socket = None

# --- Couch Play Mode ---

def run_couch_play_mode():
    """Runs the game locally for two players on the same computer."""
    global app_running, screen, clock, font_small, font_large

    print("Starting Couch Play mode...")
    pygame.display.set_caption("Fence Game - Couch Play (P1: WASD+E/R/Spc, P2: Arrows+Shift/Ctrl/Enter)")

    try:
        the_game_state = game_state.GameState()
    except Exception as e:
        print(f"FATAL: Failed to initialize GameState for Couch Play: {e}")
        app_running = False
        return

    # --- Couch Play Game Loop ---
    while app_running:
        current_time_ticks = pygame.time.get_ticks()

        # --- Get P1 (Local) Input ---
        # Using WASD, E (interact), R (fireball), Space (shoot)
        local_p1_input = {'keys': {}, 'action_interact': False, 'action_shoot': False, 'action_fireball': False}
        reset_requested = False # Shared reset flag

        for event in pygame.event.get():
            if event.type == pygame.QUIT: app_running = False; break
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: app_running = False; break
                # Check for reset key (Enter) only if game is over
                elif the_game_state.game_over and event.key == pygame.K_RETURN: reset_requested = True; continue
                # Player 1 Action Keys (only if game not over)
                elif not the_game_state.game_over:
                    if event.key == pygame.K_e: local_p1_input['action_interact'] = True
                    if event.key == pygame.K_SPACE: local_p1_input['action_shoot'] = True
                    if event.key == pygame.K_r: local_p1_input['action_fireball'] = True

        # Player 1 Movement Keys (only if game not over)
        if not the_game_state.game_over:
            keys_p1 = pygame.key.get_pressed()
            local_p1_input['keys'] = {
                'w': keys_p1[pygame.K_w], 's': keys_p1[pygame.K_s],
                'a': keys_p1[pygame.K_a], 'd': keys_p1[pygame.K_d]
            }
        else: local_p1_input['keys'] = {} # No movement input when game over

        # --- Get P2 (Local) Input ---
        # Using Arrow Keys, RSHIFT (interact), RCTRL (fireball), KP_ENTER/RETURN (shoot)
        local_p2_input = {'keys': {}, 'action_interact': False, 'action_shoot': False, 'action_fireball': False}

        # We already handled events, just need to check pressed keys for P2 actions/movement
        keys_p2 = pygame.key.get_pressed() # Get all pressed keys state

        # Player 2 Action Keys (only if game not over)
        if not the_game_state.game_over:
            local_p2_input['action_interact'] = keys_p2[pygame.K_RSHIFT] or keys_p2[pygame.K_LSHIFT] # Allow either Shift
            # Allow Numpad Enter or Right Ctrl for shoot (choose distinct keys)
            local_p2_input['action_shoot'] = keys_p2[pygame.K_KP_ENTER] or keys_p2[pygame.K_RCTRL]
            local_p2_input['action_fireball'] = keys_p2[pygame.K_KP_PERIOD] or keys_p2[pygame.K_SLASH] # e.g., Numpad . or / ?

        # Player 2 Movement Keys (only if game not over)
        if not the_game_state.game_over:
            local_p2_input['keys'] = {
                'w': keys_p2[pygame.K_UP], 's': keys_p2[pygame.K_DOWN],
                'a': keys_p2[pygame.K_LEFT], 'd': keys_p2[pygame.K_RIGHT]
            }
        else: local_p2_input['keys'] = {} # No movement input when game over


        # --- Update Game State ---
        if reset_requested: the_game_state.reset()
        elif not the_game_state.game_over:
            try:
                the_game_state.update(local_p1_input, local_p2_input, current_time_ticks)
            except Exception as e:
                print(f"CRITICAL ERROR during couch play game_state.update: {e}")
                traceback.print_exc()
                app_running = False
                break

        # --- Draw Game ---
        screen.fill(BLACK)
        try:
            the_game_state.draw(screen, current_time_ticks)
        except Exception as e:
            print(f"CRITICAL ERROR during couch play game_state.draw: {e}")
            traceback.print_exc()
            app_running = False
            break
        pygame.display.flip()
        clock.tick(60) # Target 60 FPS

    print("Exiting Couch Play mode.")
    # No network resources to clean up here


# --- Main Menu ---

def show_menu():
    """Displays the main menu and returns the user's choice."""
    global screen, clock, font_small, font_medium, font_large, app_running
    button_width, button_height, spacing = 300, 55, 20
    title_button_gap = 50 # <-- Added: Pixels between title bottom and first button top

    # Colors and Text
    title_color = WHITE; button_text_color = WHITE; button_color = BLUE; button_hover_color = GREEN

    # --- Title ---
    title = font_large.render("Fence Game", True, title_color) # Simplified title
    title_rect = title.get_rect(center=(WIDTH // 2, HEIGHT // 4)) # Position the title

    # --- Calculate Button Positions ---
    # Start the first button below the title + gap
    first_button_y = title_rect.bottom + title_button_gap
    button_center_x = WIDTH // 2

    host_rect = pygame.Rect(0, 0, button_width, button_height)
    host_rect.centerx = button_center_x
    host_rect.top = first_button_y

    join_lan_rect = pygame.Rect(0, 0, button_width, button_height)
    join_lan_rect.centerx = button_center_x
    join_lan_rect.top = host_rect.bottom + spacing # Position below previous + spacing

    join_internet_rect = pygame.Rect(0, 0, button_width, button_height)
    join_internet_rect.centerx = button_center_x
    join_internet_rect.top = join_lan_rect.bottom + spacing # Position below previous + spacing

    couch_play_rect = pygame.Rect(0, 0, button_width, button_height)
    couch_play_rect.centerx = button_center_x
    couch_play_rect.top = join_internet_rect.bottom + spacing # Position below previous + spacing

    # --- Render Button Text (centered within their rects) ---
    host_text = font_medium.render("Host Game (Online)", True, button_text_color)
    host_text_rect = host_text.get_rect(center=host_rect.center)

    join_lan_text = font_medium.render("Join Game (LAN)", True, button_text_color)
    join_lan_text_rect = join_lan_text.get_rect(center=join_lan_rect.center)

    join_internet_text = font_medium.render("Join Game (Internet)", True, button_text_color)
    join_internet_text_rect = join_internet_text.get_rect(center=join_internet_rect.center)

    couch_play_text = font_medium.render("Couch Play (Local)", True, button_text_color)
    couch_play_text_rect = couch_play_text.get_rect(center=couch_play_rect.center)

    # --- Menu Loop ---
    selected_option = None
    while selected_option is None and app_running:
        mouse_pos = pygame.mouse.get_pos()
        # Check hover state for all buttons
        host_hover = host_rect.collidepoint(mouse_pos)
        join_lan_hover = join_lan_rect.collidepoint(mouse_pos)
        join_internet_hover = join_internet_rect.collidepoint(mouse_pos)
        couch_play_hover = couch_play_rect.collidepoint(mouse_pos)

        for event in pygame.event.get():
            if event.type == pygame.QUIT: app_running = False; selected_option = "quit"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: app_running = False; selected_option = "quit"
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1: # Left click
                if host_hover: selected_option = "host"
                elif join_lan_hover: selected_option = "join_lan"
                elif join_internet_hover: selected_option = "join_internet"
                elif couch_play_hover: selected_option = "couch_play"

        # --- Drawing Menu ---
        screen.fill(BLACK)
        screen.blit(title, title_rect) # Draw title first

        # Draw Host button
        pygame.draw.rect(screen, button_hover_color if host_hover else button_color, host_rect, border_radius=8)
        screen.blit(host_text, host_text_rect)

        # Draw Join LAN button
        pygame.draw.rect(screen, button_hover_color if join_lan_hover else button_color, join_lan_rect, border_radius=8)
        screen.blit(join_lan_text, join_lan_text_rect)

        # Draw Join Internet button
        pygame.draw.rect(screen, button_hover_color if join_internet_hover else button_color, join_internet_rect, border_radius=8)
        screen.blit(join_internet_text, join_internet_text_rect)

        # Draw Couch Play button
        pygame.draw.rect(screen, button_hover_color if couch_play_hover else button_color, couch_play_rect, border_radius=8)
        screen.blit(couch_play_text, couch_play_text_rect)

        pygame.display.flip(); clock.tick(30)

    return selected_option

# --- Main Execution ---

if __name__ == "__main__":
    # Initialize Pygame screen, clock, fonts
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Fence Game") # Initial caption
    clock = pygame.time.Clock()
    try:
        font_small = pygame.font.Font(None, 28)
        font_medium = pygame.font.Font(None, 36)
        font_large = pygame.font.Font(None, 72)
    except Exception as e:
         print(f"FATAL: Font loading error: {e}"); print("Please ensure default pygame fonts are available."); pygame.quit(); sys.exit(1)

    # Show menu and get choice
    menu_choice = show_menu()

    # Execute based on choice
    if menu_choice == "host": run_server_mode()
    elif menu_choice == "join_lan": run_client_mode() # No target IP needed
    elif menu_choice == "join_internet":
        target_server_ip_port = get_server_id_input(screen, font_medium, font_medium, font_small, clock)
        if target_server_ip_port and app_running: run_client_mode(target_ip_port=target_server_ip_port) # Pass target IP
        elif app_running: print("Join Internet cancelled or no IP entered.")
    elif menu_choice == "couch_play": run_couch_play_mode() # Call the new function
    elif menu_choice == "quit": print("Quit selected from menu.")
    else:
        if app_running: print("No valid menu option selected or menu closed.") # Only print if app wasn't quit

    # --- Cleanup ---
    print("Exiting application.")
    pygame.quit()

    # Attempt to quit pygame.scrap if initialized
    try:
        if SCRAP_INITIALIZED and pygame.scrap.get_init(): pygame.scrap.quit(); print("Pygame scrap module quit.")
    except AttributeError: pass # Module didn't exist
    except pygame.error as e: print(f"Error quitting scrap module: {e}")
    except Exception as e: print(f"Unexpected error quitting scrap module: {e}")

    sys.exit(0)