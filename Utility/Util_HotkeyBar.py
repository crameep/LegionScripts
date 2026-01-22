# ============================================================
# Universal Utility Hotkeys v1.0
# by Coryigon for UO Unchained
# ============================================================
#
# Quick access to common UO commands via GUI buttons and hotkeys.
# Collapsible interface keeps your screen clean when not in use.
#
# Features:
#   - Housing commands (Secure, Lock Down, Release)
#   - Expand/collapse to save screen space
#   - Visual feedback during command execution
#   - Hotkeys for quick access
#
# Hotkeys:
#   CTRL+1 = Secure item
#   CTRL+2 = Lock down item
#   CTRL+3 = Release item
#
# ============================================================
import API
import time

__version__ = "1.1"

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
        "hotkey": "CTRL+1",
        "needs_target": True,
        "category": "housing",
        "description": "Secure an item in your house"
    },
    "lockdown": {
        "phrase": "I wish to lock this down",
        "label": "Lock Down",
        "hotkey": "CTRL+2",
        "needs_target": True,
        "category": "housing",
        "description": "Lock down an item in your house"
    },
    "release": {
        "phrase": "I release this",
        "label": "Release",
        "hotkey": "CTRL+3",
        "needs_target": True,
        "category": "housing",
        "description": "Release a secured/locked item"
    }
}

# GUI dimensions
COLLAPSED_HEIGHT = 24
EXPANDED_HEIGHT = 120
WINDOW_WIDTH = 140

# Color hues
HUE_NORMAL = 68      # Green
HUE_EXECUTING = 43   # Yellow
HUE_ERROR = 32       # Red

# ============ RUNTIME STATE ============
is_expanded = True
executing_command = None
command_buttons = {}
last_known_x = 100
last_known_y = 100
last_position_check = 0

# ============ UTILITY FUNCTIONS ============
def get_command_by_hotkey(hotkey):
    """Find command key by hotkey string"""
    for key, cmd in COMMANDS.items():
        if cmd["hotkey"] == hotkey:
            return key
    return None

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

        # If target is needed, request it
        if cmd["needs_target"]:
            update_status("Target item...", HUE_EXECUTING)
            target = API.RequestTarget(timeout=TARGET_TIMEOUT)

            if not target:
                API.SysMsg("Command cancelled (no target)", HUE_ERROR)
                update_status("Ready", 68)
            else:
                API.SysMsg(cmd["label"] + " command sent", 68)
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
    # Since labels can't change color, we'll update text only
    # Color was set at creation time
    if is_expanded:
        statusLabel.SetText(text)

# ============ GUI CALLBACKS ============
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

    # Show all command buttons and labels
    for btn in command_buttons.values():
        btn.IsVisible = True

    for label in hotkey_labels.values():
        label.IsVisible = True

    statusLabel.IsVisible = True

    # Resize gump
    x = gump.GetX()
    y = gump.GetY()
    gump.SetRect(x, y, WINDOW_WIDTH, EXPANDED_HEIGHT)
    bg.SetRect(0, 0, WINDOW_WIDTH, EXPANDED_HEIGHT)

def collapse_window():
    """Hide all controls and shrink window"""
    expandBtn.SetText("[+]")

    # Hide all command buttons and labels
    for btn in command_buttons.values():
        btn.IsVisible = False

    for label in hotkey_labels.values():
        label.IsVisible = False

    statusLabel.IsVisible = False

    # Resize gump
    x = gump.GetX()
    y = gump.GetY()
    gump.SetRect(x, y, WINDOW_WIDTH, COLLAPSED_HEIGHT)
    bg.SetRect(0, 0, WINDOW_WIDTH, COLLAPSED_HEIGHT)

# ============ COMMAND BUTTON FACTORIES ============
# Each command needs its own callback function
def make_command_executor(cmd_key):
    """Factory function to create command executor callbacks"""
    def executor():
        execute_command(cmd_key)
    return executor

# ============ PERSISTENCE ============
def save_window_position():
    """Save window position to persistence using last known position"""
    global last_known_x, last_known_y

    # Validate coordinates
    if last_known_x < 0 or last_known_y < 0:
        API.SysMsg("Invalid position (" + str(last_known_x) + "," + str(last_known_y) + "), not saving", 43)
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

# ============ CLEANUP ============
def cleanup():
    """Unregister hotkeys and cancel any pending target"""
    # Unregister hotkeys
    for cmd in COMMANDS.values():
        API.OnHotKey(cmd["hotkey"])  # Calling with no callback unregisters

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

# ============ BUILD GUI ============
gump = API.Gumps.CreateGump()
API.Gumps.AddControlOnDisposed(gump, on_closed)

# Load saved position
x, y = load_window_position()
initial_height = EXPANDED_HEIGHT if is_expanded else COLLAPSED_HEIGHT
gump.SetRect(x, y, WINDOW_WIDTH, initial_height)

# Background
bg = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
bg.SetRect(0, 0, WINDOW_WIDTH, initial_height)
gump.Add(bg)

# Title bar
title = API.Gumps.CreateGumpTTFLabel("Util Hotkeys", 16, "#00d4ff")
title.SetPos(5, 2)
gump.Add(title)

# Expand/collapse button
expandBtn = API.Gumps.CreateSimpleButton("[-]" if is_expanded else "[+]", 20, 18)
expandBtn.SetPos(115, 3)
expandBtn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(expandBtn, toggle_expand)
gump.Add(expandBtn)

# Command buttons (created but visibility controlled by expand state)
y_pos = 26
button_width = 85
hotkey_label_x = button_width + 10

# Store references for visibility control
hotkey_labels = {}

for cmd_key in ["secure", "lockdown", "release"]:
    cmd = COMMANDS[cmd_key]

    # Create command button
    btn = API.Gumps.CreateSimpleButton(cmd["label"], button_width, 22)
    btn.SetPos(5, y_pos)
    btn.SetBackgroundHue(HUE_NORMAL)
    btn.IsVisible = is_expanded
    API.Gumps.AddControlOnClick(btn, make_command_executor(cmd_key))
    gump.Add(btn)
    command_buttons[cmd_key] = btn

    # Create hotkey label
    hotkey_text = cmd["hotkey"].replace("CTRL+", "^")
    label = API.Gumps.CreateGumpTTFLabel(hotkey_text, 8, "#888888")
    label.SetPos(hotkey_label_x, y_pos + 5)
    label.IsVisible = is_expanded
    gump.Add(label)
    hotkey_labels[cmd_key] = label

    y_pos += 26

# Status label at bottom
statusLabel = API.Gumps.CreateGumpTTFLabel("Ready", 9, "#00ff00")
statusLabel.SetPos(5, y_pos + 5)
statusLabel.IsVisible = is_expanded
gump.Add(statusLabel)

API.Gumps.AddGump(gump)

# ============ REGISTER HOTKEYS ============
# Register hotkeys for each command
for cmd_key, cmd in COMMANDS.items():
    API.OnHotKey(cmd["hotkey"], make_command_executor(cmd_key))

# ============ STARTUP MESSAGE ============
API.SysMsg("=== Utility Hotkeys v1.1 ===", 68)
API.SysMsg("CTRL+1=Secure, CTRL+2=Lock, CTRL+3=Release", 53)

# ============ MAIN LOOP ============
while not API.StopRequested:
    try:
        API.ProcessCallbacks()  # Process hotkeys and GUI events

        # Periodically update last known position (every 2 seconds)
        # Skip if stop is requested to avoid "operation canceled" errors
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
