# Util_Gatherer.py - REFACTORED
# Mining/Lumberjacking gatherer with AOE harvesting, auto-dump, and combat handling
# Version 2.0 - Uses GatherFramework and LegionUtils
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
import sys
import os

# Add parent directory (CoryCustom root) to path for library imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from GatherFramework import (
    TravelSystem, StorageSystem, WeightManager, StateMachine,
    CombatSystem, Harvester, SessionStats,
    HUE_GREEN, HUE_RED, HUE_YELLOW, HUE_GRAY, HUE_PURPLE, HUE_ORANGE
)
from LegionUtils import (
    save_int, load_int, save_bool, load_bool,
    save_window_position, load_window_position,
    get_item_safe, cancel_all_targets,
    format_time_elapsed, ErrorManager,
    get_item_count, WindowPositionTracker
)

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
COMBAT_CHECK_INTERVAL = 0.3  # Check for hostiles frequently (every 0.3s)
DISPLAY_UPDATE_INTERVAL = 0.5  # Update UI twice per second
CONVERT_DELAY = 1.5  # Time to wait for log conversion

# Combat settings
FLEE_HP_THRESHOLD = 50  # Recall home if HP drops below this %
COMBAT_DISTANCE = 10  # Detect enemies within this range
COMBAT_MODE = "fight"  # "flee" or "fight" - fight back or just flee
HEAL_HP_THRESHOLD = 85  # Use bandage when HP drops below this % (PRIORITY #1)
BANDAGE_GRAPHIC = 0x0E21  # Bandage graphic
BANDAGE_DELAY = 10  # Bandage cooldown in seconds

# Weight settings
DEFAULT_WEIGHT_THRESHOLD = 80  # Return home at 80% capacity

# Smelting settings (mining only)
SMELT_ORE_THRESHOLD = 20  # Smelt when this many ore in backpack (lower to avoid weight issues)
SMELT_DELAY = 2.0  # Seconds for smelting animation

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

# Captcha detection
CAPTCHA_NUMBER_GUMP = 0x968740
CAPTCHA_PICTA_GUMP = 0xd0c93672

# ============ PERSISTENCE KEYS ============
KEY_PREFIX = "Gatherer_"
KEY_TOOL = KEY_PREFIX + "ToolSerial"
KEY_RUNEBOOK = KEY_PREFIX + "HomeRunebook"
KEY_RUNEBOOK_SLOT = KEY_PREFIX + "HomeSlot"
KEY_STORAGE_MINING = KEY_PREFIX + "StorageMining"
KEY_STORAGE_LUMBERJACKING = KEY_PREFIX + "StorageLumberjacking"
KEY_STORAGE_GUMP_MINING = KEY_PREFIX + "StorageGumpMining"
KEY_STORAGE_GUMP_LUMBERJACKING = KEY_PREFIX + "StorageGumpLumberjacking"
KEY_STORAGE_BUTTON_MINING = KEY_PREFIX + "StorageButtonMining"
KEY_STORAGE_BUTTON_LUMBERJACKING = KEY_PREFIX + "StorageButtonLumberjacking"
KEY_FIRE_BEETLE = KEY_PREFIX + "FireBeetle"
KEY_MOVEMENT_MODE = KEY_PREFIX + "MovementMode"
KEY_WEIGHT_THRESHOLD = KEY_PREFIX + "WeightThreshold"
KEY_HOTKEY_PAUSE = KEY_PREFIX + "HotkeyPause"
KEY_HOTKEY_ESC = KEY_PREFIX + "HotkeyEsc"
KEY_WINDOW_POS = KEY_PREFIX + "WindowXY"
KEY_NUM_SPOTS = KEY_PREFIX + "NumGatheringSpots"
KEY_CURRENT_SPOT = KEY_PREFIX + "CurrentSpotIndex"
KEY_WEAPON = KEY_PREFIX + "WeaponSerial"
KEY_SHIELD = KEY_PREFIX + "ShieldSerial"
KEY_COMBAT_MODE = KEY_PREFIX + "CombatMode"

# ============ RUNTIME STATE ============

# Pause control
PAUSED = True  # Start paused

# Gather tracking
gather_count = 0  # How many times we've gathered since last move
failed_gather_count = 0  # Failed gather attempts at current spot
MAX_FAILED_GATHERS = 2  # Move after this many failed attempts (no resources)

# Resource tracking
ore_count = 0
log_count = 0
session_ore = 0
session_logs = 0
session_dumps = 0

# Combat tracking
current_enemy = None
last_combat_check = 0
last_hp = 0  # Track HP for combat detection
last_beetle_hp = 0  # Track beetle HP for damage detection

# Movement
movement_mode = "random"  # Modes: random, spiral, stationary
spiral_direction = 0  # For spiral pattern: 0=N, 1=E, 2=S, 3=W
spiral_steps = 8  # Steps in current direction (start at 8 for AOE coverage)
spiral_steps_taken = 0  # Steps taken in current direction
spiral_turns = 0  # Turns completed

# Tool/Setup
tool_serial = 0
fire_beetle_serial = 0  # Fire beetle for smelting ore
weapon_serial = 0  # Weapon for combat
shield_serial = 0  # Shield for combat (optional)
num_gathering_spots = 1  # How many gathering spots in runebook (slots 2, 3, 4, etc.)
resource_type = "mining"  # "mining" or "lumberjacking" (auto-detected from tool)
combat_mode = "fight"  # "flee" or "fight"
last_bandage_time = 0  # Track bandage cooldown

# Hotkeys
hotkey_pause = "F1"
hotkey_esc = "F2"

# Display
last_display_update = 0

# Emergency charge tracking
used_emergency_charge = False

# ============ FRAMEWORK OBJECTS ============
travel = None
storage = None
weight_mgr = None
state = None
combat = None
harvester = None
stats = None
pos_tracker = None

# ============ GUI REFERENCES ============
gump = None
controls = {}
tester_gump = None
tester_controls = {}

# ============ CAPTURE STATE ============
detecting_gump = False
captured_gump_id = 0

# ============ UTILITY FUNCTIONS ============

def get_tool():
    """Get the configured harvesting tool"""
    return get_item_safe(tool_serial)

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
    """Count resources in backpack by graphic - uses LegionUtils"""
    return get_item_count(graphic)

def update_resource_counts():
    """Update ore and log counts"""
    global ore_count, log_count
    ore_count = count_resources(ORE_GRAPHIC) + count_resources(INGOT_GRAPHIC)

    # Count all log types
    log_count = count_resources(BOARD_GRAPHIC)
    for log_graphic in LOG_GRAPHICS:
        log_count += count_resources(log_graphic)

def check_for_captcha():
    """Check if a captcha gump is open"""
    try:
        if API.HasGump(CAPTCHA_NUMBER_GUMP):
            return "number"
        elif API.HasGump(CAPTCHA_PICTA_GUMP):
            return "picta"
        return None
    except Exception as e:
        # Only log unexpected errors, not normal operation
        API.SysMsg("Captcha check error: " + str(e), HUE_YELLOW)
        return None

def handle_captcha(captcha_type):
    """Handle captcha detection - recall home and PAUSE (not stop)"""
    global PAUSED

    API.SysMsg("╔════════════════════════════════════╗", HUE_RED)
    API.SysMsg("║   CAPTCHA DETECTED!                ║", HUE_RED)
    API.SysMsg("║   Type: " + captcha_type.upper().ljust(27) + "║", HUE_RED)
    API.SysMsg("║   Recalling home and pausing...    ║", HUE_RED)
    API.SysMsg("╚════════════════════════════════════╝", HUE_RED)

    # Cancel any active pathfinding
    if API.Pathfinding():
        API.CancelPathfinding()

    # Call pets to follow before recalling
    API.Msg("all follow me")
    API.Pause(0.5)

    # Try to recall home
    if not travel.at_home:
        API.SysMsg("Attempting recall home...", HUE_YELLOW)
        if travel.recall_home():
            API.SysMsg("Recalled home successfully", HUE_GREEN)
            travel.at_home = True
        else:
            API.SysMsg("Recall failed - pausing anyway", HUE_RED)

    # Pause the script (don't stop - user can resume after solving captcha)
    API.SysMsg("╔════════════════════════════════════╗", HUE_YELLOW)
    API.SysMsg("║   SCRIPT PAUSED - SOLVE CAPTCHA!   ║", HUE_YELLOW)
    API.SysMsg("║   Click RESUME when ready          ║", HUE_YELLOW)
    API.SysMsg("╚════════════════════════════════════╝", HUE_YELLOW)

    PAUSED = True
    state.set_state("idle")

def check_resource_depletion():
    """Check journal for resource depletion messages"""
    try:
        for message in DEPLETION_MESSAGES:
            if API.InJournal(message, False):
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
                return True
        return False
    except Exception as e:
        return False

def parse_cooldown():
    """Try to parse cooldown from journal message"""
    return GATHER_DELAY

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
                cancel_all_targets()

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

def get_resource_type():
    """Detect resource type based on tool graphic"""
    tool = get_tool()
    if not tool:
        return "mining"  # Default

    if tool.Graphic in [PICKAXE_GRAPHIC, SHOVEL_GRAPHIC]:
        return "mining"
    elif tool.Graphic in [HATCHET_GRAPHIC, AXE_GRAPHIC, DOUBLE_AXE_GRAPHIC]:
        return "lumberjacking"
    else:
        return "mining"  # Default

def smelt_ore(skip_threshold=False):
    """Smelt ore using fire beetle

    Args:
        skip_threshold: If True, smelt even if ore count < 50 (for pre-dump smelting)
    """
    global ore_count

    # Check if we have enough ore to smelt
    ore_count = count_resources(ORE_GRAPHIC)

    if ore_count == 0:
        return False  # No ore at all

    if not skip_threshold and ore_count < SMELT_ORE_THRESHOLD:
        # Not enough ore - this is normal, no message needed
        return False

    API.SysMsg("Attempting to smelt " + str(ore_count) + " ore...", HUE_ORANGE)

    # Get fire beetle (it's a mobile, not an item!)
    beetle = API.FindMobile(fire_beetle_serial)
    if not beetle:
        API.SysMsg("Fire beetle not found! Serial: 0x" + hex(fire_beetle_serial)[2:].upper(), HUE_RED)
        return False

    if beetle.IsDead:
        API.SysMsg("Fire beetle is dead!", HUE_RED)
        return False

    # Check if beetle is nearby
    if beetle.Distance > 2:
        API.SysMsg("Fire beetle too far away! (" + str(beetle.Distance) + " tiles)", HUE_YELLOW)
        return False

    API.SysMsg("Fire beetle found and nearby! Distance: " + str(beetle.Distance), HUE_GREEN)

    try:
        # Find ore in backpack
        API.FindType(ORE_GRAPHIC)
        if not API.Found:
            API.SysMsg("No ore found in backpack!", HUE_RED)
            return False

        ore_item = get_item_safe(API.Found)
        if not ore_item:
            API.SysMsg("Ore item not accessible!", HUE_RED)
            return False

        # Smelting sequence: Use ore, then target beetle
        # Cancel any existing targets
        cancel_all_targets()

        # Pre-target the fire beetle FIRST
        API.PreTarget(beetle.Serial, "neutral")
        API.Pause(0.2)

        # Use ore SERIAL (not object) - this opens cursor which PreTarget handles
        API.UseObject(ore_item.Serial, False)
        API.Pause(SMELT_DELAY)

        # Clean up
        API.CancelPreTarget()

        API.SysMsg("Smelting complete! (" + str(ore_count) + " ore -> ingots)", HUE_ORANGE)
        update_resource_counts()
        return True

    except Exception as e:
        API.SysMsg("Smelt error: " + str(e), HUE_RED)
        return False

# ============ CORE LOGIC ============

def perform_gather():
    """Perform gather action using AOE self-targeting"""
    global gather_count

    tool = get_tool()
    if not tool:
        API.SysMsg("No tool configured! Click [SET] to setup.", HUE_RED)
        state.set_state("idle")
        return

    try:
        # CRITICAL: Clear journal BEFORE gathering so we only see NEW messages
        API.ClearJournal()

        # Use harvester framework
        if harvester.harvest():
            gather_count += 1
            state.set_state("gathering", duration=GATHER_DELAY)
            API.SysMsg("Gathering... (x" + str(gather_count) + ")", HUE_GREEN)

            # Mark that we're at gathering spot, not home
            travel.at_home = False
        else:
            # Check if we failed because we're mounted
            journal = API.InGameJournal.GetText().lower()
            mount_messages = ["can't dig", "while riding", "while flying", "must dismount", "can't mine"]
            if any(msg in journal for msg in mount_messages):
                API.SysMsg("Mounted - dismounting...", HUE_YELLOW)
                if dismount_beetle():
                    API.Pause(0.5)
                    # Retry gather after dismounting
                    state.set_state("idle")
                    return

            API.SysMsg("Gather failed!", HUE_RED)
            state.set_state("idle")

    except Exception as e:
        API.SysMsg("Gather error: " + str(e), HUE_RED)
        state.set_state("idle")

def check_for_hostiles():
    """Check for nearby hostile mobiles - custom detection"""
    global last_combat_check, last_hp, last_beetle_hp

    now = time.time()
    if now - last_combat_check < COMBAT_CHECK_INTERVAL:
        return None

    last_combat_check = now

    # Method 1: Check if WE'RE taking damage
    current_hp = API.Player.Hits
    if last_hp > 0 and current_hp < last_hp:
        API.SysMsg("TAKING DAMAGE! HP: " + str(current_hp) + "/" + str(API.Player.HitsMax), HUE_RED)
        # We're being attacked - find closest mobile
        enemy = find_closest_mobile()
        if enemy:
            API.SysMsg("ENEMY DETECTED! Distance: " + str(enemy.Distance), HUE_RED)
            last_hp = current_hp
            return enemy

    last_hp = current_hp

    # Method 2: Check if BEETLE is taking damage (mining only)
    if resource_type == "mining" and fire_beetle_serial > 0:
        beetle = API.FindMobile(fire_beetle_serial)
        if beetle and not beetle.IsDead:
            current_beetle_hp = beetle.Hits
            if last_beetle_hp > 0 and current_beetle_hp < last_beetle_hp:
                API.SysMsg("BEETLE TAKING DAMAGE! HP: " + str(current_beetle_hp) + "/" + str(beetle.HitsMax), HUE_RED)
                # Beetle is being attacked - find enemy
                enemy = find_closest_mobile()
                if enemy:
                    API.SysMsg("ENEMY ATTACKING BEETLE! Distance: " + str(enemy.Distance), HUE_RED)
                    last_beetle_hp = current_beetle_hp
                    return enemy
            last_beetle_hp = current_beetle_hp

    # Method 3: Scan for nearby mobiles (non-friendly)
    enemy = find_closest_mobile()
    if enemy:
        # Check if close enough to be threatening
        if enemy.Distance <= 5:  # Only alert if very close
            API.SysMsg("ENEMY NEARBY! Distance: " + str(enemy.Distance), HUE_YELLOW)
            return enemy

    return None

def find_closest_mobile():
    """Find closest non-friendly mobile"""
    try:
        # Get all mobiles in journal range (this is a hack but works)
        # We'll scan for mobiles by trying different serials
        closest_mobile = None
        closest_distance = 999

        # Alternative: Use API to get mobiles if available
        # For now, check if there's a LastTarget we can use
        try:
            last_target_serial = API.GetLastTarget()
            if last_target_serial:
                mob = API.FindMobile(last_target_serial)
                if mob and not mob.IsDead:
                    if mob.Distance <= COMBAT_DISTANCE:
                        return mob
        except:
            pass

        # If no better method, return None
        # (The framework's find_closest_hostile might work but we'll try HP detection first)
        return combat.find_closest_hostile(COMBAT_DISTANCE)

    except Exception as e:
        return None

def mount_beetle():
    """Mount fire beetle for combat"""
    global beetle_mounted

    if fire_beetle_serial == 0:
        return False

    beetle = API.FindMobile(fire_beetle_serial)
    if not beetle or beetle.IsDead:
        return False

    # Check if already mounted
    if beetle_mounted:
        return True

    try:
        # Double-click beetle to mount
        API.UseObject(beetle.Serial, False)
        API.Pause(0.8)
        beetle_mounted = True
        API.SysMsg("Mounted beetle for combat!", HUE_GREEN)
        return True
    except:
        return False

def dismount_beetle():
    """Dismount beetle after combat"""
    global beetle_mounted

    if not beetle_mounted:
        return True

    try:
        # Double-click self to dismount (UseObject on player serial)
        API.UseObject(API.Player.Serial, False)
        API.Pause(0.5)
        beetle_mounted = False
        API.SysMsg("Dismounted beetle", HUE_GREEN)
        return True
    except Exception as e:
        API.SysMsg("Dismount failed: " + str(e), HUE_RED)
        return False

def equip_weapon():
    """Equip weapon and shield for combat"""
    equipped = False

    # Equip weapon
    if weapon_serial > 0:
        weapon = get_item_safe(weapon_serial)
        if weapon:
            try:
                API.UseObject(weapon.Serial, False)
                API.Pause(0.3)
                equipped = True
            except:
                pass

    # Equip shield (optional)
    if shield_serial > 0:
        shield = get_item_safe(shield_serial)
        if shield:
            try:
                API.UseObject(shield.Serial, False)
                API.Pause(0.3)
                equipped = True
            except:
                pass

    return equipped

def attack_enemy(enemy):
    """Attack an enemy"""
    try:
        # Set last target to enemy
        API.SetLastTarget(enemy.Serial)
        # Attack
        API.Attack(enemy.Serial)
        return True
    except:
        return False

def use_bandage():
    """Use bandage to heal - PRIORITY #1 in combat"""
    global last_bandage_time

    # Check cooldown
    if time.time() - last_bandage_time < BANDAGE_DELAY:
        return False

    # Find bandages
    API.FindType(BANDAGE_GRAPHIC)
    if not API.Found:
        API.SysMsg("OUT OF BANDAGES!", HUE_RED)
        return False

    try:
        bandage = get_item_safe(API.Found)
        if not bandage:
            return False

        # Use bandage on self
        cancel_all_targets()
        API.PreTarget(API.Player.Serial, "beneficial")
        API.Pause(0.1)
        API.UseObject(bandage.Serial, False)
        API.Pause(0.2)
        API.CancelPreTarget()

        last_bandage_time = time.time()
        API.SysMsg("Applying bandage...", HUE_GREEN)
        return True
    except Exception as e:
        API.SysMsg("Bandage error: " + str(e), HUE_RED)
        return False

def handle_combat(enemy):
    """Handle combat encounter"""
    global current_enemy, PAUSED

    try:
        current_enemy = enemy
        player_hp_pct = (API.Player.Hits / API.Player.HitsMax * 100) if API.Player.HitsMax > 0 else 100

        # Check if should flee (HP too low)
        if player_hp_pct < FLEE_HP_THRESHOLD:
            API.SysMsg("FLEEING - HP LOW! (" + str(int(player_hp_pct)) + "%)", HUE_RED)

            # Use combat system flee
            state.set_state("fleeing")
            if combat.flee_from_enemy(enemy, distance=15, timeout=15.0):
                # Fled successfully, now recall home
                if travel.recall_home():
                    state.set_state("dumping")
                    current_enemy = None
                else:
                    API.SysMsg("Cannot escape! PAUSING!", HUE_RED)
                    PAUSED = True
                    state.set_state("idle")
                    current_enemy = None
            else:
                # Flee failed
                API.SysMsg("Flee failed! PAUSING!", HUE_RED)
                PAUSED = True
                state.set_state("idle")
                current_enemy = None
            return

        # Fight mode - engage enemy
        if combat_mode == "fight":
            API.SysMsg("COMBAT: " + str(int(player_hp_pct)) + "% HP", HUE_YELLOW)

            # Mount beetle for combat (provides protection + damage)
            if resource_type == "mining" and fire_beetle_serial > 0:
                mount_beetle()

            # PRIORITY #1: HEAL if needed (before attacking!)
            if player_hp_pct < HEAL_HP_THRESHOLD:
                if use_bandage():
                    # Bandage applied, wait a moment before attacking
                    API.Pause(0.5)

            # Equip weapon and shield
            if weapon_serial > 0 or shield_serial > 0:
                equip_weapon()

            # Attack enemy
            attack_enemy(enemy)

            state.set_state("combat")
        else:
            # Flee mode - just run away
            API.SysMsg("Enemy detected - fleeing (flee mode)", HUE_YELLOW)
            if combat.flee_from_enemy(enemy, distance=15, timeout=5.0):
                state.set_state("idle")
                current_enemy = None
            else:
                state.set_state("combat")

    except Exception as e:
        API.SysMsg("Combat error: " + str(e), HUE_RED)
        state.set_state("idle")

def should_dump():
    """Check if we should return home to dump"""
    # Don't try to dump if we're already at home
    if travel.at_home:
        return False

    # Use weight manager
    return weight_mgr.should_dump()

def emergency_hotkey_recall():
    """Emergency recall - ESC hotkey (no flee, just try to recall)"""
    API.SysMsg("EMERGENCY RECALL (ESC key)!", HUE_RED)
    # Cancel any active pathfinding
    if API.Pathfinding():
        API.CancelPathfinding()
    if travel.recall_home():
        state.set_state("dumping")  # Go straight to dump
    else:
        API.SysMsg("Emergency recall failed! Try again or move to safety.", HUE_RED)

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
            success = move_random()  # This sets state to "moving" internally
        elif movement_mode == "spiral":
            success = move_spiral()  # This sets state to "moving" internally
        elif movement_mode == "stationary":
            # Forced movement in stationary mode - use random
            API.SysMsg("Stationary mode: forced to move, using random pattern", HUE_YELLOW)
            success = move_random()

        if not success:
            API.SysMsg("Movement failed - will retry after failed attempts", HUE_YELLOW)

def move_random():
    """Move randomly - 6-10 tiles for AOE harvest clearance using pathfinding"""
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
            state.set_state("moving", timeout=15.0)
            return True
        else:
            API.SysMsg("Pathfind failed - trying alternate location", HUE_YELLOW)
            # Try a closer location if pathfind fails
            target_x = int(player_x + 4 * math.cos(angle))
            target_y = int(player_y + 4 * math.sin(angle))
            result = API.Pathfind(target_x, target_y)
            if result:
                state.set_state("moving", timeout=15.0)
                return True
            return False

    except Exception as e:
        API.SysMsg("Move error: " + str(e), HUE_RED)
        return False

def move_spiral():
    """Move in spiral pattern using pathfinding"""
    global spiral_direction, spiral_steps, spiral_steps_taken, spiral_turns

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
            state.set_state("moving", timeout=15.0)

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
        cancel_all_targets()
        target = API.RequestTarget(timeout=15)

        if target:
            item = API.FindItem(target)
            if item and item.Graphic in TOOL_GRAPHICS:
                tool_serial = target
                save_int(KEY_TOOL, tool_serial)

                # Re-initialize framework (resource type may have changed)
                initialize_framework()

                API.SysMsg("Tool set! " + get_tool_name(item), HUE_GREEN)
                API.SysMsg("Resource type: " + resource_type.upper(), HUE_YELLOW)
                update_display()
            else:
                API.SysMsg("That's not a valid harvesting tool!", HUE_RED)
    except Exception as e:
        API.SysMsg("Tool setup error: " + str(e), HUE_RED)

def on_set_home():
    """Prompt user to target home runebook and enter slot"""
    API.SysMsg("Target your home runebook...", HUE_YELLOW)

    try:
        cancel_all_targets()
        target = API.RequestTarget(timeout=15)

        if target:
            item = API.FindItem(target)
            if item:
                travel.runebook_serial = target
                save_int(KEY_RUNEBOOK, target)

                # For now, default to slot 1 - TODO: Add slot input to UI
                travel.home_slot = 1
                save_int(KEY_RUNEBOOK_SLOT, 1)

                API.SysMsg("Runebook set! Slot 1 = home", HUE_GREEN)
                update_display()
            else:
                API.SysMsg("Item not found!", HUE_RED)
    except Exception as e:
        API.SysMsg("Runebook setup error: " + str(e), HUE_RED)

def on_set_storage():
    """Prompt user to target storage container"""
    API.SysMsg("Target your resource storage container...", HUE_YELLOW)

    try:
        cancel_all_targets()
        target = API.RequestTarget(timeout=15)

        if target:
            item = API.FindItem(target)
            if item:
                storage.container_serial = target

                # Save to correct key based on resource type
                storage_key = KEY_STORAGE_MINING if resource_type == "mining" else KEY_STORAGE_LUMBERJACKING
                save_int(storage_key, target)

                # Get container position for pathfinding
                container_x = getattr(item, 'X', 0)
                container_y = getattr(item, 'Y', 0)
                storage.set_container_position(container_x, container_y)

                API.SysMsg("Storage container set for " + resource_type + "!", HUE_GREEN)
                update_display()
            else:
                API.SysMsg("Item not found!", HUE_RED)
    except Exception as e:
        API.SysMsg("Storage setup error: " + str(e), HUE_RED)

def on_set_fire_beetle():
    """Prompt user to target fire beetle (mining only)"""
    global fire_beetle_serial

    if resource_type != "mining":
        API.SysMsg("Fire beetle only needed for mining!", HUE_YELLOW)
        return

    API.SysMsg("Target your fire beetle...", HUE_YELLOW)

    try:
        cancel_all_targets()
        target = API.RequestTarget(timeout=15)

        if target:
            mob = API.FindMobile(target)
            if mob:
                fire_beetle_serial = target
                save_int(KEY_FIRE_BEETLE, fire_beetle_serial)
                API.SysMsg("Fire beetle set!", HUE_GREEN)
                update_display()
            else:
                API.SysMsg("That's not a mobile!", HUE_RED)
    except Exception as e:
        API.SysMsg("Fire beetle setup error: " + str(e), HUE_RED)

def on_set_weapon():
    """Prompt user to target weapon for combat"""
    global weapon_serial

    API.SysMsg("Target your weapon...", HUE_YELLOW)

    try:
        cancel_all_targets()
        target = API.RequestTarget(timeout=15)

        if target:
            item = API.FindItem(target)
            if item:
                weapon_serial = target
                save_int(KEY_WEAPON, weapon_serial)
                API.SysMsg("Weapon set!", HUE_GREEN)
                update_display()
            else:
                API.SysMsg("Item not found!", HUE_RED)
    except Exception as e:
        API.SysMsg("Weapon setup error: " + str(e), HUE_RED)

def on_set_shield():
    """Prompt user to target shield for combat (optional)"""
    global shield_serial

    API.SysMsg("Target your shield (optional)...", HUE_YELLOW)

    try:
        cancel_all_targets()
        target = API.RequestTarget(timeout=15)

        if target:
            item = API.FindItem(target)
            if item:
                shield_serial = target
                save_int(KEY_SHIELD, shield_serial)
                API.SysMsg("Shield set!", HUE_GREEN)
                update_display()
            else:
                API.SysMsg("Item not found!", HUE_RED)
    except Exception as e:
        API.SysMsg("Shield setup error: " + str(e), HUE_RED)

def toggle_combat_mode():
    """Toggle between fight and flee combat modes"""
    global combat_mode

    if combat_mode == "fight":
        combat_mode = "flee"
    else:
        combat_mode = "fight"

    API.SavePersistentVar(KEY_COMBAT_MODE, combat_mode, API.PersistentVar.Char)
    API.SysMsg("Combat mode: " + combat_mode.upper(), HUE_YELLOW)

    # Update button directly
    if "combat_mode_btn" in controls:
        controls["combat_mode_btn"].SetText("FIGHT" if combat_mode == "fight" else "FLEE")
        controls["combat_mode_btn"].SetBackgroundHue(HUE_RED if combat_mode == "fight" else HUE_YELLOW)

    # Re-initialize combat system with new mode
    initialize_framework()

    update_display()

def on_detect_storage_gump():
    """Detect storage gump ID when opened - auto-detect like TomeDumper"""
    global detecting_gump, captured_gump_id

    if detecting_gump:
        API.SysMsg("Already detecting gump!", HUE_YELLOW)
        return

    detecting_gump = True
    API.SysMsg("╔════════════════════════════════════╗", HUE_ORANGE)
    API.SysMsg("║   GUMP DETECTION MODE              ║", HUE_ORANGE)
    API.SysMsg("╚════════════════════════════════════╝", HUE_ORANGE)
    API.SysMsg("Double-click your storage container...", HUE_YELLOW)

    try:
        # Wait for container gump to open (15 second timeout)
        start_time = time.time()
        detected = False

        while time.time() - start_time < 15.0 and not detected:
            API.ProcessCallbacks()

            # Try to get container gump ID using GetContainerGump
            try:
                # This attempts to get the most recently opened container gump
                container_gump_id = API.GetContainerGump()

                if container_gump_id and container_gump_id > 0:
                    # Found a gump!
                    captured_gump_id = container_gump_id

                    # Save to correct key based on resource type
                    if resource_type == "mining":
                        save_int(KEY_STORAGE_GUMP_MINING, captured_gump_id)
                        storage.gump_id = captured_gump_id
                    else:
                        save_int(KEY_STORAGE_GUMP_LUMBERJACKING, captured_gump_id)
                        storage.gump_id = captured_gump_id

                    API.SysMsg("╔════════════════════════════════════╗", HUE_GREEN)
                    API.SysMsg("║   GUMP DETECTED!                   ║", HUE_GREEN)
                    API.SysMsg("║   ID: " + str(captured_gump_id).ljust(27) + "║", HUE_GREEN)
                    API.SysMsg("╚════════════════════════════════════╝", HUE_GREEN)
                    API.SysMsg("Now use [BTN] to test button IDs", HUE_YELLOW)

                    detected = True
                    update_display()
                    break
            except:
                pass

            API.Pause(0.5)

        if not detected:
            API.SysMsg("Timeout - no gump detected!", HUE_RED)
            API.SysMsg("Try again or use GumpInspector", HUE_YELLOW)

        detecting_gump = False

    except Exception as e:
        API.SysMsg("Gump detect error: " + str(e), HUE_RED)
        detecting_gump = False

def on_open_button_tester():
    """Open button tester window"""
    # Get current gump ID
    if resource_type == "mining":
        gump_id = load_int(KEY_STORAGE_GUMP_MINING, 0)
    else:
        gump_id = load_int(KEY_STORAGE_GUMP_LUMBERJACKING, 0)

    if gump_id == 0:
        API.SysMsg("Set gump ID first! Use GumpInspector to find it,", HUE_RED)
        API.SysMsg("then set via Python console (see [?] button)", HUE_RED)
        return

    build_button_tester()

def test_button_number(button_id):
    """Test a specific button ID"""
    # Get gump ID
    if resource_type == "mining":
        gump_id = load_int(KEY_STORAGE_GUMP_MINING, 0)
    else:
        gump_id = load_int(KEY_STORAGE_GUMP_LUMBERJACKING, 0)

    if gump_id == 0:
        API.SysMsg("No gump ID set!", HUE_RED)
        return

    try:
        # Check if gump is open
        if API.HasGump(gump_id):
            # Click the button
            API.ReplyGump(button_id, gump_id)
            API.SysMsg("Clicked button " + str(button_id), HUE_GREEN)

            # Update result in tester
            if "result_label" in tester_controls:
                tester_controls["result_label"].SetText("Tested button: " + str(button_id))
        else:
            API.SysMsg("Storage gump not open! Open it first.", HUE_RED)
            if "result_label" in tester_controls:
                tester_controls["result_label"].SetText("Gump not open!")

    except Exception as e:
        API.SysMsg("Button test error: " + str(e), HUE_RED)

def set_button_as_fill():
    """Set the current test button as the fill button"""
    if "custom_input" not in tester_controls:
        return

    try:
        button_text = tester_controls["custom_input"].Text.strip()
        if not button_text:
            API.SysMsg("Enter button ID first!", HUE_RED)
            return

        button_id = int(button_text)

        # Save button ID
        if resource_type == "mining":
            save_int(KEY_STORAGE_BUTTON_MINING, button_id)
            storage.fill_button_id = button_id
        else:
            save_int(KEY_STORAGE_BUTTON_LUMBERJACKING, button_id)
            storage.fill_button_id = button_id

        API.SysMsg("Fill button set to: " + str(button_id), HUE_GREEN)
        update_display()

        # Re-init framework to use new button
        initialize_framework()

    except ValueError:
        API.SysMsg("Invalid button ID!", HUE_RED)
    except Exception as e:
        API.SysMsg("Set button error: " + str(e), HUE_RED)

def build_button_tester():
    """Build button tester window"""
    global tester_gump, tester_controls

    # Close existing tester
    if tester_gump:
        tester_gump.Dispose()

    tester_controls = {}

    # Create tester window
    tester_gump = API.Gumps.CreateGump()
    tester_gump.SetRect(400, 200, 320, 280)

    # Background
    bg = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
    bg.SetRect(0, 0, 320, 280)
    tester_gump.Add(bg)

    # Title
    title = API.Gumps.CreateGumpTTFLabel("Storage Button Tester", 16, "#ffaa00")
    title.SetPos(10, 5)
    tester_gump.Add(title)

    # Instructions
    instr = API.Gumps.CreateGumpTTFLabel("Open storage, test buttons:", 15, "#888888")
    instr.SetPos(10, 28)
    tester_gump.Add(instr)

    # Quick test grid (buttons 100-123)
    y_pos = 50
    grid_label = API.Gumps.CreateGumpTTFLabel("Common buttons:", 15, "#ffcc00")
    grid_label.SetPos(10, y_pos)
    tester_gump.Add(grid_label)

    y_pos += 20
    # Create grid of common button IDs
    common_buttons = [100, 101, 102, 103, 110, 111, 120, 121, 122, 123, 130, 131]
    for i, btn_id in enumerate(common_buttons):
        row = i // 4
        col = i % 4
        x_pos = 10 + (col * 60)
        y_btn = y_pos + (row * 26)

        test_btn = API.Gumps.CreateSimpleButton("[" + str(btn_id) + "]", 55, 22)
        test_btn.SetPos(x_pos, y_btn)
        test_btn.SetBackgroundHue(68)
        tester_gump.Add(test_btn)
        API.Gumps.AddControlOnClick(test_btn, lambda bid=btn_id: test_button_number(bid))

    y_pos += 90

    # Custom button test
    custom_label = API.Gumps.CreateGumpTTFLabel("Custom ID:", 15, "#ffcc00")
    custom_label.SetPos(10, y_pos)
    tester_gump.Add(custom_label)

    tester_controls["custom_input"] = API.Gumps.CreateGumpTextBox("", 60, 22)
    tester_controls["custom_input"].SetPos(90, y_pos)
    tester_gump.Add(tester_controls["custom_input"])

    test_custom_btn = API.Gumps.CreateSimpleButton("[TEST]", 60, 22)
    test_custom_btn.SetPos(160, y_pos)
    test_custom_btn.SetBackgroundHue(68)
    tester_gump.Add(test_custom_btn)
    API.Gumps.AddControlOnClick(test_custom_btn, lambda: test_button_number(int(tester_controls["custom_input"].Text) if tester_controls["custom_input"].Text.strip() else 0))

    y_pos += 28

    # Set button
    set_btn = API.Gumps.CreateSimpleButton("[SET AS FILL]", 100, 22)
    set_btn.SetPos(10, y_pos)
    set_btn.SetBackgroundHue(66)
    tester_gump.Add(set_btn)
    API.Gumps.AddControlOnClick(set_btn, set_button_as_fill)

    # Current button display
    if resource_type == "mining":
        current_btn = load_int(KEY_STORAGE_BUTTON_MINING, 0)
    else:
        current_btn = load_int(KEY_STORAGE_BUTTON_LUMBERJACKING, 0)

    if current_btn > 0:
        current_label = API.Gumps.CreateGumpTTFLabel("Current: " + str(current_btn), 15, "#00ff00")
        current_label.SetPos(120, y_pos + 3)
        tester_gump.Add(current_label)

    y_pos += 28

    # Result label
    tester_controls["result_label"] = API.Gumps.CreateGumpTTFLabel("Click button to test", 15, "#888888")
    tester_controls["result_label"].SetPos(10, y_pos)
    tester_gump.Add(tester_controls["result_label"])

    # Close callback
    API.Gumps.AddControlOnDisposed(tester_gump, on_tester_closed)

    # Display
    API.Gumps.AddGump(tester_gump)

def on_tester_closed():
    """Cleanup when tester window closes"""
    global tester_gump, tester_controls
    tester_gump = None
    tester_controls = {}

def on_show_storage_info():
    """Show current storage gump/button settings"""
    # Show current values
    if resource_type == "mining":
        gump_id = load_int(KEY_STORAGE_GUMP_MINING, 111922706)
        button_id = load_int(KEY_STORAGE_BUTTON_MINING, 121)
        res_type = "MINING"
    else:
        gump_id = load_int(KEY_STORAGE_GUMP_LUMBERJACKING, 111922706)
        button_id = load_int(KEY_STORAGE_BUTTON_LUMBERJACKING, 121)
        res_type = "LUMBERJACKING"

    API.SysMsg("=== " + res_type + " STORAGE ===", HUE_ORANGE)
    API.SysMsg("Gump ID: " + str(gump_id), HUE_YELLOW)
    API.SysMsg("Button ID: " + str(button_id), HUE_YELLOW)
    API.SysMsg("Click [SET ID] to configure", HUE_YELLOW)

def adjust_spots(delta):
    """Adjust number of gathering spots by +1 or -1"""
    global num_gathering_spots

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
    save_int(KEY_NUM_SPOTS, num_gathering_spots)

    # Update travel system
    travel.num_spots = num_gathering_spots
    travel.current_spot = 0  # Reset to first spot

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

    API.SavePersistentVar(KEY_MOVEMENT_MODE, movement_mode, API.PersistentVar.Char)
    API.SysMsg("Movement mode: " + movement_mode.upper(), HUE_YELLOW)
    update_display()

def test_pathfind_to_storage():
    """Test button - pathfind to storage container"""
    if storage.container_serial == 0:
        API.SysMsg("Storage container not configured! Click [SET] first.", HUE_RED)
        return

    container = API.FindItem(storage.container_serial)
    if not container:
        API.SysMsg("Storage container not found!", HUE_RED)
        return

    distance = getattr(container, 'Distance', 99)
    API.SysMsg("Container is " + str(distance) + " tiles away", HUE_YELLOW)

    if distance <= 3:
        API.SysMsg("Already close enough to container!", HUE_GREEN)
        return

    # Start pathfinding using storage system
    if storage.pathfind_to_container():
        API.SysMsg("Pathfinding started - watch your character move!", HUE_GREEN)
        state.set_state("pathfinding")
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
    """Toggle pause/resume"""
    global PAUSED

    if PAUSED:
        # Resume - recall to next gathering spot
        next_spot = travel.current_spot + 1
        next_slot = 2 + travel.current_spot

        API.SysMsg("Attempting to recall to gathering spot " + str(next_spot) + "...", HUE_YELLOW)

        # Recall to next gathering spot
        if travel.rotate_to_next_spot():
            # Successfully recalled - unpause and continue
            PAUSED = False
            travel.at_home = False  # Mark as not at home
            API.SysMsg("RESUMED - Now at spot " + str(next_spot) + "/" + str(num_gathering_spots) + " (slot " + str(next_slot) + ")", HUE_GREEN)
        else:
            # Recall failed - stay paused
            API.SysMsg("Failed to recall! Make sure you're at home with runebook.", HUE_RED)
    else:
        # Pause
        PAUSED = True
        API.SysMsg("PAUSED", HUE_YELLOW)

    update_display()

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
        if travel.runebook_serial > 0:
            runebook_text = "Slot " + str(travel.home_slot)
            if num_gathering_spots > 1 and not travel.at_home:
                # Show which gathering spot we're at
                prev_spot_index = (travel.current_spot - 1) % num_gathering_spots
                gathering_spot_display = str(prev_spot_index + 1) + "/" + str(num_gathering_spots)
                runebook_text += " | Spot " + gathering_spot_display
        if "runebook_label" in controls:
            controls["runebook_label"].SetText("Home: " + runebook_text)

        # Storage display
        storage_text = "Not Set"
        if storage.container_serial > 0:
            storage_text = "0x" + hex(storage.container_serial)[2:].upper()
        if "storage_label" in controls:
            controls["storage_label"].SetText("Storage (" + resource_type[:4] + "): " + storage_text)

        # Storage gump/button IDs
        if "storage_ids_label" in controls:
            if resource_type == "mining":
                gump_id = load_int(KEY_STORAGE_GUMP_MINING, 111922706)
                button_id = load_int(KEY_STORAGE_BUTTON_MINING, 121)
            else:
                gump_id = load_int(KEY_STORAGE_GUMP_LUMBERJACKING, 111922706)
                button_id = load_int(KEY_STORAGE_BUTTON_LUMBERJACKING, 121)
            ids_text = "Gump: " + str(gump_id) + " | Button: " + str(button_id)
            controls["storage_ids_label"].SetText(ids_text)

        # Fire beetle display (mining only)
        if "beetle_label" in controls:
            if resource_type == "mining":
                beetle_text = "Not Set"
                if fire_beetle_serial > 0:
                    beetle = API.FindMobile(fire_beetle_serial)
                    if beetle and not beetle.IsDead:
                        if beetle.Distance <= 2:
                            beetle_text = "Nearby!"
                        else:
                            beetle_text = "Far (" + str(beetle.Distance) + ")"
                    else:
                        beetle_text = "Not found"
                controls["beetle_label"].SetText("Beetle: " + beetle_text)
            else:
                controls["beetle_label"].SetText("Beetle: N/A (lumber)")

        # Spots display
        if "spots_display" in controls:
            controls["spots_display"].SetText(str(num_gathering_spots))

        # Resources
        if "resources_label" in controls:
            controls["resources_label"].SetText("Ore: " + str(ore_count) + " | Logs: " + str(log_count))

        # Weight
        if "weight_label" in controls:
            current_weight = weight_mgr.get_current_weight()
            max_weight = weight_mgr.get_max_weight()
            weight_pct = weight_mgr.get_weight_pct()
            weight_text = str(int(current_weight)) + "/" + str(int(max_weight)) + " (" + str(int(weight_pct)) + "%)"
            controls["weight_label"].SetText("Weight: " + weight_text)

        # State
        if "state_label" in controls:
            current_state = state.get_state()
            state_text = current_state.upper()
            if current_state == "gathering":
                if MOVE_ON_DEPLETION_ONLY:
                    state_text += " (x" + str(gather_count) + ")"
                    if failed_gather_count > 0:
                        state_text += " [" + str(failed_gather_count) + " failed]"
                else:
                    state_text += " (" + str(gather_count) + "/" + str(GATHERS_PER_MOVE) + ")"
            elif current_state == "pathfinding":
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
            if PAUSED and travel.at_home:
                controls["status_label"].SetText("[AT HOME]")
            else:
                controls["status_label"].SetText("[PAUSED]" if PAUSED else "[ACTIVE]")

        # Pause/Resume button (dynamically update text and color)
        if "resume_btn" in controls:
            if PAUSED:
                controls["resume_btn"].SetBackgroundHue(HUE_GREEN)
                controls["resume_btn"].SetText("RESUME")
            else:
                controls["resume_btn"].SetBackgroundHue(HUE_YELLOW)
                controls["resume_btn"].SetText("PAUSE")

    except Exception as e:
        pass

# ============ PERSISTENCE ============

def load_settings():
    """Load all settings from persistence"""
    global tool_serial, movement_mode, hotkey_pause, hotkey_esc, num_gathering_spots, weapon_serial, shield_serial, combat_mode

    try:
        tool_serial = load_int(KEY_TOOL, 0)
        weapon_serial = load_int(KEY_WEAPON, 0)
        shield_serial = load_int(KEY_SHIELD, 0)
        movement_mode = API.GetPersistentVar(KEY_MOVEMENT_MODE, "random", API.PersistentVar.Char)
        combat_mode = API.GetPersistentVar(KEY_COMBAT_MODE, "fight", API.PersistentVar.Char)
        hotkey_pause = API.GetPersistentVar(KEY_HOTKEY_PAUSE, "F1", API.PersistentVar.Char)
        hotkey_esc = API.GetPersistentVar(KEY_HOTKEY_ESC, "F2", API.PersistentVar.Char)
        num_gathering_spots = load_int(KEY_NUM_SPOTS, 1)
    except Exception as e:
        API.SysMsg("Error loading settings: " + str(e), HUE_RED)

# ============ FRAMEWORK INITIALIZATION ============

def initialize_framework():
    """Initialize framework objects after loading persistence"""
    global travel, storage, weight_mgr, state, combat, harvester, stats, pos_tracker, resource_type, fire_beetle_serial

    # Load settings first
    load_settings()

    # Detect resource type from tool
    resource_type = get_resource_type()

    # Travel system
    runebook_serial = load_int(KEY_RUNEBOOK, 0)
    runebook_slot = load_int(KEY_RUNEBOOK_SLOT, 1)
    travel = TravelSystem(runebook_serial, num_gathering_spots, runebook_slot)

    # Storage system - use correct storage based on resource type
    if resource_type == "mining":
        storage_serial = load_int(KEY_STORAGE_MINING, 0)
        storage_gump_id = load_int(KEY_STORAGE_GUMP_MINING, 111922706)
        storage_button = load_int(KEY_STORAGE_BUTTON_MINING, 121)
        fire_beetle_serial = load_int(KEY_FIRE_BEETLE, 0)
    else:  # lumberjacking
        storage_serial = load_int(KEY_STORAGE_LUMBERJACKING, 0)
        storage_gump_id = load_int(KEY_STORAGE_GUMP_LUMBERJACKING, 111922706)
        storage_button = load_int(KEY_STORAGE_BUTTON_LUMBERJACKING, 121)

    storage = StorageSystem(storage_serial, storage_gump_id, storage_button)

    # Weight manager
    threshold = load_int(KEY_WEIGHT_THRESHOLD, DEFAULT_WEIGHT_THRESHOLD)
    weight_mgr = WeightManager(threshold)

    # State machine
    state = StateMachine()

    # Combat system - use the configured combat_mode
    combat = CombatSystem(mode=combat_mode, flee_hp_threshold=FLEE_HP_THRESHOLD)

    # Harvester
    harvester = Harvester(tool_serial, GATHER_DELAY)
    harvester.use_aoe = True  # CRITICAL: Enable AOE mode

    # Session stats
    stats = SessionStats()

# ============ CLEANUP ============

def cleanup():
    """Cleanup on script stop"""
    global gump, controls, tester_gump, tester_controls

    # Save window position
    if pos_tracker:
        pos_tracker.save()

    # Dispose tester gump if open
    if tester_gump:
        try:
            tester_gump.Dispose()
        except:
            pass
        tester_gump = None
        tester_controls = {}

    # Clear control references
    controls = {}
    gump = None

def on_gump_closed():
    """Handle main gump close"""
    global PAUSED
    PAUSED = True  # Pause when gump closes
    cleanup()
    API.SysMsg("Gatherer gump closed - stopping script", HUE_YELLOW)
    API.Stop()  # Stop the script when gump is closed

# ============ BUILD GUI ============

def build_gump():
    """Build the main UI gump"""
    global gump, controls, pos_tracker

    # Load window position
    x, y = load_window_position(KEY_WINDOW_POS, 100, 100)

    # Create gump
    gump = API.Gumps.CreateGump()
    gump.SetRect(x, y, 340, 472)

    # Create position tracker
    pos_tracker = WindowPositionTracker(gump, KEY_WINDOW_POS, x, y)

    # Add background
    bg = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
    bg.SetRect(0, 0, 340, 472)
    gump.Add(bg)

    y_offset = 10

    # Title bar
    titleLabel = API.Gumps.CreateGumpTTFLabel("GATHERER v2.0", 15, "#ffaa00")
    titleLabel.SetPos(10, y_offset)
    gump.Add(titleLabel)

    controls["status_label"] = API.Gumps.CreateGumpTTFLabel("[ACTIVE]", 15, "#00ff00")
    controls["status_label"].SetPos(200, y_offset)
    gump.Add(controls["status_label"])

    y_offset += 22  # Move to next row

    # Pause/Resume toggle button
    controls["resume_btn"] = API.Gumps.CreateSimpleButton("RESUME", 100, 22)
    controls["resume_btn"].SetPos(120, y_offset)
    gump.Add(controls["resume_btn"])
    API.Gumps.AddControlOnClick(controls["resume_btn"], toggle_pause)

    y_offset += 28  # Extra space for resume button + gap

    # Setup section
    controls["tool_label"] = API.Gumps.CreateGumpTTFLabel("Tool: Not Set", 15, "#ffffff")
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

    controls["runebook_label"] = API.Gumps.CreateGumpTTFLabel("Home: Not Set", 15, "#ffffff")
    controls["runebook_label"].SetPos(10, y_offset)
    gump.Add(controls["runebook_label"])

    home_btn = API.Gumps.CreateSimpleButton("SET", 50, 20)
    home_btn.SetPos(270, y_offset - 2)
    gump.Add(home_btn)
    API.Gumps.AddControlOnClick(home_btn, on_set_home)

    y_offset += 22

    # Number of gathering spots - use buttons instead of text input
    spots_label = API.Gumps.CreateGumpTTFLabel("# Spots:", 15, "#ffffff")
    spots_label.SetPos(10, y_offset)
    gump.Add(spots_label)

    controls["spots_display"] = API.Gumps.CreateGumpTTFLabel(str(num_gathering_spots), 15, "#00ff00")
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

    spots_help = API.Gumps.CreateGumpTTFLabel("(Slots 2+)", 15, "#888888")
    spots_help.SetPos(160, y_offset + 2)
    gump.Add(spots_help)

    y_offset += 22

    controls["storage_label"] = API.Gumps.CreateGumpTTFLabel("Storage: Not Set", 15, "#ffffff")
    controls["storage_label"].SetPos(10, y_offset)
    gump.Add(controls["storage_label"])

    storage_btn = API.Gumps.CreateSimpleButton("SET", 40, 20)
    storage_btn.SetPos(140, y_offset - 2)
    gump.Add(storage_btn)
    API.Gumps.AddControlOnClick(storage_btn, on_set_storage)

    # Test buttons window
    test_btn_btn = API.Gumps.CreateSimpleButton("BTN", 40, 20)
    test_btn_btn.SetPos(185, y_offset - 2)
    gump.Add(test_btn_btn)
    API.Gumps.AddControlOnClick(test_btn_btn, on_open_button_tester)

    # Storage info button
    storage_info_btn = API.Gumps.CreateSimpleButton("?", 30, 20)
    storage_info_btn.SetPos(230, y_offset - 2)
    gump.Add(storage_info_btn)
    API.Gumps.AddControlOnClick(storage_info_btn, on_show_storage_info)

    # Test pathfind button
    test_pathfind_btn = API.Gumps.CreateSimpleButton("TST", 40, 20)
    test_pathfind_btn.SetPos(270, y_offset - 2)
    gump.Add(test_pathfind_btn)
    API.Gumps.AddControlOnClick(test_pathfind_btn, test_pathfind_to_storage)

    y_offset += 22

    # Auto-detect gump ID button (second row under storage)
    detect_gump_btn = API.Gumps.CreateSimpleButton("DETECT GUMP ID", 120, 20)
    detect_gump_btn.SetPos(10, y_offset - 2)
    detect_gump_btn.SetBackgroundHue(HUE_PURPLE)
    gump.Add(detect_gump_btn)
    API.Gumps.AddControlOnClick(detect_gump_btn, on_detect_storage_gump)

    y_offset += 22

    # Storage gump/button info
    controls["storage_ids_label"] = API.Gumps.CreateGumpTTFLabel("Gump: ??? | Button: ???", 15, "#888888")
    controls["storage_ids_label"].SetPos(10, y_offset)
    gump.Add(controls["storage_ids_label"])

    y_offset += 22

    # Fire beetle (mining only)
    controls["beetle_label"] = API.Gumps.CreateGumpTTFLabel("Beetle: Not Set", 15, "#888888")
    controls["beetle_label"].SetPos(10, y_offset)
    gump.Add(controls["beetle_label"])

    beetle_btn = API.Gumps.CreateSimpleButton("SET", 50, 20)
    beetle_btn.SetPos(210, y_offset - 2)
    gump.Add(beetle_btn)
    API.Gumps.AddControlOnClick(beetle_btn, on_set_fire_beetle)

    y_offset += 30

    # Combat section
    combat_label = API.Gumps.CreateGumpTTFLabel("Combat:", 15, "#ffffff")
    combat_label.SetPos(10, y_offset)
    gump.Add(combat_label)

    # Combat mode toggle (store in controls for updates)
    controls["combat_mode_btn"] = API.Gumps.CreateSimpleButton("FIGHT" if combat_mode == "fight" else "FLEE", 60, 20)
    controls["combat_mode_btn"].SetPos(70, y_offset - 2)
    controls["combat_mode_btn"].SetBackgroundHue(HUE_RED if combat_mode == "fight" else HUE_YELLOW)
    gump.Add(controls["combat_mode_btn"])
    API.Gumps.AddControlOnClick(controls["combat_mode_btn"], toggle_combat_mode)

    # Weapon set button
    weapon_btn = API.Gumps.CreateSimpleButton("WPN", 45, 20)
    weapon_btn.SetPos(135, y_offset - 2)
    gump.Add(weapon_btn)
    API.Gumps.AddControlOnClick(weapon_btn, on_set_weapon)

    # Shield set button (optional)
    shield_btn = API.Gumps.CreateSimpleButton("SHLD", 45, 20)
    shield_btn.SetPos(185, y_offset - 2)
    gump.Add(shield_btn)
    API.Gumps.AddControlOnClick(shield_btn, on_set_shield)

    y_offset += 30

    # Movement mode section
    mode_label = API.Gumps.CreateGumpTTFLabel("Movement:", 15, "#ffffff")
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
    controls["resources_label"] = API.Gumps.CreateGumpTTFLabel("Ore: 0 | Logs: 0", 15, "#ffffff")
    controls["resources_label"].SetPos(10, y_offset)
    gump.Add(controls["resources_label"])

    y_offset += 18

    controls["weight_label"] = API.Gumps.CreateGumpTTFLabel("Weight: 0/450 (0%)", 15, "#ffffff")
    controls["weight_label"].SetPos(10, y_offset)
    gump.Add(controls["weight_label"])

    y_offset += 18

    controls["state_label"] = API.Gumps.CreateGumpTTFLabel("State: IDLE", 15, "#ffffff")
    controls["state_label"].SetPos(10, y_offset)
    gump.Add(controls["state_label"])

    y_offset += 30

    # Session stats
    stats_title = API.Gumps.CreateGumpTTFLabel("Session Stats:", 15, "#ffaa00")
    stats_title.SetPos(10, y_offset)
    gump.Add(stats_title)

    y_offset += 18

    controls["session_ore_label"] = API.Gumps.CreateGumpTTFLabel("Total Ore: 0", 15, "#aaaaaa")
    controls["session_ore_label"].SetPos(15, y_offset)
    gump.Add(controls["session_ore_label"])

    y_offset += 16

    controls["session_logs_label"] = API.Gumps.CreateGumpTTFLabel("Total Logs: 0", 15, "#aaaaaa")
    controls["session_logs_label"].SetPos(15, y_offset)
    gump.Add(controls["session_logs_label"])

    y_offset += 16

    controls["session_dumps_label"] = API.Gumps.CreateGumpTTFLabel("Dumps: 0", 15, "#aaaaaa")
    controls["session_dumps_label"].SetPos(15, y_offset)
    gump.Add(controls["session_dumps_label"])

    y_offset += 16

    controls["session_runtime_label"] = API.Gumps.CreateGumpTTFLabel("Runtime: 0m", 15, "#aaaaaa")
    controls["session_runtime_label"].SetPos(15, y_offset)
    gump.Add(controls["session_runtime_label"])

    y_offset += 25

    # Hotkeys
    hotkeys_title = API.Gumps.CreateGumpTTFLabel("Hotkeys:", 15, "#ffaa00")
    hotkeys_title.SetPos(10, y_offset)
    gump.Add(hotkeys_title)

    y_offset += 18

    pause_label = API.Gumps.CreateGumpTTFLabel("PAUSE: [" + hotkey_pause + "]", 15, "#aaaaaa")
    pause_label.SetPos(15, y_offset)
    gump.Add(pause_label)

    y_offset += 16

    esc_label = API.Gumps.CreateGumpTTFLabel("ESC Home: [" + hotkey_esc + "]", 15, "#aaaaaa")
    esc_label.SetPos(15, y_offset)
    gump.Add(esc_label)

    y_offset += 16

    tab_label = API.Gumps.CreateGumpTTFLabel("Cycle Mode: [TAB]", 15, "#aaaaaa")
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
    API.SavePersistentVar(KEY_MOVEMENT_MODE, movement_mode, API.PersistentVar.Char)
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

# Initialize framework
initialize_framework()

# Build GUI
build_gump()

# Register hotkeys
all_keys = ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12", "TAB", "ESC"]
for key in all_keys:
    try:
        API.OnHotKey(key, make_hotkey_handler(key))
    except:
        pass

API.SysMsg("Gatherer v2.0 started! (Framework-based)", HUE_GREEN)
API.SysMsg("Press " + hotkey_pause + " to pause, " + hotkey_esc + " for emergency recall", HUE_YELLOW)

# ============ MAIN LOOP ============

try:
    while not API.StopRequested:
        API.ProcessCallbacks()  # CRITICAL: First for responsive hotkeys

        # Check for captcha (highest priority - pauses script)
        captcha = check_for_captcha()
        if captcha:
            handle_captcha(captcha)
            # Don't break - just pause (handle_captcha sets PAUSED = True)
            continue

        if PAUSED:
            API.Pause(0.1)
            continue

        # Update tracking
        update_resource_counts()

        # Update position tracker
        if pos_tracker:
            pos_tracker.update()

        # Combat check (highest priority) - but not while already in combat or at home
        current_state = state.get_state()
        if current_state not in ["fleeing", "dumping", "pathfinding", "combat", "waiting_to_recall"]:
            enemy = check_for_hostiles()
            if enemy:
                API.SysMsg("ENEMY DETECTED! Stopping to fight...", HUE_RED)
                handle_combat(enemy)
                API.Pause(0.5)  # Give combat actions time to process
                continue

        # State machine
        if current_state == "idle":
            # Check if we should smelt ore (mining only)
            if resource_type == "mining" and fire_beetle_serial > 0:
                ore_count = count_resources(ORE_GRAPHIC)
                if ore_count >= SMELT_ORE_THRESHOLD:
                    API.SysMsg("SMELT CHECK: " + str(ore_count) + " ore, threshold " + str(SMELT_ORE_THRESHOLD), HUE_BLUE)
                    if smelt_ore():
                        API.Pause(0.5)
                        continue
            elif resource_type != "mining":
                # Debug: Show why we're not smelting
                if time.time() % 10 < 0.1:  # Once every 10 seconds
                    API.SysMsg("Not mining - resource type: " + resource_type, HUE_GRAY)
            elif fire_beetle_serial == 0:
                # Debug: Show why we're not smelting
                if time.time() % 10 < 0.1:  # Once every 10 seconds
                    API.SysMsg("No fire beetle configured!", HUE_GRAY)

            # Check if we should dump
            if should_dump():
                # Smelt ALL remaining ore before dumping (mining only)
                if resource_type == "mining" and fire_beetle_serial > 0:
                    ore_count = count_resources(ORE_GRAPHIC)
                    if ore_count > 0:
                        API.SysMsg("Smelting all ore before dump...", HUE_ORANGE)
                        # Smelt all ore stacks (may need multiple iterations)
                        max_smelt_attempts = 10  # Safety limit
                        smelt_attempts = 0
                        while count_resources(ORE_GRAPHIC) > 0 and smelt_attempts < max_smelt_attempts:
                            if not smelt_ore(skip_threshold=True):
                                API.SysMsg("Smelt failed, continuing to dump anyway", HUE_YELLOW)
                                break
                            API.Pause(SMELT_DELAY)
                            smelt_attempts += 1

                        if smelt_attempts >= max_smelt_attempts:
                            API.SysMsg("Max smelt attempts reached, continuing to dump", HUE_YELLOW)

                        # Update counts after smelting
                        update_resource_counts()
                        API.SysMsg("Smelting complete!", HUE_GREEN)

                        # Check if weight is now OK after smelting (ingots are lighter than ore)
                        if not should_dump():
                            API.SysMsg("Weight OK after smelting! Continuing to mine...", HUE_GREEN)
                            continue  # Back to mining, skip the dump

                # Weight still too high - recall home and dump
                API.SysMsg("Recalling home to dump...", HUE_YELLOW)
                if travel.recall_home():
                    state.set_state("dumping")
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

        elif current_state == "gathering":
            # Wait for gather to complete
            if state.is_timeout(GATHER_DELAY):
                # Check for SUCCESS first
                success = check_gather_success()

                if success:
                    # Success! Resources were gathered
                    failed_gather_count = 0  # Reset failed counter
                    stats.increment("gathers")
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

                # Transition to idle if not moving
                if state.get_state() != "moving":
                    state.set_state("idle")

        elif current_state == "moving":
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

                state.set_state("idle")
            elif state.is_timeout(15.0):
                # Timeout after 15 seconds - cancel pathfinding
                API.SysMsg("Movement timeout - canceling", HUE_YELLOW)
                API.CancelPathfinding()
                state.set_state("idle")

        elif current_state == "combat":
            # Active combat - continue fighting
            if current_enemy:
                enemy_serial = getattr(current_enemy, 'Serial', None)
                if enemy_serial:
                    mob = API.FindMobile(enemy_serial)
                    if not mob or mob.IsDead or mob.Distance > COMBAT_DISTANCE:
                        # Combat ended - dismount to continue mining
                        if beetle_mounted:
                            API.SysMsg("Combat ended - dismount to mine", HUE_GREEN)
                            dismount_beetle()
                        current_enemy = None
                        state.set_state("idle")
                    else:
                        # Enemy still alive and nearby - continue fighting!
                        player_hp_pct = (API.Player.Hits / API.Player.HitsMax * 100) if API.Player.HitsMax > 0 else 100

                        # Check if we should flee
                        if player_hp_pct < FLEE_HP_THRESHOLD:
                            API.SysMsg("HP LOW (" + str(int(player_hp_pct)) + "%) - FLEEING!", HUE_RED)
                            current_enemy = None
                            state.set_state("idle")
                            # Don't pause - let normal flow handle it
                        else:
                            # Continue fighting
                            # PRIORITY #1: Heal if needed
                            if player_hp_pct < HEAL_HP_THRESHOLD:
                                use_bandage()

                            # Tactical kiting: If HP is low (60-70%) and bandage is on cooldown, create distance
                            now = time.time()
                            bandage_on_cooldown = (now - last_bandage_time) < BANDAGE_DELAY
                            should_kite = player_hp_pct < 70 and bandage_on_cooldown

                            if should_kite:
                                # Create distance - move away from enemy
                                enemy_distance = mob.Distance
                                if enemy_distance < 5:  # Only kite if enemy is close
                                    # Calculate position away from enemy
                                    player_x = getattr(API.Player, 'X', 0)
                                    player_y = getattr(API.Player, 'Y', 0)
                                    enemy_x = getattr(mob, 'X', player_x)
                                    enemy_y = getattr(mob, 'Y', player_y)

                                    # Move in opposite direction (4 tiles away)
                                    flee_x = player_x + (player_x - enemy_x) * 2
                                    flee_y = player_y + (player_y - enemy_y) * 2

                                    if not API.Pathfinding():
                                        API.Pathfind(flee_x, flee_y)
                                        API.SysMsg("Kiting while bandage heals... (" + str(int(player_hp_pct)) + "% HP)", HUE_YELLOW)
                                    # Don't attack while kiting - just create distance
                                else:
                                    # Enemy far enough, keep attacking
                                    attack_enemy(mob)
                            else:
                                # Normal combat - keep attacking
                                attack_enemy(mob)

                            API.Pause(0.3)  # Brief pause between combat actions
                else:
                    current_enemy = None
                    state.set_state("idle")
            else:
                state.set_state("idle")

        elif current_state == "fleeing":
            # Framework handles fleeing - this state should transition quickly
            state.set_state("idle")

        elif current_state == "pathfinding":
            # Wait for pathfinding to complete
            if not API.Pathfinding():
                # Pathfinding complete
                API.SysMsg("Reached container area", HUE_GREEN)
                state.set_state("dumping")
            elif state.is_timeout(30.0):  # Use state machine timeout
                # Timeout - cancel pathfinding and try dumping anyway
                API.SysMsg("Pathfind timeout - trying dump anyway", HUE_YELLOW)
                API.CancelPathfinding()
                state.set_state("dumping")

        elif current_state == "dumping":
            # Check if we need to pathfind first
            if not storage.is_in_range(3):
                # Too far, pathfind first
                if storage.pathfind_to_container():
                    state.set_state("pathfinding")
                else:
                    # Pathfind failed, pause
                    API.SysMsg("Can't reach container! Move closer manually.", HUE_RED)
                    PAUSED = True
                    state.set_state("idle")
                continue

            # Close enough, dump resources
            if storage.dump_resources():
                # Track session totals BEFORE clearing counts
                session_ore += ore_count
                session_logs += log_count

                session_dumps += 1
                stats.increment("dumps")

                # Update counts and weight after dump
                update_resource_counts()
                state.set_state("idle")
                API.SysMsg("======================", HUE_GREEN)
                API.SysMsg("Dump complete!", HUE_GREEN)

                # Check if journal shows emergency charge was used
                if travel.check_out_of_reagents():
                    API.SysMsg("╔════════════════════════════════════╗", HUE_RED)
                    API.SysMsg("║  OUT OF REAGENTS DETECTED!         ║", HUE_RED)
                    API.SysMsg("║  SCRIPT PAUSED - RESTOCK REGS!     ║", HUE_RED)
                    API.SysMsg("║  Click RESUME when ready           ║", HUE_RED)
                    API.SysMsg("╚════════════════════════════════════╝", HUE_RED)
                    PAUSED = True
                    travel.at_home = True
                else:
                    # Normal dump - transition to waiting state before auto-recall
                    API.SysMsg("Auto-recalling to next spot in 2 seconds...", HUE_YELLOW)
                    API.SysMsg("======================", HUE_GREEN)
                    state.set_state("waiting_to_recall")
            else:
                state.set_state("idle")
                PAUSED = True

        elif current_state == "waiting_to_recall":
            # Non-blocking wait before auto-recall
            elapsed = state.get_elapsed()

            # Debug: Show countdown every 0.5s
            if int(elapsed * 2) != int((elapsed - 0.1) * 2):  # Every 0.5s
                remaining = max(0, 2.0 - elapsed)
                API.SysMsg("Recalling in " + str(round(remaining, 1)) + "s...", HUE_GRAY)

            if elapsed >= 2.0:
                API.SysMsg("2 seconds elapsed, attempting recall...", HUE_YELLOW)
                # Auto-recall to next gathering spot
                if travel.rotate_to_next_spot():
                    # Calculate spot number AFTER rotation
                    current_gathering_spot = (travel.current_spot - 1) % num_gathering_spots + 1
                    API.SysMsg("Auto-resumed - Gathering at spot " + str(current_gathering_spot) + "/" + str(num_gathering_spots), HUE_GREEN)
                    state.set_state("idle")
                else:
                    API.SysMsg("╔════════════════════════════════════╗", HUE_RED)
                    API.SysMsg("║  Auto-recall failed!               ║", HUE_RED)
                    API.SysMsg("║  Script PAUSED - check reagents    ║", HUE_RED)
                    API.SysMsg("║  Click RESUME when ready           ║", HUE_RED)
                    API.SysMsg("╚════════════════════════════════════╝", HUE_RED)
                    PAUSED = True
                    travel.at_home = True  # Mark as at home so RESUME button works
                    state.set_state("idle")
            # else: Stay in waiting_to_recall state until 2 seconds elapse

        # Update display periodically
        now = time.time()
        if now - last_display_update > DISPLAY_UPDATE_INTERVAL:
            update_display()
            last_display_update = now

            # Update session runtime
            runtime_seconds = stats.get_runtime()
            runtime_text = format_time_elapsed(runtime_seconds)

            if "session_runtime_label" in controls:
                controls["session_runtime_label"].SetText("Runtime: " + runtime_text)

            # Update session totals
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
