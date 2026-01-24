# ============================================================
# Universal Utility Hotkeys v2.0
# by Coryigon for UO Unchained
# ============================================================
#
# Quick access to common UO commands via GUI buttons and hotkeys.
# Collapsible interface keeps your screen clean when not in use.
#
# Features:
#   - Housing commands (Secure, Lock Down, Release)
#   - Customizable hotkeys via config panel
#   - Expand/collapse to save screen space
#   - Visual feedback during command execution
#   - [C] button to configure hotkeys
#
# Default Hotkeys:
#   CTRL+1 = Secure item
#   CTRL+2 = Lock down item
#   CTRL+3 = Release item
#
# v2.0 Changes:
#   - FIXED: Release command now says "I wish to release this" (was broken)
#   - Added [C] config button with collapsible hotkey panel
#   - Customizable hotkeys (click button in config to rebind)
#   - Dynamic window sizing (155px normal, 190px config)
#   - Increased font sizes for readability (11pt labels)
#   - Integrated hotkey display on command buttons [CMD: key]
#   - Applied UI_STANDARDS.md patterns
#
# ============================================================
import API
import time

__version__ = "2.0"

# ============ USER SETTINGS ============
TARGET_TIMEOUT = 5.0  # Seconds to wait for target cursor
# =======================================

# ============ CONSTANTS ============
SETTINGS_KEY = "UtilHotkeys"

# Command definitions
COMMANDS = {
    "secure": {
        "phrase": "I wish to secure this",
        "label": "Secure",
        "description": "Secure an item in your house"
    },
    "lockdown": {
        "phrase": "I wish to lock this down",
        "label": "Lock Down",
        "description": "Lock down an item in your house"
    },
    "release": {
        "phrase": "I wish to release this",  # FIXED: Was "I release this"
        "label": "Release",
        "description": "Release a secured/locked item"
    }
}

# Window dimensions
WINDOW_WIDTH_NORMAL = 155
WINDOW_WIDTH_CONFIG = 190
COLLAPSED_HEIGHT = 24
NORMAL_HEIGHT = 130  # 3 buttons + status
CONFIG_HEIGHT = 230  # normal + config panel (~100px)

# Button dimensions
CMD_BTN_WIDTH = 145  # Command buttons (wide for integrated hotkey display)
CMD_BTN_HEIGHT = 24
CONFIG_BTN_WIDTH = 85  # Config panel buttons

# Color hues
HUE_NORMAL = 68      # Green
HUE_EXECUTING = 43   # Yellow
HUE_ERROR = 32       # Red
HUE_LISTENING = 38   # Purple

# ============ PERSISTENCE KEYS ============
SECURE_HOTKEY_KEY = "UtilHotkeys_SecureHotkey"
LOCKDOWN_HOTKEY_KEY = "UtilHotkeys_LockdownHotkey"
RELEASE_HOTKEY_KEY = "UtilHotkeys_ReleaseHotkey"

# ============ RUNTIME STATE ============
is_expanded = True
show_config = False
executing_command = None
listening_for_cmd = None  # "secure", "lockdown", "release", or None

# Runtime hotkey bindings (customizable)
hotkey_bindings = {
    "secure": "CTRL+1",
    "lockdown": "CTRL+2",
    "release": "CTRL+3"
}

# GUI element references
command_buttons = {}
last_known_x = 100
last_known_y = 100
last_position_check = 0

# All keys we can capture
ALL_KEYS = [
    # Simple keys - Function keys
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",

    # Simple keys - Letters
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
    "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",

    # Simple keys - Numbers
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",

    # Simple keys - Numpad
    "NUMPAD0", "NUMPAD1", "NUMPAD2", "NUMPAD3", "NUMPAD4",
    "NUMPAD5", "NUMPAD6", "NUMPAD7", "NUMPAD8", "NUMPAD9",

    # Simple keys - Special
    "TAB", "SPACE", "ENTER", "ESC", "PAUSE", "BACKSPACE",
    "HOME", "END", "PAGEUP", "PAGEDOWN", "INSERT", "DELETE",
    "LEFT", "RIGHT", "UP", "DOWN",
    "MULTIPLY", "ADD", "SUBTRACT", "DIVIDE", "DECIMAL",

    # CTRL+ combinations - Numbers (most common)
    "CTRL+1", "CTRL+2", "CTRL+3", "CTRL+4", "CTRL+5",
    "CTRL+6", "CTRL+7", "CTRL+8", "CTRL+9", "CTRL+0",

    # CTRL+ combinations - Function keys
    "CTRL+F1", "CTRL+F2", "CTRL+F3", "CTRL+F4", "CTRL+F5", "CTRL+F6",
    "CTRL+F7", "CTRL+F8", "CTRL+F9", "CTRL+F10", "CTRL+F11", "CTRL+F12",

    # CTRL+ combinations - Letters
    "CTRL+A", "CTRL+B", "CTRL+C", "CTRL+D", "CTRL+E", "CTRL+F", "CTRL+G",
    "CTRL+H", "CTRL+I", "CTRL+J", "CTRL+K", "CTRL+L", "CTRL+M", "CTRL+N",
    "CTRL+O", "CTRL+P", "CTRL+Q", "CTRL+R", "CTRL+S", "CTRL+T", "CTRL+U",
    "CTRL+V", "CTRL+W", "CTRL+X", "CTRL+Y", "CTRL+Z",

    # SHIFT+ combinations - Function keys (less common but useful)
    "SHIFT+F1", "SHIFT+F2", "SHIFT+F3", "SHIFT+F4", "SHIFT+F5", "SHIFT+F6",
    "SHIFT+F7", "SHIFT+F8", "SHIFT+F9", "SHIFT+F10", "SHIFT+F11", "SHIFT+F12",
]

# ============ UTILITY FUNCTIONS ============
def format_hotkey_display(hotkey):
    """Format hotkey for display on button"""
    return hotkey.replace("CTRL+", "^").replace("SHIFT+", "@")

# ============ CORE LOGIC ============
def execute_command(cmd_key):
    """Execute a utility command"""
    global executing_command

    if cmd_key not in COMMANDS:
        API.SysMsg("Unknown command: " + cmd_key, HUE_ERROR)
        return

    if executing_command:
        API.SysMsg("Command already executing, please wait", HUE_ERROR)
        return

    cmd = COMMANDS[cmd_key]
    executing_command = cmd_key

    # Update UI to show execution
    if cmd_key in command_buttons:
        btn = command_buttons[cmd_key]
        btn.SetBackgroundHue(HUE_EXECUTING)

    update_status("Executing " + cmd["label"] + "...", HUE_EXECUTING)

    try:
        # Say the command phrase
        API.Msg(cmd["phrase"])

        # Request target
        update_status("Target item...", HUE_EXECUTING)
        target = API.RequestTarget(timeout=TARGET_TIMEOUT)

        if not target:
            API.SysMsg("Command cancelled (no target)", HUE_ERROR)
            update_status("Ready", 68)
        else:
            API.SysMsg(cmd["label"] + " command sent", 68)
            update_status("Ready", 68)

    except Exception as e:
        API.SysMsg("Error: " + str(e), HUE_ERROR)
        update_status("Error - Ready", HUE_ERROR)

    finally:
        # Reset button color
        if cmd_key in command_buttons:
            btn = command_buttons[cmd_key]
            btn.SetBackgroundHue(HUE_NORMAL)
        executing_command = None

def update_status(text, color_hue):
    """Update status label text"""
    if is_expanded:
        statusLabel.SetText(text)

# ============ HOTKEY SYSTEM ============
def make_key_handler(key_name):
    """Create a callback for a specific key"""
    def handler():
        global listening_for_cmd

        # If we're listening for a key assignment
        if listening_for_cmd is not None:
            # ESC cancels listening
            if key_name == "ESC":
                API.SysMsg("Hotkey capture cancelled", 90)
                listening_for_cmd = None
                update_config_buttons()
                return

            # Assign the key
            cmd_name = listening_for_cmd  # Store before clearing
            hotkey_bindings[listening_for_cmd] = key_name
            save_hotkey_binding(listening_for_cmd, key_name)
            listening_for_cmd = None  # Clear BEFORE updating buttons

            update_config_buttons()
            update_command_buttons()

            API.SysMsg(cmd_name.title() + " bound to: " + key_name, 68)
            return

        # Not listening - execute command if this key is bound
        for cmd_key, bound_key in hotkey_bindings.items():
            if bound_key == key_name:
                execute_command(cmd_key)
                return

    return handler

def start_capture_secure():
    """Start listening for secure hotkey"""
    global listening_for_cmd
    listening_for_cmd = "secure"
    secureHkBtn.SetBackgroundHue(HUE_LISTENING)
    secureHkBtn.SetText("[Listening...]")
    API.SysMsg("Press any key to bind to Secure...", HUE_LISTENING)

def start_capture_lockdown():
    """Start listening for lockdown hotkey"""
    global listening_for_cmd
    listening_for_cmd = "lockdown"
    lockdownHkBtn.SetBackgroundHue(HUE_LISTENING)
    lockdownHkBtn.SetText("[Listening...]")
    API.SysMsg("Press any key to bind to Lock Down...", HUE_LISTENING)

def start_capture_release():
    """Start listening for release hotkey"""
    global listening_for_cmd
    listening_for_cmd = "release"
    releaseHkBtn.SetBackgroundHue(HUE_LISTENING)
    releaseHkBtn.SetText("[Listening...]")
    API.SysMsg("Press any key to bind to Release...", HUE_LISTENING)

# ============ GUI CALLBACKS ============
def toggle_config():
    """Toggle config panel visibility"""
    if show_config:
        hide_config_panel()
    else:
        show_config_panel()

def show_config_panel():
    """Show config panel and expand window width"""
    global show_config
    show_config = True

    # Show config elements
    configBg.IsVisible = True
    secureHkLabel.IsVisible = True
    secureHkBtn.IsVisible = True
    lockdownHkLabel.IsVisible = True
    lockdownHkBtn.IsVisible = True
    releaseHkLabel.IsVisible = True
    releaseHkBtn.IsVisible = True
    configDoneBtn.IsVisible = True
    configHelpLabel.IsVisible = True

    # Update config button
    configBtn.SetBackgroundHue(68)  # Green when active

    # Reposition title buttons
    configBtn.SetPos(105, 3)
    expandBtn.SetPos(130, 3)

    # Resize window
    if is_expanded:
        gump.SetRect(gump.GetX(), gump.GetY(), WINDOW_WIDTH_CONFIG, CONFIG_HEIGHT)
        bg.SetRect(0, 0, WINDOW_WIDTH_CONFIG, CONFIG_HEIGHT)
    else:
        # Collapsed mode
        gump.SetRect(gump.GetX(), gump.GetY(), WINDOW_WIDTH_CONFIG, COLLAPSED_HEIGHT)
        bg.SetRect(0, 0, WINDOW_WIDTH_CONFIG, COLLAPSED_HEIGHT)

def hide_config_panel():
    """Hide config panel and shrink window width"""
    global show_config, listening_for_cmd
    show_config = False
    listening_for_cmd = None  # Cancel any pending capture

    # Hide config elements
    configBg.IsVisible = False
    secureHkLabel.IsVisible = False
    secureHkBtn.IsVisible = False
    lockdownHkLabel.IsVisible = False
    lockdownHkBtn.IsVisible = False
    releaseHkLabel.IsVisible = False
    releaseHkBtn.IsVisible = False
    configDoneBtn.IsVisible = False
    configHelpLabel.IsVisible = False

    # Update config button
    configBtn.SetBackgroundHue(90)  # Gray when inactive

    # Reposition title buttons
    configBtn.SetPos(105, 3)
    expandBtn.SetPos(130, 3)

    # Resize window
    if is_expanded:
        gump.SetRect(gump.GetX(), gump.GetY(), WINDOW_WIDTH_NORMAL, NORMAL_HEIGHT)
        bg.SetRect(0, 0, WINDOW_WIDTH_NORMAL, NORMAL_HEIGHT)
    else:
        # Collapsed mode
        gump.SetRect(gump.GetX(), gump.GetY(), WINDOW_WIDTH_NORMAL, COLLAPSED_HEIGHT)
        bg.SetRect(0, 0, WINDOW_WIDTH_NORMAL, COLLAPSED_HEIGHT)

def toggle_expand():
    """Toggle between collapsed and expanded states"""
    global is_expanded

    is_expanded = not is_expanded
    save_expanded_state()

    if is_expanded:
        expand_window()
    else:
        collapse_window()

def expand_window():
    """Show all controls and resize window"""
    expandBtn.SetText("[-]")

    # Show all command buttons
    for btn in command_buttons.values():
        btn.IsVisible = True

    statusLabel.IsVisible = True

    # Resize gump
    x = gump.GetX()
    y = gump.GetY()

    # Choose dimensions based on config panel state
    if show_config:
        gump.SetRect(x, y, WINDOW_WIDTH_CONFIG, CONFIG_HEIGHT)
        bg.SetRect(0, 0, WINDOW_WIDTH_CONFIG, CONFIG_HEIGHT)
    else:
        gump.SetRect(x, y, WINDOW_WIDTH_NORMAL, NORMAL_HEIGHT)
        bg.SetRect(0, 0, WINDOW_WIDTH_NORMAL, NORMAL_HEIGHT)

def collapse_window():
    """Hide all controls and shrink window"""
    expandBtn.SetText("[+]")

    # Hide all command buttons
    for btn in command_buttons.values():
        btn.IsVisible = False

    statusLabel.IsVisible = False

    # Resize gump
    x = gump.GetX()
    y = gump.GetY()

    # Choose width based on config panel state
    width = WINDOW_WIDTH_CONFIG if show_config else WINDOW_WIDTH_NORMAL
    gump.SetRect(x, y, width, COLLAPSED_HEIGHT)
    bg.SetRect(0, 0, width, COLLAPSED_HEIGHT)

# ============ COMMAND BUTTON FACTORIES ============
def make_command_executor(cmd_key):
    """Factory function to create command executor callbacks"""
    def executor():
        execute_command(cmd_key)
    return executor

# ============ DISPLAY UPDATES ============
def update_command_buttons():
    """Update command button labels with current hotkeys"""
    try:
        for cmd_key, btn in command_buttons.items():
            cmd = COMMANDS[cmd_key]
            hotkey = hotkey_bindings.get(cmd_key, "---")
            hotkey_display = format_hotkey_display(hotkey)
            btn.SetText(cmd["label"] + ": " + hotkey_display)
    except Exception as e:
        API.SysMsg("Error updating buttons: " + str(e), 32)

def update_config_buttons():
    """Update config panel hotkey buttons"""
    try:
        # Secure
        if listening_for_cmd == "secure":
            secureHkBtn.SetText("[Listening...]")
            secureHkBtn.SetBackgroundHue(HUE_LISTENING)
        else:
            hotkey = hotkey_bindings.get("secure", "---")
            secureHkBtn.SetText("[" + format_hotkey_display(hotkey) + "]")
            secureHkBtn.SetBackgroundHue(68 if hotkey != "---" else 90)

        # Lockdown
        if listening_for_cmd == "lockdown":
            lockdownHkBtn.SetText("[Listening...]")
            lockdownHkBtn.SetBackgroundHue(HUE_LISTENING)
        else:
            hotkey = hotkey_bindings.get("lockdown", "---")
            lockdownHkBtn.SetText("[" + format_hotkey_display(hotkey) + "]")
            lockdownHkBtn.SetBackgroundHue(68 if hotkey != "---" else 90)

        # Release
        if listening_for_cmd == "release":
            releaseHkBtn.SetText("[Listening...]")
            releaseHkBtn.SetBackgroundHue(HUE_LISTENING)
        else:
            hotkey = hotkey_bindings.get("release", "---")
            releaseHkBtn.SetText("[" + format_hotkey_display(hotkey) + "]")
            releaseHkBtn.SetBackgroundHue(68 if hotkey != "---" else 90)
    except Exception as e:
        API.SysMsg("Error updating config buttons: " + str(e), 32)

# ============ PERSISTENCE ============
def save_window_position():
    """Save window position to persistence using last known position"""
    global last_known_x, last_known_y

    # Validate coordinates
    if last_known_x < 0 or last_known_y < 0:
        return

    pos = str(last_known_x) + "," + str(last_known_y)
    API.SavePersistentVar(SETTINGS_KEY + "_XY", pos, API.PersistentVar.Char)

def load_window_position():
    """Load window position from persistence"""
    global last_known_x, last_known_y

    saved = API.GetPersistentVar(SETTINGS_KEY + "_XY", "100,100", API.PersistentVar.Char)
    parts = saved.split(',')
    x = int(parts[0])
    y = int(parts[1])

    # Update last known position with loaded values
    last_known_x = x
    last_known_y = y

    return x, y

def save_expanded_state():
    """Save expanded state to persistence"""
    API.SavePersistentVar(SETTINGS_KEY + "_Expanded", str(is_expanded), API.PersistentVar.Char)

def load_expanded_state():
    """Load expanded state from persistence"""
    global is_expanded
    saved = API.GetPersistentVar(SETTINGS_KEY + "_Expanded", "True", API.PersistentVar.Char)
    is_expanded = (saved == "True")

def save_hotkey_binding(cmd_key, hotkey):
    """Save a single hotkey binding"""
    if cmd_key == "secure":
        API.SavePersistentVar(SECURE_HOTKEY_KEY, hotkey, API.PersistentVar.Char)
    elif cmd_key == "lockdown":
        API.SavePersistentVar(LOCKDOWN_HOTKEY_KEY, hotkey, API.PersistentVar.Char)
    elif cmd_key == "release":
        API.SavePersistentVar(RELEASE_HOTKEY_KEY, hotkey, API.PersistentVar.Char)

def load_hotkey_bindings():
    """Load all hotkey bindings from persistence"""
    global hotkey_bindings
    hotkey_bindings["secure"] = API.GetPersistentVar(SECURE_HOTKEY_KEY, "CTRL+1", API.PersistentVar.Char)
    hotkey_bindings["lockdown"] = API.GetPersistentVar(LOCKDOWN_HOTKEY_KEY, "CTRL+2", API.PersistentVar.Char)
    hotkey_bindings["release"] = API.GetPersistentVar(RELEASE_HOTKEY_KEY, "CTRL+3", API.PersistentVar.Char)

# ============ CLEANUP ============
def cleanup():
    """Unregister hotkeys and cancel any pending target"""
    # Cancel any pending target cursor
    if API.HasTarget():
        API.CancelTarget()

def on_closed():
    """Handle window close event"""
    save_window_position()
    cleanup()
    API.Stop()

def stop_script():
    """Manual stop via button"""
    save_window_position()
    cleanup()
    gump.Dispose()
    API.Stop()

# ============ INITIALIZATION ============
load_expanded_state()
load_hotkey_bindings()

# ============ BUILD GUI ============
gump = API.Gumps.CreateGump()
API.Gumps.AddControlOnDisposed(gump, on_closed)

# Load saved position
x, y = load_window_position()
initial_height = NORMAL_HEIGHT if is_expanded else COLLAPSED_HEIGHT
gump.SetRect(x, y, WINDOW_WIDTH_NORMAL, initial_height)

# Background
bg = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
bg.SetRect(0, 0, WINDOW_WIDTH_NORMAL, initial_height)
gump.Add(bg)

# Title bar
title = API.Gumps.CreateGumpTTFLabel("Util Hotkeys", 16, "#00d4ff")
title.SetPos(5, 2)
gump.Add(title)

# Config button [C]
configBtn = API.Gumps.CreateSimpleButton("[C]", 20, 18)
configBtn.SetPos(105, 3)
configBtn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(configBtn, toggle_config)
gump.Add(configBtn)

# Expand/collapse button
expandBtn = API.Gumps.CreateSimpleButton("[-]" if is_expanded else "[+]", 20, 18)
expandBtn.SetPos(130, 3)
expandBtn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(expandBtn, toggle_expand)
gump.Add(expandBtn)

# Command buttons
y_pos = 26

for cmd_key in ["secure", "lockdown", "release"]:
    cmd = COMMANDS[cmd_key]
    hotkey = hotkey_bindings.get(cmd_key, "---")
    hotkey_display = format_hotkey_display(hotkey)

    # Create command button with integrated hotkey display
    btn = API.Gumps.CreateSimpleButton(cmd["label"] + ": " + hotkey_display, CMD_BTN_WIDTH, CMD_BTN_HEIGHT)
    btn.SetPos(5, y_pos)
    btn.SetBackgroundHue(HUE_NORMAL)
    btn.IsVisible = is_expanded
    API.Gumps.AddControlOnClick(btn, make_command_executor(cmd_key))
    gump.Add(btn)
    command_buttons[cmd_key] = btn

    y_pos += 28

# Status label at bottom
statusLabel = API.Gumps.CreateGumpTTFLabel("Ready", 11, "#00ff00")  # Increased from 9pt
statusLabel.SetPos(5, y_pos + 5)
statusLabel.IsVisible = is_expanded
gump.Add(statusLabel)

# ============ CONFIG PANEL ============
config_y = NORMAL_HEIGHT

# Config background
configBg = API.Gumps.CreateGumpColorBox(0.8, "#2a2a3e")
configBg.SetRect(0, config_y, WINDOW_WIDTH_CONFIG, 100)
configBg.IsVisible = False
gump.Add(configBg)

# Help label
configHelpLabel = API.Gumps.CreateGumpTTFLabel("Click hotkey button, press key to bind", 8, "#888888")
configHelpLabel.SetPos(5, config_y + 3)
configHelpLabel.IsVisible = False
gump.Add(configHelpLabel)

config_y += 20

# Secure hotkey row
secureHkLabel = API.Gumps.CreateGumpTTFLabel("Secure:", 11, "#aaaaaa")
secureHkLabel.SetPos(5, config_y + 3)
secureHkLabel.IsVisible = False
gump.Add(secureHkLabel)

secureHkBtn = API.Gumps.CreateSimpleButton("[^1]", CONFIG_BTN_WIDTH, 20)
secureHkBtn.SetPos(55, config_y)
secureHkBtn.SetBackgroundHue(68)
secureHkBtn.IsVisible = False
API.Gumps.AddControlOnClick(secureHkBtn, start_capture_secure)
gump.Add(secureHkBtn)

config_y += 24

# Lockdown hotkey row
lockdownHkLabel = API.Gumps.CreateGumpTTFLabel("Lockdown:", 11, "#aaaaaa")
lockdownHkLabel.SetPos(5, config_y + 3)
lockdownHkLabel.IsVisible = False
gump.Add(lockdownHkLabel)

lockdownHkBtn = API.Gumps.CreateSimpleButton("[^2]", CONFIG_BTN_WIDTH, 20)
lockdownHkBtn.SetPos(55, config_y)
lockdownHkBtn.SetBackgroundHue(68)
lockdownHkBtn.IsVisible = False
API.Gumps.AddControlOnClick(lockdownHkBtn, start_capture_lockdown)
gump.Add(lockdownHkBtn)

config_y += 24

# Release hotkey row
releaseHkLabel = API.Gumps.CreateGumpTTFLabel("Release:", 11, "#aaaaaa")
releaseHkLabel.SetPos(5, config_y + 3)
releaseHkLabel.IsVisible = False
gump.Add(releaseHkLabel)

releaseHkBtn = API.Gumps.CreateSimpleButton("[^3]", CONFIG_BTN_WIDTH, 20)
releaseHkBtn.SetPos(55, config_y)
releaseHkBtn.SetBackgroundHue(68)
releaseHkBtn.IsVisible = False
API.Gumps.AddControlOnClick(releaseHkBtn, start_capture_release)
gump.Add(releaseHkBtn)

config_y += 28

# Done button
configDoneBtn = API.Gumps.CreateSimpleButton("[DONE]", 130, 20)
configDoneBtn.SetPos(30, config_y)
configDoneBtn.SetBackgroundHue(90)
configDoneBtn.IsVisible = False
API.Gumps.AddControlOnClick(configDoneBtn, hide_config_panel)
gump.Add(configDoneBtn)

# Update config buttons with loaded values
update_config_buttons()

API.Gumps.AddGump(gump)

# ============ REGISTER HOTKEYS ============
API.SysMsg("Registering key handlers...", 53)

registered_count = 0
for key in ALL_KEYS:
    try:
        API.OnHotKey(key, make_key_handler(key))
        registered_count += 1
    except Exception as e:
        # Skip keys that don't work
        pass

API.SysMsg("Registered " + str(registered_count) + " keys", 68)

# ============ STARTUP MESSAGE ============
API.SysMsg("=== Utility Hotkeys v2.0 ===", 68)
API.SysMsg("CTRL+1=Secure, CTRL+2=Lock, CTRL+3=Release", 53)
API.SysMsg("Click [C] to customize hotkeys", 53)

# ============ MAIN LOOP ============
while not API.StopRequested:
    try:
        API.ProcessCallbacks()  # Process hotkeys and GUI events

        # Periodically update last known position (every 2 seconds)
        if not API.StopRequested:
            current_time = time.time()
            if current_time - last_position_check > 2.0:
                last_position_check = current_time
                try:
                    last_known_x = gump.GetX()
                    last_known_y = gump.GetY()
                except:
                    pass  # Silently ignore if gump is disposed

        API.Pause(0.1)
    except Exception as e:
        # Don't show "operation canceled" errors during shutdown
        if "operation canceled" not in str(e).lower() and not API.StopRequested:
            API.SysMsg("Error in main loop: " + str(e), 32)
        API.Pause(1)
