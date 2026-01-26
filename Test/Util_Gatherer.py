# Util_Gatherer.py
# Mining/Lumberjacking gatherer with AOE harvesting, auto-dump, and combat handling
# Version 1.0
#
# SETUP:
# 1. Set your harvesting tool (pickaxe/hatchet/shovel)
# 2. Set your home runebook and slot
# 3. Set your resource storage bin
#
# FEATURES:
# - AOE self-targeting harvest
# - Auto-convert logs to boards (for lumberjacking)
# - Auto-recall home when weight reaches threshold
# - Auto-pathfind to storage bin and dump resources
# - Three movement modes: Random, Spiral, Stationary
# - Combat detection with flee on low HP
# - Hotkeys: F1 (pause), F2 (emergency recall), TAB (cycle movement)

import API
import time
import random
import math

# ============ CONSTANTS ============

# Tool graphics
PICKAXE_GRAPHIC = 0x0E86
SHOVEL_GRAPHIC = 0x0F39
HATCHET_GRAPHIC = 0x0F43
AXE_GRAPHIC = 0x0F49
DOUBLE_AXE_GRAPHIC = 0x0F4B
TOOL_GRAPHICS = [PICKAXE_GRAPHIC, SHOVEL_GRAPHIC, HATCHET_GRAPHIC, AXE_GRAPHIC, DOUBLE_AXE_GRAPHIC]

# Resource graphics
ORE_GRAPHIC = 0x19B9  # Iron ore pile
INGOT_GRAPHIC = 0x1BF2  # Iron ingots

# All log types (regular, oak, ash, yew, heartwood, bloodwood, frostwood)
LOG_GRAPHICS = [0x1BDD, 0x1BE0, 0x1BE1, 0x1BE2, 0x1BE3, 0x1BE4, 0x1BE5]
BOARD_GRAPHIC = 0x1BD7  # Boards (all types convert to this)

RESOURCE_GRAPHICS = [ORE_GRAPHIC, INGOT_GRAPHIC, BOARD_GRAPHIC] + LOG_GRAPHICS

# Storage shelf settings
STORAGE_SHELF_GUMP_ID = 111922706  # Gump ID for resource storage bin
STORAGE_SHELF_FILL_BUTTON = 121  # Button ID for "fill from backpack"
AUTO_CONVERT_LOGS = True  # Automatically convert logs to boards after gathering

# Timings
GATHER_DELAY = 2.5  # Seconds to complete gather action
MOVE_DELAY = 1.0  # Seconds to complete movement
RECALL_DELAY = 2.0  # Seconds for recall to complete
DUMP_PAUSE = 0.6  # Pause between item moves
COMBAT_CHECK_INTERVAL = 1.0  # Check for hostiles every second
DISPLAY_UPDATE_INTERVAL = 0.5  # Update UI twice per second

# Combat settings
FLEE_HP_THRESHOLD = 50  # Recall home if HP drops below this %
COMBAT_DISTANCE = 10  # Detect enemies within this range
ATTACK_RANGE = 1  # Must be within 1 tile to attack

# Weight settings
DEFAULT_WEIGHT_THRESHOLD = 80  # Return home at 80% capacity
DEFAULT_MAX_WEIGHT = 450  # Fallback if can't read player weight

# Movement settings
MOVE_ON_DEPLETION_ONLY = True  # Only move when resources depleted (recommended for AOE)
GATHERS_PER_MOVE = 999  # Disabled when MOVE_ON_DEPLETION_ONLY is True
RANDOM_MOVE_STEPS_MIN = 6  # Minimum tiles to move randomly
RANDOM_MOVE_STEPS_MAX = 10  # Maximum tiles to move randomly (AOE needs distance)

# Journal messages
DEPLETION_MESSAGES = [
    "There's not enough wood here to harvest",
    "There is no ore here to mine",
    "You can't mine there",
    "Target cannot be seen",
    "You cannot mine so close to another player",
    "Try mining elsewhere",
    "You have no line of sight to that location",
    "That is too far away",
    "You can't use an axe on that",
    "You can't mine that",
    "not enough ore",
    "not enough wood"
]

SUCCESS_MESSAGES = [
    "You chop some",
    "You dig some",
    "You loosen some",
    "and put them in your backpack",
    "and put it in your backpack"
]

COOLDOWN_MESSAGE = "you must wait"  # Followed by number of seconds

# Reagent messages
OUT_OF_REAGENTS_MESSAGES = [
    "Insufficient reagents",
    "More reagents are needed",
    "You do not have enough reagents",
    "You lack the reagents",
    "reagents needed",
    "insufficient mana"
]

# Emergency recall settings
EMERGENCY_RECALL_BUTTON = 10  # Button for runebook emergency charges
RUNEBOOK_GUMP_ID = 89  # Runebook gump ID

# Captcha detection
CAPTCHA_NUMBER_GUMP = 0x968740
CAPTCHA_PICTA_GUMP = 0xd0c93672

# Runebook
RUNEBOOK_GRAPHIC = 0x22C5
GUMP_WAIT_TIME = 3.0
USE_OBJECT_DELAY = 0.5
GUMP_READY_DELAY = 0.3

# UI Colors (hues)
HUE_GREEN = 68
HUE_RED = 32
HUE_YELLOW = 43
HUE_GRAY = 90
HUE_ORANGE = 53

# ============ PERSISTENCE KEYS ============
KEY_PREFIX = "Gatherer_"
KEY_TOOL = KEY_PREFIX + "ToolSerial"
KEY_RUNEBOOK = KEY_PREFIX + "HomeRunebook"
KEY_RUNEBOOK_SLOT = KEY_PREFIX + "HomeSlot"
KEY_STORAGE = KEY_PREFIX + "StorageSerial"
KEY_MOVEMENT_MODE = KEY_PREFIX + "MovementMode"
KEY_WEIGHT_THRESHOLD = KEY_PREFIX + "WeightThreshold"
KEY_HOTKEY_PAUSE = KEY_PREFIX + "HotkeyPause"
KEY_HOTKEY_ESC = KEY_PREFIX + "HotkeyEsc"
KEY_WINDOW_POS = KEY_PREFIX + "WindowXY"
KEY_NUM_SPOTS = KEY_PREFIX + "NumGatheringSpots"
KEY_CURRENT_SPOT = KEY_PREFIX + "CurrentSpotIndex"

# ============ RUNTIME STATE ============

# State machine
STATE = "idle"  # States: idle, gathering, moving, combat, fleeing, converting, pathfinding, dumping, returning
action_start_time = 0
pathfind_start_time = 0
pathfind_timeout = 10.0  # Max seconds to wait for pathfinding
convert_delay = 1.5  # Time to wait for log conversion
flee_start_time = 0
flee_timeout = 15.0  # Max seconds to try fleeing before giving up
flee_distance = 15  # Run this many tiles away from enemy
flee_last_pos_x = 0  # Track position to detect if stuck
flee_last_pos_y = 0
flee_last_move_time = 0  # When we last detected movement
flee_stuck_threshold = 1.5  # If stuck for this many seconds, try new direction

# Pause control
PAUSED = False

# Gather tracking
gather_count = 0  # How many times we've gathered since last move
failed_gather_count = 0  # Failed gather attempts at current spot
MAX_FAILED_GATHERS = 2  # Move after this many failed attempts (no resources)
last_gather_x = 0  # Where we were gathering
last_gather_y = 0
at_home = False  # Track if we're at home or gathering spot

# Resource tracking
ore_count = 0
log_count = 0
session_ore = 0
session_logs = 0
session_dumps = 0
session_start_time = time.time()

# Weight tracking
current_weight = 0
max_weight = DEFAULT_MAX_WEIGHT
weight_pct = 0

# Combat tracking
current_enemy = None
last_combat_check = 0
last_hp_for_flee = 0  # Track HP to detect if being hit while fleeing

# Movement
movement_mode = "random"  # Modes: random, spiral, stationary
spiral_direction = 0  # For spiral pattern: 0=N, 1=E, 2=S, 3=W
spiral_steps = 8  # Steps in current direction (start at 8 for AOE coverage)
spiral_steps_taken = 0  # Steps taken in current direction
spiral_turns = 0  # Turns completed

# Tool/Setup
tool_serial = 0
home_runebook_serial = 0
home_slot = 1  # Slot 1 = home (always)
storage_container_serial = 0

# Gathering spot rotation
num_gathering_spots = 1  # How many gathering spots in runebook (slots 2, 3, 4, etc.)
current_spot_index = 0  # Which spot we're at (0 = slot 2, 1 = slot 3, etc.)

# Hotkeys
hotkey_pause = "F1"
hotkey_esc = "F2"
capturing_hotkey = None  # Which hotkey we're capturing (pause/esc)

# Display
last_display_update = 0

# Emergency charge tracking
used_emergency_charge = False

# ============ GUI REFERENCES ============
gump = None
controls = {}

# ============ UTILITY FUNCTIONS ============

def debug_msg(text, hue=88):
    """Debug message"""
    API.SysMsg("DEBUG: " + text, hue)

def get_tool():
    """Get the configured harvesting tool"""
    if tool_serial == 0:
        return None
    tool = API.FindItem(tool_serial)
    if not tool:
        return None
    return tool

def get_tool_name(tool):
    """Get friendly name for tool"""
    if not tool:
        return "None"
    graphic = tool.Graphic
    if graphic == PICKAXE_GRAPHIC:
        return "Pickaxe"
    elif graphic == SHOVEL_GRAPHIC:
        return "Shovel"
    elif graphic == HATCHET_GRAPHIC:
        return "Hatchet"
    elif graphic in [AXE_GRAPHIC, DOUBLE_AXE_GRAPHIC]:
        return "Axe"
    else:
        return "Tool"

def count_resources(graphic):
    """Count resources in backpack by graphic"""
    try:
        backpack = API.Player.Backpack
        if not backpack:
            return 0

        backpack_serial = backpack.Serial if hasattr(backpack, 'Serial') else 0
        if backpack_serial == 0:
            return 0

        items = API.ItemsInContainer(backpack_serial, True)  # True = recursive
        if not items:
            return 0

        total = 0
        for item in items:
            if hasattr(item, 'Graphic') and item.Graphic == graphic:
                amount = getattr(item, 'Amount', 1)
                total += amount

        return total
    except Exception as e:
        return 0

def update_resource_counts():
    """Update ore and log counts"""
    global ore_count, log_count
    ore_count = count_resources(ORE_GRAPHIC) + count_resources(INGOT_GRAPHIC)

    # Count all log types
    log_count = count_resources(BOARD_GRAPHIC)
    for log_graphic in LOG_GRAPHICS:
        log_count += count_resources(log_graphic)

def update_weight():
    """Update weight tracking"""
    global current_weight, max_weight, weight_pct
    try:
        current_weight = getattr(API.Player, 'Weight', 0)
        max_weight = getattr(API.Player, 'MaxWeight', DEFAULT_MAX_WEIGHT)
        if max_weight > 0:
            weight_pct = (current_weight / max_weight * 100)
        else:
            weight_pct = 0
    except Exception as e:
        current_weight = 0
        max_weight = DEFAULT_MAX_WEIGHT
        weight_pct = 0

def slot_to_button(slot):
    """Convert runebook slot to button ID"""
    return 49 + slot

def check_out_of_reagents():
    """Check journal for out of reagents messages"""
    try:
        for message in OUT_OF_REAGENTS_MESSAGES:
            if API.InJournal(message, False):
                return True
        return False
    except Exception as e:
        return False

def check_for_captcha():
    """Check if a captcha gump is open"""
    try:
        if API.HasGump(CAPTCHA_NUMBER_GUMP):
            return "number"
        elif API.HasGump(CAPTCHA_PICTA_GUMP):
            return "picta"
        return None
    except Exception as e:
        return None

def handle_captcha(captcha_type):
    """Handle captcha detection - recall home and stop script"""
    global PAUSED, STATE

    API.SysMsg("╔════════════════════════════════════╗", HUE_RED)
    API.SysMsg("║   CAPTCHA DETECTED!                ║", HUE_RED)
    API.SysMsg("║   Type: " + captcha_type.upper().ljust(27) + "║", HUE_RED)
    API.SysMsg("║   Recalling home and stopping...   ║", HUE_RED)
    API.SysMsg("╚════════════════════════════════════╝", HUE_RED)

    # Cancel any active pathfinding
    if API.Pathfinding():
        API.CancelPathfinding()

    # Try to recall home
    if not at_home:
        API.SysMsg("Attempting recall home...", HUE_YELLOW)
        if recall_home():
            API.SysMsg("Recalled home successfully", HUE_GREEN)
        else:
            API.SysMsg("Recall failed - stopping anyway", HUE_RED)

    # Stop the script
    API.SysMsg("╔════════════════════════════════════╗", HUE_YELLOW)
    API.SysMsg("║   SCRIPT STOPPING - SOLVE CAPTCHA! ║", HUE_YELLOW)
    API.SysMsg("║   Restart script when ready        ║", HUE_YELLOW)
    API.SysMsg("╚════════════════════════════════════╝", HUE_YELLOW)

    PAUSED = True
    STATE = "idle"
    API.Stop()

def emergency_recall_home():
    """Use runebook emergency charges when out of reagents"""
    global at_home, used_emergency_charge

    if home_runebook_serial == 0:
        API.SysMsg("Home runebook not configured!", HUE_RED)
        return False

    runebook = API.FindItem(home_runebook_serial)
    if not runebook:
        API.SysMsg("Home runebook not found!", HUE_RED)
        return False

    try:
        # Clear journal to check for new messages
        API.ClearJournal()

        # Save position before recall to check if it worked
        pos_before_x = getattr(API.Player, 'X', 0)
        pos_before_y = getattr(API.Player, 'Y', 0)

        API.SysMsg("╔════════════════════════════════════╗", HUE_RED)
        API.SysMsg("║  USING EMERGENCY RUNEBOOK CHARGE!  ║", HUE_RED)
        API.SysMsg("╚════════════════════════════════════╝", HUE_RED)

        API.UseObject(home_runebook_serial)

        # Wait for runebook gump
        while not API.HasGump(RUNEBOOK_GUMP_ID):
            API.Pause(0.1)

        API.Pause(2.70)  # From your recording

        # Click emergency recall button (button 10)
        result = API.ReplyGump(EMERGENCY_RECALL_BUTTON, RUNEBOOK_GUMP_ID)

        if result:
            API.Pause(RECALL_DELAY)

            # Check if we actually moved
            pos_after_x = getattr(API.Player, 'X', 0)
            pos_after_y = getattr(API.Player, 'Y', 0)

            if pos_before_x != pos_after_x or pos_before_y != pos_after_y:
                # Emergency recall succeeded!
                at_home = True
                used_emergency_charge = True  # Flag that we used emergency charge
                API.SysMsg("╔════════════════════════════════════╗", HUE_YELLOW)
                API.SysMsg("║   EMERGENCY RECALL SUCCESSFUL!     ║", HUE_YELLOW)
                API.SysMsg("║   SCRIPT WILL PAUSE AFTER DUMP!    ║", HUE_YELLOW)
                API.SysMsg("║   RESTOCK REAGENTS ASAP!           ║", HUE_YELLOW)
                API.SysMsg("╚════════════════════════════════════╝", HUE_YELLOW)
                API.Pause(1.0)
                return True
            else:
                # Emergency recall also failed (no charges?)
                API.SysMsg("╔════════════════════════════════════╗", HUE_RED)
                API.SysMsg("║  EMERGENCY RECALL FAILED!          ║", HUE_RED)
                API.SysMsg("║  NO CHARGES LEFT IN RUNEBOOK!      ║", HUE_RED)
                API.SysMsg("╚════════════════════════════════════╝", HUE_RED)
                return False
        else:
            API.SysMsg("Failed to click emergency recall button!", HUE_RED)
            return False

    except Exception as e:
        API.SysMsg("Emergency recall error: " + str(e), HUE_RED)
        return False

def check_resource_depletion():
    """Check journal for resource depletion messages"""
    try:
        for message in DEPLETION_MESSAGES:
            if API.InJournal(message, False):
                # Don't clear here - journal is cleared before next gather
                API.SysMsg("DETECTED: " + message, HUE_ORANGE)
                return True
        return False
    except Exception as e:
        return False

def check_gather_success():
    """Check if gather was successful from journal"""
    try:
        for message in SUCCESS_MESSAGES:
            if API.InJournal(message, False):
                API.SysMsg("DEBUG: Found success message: " + message, HUE_GREEN)
                # Don't clear here - journal is cleared before next gather
                return True
        API.SysMsg("DEBUG: No success message found in journal", HUE_GRAY)
        return False
    except Exception as e:
        API.SysMsg("DEBUG: Exception checking success: " + str(e), HUE_RED)
        return False

def parse_cooldown():
    """Try to parse cooldown from journal message"""
    try:
        if API.InJournal(COOLDOWN_MESSAGE, False):
            # TODO: Parse actual seconds from message
            # For now just return default
            return GATHER_DELAY
        return GATHER_DELAY
    except Exception as e:
        return GATHER_DELAY

# ============ PERSISTENCE ============

def save_setting(key, value):
    """Save a single setting"""
    API.SavePersistentVar(key, str(value), API.PersistentVar.Char)

def load_setting(key, default):
    """Load a single setting"""
    return API.GetPersistentVar(key, str(default), API.PersistentVar.Char)

def load_settings():
    """Load all settings from persistence"""
    global tool_serial, home_runebook_serial, home_slot, storage_container_serial
    global movement_mode, hotkey_pause, hotkey_esc
    global num_gathering_spots, current_spot_index

    try:
        tool_serial = int(load_setting(KEY_TOOL, "0"))
        home_runebook_serial = int(load_setting(KEY_RUNEBOOK, "0"))
        home_slot = int(load_setting(KEY_RUNEBOOK_SLOT, "1"))
        storage_container_serial = int(load_setting(KEY_STORAGE, "0"))
        movement_mode = load_setting(KEY_MOVEMENT_MODE, "random")
        hotkey_pause = load_setting(KEY_HOTKEY_PAUSE, "F1")
        hotkey_esc = load_setting(KEY_HOTKEY_ESC, "F2")
        num_gathering_spots = int(load_setting(KEY_NUM_SPOTS, "1"))
        current_spot_index = int(load_setting(KEY_CURRENT_SPOT, "0"))
    except Exception as e:
        API.SysMsg("Error loading settings: " + str(e), HUE_RED)

def save_window_position():
    """Save window position"""
    if gump:
        try:
            x = gump.GetX()
            y = gump.GetY()
            save_setting(KEY_WINDOW_POS, str(x) + "," + str(y))
        except:
            pass

# ============ CORE LOGIC ============

def perform_gather():
    """Perform gather action using AOE self-targeting"""
    global STATE, action_start_time, gather_count, last_gather_x, last_gather_y, at_home

    tool = get_tool()
    if not tool:
        API.SysMsg("No tool configured! Click [SET] to setup.", HUE_RED)
        STATE = "idle"
        return

    try:
        # CRITICAL: Clear journal BEFORE gathering so we only see NEW messages
        API.ClearJournal()

        # Cancel any existing targets
        if API.HasTarget():
            API.CancelTarget()
        API.CancelPreTarget()

        # Pre-target self for AOE gather
        API.PreTarget(API.Player.Serial, "neutral")
        API.Pause(0.1)

        # Use the tool (pass the object, not serial)
        API.UseObject(tool, False)
        API.Pause(0.2)

        # Clean up
        API.CancelPreTarget()

        # Track position
        last_gather_x = getattr(API.Player, 'X', 0)
        last_gather_y = getattr(API.Player, 'Y', 0)

        # Mark that we're at gathering spot, not home
        at_home = False

        # Set state to gathering
        STATE = "gathering"
        action_start_time = time.time()
        gather_count += 1

        API.SysMsg("Gathering... (x" + str(gather_count) + ")", HUE_GREEN)

    except Exception as e:
        API.SysMsg("Gather error: " + str(e), HUE_RED)
        STATE = "idle"

def check_for_hostiles():
    """Check for nearby hostile mobiles"""
    global last_combat_check

    now = time.time()
    if now - last_combat_check < COMBAT_CHECK_INTERVAL:
        return None

    last_combat_check = now

    try:
        notorieties = [API.Notoriety.Enemy]  # Only monsters for now
        enemy = API.NearestMobile(notorieties, COMBAT_DISTANCE)

        if enemy and enemy.Serial != API.Player.Serial:
            if not enemy.IsDead:
                return enemy
    except Exception as e:
        pass

    return None

def handle_combat(enemy):
    """Handle combat encounter"""
    global STATE, current_enemy, flee_start_time, last_hp_for_flee

    try:
        # Check player HP
        player_hp_pct = (API.Player.Hits / API.Player.HitsMax * 100) if API.Player.HitsMax > 0 else 100

        # Flee if HP too low
        if player_hp_pct < FLEE_HP_THRESHOLD:
            API.SysMsg("FLEEING - HP LOW! (" + str(int(player_hp_pct)) + "%)", HUE_RED)
            current_enemy = enemy
            last_hp_for_flee = API.Player.Hits
            flee_start_time = time.time()
            start_flee_from_enemy(enemy)
            return

        # Light combat - attack if close
        current_enemy = enemy
        if enemy.Distance <= ATTACK_RANGE:
            # TODO: Implement attack - API.Attack may not exist
            # For now, just message
            API.SysMsg("Combat: " + str(int(player_hp_pct)) + "% HP", HUE_YELLOW)
            STATE = "combat"
        else:
            STATE = "idle"  # Enemy too far

    except Exception as e:
        STATE = "idle"

def start_flee_from_enemy(enemy):
    """Start fleeing from enemy - run away then recall"""
    global STATE, flee_last_pos_x, flee_last_pos_y, flee_last_move_time

    try:
        player_x = getattr(API.Player, 'X', 0)
        player_y = getattr(API.Player, 'Y', 0)

        # Initialize position tracking
        flee_last_pos_x = player_x
        flee_last_pos_y = player_y
        flee_last_move_time = time.time()

        # Get enemy position if available
        enemy_x = getattr(enemy, 'X', 0) if enemy else 0
        enemy_y = getattr(enemy, 'Y', 0) if enemy else 0

        if player_x == 0 or player_y == 0:
            API.SysMsg("Can't get position - attempting emergency recall", HUE_RED)
            STATE = "fleeing"
            return

        # Calculate flee direction
        if enemy_x > 0 and enemy_y > 0:
            # Run AWAY from enemy
            dx = player_x - enemy_x
            dy = player_y - enemy_y

            # Normalize
            distance = math.sqrt(dx * dx + dy * dy)
            if distance > 0:
                dx = dx / distance
                dy = dy / distance
        else:
            # No enemy position, pick a random direction
            angle = random.uniform(0, 2 * math.pi)
            dx = math.cos(angle)
            dy = math.sin(angle)

        # Calculate target position
        target_x = int(player_x + dx * flee_distance)
        target_y = int(player_y + dy * flee_distance)

        API.SysMsg("Running away from enemy...", HUE_YELLOW)

        # Start pathfinding away
        result = API.Pathfind(target_x, target_y)

        if result:
            STATE = "fleeing"
        else:
            # Pathfind failed, try a random direction
            API.SysMsg("Pathfind failed - trying random direction", HUE_ORANGE)
            angle = random.uniform(0, 2 * math.pi)
            target_x = int(player_x + math.cos(angle) * 10)
            target_y = int(player_y + math.sin(angle) * 10)
            result = API.Pathfind(target_x, target_y)
            STATE = "fleeing"

    except Exception as e:
        API.SysMsg("Flee error: " + str(e), HUE_RED)
        STATE = "fleeing"

def should_dump():
    """Check if we should return home to dump"""
    global weight_pct

    # Don't try to dump if we're already at home
    if at_home:
        return False

    update_weight()

    # Check weight threshold
    threshold = DEFAULT_WEIGHT_THRESHOLD
    try:
        threshold = int(load_setting(KEY_WEIGHT_THRESHOLD, str(DEFAULT_WEIGHT_THRESHOLD)))
    except:
        pass

    if weight_pct >= threshold:
        return True

    return False

def recall_home():
    """Recall to home location (tries emergency charges if out of reagents)"""
    global at_home

    if home_runebook_serial == 0:
        API.SysMsg("Home runebook not configured!", HUE_RED)
        return False

    runebook = API.FindItem(home_runebook_serial)
    if not runebook:
        API.SysMsg("Home runebook not found!", HUE_RED)
        return False

    try:
        # Clear journal before attempting recall
        API.ClearJournal()

        # Save position before recall to check if it worked
        pos_before_x = getattr(API.Player, 'X', 0)
        pos_before_y = getattr(API.Player, 'Y', 0)

        API.SysMsg("Recalling home...", HUE_YELLOW)
        API.UseObject(home_runebook_serial)
        API.Pause(USE_OBJECT_DELAY)

        if not API.WaitForGump(delay=GUMP_WAIT_TIME):
            API.SysMsg("Runebook gump didn't open!", HUE_RED)
            return False

        API.Pause(GUMP_READY_DELAY)

        button_id = slot_to_button(home_slot)
        result = API.ReplyGump(button_id)

        if result:
            # Wait longer for recall to complete (UO can be slow)
            API.Pause(RECALL_DELAY + 2.5)  # Total of ~4.5 seconds

            # Check multiple times if position changed (sometimes takes a moment)
            pos_after_x = getattr(API.Player, 'X', 0)
            pos_after_y = getattr(API.Player, 'Y', 0)

            position_changed = (pos_before_x != pos_after_x or pos_before_y != pos_after_y)

            # Also check journal for out of reagents
            out_of_regs = check_out_of_reagents()

            if position_changed:
                # Position changed - recall succeeded!
                at_home = True
                API.SysMsg("Recalled home!", HUE_GREEN)
                # Extra delay to let everything load before looking for container
                API.Pause(1.0)
                return True
            elif out_of_regs:
                # Position didn't change AND we're out of reagents
                API.SysMsg("OUT OF REAGENTS - Trying emergency charges...", HUE_ORANGE)
                API.Pause(0.5)
                # Try emergency recall
                if emergency_recall_home():
                    # Emergency recall worked
                    return True
                else:
                    # Emergency recall also failed
                    API.SysMsg("Both regular and emergency recall failed!", HUE_RED)
                    return False
            else:
                # Position didn't change but no clear error - might have worked but position not updated yet
                # Wait even longer and check again
                API.Pause(2.0)  # Wait 2 more seconds
                pos_check_x = getattr(API.Player, 'X', 0)
                pos_check_y = getattr(API.Player, 'Y', 0)

                if pos_before_x != pos_check_x or pos_before_y != pos_check_y:
                    # Position changed on second check - recall worked!
                    at_home = True
                    API.SysMsg("Recalled home!", HUE_GREEN)
                    return True
                else:
                    # Still no position change - assume it failed
                    API.SysMsg("Recall appears to have failed (no position change)", HUE_RED)
                    return False
        else:
            API.SysMsg("Failed to click recall button!", HUE_RED)
            return False

    except Exception as e:
        API.SysMsg("Recall error: " + str(e), HUE_RED)
        return False

def recall_to_gathering_spot():
    """Recall to next gathering spot in rotation"""
    global at_home, current_spot_index

    if home_runebook_serial == 0:
        API.SysMsg("Home runebook not configured!", HUE_RED)
        return False

    if num_gathering_spots < 1:
        API.SysMsg("No gathering spots configured!", HUE_RED)
        return False

    runebook = API.FindItem(home_runebook_serial)
    if not runebook:
        API.SysMsg("Home runebook not found!", HUE_RED)
        return False

    try:
        # Clear journal before attempting recall
        API.ClearJournal()

        # Save position before recall to check if it worked
        pos_before_x = getattr(API.Player, 'X', 0)
        pos_before_y = getattr(API.Player, 'Y', 0)

        # Calculate slot number: spot 0 = slot 2, spot 1 = slot 3, etc.
        gathering_slot = 2 + current_spot_index

        API.SysMsg("Recalling to gathering spot " + str(current_spot_index + 1) + "/" + str(num_gathering_spots) + " (slot " + str(gathering_slot) + ")...", HUE_YELLOW)
        API.UseObject(home_runebook_serial)
        API.Pause(USE_OBJECT_DELAY)

        if not API.WaitForGump(delay=GUMP_WAIT_TIME):
            API.SysMsg("Runebook gump didn't open!", HUE_RED)
            return False

        API.Pause(GUMP_READY_DELAY)

        button_id = slot_to_button(gathering_slot)
        result = API.ReplyGump(button_id)

        if result:
            # Wait longer for recall to complete (UO can be slow)
            API.Pause(RECALL_DELAY + 2.5)  # Total of ~4.5 seconds

            # Check if we actually moved (recall succeeded)
            pos_after_x = getattr(API.Player, 'X', 0)
            pos_after_y = getattr(API.Player, 'Y', 0)

            position_changed = (pos_before_x != pos_after_x or pos_before_y != pos_after_y)
            out_of_regs = check_out_of_reagents()

            if position_changed:
                # Position changed - recall succeeded!
                at_home = False  # Mark that we're at gathering spot
                API.SysMsg("Recalled to gathering spot!", HUE_GREEN)
                # Extra delay to let everything load
                API.Pause(1.0)

                # Move to next spot for next dump cycle (wrap around)
                current_spot_index = (current_spot_index + 1) % num_gathering_spots
                save_setting(KEY_CURRENT_SPOT, current_spot_index)

                return True
            elif out_of_regs:
                # Out of reagents detected
                API.SysMsg("╔════════════════════════════════════╗", HUE_RED)
                API.SysMsg("║  OUT OF REAGENTS!                  ║", HUE_RED)
                API.SysMsg("║  Cannot recall to gathering spot   ║", HUE_RED)
                API.SysMsg("║  Restock reagents and try again    ║", HUE_RED)
                API.SysMsg("╚════════════════════════════════════╝", HUE_RED)
                return False
            else:
                # Position didn't change - wait even longer and check again
                API.Pause(2.0)  # Wait 2 more seconds
                pos_check_x = getattr(API.Player, 'X', 0)
                pos_check_y = getattr(API.Player, 'Y', 0)

                if pos_before_x != pos_check_x or pos_before_y != pos_check_y:
                    # Position changed on second check - recall worked!
                    at_home = False
                    API.SysMsg("Recalled to gathering spot!", HUE_GREEN)

                    # Move to next spot for next dump cycle
                    current_spot_index = (current_spot_index + 1) % num_gathering_spots
                    save_setting(KEY_CURRENT_SPOT, current_spot_index)

                    return True
                else:
                    API.SysMsg("Recall to gathering spot failed (no position change)", HUE_RED)
                    return False
        else:
            API.SysMsg("Failed to click recall button!", HUE_RED)
            return False

    except Exception as e:
        API.SysMsg("Recall to gathering spot error: " + str(e), HUE_RED)
        return False

def emergency_hotkey_recall():
    """Emergency recall - ESC hotkey (no flee, just try to recall)"""
    global STATE
    API.SysMsg("EMERGENCY RECALL (ESC key)!", HUE_RED)
    # Cancel any active pathfinding
    if API.Pathfinding():
        API.CancelPathfinding()
    if recall_home():
        STATE = "dumping"  # Go straight to dump
    else:
        API.SysMsg("Emergency recall failed! Try again or move to safety.", HUE_RED)

def convert_logs_to_boards():
    """Convert ALL log types in backpack to boards using hatchet"""
    tool = get_tool()
    if not tool:
        return False

    # Only convert if we have a hatchet/axe
    if tool.Graphic not in [HATCHET_GRAPHIC, AXE_GRAPHIC, DOUBLE_AXE_GRAPHIC]:
        return False  # Not a woodcutting tool

    try:
        backpack = API.Player.Backpack
        if not backpack:
            return False

        items = API.ItemsInContainer(backpack.Serial, True)
        if not items:
            return False

        logs_found = 0
        # Check for ALL log types (regular, oak, ash, yew, heartwood, bloodwood, frostwood)
        for item in items:
            if hasattr(item, 'Graphic') and item.Graphic in LOG_GRAPHICS:
                logs_found += 1

                # Cancel any existing targets
                if API.HasTarget():
                    API.CancelTarget()
                API.CancelPreTarget()

                # Pre-target the logs
                API.PreTarget(item.Serial, "neutral")
                API.Pause(0.1)

                # Use hatchet on the logs (pass object, not serial)
                API.UseObject(tool, False)
                API.Pause(0.6)  # Wait for conversion

                # Clean up
                API.CancelPreTarget()

        if logs_found > 0:
            API.SysMsg("Converted " + str(logs_found) + " log stacks to boards", HUE_GREEN)
            return True

        return False

    except Exception as e:
        API.SysMsg("Board conversion error: " + str(e), HUE_RED)
        return False

def pathfind_to_container():
    """Pathfind to storage container"""
    global STATE, pathfind_start_time

    if storage_container_serial == 0:
        API.SysMsg("Storage container not configured!", HUE_RED)
        return False

    container = API.FindItem(storage_container_serial)
    if not container:
        API.SysMsg("Storage container not found!", HUE_RED)
        return False

    try:
        # Get container position
        container_x = getattr(container, 'X', 0)
        container_y = getattr(container, 'Y', 0)

        if container_x == 0 or container_y == 0:
            API.SysMsg("Can't get container position!", HUE_RED)
            return False

        # Check distance
        player_x = getattr(API.Player, 'X', 0)
        player_y = getattr(API.Player, 'Y', 0)
        distance = abs(container_x - player_x) + abs(container_y - player_y)

        API.SysMsg("Pathfinding to container (" + str(distance) + " tiles away)...", HUE_YELLOW)

        # Start pathfinding (distance=2 means stop 2 tiles away)
        result = API.PathfindEntity(storage_container_serial, 2)

        if result:
            STATE = "pathfinding"
            pathfind_start_time = time.time()
            return True
        else:
            API.SysMsg("Pathfind failed - walking manually", HUE_YELLOW)
            # Try to move closer manually
            return False

    except Exception as e:
        API.SysMsg("Pathfind error: " + str(e), HUE_RED)
        return False

def dump_resources():
    """Dump all resources into storage bin - boards should already be converted"""
    if storage_container_serial == 0:
        API.SysMsg("Storage container not configured!", HUE_RED)
        return False

    # Add small delay to ensure we're fully loaded after recall
    API.Pause(0.5)

    container = API.FindItem(storage_container_serial)
    if not container:
        API.SysMsg("Storage container not found! Serial: 0x" + hex(storage_container_serial)[2:].upper(), HUE_RED)
        API.SysMsg("Make sure you're at home and container is visible!", HUE_YELLOW)
        return False

    # Check if we're close enough to container
    distance = getattr(container, 'Distance', 99)
    if distance > 3:
        API.SysMsg("Too far from container! Distance: " + str(distance), HUE_RED)
        return False

    try:
        # Check if we have anything to dump
        update_resource_counts()
        if ore_count == 0 and log_count == 0:
            API.SysMsg("No resources to dump", HUE_YELLOW)
            return True

        # Use your recorded pattern:
        # API.UseObject(0x40BB574C)
        # while not API.HasGump(111922706):
        #     API.Pause(0.1)
        # API.Pause(1.65)
        # API.ReplyGump(121, 0x06ABCE12)

        API.SysMsg("Opening resource storage bin...", HUE_YELLOW)
        API.UseObject(storage_container_serial)

        # Wait for the specific resource bin gump to appear
        while not API.HasGump(STORAGE_SHELF_GUMP_ID):
            API.Pause(0.1)

        # Wait a moment for gump to fully load (from your recording)
        API.Pause(1.65)

        # Click "fill from backpack" button (button 121)
        API.SysMsg("Clicking 'fill from backpack'...", HUE_YELLOW)
        result = API.ReplyGump(STORAGE_SHELF_FILL_BUTTON, STORAGE_SHELF_GUMP_ID)

        if result:
            API.Pause(2.0)  # Wait for shelf to process items

            # Close the gump if still open
            if API.HasGump(STORAGE_SHELF_GUMP_ID):
                API.CloseGump(STORAGE_SHELF_GUMP_ID)
                API.Pause(0.3)

            API.SysMsg("Resources dumped into storage bin!", HUE_GREEN)
            return True
        else:
            API.SysMsg("Failed to click bin button!", HUE_RED)
            return False

    except Exception as e:
        API.SysMsg("Dump error: " + str(e), HUE_RED)
        return False

# ============ MOVEMENT PATTERNS ============

def check_movement(force=False):
    """Check if we should move, and execute movement pattern"""
    global gather_count, failed_gather_count

    # Only move if forced (depletion/failed attempts) or gather count reached
    should_move = force or (gather_count >= GATHERS_PER_MOVE and not MOVE_ON_DEPLETION_ONLY)

    # In stationary mode, only move if forced (depleted or too many failures)
    if movement_mode == "stationary" and not force:
        return  # Don't move on regular gather count in stationary mode

    if should_move:
        if force:
            API.SysMsg("Moving to new spot (depleted or failed)", HUE_YELLOW)
        else:
            API.SysMsg("Triggering movement after " + str(GATHERS_PER_MOVE) + " gathers", HUE_GRAY)

        gather_count = 0  # Reset counter
        failed_gather_count = 0  # Reset failed counter when moving

        success = False
        if movement_mode == "random":
            success = move_random()  # This sets STATE to "moving" internally
        elif movement_mode == "spiral":
            success = move_spiral()  # This sets STATE to "moving" internally
        elif movement_mode == "stationary":
            # Forced movement in stationary mode - use random
            API.SysMsg("Stationary mode: forced to move, using random pattern", HUE_YELLOW)
            success = move_random()

        if not success:
            API.SysMsg("Movement failed - will retry after failed attempts", HUE_YELLOW)

def move_random():
    """Move randomly - 6-10 tiles for AOE harvest clearance using pathfinding"""
    global STATE, action_start_time

    try:
        # Get current position
        player_x = getattr(API.Player, 'X', 0)
        player_y = getattr(API.Player, 'Y', 0)

        if player_x == 0 or player_y == 0:
            API.SysMsg("Can't get player position!", HUE_RED)
            return False

        # Calculate random direction and distance
        distance = random.randint(RANDOM_MOVE_STEPS_MIN, RANDOM_MOVE_STEPS_MAX)

        # Random angle in radians
        angle = random.uniform(0, 2 * math.pi)

        # Calculate target position
        target_x = int(player_x + distance * math.cos(angle))
        target_y = int(player_y + distance * math.sin(angle))

        # Direction name for display
        directions = ["North", "Northeast", "East", "Southeast", "South", "Southwest", "West", "Northwest"]
        direction_index = int(((angle + math.pi/8) % (2*math.pi)) / (math.pi/4))
        direction_name = directions[direction_index]

        API.SysMsg("Moving " + direction_name + " (" + str(distance) + " tiles)", HUE_YELLOW)

        # Start pathfinding to target location
        result = API.Pathfind(target_x, target_y)

        if result:
            STATE = "moving"
            action_start_time = time.time()
            return True
        else:
            API.SysMsg("Pathfind failed - trying alternate location", HUE_YELLOW)
            # Try a closer location if pathfind fails
            target_x = int(player_x + 4 * math.cos(angle))
            target_y = int(player_y + 4 * math.sin(angle))
            result = API.Pathfind(target_x, target_y)
            if result:
                STATE = "moving"
                action_start_time = time.time()
                return True
            return False

    except Exception as e:
        API.SysMsg("Move error: " + str(e), HUE_RED)
        return False

def move_spiral():
    """Move in spiral pattern using pathfinding"""
    global spiral_direction, spiral_steps, spiral_steps_taken, spiral_turns, STATE, action_start_time

    try:
        # Get current position
        player_x = getattr(API.Player, 'X', 0)
        player_y = getattr(API.Player, 'Y', 0)

        if player_x == 0 or player_y == 0:
            API.SysMsg("Can't get player position!", HUE_RED)
            return False

        # Calculate target position based on spiral direction
        # 0=North, 1=East, 2=South, 3=West
        target_x = player_x
        target_y = player_y

        if spiral_direction == 0:  # North
            target_y = player_y - spiral_steps
        elif spiral_direction == 1:  # East
            target_x = player_x + spiral_steps
        elif spiral_direction == 2:  # South
            target_y = player_y + spiral_steps
        elif spiral_direction == 3:  # West
            target_x = player_x - spiral_steps

        directions = ["North", "East", "South", "West"]
        direction_name = directions[spiral_direction]

        API.SysMsg("Spiral: moving " + direction_name + " (" + str(spiral_steps) + " tiles)", HUE_YELLOW)

        # Start pathfinding
        result = API.Pathfind(target_x, target_y)

        if result:
            STATE = "moving"
            action_start_time = time.time()

            # Update spiral state for next move
            spiral_steps_taken = spiral_steps  # Mark this leg complete
            spiral_direction = (spiral_direction + 1) % 4  # Turn right
            spiral_turns += 1

            # Increase steps every 2 turns (expanding spiral)
            if spiral_turns % 2 == 0:
                spiral_steps += 1

            return True
        else:
            API.SysMsg("Spiral pathfind failed!", HUE_RED)
            return False

    except Exception as e:
        API.SysMsg("Spiral move error: " + str(e), HUE_RED)
        return False

# ============ GUI SETUP CALLBACKS ============

def on_set_tool():
    """Prompt user to target harvesting tool"""
    global tool_serial
    API.SysMsg("Target your harvesting tool (pickaxe/hatchet/shovel)...", HUE_YELLOW)

    try:
        if API.HasTarget():
            API.CancelTarget()
        API.CancelPreTarget()

        target = API.RequestTarget(timeout=15)

        if target:
            item = API.FindItem(target)
            if item and item.Graphic in TOOL_GRAPHICS:
                tool_serial = target
                save_setting(KEY_TOOL, tool_serial)
                API.SysMsg("Tool set! " + get_tool_name(item), HUE_GREEN)
                update_display()
            else:
                API.SysMsg("That's not a valid harvesting tool!", HUE_RED)
    except Exception as e:
        API.SysMsg("Tool setup error: " + str(e), HUE_RED)

def on_set_home():
    """Prompt user to target home runebook and enter slot"""
    global home_runebook_serial, home_slot
    API.SysMsg("Target your home runebook...", HUE_YELLOW)

    try:
        if API.HasTarget():
            API.CancelTarget()
        API.CancelPreTarget()

        target = API.RequestTarget(timeout=15)

        if target:
            item = API.FindItem(target)
            if item:
                home_runebook_serial = target
                save_setting(KEY_RUNEBOOK, home_runebook_serial)
                API.SysMsg("Runebook set! Now enter slot (1-16) in chat", HUE_GREEN)
                # For now, default to slot 1 - TODO: Add slot input to UI
                home_slot = 1
                save_setting(KEY_RUNEBOOK_SLOT, home_slot)
                update_display()
            else:
                API.SysMsg("Item not found!", HUE_RED)
    except Exception as e:
        API.SysMsg("Runebook setup error: " + str(e), HUE_RED)

def on_set_storage():
    """Prompt user to target storage container"""
    global storage_container_serial
    API.SysMsg("Target your resource storage container...", HUE_YELLOW)

    try:
        if API.HasTarget():
            API.CancelTarget()
        API.CancelPreTarget()

        target = API.RequestTarget(timeout=15)

        if target:
            item = API.FindItem(target)
            if item:
                storage_container_serial = target
                save_setting(KEY_STORAGE, storage_container_serial)
                API.SysMsg("Storage container set!", HUE_GREEN)
                update_display()
            else:
                API.SysMsg("Item not found!", HUE_RED)
    except Exception as e:
        API.SysMsg("Storage setup error: " + str(e), HUE_RED)

def adjust_spots(delta):
    """Adjust number of gathering spots by +1 or -1"""
    global num_gathering_spots, current_spot_index

    # Calculate new value
    new_spots = num_gathering_spots + delta

    # Validate range (1-15, since slot 1 is home and slot 16 is max)
    if new_spots < 1:
        API.SysMsg("Minimum 1 spot!", HUE_RED)
        return
    if new_spots > 15:
        API.SysMsg("Maximum 15 spots!", HUE_RED)
        return

    # Apply the setting
    num_gathering_spots = new_spots
    save_setting(KEY_NUM_SPOTS, num_gathering_spots)

    # Reset current spot index to 0 when changing number of spots
    current_spot_index = 0
    save_setting(KEY_CURRENT_SPOT, current_spot_index)

    API.SysMsg("Number of gathering spots set to " + str(num_gathering_spots), HUE_GREEN)
    API.SysMsg("Will cycle through runebook slots 2-" + str(num_gathering_spots + 1), HUE_YELLOW)
    update_display()

def toggle_movement_mode():
    """Cycle through movement modes"""
    global movement_mode

    modes = ["random", "spiral", "stationary"]
    current_index = modes.index(movement_mode)
    next_index = (current_index + 1) % len(modes)
    movement_mode = modes[next_index]

    save_setting(KEY_MOVEMENT_MODE, movement_mode)
    API.SysMsg("Movement mode: " + movement_mode.upper(), HUE_YELLOW)
    update_display()

def test_pathfind_to_storage():
    """Test button - pathfind to storage container"""
    if storage_container_serial == 0:
        API.SysMsg("Storage container not configured! Click [SET] first.", HUE_RED)
        return

    container = API.FindItem(storage_container_serial)
    if not container:
        API.SysMsg("Storage container not found!", HUE_RED)
        return

    distance = getattr(container, 'Distance', 99)
    API.SysMsg("Container is " + str(distance) + " tiles away", HUE_YELLOW)

    if distance <= 3:
        API.SysMsg("Already close enough to container!", HUE_GREEN)
        return

    # Start pathfinding
    if pathfind_to_container():
        API.SysMsg("Pathfinding started - watch your character move!", HUE_GREEN)
    else:
        API.SysMsg("Pathfinding failed!", HUE_RED)

def test_convert_logs():
    """Test button - convert logs to boards"""
    tool = get_tool()
    if not tool:
        API.SysMsg("No tool configured! Click [SET] first.", HUE_RED)
        return

    if tool.Graphic not in [HATCHET_GRAPHIC, AXE_GRAPHIC, DOUBLE_AXE_GRAPHIC]:
        API.SysMsg("Tool is not a hatchet/axe! Can't convert logs.", HUE_RED)
        return

    # Count all log types
    log_count_before = 0
    for log_graphic in LOG_GRAPHICS:
        log_count_before += count_resources(log_graphic)

    if log_count_before == 0:
        API.SysMsg("No logs in backpack to convert!", HUE_YELLOW)
        return

    API.SysMsg("Converting " + str(log_count_before) + " logs to boards...", HUE_YELLOW)

    if convert_logs_to_boards():
        # Count boards after
        board_count_after = count_resources(BOARD_GRAPHIC)
        API.SysMsg("Conversion complete! Boards: " + str(board_count_after), HUE_GREEN)
    else:
        API.SysMsg("Conversion failed!", HUE_RED)

def toggle_pause():
    """Toggle pause state"""
    global PAUSED, at_home

    PAUSED = not PAUSED

    # Cancel any active pathfinding when pausing
    if PAUSED and API.Pathfinding():
        API.CancelPathfinding()

    if PAUSED:
        API.SysMsg("PAUSED", HUE_YELLOW)
    else:
        # Resuming - if at home, warn them
        if at_home:
            API.SysMsg("WARNING: Still at home! Recall to gathering spot first!", HUE_RED)
            PAUSED = True  # Keep paused
        else:
            API.SysMsg("RESUMED - Gathering", HUE_GREEN)

    update_display()

def resume_gathering():
    """Resume gathering - automatically recalls to next gathering spot"""
    global PAUSED, at_home

    if not PAUSED:
        API.SysMsg("Already running!", HUE_YELLOW)
        return

    if not at_home:
        API.SysMsg("Not at home! Can't resume.", HUE_RED)
        return

    # Show which spot we're going to BEFORE recalling (since recall_to_gathering_spot increments the index)
    next_spot = current_spot_index + 1
    next_slot = 2 + current_spot_index

    # Recall to next gathering spot
    if recall_to_gathering_spot():
        # Successfully recalled - unpause and continue
        PAUSED = False
        API.SysMsg("RESUMED - Gathering at spot " + str(next_spot) + "/" + str(num_gathering_spots) + " (slot " + str(next_slot) + ")", HUE_GREEN)
        update_display()
    else:
        # Recall failed - stay paused
        API.SysMsg("Failed to recall to gathering spot!", HUE_RED)

# ============ DISPLAY UPDATES ============

def update_display():
    """Update UI labels"""
    if not gump or not controls:
        return

    try:
        # Tool display
        tool = get_tool()
        tool_text = get_tool_name(tool) if tool else "Not Set"
        if "tool_label" in controls:
            controls["tool_label"].SetText("Tool: " + tool_text)

        # Runebook display
        runebook_text = "Not Set"
        if home_runebook_serial > 0:
            runebook_text = "Slot " + str(home_slot)
            if num_gathering_spots > 1 and not at_home:
                # Show which gathering spot we're at (calculate backwards from where we'll go NEXT)
                # current_spot_index points to NEXT spot, so we were just at (current_spot_index - 1)
                prev_spot_index = (current_spot_index - 1) % num_gathering_spots
                gathering_spot_display = str(prev_spot_index + 1) + "/" + str(num_gathering_spots)
                runebook_text += " | Spot " + gathering_spot_display
        if "runebook_label" in controls:
            controls["runebook_label"].SetText("Home: " + runebook_text)

        # Storage display
        storage_text = "Not Set"
        if storage_container_serial > 0:
            storage_text = "0x" + hex(storage_container_serial)[2:].upper()
        if "storage_label" in controls:
            controls["storage_label"].SetText("Storage: " + storage_text)

        # Spots display
        if "spots_display" in controls:
            controls["spots_display"].SetText(str(num_gathering_spots))

        # Resources
        if "resources_label" in controls:
            controls["resources_label"].SetText("Ore: " + str(ore_count) + " | Logs: " + str(log_count))

        # Weight
        if "weight_label" in controls:
            weight_text = str(int(current_weight)) + "/" + str(int(max_weight)) + " (" + str(int(weight_pct)) + "%)"
            controls["weight_label"].SetText("Weight: " + weight_text)

        # State
        if "state_label" in controls:
            state_text = STATE.upper()
            if STATE == "gathering":
                if MOVE_ON_DEPLETION_ONLY:
                    state_text += " (x" + str(gather_count) + ")"
                    if failed_gather_count > 0:
                        state_text += " [" + str(failed_gather_count) + " failed]"
                else:
                    state_text += " (" + str(gather_count) + "/" + str(GATHERS_PER_MOVE) + ")"
            elif STATE == "pathfinding":
                state_text += " (to container)"
            controls["state_label"].SetText("State: " + state_text)

        # Movement mode buttons
        if "move_random_btn" in controls:
            controls["move_random_btn"].SetBackgroundHue(HUE_GREEN if movement_mode == "random" else HUE_GRAY)
        if "move_spiral_btn" in controls:
            controls["move_spiral_btn"].SetBackgroundHue(HUE_GREEN if movement_mode == "spiral" else HUE_GRAY)
        if "move_stay_btn" in controls:
            controls["move_stay_btn"].SetBackgroundHue(HUE_GREEN if movement_mode == "stationary" else HUE_GRAY)

        # Pause status
        if "status_label" in controls:
            if PAUSED and at_home:
                controls["status_label"].SetText("[AT HOME]")
                controls["status_label"].SetColor("#ffaa00")
            else:
                controls["status_label"].SetText("[PAUSED]" if PAUSED else "[ACTIVE]")
                controls["status_label"].SetColor("#ff0000" if PAUSED else "#00ff00")

        # Resume button (highlight when needed, gray out when not)
        if "resume_btn" in controls:
            if PAUSED and at_home:
                controls["resume_btn"].SetBackgroundHue(HUE_GREEN)
                controls["resume_btn"].SetText("RESUME")
            else:
                controls["resume_btn"].SetBackgroundHue(HUE_GRAY)
                controls["resume_btn"].SetText("---")

    except Exception as e:
        pass

# ============ CLEANUP ============

def cleanup():
    """Cleanup on script stop"""
    save_window_position()

def on_gump_closed():
    """Handle gump close"""
    cleanup()

# ============ BUILD GUI ============

def build_gump():
    """Build the main UI gump"""
    global gump, controls

    # Load window position
    saved_pos = load_setting(KEY_WINDOW_POS, "100,100")
    pos_parts = saved_pos.split(',')
    x, y = int(pos_parts[0]), int(pos_parts[1])

    # Create gump
    gump = API.Gumps.CreateGump()
    gump.SetRect(x, y, 340, 472)

    # Add background
    bg = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
    bg.SetRect(0, 0, 340, 472)
    gump.Add(bg)

    y_offset = 10

    # Title bar
    titleLabel = API.Gumps.CreateGumpTTFLabel("GATHERER v1.0", 14, "#ffaa00")
    titleLabel.SetPos(10, y_offset)
    gump.Add(titleLabel)

    controls["status_label"] = API.Gumps.CreateGumpTTFLabel("[ACTIVE]", 11, "#00ff00")
    controls["status_label"].SetPos(200, y_offset)
    gump.Add(controls["status_label"])

    # Resume button (shows after dump)
    controls["resume_btn"] = API.Gumps.CreateSimpleButton("RESUME", 100, 22)
    controls["resume_btn"].SetPos(120, y_offset + 20)
    gump.Add(controls["resume_btn"])
    API.Gumps.AddControlOnClick(controls["resume_btn"], resume_gathering)

    y_offset += 20  # Extra space for resume button row

    # Setup section
    controls["tool_label"] = API.Gumps.CreateGumpTTFLabel("Tool: Not Set", 11, "#ffffff")
    controls["tool_label"].SetPos(10, y_offset)
    gump.Add(controls["tool_label"])

    tool_btn = API.Gumps.CreateSimpleButton("SET", 50, 20)
    tool_btn.SetPos(210, y_offset - 2)
    gump.Add(tool_btn)
    API.Gumps.AddControlOnClick(tool_btn, on_set_tool)

    # Test convert logs button
    convert_btn = API.Gumps.CreateSimpleButton("CONV", 50, 20)
    convert_btn.SetPos(270, y_offset - 2)
    gump.Add(convert_btn)
    API.Gumps.AddControlOnClick(convert_btn, test_convert_logs)

    y_offset += 22

    controls["runebook_label"] = API.Gumps.CreateGumpTTFLabel("Home: Not Set", 11, "#ffffff")
    controls["runebook_label"].SetPos(10, y_offset)
    gump.Add(controls["runebook_label"])

    home_btn = API.Gumps.CreateSimpleButton("SET", 50, 20)
    home_btn.SetPos(270, y_offset - 2)
    gump.Add(home_btn)
    API.Gumps.AddControlOnClick(home_btn, on_set_home)

    y_offset += 22

    # Number of gathering spots - use buttons instead of text input
    spots_label = API.Gumps.CreateGumpTTFLabel("# Spots:", 11, "#ffffff")
    spots_label.SetPos(10, y_offset)
    gump.Add(spots_label)

    controls["spots_display"] = API.Gumps.CreateGumpTTFLabel(str(num_gathering_spots), 11, "#00ff00")
    controls["spots_display"].SetPos(70, y_offset)
    gump.Add(controls["spots_display"])

    spots_minus_btn = API.Gumps.CreateSimpleButton("-", 25, 20)
    spots_minus_btn.SetPos(100, y_offset - 2)
    gump.Add(spots_minus_btn)
    API.Gumps.AddControlOnClick(spots_minus_btn, lambda: adjust_spots(-1))

    spots_plus_btn = API.Gumps.CreateSimpleButton("+", 25, 20)
    spots_plus_btn.SetPos(130, y_offset - 2)
    gump.Add(spots_plus_btn)
    API.Gumps.AddControlOnClick(spots_plus_btn, lambda: adjust_spots(1))

    spots_help = API.Gumps.CreateGumpTTFLabel("(Slots 2+)", 9, "#888888")
    spots_help.SetPos(160, y_offset + 2)
    gump.Add(spots_help)

    y_offset += 22

    controls["storage_label"] = API.Gumps.CreateGumpTTFLabel("Storage: Not Set", 11, "#ffffff")
    controls["storage_label"].SetPos(10, y_offset)
    gump.Add(controls["storage_label"])

    storage_btn = API.Gumps.CreateSimpleButton("SET", 50, 20)
    storage_btn.SetPos(210, y_offset - 2)
    gump.Add(storage_btn)
    API.Gumps.AddControlOnClick(storage_btn, on_set_storage)

    # Test pathfind button
    test_pathfind_btn = API.Gumps.CreateSimpleButton("TEST", 50, 20)
    test_pathfind_btn.SetPos(270, y_offset - 2)
    gump.Add(test_pathfind_btn)
    API.Gumps.AddControlOnClick(test_pathfind_btn, test_pathfind_to_storage)

    y_offset += 30

    # Movement mode section
    mode_label = API.Gumps.CreateGumpTTFLabel("Movement:", 11, "#ffffff")
    mode_label.SetPos(10, y_offset)
    gump.Add(mode_label)

    controls["move_random_btn"] = API.Gumps.CreateSimpleButton("Random", 70, 20)
    controls["move_random_btn"].SetPos(90, y_offset - 2)
    gump.Add(controls["move_random_btn"])
    API.Gumps.AddControlOnClick(controls["move_random_btn"], lambda: set_movement("random"))

    controls["move_spiral_btn"] = API.Gumps.CreateSimpleButton("Spiral", 70, 20)
    controls["move_spiral_btn"].SetPos(165, y_offset - 2)
    gump.Add(controls["move_spiral_btn"])
    API.Gumps.AddControlOnClick(controls["move_spiral_btn"], lambda: set_movement("spiral"))

    controls["move_stay_btn"] = API.Gumps.CreateSimpleButton("Stay", 70, 20)
    controls["move_stay_btn"].SetPos(240, y_offset - 2)
    gump.Add(controls["move_stay_btn"])
    API.Gumps.AddControlOnClick(controls["move_stay_btn"], lambda: set_movement("stationary"))

    y_offset += 30

    # Status section
    controls["resources_label"] = API.Gumps.CreateGumpTTFLabel("Ore: 0 | Logs: 0", 11, "#ffffff")
    controls["resources_label"].SetPos(10, y_offset)
    gump.Add(controls["resources_label"])

    y_offset += 18

    controls["weight_label"] = API.Gumps.CreateGumpTTFLabel("Weight: 0/450 (0%)", 11, "#ffffff")
    controls["weight_label"].SetPos(10, y_offset)
    gump.Add(controls["weight_label"])

    y_offset += 18

    controls["state_label"] = API.Gumps.CreateGumpTTFLabel("State: IDLE", 11, "#ffffff")
    controls["state_label"].SetPos(10, y_offset)
    gump.Add(controls["state_label"])

    y_offset += 30

    # Session stats
    stats_title = API.Gumps.CreateGumpTTFLabel("Session Stats:", 11, "#ffaa00")
    stats_title.SetPos(10, y_offset)
    gump.Add(stats_title)

    y_offset += 18

    controls["session_ore_label"] = API.Gumps.CreateGumpTTFLabel("Total Ore: 0", 11, "#aaaaaa")
    controls["session_ore_label"].SetPos(15, y_offset)
    gump.Add(controls["session_ore_label"])

    y_offset += 16

    controls["session_logs_label"] = API.Gumps.CreateGumpTTFLabel("Total Logs: 0", 11, "#aaaaaa")
    controls["session_logs_label"].SetPos(15, y_offset)
    gump.Add(controls["session_logs_label"])

    y_offset += 16

    controls["session_dumps_label"] = API.Gumps.CreateGumpTTFLabel("Dumps: 0", 11, "#aaaaaa")
    controls["session_dumps_label"].SetPos(15, y_offset)
    gump.Add(controls["session_dumps_label"])

    y_offset += 16

    controls["session_runtime_label"] = API.Gumps.CreateGumpTTFLabel("Runtime: 0m", 11, "#aaaaaa")
    controls["session_runtime_label"].SetPos(15, y_offset)
    gump.Add(controls["session_runtime_label"])

    y_offset += 25

    # Hotkeys
    hotkeys_title = API.Gumps.CreateGumpTTFLabel("Hotkeys:", 11, "#ffaa00")
    hotkeys_title.SetPos(10, y_offset)
    gump.Add(hotkeys_title)

    y_offset += 18

    pause_label = API.Gumps.CreateGumpTTFLabel("PAUSE: [" + hotkey_pause + "]", 11, "#aaaaaa")
    pause_label.SetPos(15, y_offset)
    gump.Add(pause_label)

    y_offset += 16

    esc_label = API.Gumps.CreateGumpTTFLabel("ESC Home: [" + hotkey_esc + "]", 11, "#aaaaaa")
    esc_label.SetPos(15, y_offset)
    gump.Add(esc_label)

    y_offset += 16

    tab_label = API.Gumps.CreateGumpTTFLabel("Cycle Mode: [TAB]", 11, "#aaaaaa")
    tab_label.SetPos(15, y_offset)
    gump.Add(tab_label)

    # Close callback
    API.Gumps.AddControlOnDisposed(gump, on_gump_closed)

    # Display the gump
    API.Gumps.AddGump(gump)
    update_display()

def set_movement(mode):
    """Set movement mode via button"""
    global movement_mode
    movement_mode = mode
    save_setting(KEY_MOVEMENT_MODE, movement_mode)
    update_display()

# ============ HOTKEY HANDLERS ============

def make_hotkey_handler(key):
    """Create hotkey handler"""
    def handler():
        if key == hotkey_pause:
            toggle_pause()
        elif key == hotkey_esc:
            emergency_hotkey_recall()
        elif key == "TAB":
            toggle_movement_mode()
    return handler

# ============ INITIALIZATION ============

# Load settings
load_settings()

# Build GUI
build_gump()

# Register hotkeys
all_keys = ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12", "TAB", "ESC"]
for key in all_keys:
    try:
        API.OnHotKey(key, make_hotkey_handler(key))
    except:
        pass

API.SysMsg("Gatherer v1.0 started!", HUE_GREEN)
API.SysMsg("Press " + hotkey_pause + " to pause, " + hotkey_esc + " for emergency recall", HUE_YELLOW)

# ============ MAIN LOOP ============

try:
    while not API.StopRequested:
        API.ProcessCallbacks()  # CRITICAL: First for responsive hotkeys

        # Check for captcha (highest priority - stops script immediately)
        captcha = check_for_captcha()
        if captcha:
            handle_captcha(captcha)
            break  # Exit main loop after captcha handling

        if PAUSED:
            API.Pause(0.1)
            continue

        # Update tracking
        update_resource_counts()
        update_weight()

        # Combat check (highest priority) - but not while already fleeing or at home
        if STATE not in ["fleeing", "dumping", "pathfinding"]:
            enemy = check_for_hostiles()
            if enemy:
                handle_combat(enemy)
                API.Pause(0.1)
                continue

        # State machine
        if STATE == "idle":
            # Check if we should dump
            if should_dump():
                if recall_home():
                    STATE = "dumping"
                else:
                    # Recall failed - pause and notify
                    API.SysMsg("Cannot recall home! Pausing - restock reagents or check runebook.", HUE_RED)
                    PAUSED = True
            # Otherwise, gather
            elif tool_serial > 0:
                tool = get_tool()
                if tool:
                    perform_gather()
                else:
                    if time.time() % 5 < 0.1:  # Message every 5 seconds
                        API.SysMsg("IDLE - Tool not found (serial: 0x" + hex(tool_serial)[2:].upper() + ")", HUE_RED)
            else:
                # No tool configured
                if time.time() % 5 < 0.1:  # Message every 5 seconds
                    API.SysMsg("IDLE - No tool configured! Click [SET]", HUE_RED)

        elif STATE == "gathering":
            # Wait for gather to complete
            if time.time() > action_start_time + GATHER_DELAY:
                # Check for SUCCESS first (clears journal if found)
                success = check_gather_success()

                if success:
                    # Success! Resources were gathered
                    failed_gather_count = 0  # Reset failed counter
                    API.SysMsg("Success! Gathered resources (x" + str(gather_count) + ")", HUE_GREEN)
                else:
                    # No success - check if it's due to depletion or just a miss
                    depleted = check_resource_depletion()

                    if depleted:
                        # Force movement when resources are depleted
                        failed_gather_count = 0  # Reset failed counter
                        API.SysMsg("=== DEPLETED - MOVING ===", HUE_RED)
                        check_movement(force=True)
                    else:
                        # Failed gather - no success message and not depleted
                        failed_gather_count += 1
                        API.SysMsg("Failed gather " + str(failed_gather_count) + "/" + str(MAX_FAILED_GATHERS), HUE_YELLOW)

                        # Move if we've failed too many times
                        if failed_gather_count >= MAX_FAILED_GATHERS:
                            API.SysMsg("=== TOO MANY FAILURES - MOVING ===", HUE_ORANGE)
                            failed_gather_count = 0
                            check_movement(force=True)

                # Transition to idle if not moving (don't call check_movement again)
                if STATE != "moving":
                    STATE = "idle"

        elif STATE == "moving":
            # Check if pathfinding movement is complete
            if not API.Pathfinding():
                # Movement complete
                API.SysMsg("Movement complete", HUE_GREEN)

                # Convert logs to boards if we have a hatchet (during idle time between spots)
                tool = get_tool()
                if tool and AUTO_CONVERT_LOGS:
                    if tool.Graphic in [HATCHET_GRAPHIC, AXE_GRAPHIC, DOUBLE_AXE_GRAPHIC]:
                        # Count all log types
                        log_count_before = 0
                        for log_graphic in LOG_GRAPHICS:
                            log_count_before += count_resources(log_graphic)

                        if log_count_before > 0:
                            API.SysMsg("Converting logs to boards...", HUE_YELLOW)
                            convert_logs_to_boards()
                            API.Pause(0.5)

                STATE = "idle"
            elif time.time() > action_start_time + 15.0:
                # Timeout after 15 seconds - cancel pathfinding
                API.SysMsg("Movement timeout - canceling", HUE_YELLOW)
                API.CancelPathfinding()
                STATE = "idle"

        elif STATE == "combat":
            # Re-check enemy
            if current_enemy:
                mob = API.Mobiles.FindMobile(current_enemy.Serial)
                if not mob or mob.IsDead or mob.Distance > COMBAT_DISTANCE:
                    current_enemy = None
                    STATE = "idle"
            else:
                STATE = "idle"

        elif STATE == "fleeing":
            # Check current position to detect if stuck
            current_x = getattr(API.Player, 'X', 0)
            current_y = getattr(API.Player, 'Y', 0)

            # Check if we've moved
            if current_x != flee_last_pos_x or current_y != flee_last_pos_y:
                # We moved! Update tracking
                flee_last_pos_x = current_x
                flee_last_pos_y = current_y
                flee_last_move_time = time.time()

            # Check if we're STUCK (haven't moved in a while)
            time_since_movement = time.time() - flee_last_move_time
            if time_since_movement >= flee_stuck_threshold:
                # STUCK! Try a new direction immediately
                API.SysMsg("STUCK! Trying new direction...", HUE_RED)
                API.CancelPathfinding()

                # Try random direction
                if current_enemy:
                    mob = API.Mobiles.FindMobile(current_enemy.Serial)
                    if mob and not mob.IsDead:
                        start_flee_from_enemy(mob)
                    else:
                        start_flee_from_enemy(None)
                else:
                    start_flee_from_enemy(None)

                flee_last_move_time = time.time()  # Reset timer
                API.Pause(0.1)
                continue

            # Check if we're safe to recall
            current_hp = API.Player.Hits
            flee_time = time.time() - flee_start_time

            # Check if enemy is still close
            enemy_close = False
            enemy_distance = 99
            if current_enemy:
                mob = API.Mobiles.FindMobile(current_enemy.Serial)
                if mob and not mob.IsDead:
                    enemy_distance = getattr(mob, 'Distance', 99)
                    if enemy_distance < 8:
                        enemy_close = True

            # Check if we're still being hit (HP dropping)
            being_hit = (current_hp < last_hp_for_flee)
            last_hp_for_flee = current_hp

            # Safe to recall if:
            # 1. We've been fleeing for at least 2 seconds AND
            # 2. Enemy is far away (8+ tiles) OR we're not being hit recently
            if flee_time >= 2.0 and (not enemy_close or not being_hit):
                API.SysMsg("Safe distance reached (" + str(enemy_distance) + " tiles) - recalling home!", HUE_GREEN)
                API.CancelPathfinding()  # Stop running
                if recall_home():
                    # Check if we used emergency charges (journal will have the warning)
                    STATE = "dumping"  # Go straight to dump
                    current_enemy = None
                    # If emergency charges were used, pause after dumping
                    # (emergency_recall_home() already shows big warning)
                else:
                    # Recall failed completely
                    API.SysMsg("╔════════════════════════════════════╗", HUE_RED)
                    API.SysMsg("║  RECALL FAILED - CANNOT ESCAPE!    ║", HUE_RED)
                    API.SysMsg("║  Script PAUSED - manual escape     ║", HUE_RED)
                    API.SysMsg("╚════════════════════════════════════╝", HUE_RED)
                    API.CancelPathfinding()
                    PAUSED = True
                    STATE = "idle"
                    current_enemy = None

            # Timeout after 15 seconds - force recall attempt
            elif flee_time >= flee_timeout:
                API.SysMsg("Flee timeout - forcing recall!", HUE_RED)
                API.CancelPathfinding()
                if recall_home():
                    STATE = "dumping"
                    current_enemy = None
                else:
                    # Give up and pause
                    API.SysMsg("Cannot escape! PAUSING - recall manually!", HUE_RED)
                    API.CancelPathfinding()
                    PAUSED = True
                    STATE = "idle"
                    current_enemy = None

            # Still fleeing - check if pathfinding stopped (reached destination)
            elif not API.Pathfinding() and flee_time < 2.0:
                # Reached flee destination but not safe yet, run further
                if current_enemy:
                    mob = API.Mobiles.FindMobile(current_enemy.Serial)
                    if mob and not mob.IsDead:
                        API.SysMsg("Not safe yet - running further!", HUE_YELLOW)
                        start_flee_from_enemy(mob)

            # Every second, show status
            if int(flee_time) != int(flee_time - 0.1):
                player_hp_pct = (API.Player.Hits / API.Player.HitsMax * 100) if API.Player.HitsMax > 0 else 100
                status = "Fleeing... HP: " + str(int(player_hp_pct)) + "% | Dist: " + str(enemy_distance) + " tiles"
                if enemy_close:
                    status += " | TOO CLOSE!"
                if being_hit:
                    status += " | BEING HIT!"
                API.SysMsg(status, HUE_ORANGE)

        elif STATE == "pathfinding":
            # Wait for pathfinding to complete
            if not API.Pathfinding():
                # Pathfinding complete
                API.SysMsg("Reached container area", HUE_GREEN)
                STATE = "dumping"
            elif time.time() > pathfind_start_time + pathfind_timeout:
                # Timeout - cancel pathfinding and try dumping anyway
                API.SysMsg("Pathfind timeout - trying dump anyway", HUE_YELLOW)
                API.CancelPathfinding()
                STATE = "dumping"

        elif STATE == "dumping":
            # Check if we need to pathfind first
            if storage_container_serial > 0:
                container = API.FindItem(storage_container_serial)
                if container:
                    distance = getattr(container, 'Distance', 99)
                    if distance > 3:
                        # Too far, pathfind first
                        if pathfind_to_container():
                            # Pathfinding started, stay in dumping state
                            pass
                        else:
                            # Pathfind failed, pause
                            API.SysMsg("Can't reach container! Move closer manually.", HUE_RED)
                            PAUSED = True
                            STATE = "idle"
                        continue

            # Close enough, dump resources
            if dump_resources():
                session_dumps += 1
                # Update counts and weight after dump
                update_resource_counts()
                update_weight()
                STATE = "idle"
                API.SysMsg("======================", HUE_GREEN)
                API.SysMsg("Dump complete!", HUE_GREEN)

                # Check if we used emergency charge - if so, pause here
                if used_emergency_charge:
                    API.SysMsg("╔════════════════════════════════════╗", HUE_RED)
                    API.SysMsg("║  EMERGENCY CHARGE WAS USED!        ║", HUE_RED)
                    API.SysMsg("║  SCRIPT PAUSED - RESTOCK REGS!     ║", HUE_RED)
                    API.SysMsg("║  Click RESUME when ready           ║", HUE_RED)
                    API.SysMsg("╚════════════════════════════════════╝", HUE_RED)
                    used_emergency_charge = False  # Reset flag
                    PAUSED = True
                    at_home = True
                else:
                    # Normal dump - auto-recall to next spot
                    API.SysMsg("Auto-recalling to next spot in 2 seconds...", HUE_YELLOW)
                    API.SysMsg("======================", HUE_GREEN)

                    # Wait 2 seconds
                    API.Pause(2.0)

                    # Show which spot we're going to
                    next_spot = current_spot_index + 1
                    next_slot = 2 + current_spot_index

                    # Auto-recall to next gathering spot
                    if recall_to_gathering_spot():
                        API.SysMsg("Auto-resumed - Gathering at spot " + str(next_spot) + "/" + str(num_gathering_spots) + " (slot " + str(next_slot) + ")", HUE_GREEN)
                    else:
                        API.SysMsg("╔════════════════════════════════════╗", HUE_RED)
                        API.SysMsg("║  Auto-recall failed!               ║", HUE_RED)
                        API.SysMsg("║  Script PAUSED - check reagents    ║", HUE_RED)
                        API.SysMsg("║  Click RESUME when ready           ║", HUE_RED)
                        API.SysMsg("╚════════════════════════════════════╝", HUE_RED)
                        PAUSED = True
                        at_home = True  # Mark as at home so RESUME button works
            else:
                STATE = "idle"
                PAUSED = True

        # Update display periodically
        now = time.time()
        if now - last_display_update > DISPLAY_UPDATE_INTERVAL:
            update_display()
            last_display_update = now

            # Update session runtime
            runtime_seconds = int(now - session_start_time)
            runtime_minutes = runtime_seconds // 60
            runtime_hours = runtime_minutes // 60
            runtime_minutes = runtime_minutes % 60

            if runtime_hours > 0:
                runtime_text = str(runtime_hours) + "h " + str(runtime_minutes) + "m"
            else:
                runtime_text = str(runtime_minutes) + "m"

            if "session_runtime_label" in controls:
                controls["session_runtime_label"].SetText("Runtime: " + runtime_text)

            # Update session totals (ore/logs collected = current + session totals from previous dumps)
            if "session_ore_label" in controls:
                controls["session_ore_label"].SetText("Total Ore: " + str(session_ore + ore_count))
            if "session_logs_label" in controls:
                controls["session_logs_label"].SetText("Total Logs: " + str(session_logs + log_count))
            if "session_dumps_label" in controls:
                controls["session_dumps_label"].SetText("Dumps: " + str(session_dumps))

        API.Pause(0.1)  # Short pause only

except Exception as e:
    API.SysMsg("CRITICAL ERROR: " + str(e), HUE_RED)

# Cleanup
cleanup()
API.SysMsg("Gatherer stopped", HUE_YELLOW)
