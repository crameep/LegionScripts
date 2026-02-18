# ============================================================
# Packy Suite v1.0
# by Coryigon for UO Unchained
# ============================================================
#
# Automatically moves specific item types from your backpack to
# a designated packhorse (or any container mobile).
#
# Features:
#   - Target any packhorse/container mobile as destination
#   - Add item types by targeting items in-game
#   - Remove item types from watch list
#   - Automatic scanning and transfer with QueueMoveItem
#   - Enable/disable toggle
#   - Collapsible GUI with position persistence
#
# ============================================================
import API
import time
import sys
import os

# Add parent directory (CoryCustom root) to path for library imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from LegionUtils import (
    # Foundation utilities
    get_item_safe, cancel_all_targets, request_target,
    load_bool, save_bool, load_int, save_int,
    load_list, save_list,
    # Standalone utilities
    ErrorManager,
    # Complex systems
    WindowPositionTracker
)

__version__ = "1.0"

# ============ USER SETTINGS ============
SCAN_INTERVAL = 2.0       # Seconds between backpack scans
MOVE_PAUSE = 0.5          # Pause between item moves
MAX_MOVES_PER_SCAN = 10   # Maximum items to move per scan cycle
MAX_DISTANCE = 8          # Maximum distance to packhorse for transfers
DEBUG = False

# ============ GUI DIMENSIONS ============
WINDOW_WIDTH = 200
COLLAPSED_HEIGHT = 24
NORMAL_HEIGHT = 180

# ============ PERSISTENCE KEYS ============
KEY_PREFIX = "PackySuite_"
PACKY_KEY = KEY_PREFIX + "PackySerial"
ENABLED_KEY = KEY_PREFIX + "Enabled"
SETTINGS_KEY = KEY_PREFIX + "XY"
EXPANDED_KEY = KEY_PREFIX + "Expanded"
ITEMS_KEY = KEY_PREFIX + "WatchedItems"

# ============ RUNTIME STATE ============
packy_serial = 0
enabled = True
is_expanded = True
watched_items = []  # List of graphic IDs (integers) to watch for
script_should_stop = False  # Flag for clean shutdown
pos_tracker = None  # WindowPositionTracker instance

# Error management
errors = ErrorManager(cooldown=5.0)

# Timing
last_scan_time = 0
items_moved_session = 0  # Count of items moved this session

# GUI elements
gump = None
bg = None
titleLabel = None
statusLabel = None
packyLabel = None
itemsLabel = None
enableBtn = None
targetPackyBtn = None
addItemBtn = None
clearItemsBtn = None
expandBtn = None

# ============ UTILITY FUNCTIONS ============
def debug_msg(text):
    """Print debug message to system chat if DEBUG enabled"""
    if DEBUG:
        API.SysMsg("DEBUG: " + text, 88)

def get_packy():
    """Returns the packhorse mobile if valid and in range, None otherwise"""
    if packy_serial == 0:
        return None

    try:
        mob = API.Mobiles.FindMobile(packy_serial)
        if mob is None:
            return None
        if mob.IsDead:
            return None
        return mob
    except Exception as e:
        debug_msg("Error finding packy: " + str(e))
        return None

def save_watched_items():
    """Save watched items list to persistence"""
    # Convert integers to strings for save_list
    items_str = [str(g) for g in watched_items]
    save_list(ITEMS_KEY, items_str)
    debug_msg("Saved " + str(len(watched_items)) + " watched items")

def load_watched_items():
    """Load watched items list from persistence"""
    global watched_items
    items_str = load_list(ITEMS_KEY)
    watched_items = []
    for item in items_str:
        if item:
            try:
                watched_items.append(int(item))
            except ValueError:
                debug_msg("Invalid item graphic: " + item)
    debug_msg("Loaded " + str(len(watched_items)) + " watched items")

def save_expanded_state():
    """Save expanded/collapsed state"""
    save_bool(EXPANDED_KEY, is_expanded)

def load_expanded_state():
    """Load expanded/collapsed state"""
    global is_expanded
    is_expanded = load_bool(EXPANDED_KEY, True)

# ============ EXPAND/COLLAPSE ============
def toggle_expand():
    """Toggle window expanded/collapsed state"""
    global is_expanded

    is_expanded = not is_expanded
    save_expanded_state()

    if is_expanded:
        expand_window()
    else:
        collapse_window()

def expand_window():
    """Expand window to show full content"""
    expandBtn.SetText("[-]")

    # Show main content elements
    statusLabel.IsVisible = True
    packyLabel.IsVisible = True
    itemsLabel.IsVisible = True
    enableBtn.IsVisible = True
    targetPackyBtn.IsVisible = True
    addItemBtn.IsVisible = True
    clearItemsBtn.IsVisible = True

    # Resize window
    x = gump.GetX()
    y = gump.GetY()
    gump.SetRect(x, y, WINDOW_WIDTH, NORMAL_HEIGHT)
    bg.SetRect(0, 0, WINDOW_WIDTH, NORMAL_HEIGHT)

def collapse_window():
    """Collapse window to title bar only"""
    expandBtn.SetText("[+]")

    # Hide all main content
    statusLabel.IsVisible = False
    packyLabel.IsVisible = False
    itemsLabel.IsVisible = False
    enableBtn.IsVisible = False
    targetPackyBtn.IsVisible = False
    addItemBtn.IsVisible = False
    clearItemsBtn.IsVisible = False

    # Resize window
    x = gump.GetX()
    y = gump.GetY()
    gump.SetRect(x, y, WINDOW_WIDTH, COLLAPSED_HEIGHT)
    bg.SetRect(0, 0, WINDOW_WIDTH, COLLAPSED_HEIGHT)

# ============ GUI CALLBACKS (placeholders for later subtasks) ============
def toggle_enabled():
    """Toggle script enabled state"""
    global enabled
    enabled = not enabled
    save_bool(ENABLED_KEY, enabled)
    update_display()
    API.SysMsg("Packy Suite: " + ("ENABLED" if enabled else "DISABLED"), 68 if enabled else 32)

def target_packy():
    """Target packhorse to set as destination"""
    global packy_serial

    API.SysMsg("Target your packhorse...", 68)

    target = request_target(timeout=10)
    if target:
        mob = API.Mobiles.FindMobile(target)
        if not mob:
            API.SysMsg("Invalid target - must be a mobile!", 32)
            return

        packy_serial = target
        save_int(PACKY_KEY, packy_serial)
        debug_msg("Packy serial set to: " + str(packy_serial))
        errors.clear_error()
        update_display()
        API.SysMsg("Packhorse set! Serial: 0x" + format(packy_serial, 'X'), 68)
    else:
        API.SysMsg("Targeting cancelled", 53)

def add_item_type():
    """Add an item type to watch list by targeting an item"""
    global watched_items

    API.SysMsg("Target an item to add to watch list...", 68)

    target = request_target(timeout=10)
    if target:
        item = API.FindItem(target)
        if not item:
            API.SysMsg("Invalid target!", 32)
            return

        graphic = getattr(item, 'Graphic', 0)
        if graphic == 0:
            API.SysMsg("Could not get item graphic!", 32)
            return

        if graphic in watched_items:
            API.SysMsg("Item type already in watch list!", 43)
            return

        watched_items.append(graphic)
        save_watched_items()
        update_display()
        API.SysMsg("Added item type: 0x" + format(graphic, 'X') + " (" + str(len(watched_items)) + " total)", 68)
    else:
        API.SysMsg("Targeting cancelled", 53)

def clear_items():
    """Clear all watched item types"""
    global watched_items
    watched_items = []
    save_watched_items()
    update_display()
    API.SysMsg("Watch list cleared", 68)

def update_display():
    """Update all GUI display elements"""
    if not gump:
        return

    try:
        # Status label
        if enabled:
            if packy_serial == 0:
                statusLabel.SetText("Status: NO PACKY")
            else:
                packy = get_packy()
                if packy:
                    if packy.Distance <= MAX_DISTANCE:
                        statusLabel.SetText("Status: ACTIVE")
                    else:
                        statusLabel.SetText("Status: TOO FAR")
                else:
                    statusLabel.SetText("Status: NOT FOUND")
        else:
            statusLabel.SetText("Status: DISABLED")

        # Packy label
        if packy_serial == 0:
            packyLabel.SetText("Packy: [Not Set]")
        else:
            packy = get_packy()
            if packy:
                packyLabel.SetText("Packy: 0x" + format(packy_serial, 'X')[:6] + " [OK]")
            else:
                packyLabel.SetText("Packy: 0x" + format(packy_serial, 'X')[:6] + " [?]")

        # Items label
        itemsLabel.SetText("Items: " + str(len(watched_items)) + " types | Moved: " + str(items_moved_session))

        # Enable button
        enableBtn.SetText("[" + ("ON" if enabled else "OFF") + "]")
        enableBtn.SetBackgroundHue(68 if enabled else 32)

    except Exception as e:
        API.SysMsg("Error updating display: " + str(e), 32)

# ============ INITIALIZATION ============
packy_serial = load_int(PACKY_KEY, 0)
enabled = load_bool(ENABLED_KEY, True)
load_watched_items()
load_expanded_state()

# ============ BUILD GUI ============
initial_width = WINDOW_WIDTH
initial_height = NORMAL_HEIGHT if is_expanded else COLLAPSED_HEIGHT

gump = API.Gumps.CreateGump()

# Initialize position tracker
pos_tracker = WindowPositionTracker(gump, SETTINGS_KEY, 100, 100)
gump.SetRect(pos_tracker.last_x, pos_tracker.last_y, initial_width, initial_height)

def on_gump_closed():
    """Cleanup when window is closed"""
    global script_should_stop
    try:
        pos_tracker.save()
    except Exception as e:
        API.SysMsg("Error saving position: " + str(e), 32)
    script_should_stop = True  # Signal main loop to stop

API.Gumps.AddControlOnDisposed(gump, on_gump_closed)

# Background
bg = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
bg.SetRect(0, 0, initial_width, initial_height)
gump.Add(bg)

# ============ TITLE BAR ============
titleLabel = API.Gumps.CreateGumpTTFLabel("Packy Suite", 16, "#ffaa00")
titleLabel.SetPos(5, 2)
gump.Add(titleLabel)

expandBtn = API.Gumps.CreateSimpleButton("[-]" if is_expanded else "[+]", 20, 18)
expandBtn.SetPos(WINDOW_WIDTH - 25, 3)
expandBtn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(expandBtn, toggle_expand)
gump.Add(expandBtn)

# ============ MAIN CONTENT ============
leftMargin = 5
y = 26

statusLabel = API.Gumps.CreateGumpTTFLabel("Status: ACTIVE", 15, "#00ff00")
statusLabel.SetPos(leftMargin, y)
statusLabel.IsVisible = is_expanded
gump.Add(statusLabel)

y += 14
packyLabel = API.Gumps.CreateGumpTTFLabel("Packy: [Not Set]", 15, "#ff6666")
packyLabel.SetPos(leftMargin, y)
packyLabel.IsVisible = is_expanded
gump.Add(packyLabel)

y += 14
itemsLabel = API.Gumps.CreateGumpTTFLabel("Items: 0 types | Moved: 0", 15, "#00ff88")
itemsLabel.SetPos(leftMargin, y)
itemsLabel.IsVisible = is_expanded
gump.Add(itemsLabel)

y += 20
# Control buttons
btnW = 90
btnH = 22

enableBtn = API.Gumps.CreateSimpleButton("[ON]", 50, btnH)
enableBtn.SetPos(leftMargin, y)
enableBtn.SetBackgroundHue(68)
enableBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(enableBtn, toggle_enabled)
gump.Add(enableBtn)

targetPackyBtn = API.Gumps.CreateSimpleButton("[Packy]", 65, btnH)
targetPackyBtn.SetPos(leftMargin + 55, y)
targetPackyBtn.SetBackgroundHue(66)
targetPackyBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(targetPackyBtn, target_packy)
gump.Add(targetPackyBtn)

y += 26
addItemBtn = API.Gumps.CreateSimpleButton("[+ Add Item]", btnW, btnH)
addItemBtn.SetPos(leftMargin, y)
addItemBtn.SetBackgroundHue(66)
addItemBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(addItemBtn, add_item_type)
gump.Add(addItemBtn)

clearItemsBtn = API.Gumps.CreateSimpleButton("[Clear]", 55, btnH)
clearItemsBtn.SetPos(leftMargin + btnW + 5, y)
clearItemsBtn.SetBackgroundHue(53)
clearItemsBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(clearItemsBtn, clear_items)
gump.Add(clearItemsBtn)

# Show gump
API.Gumps.AddGump(gump)

# Update display with loaded state
update_display()

# Startup messages
API.SysMsg("Packy Suite v" + __version__ + " loaded!", 68)
if packy_serial > 0:
    API.SysMsg("Packhorse: 0x" + format(packy_serial, 'X'), 66)
else:
    API.SysMsg("Click [Packy] to set your packhorse", 43)
if len(watched_items) > 0:
    API.SysMsg("Watching " + str(len(watched_items)) + " item types", 66)
else:
    API.SysMsg("Click [+ Add Item] to add items to watch", 43)

# ============ MAIN LOOP ============
DISPLAY_UPDATE_INTERVAL = 0.5
next_scan = time.time() + SCAN_INTERVAL
next_display = time.time() + DISPLAY_UPDATE_INTERVAL

while not API.StopRequested and not script_should_stop:
    try:
        API.ProcessCallbacks()

        # Track window position periodically
        pos_tracker.update()

        # Placeholder: main scanning logic will be implemented in later subtask
        # if enabled and time.time() >= next_scan:
        #     scan_and_move_items()
        #     next_scan = time.time() + SCAN_INTERVAL

        if time.time() >= next_display:
            update_display()
            next_display = time.time() + DISPLAY_UPDATE_INTERVAL

        API.Pause(0.1)

    except Exception as e:
        API.SysMsg("Error in main loop: " + str(e), 32)
        debug_msg("Main loop exception: " + str(e))
        API.Pause(1)