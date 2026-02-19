# Util_TomeDumper_v2.py
# Refactored bag dumping utility for storage tomes
# by Coryigon for UO Unchained
#
# Features:
# - Capture tome serials, gump IDs, and button IDs
# - Optional item graphics filtering
# - Optional container targeting
# - Multi-tome configurations
# - Enable/disable tomes
# - Hotkeys for dumping

import API
import time
import sys
import os

# Add parent directory (CoryCustom root) to path for library imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from LegionUtils import *

# ============ CONSTANTS ============
WINDOW_WIDTH = 280
MAIN_HEIGHT = 400
CONFIG_WIDTH = 400
CONFIG_HEIGHT = 550
TESTER_WIDTH = 320
TESTER_HEIGHT = 200

# Color hues
HUE_RED = 32        # Danger/error
HUE_GREEN = 68      # Success/active
HUE_YELLOW = 43     # Warning
HUE_GRAY = 90       # Neutral

# ============ PERSISTENCE KEYS ============
KEY_PREFIX = "TomeDumper_"
TOMES_KEY = KEY_PREFIX + "Tomes"
MAIN_POS_KEY = KEY_PREFIX + "MainXY"
CONFIG_POS_KEY = KEY_PREFIX + "ConfigXY"
TESTER_POS_KEY = KEY_PREFIX + "TesterXY"

# ============ RUNTIME STATE ============
tomes = []
editing_tome = None
editing_index = -1
editing_dirty = False

# Gumps
main_gump = None
config_gump = None
tester_gump = None

# Button references
main_controls = {}
config_controls = {}
tester_controls = {}

# Capture state
capturing_tome = False
capturing_container = False
capturing_items = False
detecting_gump = False
testing_buttons = False

# Stats
session_dumps = 0
session_items = 0
last_dump_result = ""

# Display update timing
last_main_display_update = 0
MAIN_DISPLAY_INTERVAL = 1.0

# Config rebuild guard (prevents duplicate config gumps)
config_building = False
last_config_build_time = 0
CONFIG_BUILD_COOLDOWN = 0.2
_config_gump_gen = 0  # Incremented on each rebuild; on_config_closed ignores stale callbacks

# Item count cache (to avoid expensive recalculation)
item_count_cache = {}
last_count_cache_update = 0
COUNT_CACHE_INTERVAL = 2.0

# Utilities
gump_capture = GumpCapture()
error_mgr = ErrorManager(cooldown=5.0)

# UI controls (stored globally so they persist and can be updated without rebuild)
name_text_box = None
name_display_label = None

# Targeting mode buttons
mode_buttons = {
    "none": None,
    "container": None,
    "single": None,
    "multi": None
}

# Auto-retarget buttons
retarget_buttons = {
    "on": None,
    "off": None
}

# Graphic targeting buttons
graphic_buttons = {
    "on": None,
    "off": None
}

# Hue specific buttons
hue_buttons = {
    "on": None,
    "off": None
}

# ============ UTILITY FUNCTIONS ============
def debug_msg(text):
    """Debug message helper"""
    API.SysMsg("DEBUG: " + text, 88)

def resolve_target_containers(tome_config, validate=False):
    """Resolve target containers for container/multi_item modes.

    Returns a list of container serials. If validate=True and any container
    is missing, returns None.
    """
    targeting_mode = tome_config.get("targeting_mode", "container")
    if targeting_mode not in ["container", "multi_item"]:
        return []

    containers = []

    if tome_config.get("use_graphic_targeting", False):
        target_graphic = tome_config.get("target_graphic", 0)
        if target_graphic == 0:
            return []

        if not API.Player:
            return []
        backpack = API.Player.Backpack
        if not backpack:
            return []

        backpack_serial = backpack.Serial if hasattr(backpack, 'Serial') else backpack
        items = API.ItemsInContainer(backpack_serial, recursive=False)
        if not items:
            return []

        for item in items:
            if not hasattr(item, 'Graphic'):
                continue
            if item.Graphic != target_graphic:
                continue

            if tome_config.get("target_hue_specific", False):
                target_hue = tome_config.get("target_hue", 0)
                item_hue = getattr(item, 'Hue', 0)
                if item_hue != target_hue:
                    continue

            containers.append(item.Serial)
    else:
        containers = tome_config.get("target_containers", [])
        if not containers:
            old_container = tome_config.get("target_container", 0)
            if old_container > 0:
                containers = [old_container]

    if validate:
        for container_serial in containers:
            if not API.FindItem(container_serial):
                return None

    return containers

def get_items_to_dump(tome_config):
    """Get items matching tome's filter from configured containers (or backpack if none)"""
    try:
        all_matching = []

        targeting_mode = tome_config.get("targeting_mode", "container")
        containers_to_check = resolve_target_containers(tome_config, validate=False)

        # For non-container modes, or if no containers resolved, check backpack
        if not containers_to_check:
            if targeting_mode in ["container", "multi_item"]:
                return []
            if not API.Player:
                return []
            backpack = API.Player.Backpack
            if backpack:
                containers_to_check = [backpack.Serial]

        # Check each container
        for container_serial in containers_to_check:
            items = API.ItemsInContainer(container_serial, recursive=False)
            if not items:
                continue

            # No filter = add all items (WARNING!)
            if not tome_config.get("item_graphics", []):
                all_matching.extend(items)
            else:
                # Filter by graphics
                for item in items:
                    if hasattr(item, 'Graphic') and item.Graphic in tome_config["item_graphics"]:
                        all_matching.append(item)

        return all_matching
    except Exception as e:
        debug_msg("get_items_to_dump error: " + str(e))
        return []

def count_items_for_tome(tome_config):
    """Count items that match tome's filter"""
    items = get_items_to_dump(tome_config)
    return len(items)

def update_item_count_cache():
    """Update cached item counts for all tomes (rate-limited)"""
    global item_count_cache, last_count_cache_update

    if time.time() - last_count_cache_update < COUNT_CACHE_INTERVAL:
        return

    item_count_cache = {}
    for i, tome in enumerate(tomes):
        item_count_cache[i] = count_items_for_tome(tome)

    last_count_cache_update = time.time()

def get_cached_item_count(tome_index):
    """Get cached item count for tome (or 0 if not cached)"""
    return item_count_cache.get(tome_index, 0)

# ============ CORE LOGIC - DUMP PROCESS ============
def get_tome_gump_id(tome_serial):
    """Get the current gump ID for an open tome (handles dynamic IDs)"""
    try:
        tome = API.FindItem(tome_serial)
        if not tome:
            return 0

        # Try to get the container gump from the tome item
        try:
            gump = tome.GetContainerGump()
            if gump:
                # Use ServerSerial (consistent) first, then LocalSerial
                if hasattr(gump, 'ServerSerial') and gump.ServerSerial:
                    return gump.ServerSerial
                elif hasattr(gump, 'LocalSerial') and gump.LocalSerial:
                    return gump.LocalSerial
        except:
            pass

        # Fallback: scan all gumps (less reliable but works)
        try:
            all_gumps = API.GetAllGumps()
            if all_gumps and len(all_gumps) > 0:
                # Return the most recent gump (last in list)
                gump = all_gumps[-1]
                # Use ServerSerial first (consistent ID)
                if hasattr(gump, 'ServerSerial') and gump.ServerSerial:
                    return gump.ServerSerial
                elif hasattr(gump, 'LocalSerial') and gump.LocalSerial:
                    return gump.LocalSerial
                else:
                    return gump
        except:
            pass

        return 0
    except Exception as e:
        API.SysMsg("Error getting gump ID: " + str(e), 32)
        return 0

def open_tome_and_get_gump_id(tome_serial, expected_gump_id=0, timeout=3.0):
    """Open the tome and return the current gump ID (dynamic-safe)."""
    API.UseObject(tome_serial, False)
    API.Pause(0.8)

    if expected_gump_id > 0:
        wait_until = time.time() + timeout
        while time.time() < wait_until:
            if API.HasGump(expected_gump_id):
                break
            API.Pause(0.1)

    # Always resolve current gump ID from the open tome
    return get_tome_gump_id(tome_serial)

def dump_single_tome(tome_config):
    """Dump items to a single tome"""
    global session_dumps, session_items, last_dump_result

    current_gump_id = 0

    try:
        # Find tome item
        tome = API.FindItem(tome_config["tome_serial"])
        if not tome:
            error_mgr.set_error("Tome not found: " + str(tome_config.get("name", "Unknown")))
            return False

        # Move to tome if it's out of range
        tome_distance = getattr(tome, 'Distance', 999)
        if tome_distance > 2:
            API.SysMsg("Moving to tome...", 68)
            # Pathfind to the tome
            if hasattr(API, 'PathfindEntity'):
                API.PathfindEntity(tome.Serial, 1)
                # Wait for pathfinding to complete or timeout
                timeout = time.time() + 5.0
                while time.time() < timeout:
                    API.Pause(0.1)
                    if not API.Pathfinding():
                        break
                    # Check if we're close enough
                    updated_tome = API.FindItem(tome_config["tome_serial"])
                    if updated_tome and getattr(updated_tome, 'Distance', 999) <= 2:
                        break

                # Verify we're in range now
                tome = API.FindItem(tome_config["tome_serial"])
                if tome and getattr(tome, 'Distance', 999) > 2:
                    error_mgr.set_error("Could not reach tome: " + str(tome_config.get("name", "Unknown")))
                    return False
            else:
                API.SysMsg("Cannot pathfind - tome too far", 32)
                return False

        # Get target containers (for container mode and multi_item mode)
        targeting_mode = tome_config.get("targeting_mode", "container")

        # Populate containers for both container and multi_item modes
        if targeting_mode in ["container", "multi_item"]:
            target_containers = resolve_target_containers(tome_config, validate=True)
            if target_containers is None:
                error_mgr.set_error("Container not found for " + str(tome_config.get("name", "Unknown")))
                return False

            if not target_containers and targeting_mode == "container":
                error_mgr.set_error("No target containers set for " + str(tome_config.get("name", "Unknown")))
                return False

            if not target_containers and tome_config.get("use_graphic_targeting", False):
                target_graphic = tome_config.get("target_graphic", 0)
                hue_info = " with hue 0x{:X}".format(tome_config.get("target_hue", 0)) if tome_config.get("target_hue_specific", False) else ""
                API.SysMsg("No containers found with graphic 0x{:X}{}".format(target_graphic, hue_info), 43)
                return True
        else:
            target_containers = []

        # Count matching items after container resolution
        item_count = count_items_for_tome(tome_config)
        if item_count == 0:
            API.SysMsg("No items to dump for " + str(tome_config.get("name", "Unknown")), 90)
            return True

        # Handle different targeting modes
        # targeting_mode already declared above

        if targeting_mode == "none":
            # No targeting - just click button once
            # Open tome and resolve current gump ID (dynamic)
            current_gump_id = open_tome_and_get_gump_id(tome.Serial, tome_config.get("gump_id", 0))
            if current_gump_id == 0:
                error_mgr.set_error("Could not get gump ID for: " + str(tome_config.get("name", "Unknown")))
                return False

            # Click fill button with current gump ID
            if tome_config["fill_button_id"] > 0:
                API.ReplyGump(tome_config["fill_button_id"], current_gump_id)
                API.Pause(0.5)

            session_dumps += 1
            session_items += item_count
            last_dump_result = "Dumped to " + str(tome_config.get("name", "Unknown"))
            API.SysMsg(last_dump_result, 68)

        elif targeting_mode == "container":
            # Targeting needed - dump once per container
            total_dumped = 0
            for i, container_serial in enumerate(target_containers):
                API.SysMsg("Dumping from container " + str(i + 1) + "/" + str(len(target_containers)) + "...", 68)

                # Open tome gump and resolve current ID (dynamic)
                current_gump_id = open_tome_and_get_gump_id(tome.Serial, tome_config.get("gump_id", 0))
                if current_gump_id == 0:
                    error_mgr.set_error("Could not get gump ID for: " + str(tome_config.get("name", "Unknown")))
                    break  # Stop processing remaining containers

                API.Pause(0.3)

                # Clear any existing targets
                cancel_all_targets()
                API.Pause(0.2)

                # Click button to create target cursor
                if tome_config["fill_button_id"] > 0:
                    API.SysMsg("Clicking button " + str(tome_config["fill_button_id"]) + "...", 88)
                    API.ReplyGump(tome_config["fill_button_id"], current_gump_id)
                    API.Pause(0.3)

                    # Wait for target cursor to be ready
                    API.SysMsg("Waiting for target cursor...", 88)
                    if API.WaitForTarget(timeout=3.0):
                        # Target the container
                        API.SysMsg("Targeting container 0x{:X}...".format(container_serial), 68)
                        API.Target(container_serial)
                        API.Pause(0.8)
                        total_dumped += 1

                        # Clean up any lingering cursor
                        if API.HasTarget():
                            API.CancelTarget()
                    else:
                        API.SysMsg("Target cursor timeout", 32)

            # Update stats
            session_dumps += total_dumped
            session_items += item_count
            last_dump_result = "Dumped from " + str(total_dumped) + " containers to " + str(tome_config.get("name", "Unknown"))
            API.SysMsg(last_dump_result, 68)

        elif targeting_mode == "single_item":
            # Single item mode - click button, target one item, done
            current_gump_id = open_tome_and_get_gump_id(tome.Serial, tome_config.get("gump_id", 0))
            if current_gump_id == 0:
                error_mgr.set_error("Gump timeout: " + str(tome_config.get("name", "Unknown")))
                return False

            # Click button
            if tome_config["fill_button_id"] > 0:
                API.SysMsg("Click button, target 1 item...", 68)
                cancel_all_targets()
                API.Pause(0.2)

                API.ReplyGump(tome_config["fill_button_id"], current_gump_id)
                API.Pause(0.3)

                # Wait for target cursor to be ready
                if API.WaitForTarget(timeout=3.0):
                    API.SysMsg("Target item now (ESC to cancel)...", 68)
                    # Wait for user to target
                    timeout = time.time() + 30.0
                    targeted = False

                    while time.time() < timeout:
                        if not API.HasTarget():
                            targeted = True  # Cursor cleared - user targeted
                            break
                        API.Pause(0.1)

                    if targeted:
                        session_dumps += 1
                        last_dump_result = "Single item to " + str(tome_config.get("name", "Unknown"))
                        API.SysMsg(last_dump_result, 68)
                    else:
                        API.SysMsg("Targeting timed out", 43)
                else:
                    API.SysMsg("Target cursor timeout", 32)

        elif targeting_mode == "multi_item":
            # Multi item mode - target items repeatedly
            auto_retarget = tome_config.get("auto_retarget", True)

            # Check if we have containers configured
            has_containers = len(target_containers) > 0

            current_gump_id = open_tome_and_get_gump_id(tome.Serial, tome_config.get("gump_id", 0))
            if current_gump_id == 0:
                error_mgr.set_error("Gump timeout: " + str(tome_config.get("name", "Unknown")))
                return False

            if has_containers:
                # Container mode - search containers and auto-target matching items
                API.SysMsg("Searching " + str(len(target_containers)) + " containers for items...", 68)
                API.SysMsg("Container serials: " + ", ".join("0x{:X}".format(c) for c in target_containers), 88)
                items_targeted = 0

                for container_idx, container_serial in enumerate(target_containers):
                    API.SysMsg("Processing container " + str(container_idx + 1) + "/" + str(len(target_containers)) + ": 0x{:X}".format(container_serial), 88)
                    container = API.FindItem(container_serial)
                    if not container:
                        API.SysMsg("Container 0x{:X} not found, skipping".format(container_serial), 32)
                        continue

                    # Get items from this container
                    container_items = API.ItemsInContainer(container_serial, recursive=False)
                    if not container_items:
                        API.SysMsg("Container 0x{:X} is empty".format(container_serial), 43)
                        continue

                    API.SysMsg("Container 0x{:X} has {} items total".format(container_serial, len(container_items)), 88)

                    # Filter by item graphics if specified
                    items_to_dump = []
                    filter_graphics = tome_config.get("item_graphics", [])

                    if filter_graphics:
                        API.SysMsg("Filtering for graphics: " + ", ".join("0x{:X}".format(g) for g in filter_graphics), 88)
                        for item in container_items:
                            if hasattr(item, 'Graphic'):
                                if item.Graphic in filter_graphics:
                                    items_to_dump.append(item)
                                    API.SysMsg("  Found matching item: graphic 0x{:X}, serial 0x{:X}".format(item.Graphic, item.Serial), 88)
                    else:
                        API.SysMsg("No filter - will target ALL items", 43)
                        items_to_dump = list(container_items)

                    if not items_to_dump:
                        API.SysMsg("No matching items in container 0x{:X}, continuing to next...".format(container_serial), 43)
                        continue

                    API.SysMsg("Found " + str(len(items_to_dump)) + " items to dump from 0x{:X}".format(container_serial), 68)

                    # Target each item
                    for idx, item in enumerate(items_to_dump):
                        API.SysMsg("Targeting item " + str(idx + 1) + "/" + str(len(items_to_dump)) + "...", 88)

                        # Verify item still exists before targeting
                        if not API.FindItem(item.Serial):
                            API.SysMsg("Item 0x{:X} no longer exists, skipping".format(item.Serial), 43)
                            continue

                        # Click button if needed
                        if not API.HasTarget():
                            API.SysMsg("  No target cursor, clicking button...", 88)

                            if current_gump_id == 0 or not API.HasGump(current_gump_id):
                                API.SysMsg("  Gump not open, reopening tome...", 88)
                                current_gump_id = open_tome_and_get_gump_id(tome.Serial, tome_config.get("gump_id", 0))
                                if current_gump_id == 0:
                                    API.SysMsg("  Gump timeout, stopping", 32)
                                    break

                            if tome_config["fill_button_id"] > 0:
                                API.SysMsg("  Clicking button " + str(tome_config["fill_button_id"]), 88)
                                API.ReplyGump(tome_config["fill_button_id"], current_gump_id)
                                API.Pause(0.3)

                                # Verify cursor appeared after button click
                                if not API.WaitForTarget(timeout=1.0):
                                    API.SysMsg("Button didn't create cursor - stopping", 32)
                                    break

                        # Target cursor should already be active from button click above
                        # Brief pause to ensure cursor is ready, then send target
                        API.Pause(0.2)

                        if API.HasTarget():
                            API.SysMsg("  Targeting item serial 0x{:X}".format(item.Serial), 68)
                            API.Target(item.Serial)
                            items_targeted += 1
                            API.Pause(0.5)

                            # If auto-retarget, wait for cursor to reappear
                            if auto_retarget:
                                API.SysMsg("  Waiting for auto-retarget...", 88)
                                retarget_timeout = time.time() + 2.0
                                cursor_reappeared = False
                                while time.time() < retarget_timeout:
                                    if API.HasTarget():
                                        cursor_reappeared = True
                                        break
                                    API.Pause(0.1)

                                if not cursor_reappeared:
                                    API.SysMsg("Auto-retarget stopped working", 43)
                                    break
                        else:
                            API.SysMsg("  Cursor disappeared, stopping", 32)
                            break

                    # Finished processing this container
                    API.SysMsg("Finished processing container 0x{:X}".format(container_serial), 88)

                # Finished processing all containers
                session_dumps += items_targeted
                last_dump_result = "Targeted " + str(items_targeted) + " items from " + str(len(target_containers)) + " containers"
                API.SysMsg(last_dump_result, 68)

            elif auto_retarget:
                # Auto-retarget mode - target multiple items
                API.SysMsg("Click button, target items (ESC when done)...", 68)
                cancel_all_targets()
                API.Pause(0.2)

                # Click button once
                if tome_config["fill_button_id"] > 0:
                    API.ReplyGump(tome_config["fill_button_id"], current_gump_id)
                    API.Pause(0.5)

                # Wait for targets
                items_targeted = 0
                previous_had_target = False
                timeout = time.time() + 60.0  # 60 second timeout for multi-targeting
                while time.time() < timeout:
                    API.ProcessCallbacks()  # Allow script stop
                    if API.StopRequested:
                        break

                    has_target_now = API.HasTarget()

                    if has_target_now:
                        previous_had_target = True
                        API.Pause(0.1)
                    else:
                        # Cursor just cleared - check if we actually targeted
                        if previous_had_target and current_gump_id > 0 and API.HasGump(current_gump_id):
                            items_targeted += 1
                            previous_had_target = False
                            API.Pause(0.3)  # Wait for potential auto-retarget
                        elif current_gump_id == 0 or not API.HasGump(current_gump_id):
                            # Gump closed or user cancelled
                            break
                        else:
                            # No previous target state - wait
                            API.Pause(0.1)

                session_dumps += items_targeted
                last_dump_result = "Targeted " + str(items_targeted) + " items to " + str(tome_config.get("name", "Unknown"))
                API.SysMsg(last_dump_result, 68)
            else:
                # Manual retarget mode - click button for each item
                API.SysMsg("Click button for each item (ESC to stop)...", 68)
                items_targeted = 0

                # Loop: click button, wait for target, repeat
                for attempt in range(100):  # Max 100 items
                    cancel_all_targets()
                    API.Pause(0.2)

                    # Reopen gump if needed
                    if current_gump_id == 0 or not API.HasGump(current_gump_id):
                        current_gump_id = open_tome_and_get_gump_id(tome.Serial, tome_config.get("gump_id", 0))
                        if current_gump_id == 0:
                            API.SysMsg("Gump timeout", 32)
                            break

                    # Click button
                    if tome_config["fill_button_id"] > 0:
                        API.ReplyGump(tome_config["fill_button_id"], current_gump_id)
                        API.Pause(0.3)

                    # Wait for target cursor to be ready
                    if not API.WaitForTarget(timeout=3.0):
                        # No cursor - done
                        break

                    # Wait for user to target (or ESC)
                    target_timeout = time.time() + 30.0
                    had_target = True
                    while time.time() < target_timeout:
                        if not API.HasTarget():
                            had_target = False
                            break
                        API.Pause(0.1)

                    if had_target:
                        # User cancelled (ESC)
                        break

                    items_targeted += 1
                    API.SysMsg("Item " + str(items_targeted) + " targeted", 68)
                    API.Pause(0.5)

                session_dumps += items_targeted
                last_dump_result = "Targeted " + str(items_targeted) + " items to " + str(tome_config.get("name", "Unknown"))
                API.SysMsg(last_dump_result, 68)

        return True

    except Exception as e:
        error_mgr.set_error("Dump error: " + str(e))
        return False

    finally:
        # CLEANUP: Close tome gump if it's open
        gump_id = current_gump_id
        if gump_id > 0 and API.HasGump(gump_id):
            try:
                API.CloseGump(gump_id)
                API.Pause(0.2)  # Brief pause to ensure closure
                debug_msg("Closed tome gump: ID " + str(gump_id))
            except Exception as cleanup_err:
                debug_msg("Error closing tome gump: " + str(cleanup_err))
                pass  # Ignore errors closing gump

def dump_enabled_tomes():
    """Dump to all enabled tomes"""
    global last_dump_result

    enabled = [t for t in tomes if t.get("enabled", True)]
    if not enabled:
        API.SysMsg("No tomes enabled", 43)
        return

    API.SysMsg("Dumping to " + str(len(enabled)) + " tomes...", 68)

    success_count = 0
    for tome in enabled:
        if dump_single_tome(tome):
            success_count += 1
        API.Pause(0.5)

    last_dump_result = "Dumped to " + str(success_count) + "/" + str(len(enabled)) + " tomes"
    API.SysMsg(last_dump_result, 68)
    update_main_display()

def dump_all_tomes():
    """Dump to all tomes (ignoring enabled state)"""
    global last_dump_result

    if not tomes:
        API.SysMsg("No tomes configured", 43)
        return

    API.SysMsg("Dumping to ALL " + str(len(tomes)) + " tomes...", 68)

    success_count = 0
    for tome in tomes:
        if dump_single_tome(tome):
            success_count += 1
        API.Pause(0.5)

    last_dump_result = "Dumped to " + str(success_count) + "/" + str(len(tomes)) + " tomes"
    API.SysMsg(last_dump_result, 68)
    update_main_display()

# ============ PERSISTENCE ============
def save_tome_list(tome_list, key):
    """Save list of tomes to persistence"""
    import json
    try:
        tome_data = json.dumps(tome_list)
        API.SavePersistentVar(key, tome_data, API.PersistentVar.Char)
    except Exception as e:
        API.SysMsg("Error saving tomes: " + str(e), HUE_RED)

def load_tome_list(key):
    """Load list of tomes from persistence"""
    import json
    try:
        tome_data = API.GetPersistentVar(key, "[]", API.PersistentVar.Char)
        if tome_data:
            return json.loads(tome_data)
    except Exception as e:
        API.SysMsg("Error loading tomes: " + str(e), HUE_RED)
    return []

def save_tomes():
    """Save tome configurations"""
    save_tome_list(tomes, TOMES_KEY)

def load_tomes():
    """Load tome configurations"""
    global tomes
    tomes = load_tome_list(TOMES_KEY)

# ============ DISPLAY UPDATES ============
def update_main_display():
    """Update main window display (rate-limited)"""
    global last_main_display_update

    if main_gump is None:
        return

    # Rate-limit updates to prevent lag
    if time.time() - last_main_display_update < MAIN_DISPLAY_INTERVAL:
        return
    last_main_display_update = time.time()

    # Update stats label
    if "stats_label" in main_controls:
        main_controls["stats_label"].SetText(
            "Session: " + str(session_dumps) + " dumps, " + str(session_items) + " items"
        )

    # Update status label
    if "status_label" in main_controls and last_dump_result:
        main_controls["status_label"].SetText(last_dump_result)

# ============ GUI CALLBACKS - MAIN WINDOW ============
def on_config_clicked():
    """Open config window"""
    # Only build if window doesn't exist
    if config_gump is None:
        build_config_gump()
    else:
        API.SysMsg("Config window already open", 43)

def on_dump_enabled_clicked():
    """Dump to enabled tomes"""
    dump_enabled_tomes()

def on_dump_all_clicked():
    """Dump to all tomes"""
    dump_all_tomes()

def on_main_closed():
    """Main window closed"""
    global main_gump, main_controls
    save_window_position(MAIN_POS_KEY, main_gump)
    main_gump = None
    main_controls = {}

# ============ GUI CALLBACKS - CONFIG WINDOW ============
def on_name_changed():
    """Handle name text input change"""
    global editing_dirty

    if not editing_tome or "name_input" not in config_controls:
        return

    new_name = config_controls["name_input"].Text.strip()
    if new_name != editing_tome["name"]:
        editing_tome["name"] = new_name
        editing_dirty = True

def on_add_tome_clicked():
    """Start adding new tome"""
    global editing_tome, editing_index, editing_dirty

    try:
        API.SysMsg("on_add_tome_clicked() called", 68)

        # Warn if already editing with unsaved changes
        if editing_tome and editing_dirty:
            API.SysMsg("Save or cancel current edit first!", 43)
            return

        editing_tome = {
            "name": str("Weapon Tome"),
            "tome_serial": int(0),
            "gump_id": int(0),
            "fill_button_id": int(0),
            "needs_targeting": bool(True),  # Match default targeting_mode
            "target_containers": list([]),
            "use_graphic_targeting": bool(False),
            "target_graphic": int(0),
            "target_hue_specific": bool(False),
            "target_hue": int(0),
            "item_graphics": list([]),
            "targeting_mode": str("container"),  # "container", "single_item", "multi_item"
            "auto_retarget": bool(True),  # For multi_item mode
            "enabled": bool(True)
        }
        editing_index = -1
        editing_dirty = False

        API.SysMsg("Set editing_tome: " + str(editing_tome is not None), 68)
        debug_msg("editing_tome type: " + str(type(editing_tome)))
        debug_msg("editing_tome keys: " + str(list(editing_tome.keys()) if editing_tome else "None"))

        # Rebuild window to show edit panel (intentional - switches UI mode)
        build_config_gump()

        API.SysMsg("After build_config_gump, editing_tome is: " + str(editing_tome is not None), 68)
    except Exception as e:
        API.SysMsg("ERROR in on_add_tome_clicked: " + str(e), 32)
        import traceback
        API.SysMsg(str(traceback.format_exc()), 32)

def on_target_tome_clicked():
    """Capture tome serial"""
    global capturing_tome, editing_dirty

    if capturing_tome:
        return

    if not editing_tome:
        return

    try:
        capturing_tome = True
        API.SysMsg("Target the tome...", 68)

        target = request_target(timeout=10)

        if not target:
            API.SysMsg("Cancelled", 90)
            return

        # Re-check editing state after blocking call
        if not editing_tome:
            API.SysMsg("Editing cancelled", 90)
            return

        tome = API.FindItem(target)
        if not tome:
            error_mgr.set_error("Invalid tome")
            return

        editing_tome["tome_serial"] = int(target)
        editing_dirty = True
        API.SysMsg("Tome captured: 0x{:X}".format(target), 68)

        # Update config window label directly instead of rebuilding
        if "tome_serial_label" in config_controls:
            config_controls["tome_serial_label"].SetText("Tome: 0x{:X}".format(target))
        else:
            # If label doesn't exist (first time capturing), rebuild to show it
            build_config_gump()

        # Update target tome button color if it exists
        if "target_tome_btn" in config_controls:
            config_controls["target_tome_btn"].SetBackgroundHue(68)  # Green when captured
    except Exception as e:
        API.SysMsg("ERROR in on_target_tome_clicked: " + str(e), 32)
    finally:
        capturing_tome = False

def on_detect_gump_clicked():
    """Detect gump ID automatically"""
    global detecting_gump, editing_dirty

    if detecting_gump:
        return

    try:
        detecting_gump = True
        API.SysMsg("Open tome now...", 68)

        # Update button text directly instead of rebuilding entire gump
        if "detect_gump_btn" in config_controls:
            config_controls["detect_gump_btn"].SetText("[DETECTING...]")
            config_controls["detect_gump_btn"].SetBackgroundHue(43)

        gump_id = gump_capture.detect_new_gump(None, timeout=10)

        if gump_id > 0 and editing_tome:
            editing_tome["gump_id"] = int(gump_id)
            editing_dirty = True
            API.SysMsg("Gump captured: ID {}".format(gump_id), 68)

            # Update config window label directly instead of rebuilding
            if "gump_id_label" in config_controls:
                config_controls["gump_id_label"].SetText("Gump ID: " + str(gump_id))
            else:
                # If label doesn't exist (first time capturing), rebuild to show it
                build_config_gump()

            # Update detect button
            if "detect_gump_btn" in config_controls:
                config_controls["detect_gump_btn"].SetText("[DETECT GUMP]")
                config_controls["detect_gump_btn"].SetBackgroundHue(68)  # Green when captured
        else:
            API.SysMsg("No gump detected", 32)
            # Just reset button text instead of rebuilding
            if "detect_gump_btn" in config_controls:
                config_controls["detect_gump_btn"].SetText("[DETECT GUMP]")
                config_controls["detect_gump_btn"].SetBackgroundHue(43)
    except Exception as e:
        API.SysMsg("ERROR in on_detect_gump_clicked: " + str(e), 32)
    finally:
        detecting_gump = False

def on_test_buttons_clicked():
    """Open button tester window"""
    if editing_tome and editing_tome["gump_id"] > 0:
        build_tester_gump()
    else:
        API.SysMsg("Set gump ID first", 43)

def on_set_name_clicked():
    """Read name from text box and save to tome"""
    global editing_dirty, name_text_box, name_display_label

    if not editing_tome:
        return

    if not name_text_box:
        API.SysMsg("Text box not initialized", 32)
        return

    try:
        # Read from text box (like Runebook script does)
        name_text = name_text_box.Text

        if not name_text or str(name_text).strip() == "":
            API.SysMsg("Name cannot be empty", 32)
            return

        name = str(name_text).strip()
        editing_tome["name"] = name
        editing_dirty = True

        # Update the display label directly without rebuilding
        if name_display_label:
            name_display_label.SetText("Saved: " + name)

        API.SysMsg("Name saved: '" + name + "'", 68)

    except Exception as e:
        API.SysMsg("Error reading name: " + str(e), 32)

def on_targeting_mode_set(mode):
    """Set targeting mode"""
    global editing_dirty

    if editing_tome:
        old_mode = editing_tome.get("targeting_mode", "container")
        editing_tome["targeting_mode"] = mode
        # Set needs_targeting based on mode for backward compatibility
        editing_tome["needs_targeting"] = (mode != "none")
        editing_dirty = True

        # Update button colors directly
        for key in ["none", "container", "single", "multi"]:
            btn_key = "mode_" + key
            if btn_key in config_controls:
                config_controls[btn_key].SetBackgroundHue(68 if mode == key or (key == "single" and mode == "single_item") or (key == "multi" and mode == "multi_item") else 90)

        # Only rebuild if we need to show/hide different UI sections
        # (container list, auto-retarget options, etc.)
        if (old_mode == "container") != (mode == "container") or (old_mode == "multi_item") != (mode == "multi_item"):
            build_config_gump()
        else:
            API.SysMsg("Targeting mode: " + mode, 68)

def on_auto_retarget_set(value):
    """Set auto-retarget for multi-item mode"""
    global editing_dirty

    if editing_tome:
        editing_tome["auto_retarget"] = value
        editing_dirty = True
        # Don't rebuild for this - it's just a simple toggle
        API.SysMsg("Auto-retarget: " + ("YES" if value else "NO"), 68)

def on_add_target_clicked():
    """Add a target container to the list"""
    global capturing_container, editing_dirty

    if capturing_container:
        return

    if not editing_tome:
        return

    try:
        capturing_container = True
        API.SysMsg("Target yourself (for backpack) or a container...", 68)

        target = request_target(timeout=15)

        if not target:
            API.SysMsg("Cancelled", 90)
            return

        # Null safety check for API.Player
        if not API.Player:
            API.SysMsg("Player not available", 32)
            return

        player_serial = getattr(API.Player, 'Serial', None)
        if not player_serial:
            API.SysMsg("Player serial not available", 32)
            return

        # Check if they targeted themselves (the player)
        if target == player_serial:
            # Use player's backpack
            backpack = API.Player.Backpack
            if not backpack:
                API.SysMsg("No backpack found", 32)
                return
            target = backpack.Serial if hasattr(backpack, 'Serial') else backpack
            API.SysMsg("Using your backpack: 0x{:X}".format(target), 68)
        else:
            # Try as item (container)
            item = API.FindItem(target)
            if not item:
                API.SysMsg("Invalid target", 32)
                return
            API.SysMsg("Added container: 0x{:X}".format(target), 68)

        # Initialize list if needed
        if "target_containers" not in editing_tome:
            editing_tome["target_containers"] = []

        # Check for duplicates
        if target in editing_tome["target_containers"]:
            API.SysMsg("Already added", 43)
            return

        # Add to list
        editing_tome["target_containers"].append(target)
        editing_dirty = True
        build_config_gump()
    except Exception as e:
        API.SysMsg("ERROR in on_add_target_clicked: " + str(e), 32)
    finally:
        capturing_container = False

def on_delete_target_clicked(index):
    """Remove a target container from the list"""
    global editing_dirty

    if not editing_tome:
        return

    target_containers = editing_tome.get("target_containers", [])
    if index < 0 or index >= len(target_containers):
        return

    removed = target_containers[index]
    del target_containers[index]
    editing_dirty = True
    API.SysMsg("Removed target: 0x{:X}".format(removed), 90)
    build_config_gump()

def on_graphic_targeting_set(value):
    """Set graphic targeting mode"""
    global editing_dirty

    if editing_tome:
        old_value = editing_tome.get("use_graphic_targeting", False)
        editing_tome["use_graphic_targeting"] = value
        editing_dirty = True

        # Update button colors directly
        if "graphic_on" in config_controls:
            config_controls["graphic_on"].SetBackgroundHue(68 if value else 90)
        if "graphic_off" in config_controls:
            config_controls["graphic_off"].SetBackgroundHue(32 if not value else 90)

        # Only rebuild if toggling (to show/hide capture graphic section)
        if old_value != value:
            build_config_gump()
        else:
            API.SysMsg("Graphic targeting: " + ("YES" if value else "NO"), 68)

def on_capture_graphic_clicked():
    """Capture graphic and optionally hue from target"""
    global capturing_container, editing_dirty

    if capturing_container:
        return

    if not editing_tome:
        return

    try:
        capturing_container = True
        API.SysMsg("Target a container to capture its graphic/hue...", 68)

        target = request_target(timeout=15)

        if not target:
            API.SysMsg("Cancelled", 90)
            return

        # Get the item
        item = API.FindItem(target)
        if not item:
            API.SysMsg("Invalid target", 32)
            return

        # Capture graphic
        graphic = getattr(item, 'Graphic', 0)
        if graphic == 0:
            API.SysMsg("No graphic found", 32)
            return

        editing_tome["target_graphic"] = graphic
        API.SysMsg("Captured graphic: 0x{:X}".format(graphic), 68)

        # Also capture hue if hue-specific mode is on
        if editing_tome.get("target_hue_specific", False):
            hue = getattr(item, 'Hue', 0)
            editing_tome["target_hue"] = hue
            API.SysMsg("Captured hue: 0x{:X}".format(hue), 68)

        editing_dirty = True

        # Update label directly instead of rebuilding
        if "graphic_label" in config_controls:
            config_controls["graphic_label"].SetText("Graphic: 0x{:X}".format(graphic))
        else:
            # First time - rebuild to create label
            build_config_gump()

        # Update button color
        if "capture_graphic_btn" in config_controls:
            config_controls["capture_graphic_btn"].SetBackgroundHue(68)
    except Exception as e:
        API.SysMsg("ERROR in on_capture_graphic_clicked: " + str(e), 32)
    finally:
        capturing_container = False

def on_hue_specific_set(value):
    """Set hue specific mode"""
    global editing_dirty

    if editing_tome:
        editing_tome["target_hue_specific"] = value
        editing_dirty = True

        # Update button colors directly without rebuilding
        if "hue_on" in config_controls:
            config_controls["hue_on"].SetBackgroundHue(68 if value else 90)
        if "hue_off" in config_controls:
            config_controls["hue_off"].SetBackgroundHue(32 if not value else 90)

        API.SysMsg("Hue specific: " + ("YES" if value else "NO"), 68)

def on_capture_items_clicked():
    """Capture item graphics"""
    global capturing_items, editing_dirty

    if capturing_items:
        return

    try:
        capturing_items = True
        graphics = capture_item_graphics()

        if graphics and editing_tome:
            editing_tome["item_graphics"] = graphics
            editing_dirty = True
            API.SysMsg("Captured " + str(len(graphics)) + " item graphics", 68)
            # Don't rebuild - value is saved
    except Exception as e:
        API.SysMsg("ERROR in on_capture_items_clicked: " + str(e), 32)
    finally:
        capturing_items = False

def on_save_tome_clicked():
    """Save current tome being edited"""
    global editing_tome, editing_index, editing_dirty

    if not editing_tome:
        return

    # Validate name
    tome_name = editing_tome.get("name", "").strip()
    if not tome_name:
        error_mgr.set_error("Name required - type name and click [SET]")
        return

    if editing_tome["tome_serial"] == 0:
        error_mgr.set_error("Tome serial required")
        return

    # Check for duplicate serial
    for i, existing in enumerate(tomes):
        if i != editing_index and existing["tome_serial"] == editing_tome["tome_serial"]:
            error_mgr.set_error("Tome serial already exists")
            return

    # Add or update
    if editing_index >= 0:
        # Update existing
        tomes[editing_index] = editing_tome
        API.SysMsg("Tome updated: " + tome_name, 68)
    else:
        # Add new
        tomes.append(editing_tome)
        API.SysMsg("Tome added: " + tome_name, 68)

    save_tomes()
    editing_tome = None
    editing_index = -1
    editing_dirty = False
    build_config_gump()
    build_main_gump()

def on_cancel_edit_clicked():
    """Cancel editing"""
    global editing_tome, editing_index, editing_dirty

    editing_tome = None
    editing_index = -1
    editing_dirty = False
    build_config_gump()

def on_edit_tome_clicked(index):
    """Edit existing tome"""
    global editing_tome, editing_index, editing_dirty

    if index < 0 or index >= len(tomes):
        return

    # Deep copy to avoid mutating saved data
    editing_tome = dict(tomes[index])
    editing_tome["target_containers"] = list(tomes[index].get("target_containers", []))
    editing_tome["item_graphics"] = list(tomes[index].get("item_graphics", []))
    editing_index = index
    editing_dirty = False  # Start clean when loading existing
    build_config_gump()

def on_delete_tome_clicked(index):
    """Delete tome"""
    global editing_tome, editing_index

    if index < 0 or index >= len(tomes):
        return

    # Cancel edit if deleting the tome being edited
    if index == editing_index:
        editing_tome = None
        editing_index = -1
        API.SysMsg("Cancelled edit - tome deleted", 43)
    # Adjust editing_index if deleting before it
    elif index < editing_index:
        editing_index -= 1

    tome_name = tomes[index].get("name", "Unknown")
    del tomes[index]
    save_tomes()

    API.SysMsg("Deleted: " + tome_name, 90)
    build_config_gump()
    build_main_gump()

def on_toggle_tome_clicked(index):
    """Toggle tome enabled state"""
    if index < 0 or index >= len(tomes):
        return

    tomes[index]["enabled"] = not tomes[index].get("enabled", True)
    save_tomes()
    build_config_gump()
    build_main_gump()

def on_config_closed(gen=None):
    """Config window closed"""
    global config_gump, config_controls

    # Ignore stale callbacks from old gumps that fired after a programmatic rebuild
    if gen is not None and gen != _config_gump_gen:
        return

    if config_gump:
        save_window_position(CONFIG_POS_KEY, config_gump)

    # Only clear gump references, NOT editing state
    # editing_tome will be cleared explicitly in cancel/save callbacks
    config_gump = None
    config_controls = {}

# ============ GUI CALLBACKS - TESTER WINDOW ============
def on_test_button_number(button_id):
    """Test a specific button number"""
    if not editing_tome or editing_tome["gump_id"] == 0:
        return

    gump_id = editing_tome["gump_id"]

    # Test button
    result = gump_capture.test_button(gump_id, button_id)

    # Update result label
    if "result_label" in tester_controls:
        if result:
            tester_controls["result_label"].SetText("Button " + str(button_id) + " closed gump")
            API.SysMsg("Button " + str(button_id) + " closed gump", 68)
        else:
            tester_controls["result_label"].SetText("Button " + str(button_id) + " no effect")
            API.SysMsg("Button " + str(button_id) + " no effect", 90)

def on_test_custom_button():
    """Test custom button ID from text input"""
    if "custom_input" not in tester_controls:
        return

    try:
        button_id = int(tester_controls["custom_input"].Text.strip())
        on_test_button_number(button_id)
    except:
        API.SysMsg("Invalid button ID", 32)

def on_set_custom_button():
    """Set custom button ID as the fill button"""
    global editing_dirty

    if "custom_input" not in tester_controls:
        return

    try:
        button_id = int(tester_controls["custom_input"].Text.strip())
        if editing_tome:
            editing_tome["fill_button_id"] = button_id
            editing_dirty = True
            API.SysMsg("Fill button set to: " + str(button_id), 68)

            # Update config window label directly instead of rebuilding
            if "fill_button_label" in config_controls:
                config_controls["fill_button_label"].SetText("Button: " + str(button_id))
            else:
                # If label doesn't exist (button not previously set), rebuild to show it
                build_config_gump()

            # Update test button label in config if it exists
            if "test_buttons_btn" in config_controls:
                config_controls["test_buttons_btn"].SetBackgroundHue(68)  # Green when button set

            # Close tester
            if tester_gump:
                tester_gump.Dispose()
        else:
            API.SysMsg("No tome being edited", 32)
    except:
        API.SysMsg("Invalid button ID", 32)

def on_use_button_clicked(button_id):
    """Set button as tome's fill button"""
    global editing_dirty

    if editing_tome:
        editing_tome["fill_button_id"] = button_id
        editing_dirty = True
        API.SysMsg("Button " + str(button_id) + " set as fill button", 68)

        # Update config window label directly instead of rebuilding
        if "fill_button_label" in config_controls:
            config_controls["fill_button_label"].SetText("Button: " + str(button_id))
        else:
            # If label doesn't exist (button not previously set), rebuild to show it
            build_config_gump()

        # Update test button label in config if it exists
        if "test_buttons_btn" in config_controls:
            config_controls["test_buttons_btn"].SetBackgroundHue(68)  # Green when button set

        # Close tester
        if tester_gump:
            tester_gump.Dispose()

def on_tester_closed():
    """Tester window closed"""
    global tester_gump, tester_controls

    save_window_position(TESTER_POS_KEY, tester_gump)
    tester_gump = None
    tester_controls = {}

# ============ BUILD GUI - MAIN WINDOW ============
def build_main_gump():
    """Build main window"""
    global main_gump, main_controls

    # Dispose old window
    if main_gump:
        main_gump.Dispose()

    # Clear controls
    main_controls = {}

    # Load position
    x, y = load_window_position(MAIN_POS_KEY, 100, 100)

    # Create gump
    main_gump = API.Gumps.CreateGump()
    main_gump.SetRect(x, y, WINDOW_WIDTH, MAIN_HEIGHT)

    # Background
    background = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
    background.SetRect(0, 0, WINDOW_WIDTH, MAIN_HEIGHT)
    main_gump.Add(background)

    # Title bar
    titleLabel = API.Gumps.CreateGumpTTFLabel("Tome Dumper", 16, "#ffaa00")
    titleLabel.SetPos(10, 2)
    main_gump.Add(titleLabel)

    # Config button
    main_controls["config_btn"] = API.Gumps.CreateSimpleButton("[CONFIG]", 80, 18)
    main_controls["config_btn"].SetPos(185, 2)
    main_controls["config_btn"].SetBackgroundHue(68)
    main_gump.Add(main_controls["config_btn"])
    API.Gumps.AddControlOnClick(main_controls["config_btn"], on_config_clicked)

    # Tome list label
    listLabel = API.Gumps.CreateGumpTTFLabel("Tomes:", 15, "#ffcc00")
    listLabel.SetPos(10, 28)
    main_gump.Add(listLabel)

    # Tome list (uses cached counts to avoid lag)
    y_pos = 50
    for i, tome in enumerate(tomes):
        enabled_text = "> " if tome.get("enabled", True) else "  "
        hue = "#00ff00" if tome.get("enabled", True) else "#888888"

        # Use cached count (updated periodically in main loop)
        item_count = get_cached_item_count(i)

        tomeLabel = API.Gumps.CreateGumpTTFLabel(
            enabled_text + str(tome.get("name", "Unknown")) + " (" + str(item_count) + ")", 15, hue
        )
        tomeLabel.SetPos(15, y_pos)
        main_gump.Add(tomeLabel)

        y_pos += 20

    # Action buttons
    main_controls["dump_enabled_btn"] = API.Gumps.CreateSimpleButton("[DUMP ENABLED]", 130, 22)
    main_controls["dump_enabled_btn"].SetPos(10, 320)
    main_controls["dump_enabled_btn"].SetBackgroundHue(68)
    main_gump.Add(main_controls["dump_enabled_btn"])
    API.Gumps.AddControlOnClick(main_controls["dump_enabled_btn"], on_dump_enabled_clicked)

    main_controls["dump_all_btn"] = API.Gumps.CreateSimpleButton("[DUMP ALL]", 120, 22)
    main_controls["dump_all_btn"].SetPos(150, 320)
    main_controls["dump_all_btn"].SetBackgroundHue(43)
    main_gump.Add(main_controls["dump_all_btn"])
    API.Gumps.AddControlOnClick(main_controls["dump_all_btn"], on_dump_all_clicked)

    # Status display
    statusLabel = API.Gumps.CreateGumpTTFLabel("Ready", 15, "#888888")
    statusLabel.SetPos(10, 350)
    main_gump.Add(statusLabel)
    main_controls["status_label"] = statusLabel

    # Stats
    statsLabel = API.Gumps.CreateGumpTTFLabel(
        "Session: " + str(session_dumps) + " dumps, " + str(session_items) + " items",
        15, "#ffcc00"
    )
    statsLabel.SetPos(10, 370)
    main_gump.Add(statsLabel)
    main_controls["stats_label"] = statsLabel

    # Close callback
    API.Gumps.AddControlOnDisposed(main_gump, on_main_closed)

    # Display
    API.Gumps.AddGump(main_gump)

# ============ BUILD GUI - CONFIG WINDOW ============
def build_config_gump():
    """Build config window"""
    global config_gump, config_controls, editing_tome, config_building, last_config_build_time
    global _config_gump_gen

    # Note: Text box .Text property doesn't update as you type in Legion
    # User must click [SET] button next to name field to save their typed name

    if config_building:
        return
    if time.time() - last_config_build_time < CONFIG_BUILD_COOLDOWN:
        return

    config_building = True
    # Dispose old window before creating new one
    old_gump = config_gump
    config_controls = {}

    if old_gump:
        # Save position before dispose (on_config_closed will be ignored for this programmatic close)
        save_window_position(CONFIG_POS_KEY, old_gump)
        # Increment generation BEFORE dispose so any sync/async on_config_closed callbacks are ignored
        _config_gump_gen += 1
        try:
            old_gump.Dispose()
        except Exception as e:
            API.SysMsg("Config window close failed: " + str(e), 32)
            config_building = False
            return

    config_gump = None

    # Load position
    x, y = load_window_position(CONFIG_POS_KEY, 120, 120)

    # Create gump
    config_gump = API.Gumps.CreateGump()
    config_gump.SetRect(x, y, CONFIG_WIDTH, CONFIG_HEIGHT)

    # Background
    background = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
    background.SetRect(0, 0, CONFIG_WIDTH, CONFIG_HEIGHT)
    config_gump.Add(background)

    # Title
    titleLabel = API.Gumps.CreateGumpTTFLabel("Tome Configuration", 16, "#ffaa00")
    titleLabel.SetPos(10, 2)
    config_gump.Add(titleLabel)

    # Add new tome button
    config_controls["add_tome_btn"] = API.Gumps.CreateSimpleButton("[ADD NEW TOME]", 140, 22)
    config_controls["add_tome_btn"].SetPos(10, 30)
    config_controls["add_tome_btn"].SetBackgroundHue(68)
    config_gump.Add(config_controls["add_tome_btn"])
    API.Gumps.AddControlOnClick(config_controls["add_tome_btn"], on_add_tome_clicked)

    # Edit panel (shown when editing_tome is not None)
    y_pos = 60

    if editing_tome:
        # Edit header with dirty indicator
        edit_header = "Edit Tome"
        if editing_dirty:
            edit_header += " *"
        editLabel = API.Gumps.CreateGumpTTFLabel(edit_header, 15, "#ffcc00")
        editLabel.SetPos(10, y_pos)
        config_gump.Add(editLabel)
        y_pos += 20

        # Instructions
        instructLabel = API.Gumps.CreateGumpTTFLabel("1. Type name, click [SET]  2. Target tome  3. Detect gump  4. Test buttons", 15, "#888888")
        instructLabel.SetPos(10, y_pos)
        config_gump.Add(instructLabel)
        y_pos += 20

        # Name input
        global name_text_box, name_display_label

        nameLabel = API.Gumps.CreateGumpTTFLabel("Name:", 15, "#ffffff")
        nameLabel.SetPos(15, y_pos)
        config_gump.Add(nameLabel)

        current_name = str(editing_tome.get("name", "Weapon Tome"))
        name_text_box = API.Gumps.CreateGumpTextBox(current_name, 150, 22)
        name_text_box.SetPos(70, y_pos)
        config_gump.Add(name_text_box)

        # SET NAME button - reads from text box and saves to tome
        config_controls["set_name_btn"] = API.Gumps.CreateSimpleButton("[SET]", 45, 22)
        config_controls["set_name_btn"].SetPos(230, y_pos)
        config_controls["set_name_btn"].SetBackgroundHue(68)
        config_gump.Add(config_controls["set_name_btn"])
        API.Gumps.AddControlOnClick(config_controls["set_name_btn"], on_set_name_clicked)

        # Display current saved name
        name_display_label = API.Gumps.CreateGumpTTFLabel("Saved: " + current_name, 15, "#00ff88")
        name_display_label.SetPos(285, y_pos + 5)
        config_gump.Add(name_display_label)

        y_pos += 30

        # Target tome button
        tome_serial = editing_tome.get("tome_serial", 0)
        tome_captured = tome_serial > 0

        config_controls["target_tome_btn"] = API.Gumps.CreateSimpleButton("[TARGET TOME]", 120, 22)
        config_controls["target_tome_btn"].SetPos(15, y_pos)
        config_controls["target_tome_btn"].SetBackgroundHue(68 if tome_captured else 43)
        config_gump.Add(config_controls["target_tome_btn"])
        API.Gumps.AddControlOnClick(config_controls["target_tome_btn"], on_target_tome_clicked)

        # Always show status
        if tome_captured:
            serialLabel = API.Gumps.CreateGumpTTFLabel("Tome: 0x{:X}".format(tome_serial), 15, "#00ff00")
            serialLabel.SetPos(145, y_pos + 5)
            config_gump.Add(serialLabel)
            config_controls["tome_serial_label"] = serialLabel  # Store for updates
        else:
            helpLabel = API.Gumps.CreateGumpTTFLabel("Click to target tome", 15, "#888888")
            helpLabel.SetPos(145, y_pos + 5)
            config_gump.Add(helpLabel)
        y_pos += 30

        # Detect gump button
        gump_id = editing_tome.get("gump_id", 0)
        gump_captured = gump_id > 0

        btn_text = "[DETECTING...]" if detecting_gump else "[DETECT GUMP]"
        config_controls["detect_gump_btn"] = API.Gumps.CreateSimpleButton(btn_text, 120, 22)
        config_controls["detect_gump_btn"].SetPos(15, y_pos)
        config_controls["detect_gump_btn"].SetBackgroundHue(68 if gump_captured else 43)
        config_gump.Add(config_controls["detect_gump_btn"])
        API.Gumps.AddControlOnClick(config_controls["detect_gump_btn"], on_detect_gump_clicked)

        # Always show status
        if gump_captured:
            gumpLabel = API.Gumps.CreateGumpTTFLabel("Gump ID: " + str(gump_id), 15, "#00ff00")
            gumpLabel.SetPos(145, y_pos + 5)
            config_gump.Add(gumpLabel)
            config_controls["gump_id_label"] = gumpLabel  # Store for updates
        else:
            helpLabel = API.Gumps.CreateGumpTTFLabel("Open tome, wait for detect", 15, "#888888")
            helpLabel.SetPos(145, y_pos + 5)
            config_gump.Add(helpLabel)
        y_pos += 30

        # Test buttons button
        btn_captured = editing_tome.get("fill_button_id", 0) > 0
        gump_ready = editing_tome.get("gump_id", 0) > 0
        config_controls["test_buttons_btn"] = API.Gumps.CreateSimpleButton("[TEST BUTTONS]", 120, 22)
        config_controls["test_buttons_btn"].SetPos(15, y_pos)
        config_controls["test_buttons_btn"].SetBackgroundHue(68 if btn_captured else (43 if gump_ready else 90))
        config_gump.Add(config_controls["test_buttons_btn"])
        API.Gumps.AddControlOnClick(config_controls["test_buttons_btn"], on_test_buttons_clicked)

        # Always show status
        if btn_captured:
            buttonLabel = API.Gumps.CreateGumpTTFLabel("Button: " + str(editing_tome["fill_button_id"]), 15, "#00ff00")
            buttonLabel.SetPos(145, y_pos + 5)
            config_gump.Add(buttonLabel)
            config_controls["fill_button_label"] = buttonLabel  # Store for updates
        elif gump_ready:
            helpLabel = API.Gumps.CreateGumpTTFLabel("Test to find fill button", 15, "#888888")
            helpLabel.SetPos(145, y_pos + 5)
            config_gump.Add(helpLabel)
        else:
            helpLabel = API.Gumps.CreateGumpTTFLabel("Need gump ID first", 15, "#ff8800")
            helpLabel.SetPos(145, y_pos + 5)
            config_gump.Add(helpLabel)
        y_pos += 30

        # Targeting Mode Selection
        targetingLabel = API.Gumps.CreateGumpTTFLabel("Targeting mode:", 15, "#ffffff")
        targetingLabel.SetPos(15, y_pos + 2)
        config_gump.Add(targetingLabel)

        targeting_mode = editing_tome.get("targeting_mode", "container")

        # None button
        config_controls["mode_none"] = API.Gumps.CreateSimpleButton("[NONE]", 55, 18)
        config_controls["mode_none"].SetPos(125, y_pos)
        config_controls["mode_none"].SetBackgroundHue(32 if targeting_mode == "none" else 90)
        config_gump.Add(config_controls["mode_none"])
        API.Gumps.AddControlOnClick(config_controls["mode_none"], lambda: on_targeting_mode_set("none"))

        # Container button
        config_controls["mode_container"] = API.Gumps.CreateSimpleButton("[CNTR]", 55, 18)
        config_controls["mode_container"].SetPos(185, y_pos)
        config_controls["mode_container"].SetBackgroundHue(68 if targeting_mode == "container" else 90)
        config_gump.Add(config_controls["mode_container"])
        API.Gumps.AddControlOnClick(config_controls["mode_container"], lambda: on_targeting_mode_set("container"))

        # Single item button
        config_controls["mode_single"] = API.Gumps.CreateSimpleButton("[1 ITEM]", 60, 18)
        config_controls["mode_single"].SetPos(245, y_pos)
        config_controls["mode_single"].SetBackgroundHue(68 if targeting_mode == "single_item" else 90)
        config_gump.Add(config_controls["mode_single"])
        API.Gumps.AddControlOnClick(config_controls["mode_single"], lambda: on_targeting_mode_set("single_item"))

        # Multi item button
        config_controls["mode_multi"] = API.Gumps.CreateSimpleButton("[MULTI]", 60, 18)
        config_controls["mode_multi"].SetPos(310, y_pos)
        config_controls["mode_multi"].SetBackgroundHue(68 if targeting_mode == "multi_item" else 90)
        config_gump.Add(config_controls["mode_multi"])
        API.Gumps.AddControlOnClick(config_controls["mode_multi"], lambda: on_targeting_mode_set("multi_item"))

        y_pos += 22

        # Help text for targeting modes
        mode_help = {
            "none": "Button doesn't need target",
            "container": "Target containers to dump from",
            "single_item": "Target 1 item per button click",
            "multi_item": "Target items repeatedly"
        }
        helpLabel = API.Gumps.CreateGumpTTFLabel(mode_help.get(targeting_mode, ""), 15, "#888888")
        helpLabel.SetPos(15, y_pos)
        config_gump.Add(helpLabel)

        y_pos += 18

        # Auto-retarget option (only for multi_item mode)
        if targeting_mode == "multi_item":
            autoRetargetLabel = API.Gumps.CreateGumpTTFLabel("Auto-retarget:", 15, "#ffffff")
            autoRetargetLabel.SetPos(30, y_pos + 2)
            config_gump.Add(autoRetargetLabel)

            auto_retarget = editing_tome.get("auto_retarget", True)

            config_controls["retarget_off"] = API.Gumps.CreateSimpleButton("[NO]", 45, 18)
            config_controls["retarget_off"].SetPos(145, y_pos)
            config_controls["retarget_off"].SetBackgroundHue(32 if not auto_retarget else 90)
            config_gump.Add(config_controls["retarget_off"])
            API.Gumps.AddControlOnClick(config_controls["retarget_off"], lambda: on_auto_retarget_set(False))

            config_controls["retarget_on"] = API.Gumps.CreateSimpleButton("[YES]", 45, 18)
            config_controls["retarget_on"].SetPos(195, y_pos)
            config_controls["retarget_on"].SetBackgroundHue(68 if auto_retarget else 90)
            config_gump.Add(config_controls["retarget_on"])
            API.Gumps.AddControlOnClick(config_controls["retarget_on"], lambda: on_auto_retarget_set(True))

            helpLabel2 = API.Gumps.CreateGumpTTFLabel("(cursor reappears after each item)", 15, "#888888")
            helpLabel2.SetPos(30, y_pos + 22)
            config_gump.Add(helpLabel2)

            y_pos += 40

        # Target containers (for container and multi_item modes)
        if targeting_mode in ["container", "multi_item"]:
            # Get current containers (support both old and new format)
            target_containers = editing_tome.get("target_containers", [])
            if not target_containers:
                # Legacy support - convert old single container
                old_container = editing_tome.get("target_container", 0)
                if old_container > 0:
                    target_containers = [old_container]
                    editing_tome["target_containers"] = target_containers

            # Add target button
            config_controls["add_target_btn"] = API.Gumps.CreateSimpleButton("[ADD TARGET]", 120, 22)
            config_controls["add_target_btn"].SetPos(15, y_pos)
            config_controls["add_target_btn"].SetBackgroundHue(68)
            config_gump.Add(config_controls["add_target_btn"])
            API.Gumps.AddControlOnClick(config_controls["add_target_btn"], on_add_target_clicked)

            # Help text
            helpLabel = API.Gumps.CreateGumpTTFLabel("Target backpack, lootpack, etc.", 15, "#888888")
            helpLabel.SetPos(145, y_pos + 5)
            config_gump.Add(helpLabel)
            y_pos += 30

            # List of containers
            if target_containers:
                containerListLabel = API.Gumps.CreateGumpTTFLabel("Targets (" + str(len(target_containers)) + "):", 15, "#ffcc00")
                containerListLabel.SetPos(15, y_pos)
                config_gump.Add(containerListLabel)
                y_pos += 18

                for i, container_serial in enumerate(target_containers):
                    # Try to get container name
                    container_item = API.FindItem(container_serial)
                    if container_item:
                        container_name = getattr(container_item, 'Name', 'Unknown')
                        container_text = "  " + container_name + " (0x{:X})".format(container_serial)
                    else:
                        container_text = "  0x{:X} (not found)".format(container_serial)

                    serialLabel = API.Gumps.CreateGumpTTFLabel(container_text, 15, "#00ff88")
                    serialLabel.SetPos(15, y_pos)
                    config_gump.Add(serialLabel)

                    # Delete button
                    delete_key = "del_target_" + str(i)
                    config_controls[delete_key] = API.Gumps.CreateSimpleButton("[X]", 30, 18)
                    config_controls[delete_key].SetPos(320, y_pos - 2)
                    config_controls[delete_key].SetBackgroundHue(32)
                    config_gump.Add(config_controls[delete_key])
                    API.Gumps.AddControlOnClick(config_controls[delete_key], lambda idx=i: on_delete_target_clicked(idx))

                    y_pos += 18
            else:
                noTargetsLabel = API.Gumps.CreateGumpTTFLabel("  No targets - click [ADD TARGET]", 15, "#888888")
                noTargetsLabel.SetPos(15, y_pos)
                config_gump.Add(noTargetsLabel)
                y_pos += 18

            y_pos += 10

            # Graphic targeting option
            graphicTargetLabel = API.Gumps.CreateGumpTTFLabel("Or use Graphic ID:", 15, "#ffffff")
            graphicTargetLabel.SetPos(15, y_pos + 2)
            config_gump.Add(graphicTargetLabel)

            use_graphic = editing_tome.get("use_graphic_targeting", False)

            config_controls["graphic_off"] = API.Gumps.CreateSimpleButton("[NO]", 45, 18)
            config_controls["graphic_off"].SetPos(145, y_pos)
            config_controls["graphic_off"].SetBackgroundHue(32 if not use_graphic else 90)
            config_gump.Add(config_controls["graphic_off"])
            API.Gumps.AddControlOnClick(config_controls["graphic_off"], lambda: on_graphic_targeting_set(False))

            config_controls["graphic_on"] = API.Gumps.CreateSimpleButton("[YES]", 45, 18)
            config_controls["graphic_on"].SetPos(195, y_pos)
            config_controls["graphic_on"].SetBackgroundHue(68 if use_graphic else 90)
            config_gump.Add(config_controls["graphic_on"])
            API.Gumps.AddControlOnClick(config_controls["graphic_on"], lambda: on_graphic_targeting_set(True))

            # Help text
            helpLabel = API.Gumps.CreateGumpTTFLabel("(target any bag type instead of specific)", 15, "#888888")
            helpLabel.SetPos(15, y_pos + 22)
            config_gump.Add(helpLabel)
            y_pos += 40

            # If graphic targeting enabled, show capture buttons
            if use_graphic:
                # Capture graphic button
                has_graphic = editing_tome.get("target_graphic", 0) > 0
                config_controls["capture_graphic_btn"] = API.Gumps.CreateSimpleButton("[CAPTURE GRAPHIC]", 140, 22)
                config_controls["capture_graphic_btn"].SetPos(15, y_pos)
                config_controls["capture_graphic_btn"].SetBackgroundHue(68 if has_graphic else 43)
                config_gump.Add(config_controls["capture_graphic_btn"])
                API.Gumps.AddControlOnClick(config_controls["capture_graphic_btn"], on_capture_graphic_clicked)

                if has_graphic:
                    graphicLabel = API.Gumps.CreateGumpTTFLabel("Graphic: 0x{:X}".format(editing_tome["target_graphic"]), 15, "#00ff00")
                    graphicLabel.SetPos(165, y_pos + 5)
                    config_gump.Add(graphicLabel)
                    config_controls["graphic_label"] = graphicLabel  # Store for updates
                else:
                    helpLabel = API.Gumps.CreateGumpTTFLabel("Target a container type", 15, "#888888")
                    helpLabel.SetPos(165, y_pos + 5)
                    config_gump.Add(helpLabel)
                y_pos += 30

                # Hue specific toggle
                hueSpecificLabel = API.Gumps.CreateGumpTTFLabel("Hue specific:", 15, "#ffffff")
                hueSpecificLabel.SetPos(15, y_pos + 2)
                config_gump.Add(hueSpecificLabel)

                hue_specific = editing_tome.get("target_hue_specific", False)

                config_controls["hue_off"] = API.Gumps.CreateSimpleButton("[NO]", 45, 18)
                config_controls["hue_off"].SetPos(145, y_pos)
                config_controls["hue_off"].SetBackgroundHue(32 if not hue_specific else 90)
                config_gump.Add(config_controls["hue_off"])
                API.Gumps.AddControlOnClick(config_controls["hue_off"], lambda: on_hue_specific_set(False))

                config_controls["hue_on"] = API.Gumps.CreateSimpleButton("[YES]", 45, 18)
                config_controls["hue_on"].SetPos(195, y_pos)
                config_controls["hue_on"].SetBackgroundHue(68 if hue_specific else 90)
                config_gump.Add(config_controls["hue_on"])
                API.Gumps.AddControlOnClick(config_controls["hue_on"], lambda: on_hue_specific_set(True))
                y_pos += 30

                # If hue specific, show hue value
                if hue_specific:
                    has_hue = editing_tome.get("target_hue", 0) > 0
                    hue_text = "Hue: 0x{:X}".format(editing_tome.get("target_hue", 0)) if has_hue else "Hue: (any color captured)"
                    hueLabel = API.Gumps.CreateGumpTTFLabel(hue_text, 15, "#00ff88")
                    hueLabel.SetPos(15, y_pos)
                    config_gump.Add(hueLabel)
                    y_pos += 18

        # Capture items button
        items_captured = len(editing_tome.get("item_graphics", [])) > 0
        btn_text = "[CAPTURING...]" if capturing_items else "[CAPTURE ITEMS]"
        config_controls["capture_items_btn"] = API.Gumps.CreateSimpleButton(btn_text, 130, 22)
        config_controls["capture_items_btn"].SetPos(15, y_pos)
        config_controls["capture_items_btn"].SetBackgroundHue(68 if items_captured else 43)
        config_gump.Add(config_controls["capture_items_btn"])
        API.Gumps.AddControlOnClick(config_controls["capture_items_btn"], on_capture_items_clicked)

        # Show captured graphics
        if items_captured:
            graphics_str = ", ".join("0x{:X}".format(g) for g in editing_tome["item_graphics"][:3])
            if len(editing_tome["item_graphics"]) > 3:
                graphics_str += "..."
            graphicsLabel = API.Gumps.CreateGumpTTFLabel(graphics_str + " (" + str(len(editing_tome["item_graphics"])) + " types)", 15, "#00ff00")
            graphicsLabel.SetPos(155, y_pos + 5)
            config_gump.Add(graphicsLabel)
        else:
            noFilterLabel = API.Gumps.CreateGumpTTFLabel("No filter = ALL items!", 15, "#ff8800")
            noFilterLabel.SetPos(155, y_pos + 5)
            config_gump.Add(noFilterLabel)
        y_pos += 30

        # Summary
        summaryLabel = API.Gumps.CreateGumpTTFLabel("Ready to save:", 15, "#ffcc00")
        summaryLabel.SetPos(15, y_pos)
        config_gump.Add(summaryLabel)
        y_pos += 18

        # Check readiness
        has_tome = editing_tome.get("tome_serial", 0) > 0
        has_gump = editing_tome.get("gump_id", 0) > 0
        has_button = editing_tome.get("fill_button_id", 0) > 0
        needs_tgt = editing_tome.get("needs_targeting", False)
        has_containers = len(editing_tome.get("target_containers", [])) > 0

        check_tome = "[x]" if has_tome else "[ ]"
        check_gump = "[x]" if has_gump else "[ ]"
        check_button = "[x]" if has_button else "[ ]"
        check_container = "[x]" if (not needs_tgt or has_containers) else "[ ]"

        checkLabel1 = API.Gumps.CreateGumpTTFLabel(check_tome + " Tome  " + check_gump + " Gump  " + check_button + " Button  " + check_container + " Target", 15, "#aaaaaa")
        checkLabel1.SetPos(20, y_pos)
        config_gump.Add(checkLabel1)
        y_pos += 18

        # Can save?
        ready_to_save = has_tome and (not needs_tgt or has_containers)

        # Save/Cancel buttons
        config_controls["save_btn"] = API.Gumps.CreateSimpleButton("[SAVE]", 80, 22)
        config_controls["save_btn"].SetPos(15, y_pos)
        config_controls["save_btn"].SetBackgroundHue(68 if ready_to_save else 90)
        config_gump.Add(config_controls["save_btn"])
        API.Gumps.AddControlOnClick(config_controls["save_btn"], on_save_tome_clicked)

        config_controls["cancel_btn"] = API.Gumps.CreateSimpleButton("[CANCEL]", 80, 22)
        config_controls["cancel_btn"].SetPos(105, y_pos)
        config_controls["cancel_btn"].SetBackgroundHue(32)
        config_gump.Add(config_controls["cancel_btn"])
        API.Gumps.AddControlOnClick(config_controls["cancel_btn"], on_cancel_edit_clicked)

        if not ready_to_save:
            warnLabel = API.Gumps.CreateGumpTTFLabel("Missing required fields", 15, "#ff8800")
            warnLabel.SetPos(200, y_pos + 5)
            config_gump.Add(warnLabel)

        y_pos += 35

    # Existing tomes list
    list_y_pos = y_pos if editing_tome else 60
    listLabel = API.Gumps.CreateGumpTTFLabel("Existing Tomes:", 15, "#ffcc00")
    listLabel.SetPos(10, list_y_pos)
    config_gump.Add(listLabel)
    list_y_pos += 25

    for i, tome in enumerate(tomes):
        # Skip if we're past window bounds
        if list_y_pos > CONFIG_HEIGHT - 30:
            moreLabel = API.Gumps.CreateGumpTTFLabel("... (scroll down for more)", 15, "#888888")
            moreLabel.SetPos(15, list_y_pos)
            config_gump.Add(moreLabel)
            break

        enabled_text = "[ON] " if tome.get("enabled", True) else "[OFF]"
        hue = "#00ff00" if tome.get("enabled", True) else "#888888"

        tomeLabel = API.Gumps.CreateGumpTTFLabel(enabled_text + str(tome.get("name", "Unknown")), 15, hue)
        tomeLabel.SetPos(15, list_y_pos)
        config_gump.Add(tomeLabel)

        # Edit button
        editBtn = API.Gumps.CreateSimpleButton("[EDIT]", 60, 18)
        editBtn.SetPos(250, list_y_pos - 2)
        editBtn.SetBackgroundHue(68)
        config_gump.Add(editBtn)
        API.Gumps.AddControlOnClick(editBtn, lambda idx=i: on_edit_tome_clicked(idx))

        # Delete button
        delBtn = API.Gumps.CreateSimpleButton("[DEL]", 50, 18)
        delBtn.SetPos(320, list_y_pos - 2)
        delBtn.SetBackgroundHue(32)
        config_gump.Add(delBtn)
        API.Gumps.AddControlOnClick(delBtn, lambda idx=i: on_delete_tome_clicked(idx))

        list_y_pos += 22

    # Close callback - bind current generation so stale async callbacks are ignored
    this_gen = _config_gump_gen
    API.Gumps.AddControlOnDisposed(config_gump, lambda gen=this_gen: on_config_closed(gen))

    # Display
    API.Gumps.AddGump(config_gump)
    last_config_build_time = time.time()
    config_building = False

# ============ BUILD GUI - TESTER WINDOW ============
def build_tester_gump():
    """Build button tester window"""
    global tester_gump, tester_controls

    # Dispose old window
    if tester_gump:
        tester_gump.Dispose()

    # Clear controls
    tester_controls = {}

    # Load position
    x, y = load_window_position(TESTER_POS_KEY, 140, 140)

    # Create gump
    tester_gump = API.Gumps.CreateGump()
    tester_gump.SetRect(x, y, TESTER_WIDTH, TESTER_HEIGHT + 80)

    # Background
    background = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
    background.SetRect(0, 0, TESTER_WIDTH, TESTER_HEIGHT + 50)
    tester_gump.Add(background)

    # Title
    titleLabel = API.Gumps.CreateGumpTTFLabel("Button Tester", 16, "#ffaa00")
    titleLabel.SetPos(10, 2)
    tester_gump.Add(titleLabel)

    # Instructions
    instrLabel = API.Gumps.CreateGumpTTFLabel("Open tome, then test buttons:", 15, "#888888")
    instrLabel.SetPos(10, 25)
    tester_gump.Add(instrLabel)

    # Quick test grid (buttons 0-11)
    gridLabel = API.Gumps.CreateGumpTTFLabel("Quick Test (0-11):", 15, "#ffcc00")
    gridLabel.SetPos(10, 40)
    tester_gump.Add(gridLabel)

    # Button grid
    y_pos = 60
    for row in range(3):
        x_pos = 10
        for col in range(4):
            button_id = row * 4 + col

            testBtn = API.Gumps.CreateSimpleButton("[" + str(button_id) + "]", 40, 22)
            testBtn.SetPos(x_pos, y_pos)
            testBtn.SetBackgroundHue(68)
            tester_gump.Add(testBtn)
            API.Gumps.AddControlOnClick(testBtn, lambda bid=button_id: on_test_button_number(bid))

            x_pos += 50

        y_pos += 30

    # Custom button input
    customLabel = API.Gumps.CreateGumpTTFLabel("Custom ID:", 15, "#ffcc00")
    customLabel.SetPos(10, 155)
    tester_gump.Add(customLabel)

    tester_controls["custom_input"] = API.Gumps.CreateGumpTextBox("", 60, 22)
    tester_controls["custom_input"].SetPos(90, 155)
    tester_gump.Add(tester_controls["custom_input"])

    testCustomBtn = API.Gumps.CreateSimpleButton("[TEST]", 60, 22)
    testCustomBtn.SetPos(160, 155)
    testCustomBtn.SetBackgroundHue(68)
    tester_gump.Add(testCustomBtn)
    API.Gumps.AddControlOnClick(testCustomBtn, on_test_custom_button)

    # Set button - takes value from custom input
    setBtn = API.Gumps.CreateSimpleButton("[SET AS FILL]", 90, 22)
    setBtn.SetPos(230, 155)
    setBtn.SetBackgroundHue(66)
    tester_gump.Add(setBtn)
    API.Gumps.AddControlOnClick(setBtn, on_set_custom_button)

    # Show current button if already set
    y_pos = 185
    if editing_tome and editing_tome.get("fill_button_id", 0) > 0:
        currentLabel = API.Gumps.CreateGumpTTFLabel("Current fill button: " + str(editing_tome["fill_button_id"]), 15, "#00ff00")
        currentLabel.SetPos(10, y_pos)
        tester_gump.Add(currentLabel)
        y_pos += 18

    # Instructions
    instrLabel = API.Gumps.CreateGumpTTFLabel("Type button # above, click [TEST], then [SET AS FILL]", 15, "#888888")
    instrLabel.SetPos(10, y_pos)
    tester_gump.Add(instrLabel)
    y_pos += 18

    # Last result display
    resultLabel = API.Gumps.CreateGumpTTFLabel("Click button to test", 15, "#888888")
    resultLabel.SetPos(10, y_pos)
    tester_gump.Add(resultLabel)
    tester_controls["result_label"] = resultLabel

    # Close callback
    API.Gumps.AddControlOnDisposed(tester_gump, on_tester_closed)

    # Display
    API.Gumps.AddGump(tester_gump)

# ============ CLEANUP ============
def cleanup():
    """Cleanup on script stop"""
    global main_gump, config_gump, tester_gump

    cancel_all_targets()

    if main_gump:
        save_window_position(MAIN_POS_KEY, main_gump)
        main_gump.Dispose()

    if config_gump:
        save_window_position(CONFIG_POS_KEY, config_gump)
        config_gump.Dispose()

    if tester_gump:
        save_window_position(TESTER_POS_KEY, tester_gump)
        tester_gump.Dispose()

# ============ INITIALIZATION ============
load_tomes()
update_item_count_cache()  # Prime cache before first display

# ============ BUILD MAIN GUI ============
build_main_gump()

# ============ REGISTER HOTKEYS ============
hotkeys = HotkeyManager()
hotkeys.add("dump", KEY_PREFIX + "DumpHK", "Dump Enabled",
            dump_enabled_tomes, None, "D")
hotkeys.add("dump_all", KEY_PREFIX + "DumpAllHK", "Dump All",
            dump_all_tomes, None, "CTRL+D")
hotkeys.register_all()

# ============ MAIN LOOP ============
while not API.StopRequested:
    try:
        API.ProcessCallbacks()

        # Update item count cache (rate-limited to every 2s)
        update_item_count_cache()

        # Update displays (rate-limited to every 1s)
        update_main_display()

        API.Pause(0.1)

    except Exception as e:
        API.SysMsg("ERROR: " + str(e), 32)
        API.Pause(1)

cleanup()
