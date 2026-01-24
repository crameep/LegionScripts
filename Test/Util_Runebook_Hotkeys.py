# ============================================================
# Runebook Recaller v2.0 (with Hotkeys)
# by Coryigon for UO Unchained
# ============================================================
#
# Quick travel to your favorite spots. Save up to 4 runebook
# destinations and recall to them with a single click or hotkey!
#
# Setup:
#   1. Click [SET] next to any destination button
#   2. Target your runebook
#   3. Pick the rune slot (1-16)
#   4. Click yellow [K] button to set custom hotkey
#
# NEW: Customizable hotkeys for each destination!
#
# Features:
#   - Customizable hotkeys - click yellow [K] button to rebind
#   - Compact UI - hotkey buttons show current binding (22px)
#   - Collapsible interface (click [-] to minimize, [+] to expand)
#   - 4 quick-access destination slots
#   - Works with any runebook
#   - Remembers settings between sessions
#   - Yellow = configurable | Purple = listening | ESC = cancel
#
# ============================================================
import API
import time

__version__ = "2.0"

# ============ SETTINGS ============
SETTINGS_KEY = "RunebookRecall"
RECALL_COOLDOWN = 1.0      # Seconds between recalls
GUMP_WAIT_TIME = 3.0       # Max time to wait for runebook gump (increased)
RUNEBOOK_GRAPHIC = 0x22C5  # Standard runebook graphic
USE_OBJECT_DELAY = 0.5     # Delay after using runebook before waiting for gump
GUMP_READY_DELAY = 0.3     # Delay after gump appears before clicking button

# ============ GUI DIMENSIONS ============
WINDOW_WIDTH = 140
COLLAPSED_HEIGHT = 24
NORMAL_HEIGHT = 160  # Taller to accommodate info label
SETUP_HEIGHT = 230  # Taller to accommodate info label

# ============ HOTKEY SYSTEM ============
# All possible keys for hotkey assignment
ALL_KEYS = [
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
    "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "NUMPAD0", "NUMPAD1", "NUMPAD2", "NUMPAD3", "NUMPAD4",
    "NUMPAD5", "NUMPAD6", "NUMPAD7", "NUMPAD8", "NUMPAD9",
    "ESC",  # For canceling hotkey capture
]

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
destinations = {
    "Home": {"runebook": 0, "slot": 0, "name": "Home"},
    "Bank": {"runebook": 0, "slot": 0, "name": "Bank"},
    "Custom1": {"runebook": 0, "slot": 0, "name": "Custom1"},
    "Custom2": {"runebook": 0, "slot": 0, "name": "Custom2"},
}

# Hotkey state
home_hotkey = "F1"
bank_hotkey = "F2"
custom1_hotkey = "F3"
custom2_hotkey = "F4"
listening_for_action = None  # "home", "bank", "custom1", "custom2", or None

# ============ PERSISTENCE ============
def save_destinations():
    """Save all destinations to persistent storage"""
    data = ""
    for key, dest in destinations.items():
        data += key + ":" + str(dest["runebook"]) + ":" + str(dest["slot"]) + ":" + dest["name"] + "|"
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
        except:
            pass
    update_button_labels()

def update_button_labels():
    """Update button labels based on saved destinations"""
    for key, dest in destinations.items():
        if dest["slot"] > 0:
            label = dest["name"] + " [" + str(dest["slot"]) + "]"
        else:
            label = key + " [---]"

        if key == "Home":
            homeBtn.SetText(label[:11])
        elif key == "Bank":
            bankBtn.SetText(label[:11])
        elif key == "Custom1":
            custom1Btn.SetText(label[:11])
        elif key == "Custom2":
            custom2Btn.SetText(label[:11])

# ============ HOTKEY SYSTEM ============
def make_key_handler(key_name):
    """Create a callback for a specific key"""
    def handler():
        global listening_for_action, home_hotkey, bank_hotkey, custom1_hotkey, custom2_hotkey

        # If we're listening for a key assignment
        if listening_for_action is not None:
            # ESC cancels listening mode
            if key_name == "ESC":
                if listening_for_action == "home":
                    homeHotkeyBtn.SetBackgroundHue(43)
                    homeHotkeyBtn.SetText("[" + home_hotkey + "]")
                    API.SysMsg("Cancelled - kept " + home_hotkey, 53)
                elif listening_for_action == "bank":
                    bankHotkeyBtn.SetBackgroundHue(43)
                    bankHotkeyBtn.SetText("[" + bank_hotkey + "]")
                    API.SysMsg("Cancelled - kept " + bank_hotkey, 53)
                elif listening_for_action == "custom1":
                    custom1HotkeyBtn.SetBackgroundHue(43)
                    custom1HotkeyBtn.SetText("[" + custom1_hotkey + "]")
                    API.SysMsg("Cancelled - kept " + custom1_hotkey, 53)
                elif listening_for_action == "custom2":
                    custom2HotkeyBtn.SetBackgroundHue(43)
                    custom2HotkeyBtn.SetText("[" + custom2_hotkey + "]")
                    API.SysMsg("Cancelled - kept " + custom2_hotkey, 53)
                listening_for_action = None
                return

            # Assign the key
            if listening_for_action == "home":
                if key_name == bank_hotkey or key_name == custom1_hotkey or key_name == custom2_hotkey:
                    API.SysMsg("Warning: " + key_name + " already in use", 43)
                home_hotkey = key_name
                API.SavePersistentVar(SETTINGS_KEY + "_HomeKey", home_hotkey, API.PersistentVar.Char)
                API.SysMsg("Home bound to: " + key_name, 68)
                homeHotkeyBtn.SetBackgroundHue(43)
                homeHotkeyBtn.SetText("[" + key_name + "]")
            elif listening_for_action == "bank":
                if key_name == home_hotkey or key_name == custom1_hotkey or key_name == custom2_hotkey:
                    API.SysMsg("Warning: " + key_name + " already in use", 43)
                bank_hotkey = key_name
                API.SavePersistentVar(SETTINGS_KEY + "_BankKey", bank_hotkey, API.PersistentVar.Char)
                API.SysMsg("Bank bound to: " + key_name, 68)
                bankHotkeyBtn.SetBackgroundHue(43)
                bankHotkeyBtn.SetText("[" + key_name + "]")
            elif listening_for_action == "custom1":
                if key_name == home_hotkey or key_name == bank_hotkey or key_name == custom2_hotkey:
                    API.SysMsg("Warning: " + key_name + " already in use", 43)
                custom1_hotkey = key_name
                API.SavePersistentVar(SETTINGS_KEY + "_Custom1Key", custom1_hotkey, API.PersistentVar.Char)
                API.SysMsg("Custom1 bound to: " + key_name, 68)
                custom1HotkeyBtn.SetBackgroundHue(43)
                custom1HotkeyBtn.SetText("[" + key_name + "]")
            elif listening_for_action == "custom2":
                if key_name == home_hotkey or key_name == bank_hotkey or key_name == custom1_hotkey:
                    API.SysMsg("Warning: " + key_name + " already in use", 43)
                custom2_hotkey = key_name
                API.SavePersistentVar(SETTINGS_KEY + "_Custom2Key", custom2_hotkey, API.PersistentVar.Char)
                API.SysMsg("Custom2 bound to: " + key_name, 68)
                custom2HotkeyBtn.SetBackgroundHue(43)
                custom2HotkeyBtn.SetText("[" + key_name + "]")

            listening_for_action = None
            return

        # Not listening - execute the action if this key is bound
        if key_name == home_hotkey:
            recall_home()
        elif key_name == bank_hotkey:
            recall_bank()
        elif key_name == custom1_hotkey:
            recall_custom1()
        elif key_name == custom2_hotkey:
            recall_custom2()

    return handler

def start_capture_home_hotkey():
    """Start listening for home hotkey"""
    global listening_for_action
    listening_for_action = "home"
    homeHotkeyBtn.SetBackgroundHue(38)  # Purple
    homeHotkeyBtn.SetText("[?]")
    API.SysMsg("Press key for Home hotkey (ESC to cancel)...", 38)

def start_capture_bank_hotkey():
    """Start listening for bank hotkey"""
    global listening_for_action
    listening_for_action = "bank"
    bankHotkeyBtn.SetBackgroundHue(38)  # Purple
    bankHotkeyBtn.SetText("[?]")
    API.SysMsg("Press key for Bank hotkey (ESC to cancel)...", 38)

def start_capture_custom1_hotkey():
    """Start listening for custom1 hotkey"""
    global listening_for_action
    listening_for_action = "custom1"
    custom1HotkeyBtn.SetBackgroundHue(38)  # Purple
    custom1HotkeyBtn.SetText("[?]")
    API.SysMsg("Press key for Custom1 hotkey (ESC to cancel)...", 38)

def start_capture_custom2_hotkey():
    """Start listening for custom2 hotkey"""
    global listening_for_action
    listening_for_action = "custom2"
    custom2HotkeyBtn.SetBackgroundHue(38)  # Purple
    custom2HotkeyBtn.SetText("[?]")
    API.SysMsg("Press key for Custom2 hotkey (ESC to cancel)...", 38)

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

    # Show all destination buttons
    homeBtn.IsVisible = True
    homeHotkeyBtn.IsVisible = True
    homeSetBtn.IsVisible = True
    bankBtn.IsVisible = True
    bankHotkeyBtn.IsVisible = True
    bankSetBtn.IsVisible = True
    custom1Btn.IsVisible = True
    custom1HotkeyBtn.IsVisible = True
    custom1SetBtn.IsVisible = True
    custom2Btn.IsVisible = True
    custom2HotkeyBtn.IsVisible = True
    custom2SetBtn.IsVisible = True
    infoLabel.IsVisible = True

    # Resize gump and background
    x = gump.GetX()
    y = gump.GetY()
    gump.SetRect(x, y, WINDOW_WIDTH, NORMAL_HEIGHT)
    bg.SetRect(0, 0, WINDOW_WIDTH, NORMAL_HEIGHT)

def collapse_window():
    """Hide all controls and shrink window"""
    expandBtn.SetText("[+]")

    # Hide all destination buttons
    homeBtn.IsVisible = False
    homeHotkeyBtn.IsVisible = False
    homeSetBtn.IsVisible = False
    bankBtn.IsVisible = False
    bankHotkeyBtn.IsVisible = False
    bankSetBtn.IsVisible = False
    custom1Btn.IsVisible = False
    custom1HotkeyBtn.IsVisible = False
    custom1SetBtn.IsVisible = False
    custom2Btn.IsVisible = False
    custom2HotkeyBtn.IsVisible = False
    custom2SetBtn.IsVisible = False
    infoLabel.IsVisible = False

    # Also hide setup panel if it's showing
    hide_setup_panel()

    # Resize gump and background
    x = gump.GetX()
    y = gump.GetY()
    gump.SetRect(x, y, WINDOW_WIDTH, COLLAPSED_HEIGHT)
    bg.SetRect(0, 0, WINDOW_WIDTH, COLLAPSED_HEIGHT)

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
    
    # Find the runebook
    runebook = API.FindItem(dest["runebook"])
    if not runebook:
        API.SysMsg("Runebook not found! Re-setup " + dest_key, 32)
        return False
    
    # Use the runebook
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
    
    target = API.RequestTarget(timeout=30)
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
    slotInput.Text = "1"
    nameInput.Text = dest_key
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
    setupBg.IsVisible = True
    slotLabel.IsVisible = True
    slotInput.IsVisible = True
    nameLabel.IsVisible = True
    nameInput.IsVisible = True
    confirmBtn.IsVisible = True
    cancelBtn.IsVisible = True
    statusLabel.IsVisible = True
    # Expand gump
    gump.SetRect(gump.GetX(), gump.GetY(), WINDOW_WIDTH, SETUP_HEIGHT)
    bg.SetRect(0, 0, WINDOW_WIDTH, SETUP_HEIGHT)

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
    # Shrink gump back to normal (only if expanded)
    if is_expanded:
        gump.SetRect(gump.GetX(), gump.GetY(), WINDOW_WIDTH, NORMAL_HEIGHT)
        bg.SetRect(0, 0, WINDOW_WIDTH, NORMAL_HEIGHT)

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
def stop_script():
    save_window_position()
    gump.Dispose()
    API.Stop()

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
gump.SetRect(x, y, WINDOW_WIDTH, initial_height)

# Background
bg = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
bg.SetRect(0, 0, WINDOW_WIDTH, initial_height)
gump.Add(bg)

# Title bar
title = API.Gumps.CreateGumpTTFLabel("Runebook", 16, "#00d4ff")
title.SetPos(5, 2)
gump.Add(title)

# Expand/collapse button
expandBtn = API.Gumps.CreateSimpleButton("[-]" if is_expanded else "[+]", 20, 18)
expandBtn.SetPos(115, 3)
expandBtn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(expandBtn, toggle_expand)
gump.Add(expandBtn)

# === DESTINATION BUTTONS ===
y = 26
btnW = 63  # Smaller to make room for hotkey button
hotkeyW = 22
setW = 41

# Home
homeBtn = API.Gumps.CreateSimpleButton("Home [---]", btnW, 22)
homeBtn.SetPos(5, y)
homeBtn.SetBackgroundHue(68)
homeBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(homeBtn, recall_home)
gump.Add(homeBtn)

homeHotkeyBtn = API.Gumps.CreateSimpleButton("[" + home_hotkey + "]", hotkeyW, 22)
homeHotkeyBtn.SetPos(70, y)
homeHotkeyBtn.SetBackgroundHue(43)  # Yellow - configurable
homeHotkeyBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(homeHotkeyBtn, start_capture_home_hotkey)
gump.Add(homeHotkeyBtn)

homeSetBtn = API.Gumps.CreateSimpleButton("[SET]", setW, 22)
homeSetBtn.SetPos(94, y)
homeSetBtn.SetBackgroundHue(53)
homeSetBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(homeSetBtn, setup_home)
gump.Add(homeSetBtn)

# Bank
y += 26
bankBtn = API.Gumps.CreateSimpleButton("Bank [---]", btnW, 22)
bankBtn.SetPos(5, y)
bankBtn.SetBackgroundHue(88)
bankBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(bankBtn, recall_bank)
gump.Add(bankBtn)

bankHotkeyBtn = API.Gumps.CreateSimpleButton("[" + bank_hotkey + "]", hotkeyW, 22)
bankHotkeyBtn.SetPos(70, y)
bankHotkeyBtn.SetBackgroundHue(43)  # Yellow - configurable
bankHotkeyBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(bankHotkeyBtn, start_capture_bank_hotkey)
gump.Add(bankHotkeyBtn)

bankSetBtn = API.Gumps.CreateSimpleButton("[SET]", setW, 22)
bankSetBtn.SetPos(94, y)
bankSetBtn.SetBackgroundHue(53)
bankSetBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(bankSetBtn, setup_bank)
gump.Add(bankSetBtn)

# Custom1
y += 26
custom1Btn = API.Gumps.CreateSimpleButton("Custom1 [---]", btnW, 22)
custom1Btn.SetPos(5, y)
custom1Btn.SetBackgroundHue(43)
custom1Btn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(custom1Btn, recall_custom1)
gump.Add(custom1Btn)

custom1HotkeyBtn = API.Gumps.CreateSimpleButton("[" + custom1_hotkey + "]", hotkeyW, 22)
custom1HotkeyBtn.SetPos(70, y)
custom1HotkeyBtn.SetBackgroundHue(43)  # Yellow - configurable
custom1HotkeyBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(custom1HotkeyBtn, start_capture_custom1_hotkey)
gump.Add(custom1HotkeyBtn)

custom1SetBtn = API.Gumps.CreateSimpleButton("[SET]", setW, 22)
custom1SetBtn.SetPos(94, y)
custom1SetBtn.SetBackgroundHue(53)
custom1SetBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(custom1SetBtn, setup_custom1)
gump.Add(custom1SetBtn)

# Custom2
y += 26
custom2Btn = API.Gumps.CreateSimpleButton("Custom2 [---]", btnW, 22)
custom2Btn.SetPos(5, y)
custom2Btn.SetBackgroundHue(63)
custom2Btn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(custom2Btn, recall_custom2)
gump.Add(custom2Btn)

custom2HotkeyBtn = API.Gumps.CreateSimpleButton("[" + custom2_hotkey + "]", hotkeyW, 22)
custom2HotkeyBtn.SetPos(70, y)
custom2HotkeyBtn.SetBackgroundHue(43)  # Yellow - configurable
custom2HotkeyBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(custom2HotkeyBtn, start_capture_custom2_hotkey)
gump.Add(custom2HotkeyBtn)

custom2SetBtn = API.Gumps.CreateSimpleButton("[SET]", setW, 22)
custom2SetBtn.SetPos(94, y)
custom2SetBtn.SetBackgroundHue(53)
custom2SetBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(custom2SetBtn, setup_custom2)
gump.Add(custom2SetBtn)

y += 24
# Help label
infoLabel = API.Gumps.CreateGumpTTFLabel("Yellow [K] = click to rebind key", 7, "#888888", aligned="center", maxWidth=WINDOW_WIDTH)
infoLabel.SetPos(0, y)
infoLabel.IsVisible = is_expanded
gump.Add(infoLabel)

# === SETUP SECTION (hidden initially) ===
y += 30

# Setup background
setupBg = API.Gumps.CreateGumpColorBox(0.8, "#2a2a3e")
setupBg.SetRect(0, y - 3, WINDOW_WIDTH, 70)
setupBg.IsVisible = False
gump.Add(setupBg)

# Slot input
slotLabel = API.Gumps.CreateGumpTTFLabel("Slot:", 8, "#aaaaaa")
slotLabel.SetPos(5, y + 3)
slotLabel.IsVisible = False
gump.Add(slotLabel)

slotInput = API.Gumps.CreateGumpTextBox("1", 28, 20)
slotInput.SetPos(30, y)
slotInput.IsVisible = False
gump.Add(slotInput)

# Name input
nameLabel = API.Gumps.CreateGumpTTFLabel("Name:", 8, "#aaaaaa")
nameLabel.SetPos(63, y + 3)
nameLabel.IsVisible = False
gump.Add(nameLabel)

nameInput = API.Gumps.CreateGumpTextBox("", 48, 20)
nameInput.SetPos(87, y)
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
statusLabel = API.Gumps.CreateGumpTTFLabel("", 7, "#888888")
statusLabel.SetPos(5, y)
statusLabel.IsVisible = False
gump.Add(statusLabel)

API.Gumps.AddGump(gump)

# ============ INITIALIZATION ============
load_destinations()

# Load hotkeys
home_hotkey = API.GetPersistentVar(SETTINGS_KEY + "_HomeKey", "F1", API.PersistentVar.Char)
bank_hotkey = API.GetPersistentVar(SETTINGS_KEY + "_BankKey", "F2", API.PersistentVar.Char)
custom1_hotkey = API.GetPersistentVar(SETTINGS_KEY + "_Custom1Key", "F3", API.PersistentVar.Char)
custom2_hotkey = API.GetPersistentVar(SETTINGS_KEY + "_Custom2Key", "F4", API.PersistentVar.Char)

# Register all possible keys
registered_count = 0
for key in ALL_KEYS:
    try:
        API.OnHotKey(key, make_key_handler(key))
        registered_count += 1
    except:
        pass

API.SysMsg("=== Runebook Recall v2.0 (Hotkeys) ===", 68)
API.SysMsg("Click to recall, [SET] to config, Yellow [K] to rebind key", 43)
API.SysMsg("Home=" + home_hotkey + " Bank=" + bank_hotkey + " C1=" + custom1_hotkey + " C2=" + custom2_hotkey, 53)

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