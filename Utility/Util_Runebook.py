# ============================================================
# Runebook Recaller v2.7 (Hotkey Edition)
# by Coryigon for UO Unchained
# ============================================================
#
# Quick travel to your favorite spots. Save up to 4 runebook
# destinations and recall to them with a single click or hotkey.
#
# Setup:
#   1. Click [SET] next to any destination button
#   2. Target your runebook
#   3. Pick the rune slot (1-16)
#   4. Click [C] in title bar to configure hotkeys
#
# Hotkey Binding:
#   1. Click [C] to open hotkey config panel
#   2. Click the button next to a destination (turns PURPLE)
#   3. Press any key to bind it (or ESC to cancel)
#   4. Button shows your bound key and turns green
#
# Features:
#   - Collapsible interface (click [-] to minimize, [+] to expand)
#   - 4 quick-access destination slots
#   - Dynamic hotkey binding (any key, even modifiers like CTRL+F1)
#   - Click-to-capture hotkey system (purple = listening)
#   - Visual feedback (green = configured, gray = not configured)
#   - Works with any runebook
#   - Remembers settings between sessions
#   - Unified UI design (180px width, semantic color coding)
#
# v2.7 Changes:
#   - Dynamic window width: 155px normal mode, 190px config mode
#   - Buttons fill space in normal mode, window expands for SET buttons
#   - SET button width increased to 36px (no truncation)
#
# v2.6 Changes:
#   - Reverted to working button pattern (dimensions in Create, SetPos for position)
#   - Fixed all buttons that broke in v2.5
#   - Fixed gump position access (back to GetX()/GetY() methods, not properties)
#   - Fixed text input SetText() method calls
#
# v2.4 Changes:
#   - Fixed hotkey capture system (now uses proven pattern)
#   - Added ESC to cancel hotkey capture
#   - Unified button colors (green = ready, gray = not configured)
#   - Non-blocking hotkey registration
#   - Added hotkey display on destination buttons
#   - SET buttons only visible in config mode
#
# ============================================================
import API
import time

__version__ = "2.7"

# ============ SETTINGS ============
SETTINGS_KEY = "RunebookRecall"
RECALL_COOLDOWN = 1.0      # Seconds between recalls
GUMP_WAIT_TIME = 3.0       # Max time to wait for runebook gump (increased)
RUNEBOOK_GRAPHIC = 0x22C5  # Standard runebook graphic
USE_OBJECT_DELAY = 0.5     # Delay after using runebook before waiting for gump
GUMP_READY_DELAY = 0.3     # Delay after gump appears before clicking button

# ============ GUI DIMENSIONS ============
WINDOW_WIDTH_NORMAL = 155  # Normal mode (no SET buttons): 5px + 147px button + 3px margin
WINDOW_WIDTH_CONFIG = 190  # Config mode (with SET buttons): 5px + 147px + 2px + 36px SET
COLLAPSED_HEIGHT = 24
NORMAL_HEIGHT = 145
SETUP_HEIGHT = 215
CONFIG_HEIGHT = 265  # Normal height + config panel (120px)

# Button widths (Note: Legion API doesn't support resizing buttons after creation)
# Layout: 5px margin + 147px button + 2px gap + 36px SET = 190px total
BTN_WIDTH = 147        # Destination button width (wider for less empty space in normal mode)
SET_BTN_WIDTH = 36     # SET button width (wider so [SET] isn't truncated)
SET_BTN_X = 154        # 5 + 147 + 2

# ============ BUTTON FORMULA ============
# Your server: Button ID = 49 + slot number
# Slot 1 = Button 50, Slot 2 = Button 51, etc.
def slot_to_button(slot):
    return 49 + slot

# ============ STATE ============
last_recall_time = 0
is_expanded = True
current_setup_key = None
last_known_x = 100
last_known_y = 100
last_position_check = 0
show_config = False  # Hotkey config panel visibility
capturing_for = None  # Which destination is capturing a hotkey (Home, Bank, Custom1, Custom2, or None)

destinations = {
    "Home": {"runebook": 0, "slot": 0, "name": "Home", "hotkey": "F1"},
    "Bank": {"runebook": 0, "slot": 0, "name": "Bank", "hotkey": "F2"},
    "Custom1": {"runebook": 0, "slot": 0, "name": "Custom1", "hotkey": "F3"},
    "Custom2": {"runebook": 0, "slot": 0, "name": "Custom2", "hotkey": "F4"},
}

# ============ ALL POSSIBLE KEYS ============
# Register all these keys to capture any press
ALL_KEYS = [
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
    "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "NUMPAD0", "NUMPAD1", "NUMPAD2", "NUMPAD3", "NUMPAD4",
    "NUMPAD5", "NUMPAD6", "NUMPAD7", "NUMPAD8", "NUMPAD9",
    "TAB", "SPACE", "ENTER", "ESC", "PAUSE", "BACKSPACE",
    "HOME", "END", "PAGEUP", "PAGEDOWN", "INSERT", "DELETE",
    "LEFT", "RIGHT", "UP", "DOWN",
    "MULTIPLY", "ADD", "SUBTRACT", "DIVIDE", "DECIMAL",
]

# ============ HOTKEY MANAGEMENT ============
def make_key_handler(key_name):
    """Create a callback for a specific key - handles both capture and execution"""
    def handler():
        global capturing_for

        # If we're in capture mode
        if capturing_for is not None:
            # ESC cancels capture
            if key_name == "ESC":
                API.SysMsg("Hotkey capture cancelled", 90)
                capturing_for = None
                update_config_buttons()
                return

            # Assign this key to the destination
            destinations[capturing_for]["hotkey"] = key_name
            save_destinations()
            update_config_buttons()
            update_button_labels()  # Update destination buttons to show new hotkey

            API.SysMsg(capturing_for + " bound to: " + key_name, 68)
            capturing_for = None
            return

        # Not capturing - execute recall if this key is bound to a destination
        for dest_key, dest in destinations.items():
            if dest.get("hotkey", "") == key_name:
                do_recall(dest_key)
                return

    return handler

def start_capture_home():
    """Start listening for a key to bind to Home"""
    global capturing_for
    capturing_for = "Home"
    homeHkBtn.SetBackgroundHue(38)  # Purple = listening
    homeHkBtn.SetText("[Listening...]")
    API.SysMsg("Press any key to bind to Home...", 38)

def start_capture_bank():
    """Start listening for a key to bind to Bank"""
    global capturing_for
    capturing_for = "Bank"
    bankHkBtn.SetBackgroundHue(38)  # Purple = listening
    bankHkBtn.SetText("[Listening...]")
    API.SysMsg("Press any key to bind to Bank...", 38)

def start_capture_custom1():
    """Start listening for a key to bind to Custom1"""
    global capturing_for
    capturing_for = "Custom1"
    custom1HkBtn.SetBackgroundHue(38)  # Purple = listening
    custom1HkBtn.SetText("[Listening...]")
    API.SysMsg("Press any key to bind to Custom1...", 38)

def start_capture_custom2():
    """Start listening for a key to bind to Custom2"""
    global capturing_for
    capturing_for = "Custom2"
    custom2HkBtn.SetBackgroundHue(38)  # Purple = listening
    custom2HkBtn.SetText("[Listening...]")
    API.SysMsg("Press any key to bind to Custom2...", 38)

def cancel_capture():
    """Cancel hotkey capture mode"""
    global capturing_for
    if capturing_for is not None:
        API.SysMsg("Hotkey capture cancelled", 90)
        capturing_for = None
        update_config_buttons()

# ============ PERSISTENCE ============
def save_destinations():
    """Save all destinations to persistent storage"""
    data = ""
    for key, dest in destinations.items():
        hotkey = dest.get("hotkey", "")
        data += key + ":" + str(dest["runebook"]) + ":" + str(dest["slot"]) + ":" + dest["name"] + ":" + hotkey + "|"
    API.SavePersistentVar(SETTINGS_KEY + "_Dest", data, API.PersistentVar.Char)

def load_destinations():
    """Load destinations from persistent storage"""
    global destinations
    data = API.GetPersistentVar(SETTINGS_KEY + "_Dest", "", API.PersistentVar.Char)
    if data:
        try:
            parts = data.split("|")
            for part in parts:
                if ":" in part:
                    pieces = part.split(":")
                    if len(pieces) >= 4:
                        key = pieces[0]
                        if key in destinations:
                            destinations[key]["runebook"] = int(pieces[1])
                            destinations[key]["slot"] = int(pieces[2])
                            destinations[key]["name"] = pieces[3]
                            # Load hotkey if present
                            if len(pieces) >= 5:
                                destinations[key]["hotkey"] = pieces[4]
        except:
            pass
    update_button_labels()
    update_config_buttons()

def update_button_labels():
    """Update button labels and hues based on saved destinations"""
    try:
        for key, dest in destinations.items():
            hotkey = dest.get("hotkey", "")

            if dest["slot"] > 0:
                label = dest["name"] + " [" + str(dest["slot"]) + "]"
                # Add hotkey if configured
                if hotkey:
                    label += " (" + hotkey + ")"
                hue = 68  # Green = configured and ready
            else:
                label = key + " [---]"
                # Add hotkey even if slot not configured
                if hotkey:
                    label += " (" + hotkey + ")"
                hue = 90  # Gray = not configured

            if key == "Home":
                homeBtn.SetText(label)
                homeBtn.SetBackgroundHue(hue)
            elif key == "Bank":
                bankBtn.SetText(label)
                bankBtn.SetBackgroundHue(hue)
            elif key == "Custom1":
                custom1Btn.SetText(label)
                custom1Btn.SetBackgroundHue(hue)
            elif key == "Custom2":
                custom2Btn.SetText(label)
                custom2Btn.SetBackgroundHue(hue)
    except Exception as e:
        API.SysMsg("Error updating button labels: " + str(e), 32)

def update_config_buttons():
    """Update hotkey config button labels and hues"""
    try:
        for key, dest in destinations.items():
            hotkey = dest.get("hotkey", "")
            if hotkey:
                label = "[" + hotkey + "]"
                hue = 68  # Green = hotkey bound
            else:
                label = "[---]"
                hue = 90  # Gray = no hotkey

            if key == "Home":
                homeHkBtn.SetText(label)
                homeHkBtn.SetBackgroundHue(hue)
            elif key == "Bank":
                bankHkBtn.SetText(label)
                bankHkBtn.SetBackgroundHue(hue)
            elif key == "Custom1":
                custom1HkBtn.SetText(label)
                custom1HkBtn.SetBackgroundHue(hue)
            elif key == "Custom2":
                custom2HkBtn.SetText(label)
                custom2HkBtn.SetBackgroundHue(hue)
    except Exception as e:
        API.SysMsg("Error updating config buttons: " + str(e), 32)

# ============ EXPAND/COLLAPSE ============
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

    # Show destination buttons
    homeBtn.IsVisible = True
    bankBtn.IsVisible = True
    custom1Btn.IsVisible = True
    custom2Btn.IsVisible = True

    # Resize gump and background
    x = gump.GetX()
    y = gump.GetY()

    # Choose height and width based on active panels
    height = NORMAL_HEIGHT
    width = WINDOW_WIDTH_NORMAL
    if show_config:
        height = CONFIG_HEIGHT
        width = WINDOW_WIDTH_CONFIG
        # Position buttons for wider window
        configBtn.SetPos(140, 3)
        expandBtn.SetPos(165, 3)
    else:
        # Position buttons for narrower window
        configBtn.SetPos(105, 3)
        expandBtn.SetPos(130, 3)

    gump.SetRect(x, y, width, height)
    bg.SetRect(0, 0, width, height)

    # Restore config panel if it was showing
    if show_config:
        configBg.IsVisible = True
        homeHkLabel.IsVisible = True
        homeHkBtn.IsVisible = True
        bankHkLabel.IsVisible = True
        bankHkBtn.IsVisible = True
        custom1HkLabel.IsVisible = True
        custom1HkBtn.IsVisible = True
        custom2HkLabel.IsVisible = True
        custom2HkBtn.IsVisible = True
        configDoneBtn.IsVisible = True
        configHelpLabel.IsVisible = True
        homeSetBtn.IsVisible = True
        bankSetBtn.IsVisible = True
        custom1SetBtn.IsVisible = True
        custom2SetBtn.IsVisible = True

def collapse_window():
    """Hide all controls and shrink window"""
    expandBtn.SetText("[+]")

    # Hide all destination buttons
    homeBtn.IsVisible = False
    homeSetBtn.IsVisible = False
    bankBtn.IsVisible = False
    bankSetBtn.IsVisible = False
    custom1Btn.IsVisible = False
    custom1SetBtn.IsVisible = False
    custom2Btn.IsVisible = False
    custom2SetBtn.IsVisible = False

    # Hide setup panel
    hide_setup_panel()

    # Hide config panel controls visually (but preserve show_config state)
    configBg.IsVisible = False
    homeHkLabel.IsVisible = False
    homeHkBtn.IsVisible = False
    bankHkLabel.IsVisible = False
    bankHkBtn.IsVisible = False
    custom1HkLabel.IsVisible = False
    custom1HkBtn.IsVisible = False
    custom2HkLabel.IsVisible = False
    custom2HkBtn.IsVisible = False
    configDoneBtn.IsVisible = False
    configHelpLabel.IsVisible = False

    # Resize gump and background (use config width if config was active)
    x = gump.GetX()
    y = gump.GetY()
    width = WINDOW_WIDTH_CONFIG if show_config else WINDOW_WIDTH_NORMAL

    # Position buttons based on width
    if show_config:
        configBtn.SetPos(140, 3)
        expandBtn.SetPos(165, 3)
    else:
        configBtn.SetPos(105, 3)
        expandBtn.SetPos(130, 3)

    gump.SetRect(x, y, width, COLLAPSED_HEIGHT)
    bg.SetRect(0, 0, width, COLLAPSED_HEIGHT)

def save_expanded_state():
    """Save expanded state to persistence"""
    API.SavePersistentVar(SETTINGS_KEY + "_Expanded", str(is_expanded), API.PersistentVar.Char)

def load_expanded_state():
    """Load expanded state from persistence"""
    global is_expanded
    saved = API.GetPersistentVar(SETTINGS_KEY + "_Expanded", "True", API.PersistentVar.Char)
    is_expanded = (saved == "True")

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

# ============ CONFIG PANEL ============
def toggle_config():
    """Toggle hotkey config panel visibility"""
    global show_config

    if show_config:
        hide_config_panel()
    else:
        show_config_panel()

def show_config_panel():
    """Show the hotkey config panel"""
    global show_config

    # Hide setup panel if showing
    hide_setup_panel()

    show_config = True

    # Show all config controls
    configBg.IsVisible = True
    homeHkLabel.IsVisible = True
    homeHkBtn.IsVisible = True
    bankHkLabel.IsVisible = True
    bankHkBtn.IsVisible = True
    custom1HkLabel.IsVisible = True
    custom1HkBtn.IsVisible = True
    custom2HkLabel.IsVisible = True
    custom2HkBtn.IsVisible = True
    configDoneBtn.IsVisible = True
    configHelpLabel.IsVisible = True

    # Show SET buttons in config mode
    homeSetBtn.IsVisible = True
    bankSetBtn.IsVisible = True
    custom1SetBtn.IsVisible = True
    custom2SetBtn.IsVisible = True

    # Update button text
    configBtn.SetText("[C]")
    configBtn.SetBackgroundHue(68)

    # Reposition title bar buttons for wider window
    configBtn.SetPos(140, 3)
    expandBtn.SetPos(165, 3)

    # Expand window to wider config width
    if is_expanded:
        gump.SetRect(gump.GetX(), gump.GetY(), WINDOW_WIDTH_CONFIG, CONFIG_HEIGHT)
        bg.SetRect(0, 0, WINDOW_WIDTH_CONFIG, CONFIG_HEIGHT)

def hide_config_panel():
    """Hide the hotkey config panel"""
    global show_config

    show_config = False

    # Hide all config controls
    configBg.IsVisible = False
    homeHkLabel.IsVisible = False
    homeHkBtn.IsVisible = False
    bankHkLabel.IsVisible = False
    bankHkBtn.IsVisible = False
    custom1HkLabel.IsVisible = False
    custom1HkBtn.IsVisible = False
    custom2HkLabel.IsVisible = False
    custom2HkBtn.IsVisible = False
    configDoneBtn.IsVisible = False
    configHelpLabel.IsVisible = False

    # Hide SET buttons when not in config mode
    homeSetBtn.IsVisible = False
    bankSetBtn.IsVisible = False
    custom1SetBtn.IsVisible = False
    custom2SetBtn.IsVisible = False

    # Update button text
    configBtn.SetText("[C]")
    configBtn.SetBackgroundHue(90)

    # Reposition title bar buttons for narrower window
    configBtn.SetPos(105, 3)
    expandBtn.SetPos(130, 3)

    # Shrink window back to normal width (only if expanded)
    if is_expanded:
        gump.SetRect(gump.GetX(), gump.GetY(), WINDOW_WIDTH_NORMAL, NORMAL_HEIGHT)
        bg.SetRect(0, 0, WINDOW_WIDTH_NORMAL, NORMAL_HEIGHT)

# ============ RECALL FUNCTION ============
def do_recall(dest_key):
    """Perform recall to a destination"""
    global last_recall_time

    dest = destinations.get(dest_key)
    if not dest or dest["runebook"] == 0 or dest["slot"] == 0:
        API.SysMsg(dest_key + " not configured! Click [SET] to setup.", 32)
        return False

    # Check cooldown
    now = time.time()
    if now - last_recall_time < RECALL_COOLDOWN:
        remaining = RECALL_COOLDOWN - (now - last_recall_time)
        API.SysMsg("Cooldown: " + str(round(remaining, 1)) + "s", 43)
        return False

    # Use the runebook (works even if in closed container)
    API.SysMsg("Recalling to " + dest["name"] + "...", 68)
    API.UseObject(dest["runebook"])

    # Delay after using object - let the server process it
    API.Pause(USE_OBJECT_DELAY)

    # Wait for gump
    if not API.WaitForGump(delay=GUMP_WAIT_TIME):
        API.SysMsg("Runebook gump didn't open!", 32)
        return False

    # Delay after gump appears - let it fully render
    API.Pause(GUMP_READY_DELAY)

    # Click the recall button
    button_id = slot_to_button(dest["slot"])
    result = API.ReplyGump(button_id)

    if result:
        last_recall_time = time.time()
        API.SysMsg("Recall: " + dest["name"] + " (slot " + str(dest["slot"]) + ")", 68)
        return True
    else:
        API.SysMsg("Failed to click button " + str(button_id), 32)
        return False

# ============ SETUP FUNCTIONS ============
def setup_destination(dest_key):
    """Setup a destination - target runebook and select slot"""
    API.SysMsg("=== Setup " + dest_key + " ===", 68)
    API.SysMsg("Target your runebook...", 53)

    target = API.RequestTarget(timeout=15)
    if not target:
        API.SysMsg("Cancelled", 32)
        hide_setup_panel()
        return

    # Verify it's an item
    item = API.FindItem(target)
    if not item:
        API.SysMsg("Item not found!", 32)
        hide_setup_panel()
        return

    # Store the runebook serial
    destinations[dest_key]["runebook"] = target
    destinations[dest_key]["pending_setup"] = True

    # Show setup panel and set defaults
    show_setup_panel()
    slotInput.SetText("1")
    nameInput.SetText(dest_key)
    statusLabel.SetText(dest_key + ": Enter slot, click CONFIRM")

    API.SysMsg("Runebook saved! Enter slot (1-16) and click CONFIRM", 68)

def confirm_setup(dest_key):
    """Confirm the slot number for setup"""
    global current_setup_key

    if not destinations[dest_key].get("pending_setup"):
        API.SysMsg("Click [SET] first to start setup!", 32)
        return

    # Get slot text - use .Text property
    slot_text = ""
    try:
        slot_text = slotInput.Text
    except Exception as e:
        API.SysMsg("Error reading slot: " + str(e), 32)
        return

    # Handle empty or None
    if not slot_text or str(slot_text).strip() == "":
        slot_text = "1"  # Default to slot 1
        API.SysMsg("Using default slot 1", 43)

    # Parse slot number
    try:
        slot = int(str(slot_text).strip())
    except:
        API.SysMsg("'" + str(slot_text) + "' is not a number! Enter 1-16", 32)
        return

    if slot < 1 or slot > 16:
        API.SysMsg("Slot must be 1-16! You entered: " + str(slot), 32)
        return

    # Get custom name
    name = dest_key
    try:
        name_text = nameInput.Text
        if name_text and str(name_text).strip():
            name = str(name_text).strip()
    except:
        pass  # Use default name

    # Save it
    destinations[dest_key]["slot"] = slot
    destinations[dest_key]["name"] = name
    destinations[dest_key]["pending_setup"] = False

    save_destinations()
    update_button_labels()

    API.SysMsg(dest_key + " set to slot " + str(slot) + " (" + name + ")", 68)

    # Hide setup panel and clear state
    current_setup_key = None
    hide_setup_panel()

def show_setup_panel():
    """Show the setup controls and expand gump"""
    # Hide config panel if showing
    hide_config_panel()

    setupBg.IsVisible = True
    slotLabel.IsVisible = True
    slotInput.IsVisible = True
    nameLabel.IsVisible = True
    nameInput.IsVisible = True
    confirmBtn.IsVisible = True
    cancelBtn.IsVisible = True
    statusLabel.IsVisible = True
    # Expand gump (use normal width for setup)
    gump.SetRect(gump.GetX(), gump.GetY(), WINDOW_WIDTH_NORMAL, SETUP_HEIGHT)
    bg.SetRect(0, 0, WINDOW_WIDTH_NORMAL, SETUP_HEIGHT)

def hide_setup_panel():
    """Hide the setup controls and shrink gump"""
    setupBg.IsVisible = False
    slotLabel.IsVisible = False
    slotInput.IsVisible = False
    nameLabel.IsVisible = False
    nameInput.IsVisible = False
    confirmBtn.IsVisible = False
    cancelBtn.IsVisible = False
    statusLabel.IsVisible = False
    # Shrink gump back to normal (only if expanded and config not showing)
    if is_expanded and not show_config:
        gump.SetRect(gump.GetX(), gump.GetY(), WINDOW_WIDTH_NORMAL, NORMAL_HEIGHT)
        bg.SetRect(0, 0, WINDOW_WIDTH_NORMAL, NORMAL_HEIGHT)

def cancel_setup():
    """Cancel current setup"""
    global current_setup_key
    if current_setup_key:
        destinations[current_setup_key]["pending_setup"] = False
    current_setup_key = None
    hide_setup_panel()
    API.SysMsg("Setup cancelled", 43)

def setup_home():
    global current_setup_key
    current_setup_key = "Home"
    setup_destination("Home")

def setup_bank():
    global current_setup_key
    current_setup_key = "Bank"
    setup_destination("Bank")

def setup_custom1():
    global current_setup_key
    current_setup_key = "Custom1"
    setup_destination("Custom1")

def setup_custom2():
    global current_setup_key
    current_setup_key = "Custom2"
    setup_destination("Custom2")

def confirm_current_setup():
    global current_setup_key
    if current_setup_key:
        confirm_setup(current_setup_key)
    else:
        API.SysMsg("Click [SET] next to a button first!", 32)

# ============ RECALL BUTTON HANDLERS ============
def recall_home():
    do_recall("Home")

def recall_bank():
    do_recall("Bank")

def recall_custom1():
    do_recall("Custom1")

def recall_custom2():
    do_recall("Custom2")

# ============ CLEANUP ============
def onClosed():
    """Handle window close event"""
    save_window_position()
    API.Stop()

# ============ BUILD GUI ============
# Load expanded state and position
load_expanded_state()
x, y = load_window_position()

gump = API.Gumps.CreateGump()
API.Gumps.AddControlOnDisposed(gump, onClosed)

initial_height = NORMAL_HEIGHT if is_expanded else COLLAPSED_HEIGHT
initial_width = WINDOW_WIDTH_NORMAL  # Start with normal width (no config panel)
gump.SetRect(x, y, initial_width, initial_height)

# Background
bg = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
bg.SetRect(0, 0, initial_width, initial_height)
gump.Add(bg)

# Title bar
title = API.Gumps.CreateGumpTTFLabel("Runebook", 16, "#00d4ff")
title.SetPos(5, 2)
gump.Add(title)

# Config button [C] - next to expand button
configBtn = API.Gumps.CreateSimpleButton("[C]", 20, 18)
configBtn.SetPos(105, 3)  # Position for 155px width
configBtn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(configBtn, toggle_config)
gump.Add(configBtn)

# Expand/collapse button
expandBtn = API.Gumps.CreateSimpleButton("[-]" if is_expanded else "[+]", 20, 18)
expandBtn.SetPos(130, 3)  # Position for 155px width
expandBtn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(expandBtn, toggle_expand)
gump.Add(expandBtn)

# === DESTINATION BUTTONS ===
y = 26

# Home (start with full width, config is hidden initially)
homeBtn = API.Gumps.CreateSimpleButton("Home [---]", BTN_WIDTH, 22)
homeBtn.SetPos(5, y)
homeBtn.SetBackgroundHue(90)  # Gray = not configured (will update on load)
homeBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(homeBtn, recall_home)
gump.Add(homeBtn)

homeSetBtn = API.Gumps.CreateSimpleButton("[SET]", SET_BTN_WIDTH, 22)
homeSetBtn.SetPos(SET_BTN_X, y)
homeSetBtn.SetBackgroundHue(53)
homeSetBtn.IsVisible = False  # Only show in config mode
API.Gumps.AddControlOnClick(homeSetBtn, setup_home)
gump.Add(homeSetBtn)

# Bank
y += 26
bankBtn = API.Gumps.CreateSimpleButton("Bank [---]", BTN_WIDTH, 22)
bankBtn.SetPos(5, y)
bankBtn.SetBackgroundHue(90)  # Gray = not configured (will update on load)
bankBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(bankBtn, recall_bank)
gump.Add(bankBtn)

bankSetBtn = API.Gumps.CreateSimpleButton("[SET]", SET_BTN_WIDTH, 22)
bankSetBtn.SetPos(SET_BTN_X, y)
bankSetBtn.SetBackgroundHue(53)
bankSetBtn.IsVisible = False  # Only show in config mode
API.Gumps.AddControlOnClick(bankSetBtn, setup_bank)
gump.Add(bankSetBtn)

# Custom1
y += 26
custom1Btn = API.Gumps.CreateSimpleButton("Custom1 [---]", BTN_WIDTH, 22)
custom1Btn.SetPos(5, y)
custom1Btn.SetBackgroundHue(90)  # Gray = not configured (will update on load)
custom1Btn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(custom1Btn, recall_custom1)
gump.Add(custom1Btn)

custom1SetBtn = API.Gumps.CreateSimpleButton("[SET]", SET_BTN_WIDTH, 22)
custom1SetBtn.SetPos(SET_BTN_X, y)
custom1SetBtn.SetBackgroundHue(53)
custom1SetBtn.IsVisible = False  # Only show in config mode
API.Gumps.AddControlOnClick(custom1SetBtn, setup_custom1)
gump.Add(custom1SetBtn)

# Custom2
y += 26
custom2Btn = API.Gumps.CreateSimpleButton("Custom2 [---]", BTN_WIDTH, 22)
custom2Btn.SetPos(5, y)
custom2Btn.SetBackgroundHue(90)  # Gray = not configured (will update on load)
custom2Btn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(custom2Btn, recall_custom2)
gump.Add(custom2Btn)

custom2SetBtn = API.Gumps.CreateSimpleButton("[SET]", SET_BTN_WIDTH, 22)
custom2SetBtn.SetPos(SET_BTN_X, y)
custom2SetBtn.SetBackgroundHue(53)
custom2SetBtn.IsVisible = False  # Only show in config mode
API.Gumps.AddControlOnClick(custom2SetBtn, setup_custom2)
gump.Add(custom2SetBtn)

# === SETUP SECTION (hidden initially) ===
y += 30

# Setup background
setupBg = API.Gumps.CreateGumpColorBox(0.8, "#2a2a3e")
setupBg.SetRect(0, y - 3, WINDOW_WIDTH_NORMAL, 70)
setupBg.IsVisible = False
gump.Add(setupBg)

# Slot input
slotLabel = API.Gumps.CreateGumpTTFLabel("Slot:", 15, "#aaaaaa")
slotLabel.SetPos(5, y + 3)
slotLabel.IsVisible = False
gump.Add(slotLabel)

slotInput = API.Gumps.CreateGumpTextBox("1", 28, 20)
slotInput.SetRect(30, y, 28, 20)
slotInput.IsVisible = False
gump.Add(slotInput)

# Name input
nameLabel = API.Gumps.CreateGumpTTFLabel("Name:", 15, "#aaaaaa")
nameLabel.SetPos(63, y + 3)
nameLabel.IsVisible = False
gump.Add(nameLabel)

nameInput = API.Gumps.CreateGumpTextBox("", 48, 20)
nameInput.SetRect(87, y, 48, 20)
nameInput.IsVisible = False
gump.Add(nameInput)

# Confirm button
y += 24
confirmBtn = API.Gumps.CreateSimpleButton("[OK]", 62, 20)
confirmBtn.SetPos(5, y)
confirmBtn.SetBackgroundHue(68)
confirmBtn.IsVisible = False
API.Gumps.AddControlOnClick(confirmBtn, confirm_current_setup)
gump.Add(confirmBtn)

# Cancel button
cancelBtn = API.Gumps.CreateSimpleButton("[CANCEL]", 62, 20)
cancelBtn.SetPos(73, y)
cancelBtn.SetBackgroundHue(32)
cancelBtn.IsVisible = False
API.Gumps.AddControlOnClick(cancelBtn, cancel_setup)
gump.Add(cancelBtn)

# Status label
y += 22
statusLabel = API.Gumps.CreateGumpTTFLabel("", 15, "#888888")
statusLabel.SetPos(5, y)
statusLabel.IsVisible = False
gump.Add(statusLabel)

# === HOTKEY CONFIG SECTION (hidden initially) ===
# Starts after Custom2 button at y=130
configY = 130

# Config background
configBg = API.Gumps.CreateGumpColorBox(0.8, "#2a2a3e")
configBg.SetRect(0, configY, WINDOW_WIDTH_CONFIG, 120)
configBg.IsVisible = False
gump.Add(configBg)

# Help text
configHelpLabel = API.Gumps.CreateGumpTTFLabel("Click hotkey, press key to bind", 15, "#888888")
configHelpLabel.SetPos(5, configY + 3)
configHelpLabel.IsVisible = False
gump.Add(configHelpLabel)

configY += 18

# Home hotkey
homeHkLabel = API.Gumps.CreateGumpTTFLabel("Home:", 15, "#aaaaaa")
homeHkLabel.SetPos(5, configY + 3)
homeHkLabel.IsVisible = False
gump.Add(homeHkLabel)

homeHkBtn = API.Gumps.CreateSimpleButton("[F1]", 95, 20)
homeHkBtn.SetPos(40, configY)
homeHkBtn.SetBackgroundHue(90)  # Will update on load
homeHkBtn.IsVisible = False
API.Gumps.AddControlOnClick(homeHkBtn, start_capture_home)
gump.Add(homeHkBtn)

# Bank hotkey
configY += 23
bankHkLabel = API.Gumps.CreateGumpTTFLabel("Bank:", 15, "#aaaaaa")
bankHkLabel.SetPos(5, configY + 3)
bankHkLabel.IsVisible = False
gump.Add(bankHkLabel)

bankHkBtn = API.Gumps.CreateSimpleButton("[F2]", 95, 20)
bankHkBtn.SetPos(40, configY)
bankHkBtn.SetBackgroundHue(90)  # Will update on load
bankHkBtn.IsVisible = False
API.Gumps.AddControlOnClick(bankHkBtn, start_capture_bank)
gump.Add(bankHkBtn)

# Custom1 hotkey
configY += 23
custom1HkLabel = API.Gumps.CreateGumpTTFLabel("Custom1:", 15, "#aaaaaa")
custom1HkLabel.SetPos(5, configY + 3)
custom1HkLabel.IsVisible = False
gump.Add(custom1HkLabel)

custom1HkBtn = API.Gumps.CreateSimpleButton("[F3]", 95, 20)
custom1HkBtn.SetPos(40, configY)
custom1HkBtn.SetBackgroundHue(90)  # Will update on load
custom1HkBtn.IsVisible = False
API.Gumps.AddControlOnClick(custom1HkBtn, start_capture_custom1)
gump.Add(custom1HkBtn)

# Custom2 hotkey
configY += 23
custom2HkLabel = API.Gumps.CreateGumpTTFLabel("Custom2:", 15, "#aaaaaa")
custom2HkLabel.SetPos(5, configY + 3)
custom2HkLabel.IsVisible = False
gump.Add(custom2HkLabel)

custom2HkBtn = API.Gumps.CreateSimpleButton("[F4]", 95, 20)
custom2HkBtn.SetPos(40, configY)
custom2HkBtn.SetBackgroundHue(90)  # Will update on load
custom2HkBtn.IsVisible = False
API.Gumps.AddControlOnClick(custom2HkBtn, start_capture_custom2)
gump.Add(custom2HkBtn)

# Done button
configY += 26
configDoneBtn = API.Gumps.CreateSimpleButton("[DONE]", 130, 20)
configDoneBtn.SetPos(5, configY)
configDoneBtn.SetBackgroundHue(68)
configDoneBtn.IsVisible = False
API.Gumps.AddControlOnClick(configDoneBtn, hide_config_panel)
gump.Add(configDoneBtn)

API.Gumps.AddGump(gump)

# ============ INITIALIZATION ============
try:
    load_destinations()
except Exception as e:
    API.SysMsg("Error loading destinations: " + str(e), 32)
    API.SysMsg("Using default settings", 43)

# Register ALL possible keys with handler system
API.SysMsg("=== Runebook Recall v" + __version__ + " ===", 68)
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
API.SysMsg("Click destination to recall, [C] for hotkeys", 53)

# ============ MAIN LOOP ============
while not API.StopRequested:
    try:
        API.ProcessCallbacks()

        # Periodically update last known position (every 2 seconds)
        if not API.StopRequested:
            current_time = time.time()
            if current_time - last_position_check > 2.0:
                last_position_check = current_time
                try:
                    # Get both coordinates atomically to avoid race condition
                    x = gump.GetX()
                    y = gump.GetY()
                    # Only update if both succeed
                    last_known_x = x
                    last_known_y = y
                except:
                    pass  # Silently ignore if gump is disposed

        API.Pause(0.1)
    except Exception as e:
        # Don't show "operation canceled" errors during shutdown
        if "operation canceled" not in str(e).lower() and not API.StopRequested:
            API.SysMsg("Error in main loop: " + str(e), 32)
        API.Pause(1)
