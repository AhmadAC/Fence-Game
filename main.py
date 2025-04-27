# main.py
import pygame
import sys
import socket
import threading
import time
import json
from constants import *
import game_state
import traceback

PYPERCLIP_AVAILABLE = False
try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
    print("Pyperclip library found and imported successfully.")
except ImportError:
    print("Warning: Pyperclip library not found (pip install pyperclip).")
    print("Paste functionality will rely solely on pygame.scrap (if available).")

pygame.init()
pygame.font.init()
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


BLUE = (0, 0, 255)

SERVER_IP_BIND = '0.0.0.0'
SERVER_PORT_TCP = 5555
DISCOVERY_PORT_UDP = 5556
BUFFER_SIZE = 4096
BROADCAST_INTERVAL_S = 1.0
CLIENT_SEARCH_TIMEOUT_S = 5.0
SERVICE_NAME = "fence_game_lan_v3"

screen = None
clock = None
font_small = None
font_medium = None
font_large = None
app_running = True

server_tcp_socket = None
server_udp_socket = None
client_connection = None
client_address = None
client_input_buffer = {}
client_lock = threading.Lock()
broadcast_thread = None
client_handler_thread = None

client_tcp_socket = None

def get_local_ip():
    best_ip = '127.0.0.1'
    try:
        host_name = socket.gethostname()
        addr_info = socket.getaddrinfo(host_name, None)
        candidate_ips = []
        for item in addr_info:
            if item[0] == socket.AF_INET:
                ip = item[4][0]
                candidate_ips.append(ip)
                if ip.startswith(('192.168.', '10.', '172.')):
                    s_test = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    try:
                         s_test.connect((ip, 1))
                         best_ip = ip
                         s_test.close()
                         return best_ip
                    except OSError: s_test.close()
                    except Exception: s_test.close()
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
        if best_ip == '127.0.0.1':
             s_fallback = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
             try:
                 s_fallback.connect(('10.255.255.255', 1))
                 best_ip = s_fallback.getsockname()[0]
             except Exception:
                 try: best_ip = socket.gethostbyname(socket.gethostname())
                 except Exception: best_ip = '127.0.0.1'
             finally: s_fallback.close()
    except socket.gaierror:
        s_final = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s_final.connect(('10.255.255.255', 1))
            best_ip = s_final.getsockname()[0]
        except Exception: best_ip = '127.0.0.1'
        finally: s_final.close()
    return best_ip

def encode_data(data):
    try: return json.dumps(data).encode('utf-8')
    except TypeError as e:
        print(f"Encoding Error: Could not serialize data. Error: {e}")
        print(f"Problematic Data Snippet: {str(data)[:200]}")
        return None
    except Exception as e: print(f"Unexpected Encoding Error: {e}"); return None

def decode_data(byte_data):
    if not byte_data: return None
    try: return json.loads(byte_data.decode('utf-8'))
    except json.JSONDecodeError as e:
        print(f"Decoding Error: Invalid JSON received. Error: {e}")
        print(f"Problematic Data Snippet: {byte_data[:200]}")
        return None
    except UnicodeDecodeError as e:
        print(f"Decoding Error: Invalid UTF-8 data received. Error: {e}")
        print(f"Problematic Data Snippet (raw bytes): {byte_data[:200]}")
        return None
    except Exception as e: print(f"Unexpected Decoding Error: {e}"); return None

def broadcast_presence(server_lan_ip):
    global app_running, server_udp_socket
    print(f"Starting presence broadcast on UDP port {DISCOVERY_PORT_UDP}")
    broadcast_message = encode_data({
        "service": SERVICE_NAME, "tcp_ip": server_lan_ip, "tcp_port": SERVER_PORT_TCP })
    if not broadcast_message: print("Error: Could not encode broadcast message. Broadcast aborted."); return
    try:
        server_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        server_udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        server_udp_socket.settimeout(0.5)
    except socket.error as e: print(f"Error creating UDP broadcast socket: {e}"); server_udp_socket = None; return
    broadcast_address = ('<broadcast>', DISCOVERY_PORT_UDP)
    print(f"Broadcasting service '{SERVICE_NAME}' for {server_lan_ip}:{SERVER_PORT_TCP}...")
    while app_running:
        try: server_udp_socket.sendto(broadcast_message, broadcast_address)
        except socket.error: pass
        except Exception as e: print(f"Unexpected error during broadcast send: {e}")
        time.sleep(BROADCAST_INTERVAL_S)
    print("Stopping presence broadcast.")
    if server_udp_socket: server_udp_socket.close(); server_udp_socket = None

def handle_client_connection(conn, addr):
    global client_input_buffer, app_running, client_lock, client_connection
    print(f"Client connected via TCP: {addr}")
    conn.settimeout(5.0)
    partial_data = b""
    while app_running:
        try:
            chunk = conn.recv(BUFFER_SIZE)
            if not chunk: print(f"Client {addr} disconnected (received empty data)."); break
            partial_data += chunk
            while b'\n' in partial_data:
                message, partial_data = partial_data.split(b'\n', 1)
                if not message: continue
                decoded = decode_data(message)
                if decoded and "input" in decoded:
                    with client_lock:
                        if not client_input_buffer.get("disconnect"):
                            client_input_buffer = decoded["input"]
        except socket.timeout: continue
        except socket.error as e:
            if app_running: print(f"Socket error with client {addr}: {e}. Assuming disconnect.")
            break
        except Exception as e: print(f"Unexpected error handling client {addr}: {e}"); break
    print(f"Stopping client handler thread for {addr}.")
    if app_running:
        with client_lock: client_input_buffer = {"disconnect": True}
    try: conn.shutdown(socket.SHUT_RDWR)
    except (socket.error, OSError): pass
    try: conn.close()
    except (socket.error, OSError): pass
    with client_lock:
        if client_connection is conn: client_connection = None

def run_server_mode():
    global app_running, screen, clock, font_small, font_large
    global client_connection, client_address, client_input_buffer
    global server_tcp_socket, broadcast_thread, client_handler_thread, client_lock

    try: the_game_state = game_state.GameState()
    except Exception as e: print(f"FATAL: Failed to initialize GameState: {e}"); app_running = False; return

    pygame.display.set_caption("Fence Game - HOST (Player 1 - White)")
    server_lan_ip = get_local_ip()
    print(f"Server LAN IP detected as: {server_lan_ip}")
    print("-" * 30); print(f"INFO: For external players, forward TCP port {SERVER_PORT_TCP} to {server_lan_ip}."); print("-" * 30)

    broadcast_thread = threading.Thread(target=broadcast_presence, args=(server_lan_ip,), daemon=True)
    broadcast_thread.start()

    server_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_tcp_socket.bind((SERVER_IP_BIND, SERVER_PORT_TCP))
        server_tcp_socket.listen(1); server_tcp_socket.settimeout(1.0)
        print(f"Server TCP listening on {SERVER_IP_BIND}:{SERVER_PORT_TCP}")
    except socket.error as e: print(f"FATAL: Failed to bind server TCP socket on port {SERVER_PORT_TCP}: {e}"); app_running = False; return

    print("Waiting for a client to connect via TCP...")
    client_connection = None
    while client_connection is None and app_running:
        try:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: app_running = False; break
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: app_running = False; break
            if not app_running: break
            screen.fill(BLACK)
            wait_text = font_large.render("Waiting for player 2...", True, WHITE)
            ip_text = font_small.render(f"Your LAN IP: {server_lan_ip} (Port: {SERVER_PORT_TCP})", True, WHITE)
            info_text = font_small.render("Others on LAN use 'Join Game (LAN)'", True, WHITE)
            info2_text = font_small.render("Others online need Public IP + 'Join Game (Internet)'", True, WHITE)
            screen.blit(wait_text, wait_text.get_rect(center=(WIDTH//2, HEIGHT//2 - 60)))
            screen.blit(ip_text, ip_text.get_rect(center=(WIDTH//2, HEIGHT//2 + 20)))
            screen.blit(info_text, info_text.get_rect(center=(WIDTH//2, HEIGHT//2 + 60)))
            screen.blit(info2_text, info2_text.get_rect(center=(WIDTH//2, HEIGHT//2 + 90)))
            pygame.display.flip(); clock.tick(10)
            client_conn_candidate, client_addr_candidate = server_tcp_socket.accept()
            with client_lock:
                 client_connection = client_conn_candidate
                 client_address = client_addr_candidate
                 client_input_buffer = {}
        except socket.timeout: continue
        except socket.error as e:
            if app_running: print(f"Error accepting connection: {e}")
            app_running = False; break
        except Exception as e: print(f"Unexpected error during client wait loop: {e}"); app_running = False; break

    if not app_running or client_connection is None:
        print("Exiting server mode (app closed or no client).");
        if server_tcp_socket: server_tcp_socket.close()
        return

    print(f"Client connected: {client_address}. Starting game...")
    client_handler_thread = threading.Thread(target=handle_client_connection, args=(client_connection, client_address), daemon=True)
    client_handler_thread.start()

    while app_running:
        current_time_ticks = pygame.time.get_ticks()
        local_p1_input = {'keys': {}, 'action_interact': False, 'action_shoot': False, 'action_fireball': False}
        reset_requested_by_p1 = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT: app_running = False; break
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: app_running = False; break
                elif the_game_state.game_over and event.key == pygame.K_RETURN: reset_requested_by_p1 = True; pass
                elif not the_game_state.game_over:
                    if event.key == pygame.K_e: local_p1_input['action_interact'] = True
                    if event.key == pygame.K_SPACE: local_p1_input['action_shoot'] = True
                    if event.key == pygame.K_r: local_p1_input['action_fireball'] = True
        if not the_game_state.game_over:
            keys = pygame.key.get_pressed()
            local_p1_input['keys'] = {'w': keys[pygame.K_w], 's': keys[pygame.K_s], 'a': keys[pygame.K_a], 'd': keys[pygame.K_d]}
        else: local_p1_input['keys'] = {}

        remote_p2_input_copy = {'keys': {}, 'action_interact': False, 'action_shoot': False, 'action_fireball': False}
        client_disconnected = False; reset_requested_by_p2 = False
        with client_lock:
            if client_input_buffer:
                if client_input_buffer.get("disconnect"): client_disconnected = True; client_input_buffer = {}; app_running = False
                elif the_game_state.game_over and client_input_buffer.get("action_reset", False): reset_requested_by_p2 = True; client_input_buffer = {}
                elif not the_game_state.game_over: remote_p2_input_copy = client_input_buffer.copy(); client_input_buffer = {}
        if client_disconnected: break

        if reset_requested_by_p2: the_game_state.reset()
        elif not the_game_state.game_over:
            try: the_game_state.update(local_p1_input, remote_p2_input_copy, current_time_ticks)
            except Exception as e: print(f"CRITICAL ERROR during game_state.update: {e}"); traceback.print_exc(); app_running = False; break

        if client_connection:
            network_state = the_game_state.get_network_state()
            encoded_state = encode_data(network_state)
            if encoded_state:
                try: client_connection.sendall(encoded_state + b'\n')
                except socket.error as e:
                    if app_running: print(f"Send failed (client likely disconnected): {e}")
                    with client_lock: client_input_buffer = {"disconnect": True}
                    app_running = False; break
            else: print("Error: Failed to encode network state. Cannot send.")

        screen.fill(BLACK)
        try: the_game_state.draw(screen, current_time_ticks)
        except Exception as e: print(f"CRITICAL ERROR during game_state.draw: {e}"); traceback.print_exc(); app_running = False; break
        pygame.display.flip(); clock.tick(60)

    print("Cleaning up server resources...")
    app_running = False
    temp_conn = None
    with client_lock:
        if client_connection: temp_conn = client_connection; client_connection = None
    if temp_conn:
         try: temp_conn.shutdown(socket.SHUT_RDWR)
         except (socket.error, OSError): pass
         try: temp_conn.close()
         except (socket.error, OSError): pass
    if server_tcp_socket: server_tcp_socket.close(); server_tcp_socket = None
    if broadcast_thread and broadcast_thread.is_alive(): broadcast_thread.join(timeout=1.0)
    if client_handler_thread and client_handler_thread.is_alive(): client_handler_thread.join(timeout=1.0)

def find_server(screen_surf, font_small_obj, font_large_obj):
    global app_running, clock
    print(f"Searching for server on LAN via UDP port {DISCOVERY_PORT_UDP}...")
    pygame.display.set_caption("Fence Game - Searching LAN...")
    search_text = font_large_obj.render("Searching for server on LAN...", True, WHITE)
    listen_socket = None
    found_server_ip, found_server_port = None, None

    try:
        listen_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_socket.bind(('', DISCOVERY_PORT_UDP))
        listen_socket.settimeout(0.5)
        print(f"Listening for broadcasts on UDP port {DISCOVERY_PORT_UDP}")
    except socket.error as e:
        print(f"Error binding UDP listen socket {DISCOVERY_PORT_UDP}: {e}")
        print("Check if another application (or another instance of this game) is already using this port.")
        screen_surf.fill(BLACK)
        err1 = font_small_obj.render(f"Error: Could not listen on UDP port {DISCOVERY_PORT_UDP}.", True, RED)
        err2 = font_small_obj.render("Another app using the port?", True, RED)
        screen_surf.blit(err1, err1.get_rect(center=(WIDTH//2, HEIGHT // 2 - 20)))
        screen_surf.blit(err2, err2.get_rect(center=(WIDTH//2, HEIGHT // 2 + 10)))
        pygame.display.flip(); time.sleep(4)
        return None, None

    start_time = time.time()
    my_ip = get_local_ip()

    while time.time() - start_time < CLIENT_SEARCH_TIMEOUT_S and app_running:
        for event in pygame.event.get():
             if event.type == pygame.QUIT: app_running = False; break
             if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: print("Search cancelled by user."); app_running = False; break
        if not app_running: break

        screen_surf.fill(BLACK)
        screen_surf.blit(search_text, search_text.get_rect(center=(WIDTH//2, HEIGHT//2)))
        pygame.display.flip(); clock.tick(10)

        try:
            data, addr = listen_socket.recvfrom(BUFFER_SIZE)
            if addr[0] == my_ip: continue

            message = decode_data(data)
            if (message and
                message.get("service") == SERVICE_NAME and
                isinstance(message.get("tcp_ip"), str) and
                isinstance(message.get("tcp_port"), int)):
                ip, port = message["tcp_ip"], message["tcp_port"]
                print(f"Found potential server: {ip}:{port} from {addr[0]}")
                found_server_ip, found_server_port = ip, port; break
        except socket.timeout: continue
        except socket.error as e: print(f"UDP Socket error during search: {e}"); time.sleep(0.1)
        except Exception as e: print(f"Error processing UDP broadcast: {e}")

    listen_socket.close()

    if not found_server_ip and app_running:
        print(f"No server found on LAN broadcasting '{SERVICE_NAME}' within {CLIENT_SEARCH_TIMEOUT_S}s.")
        screen_surf.fill(BLACK)
        fail_text_line1 = font_large_obj.render("Server not found!", True, RED)
        fail_text_line2 = font_small_obj.render("Ensure host is running and on the same LAN.", True, WHITE)
        screen_surf.blit(fail_text_line1, fail_text_line1.get_rect(center=(WIDTH//2, HEIGHT//2 - 30)))
        screen_surf.blit(fail_text_line2, fail_text_line2.get_rect(center=(WIDTH//2, HEIGHT//2 + 40)))
        pygame.display.flip()
        wait_start = time.time()
        while time.time() - wait_start < 3.0 and app_running:
             for event in pygame.event.get():
                 if event.type == pygame.QUIT: app_running = False
             if not app_running: break
             time.sleep(0.1)

    return found_server_ip, found_server_port

def get_server_id_input(screen_surf, font_prompt, font_input, font_info, clock_obj):
    global app_running, SCRAP_INITIALIZED, PYPERCLIP_AVAILABLE
    input_text = ""
    input_active = True
    cursor_visible = True
    last_cursor_toggle = time.time()
    input_rect = pygame.Rect(WIDTH // 4, HEIGHT // 2 - 10, WIDTH // 2, 50)

    print("Prompting user for Server IP Address (or IP:Port)...")
    pygame.key.set_repeat(500, 50)

    paste_info_msg = None
    paste_msg_start_time = 0

    while input_active and app_running:
        current_time = time.time()
        if current_time - last_cursor_toggle > 0.5: cursor_visible = not cursor_visible; last_cursor_toggle = current_time

        for event in pygame.event.get():
            if event.type == pygame.QUIT: app_running = False; input_active = False
            if event.type == pygame.KEYDOWN:
                paste_info_msg = None
                if event.key == pygame.K_ESCAPE: print("Input cancelled by user."); input_active = False; input_text = None
                elif event.key == pygame.K_RETURN:
                    if input_text.strip(): print(f"User entered Server ID: {input_text.strip()}"); input_active = False
                    else: print("User pressed Enter with empty input."); input_text = ""
                elif event.key == pygame.K_BACKSPACE: input_text = input_text[:-1]
                elif event.key == pygame.K_v and (event.mod & pygame.KMOD_CTRL or event.mod & pygame.KMOD_META):
                    pasted_content = None; paste_method_used = "None"
                    if SCRAP_INITIALIZED:
                        try:
                            clipboard_data = pygame.scrap.get(pygame.SCRAP_TEXT)
                            if clipboard_data:
                                cleaned_text = ""
                                if isinstance(clipboard_data, bytes):
                                    try: cleaned_text = clipboard_data.decode('utf-8', errors='ignore')
                                    except UnicodeDecodeError:
                                         try: cleaned_text = clipboard_data.decode('latin-1', errors='ignore')
                                         except: cleaned_text = ""
                                elif isinstance(clipboard_data, str): cleaned_text = clipboard_data
                                cleaned_text = cleaned_text.replace('\x00', '').strip()
                                if cleaned_text: pasted_content = cleaned_text; paste_method_used = "pygame.scrap"
                                else: print("pygame.scrap clipboard was empty/non-text after cleaning.")
                            else: print("pygame.scrap clipboard returned no data.")
                        except pygame.error as e: print(f"pygame.scrap paste failed: {e}")
                        except Exception as e: print(f"Unexpected error during pygame.scrap paste: {e}")
                    if pasted_content is None and PYPERCLIP_AVAILABLE:
                        try:
                            clipboard_text = pyperclip.paste()
                            if isinstance(clipboard_text, str):
                                cleaned_text = clipboard_text.replace('\x00', '').strip()
                                if cleaned_text: pasted_content = cleaned_text; paste_method_used = "pyperclip"
                                else: print("pyperclip paste result was empty/whitespace after cleaning.")
                            else: print("pyperclip paste did not return a string.")
                        except Exception as e: print(f"pyperclip paste failed: {e}")
                    if pasted_content is not None: input_text += pasted_content; print(f"Pasted using {paste_method_used}.")
                    elif SCRAP_INITIALIZED or PYPERCLIP_AVAILABLE: print("Paste failed or clipboard empty/unusable."); paste_info_msg = "Paste Failed / Empty"; paste_msg_start_time = current_time
                    else: print("Paste failed: No clipboard system available."); paste_info_msg = "Clipboard Unavailable"; paste_msg_start_time = current_time
                elif event.unicode.isalnum() or event.unicode in ['.', ':']: input_text += event.unicode

        screen_surf.fill(BLACK)
        prompt_surf = font_prompt.render("Enter Host IP Address or IP:Port", True, WHITE)
        prompt_rect = prompt_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 60))
        screen_surf.blit(prompt_surf, prompt_rect)

        info_surf = font_info.render("(Enter=Confirm, Esc=Cancel, Ctrl+V=Paste)", True, GREY)
        info_rect = info_surf.get_rect(center=(WIDTH // 2, HEIGHT - 40))
        screen_surf.blit(info_surf, info_rect)

        pygame.draw.rect(screen_surf, GREY, input_rect, border_radius=5)
        pygame.draw.rect(screen_surf, WHITE, input_rect, 2, border_radius=5)

        text_surf = font_input.render(input_text, True, BLACK)
        text_rect = text_surf.get_rect(midleft=(input_rect.left + 10, input_rect.centery))
        clip_area = input_rect.inflate(-12, -12)
        if text_rect.right > clip_area.right: text_rect.right = clip_area.right
        screen_surf.set_clip(clip_area)
        screen_surf.blit(text_surf, text_rect)
        screen_surf.set_clip(None)

        if cursor_visible:
            cursor_x = text_rect.right + 2
            if cursor_x < clip_area.left: cursor_x = clip_area.left + 2
            if cursor_x > clip_area.right: cursor_x = clip_area.right - 1
            cursor_y = input_rect.centery
            pygame.draw.line(screen_surf, BLACK, (cursor_x, cursor_y - 15), (cursor_x, cursor_y + 15), 2)

        if paste_info_msg and current_time - paste_msg_start_time < 2.0:
            msg_surf = font_info.render(paste_info_msg, True, RED if "Fail" in paste_info_msg else YELLOW)
            msg_rect = msg_surf.get_rect(center=(WIDTH // 2, input_rect.bottom + 30))
            screen_surf.blit(msg_surf, msg_rect)
        elif paste_info_msg: paste_info_msg = None

        pygame.display.flip(); clock_obj.tick(30)

    pygame.key.set_repeat(0, 0)
    return input_text.strip() if input_text is not None else None

def run_client_mode(target_ip_port=None):
    global app_running, screen, clock, font_small, font_large, client_tcp_socket

    try: the_game_state = game_state.GameState()
    except Exception as e: print(f"FATAL: Failed to initialize GameState on client: {e}"); app_running = False; return

    server_ip_connect = None
    server_port_connect = SERVER_PORT_TCP

    if target_ip_port:
        print(f"Attempting direct connection to: {target_ip_port}")
        if ':' in target_ip_port:
             parts = target_ip_port.rsplit(':', 1); ip_part = parts[0]; port_part = parts[1]
             try:
                 port_num = int(port_part)
                 if 0 < port_num < 65536: server_ip_connect = ip_part; server_port_connect = port_num; print(f"Parsed IP: {server_ip_connect}, Port: {server_port_connect}")
                 else: print(f"Warning: Invalid port number '{port_part}' in input. Using default {SERVER_PORT_TCP}."); server_ip_connect = ip_part
             except ValueError: print(f"Warning: Could not parse port from '{port_part}'. Assuming input is just IP."); server_ip_connect = target_ip_port
        else: server_ip_connect = target_ip_port
    else:
        pygame.display.set_caption("Fence Game - Searching LAN...")
        server_ip_connect, found_port = find_server(screen, font_small, font_large)
        if found_port: server_port_connect = found_port

    if not server_ip_connect:
        if app_running: print("Exiting client mode (no server address).")
        return
    if not app_running: print("Exiting client mode (app closed during search/input)."); return

    client_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    connection_successful = False; error_message = "Unknown Error"
    try:
        print(f"Attempting TCP connection to {server_ip_connect}:{server_port_connect}...")
        pygame.display.set_caption(f"Fence Game - Connecting...")
        screen.fill(BLACK)
        conn_text = font_large.render(f"Connecting to Host...", True, WHITE)
        conn_details = font_small.render(f"({server_ip_connect}:{server_port_connect})", True, GREY)
        screen.blit(conn_text, conn_text.get_rect(center=(WIDTH//2, HEIGHT//2 - 20)))
        screen.blit(conn_details, conn_details.get_rect(center=(WIDTH//2, HEIGHT//2 + 30)))
        pygame.display.flip()
        client_tcp_socket.settimeout(10.0)
        client_tcp_socket.connect((server_ip_connect, server_port_connect))
        client_tcp_socket.settimeout(5.0); print("TCP Connection successful!"); connection_successful = True
    except socket.gaierror as e: print(f"Connection Error: Address-related error - {e}"); error_message = f"Invalid Address or Hostname!"
    except socket.timeout: print(f"Connection Error: Connection timed out."); error_message = f"Connection Timed Out!"
    except socket.error as e: print(f"Connection Error: {e}"); error_message = f"Connection Failed! ({e.strerror})"
    except Exception as e: print(f"Unexpected Connection Error: {e}"); error_message = "An Unexpected Error Occurred!"

    if not connection_successful:
        screen.fill(BLACK)
        fail_text1 = font_large.render(f"Connection Failed", True, RED)
        fail_text2 = font_small.render(error_message, True, WHITE)
        fail_text3 = font_small.render(f"Host: {server_ip_connect}:{server_port_connect}", True, GREY)
        screen.blit(fail_text1, fail_text1.get_rect(center=(WIDTH//2, HEIGHT//2 - 50)))
        screen.blit(fail_text2, fail_text2.get_rect(center=(WIDTH//2, HEIGHT//2 + 0)))
        screen.blit(fail_text3, fail_text3.get_rect(center=(WIDTH//2, HEIGHT//2 + 40)))
        pygame.display.flip(); time.sleep(4)
        if client_tcp_socket: client_tcp_socket.close(); client_tcp_socket = None
        return

    pygame.display.set_caption("Fence Game - CLIENT (Player 2 - Red)")
    last_received_state = None
    partial_data = b""

    while app_running:
        current_time_ticks = pygame.time.get_ticks()
        local_p2_input = {'keys': {}, 'action_interact': False, 'action_shoot': False, 'action_fireball': False, 'action_reset': False}
        is_game_over_locally = the_game_state.game_over

        for event in pygame.event.get():
            if event.type == pygame.QUIT: app_running = False; break
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: app_running = False; break
                elif is_game_over_locally and event.key == pygame.K_RETURN: print("Sending reset request to server..."); local_p2_input['action_reset'] = True; continue
                elif not is_game_over_locally:
                    if event.key == pygame.K_e: local_p2_input['action_interact'] = True
                    if event.key == pygame.K_SPACE: local_p2_input['action_shoot'] = True
                    if event.key == pygame.K_r: local_p2_input['action_fireball'] = True

        if not is_game_over_locally and not local_p2_input['action_reset']:
            keys = pygame.key.get_pressed()
            local_p2_input['keys'] = {'w': keys[pygame.K_w], 's': keys[pygame.K_s], 'a': keys[pygame.K_a], 'd': keys[pygame.K_d]}
        else: local_p2_input['keys'] = {}

        if client_tcp_socket:
            client_input_data = {"input": local_p2_input}
            encoded_input = encode_data(client_input_data)
            if encoded_input:
                try: client_tcp_socket.sendall(encoded_input + b'\n')
                except socket.error as e:
                    if app_running: print(f"Send failed (server disconnected?): {e}")
                    app_running = False; break
            else: print("Error: Failed to encode client input. Cannot send.")

        received_new_state_this_frame = False
        if client_tcp_socket:
            try:
                chunk = client_tcp_socket.recv(BUFFER_SIZE)
                if not chunk:
                    if app_running: print("Server disconnected (received empty data).")
                    app_running = False; break
                partial_data += chunk
                processed_a_message = False
                while b'\n' in partial_data:
                    message, partial_data = partial_data.split(b'\n', 1)
                    if not message: continue
                    decoded_state = decode_data(message)
                    if decoded_state:
                        last_received_state = decoded_state
                        received_new_state_this_frame = True
                        processed_a_message = True
            except socket.timeout: pass
            except socket.error as e:
                if app_running: print(f"Receive error (server disconnected?): {e}")
                app_running = False; break
            except Exception as e:
                if app_running: print(f"Error processing data from server: {e}")
                app_running = False; break
        else:
             if app_running: print("Error: Client socket is None in game loop.")
             app_running = False; break

        if last_received_state:
             try: the_game_state.set_network_state(last_received_state)
             except Exception as e:
                 print(f"CRITICAL: Error applying network state: {e}")
                 print(f"Problematic state data: {str(last_received_state)[:500]}")
                 traceback.print_exc(); app_running = False; break

        screen.fill(BLACK)
        try: the_game_state.draw(screen, current_time_ticks)
        except Exception as e: print(f"CRITICAL ERROR during client game_state.draw: {e}"); traceback.print_exc(); app_running = False; break
        pygame.display.flip(); clock.tick(60)

    print("Cleaning up client resources...")
    if client_tcp_socket:
        try: client_tcp_socket.shutdown(socket.SHUT_RDWR)
        except (socket.error, OSError): pass
        try: client_tcp_socket.close()
        except (socket.error, OSError): pass
        client_tcp_socket = None

def show_menu():
    global screen, clock, font_small, font_large, app_running
    button_width, button_height, spacing = 280, 55, 25
    total_height = 3 * button_height + 2 * spacing
    start_y = (HEIGHT - total_height) // 2 + 20

    host_rect = pygame.Rect((WIDTH - button_width) // 2, start_y, button_width, button_height)
    join_lan_rect = pygame.Rect((WIDTH - button_width) // 2, start_y + button_height + spacing, button_width, button_height)
    join_internet_rect = pygame.Rect((WIDTH - button_width) // 2, start_y + 2 * (button_height + spacing), button_width, button_height)

    title_color = WHITE; button_text_color = WHITE; button_color = BLUE; button_hover_color = GREEN

    title = font_large.render("Fence Game Online", True, title_color)
    title_rect = title.get_rect(center=(WIDTH // 2, HEIGHT // 4))
    host_text = font_medium.render("Host Game", True, button_text_color)
    host_text_rect = host_text.get_rect(center=host_rect.center)
    join_lan_text = font_medium.render("Join Game (LAN)", True, button_text_color)
    join_lan_text_rect = join_lan_text.get_rect(center=join_lan_rect.center)
    join_internet_text = font_medium.render("Join Game (Internet)", True, button_text_color)
    join_internet_text_rect = join_internet_text.get_rect(center=join_internet_rect.center)

    selected_option = None
    while selected_option is None and app_running:
        mouse_pos = pygame.mouse.get_pos()
        host_hover = host_rect.collidepoint(mouse_pos)
        join_lan_hover = join_lan_rect.collidepoint(mouse_pos)
        join_internet_hover = join_internet_rect.collidepoint(mouse_pos)

        for event in pygame.event.get():
            if event.type == pygame.QUIT: app_running = False; selected_option = "quit"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: app_running = False; selected_option = "quit"
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if host_hover: selected_option = "host"
                elif join_lan_hover: selected_option = "join_lan"
                elif join_internet_hover: selected_option = "join_internet"

        screen.fill(BLACK)
        screen.blit(title, title_rect)
        pygame.draw.rect(screen, button_hover_color if host_hover else button_color, host_rect, border_radius=8)
        screen.blit(host_text, host_text_rect)
        pygame.draw.rect(screen, button_hover_color if join_lan_hover else button_color, join_lan_rect, border_radius=8)
        screen.blit(join_lan_text, join_lan_text_rect)
        pygame.draw.rect(screen, button_hover_color if join_internet_hover else button_color, join_internet_rect, border_radius=8)
        screen.blit(join_internet_text, join_internet_text_rect)
        pygame.display.flip(); clock.tick(30)

    return selected_option

if __name__ == "__main__":
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Fence Game Online")
    clock = pygame.time.Clock()
    try:
        font_small = pygame.font.Font(None, 28)
        font_medium = pygame.font.Font(None, 36)
        font_large = pygame.font.Font(None, 72)
    except Exception as e:
         print(f"FATAL: Font loading error: {e}"); print("Please ensure default pygame fonts are available."); pygame.quit(); sys.exit(1)

    menu_choice = show_menu()

    if menu_choice == "host": run_server_mode()
    elif menu_choice == "join_lan": run_client_mode()
    elif menu_choice == "join_internet":
        target_server_ip_port = get_server_id_input(screen, font_medium, font_medium, font_small, clock)
        if target_server_ip_port and app_running: run_client_mode(target_ip_port=target_server_ip_port)
        elif app_running: print("Join Internet cancelled or no IP entered.")
    elif menu_choice == "quit": print("Quit selected from menu.")
    else: print("No valid menu option selected.")

    print("Exiting application.")
    pygame.quit()
    try:
        if SCRAP_INITIALIZED and pygame.scrap.get_init(): pygame.scrap.quit(); print("Pygame scrap module quit.")
    except AttributeError: pass
    except pygame.error as e: print(f"Error quitting scrap module: {e}")
    except Exception as e: print(f"Unexpected error quitting scrap module: {e}")

    sys.exit(0)