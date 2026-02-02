# Example_MiningBot.py
# Example mining bot using GatherFramework
# Version 1.0
#
# This demonstrates how to create a simple resource gathering bot
# using the framework. This bot:
# - Mines ore using AOE self-targeting
# - Auto-recalls home when weight threshold reached
# - Dumps ore to storage container
# - Rotates through multiple mining spots
# - Flees from hostiles

import API
import time
import sys

# Add parent directory to path to import framework
parent_path = "G:\\Ultima Online\\TazUO-Launcher.win-x64\\TazUO\\LegionScripts\\CoryCustom"
if parent_path not in sys.path:
    sys.path.insert(0, parent_path)

from GatherFramework import (
    TravelSystem,
    StorageSystem,
    WeightManager,
    StateMachine,
    CombatSystem,
    ResourceFinder,
    Harvester,
    SessionStats,
    HUE_GREEN,
    HUE_RED,
    HUE_YELLOW
)

# ============ CONFIGURATION ============

# Graphics
ORE_GRAPHIC = 0x19B9
PICKAXE_GRAPHIC = 0x0E86
SHOVEL_GRAPHIC = 0x0F39

# Timings
MINE_DELAY = 2.5

# Journal messages
SUCCESS_MESSAGES = [
    "You dig some",
    "You loosen some",
    "and put it in your backpack"
]

DEPLETION_MESSAGES = [
    "There is no ore here to mine",
    "You can't mine there",
    "Try mining elsewhere",
    "not enough ore"
]

# ============ STATE ============

# Pause control
PAUSED = False

# Configuration (would normally be loaded from persistence)
pickaxe_serial = 0
runebook_serial = 0
storage_container_serial = 0
num_mining_spots = 3
weight_threshold = 80

# ============ FRAMEWORK INSTANCES ============

travel_system = None
storage_system = None
weight_manager = None
state_machine = None
combat_system = None
harvester = None
stats = None

# ============ STATE HANDLERS ============

def handle_idle(sm):
    """Idle state - check if should dump or mine."""
    global PAUSED

    # Check if should dump
    if weight_manager.should_dump():
        API.SysMsg("Weight threshold reached - recalling home", HUE_YELLOW)
        if travel_system.recall_home():
            sm.set_state("pathfinding_to_storage")
        else:
            API.SysMsg("Recall failed - pausing", HUE_RED)
            PAUSED = True
        return

    # Mine at current location (AOE mode)
    if harvester.harvest():
        sm.set_state("mining", start_time=time.time())
    else:
        API.SysMsg("No pickaxe found!", HUE_RED)
        PAUSED = True

def handle_mining(sm):
    """Mining state - wait for mining to complete."""
    if time.time() > sm.state_data.get('start_time', 0) + MINE_DELAY:
        result = harvester.check_journal(SUCCESS_MESSAGES, DEPLETION_MESSAGES)

        if result == "success":
            stats.increment("ore_mined")
            sm.set_state("idle")
        elif result == "depleted":
            # Resource depleted - rotate to next spot
            API.SysMsg("Resources depleted - rotating to next spot", HUE_YELLOW)
            sm.set_state("rotating_spot")
        else:
            # Unknown result - try again
            sm.set_state("idle")

def handle_rotating_spot(sm):
    """Rotate to next mining spot."""
    global PAUSED

    if travel_system.rotate_to_next_spot():
        API.SysMsg("At next mining spot", HUE_GREEN)
        sm.set_state("idle")
    else:
        API.SysMsg("Failed to rotate to next spot - pausing", HUE_RED)
        PAUSED = True

def handle_pathfinding_to_storage(sm):
    """Pathfind to storage container."""
    global PAUSED

    if storage_system.pathfind_to_container():
        sm.set_state("dumping")
    else:
        API.SysMsg("Failed to pathfind to storage - pausing", HUE_RED)
        PAUSED = True

def handle_dumping(sm):
    """Dump ore to storage."""
    global PAUSED

    if storage_system.dump_resources():
        stats.increment("dumps_completed")
        API.SysMsg("Resources dumped successfully!", HUE_GREEN)

        # Return to mining spot
        if travel_system.recall_to_current_spot():
            sm.set_state("idle")
        else:
            API.SysMsg("Failed to return to mining spot - pausing", HUE_RED)
            PAUSED = True
    else:
        API.SysMsg("Failed to dump resources - pausing", HUE_RED)
        PAUSED = True

def handle_combat(sm):
    """Combat state - flee from enemy."""
    enemy = combat_system.find_closest_hostile()

    if not enemy:
        # No enemy found - return to idle
        sm.set_state("idle")
        return

    # Check if should flee
    if combat_system.should_flee():
        API.SysMsg("HP low - fleeing to safety", HUE_RED)

        if combat_system.flee_from_enemy(enemy):
            # Successfully fled - recall home
            if travel_system.recall_home():
                API.SysMsg("Recalled home safely", HUE_GREEN)
                sm.set_state("idle")
            else:
                API.SysMsg("Failed to recall - continuing to flee", HUE_RED)
        else:
            API.SysMsg("Flee failed - recalling anyway", HUE_RED)
            travel_system.recall_home()

        sm.set_state("idle")

# ============ HOTKEY HANDLERS ============

def toggle_pause():
    """Toggle pause state."""
    global PAUSED
    PAUSED = not PAUSED

    if PAUSED:
        API.SysMsg("Mining Bot PAUSED", HUE_YELLOW)
    else:
        API.SysMsg("Mining Bot RESUMED", HUE_GREEN)

def emergency_recall():
    """Emergency recall home."""
    if travel_system.recall_home():
        API.SysMsg("EMERGENCY RECALL - AT HOME", HUE_RED)
    else:
        API.SysMsg("EMERGENCY RECALL FAILED!", HUE_RED)

# ============ INITIALIZATION ============

def initialize():
    """Initialize framework components."""
    global travel_system, storage_system, weight_manager, state_machine
    global combat_system, harvester, stats

    # Initialize systems
    travel_system = TravelSystem(runebook_serial, num_mining_spots)
    storage_system = StorageSystem(storage_container_serial)
    weight_manager = WeightManager(weight_threshold)
    state_machine = StateMachine()
    combat_system = CombatSystem(mode="flee", flee_hp_threshold=50)
    harvester = Harvester(pickaxe_serial, MINE_DELAY)
    harvester.use_aoe = True  # AOE mining
    stats = SessionStats()

    # Register state handlers
    state_machine.register_handler("idle", handle_idle)
    state_machine.register_handler("mining", handle_mining)
    state_machine.register_handler("rotating_spot", handle_rotating_spot)
    state_machine.register_handler("pathfinding_to_storage", handle_pathfinding_to_storage)
    state_machine.register_handler("dumping", handle_dumping)
    state_machine.register_handler("combat", handle_combat)

    # Register hotkeys
    API.OnHotKey("F1", toggle_pause)
    API.OnHotKey("F2", emergency_recall)

# ============ MAIN LOOP ============

# Configuration would normally be loaded here from persistence
# For this example, you'd set:
# pickaxe_serial = 0x12345678
# runebook_serial = 0x23456789
# storage_container_serial = 0x34567890

API.SysMsg("Example Mining Bot - Configure serials before running!", HUE_YELLOW)
API.SysMsg("Uncomment main loop code after configuration", HUE_RED)

# Uncomment below after configuring serials
"""
# Initialize
initialize()

API.SysMsg("Mining Bot started!", HUE_GREEN)
API.SysMsg("F1 = Pause, F2 = Emergency Recall", HUE_YELLOW)

# Main loop
try:
    while not API.StopRequested:
        try:
            API.ProcessCallbacks()

            if PAUSED:
                API.Pause(0.1)
                continue

            # Combat check (highest priority)
            enemy = combat_system.find_closest_hostile()
            if enemy and not travel_system.at_home:
                state_machine.set_state("combat")

            # Execute state machine
            state_machine.tick()

            API.Pause(0.1)

        except Exception as e:
            API.SysMsg(f"Error: {e}", HUE_RED)
            API.Pause(1.0)

except Exception as e:
    API.SysMsg(f"CRITICAL ERROR: {e}", HUE_RED)

API.SysMsg("Mining Bot stopped", HUE_RED)
"""
