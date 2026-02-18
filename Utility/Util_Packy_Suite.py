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
