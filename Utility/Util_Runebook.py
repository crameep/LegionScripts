# ============================================================
# Runebook Recaller v1.2
# by Coryigon for UO Unchained
# ============================================================
#
# Quick travel to your favorite spots. Save up to 4 runebook
# destinations and recall to them with a single click.
#
# Setup:
#   1. Click [SET] next to any destination button
#   2. Target your runebook
#   3. Pick the rune slot (1-16)
#
# Features:
#   - Collapsible interface (click [-] to minimize, [+] to expand)
#   - 4 quick-access destination slots
#   - Works with any runebook
#   - Remembers settings between sessions
#   - Unified UI design matching other utility scripts
#
# ============================================================
import API
import time

__version__ = "1.2"

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
NORMAL_HEIGHT = 145
SETUP_HEIGHT = 215

# ============ BUTTON FORMULA ============
# Your server: Button ID = 49 + slot number
# Slot 1 = Button 50, Slot 2 = Button 51, etc.
def slot_to_button(slot):
    return 49 + slot

# ============ STATE ============
last_recall_time = 0
is_expanded = True
current_setup_key = None
destinations = {
    "Home": {"runebook": 0, "slot": 0, "name": "Home"},
    "Bank": {"runebook": 0, "slot": 0, "name": "Bank"},
    "Custom1": {"runebook": 0, "slot": 0, "name": "Custom1"},
    "Custom2": {"runebook": 0, "slot": 0, "name": "Custom2"},
}

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
    homeSetBtn.IsVisible = True
    bankBtn.IsVisible = True
    bankSetBtn.IsVisible = True
    custom1Btn.IsVisible = True
    custom1SetBtn.IsVisible = True
    custom2Btn.IsVisible = True
    custom2SetBtn.IsVisible = True

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
    homeSetBtn.IsVisible = False
    bankBtn.IsVisible = False
    bankSetBtn.IsVisible = False
    custom1Btn.IsVisible = False
    custom1SetBtn.IsVisible = False
    custom2Btn.IsVisible = False
    custom2SetBtn.IsVisible = False

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
    API.SavePersistentVar(SETTINGS_KEY + "_XY", str(gump.GetX()) + "," + str(gump.GetY()), API.PersistentVar.Char)
    gump.Dispose()
    API.Stop()

def onClosed():
    API.SavePersistentVar(SETTINGS_KEY + "_XY", str(gump.GetX()) + "," + str(gump.GetY()), API.PersistentVar.Char)
    API.Stop()

# ============ BUILD GUI ============
# Load expanded state first
load_expanded_state()

gump = API.Gumps.CreateGump()
API.Gumps.AddControlOnDisposed(gump, onClosed)

savedPos = API.GetPersistentVar(SETTINGS_KEY + "_XY", "100,100", API.PersistentVar.Char)
posXY = savedPos.split(',')
initial_height = NORMAL_HEIGHT if is_expanded else COLLAPSED_HEIGHT
gump.SetRect(int(posXY[0]), int(posXY[1]), WINDOW_WIDTH, initial_height)

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
btnW = 90
setW = 35

# Home
homeBtn = API.Gumps.CreateSimpleButton("Home [---]", btnW, 22)
homeBtn.SetPos(5, y)
homeBtn.SetBackgroundHue(68)
homeBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(homeBtn, recall_home)
gump.Add(homeBtn)

homeSetBtn = API.Gumps.CreateSimpleButton("[SET]", setW, 22)
homeSetBtn.SetPos(100, y)
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

bankSetBtn = API.Gumps.CreateSimpleButton("[SET]", setW, 22)
bankSetBtn.SetPos(100, y)
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

custom1SetBtn = API.Gumps.CreateSimpleButton("[SET]", setW, 22)
custom1SetBtn.SetPos(100, y)
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

custom2SetBtn = API.Gumps.CreateSimpleButton("[SET]", setW, 22)
custom2SetBtn.SetPos(100, y)
custom2SetBtn.SetBackgroundHue(53)
custom2SetBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(custom2SetBtn, setup_custom2)
gump.Add(custom2SetBtn)

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
API.SysMsg("=== Runebook Recall v1.2 ===", 68)
API.SysMsg("Click destination to recall, [SET] to configure", 53)

# ============ MAIN LOOP ============
while not API.StopRequested:
    API.ProcessCallbacks()
    API.Pause(0.1)