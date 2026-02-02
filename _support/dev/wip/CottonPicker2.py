# CottonPicker2.py
# Full automation cotton picker using GatherFramework
# Version 1.0
#
# Features:
# - Picks cotton from farms
# - Processes: cotton → spools → cloth → bandages
# - Auto-storage in resource bin
# - Combat with pets
# - Farm rotation with 15-min respawn wait

import API
import time

# Import framework (in same directory)
from GatherFramework import (
    TravelSystem,
    StorageSystem,
    WeightManager,
    StateMachine,
    CombatSystem,
    PetSystem,
    ResourceFinder,
    SessionStats,
    DamageTracker,
    HUE_GREEN,
    HUE_RED,
    HUE_YELLOW,
    HUE_PURPLE
)

# ============ CONFIGURATION ============

# Graphics
COTTON_PLANT_GRAPHICS = [0x0C51, 0x0C52, 0x0C53, 0x0C54]  # All growth stages
COTTON_GRAPHIC = 0x0DF9
SPOOL_GRAPHIC = 0x0FA0
CLOTH_BOLT_GRAPHIC = 0x0F95
CLOTH_PIECE_GRAPHIC = 0x1766
SCISSORS_GRAPHIC = 0x0F9F
BANDAGE_GRAPHIC = 0x0E21

# Timings
PICK_DELAY = 2.5
SPIN_DELAY = 2.0
WEAVE_DELAY = 2.0
CUT_DELAY = 2.0
MAKE_BANDAGE_DELAY = 2.0
LOOT_DELAY = 1.0
NO_PLANTS_TIMEOUT = 5  # Match original - rotate farms after 5s with no plants
PICK_REACH = 1  # Must be 1 tile away to pick
PLANT_COOLDOWN = 10.0  # Per-plant cooldown after picking
RESPAWN_WAIT = 900  # 15 minutes

# Ranges
SCAN_RANGE = 24
LOOT_RANGE = 2

# Persistence keys
KEY_PREFIX = "CottonPicker2_"

# ============ RUNTIME STATE ============

paused = True  # Start paused - user must click Start button
ui_closed = False

# Configuration
runebook_serial = 0
wheel_serial = 0
loom_serial = 0
storage_serial = 0
num_farm_spots = 3
weight_threshold = 80
home_slot = 1
first_farm_slot = 2

# Positions
wheel_x = 0
wheel_y = 0
loom_x = 0
loom_y = 0
storage_x = 0
storage_y = 0

# Full automation state
fullauto_state = "checking_inventory"
fullauto_start_time = 0
fullauto_timeout = 60.0

# Picking state
no_plants_start_time = 0
fullauto_empty_farms_count = 0
current_farm = 0

# Respawn wait
respawn_wait_start = 0

# Combat state
in_combat = False
combat_start_time = 0
current_enemy_serial = 0
last_kill_command_time = 0
last_bandage_time = 0

# Plant cooldown tracking
last_clicked = {}  # {plant_serial: timestamp}

# Pet damage tracking
pet_last_hp = {}  # {pet_serial: last_hp}

# ============ FRAMEWORK INSTANCES ============

travel_system = None
storage_system = None
weight_manager = None
state_machine = None
combat_system = None
pet_system = None
resource_finder = None
stats = None
damage_tracker = None

# ============ GUI REFERENCES ============

gump = None
labels = {}

# ============ UTILITY FUNCTIONS ============

def find_backpack_item(graphic):
    """Find item in backpack by graphic."""
    backpack = API.Player.Backpack
    if not backpack:
        return None

    # Search ONLY in backpack (not entire world)
    API.FindType(graphic, backpack.Serial)
    if API.Found:
        return API.FindItem(API.Found)
    return None

def count_backpack_item(graphic):
    """Count items in backpack by graphic."""
    item = find_backpack_item(graphic)
    return item.Amount if item else 0

def count_cotton():
    return count_backpack_item(COTTON_GRAPHIC)

def count_spools():
    return count_backpack_item(SPOOL_GRAPHIC)

def count_cloth_bolts():
    return count_backpack_item(CLOTH_BOLT_GRAPHIC)

def count_cloth_pieces():
    return count_backpack_item(CLOTH_PIECE_GRAPHIC)

def count_bandages():
    return count_backpack_item(BANDAGE_GRAPHIC)

def have_scissors():
    """Check if player has scissors."""
    return find_backpack_item(SCISSORS_GRAPHIC) is not None

def is_plant_on_cooldown(plant_serial):
    """Check if plant is on cooldown (10s after last click)."""
    if plant_serial in last_clicked:
        if time.time() < last_clicked[plant_serial] + PLANT_COOLDOWN:
            return True
    return False

def check_pets_taking_damage():
    """Check if any pet is taking damage (HP dropping)."""
    if not pet_system:
        return False

    pets = pet_system.get_pets()
    if not pets:
        return False

    for pet in pets:
        if not pet or pet.IsDead:
            continue

        pet_serial = getattr(pet, 'Serial', 0)
        if pet_serial == 0:
            continue

        current_hp = getattr(pet, 'Hits', 0)

        # Initialize if first check
        if pet_serial not in pet_last_hp:
            pet_last_hp[pet_serial] = current_hp
            continue

        # Check for HP drop
        if current_hp < pet_last_hp[pet_serial]:
            pet_last_hp[pet_serial] = current_hp
            return True

        # Update HP
        pet_last_hp[pet_serial] = current_hp

    return False

def use_bandage_on_self():
    """Use bandage on self."""
    global last_bandage_time

    # Check cooldown (10s between bandages)
    if time.time() < last_bandage_time + 10.0:
        return False

    bandage = find_backpack_item(BANDAGE_GRAPHIC)
    if not bandage:
        return False

    try:
        # Use bandage on self
        API.UseObject(bandage.Serial, False)
        API.Pause(0.3)

        # Wait for target cursor
        if API.WaitForTarget(timeout=2.0):
            API.Target(API.Player.Serial)
            last_bandage_time = time.time()
            return True

        return False
    except:
        return False

def heal_pets():
    """Heal injured pets with bandages."""
    global last_bandage_time

    # Check cooldown
    if time.time() < last_bandage_time + 10.0:
        return False

    if not pet_system:
        return False

    pets = pet_system.get_pets()
    if not pets:
        return False

    # Find most injured pet
    most_injured = None
    lowest_hp_pct = 100.0

    for pet in pets:
        hits = getattr(pet, 'Hits', 0)
        hits_max = getattr(pet, 'HitsMax', 1)
        if hits_max > 0:
            hp_pct = (hits / hits_max) * 100.0
            if hp_pct < 100.0 and hp_pct < lowest_hp_pct:
                lowest_hp_pct = hp_pct
                most_injured = pet

    if not most_injured:
        return False

    # Use bandage on pet
    bandage = find_backpack_item(BANDAGE_GRAPHIC)
    if not bandage:
        return False

    try:
        pet_serial = getattr(most_injured, 'Serial', None)
        if not pet_serial:
            return False

        # Use bandage
        API.UseObject(bandage.Serial, False)
        API.Pause(0.3)

        # Wait for target cursor
        if API.WaitForTarget(timeout=2.0):
            API.Target(pet_serial)
            last_bandage_time = time.time()
            API.SysMsg(f"Healing pet ({int(lowest_hp_pct)}% HP)", HUE_GREEN)
            return True

        return False
    except:
        return False

# ============ PATHFINDING FUNCTIONS ============

def pathfind_to_wheel():
    """Pathfind to spinning wheel."""
    if wheel_x == 0 or wheel_y == 0:
        return False

    # Check if already there
    dist_x = abs(API.Player.X - wheel_x)
    dist_y = abs(API.Player.Y - wheel_y)
    if dist_x <= 2 and dist_y <= 2:
        return True

    # Start pathfinding
    API.Pathfind(wheel_x, wheel_y)

    # Wait for arrival (max 30s)
    start_time = time.time()
    while time.time() < start_time + 30:
        API.ProcessCallbacks()

        if ui_closed or paused:
            if API.Pathfinding():
                API.CancelPathfinding()
            return False

        # Check if arrived
        dist_x = abs(API.Player.X - wheel_x)
        dist_y = abs(API.Player.Y - wheel_y)
        if dist_x <= 2 and dist_y <= 2:
            if API.Pathfinding():
                API.CancelPathfinding()
            return True

        API.Pause(0.1)

    # Timeout
    if API.Pathfinding():
        API.CancelPathfinding()
    return False

def pathfind_to_loom():
    """Pathfind to loom."""
    if loom_x == 0 or loom_y == 0:
        return False

    # Check if already there
    dist_x = abs(API.Player.X - loom_x)
    dist_y = abs(API.Player.Y - loom_y)
    if dist_x <= 2 and dist_y <= 2:
        return True

    # Start pathfinding
    API.Pathfind(loom_x, loom_y)

    # Wait for arrival (max 30s)
    start_time = time.time()
    while time.time() < start_time + 30:
        API.ProcessCallbacks()

        if ui_closed or paused:
            if API.Pathfinding():
                API.CancelPathfinding()
            return False

        # Check if arrived
        dist_x = abs(API.Player.X - loom_x)
        dist_y = abs(API.Player.Y - loom_y)
        if dist_x <= 2 and dist_y <= 2:
            if API.Pathfinding():
                API.CancelPathfinding()
            return True

        API.Pause(0.1)

    # Timeout
    if API.Pathfinding():
        API.CancelPathfinding()
    return False

# ============ PROCESSING FUNCTIONS ============

def spin_cotton():
    """Use spinning wheel to spin cotton into spools."""
    if wheel_serial == 0:
        return False

    wheel = API.FindItem(wheel_serial)
    if not wheel:
        API.SysMsg("Spinning wheel not found!", HUE_RED)
        return False

    # Use wheel
    API.UseObject(wheel_serial, False)
    API.Pause(SPIN_DELAY)

    # Check journal
    if API.InJournal("You create some thread"):
        stats.increment("cotton_spun")
        return True

    return False

def weave_cloth():
    """Use loom to weave spools into cloth."""
    if loom_serial == 0:
        return False

    loom = API.FindItem(loom_serial)
    if not loom:
        API.SysMsg("Loom not found!", HUE_RED)
        return False

    # Use loom
    API.UseObject(loom_serial, False)
    API.Pause(WEAVE_DELAY)

    # Check journal
    if API.InJournal("You create some cloth"):
        stats.increment("cloth_woven")
        return True

    return False

def cut_cloth():
    """Use scissors to cut cloth bolts into pieces."""
    scissors = find_backpack_item(SCISSORS_GRAPHIC)
    if not scissors:
        return False

    bolts = find_backpack_item(CLOTH_BOLT_GRAPHIC)
    if not bolts:
        return False

    # Cancel any existing targets
    if API.HasTarget():
        API.CancelTarget()
    API.CancelPreTarget()

    # Use scissors
    API.UseObject(scissors.Serial, False)
    API.Pause(0.3)

    # Wait for target cursor
    wait_start = time.time()
    while not API.HasTarget() and time.time() < wait_start + 2:
        API.Pause(0.1)

    if not API.HasTarget():
        return False

    # Target cloth bolts
    API.PreTarget(bolts.Serial, "harmful")
    API.Pause(0.1)
    API.CancelPreTarget()

    API.Pause(CUT_DELAY)

    # Check journal
    if API.InJournal("You cut the cloth"):
        stats.increment("cloth_cut")
        return True

    return False

def make_bandages():
    """Make bandages from cloth pieces."""
    cloth = find_backpack_item(CLOTH_PIECE_GRAPHIC)
    if not cloth:
        return False

    # Cancel any existing targets
    if API.HasTarget():
        API.CancelTarget()
    API.CancelPreTarget()

    # Use cloth
    API.UseObject(cloth.Serial, False)
    API.Pause(MAKE_BANDAGE_DELAY)

    # Check journal
    if API.InJournal("You make some bandages"):
        stats.increment("bandages_made")
        return True

    return False

# ============ PICKING FUNCTIONS ============

def loot_cotton():
    """Loot cotton from ground."""
    # Find all cotton bales on ground
    bales = API.GetItemsOnGround(LOOT_RANGE, COTTON_GRAPHIC)
    if not bales or len(bales) == 0:
        return False

    backpack = API.Player.Backpack
    if not backpack:
        return False

    looted = False
    for bale in bales:
        if not bale:
            continue

        # Move to backpack
        API.MoveItem(bale.Serial, backpack, 0)
        API.Pause(0.6)
        looted = True

    return looted

# ============ FULL AUTOMATION STATE MACHINE ============

def fullauto_logic():
    """Full automation state machine."""
    global fullauto_state, fullauto_start_time, no_plants_start_time
    global fullauto_empty_farms_count, current_farm, respawn_wait_start
    global in_combat, combat_start_time, current_enemy_serial, last_kill_command_time
    global paused

    if paused or ui_closed:
        fullauto_state = "checking_inventory"
        if API.Pathfinding():
            API.CancelPathfinding()
        return

    # Combat check (highest priority)
    if not travel_system.at_home:
        enemies = combat_system.find_all_hostiles()
        if enemies and len(enemies) > 0 and not enemies[0].IsDead:
            in_combat = True
            combat_start_time = time.time()
            fullauto_state = "combat_mode"

    # Global timeout per state
    if time.time() > fullauto_start_time + fullauto_timeout:
        API.SysMsg(f"State timeout in {fullauto_state}", HUE_RED)
        fullauto_state = "checking_inventory"
        fullauto_start_time = time.time()

    # State machine
    if fullauto_state == "checking_inventory":
        fullauto_start_time = time.time()

        # Check if in respawn wait
        if respawn_wait_start > 0:
            remaining = RESPAWN_WAIT - (time.time() - respawn_wait_start)
            if remaining > 0:
                fullauto_state = "waiting_for_respawn"
                return
            else:
                # Wait complete
                respawn_wait_start = 0
                fullauto_empty_farms_count = 0

        # CRITICAL: Check if we have materials and need to be at home to process them
        has_materials = (count_cloth_pieces() > 0 or count_bandages() > 0 or
                         count_cloth_bolts() > 0 or count_spools() > 0 or
                         count_cotton() > 0)

        if has_materials and not travel_system.at_home:
            # Have materials but not at home - recall home first
            API.SysMsg("Have materials - recalling home to process", HUE_YELLOW)
            fullauto_state = "recalling_home"
            fullauto_start_time = time.time()
            return

        # Priority: process materials first (we're at home if we have any)
        if count_cloth_pieces() > 0:
            fullauto_state = "making_bandages_phase"
        elif count_bandages() > 0:
            fullauto_state = "pathfinding_to_storage"
        elif count_cloth_bolts() > 0:
            if not have_scissors():
                API.SysMsg("WARNING: No scissors found!", HUE_RED)
                fullauto_state = "pathfinding_to_storage"  # Store bolts
            else:
                fullauto_state = "cutting_phase"
        elif count_spools() > 0:
            fullauto_state = "pathfinding_to_loom"
        elif count_cotton() > 0:
            fullauto_state = "pathfinding_to_wheel"
        else:
            # No materials - go pick
            fullauto_state = "recalling_to_farm"

    elif fullauto_state == "recalling_to_farm":
        fullauto_start_time = time.time()

        # Call pets to follow before recall
        if combat_system:
            combat_system.all_follow_me()
            API.Pause(0.5)

        # Calculate farm slot
        farm_slot = first_farm_slot + current_farm

        API.SysMsg(f"Recalling to farm {current_farm + 1}...", HUE_YELLOW)

        if travel_system.recall_to_slot(farm_slot):
            travel_system.at_home = False
            no_plants_start_time = 0  # Reset timer - picking_phase will initialize

            # Call pets to guard after arrival
            if combat_system:
                combat_system.all_guard_me()
                API.Pause(0.5)

            # Save current farm index after successful recall (like original)
            save_settings()

            fullauto_state = "picking_phase"
        else:
            API.SysMsg("Recall failed - pausing", HUE_RED)
            fullauto_state = "checking_inventory"

    elif fullauto_state == "picking_phase":
        fullauto_start_time = time.time()

        # CRITICAL: Check for enemies FIRST (before any other checks)
        if not travel_system.at_home:
            enemies = combat_system.find_all_hostiles()
            if enemies and len(enemies) > 0:
                API.SysMsg("=== ENEMY DETECTED - ENTERING COMBAT ===", HUE_RED)

                # Call pets to guard
                if combat_system:
                    combat_system.all_guard_me()
                    API.Pause(0.5)

                # Attack closest enemy
                if combat_system.all_kill(enemies[0]):
                    current_enemy_serial = getattr(enemies[0], 'Serial', 0)
                    last_kill_command_time = time.time()
                    API.SysMsg(f"Pets attacking enemy at {enemies[0].Distance} tiles!", HUE_RED)
                    combat_start_time = time.time()
                    in_combat = True

                fullauto_state = "combat_mode"
                return

        # Check for player damage
        if damage_tracker.is_taking_damage():
            API.SysMsg("=== TAKING DAMAGE - ENTERING COMBAT ===", HUE_RED)

            # Call pets to guard
            if combat_system:
                combat_system.all_guard_me()
                API.Pause(0.5)

            # Find and attack enemy
            enemy = combat_system.find_closest_hostile()
            if enemy:
                API.SysMsg(f"Attacking hostile at {enemy.Distance} tiles!", HUE_RED)
                if combat_system.all_kill(enemy):
                    current_enemy_serial = getattr(enemy, 'Serial', 0)
                    last_kill_command_time = time.time()
                combat_start_time = time.time()
                in_combat = True

            fullauto_state = "combat_mode"
            return

        # Check for pet damage
        if check_pets_taking_damage():
            API.SysMsg("=== PET TAKING DAMAGE - ENTERING COMBAT ===", HUE_RED)

            # Call pets to guard
            if combat_system:
                combat_system.all_guard_me()
                API.Pause(0.5)

            # Find and attack enemy
            enemy = combat_system.find_closest_hostile()
            if enemy:
                API.SysMsg(f"Pet being attacked - targeting enemy at {enemy.Distance} tiles!", HUE_RED)
                if combat_system.all_kill(enemy):
                    current_enemy_serial = getattr(enemy, 'Serial', 0)
                    last_kill_command_time = time.time()
                combat_start_time = time.time()
                in_combat = True

            fullauto_state = "combat_mode"
            return

        # Check weight
        if weight_manager.should_dump():
            API.SysMsg("Weight threshold reached", HUE_YELLOW)
            fullauto_state = "recalling_home"
            return

        # Find plants
        plants = resource_finder.find_resources()

        if not plants or len(plants) == 0:
            # Initialize timer on first "no plants" detection
            if no_plants_start_time == 0:
                no_plants_start_time = time.time()
                API.SysMsg("No plants found - waiting for timeout...", HUE_YELLOW)

            # Check timeout
            elapsed = time.time() - no_plants_start_time
            if elapsed > NO_PLANTS_TIMEOUT:
                # No plants for 30s - try next farm
                API.SysMsg(f"Timeout reached ({NO_PLANTS_TIMEOUT}s) - rotating", HUE_YELLOW)

                if num_farm_spots > 1:
                    fullauto_empty_farms_count += 1

                    if fullauto_empty_farms_count >= num_farm_spots:
                        # All farms empty - go home and wait
                        API.SysMsg("All farms empty - waiting 15 min", HUE_YELLOW)
                        fullauto_empty_farms_count = 0
                        respawn_wait_start = time.time()
                        no_plants_start_time = 0
                        fullauto_state = "recalling_home"
                    else:
                        # Try next farm
                        current_farm = (current_farm + 1) % num_farm_spots
                        no_plants_start_time = 0  # Reset timer for new farm
                        fullauto_state = "recalling_to_farm"
                else:
                    # Single farm - wait here
                    API.SysMsg("Farm empty - waiting 15 min", HUE_YELLOW)
                    respawn_wait_start = time.time()
                    no_plants_start_time = 0
                    fullauto_state = "waiting_for_respawn"
            else:
                # Show countdown every 5 seconds
                remaining = int(NO_PLANTS_TIMEOUT - elapsed)
                if int(elapsed) % 5 == 0 and int(elapsed) > 0:
                    API.SysMsg(f"Waiting for plants: {remaining}s remaining", HUE_YELLOW)
            return

        # Plants found - reset no-plants timer
        no_plants_start_time = time.time()
        fullauto_empty_farms_count = 0

        # Filter plants by cooldown
        available_plants = [p for p in plants if not is_plant_on_cooldown(p.Serial)]

        if not available_plants:
            # All plants on cooldown - wait
            API.Pause(0.5)
            return

        # Pick closest available plant (already sorted by distance)
        plant = available_plants[0]

        # Pathfind if too far (must be exactly PICK_REACH=1 tile to pick)
        if plant.Distance > PICK_REACH:
            if not API.Pathfinding():
                API.Pathfind(plant.X, plant.Y)
            return

        # Cancel pathfinding if arrived
        if API.Pathfinding():
            API.CancelPathfinding()

        # Pick the plant - cotton uses UseObject (no tool needed)
        API.ClearJournal()
        API.UseObject(plant.Serial, False)
        last_clicked[plant.Serial] = time.time()  # Record cooldown
        stats.increment("cotton_picked")
        API.Pause(PICK_DELAY)

        # Loot cotton from ground
        if loot_cotton():
            stats.increment("cotton_looted")

    elif fullauto_state == "recalling_home":
        fullauto_start_time = time.time()

        # Call pets to follow before recall
        if combat_system:
            combat_system.all_follow_me()
            API.Pause(0.5)

        API.SysMsg("Recalling home...", HUE_YELLOW)

        if travel_system.recall_home():
            travel_system.at_home = True

            # Call pets to guard after arrival
            if combat_system:
                combat_system.all_guard_me()
                API.Pause(0.5)

            fullauto_state = "checking_inventory"
        else:
            API.SysMsg("Recall home failed - pausing", HUE_RED)
            fullauto_state = "checking_inventory"

    elif fullauto_state == "pathfinding_to_wheel":
        fullauto_start_time = time.time()

        API.SysMsg("Pathfinding to spinning wheel...", HUE_YELLOW)

        if pathfind_to_wheel():
            fullauto_state = "spinning_phase"
        else:
            API.SysMsg("Pathfinding to wheel failed", HUE_RED)
            fullauto_state = "checking_inventory"

    elif fullauto_state == "spinning_phase":
        fullauto_start_time = time.time()

        if count_cotton() > 0:
            if spin_cotton():
                API.SysMsg("Spun cotton into spools", HUE_GREEN)
        else:
            fullauto_state = "checking_inventory"

    elif fullauto_state == "pathfinding_to_loom":
        fullauto_start_time = time.time()

        API.SysMsg("Pathfinding to loom...", HUE_YELLOW)

        if pathfind_to_loom():
            fullauto_state = "weaving_phase"
        else:
            API.SysMsg("Pathfinding to loom failed", HUE_RED)
            fullauto_state = "checking_inventory"

    elif fullauto_state == "weaving_phase":
        fullauto_start_time = time.time()

        if count_spools() > 0:
            if weave_cloth():
                API.SysMsg("Wove spools into cloth", HUE_GREEN)
        else:
            fullauto_state = "checking_inventory"

    elif fullauto_state == "cutting_phase":
        fullauto_start_time = time.time()

        if count_cloth_bolts() > 0:
            if cut_cloth():
                API.SysMsg("Cut cloth into pieces", HUE_GREEN)
        else:
            fullauto_state = "checking_inventory"

    elif fullauto_state == "making_bandages_phase":
        fullauto_start_time = time.time()

        if count_cloth_pieces() > 0:
            if make_bandages():
                API.SysMsg("Made bandages from cloth", HUE_GREEN)
        else:
            fullauto_state = "checking_inventory"

    elif fullauto_state == "pathfinding_to_storage":
        fullauto_start_time = time.time()

        API.SysMsg("Pathfinding to storage...", HUE_YELLOW)

        if storage_system.pathfind_to_container():
            fullauto_state = "storing_phase"
        else:
            API.SysMsg("Pathfinding to storage failed", HUE_RED)
            fullauto_state = "checking_inventory"

    elif fullauto_state == "storing_phase":
        fullauto_start_time = time.time()

        if storage_system.dump_resources():
            stats.increment("dumps_completed")
            API.SysMsg("Resources stored successfully!", HUE_GREEN)
            fullauto_state = "checking_inventory"
        else:
            API.SysMsg("Failed to store resources", HUE_RED)
            fullauto_state = "checking_inventory"

    elif fullauto_state == "waiting_for_respawn":
        fullauto_start_time = time.time()

        remaining = RESPAWN_WAIT - (time.time() - respawn_wait_start)

        if remaining <= 0:
            API.SysMsg("Respawn wait complete - returning to farm", HUE_GREEN)
            respawn_wait_start = 0
            fullauto_empty_farms_count = 0
            fullauto_state = "checking_inventory"
        else:
            # Show countdown every 60s
            if int(remaining) % 60 == 0:
                mins = int(remaining / 60)
                API.SysMsg(f"Waiting for respawn: {mins} min remaining", HUE_YELLOW)

    elif fullauto_state == "combat_mode":
        fullauto_start_time = time.time()

        # Check for enemies
        enemies = combat_system.find_all_hostiles()

        if not enemies or len(enemies) == 0:
            API.SysMsg("All enemies dead", HUE_GREEN)

            # Guard pets - use combat_system not pet_system
            if combat_system:
                combat_system.all_guard_me()

            in_combat = False
            current_enemy_serial = 0
            fullauto_state = "checking_inventory"
            return

        # Check if should flee
        if combat_system.should_flee():
            API.SysMsg("HP low - fleeing!", HUE_RED)

            # Call pets to follow before fleeing
            if combat_system:
                combat_system.all_follow_me()
                API.Pause(0.5)

            closest_enemy = enemies[0]  # Already a mobile object
            if combat_system.flee_from_enemy(closest_enemy):
                # Fled successfully - recall home
                if travel_system.recall_home():
                    travel_system.at_home = True
                    in_combat = False
                    current_enemy_serial = 0
                    API.SysMsg("Recalled home after flee - healing", HUE_YELLOW)
                    fullauto_state = "healing_after_combat"
        else:
            # Command pets to kill (with 5s cooldown per enemy)
            closest_enemy = enemies[0]  # Already a mobile object
            enemy_serial = getattr(closest_enemy, 'Serial', 0)

            # Only re-target if new enemy or 5s has passed
            if enemy_serial != current_enemy_serial or time.time() > last_kill_command_time + 5.0:
                if combat_system.all_kill(closest_enemy):
                    current_enemy_serial = enemy_serial
                    last_kill_command_time = time.time()
                    API.SysMsg(f"Pets attacking enemy at {closest_enemy.Distance} tiles", HUE_GREEN)

        # Pause in combat loop to avoid spam
        API.Pause(1.0)

    elif fullauto_state == "healing_after_combat":
        # Reset timeout at start of phase to prevent timeout during healing
        fullauto_start_time = time.time()

        # Check for bandages
        if count_bandages() == 0:
            API.SysMsg("=== OUT OF BANDAGES - PAUSING ===", HUE_RED)
            paused = True
            fullauto_state = "checking_inventory"
            return

        # Heal pets first
        if heal_pets():
            API.Pause(BANDAGE_DELAY)
            return  # Try to heal more pets next cycle

        # Check if player needs healing
        current_hp = API.Player.Hits
        max_hp = getattr(API.Player, 'HitsMax', 1)
        hp_pct = (current_hp / max_hp * 100) if max_hp > 0 else 100

        if hp_pct < 90:
            if use_bandage_on_self():
                API.SysMsg(f"Healing self ({int(hp_pct)}% HP)", HUE_YELLOW)
                API.Pause(BANDAGE_DELAY)
                return  # Wait for bandage to finish

        # All healed - continue
        API.SysMsg("Healing complete - continuing", HUE_GREEN)
        fullauto_state = "checking_inventory"

# ============ PERSISTENCE ============

def save_settings():
    """Save all settings to persistence."""
    API.SavePersistentVar(KEY_PREFIX + "RunebookSerial", str(runebook_serial), API.PersistentVar.Char)
    API.SavePersistentVar(KEY_PREFIX + "WheelSerial", str(wheel_serial), API.PersistentVar.Char)
    API.SavePersistentVar(KEY_PREFIX + "LoomSerial", str(loom_serial), API.PersistentVar.Char)
    API.SavePersistentVar(KEY_PREFIX + "StorageSerial", str(storage_serial), API.PersistentVar.Char)
    API.SavePersistentVar(KEY_PREFIX + "NumFarmSpots", str(num_farm_spots), API.PersistentVar.Char)
    API.SavePersistentVar(KEY_PREFIX + "WeightThreshold", str(weight_threshold), API.PersistentVar.Char)
    API.SavePersistentVar(KEY_PREFIX + "HomeSlot", str(home_slot), API.PersistentVar.Char)
    API.SavePersistentVar(KEY_PREFIX + "FirstFarmSlot", str(first_farm_slot), API.PersistentVar.Char)
    API.SavePersistentVar(KEY_PREFIX + "WheelX", str(wheel_x), API.PersistentVar.Char)
    API.SavePersistentVar(KEY_PREFIX + "WheelY", str(wheel_y), API.PersistentVar.Char)
    API.SavePersistentVar(KEY_PREFIX + "LoomX", str(loom_x), API.PersistentVar.Char)
    API.SavePersistentVar(KEY_PREFIX + "LoomY", str(loom_y), API.PersistentVar.Char)
    API.SavePersistentVar(KEY_PREFIX + "StorageX", str(storage_x), API.PersistentVar.Char)
    API.SavePersistentVar(KEY_PREFIX + "StorageY", str(storage_y), API.PersistentVar.Char)
    API.SavePersistentVar(KEY_PREFIX + "CurrentFarm", str(current_farm), API.PersistentVar.Char)

def load_settings():
    """Load all settings from persistence."""
    global runebook_serial, wheel_serial, loom_serial, storage_serial
    global num_farm_spots, weight_threshold, home_slot, first_farm_slot
    global wheel_x, wheel_y, loom_x, loom_y, storage_x, storage_y, current_farm

    runebook_serial = int(API.GetPersistentVar(KEY_PREFIX + "RunebookSerial", "0", API.PersistentVar.Char))
    wheel_serial = int(API.GetPersistentVar(KEY_PREFIX + "WheelSerial", "0", API.PersistentVar.Char))
    loom_serial = int(API.GetPersistentVar(KEY_PREFIX + "LoomSerial", "0", API.PersistentVar.Char))
    storage_serial = int(API.GetPersistentVar(KEY_PREFIX + "StorageSerial", "0", API.PersistentVar.Char))
    num_farm_spots = int(API.GetPersistentVar(KEY_PREFIX + "NumFarmSpots", "3", API.PersistentVar.Char))
    weight_threshold = int(API.GetPersistentVar(KEY_PREFIX + "WeightThreshold", "80", API.PersistentVar.Char))
    home_slot = int(API.GetPersistentVar(KEY_PREFIX + "HomeSlot", "1", API.PersistentVar.Char))
    first_farm_slot = int(API.GetPersistentVar(KEY_PREFIX + "FirstFarmSlot", "2", API.PersistentVar.Char))
    wheel_x = int(API.GetPersistentVar(KEY_PREFIX + "WheelX", "0", API.PersistentVar.Char))
    wheel_y = int(API.GetPersistentVar(KEY_PREFIX + "WheelY", "0", API.PersistentVar.Char))
    loom_x = int(API.GetPersistentVar(KEY_PREFIX + "LoomX", "0", API.PersistentVar.Char))
    loom_y = int(API.GetPersistentVar(KEY_PREFIX + "LoomY", "0", API.PersistentVar.Char))
    storage_x = int(API.GetPersistentVar(KEY_PREFIX + "StorageX", "0", API.PersistentVar.Char))
    storage_y = int(API.GetPersistentVar(KEY_PREFIX + "StorageY", "0", API.PersistentVar.Char))
    current_farm = int(API.GetPersistentVar(KEY_PREFIX + "CurrentFarm", "0", API.PersistentVar.Char))

# ============ GUI CALLBACKS ============

def on_start():
    """Start full automation."""
    global paused, fullauto_state

    # Validate configuration
    if runebook_serial == 0:
        API.SysMsg("ERROR: Runebook not set!", HUE_RED)
        return

    if wheel_serial == 0:
        API.SysMsg("ERROR: Spinning wheel not set!", HUE_RED)
        return

    if loom_serial == 0:
        API.SysMsg("ERROR: Loom not set!", HUE_RED)
        return

    if storage_serial == 0:
        API.SysMsg("ERROR: Storage container not set!", HUE_RED)
        return

    paused = False
    fullauto_state = "checking_inventory"
    API.SysMsg("Cotton Picker started!", HUE_GREEN)

def on_pause():
    """Toggle pause."""
    global paused
    paused = not paused

    if paused:
        API.SysMsg("Cotton Picker PAUSED", HUE_YELLOW)
        if API.Pathfinding():
            API.CancelPathfinding()
    else:
        API.SysMsg("Cotton Picker RESUMED", HUE_GREEN)

def on_emergency_recall():
    """Emergency recall home."""
    if travel_system.recall_home():
        API.SysMsg("EMERGENCY RECALL - AT HOME", HUE_RED)
    else:
        API.SysMsg("EMERGENCY RECALL FAILED!", HUE_RED)

def on_set_runebook():
    """Set runebook."""
    global runebook_serial

    API.SysMsg("Target runebook...", HUE_YELLOW)
    target = API.RequestTarget(15)

    if target:
        item = API.FindItem(target)
        if item:
            runebook_serial = target
            save_settings()

            # Update travel system
            if travel_system:
                travel_system.runebook_serial = runebook_serial

            API.SysMsg("Runebook set!", HUE_GREEN)
            update_display()

def on_set_wheel():
    """Set spinning wheel."""
    global wheel_serial, wheel_x, wheel_y

    API.SysMsg("Target spinning wheel...", HUE_YELLOW)
    target = API.RequestTarget(15)

    if target:
        item = API.FindItem(target)
        if item:
            wheel_serial = target
            wheel_x = item.X
            wheel_y = item.Y
            save_settings()
            API.SysMsg("Spinning wheel set!", HUE_GREEN)
            update_display()

def on_set_loom():
    """Set loom."""
    global loom_serial, loom_x, loom_y

    API.SysMsg("Target loom...", HUE_YELLOW)
    target = API.RequestTarget(15)

    if target:
        item = API.FindItem(target)
        if item:
            loom_serial = target
            loom_x = item.X
            loom_y = item.Y
            save_settings()
            API.SysMsg("Loom set!", HUE_GREEN)
            update_display()

def on_set_storage():
    """Set storage container."""
    global storage_serial, storage_x, storage_y

    API.SysMsg("Target storage container...", HUE_YELLOW)
    target = API.RequestTarget(15)

    if target:
        item = API.FindItem(target)
        if item:
            storage_serial = target
            storage_x = item.X
            storage_y = item.Y
            save_settings()

            # Update storage system
            if storage_system:
                storage_system.container_serial = storage_serial

            API.SysMsg("Storage container set!", HUE_GREEN)
            update_display()

def on_farm_decrease():
    """Decrease number of farm spots."""
    global num_farm_spots

    if num_farm_spots > 1:
        num_farm_spots -= 1
        save_settings()
        update_display()
        API.SysMsg(f"Farm spots: {num_farm_spots}", HUE_YELLOW)

def on_farm_increase():
    """Increase number of farm spots."""
    global num_farm_spots

    if num_farm_spots < 14:
        num_farm_spots += 1
        save_settings()
        update_display()
        API.SysMsg(f"Farm spots: {num_farm_spots}", HUE_YELLOW)

def on_closed():
    """Handle window close."""
    global ui_closed
    ui_closed = True

    if API.Pathfinding():
        API.CancelPathfinding()

# ============ DISPLAY UPDATES ============

def update_display():
    """Update GUI labels."""
    if ui_closed or gump is None:
        return

    # Status
    if paused:
        status = "PAUSED"
        color = HUE_YELLOW
    elif in_combat:
        status = "COMBAT"
        color = HUE_RED
    else:
        status = fullauto_state.replace("_", " ").upper()
        color = HUE_GREEN

    if "status" in labels:
        labels["status"].SetText(f"Status: {status}")

    # Configuration status
    config_status = []
    if runebook_serial > 0:
        config_status.append("RB")
    if wheel_serial > 0:
        config_status.append("WHL")
    if loom_serial > 0:
        config_status.append("LM")
    if storage_serial > 0:
        config_status.append("STR")

    if "config" in labels:
        labels["config"].SetText("Config: " + "/".join(config_status) if config_status else "NONE")

    # Farm count
    if "farm_count" in labels:
        labels["farm_count"].SetText(str(num_farm_spots))

    # Stats
    if stats:
        if "cotton_picked" in labels:
            labels["cotton_picked"].SetText(f"Cotton Picked: {stats.get('cotton_picked')}")

        if "bandages_made" in labels:
            labels["bandages_made"].SetText(f"Bandages Made: {stats.get('bandages_made')}")

        if "dumps" in labels:
            labels["dumps"].SetText(f"Dumps: {stats.get('dumps_completed')}")

    # Inventory
    if "inventory" in labels:
        inv_text = f"Cotton:{count_cotton()} Spools:{count_spools()} Cloth:{count_cloth_bolts()} Pieces:{count_cloth_pieces()} Bandages:{count_bandages()}"
        labels["inventory"].SetText(inv_text)

# ============ INITIALIZATION ============

def initialize():
    """Initialize framework components."""
    global travel_system, storage_system, weight_manager, state_machine
    global combat_system, pet_system, resource_finder, stats, damage_tracker

    # Load settings
    load_settings()

    # Initialize framework
    travel_system = TravelSystem(runebook_serial, num_farm_spots, home_slot=home_slot)
    storage_system = StorageSystem(storage_serial)
    weight_manager = WeightManager(weight_threshold)
    state_machine = StateMachine()
    combat_system = CombatSystem(mode="flee", flee_hp_threshold=50)
    pet_system = PetSystem()
    resource_finder = ResourceFinder(COTTON_PLANT_GRAPHICS, SCAN_RANGE)  # All growth stages
    stats = SessionStats()
    damage_tracker = DamageTracker()

# ============ BUILD GUI ============

def build_gui():
    """Build GUI window."""
    global gump, labels

    gump = API.Gumps.CreateGump()
    gump.SetRect(100, 100, 400, 500)

    # Background
    bg = API.Gumps.CreateGumpColorBox(0.85, "#1a1a1a")
    bg.SetRect(0, 0, 400, 500)
    gump.Add(bg)

    # Title
    title = API.Gumps.CreateGumpTTFLabel("Cotton Picker 2 v1.0", 16, "#ffaa00")
    title.SetPos(10, 10)
    gump.Add(title)

    y = 40

    # Status
    labels["status"] = API.Gumps.CreateGumpTTFLabel("Status: IDLE", 11, "#00ff00")
    labels["status"].SetPos(10, y)
    gump.Add(labels["status"])
    y += 20

    # Config status
    labels["config"] = API.Gumps.CreateGumpTTFLabel("Config: NONE", 11, "#888888")
    labels["config"].SetPos(10, y)
    gump.Add(labels["config"])
    y += 30

    # Control buttons
    start_btn = API.Gumps.CreateSimpleButton("[START]", 80, 22)
    start_btn.SetPos(10, y)
    gump.Add(start_btn)
    API.Gumps.AddControlOnClick(start_btn, on_start)

    pause_btn = API.Gumps.CreateSimpleButton("[PAUSE]", 80, 22)
    pause_btn.SetPos(100, y)
    gump.Add(pause_btn)
    API.Gumps.AddControlOnClick(pause_btn, on_pause)

    recall_btn = API.Gumps.CreateSimpleButton("[RECALL]", 80, 22)
    recall_btn.SetPos(190, y)
    gump.Add(recall_btn)
    API.Gumps.AddControlOnClick(recall_btn, on_emergency_recall)
    y += 40

    # Configuration section
    config_label = API.Gumps.CreateGumpTTFLabel("=== CONFIGURATION ===", 13, "#ffcc00")
    config_label.SetPos(10, y)
    gump.Add(config_label)
    y += 25

    # Runebook
    rb_btn = API.Gumps.CreateSimpleButton("[Set Runebook]", 120, 22)
    rb_btn.SetPos(10, y)
    gump.Add(rb_btn)
    API.Gumps.AddControlOnClick(rb_btn, on_set_runebook)
    y += 30

    # Wheel
    wheel_btn = API.Gumps.CreateSimpleButton("[Set Wheel]", 120, 22)
    wheel_btn.SetPos(10, y)
    gump.Add(wheel_btn)
    API.Gumps.AddControlOnClick(wheel_btn, on_set_wheel)
    y += 30

    # Loom
    loom_btn = API.Gumps.CreateSimpleButton("[Set Loom]", 120, 22)
    loom_btn.SetPos(10, y)
    gump.Add(loom_btn)
    API.Gumps.AddControlOnClick(loom_btn, on_set_loom)
    y += 30

    # Storage
    storage_btn = API.Gumps.CreateSimpleButton("[Set Storage]", 120, 22)
    storage_btn.SetPos(10, y)
    gump.Add(storage_btn)
    API.Gumps.AddControlOnClick(storage_btn, on_set_storage)
    y += 30

    # Farm count controls
    farm_label = API.Gumps.CreateGumpTTFLabel("Farms:", 11, "#cccccc")
    farm_label.SetPos(10, y)
    gump.Add(farm_label)

    farm_dec_btn = API.Gumps.CreateSimpleButton("[-]", 30, 22)
    farm_dec_btn.SetPos(70, y - 2)
    gump.Add(farm_dec_btn)
    API.Gumps.AddControlOnClick(farm_dec_btn, on_farm_decrease)

    labels["farm_count"] = API.Gumps.CreateGumpTTFLabel(str(num_farm_spots), 11, "#00ff88")
    labels["farm_count"].SetPos(110, y)
    gump.Add(labels["farm_count"])

    farm_inc_btn = API.Gumps.CreateSimpleButton("[+]", 30, 22)
    farm_inc_btn.SetPos(140, y - 2)
    gump.Add(farm_inc_btn)
    API.Gumps.AddControlOnClick(farm_inc_btn, on_farm_increase)
    y += 40

    # Stats section
    stats_label = API.Gumps.CreateGumpTTFLabel("=== STATISTICS ===", 13, "#ffcc00")
    stats_label.SetPos(10, y)
    gump.Add(stats_label)
    y += 25

    labels["cotton_picked"] = API.Gumps.CreateGumpTTFLabel("Cotton Picked: 0", 11, "#00ff88")
    labels["cotton_picked"].SetPos(10, y)
    gump.Add(labels["cotton_picked"])
    y += 20

    labels["bandages_made"] = API.Gumps.CreateGumpTTFLabel("Bandages Made: 0", 11, "#00ff88")
    labels["bandages_made"].SetPos(10, y)
    gump.Add(labels["bandages_made"])
    y += 20

    labels["dumps"] = API.Gumps.CreateGumpTTFLabel("Dumps: 0", 11, "#00ff88")
    labels["dumps"].SetPos(10, y)
    gump.Add(labels["dumps"])
    y += 30

    # Inventory
    labels["inventory"] = API.Gumps.CreateGumpTTFLabel("Inventory: ...", 9, "#888888")
    labels["inventory"].SetPos(10, y)
    gump.Add(labels["inventory"])

    # Close callback
    API.Gumps.AddControlOnDisposed(gump, on_closed)

    # Display
    API.Gumps.AddGump(gump)

    # Initial update
    update_display()

# ============ MAIN LOOP ============

# Initialize
initialize()
build_gui()

API.SysMsg("Cotton Picker 2 loaded!", HUE_GREEN)
API.SysMsg("Configure runebook, wheel, loom, and storage", HUE_YELLOW)

# Main loop
try:
    while not API.StopRequested and not ui_closed:
        try:
            API.ProcessCallbacks()

            if not paused:
                fullauto_logic()

            update_display()

            API.Pause(0.1)

        except Exception as e:
            API.SysMsg(f"Error: {e}", HUE_RED)
            API.Pause(1.0)

except Exception as e:
    API.SysMsg(f"CRITICAL ERROR: {e}", HUE_RED)

API.SysMsg("Cotton Picker 2 stopped", HUE_RED)
