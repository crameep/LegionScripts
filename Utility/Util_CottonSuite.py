# Util_CottonSuite.py
# Cotton farming automation with Picker, Weaver, and AutoPick modes
# Converted from RazorEnhanced by Frogmancer Schteve
import API
import time

# ============ CONSTANTS ============
# Graphics
COTTON_PLANT_GRAPHICS = [0x0C51, 0x0C52, 0x0C53, 0x0C54]
COTTON_BALE_GRAPHIC = 0x0DF9
SPOOL_GRAPHIC = 0x0FA0
CLOTH_BOLT_GRAPHIC = 0x0F95
SCISSORS_GRAPHIC = 0x0F9F
CLOTH_PIECE_GRAPHIC = 0x1766
BANDAGE_GRAPHIC = 0x0E21
HIGHLIGHT_HUE = 1152

# Ranges and timing
SCAN_RANGE = 24
PICK_REACH = 1
PLANT_COOLDOWN = 10.0  # seconds
CLICK_DELAY = 0.14
SPIN_DELAY = 6.0  # Time for spinning wheel to complete
WEAVE_DELAY = 2.0  # Time for loom to complete weaving
CUT_DELAY = 2.0  # Time to cut cloth bolt
TARGET_TIMEOUT = 2.0
BANDAGE_DELAY = 4.5  # Time to apply bandage
ENEMY_SCAN_RANGE = 12  # Range to scan for enemies
FLEE_DISTANCE = 8  # Tiles to flee when taking damage
EMERGENCY_FLEE_DISTANCE = 18  # Tiles to flee before emergency recall
CRITICAL_HP_THRESHOLD = 40  # Emergency recall below this HP %

# Recall timing
RECALL_DELAY = 2.0  # Seconds for recall to complete
GUMP_WAIT_TIME = 3.0  # Seconds to wait for gump to appear
USE_OBJECT_DELAY = 0.5  # Seconds after using object
GUMP_READY_DELAY = 0.3  # Seconds for gump to be ready for interaction
RUNEBOOK_GUMP_ID = 89  # Runebook gump ID
EMERGENCY_RECALL_BUTTON = 10  # Button for runebook emergency charges

# Weight settings
DEFAULT_MAX_WEIGHT = 450  # Fallback if can't read player weight
NO_PLANTS_TIMEOUT = 5.0  # Seconds before rotating to next farm if no plants found
RESPAWN_WAIT_TIME = 900.0  # 15 minutes wait for plants to respawn at single farm spot

# GUI Colors
COLOR_BG = "#1a1a2e"
COLOR_TITLE = "#ffaa00"
COLOR_GREEN = "#00ff00"
COLOR_RED = "#ff3333"
COLOR_YELLOW = "#ffcc00"
COLOR_GRAY = "#888888"
COLOR_PURPLE = "#cc88ff"

# ============ PERSISTENCE KEYS ============
KEY_PREFIX = "CottonSuite_"

# ============ RUNTIME STATE ============
# Mode control
mode = "idle"  # idle, picker, weaver, autopick, fullautomation
paused = False
ui_closed = False  # Prevent disposed control access

# Picker state
STATE = "idle"  # idle, picking, looting
action_start_time = 0
action_duration = 0
last_clicked = {}  # {plant_serial: timestamp}
last_plant_count = -1
current_target_serial = None
MAX_COOLDOWN_ENTRIES = 100  # Prune last_clicked to prevent memory leak

# Weaver state
weaver_state = "idle"  # idle, spinning, weaving, waiting_bolt
weaver_start_time = 0
weaver_duration = 0
wheel_serial = None
loom_serial = None
wheel_x = 0
wheel_y = 0
loom_x = 0
loom_y = 0

# Storage
storage_box_serial = None
storage_gump_id = 0
storage_button_id = 121
storage_x = 0
storage_y = 0
make_bandages = False  # Toggle: make bandages from cloth instead of storing bolts

# Pet summoning
pet_summoner_serial = None  # Item that summons pets (e.g., spell book, statue, etc.)

# Runebook/farm rotation state
runebook_serial = None
num_farm_spots = 1
current_farm_index = 0  # Index for farm rotation (0 to num_farm_spots-1)
weight_threshold = 80  # Percent of max weight
at_home = True  # Whether player is at home or at farm
no_plants_start_time = 0  # Track when we started finding no plants

# Session stats
session_start = time.time()
stats = {
    "cotton_picked": 0,
    "spools_made": 0,
    "bolts_created": 0,
    "ground_cotton_collected": 0,
    "cloth_cut": 0,
    "cloth_stored": 0,
    "bandages_made": 0,
    "bandages_stored": 0,
    "cycles_completed": 0
}

# Hotkeys
hotkeys = {"pause": "PAUSE"}

DEBUG = False

# ============ UTILITY FUNCTIONS ============
def debug_msg(text):
    if DEBUG:
        API.SysMsg("DEBUG: " + text, 88)

def manhattan_distance(x1, y1, x2, y2):
    """Calculate Manhattan distance between two points."""
    return abs(x1 - x2) + abs(y1 - y2)

def get_player_pos():
    """Get player X, Y coordinates."""
    return getattr(API.Player, 'X', 0), getattr(API.Player, 'Y', 0)

def format_time(seconds):
    """Format seconds as HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return "{:02d}:{:02d}:{:02d}".format(h, m, s)

def format_number(num):
    """Format number with thousands separator."""
    return "{:,}".format(num)

def get_weight_pct():
    """Get player weight percentage."""
    try:
        current_weight = getattr(API.Player, 'Weight', 0)
        max_weight = getattr(API.Player, 'MaxWeight', DEFAULT_MAX_WEIGHT)
        if max_weight <= 0:
            max_weight = DEFAULT_MAX_WEIGHT
        weight_pct = (float(current_weight) / float(max_weight)) * 100.0
        return weight_pct
    except:
        return 0.0

def check_weight_threshold():
    """Check if player weight exceeds threshold."""
    weight_pct = get_weight_pct()
    return weight_pct >= weight_threshold

def slot_to_button(slot):
    """Convert runebook slot to button ID."""
    return 49 + slot

def check_out_of_reagents():
    """Check journal for out of reagents messages."""
    try:
        journal_text = API.InGameJournal.GetText()
        if not journal_text:
            return False

        # Check for reagent messages
        reagent_messages = [
            "reagents to cast",
            "insufficient reagents",
            "more reagents"
        ]

        journal_lower = journal_text.lower()
        for msg in reagent_messages:
            if msg in journal_lower:
                return True

        return False
    except:
        return False

# ============ ITEM FINDING ============
def find_cotton_plants():
    """Find all cotton plants in range, sorted by distance."""
    plants = []
    px, py = get_player_pos()

    # Use GetItemsOnGround to find all plants of each graphic
    for graphic in COTTON_PLANT_GRAPHICS:
        try:
            items = API.GetItemsOnGround(SCAN_RANGE, graphic)
            if items:
                for plant in items:
                    if plant:
                        # Calculate distance for sorting
                        plant_x = getattr(plant, 'X', px)
                        plant_y = getattr(plant, 'Y', py)
                        dist = manhattan_distance(px, py, plant_x, plant_y)
                        plants.append((plant, dist))
        except Exception as e:
            API.SysMsg("Error finding plants: " + str(e), 32)
            continue

    # Sort by distance and return just the plant objects
    plants.sort(key=lambda x: x[1])
    return [p[0] for p in plants]

def find_ground_cotton():
    """Find cotton bales on ground near player."""
    try:
        # Use GetItemsOnGround to find all cotton within 2 tiles
        items = API.GetItemsOnGround(2, COTTON_BALE_GRAPHIC)
        if items:
            return items
    except:
        pass
    return []

def find_backpack_cotton():
    """Find cotton in backpack."""
    backpack = API.Player.Backpack
    if not backpack:
        return None

    # Search backpack for cotton (no hue filter)
    API.FindType(COTTON_BALE_GRAPHIC, backpack.Serial)
    if API.Found:
        return API.Found
    return None

def find_backpack_spool():
    """Find spool in backpack."""
    backpack = API.Player.Backpack
    if not backpack:
        return None

    # Search backpack for spool (no hue filter)
    API.FindType(SPOOL_GRAPHIC, backpack.Serial)
    if API.Found:
        return API.Found
    return None

def count_spools():
    """Count spools in backpack."""
    backpack = API.Player.Backpack
    if not backpack:
        return 0

    # Search backpack for spool (no hue filter)
    API.FindType(SPOOL_GRAPHIC, backpack.Serial)
    if API.Found:
        spool = API.Found
        if spool and hasattr(spool, 'Amount'):
            return spool.Amount
        return 1  # Found but no amount attribute means 1 item
    return 0

def find_backpack_scissors():
    """Find scissors in backpack."""
    backpack = API.Player.Backpack
    if not backpack:
        return None

    # Search backpack for scissors
    API.FindType(SCISSORS_GRAPHIC, backpack.Serial)
    if API.Found:
        return API.Found
    return None

def find_backpack_cloth_bolts():
    """Find cloth bolts in backpack."""
    backpack = API.Player.Backpack
    if not backpack:
        return None

    # Search backpack for cloth bolts
    API.FindType(CLOTH_BOLT_GRAPHIC, backpack.Serial)
    if API.Found:
        return API.Found
    return None

def count_cloth_bolts():
    """Count cloth bolts in backpack."""
    backpack = API.Player.Backpack
    if not backpack:
        return 0

    API.FindType(CLOTH_BOLT_GRAPHIC, backpack.Serial)
    if API.Found:
        bolt = API.Found
        if bolt and hasattr(bolt, 'Amount'):
            return bolt.Amount
        return 1
    return 0

def find_backpack_cloth_pieces():
    """Find cloth pieces in backpack."""
    backpack = API.Player.Backpack
    if not backpack:
        return None

    API.FindType(CLOTH_PIECE_GRAPHIC, backpack.Serial)
    if API.Found:
        return API.Found
    return None

def count_cloth_pieces():
    """Count cloth pieces in backpack."""
    backpack = API.Player.Backpack
    if not backpack:
        return 0

    API.FindType(CLOTH_PIECE_GRAPHIC, backpack.Serial)
    if API.Found:
        cloth = API.Found
        if cloth and hasattr(cloth, 'Amount'):
            return cloth.Amount
        return 1
    return 0

def cut_cloth_bolts():
    """Use scissors to cut all cloth bolts into pieces (one action cuts whole stack)."""
    global stats

    # Auto-find scissors in backpack
    scissors = find_backpack_scissors()
    if not scissors:
        API.SysMsg("No scissors found in backpack! (graphic 0x0F9F)", 32)
        return False

    # Get scissors serial
    if hasattr(scissors, 'Serial'):
        scissors_serial = scissors.Serial
    else:
        scissors_serial = scissors

    bolt = find_backpack_cloth_bolts()
    if not bolt:
        return False

    # Get serial
    if hasattr(bolt, 'Serial'):
        bolt_serial = bolt.Serial
    else:
        bolt_serial = bolt

    # Clear targets
    if API.HasTarget():
        API.CancelTarget()
    API.CancelPreTarget()

    # Clear journal
    API.ClearJournal()

    # Use scissors
    API.UseObject(scissors_serial, False)
    API.Pause(0.3)

    # Wait for target cursor
    wait_start = time.time()
    target_appeared = False
    while time.time() < wait_start + TARGET_TIMEOUT:
        API.ProcessCallbacks()

        if API.HasTarget():
            target_appeared = True
            break

        API.Pause(0.05)

    if not target_appeared:
        return False

    # Target the bolt stack
    API.Target(bolt_serial)
    API.Pause(CUT_DELAY)

    # Check journal for success
    if API.InJournal("You cut the cloth"):
        stats["cloth_cut"] += 1
        return True

    # Assume success if no error
    stats["cloth_cut"] += 1
    return True

def make_bandages_from_cloth():
    """Use scissors on cloth pieces to make bandages.

    Only uses cloth pieces from main backpack (not sub-containers).
    """
    global stats

    # Auto-find scissors in backpack
    scissors = find_backpack_scissors()
    if not scissors:
        API.SysMsg("No scissors found in backpack! (graphic 0x0F9F)", 32)
        return False

    # Get scissors serial
    if hasattr(scissors, 'Serial'):
        scissors_serial = scissors.Serial
    else:
        scissors_serial = scissors

    # Find cloth in main backpack only
    cloth = find_backpack_cloth_pieces()
    if not cloth:
        return False

    # Get serial
    if hasattr(cloth, 'Serial'):
        cloth_serial = cloth.Serial
    else:
        cloth_serial = cloth

    # Clear targets
    if API.HasTarget():
        API.CancelTarget()
    API.CancelPreTarget()

    # Clear journal
    API.ClearJournal()

    # Use scissors
    API.UseObject(scissors_serial, False)
    API.Pause(0.3)

    # Wait for target cursor
    wait_start = time.time()
    target_appeared = False
    while time.time() < wait_start + TARGET_TIMEOUT:
        API.ProcessCallbacks()

        if API.HasTarget():
            target_appeared = True
            break

        API.Pause(0.05)

    if not target_appeared:
        return False

    # Target the cloth stack
    API.Target(cloth_serial)
    API.Pause(CUT_DELAY)

    # Check journal for success (might say "You make bandages" or similar)
    if API.InJournal("bandage"):
        stats["bandages_made"] += 1
        API.SysMsg("Bandages made!", 68)
        return True

    # Assume success
    stats["bandages_made"] += 1
    API.SysMsg("Bandages made!", 68)
    return True

def store_bandages():
    """Store bandages in resource storage bin using Add Item button.

    IMPORTANT: Only stores bandages from MAIN backpack (newly made ones).
    Does NOT touch bandages in sub-containers like loadout bags.
    """
    global storage_gump_id, stats

    if not storage_box_serial:
        API.SysMsg("No storage bin configured!", 32)
        return False

    storage_box = API.FindItem(storage_box_serial)
    if not storage_box:
        API.SysMsg("Storage bin not found!", 32)
        return False

    # Check if we have bandages to store (ONLY main backpack, not sub-containers)
    bandages = find_main_backpack_bandages_only()
    if not bandages:
        return True  # Nothing to store = success

    # Get bandage serial and count
    if hasattr(bandages, 'Serial'):
        bandage_serial = bandages.Serial
        bandage_amount = getattr(bandages, 'Amount', 1)
    else:
        bandage_serial = bandages
        bandage_amount = 1

    try:
        # Use storage bin
        API.UseObject(storage_box_serial)
        API.Pause(USE_OBJECT_DELAY)

        # Wait for gump
        wait_start = time.time()
        gump_found = False
        while time.time() < wait_start + GUMP_WAIT_TIME:
            if API.HasGump(111922706):
                gump_found = True
                storage_gump_id = 111922706
                break
            API.Pause(0.1)

        if not gump_found:
            if not API.WaitForGump(delay=GUMP_WAIT_TIME):
                API.SysMsg("Storage bin gump didn't open!", 32)
                return False

        API.Pause(GUMP_READY_DELAY)

        # Click "Add Item" button (button 120)
        result = API.ReplyGump(120, storage_gump_id if storage_gump_id > 0 else 0)

        if not result:
            API.SysMsg("Failed to click Add Item button!", 32)
            return False

        API.Pause(0.5)

        # Wait for gump to reappear
        wait_start = time.time()
        while time.time() < wait_start + 2.0:
            if API.HasGump(storage_gump_id if storage_gump_id > 0 else 111922706):
                break
            API.Pause(0.1)

        API.Pause(0.5)

        # Target the bandages
        API.Target(bandage_serial)

        # Wait for gump again
        API.Pause(1.0)

        # Close the gump
        if storage_gump_id > 0 and API.HasGump(storage_gump_id):
            API.CloseGump(storage_gump_id)
            API.Pause(0.3)

        stats["bandages_stored"] += bandage_amount
        API.SysMsg("Bandages stored successfully!", 68)
        return True

    except Exception as e:
        API.SysMsg("Error storing bandages: " + str(e), 32)
        return False

def store_resources():
    """Store cloth pieces in resource storage bin using Add Item button.

    IMPORTANT: Only stores cloth pieces (0x1766) from main backpack.
    Does NOT store bandages (0x0E21) - they have different graphic IDs.
    Uses button 120 (Add Item) + target, not button 121 (Fill from Backpack).
    """
    global storage_gump_id, stats

    if not storage_box_serial:
        API.SysMsg("No storage bin configured!", 32)
        return False

    storage_box = API.FindItem(storage_box_serial)
    if not storage_box:
        API.SysMsg("Storage bin not found!", 32)
        return False

    # Check if we have cloth to store (only searches main backpack, not sub-containers)
    cloth = find_backpack_cloth_pieces()
    if not cloth:
        return True  # Nothing to store = success

    # Get cloth serial
    if hasattr(cloth, 'Serial'):
        cloth_serial = cloth.Serial
    else:
        cloth_serial = cloth

    try:
        # Use storage bin
        API.UseObject(storage_box_serial)
        API.Pause(USE_OBJECT_DELAY)

        # Wait for gump (using common resource storage gump ID 111922706 or any gump)
        wait_start = time.time()
        gump_found = False
        while time.time() < wait_start + GUMP_WAIT_TIME:
            if API.HasGump(111922706):  # Common resource storage gump ID
                gump_found = True
                storage_gump_id = 111922706
                break
            API.Pause(0.1)

        if not gump_found:
            # Try generic wait
            if not API.WaitForGump(delay=GUMP_WAIT_TIME):
                API.SysMsg("Storage bin gump didn't open!", 32)
                return False

        API.Pause(GUMP_READY_DELAY)

        # Click "Add Item" button (button 120, not 121!)
        result = API.ReplyGump(120, storage_gump_id if storage_gump_id > 0 else 0)

        if not result:
            API.SysMsg("Failed to click Add Item button!", 32)
            return False

        API.Pause(0.5)

        # Wait for gump to reappear after clicking
        wait_start = time.time()
        while time.time() < wait_start + 2.0:
            if API.HasGump(storage_gump_id if storage_gump_id > 0 else 111922706):
                break
            API.Pause(0.1)

        API.Pause(0.5)

        # Target the cloth pieces
        API.Target(cloth_serial)

        # Wait for gump again to confirm
        API.Pause(1.0)

        # Close the gump
        if storage_gump_id > 0 and API.HasGump(storage_gump_id):
            API.CloseGump(storage_gump_id)
            API.Pause(0.3)

        stats["cloth_stored"] += 1
        API.SysMsg("Cloth stored successfully!", 68)
        return True

    except Exception as e:
        API.SysMsg("Storage error: " + str(e), 32)
        # Try to close gump on error too
        try:
            if storage_gump_id > 0 and API.HasGump(storage_gump_id):
                API.CloseGump(storage_gump_id)
        except:
            pass
        return False

# ============ COMBAT FUNCTIONS ============
def find_closest_hostile():
    """Find closest hostile mob using API.NearestMobile (like TamerSuite)."""
    try:
        # Target Criminal, Murderer, Enemy notorieties
        notorieties = [API.Notoriety.Enemy, API.Notoriety.Murderer, API.Notoriety.Criminal]

        # Search within 10 tiles
        enemy = API.NearestMobile(notorieties, 10)

        if enemy and enemy.Serial != API.Player.Serial and not enemy.IsDead:
            return enemy
        return None
    except:
        return None

def find_enemies():
    """Find hostile mobiles nearby - returns list with closest if exists."""
    enemy = find_closest_hostile()
    if enemy:
        return [enemy]
    return []

def all_kill_closest():
    """Send All Kill command targeting closest hostile (like TamerSuite)."""
    try:
        # Find closest hostile
        enemy = find_closest_hostile()

        if not enemy:
            API.SysMsg("No hostile found nearby", 43)
            return False

        # Say all kill
        API.Msg("all kill")
        API.Pause(0.3)

        # Wait for target cursor and target the enemy
        if API.WaitForTarget(timeout=2.0):
            API.Target(enemy.Serial)
            API.Attack(enemy.Serial)
            API.HeadMsg("KILL!", enemy.Serial, 32)
            API.SysMsg("All kill: targeting hostile at " + str(enemy.Distance) + " tiles", 68)
            return True
        else:
            API.SysMsg("No target cursor", 32)
            return False
    except Exception as e:
        API.SysMsg("All kill error: " + str(e), 32)
        return False

def all_kill():
    """Send All Kill command - uses all_kill_closest()."""
    return all_kill_closest()

def all_guard_me():
    """Send All Guard Me command."""
    try:
        API.Say("all guard me")
        API.Pause(0.5)
        return True
    except:
        return False

def all_follow_me():
    """Send All Follow Me command."""
    try:
        API.Say("all follow me")
        API.Pause(0.5)
        return True
    except:
        return False

def find_backpack_bandages():
    """Find bandages in backpack (including sub-containers).

    Since bandages can be used from sub-containers, search recursively.
    """
    return find_all_bandages_recursive()

def find_main_backpack_bandages_only():
    """Find bandages ONLY in main backpack (not sub-containers).

    Used for storage - only store newly made bandages from main backpack.
    """
    backpack = API.Player.Backpack
    if not backpack:
        return None

    # Search only main backpack, not recursively
    API.FindType(BANDAGE_GRAPHIC, backpack.Serial)
    if API.Found:
        return API.Found
    return None

def find_all_bandages_recursive():
    """Find bandages in ALL containers (main backpack + sub-containers).

    Uses FindTypeAll without container parameter to search recursively.
    """
    try:
        # FindTypeAll without container searches all containers recursively
        items = API.FindTypeAll(BANDAGE_GRAPHIC)
        if items and len(items) > 0:
            return items[0]  # Return first bandage found
    except:
        pass

    return None

def use_bandage_on_self():
    """Use bandage on self."""
    global fullauto_last_bandage_time

    # Check cooldown (10s between bandages)
    if time.time() < fullauto_last_bandage_time + 10.0:
        return False

    bandage = find_backpack_bandages()
    if not bandage:
        return False

    try:
        # Get bandage serial
        if hasattr(bandage, 'Serial'):
            bandage_serial = bandage.Serial
        else:
            bandage_serial = bandage

        # Use bandage on self
        API.UseObject(bandage_serial, False)
        API.Pause(0.3)

        # Wait for target cursor
        wait_start = time.time()
        while time.time() < wait_start + 2.0:
            if API.HasTarget():
                API.Target(API.Player.Serial)
                fullauto_last_bandage_time = time.time()
                return True
            API.Pause(0.1)

        return False
    except:
        return False

def get_player_pets():
    """Get list of player's pets (followers) from shared pet storage.

    Reads from SharedPets_List persistence (same as Tamer Suite).
    Format: name:serial:active|name:serial:active|...
    """
    pets = []
    try:
        # Read shared pet list from persistence (same key as Tamer Suite)
        shared_pets_str = API.GetPersistentVar("SharedPets_List", "", API.PersistentVar.Char)

        if not shared_pets_str:
            return []

        # Parse pet list: name:serial:active|name:serial:active|...
        pet_entries = shared_pets_str.split('|')

        for entry in pet_entries:
            if not entry:
                continue

            parts = entry.split(':')
            if len(parts) < 2:
                continue

            pet_serial = int(parts[1]) if parts[1].isdigit() else 0
            if pet_serial == 0:
                continue

            # Get the mobile (correct API is API.FindMobile, not API.Mobiles.FindMobile)
            mob = API.FindMobile(pet_serial)
            if mob and not mob.IsDead:
                pets.append(mob)

        return pets
    except:
        return []

def heal_pets():
    """Heal injured pets with bandages."""
    global fullauto_last_bandage_time

    # Check cooldown
    if time.time() < fullauto_last_bandage_time + 10.0:
        return False

    pets = get_player_pets()
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
    bandage = find_backpack_bandages()
    if not bandage:
        return False

    try:
        if hasattr(bandage, 'Serial'):
            bandage_serial = bandage.Serial
        else:
            bandage_serial = bandage

        pet_serial = getattr(most_injured, 'Serial', None)
        if not pet_serial:
            return False

        # Use bandage
        API.UseObject(bandage_serial, False)
        API.Pause(0.3)

        # Wait for target cursor
        wait_start = time.time()
        while time.time() < wait_start + 2.0:
            if API.HasTarget():
                API.Target(pet_serial)
                fullauto_last_bandage_time = time.time()
                API.SysMsg("Healing pet (" + str(int(lowest_hp_pct)) + "% HP)", 68)
                return True
            API.Pause(0.1)

        return False
    except:
        return False

def is_taking_damage():
    """Check if player is taking damage."""
    global fullauto_last_hp

    current_hp = API.Player.Hits

    # Initialize on first check
    if fullauto_last_hp == 0:
        fullauto_last_hp = current_hp
        return False

    # Check if HP decreased
    if current_hp < fullauto_last_hp:
        fullauto_last_hp = current_hp
        return True

    fullauto_last_hp = current_hp
    return False

def check_critical_hp():
    """Check if player or any pet is below critical HP threshold."""
    # Check player HP
    player_hp = API.Player.Hits
    player_max_hp = getattr(API.Player, 'HitsMax', 1)
    player_hp_pct = (player_hp / player_max_hp * 100) if player_max_hp > 0 else 100

    if player_hp_pct < CRITICAL_HP_THRESHOLD:
        API.SysMsg("CRITICAL: Player HP below 40%!", 32)
        return True

    # Check pet HP
    pets = get_player_pets()
    for pet in pets:
        pet_hp = getattr(pet, 'Hits', 0)
        pet_max_hp = getattr(pet, 'HitsMax', 1)
        pet_hp_pct = (pet_hp / pet_max_hp * 100) if pet_max_hp > 0 else 100

        if pet_hp_pct < CRITICAL_HP_THRESHOLD:
            API.SysMsg("CRITICAL: Pet HP below 40%!", 32)
            return True

    return False

def get_dead_pets():
    """Get list of dead pets that need resurrection from shared pet storage.

    Reads from SharedPets_List persistence (same as Tamer Suite).
    """
    dead_pets = []
    try:
        # Read shared pet list from persistence
        shared_pets_str = API.GetPersistentVar("SharedPets_List", "", API.PersistentVar.Char)

        if not shared_pets_str:
            return []

        # Parse pet list: name:serial:active|name:serial:active|...
        pet_entries = shared_pets_str.split('|')

        for entry in pet_entries:
            if not entry:
                continue

            parts = entry.split(':')
            if len(parts) < 2:
                continue

            pet_serial = int(parts[1]) if parts[1].isdigit() else 0
            if pet_serial == 0:
                continue

            # Get the mobile (correct API is API.FindMobile, not API.Mobiles.FindMobile)
            mob = API.FindMobile(pet_serial)
            if mob and mob.IsDead:
                distance = getattr(mob, 'Distance', 999)
                if distance <= 10:
                    dead_pets.append(mob)

        return dead_pets
    except:
        return []

def resurrect_pet(pet_serial):
    """Attempt to resurrect a pet using bandages."""
    global fullauto_last_bandage_time

    # Check cooldown
    if time.time() < fullauto_last_bandage_time + 10.0:
        return False

    bandage = find_backpack_bandages()
    if not bandage:
        API.SysMsg("No bandages for resurrection!", 32)
        return False

    try:
        if hasattr(bandage, 'Serial'):
            bandage_serial = bandage.Serial
        else:
            bandage_serial = bandage

        # Use bandage
        API.UseObject(bandage_serial, False)
        API.Pause(0.3)

        # Wait for target cursor
        wait_start = time.time()
        while time.time() < wait_start + 2.0:
            if API.HasTarget():
                API.Target(pet_serial)
                fullauto_last_bandage_time = time.time()
                API.SysMsg("Attempting pet resurrection...", 68)
                API.Pause(10.0)  # Wait for rez to complete
                return True
            API.Pause(0.1)

        return False
    except:
        return False

def check_if_at_home():
    """Check if player is at home by detecting wheel/loom/storage nearby."""
    # Check if wheel is nearby
    if wheel_serial:
        wheel = API.FindItem(wheel_serial)
        if wheel:
            distance = getattr(wheel, 'Distance', 999)
            if distance <= 20:  # Within 20 tiles = at home
                return True

    # Check if loom is nearby
    if loom_serial:
        loom = API.FindItem(loom_serial)
        if loom:
            distance = getattr(loom, 'Distance', 999)
            if distance <= 20:
                return True

    # Check if storage is nearby
    if storage_box_serial:
        storage = API.FindItem(storage_box_serial)
        if storage:
            distance = getattr(storage, 'Distance', 999)
            if distance <= 20:
                return True

    return False

def debug_shared_pets():
    """Debug function to check what's in SharedPets_List."""
    try:
        shared_pets_str = API.GetPersistentVar("SharedPets_List", "", API.PersistentVar.Char)

        if not shared_pets_str:
            API.SysMsg("=== DEBUG: SharedPets_List is EMPTY ===", 43)
            return

        API.SysMsg("=== DEBUG: SharedPets_List Contents ===", 68)
        API.SysMsg("Raw string: " + shared_pets_str, 68)

        pet_entries = shared_pets_str.split('|')
        API.SysMsg("Found " + str(len(pet_entries)) + " entries", 68)

        for i, entry in enumerate(pet_entries):
            if entry:
                parts = entry.split(':')
                if len(parts) >= 2:
                    name = parts[0]
                    serial = parts[1]
                    active = parts[2] if len(parts) >= 3 else "unknown"
                    API.SysMsg("Pet " + str(i+1) + ": " + name + " (Serial: " + serial + ", Active: " + active + ")", 68)

                    # Try to find the mobile
                    try:
                        pet_serial = int(serial)
                        API.SysMsg("  Trying to find serial: " + str(pet_serial), 68)
                        mob = API.FindMobile(pet_serial)
                        if mob:
                            is_dead = "DEAD" if mob.IsDead else "ALIVE"
                            distance = getattr(mob, 'Distance', 999)
                            API.SysMsg("  Status: " + is_dead + ", Distance: " + str(distance), 68)
                        else:
                            API.SysMsg("  Status: NOT FOUND (mobile not loaded)", 43)
                    except Exception as e:
                        API.SysMsg("  Status: ERROR - " + str(e), 32)
    except Exception as e:
        API.SysMsg("=== DEBUG ERROR: " + str(e) + " ===", 32)

def count_expected_pets():
    """Count how many pets are registered in SharedPets_List."""
    try:
        shared_pets_str = API.GetPersistentVar("SharedPets_List", "", API.PersistentVar.Char)
        if not shared_pets_str:
            return 0

        pet_entries = shared_pets_str.split('|')
        count = 0
        for entry in pet_entries:
            if entry and ':' in entry:
                count += 1
        return count
    except:
        return 0

def count_present_pets():
    """Count how many pets are currently present (not dead, within range)."""
    pets = get_player_pets()
    return len(pets) if pets else 0

def summon_pets():
    """Summon pets using context menu (hardcoded serial)."""
    try:
        API.SysMsg("Summoning pets...", 68)

        # Use context menu option 7 to summon pets (hardcoded serial from user)
        API.ContextMenu(0x000304AE, 7)

        # Wait 10 seconds for pets to arrive
        API.Pause(10.0)

        API.SysMsg("Pets summoned", 68)
        return True
    except Exception as e:
        API.SysMsg("Error summoning pets: " + str(e), 32)
        return False

def check_and_summon_missing_pets():
    """Check if any pets are missing and summon them if needed."""
    expected_count = count_expected_pets()
    present_count = count_present_pets()

    if expected_count == 0:
        # No pets registered
        return True

    if present_count < expected_count:
        API.SysMsg("Missing pets! ({}/{}) - Summoning...".format(present_count, expected_count), 43)
        return summon_pets()

    return True

def preflight_check():
    """Check if ready to farm: bandages, pets alive, everyone healthy.

    Returns: "ok", "no_bandages", "dead_pets", "needs_healing"
    """
    # Check bandages (search ALL containers including sub-containers)
    if not find_all_bandages_recursive():
        API.SysMsg("=== PREFLIGHT FAILED: NO BANDAGES ===", 32)
        return "no_bandages"

    # Check for dead pets
    dead_pets = get_dead_pets()
    if dead_pets and len(dead_pets) > 0:
        API.SysMsg("=== PREFLIGHT FAILED: DEAD PETS - REZ FIRST ===", 32)
        return "dead_pets"

    # Check pet health
    pets = get_player_pets()
    if not pets or len(pets) == 0:
        API.SysMsg("=== PREFLIGHT WARNING: NO PETS DETECTED ===", 43)
        API.SysMsg("Run Tamer Suite first to register pets in SharedPets_List", 43)
        # Continue anyway - maybe pets are out of range or user doesn't have pets

    needs_healing = False
    for pet in pets:
        pet_hp = getattr(pet, 'Hits', 0)
        pet_max_hp = getattr(pet, 'HitsMax', 1)
        pet_hp_pct = (pet_hp / pet_max_hp * 100) if pet_max_hp > 0 else 100

        if pet_hp_pct < 80:
            API.SysMsg("=== PREFLIGHT: PET INJURED ({}%) - HEALING ===".format(int(pet_hp_pct)), 43)
            needs_healing = True

    # Check player health
    player_hp = API.Player.Hits
    player_max_hp = getattr(API.Player, 'HitsMax', 1)
    player_hp_pct = (player_hp / player_max_hp * 100) if player_max_hp > 0 else 100

    if player_hp_pct < 80:
        API.SysMsg("=== PREFLIGHT: PLAYER INJURED ({}%) - HEALING ===".format(int(player_hp_pct)), 43)
        needs_healing = True

    if needs_healing:
        return "needs_healing"

    API.SysMsg("Preflight check passed - ready to farm!", 68)
    return "ok"

# ============ RECALL FUNCTIONS ============
def recall_to_slot(slot_number):
    """Recall to specified runebook slot with position verification."""
    if runebook_serial is None or runebook_serial == 0:
        API.SysMsg("No runebook configured!", 32)
        return False

    runebook = API.FindItem(runebook_serial)
    if not runebook:
        API.SysMsg("Runebook not found!", 32)
        return False

    # Check if player has enough mana to recall (11 mana required)
    # Wait for mana to regenerate if needed (don't fail recall due to low mana)
    mana_wait_start = time.time()
    mana_wait_timeout = 60.0  # Max 60 seconds to wait for mana

    while True:
        player_mana = getattr(API.Player, 'Mana', 0)

        if player_mana >= 11:
            # Have enough mana
            break

        # Check timeout
        if time.time() > mana_wait_start + mana_wait_timeout:
            API.SysMsg("Timeout waiting for mana - Cannot recall", 32)
            return False

        # Show status
        API.SysMsg("Waiting for mana to regen: {}/11".format(player_mana), 43)

        # Wait a bit and check again (mana regens ~1-2 per second)
        API.Pause(2.0)
        API.ProcessCallbacks()  # Keep hotkeys responsive

    try:
        # Clear journal before attempting recall
        API.ClearJournal()

        # Save position before recall to check if it worked
        pos_before_x = getattr(API.Player, 'X', 0)
        pos_before_y = getattr(API.Player, 'Y', 0)

        API.SysMsg("Recalling to slot " + str(slot_number) + "...", 43)
        API.UseObject(runebook_serial)
        API.Pause(USE_OBJECT_DELAY)

        if not API.WaitForGump(delay=GUMP_WAIT_TIME):
            API.SysMsg("Runebook gump didn't open!", 32)
            return False

        API.Pause(GUMP_READY_DELAY)

        button_id = slot_to_button(slot_number)
        result = API.ReplyGump(button_id)

        if result:
            # Wait longer for recall to complete (UO can be slow)
            API.Pause(RECALL_DELAY + 2.5)  # Total of ~4.5 seconds

            # Check if position changed
            pos_after_x = getattr(API.Player, 'X', 0)
            pos_after_y = getattr(API.Player, 'Y', 0)

            position_changed = (pos_before_x != pos_after_x or pos_before_y != pos_after_y)
            out_of_regs = check_out_of_reagents()

            if position_changed:
                # Position changed - recall succeeded!
                API.SysMsg("Recall successful!", 68)
                API.Pause(1.0)
                return True
            elif out_of_regs:
                # Out of reagents - try emergency charges
                API.SysMsg("OUT OF REAGENTS - Trying emergency charges...", 43)
                API.Pause(0.5)
                return emergency_recall_to_slot(slot_number)
            else:
                # Position didn't change - wait longer and check again
                API.Pause(2.0)
                pos_check_x = getattr(API.Player, 'X', 0)
                pos_check_y = getattr(API.Player, 'Y', 0)

                if pos_before_x != pos_check_x or pos_before_y != pos_check_y:
                    # Position changed on second check - recall worked!
                    API.SysMsg("Recall successful!", 68)
                    return True
                else:
                    # Still no position change - assume it failed
                    API.SysMsg("Recall failed (no position change)", 32)
                    return False
        else:
            API.SysMsg("Failed to click recall button!", 32)
            return False

    except Exception as e:
        API.SysMsg("Recall error: " + str(e), 32)
        return False

def emergency_recall_to_slot(slot_number):
    """Use runebook emergency charges when out of reagents."""
    if runebook_serial is None or runebook_serial == 0:
        API.SysMsg("No runebook configured!", 32)
        return False

    runebook = API.FindItem(runebook_serial)
    if not runebook:
        API.SysMsg("Runebook not found!", 32)
        return False

    try:
        # Clear journal to check for new messages
        API.ClearJournal()

        # Save position before recall to check if it worked
        pos_before_x = getattr(API.Player, 'X', 0)
        pos_before_y = getattr(API.Player, 'Y', 0)

        API.SysMsg("=== USING EMERGENCY RUNEBOOK CHARGE! ===", 32)

        API.UseObject(runebook_serial)

        # Wait for runebook gump
        while not API.HasGump(RUNEBOOK_GUMP_ID):
            API.Pause(0.1)

        API.Pause(2.70)

        # Click emergency recall button (button 10)
        result = API.ReplyGump(EMERGENCY_RECALL_BUTTON, RUNEBOOK_GUMP_ID)

        if result:
            API.Pause(0.5)

            # Target the slot button
            if API.HasGump(RUNEBOOK_GUMP_ID):
                slot_button = slot_to_button(slot_number)
                API.ReplyGump(slot_button, RUNEBOOK_GUMP_ID)

            API.Pause(RECALL_DELAY + 2.5)

            # Check if we actually moved
            pos_after_x = getattr(API.Player, 'X', 0)
            pos_after_y = getattr(API.Player, 'Y', 0)

            if pos_before_x != pos_after_x or pos_before_y != pos_after_y:
                # Emergency recall succeeded!
                API.SysMsg("=== EMERGENCY RECALL SUCCESSFUL! ===", 43)
                API.Pause(1.0)
                return True
            else:
                # Emergency recall failed (no charges?)
                API.SysMsg("=== EMERGENCY RECALL FAILED! ===", 32)
                API.SysMsg("=== NO CHARGES LEFT IN RUNEBOOK! ===", 32)
                return False
        else:
            API.SysMsg("Failed to click emergency recall button!", 32)
            return False

    except Exception as e:
        API.SysMsg("Emergency recall error: " + str(e), 32)
        return False

def recall_home():
    """Recall to home location (slot 1)."""
    global at_home
    if recall_to_slot(1):
        at_home = True
        return True
    return False

def recall_to_farm():
    """Recall to current farm spot (slots 2+)."""
    global at_home, current_farm_index

    if num_farm_spots < 1:
        API.SysMsg("No farm spots configured!", 32)
        return False

    # Calculate slot number: farm 0 = slot 2, farm 1 = slot 3, etc.
    farm_slot = 2 + current_farm_index

    API.SysMsg("Recalling to farm " + str(current_farm_index + 1) + "/" + str(num_farm_spots) + "...", 68)

    if recall_to_slot(farm_slot):
        at_home = False
        # Rotate to next farm for next cycle
        current_farm_index = (current_farm_index + 1) % num_farm_spots
        save_persistent_var("CurrentFarmIndex", str(current_farm_index))
        return True

    return False

# ============ PATHFINDING FUNCTIONS ============
def pathfind_to_wheel():
    """Pathfind to spinning wheel location."""
    if not wheel_serial or wheel_x == 0 or wheel_y == 0:
        API.SysMsg("Wheel location not configured!", 32)
        return False

    # Check if already at wheel
    wheel = API.FindItem(wheel_serial)
    if wheel and wheel.Distance <= 2:
        return True

    # Start pathfinding
    API.Pathfind(wheel_x, wheel_y)

    # Wait for arrival (up to 30 seconds)
    timeout = time.time() + 30.0
    while time.time() < timeout:
        API.ProcessCallbacks()

        if not API.Pathfinding():
            # Pathfinding stopped - check if we arrived
            wheel = API.FindItem(wheel_serial)
            if wheel and wheel.Distance <= 2:
                return True
            else:
                # Pathfinding stopped but not at target
                API.SysMsg("Pathfinding to wheel stopped early", 43)
                return False

        API.Pause(0.1)

    # Timeout
    API.SysMsg("Pathfinding to wheel timed out!", 32)
    if API.Pathfinding():
        API.CancelPathfinding()
    return False

def pathfind_to_loom():
    """Pathfind to loom location."""
    if not loom_serial or loom_x == 0 or loom_y == 0:
        API.SysMsg("Loom location not configured!", 32)
        return False

    # Check if already at loom
    loom = API.FindItem(loom_serial)
    if loom and loom.Distance <= 2:
        return True

    # Start pathfinding
    API.Pathfind(loom_x, loom_y)

    # Wait for arrival (up to 30 seconds)
    timeout = time.time() + 30.0
    while time.time() < timeout:
        API.ProcessCallbacks()

        if not API.Pathfinding():
            # Pathfinding stopped - check if we arrived
            loom = API.FindItem(loom_serial)
            if loom and loom.Distance <= 2:
                return True
            else:
                # Pathfinding stopped but not at target
                API.SysMsg("Pathfinding to loom stopped early", 43)
                return False

        API.Pause(0.1)

    # Timeout
    API.SysMsg("Pathfinding to loom timed out!", 32)
    if API.Pathfinding():
        API.CancelPathfinding()
    return False

def pathfind_to_storage_bin():
    """Pathfind to storage bin location."""
    if not storage_box_serial:
        API.SysMsg("Storage bin not configured!", 32)
        return False

    # Check if already at storage
    storage_box = API.FindItem(storage_box_serial)
    if storage_box and storage_box.Distance <= 2:
        return True

    # Use entity-based pathfinding if we have coordinates
    if storage_x > 0 and storage_y > 0:
        API.Pathfind(storage_x, storage_y)
    else:
        # Fallback to item-based pathfinding
        API.SysMsg("No storage position saved - using item location", 43)
        if not storage_box:
            API.SysMsg("Storage bin not found!", 32)
            return False

    # Wait for arrival (up to 30 seconds)
    timeout = time.time() + 30.0
    while time.time() < timeout:
        API.ProcessCallbacks()

        if not API.Pathfinding():
            # Pathfinding stopped - check if we arrived
            storage_box = API.FindItem(storage_box_serial)
            if storage_box and storage_box.Distance <= 2:
                return True
            else:
                # Pathfinding stopped but not at target
                API.SysMsg("Pathfinding to storage stopped early", 43)
                return False

        API.Pause(0.1)

    # Timeout
    API.SysMsg("Pathfinding to storage timed out!", 32)
    if API.Pathfinding():
        API.CancelPathfinding()
    return False

# ============ PICKER LOGIC ============
def is_on_cooldown(plant_serial):
    """Check if plant is on cooldown."""
    if plant_serial not in last_clicked:
        return False
    elapsed = time.time() - last_clicked[plant_serial]
    return elapsed < PLANT_COOLDOWN

def prune_cooldown_dict():
    """Prune old entries from last_clicked to prevent memory leak."""
    global last_clicked
    if len(last_clicked) > MAX_COOLDOWN_ENTRIES:
        # Remove entries older than cooldown period
        current_time = time.time()
        last_clicked = {
            serial: timestamp
            for serial, timestamp in last_clicked.items()
            if current_time - timestamp < PLANT_COOLDOWN
        }

def highlight_plant(item):
    """Highlight plant (visual feedback)."""
    try:
        # Legion doesn't have direct color override, skip highlighting
        pass
    except:
        pass

def loot_ground_cotton():
    """Pick up cotton bales from ground by moving to backpack. Returns amount collected."""
    global stats
    collected_any = False

    # Get backpack
    backpack = API.Player.Backpack
    if not backpack:
        return 0

    # Try to find and pick up ground cotton multiple times
    for _ in range(3):
        bales = find_ground_cotton()
        if not bales:
            break

        for bale in bales:
            if not bale:
                continue

            try:
                # Move to backpack (not UseObject!)
                API.MoveItem(bale.Serial, backpack.Serial, 0)
                API.Pause(0.6)
                collected_any = True
                stats["ground_cotton_collected"] += 1
            except:
                pass

    return 1 if collected_any else 0

def start_picking_plant(plant_serial):
    """Start picking action on a plant."""
    global STATE, action_start_time, action_duration, current_target_serial, last_clicked

    # Double-click plant
    API.DoubleClick(plant_serial)

    # Mark as clicked
    last_clicked[plant_serial] = time.time()
    current_target_serial = plant_serial

    # Set state
    STATE = "picking"
    action_start_time = time.time()
    action_duration = CLICK_DELAY

    debug_msg("Started picking plant " + str(plant_serial))

    # Prune cooldown dict periodically
    prune_cooldown_dict()

def picker_logic():
    """Main picker state machine."""
    global STATE, action_start_time, last_plant_count, stats

    if paused or ui_closed:
        STATE = "idle"
        return

    if STATE == "idle":
        # Find plants
        plants = find_cotton_plants()

        # Update plant count message
        if len(plants) != last_plant_count:
            if plants:
                API.SysMsg("Found " + str(len(plants)) + " cotton plants", 55)
            else:
                API.SysMsg("No cotton nearby", 33)
            last_plant_count = len(plants)

        # Find pickable plant
        px, py = get_player_pos()
        for plant in plants:
            if not plant:
                continue

            # Highlight
            highlight_plant(plant)

            # Check cooldown
            if is_on_cooldown(plant.Serial):
                continue

            # Check reach (Manhattan distance)
            plant_x = getattr(plant, 'X', px)
            plant_y = getattr(plant, 'Y', py)
            dist = manhattan_distance(px, py, plant_x, plant_y)

            if dist <= PICK_REACH:
                # Verify plant still exists before picking
                plant_check = API.FindItem(plant.Serial)
                if plant_check:
                    start_picking_plant(plant.Serial)
                return

        # No plants in reach, idle
        API.Pause(0.2)

    elif STATE == "picking":
        # Wait for pick action to complete
        if time.time() > action_start_time + action_duration:
            # Pick complete, now loot
            STATE = "looting"
            action_start_time = time.time()
            action_duration = 0.1  # Quick check

    elif STATE == "looting":
        # Loot ground cotton
        if time.time() > action_start_time + action_duration:
            collected = loot_ground_cotton()
            # Only count pick if we actually collected cotton
            if collected > 0:
                stats["cotton_picked"] += 1
            STATE = "idle"

# ============ WEAVER LOGIC ============
def request_wheel_target_blocking():
    """Request wheel target from player (blocking - only call from button callback)."""
    global wheel_serial, wheel_x, wheel_y

    API.SysMsg("Target your SPINNING WHEEL", 55)
    wheel_serial = API.RequestTarget(15)

    # Clean up cursor on timeout
    if not wheel_serial:
        if API.HasTarget():
            API.CancelTarget()
        API.CancelPreTarget()
        API.SysMsg("Wheel target cancelled", 33)
    else:
        # Get wheel position
        wheel = API.FindItem(wheel_serial)
        if wheel:
            wheel_x = getattr(wheel, 'X', 0)
            wheel_y = getattr(wheel, 'Y', 0)
            save_persistent_var("WheelSerial", str(wheel_serial))
            save_persistent_var("WheelX", str(wheel_x))
            save_persistent_var("WheelY", str(wheel_y))
            API.SysMsg("Wheel saved at ({}, {})!".format(wheel_x, wheel_y), 68)
        else:
            save_persistent_var("WheelSerial", str(wheel_serial))
            API.SysMsg("Wheel saved!", 68)

def request_loom_target_blocking():
    """Request loom target from player (blocking - only call from button callback)."""
    global loom_serial, loom_x, loom_y

    API.SysMsg("Target your LOOM", 55)
    loom_serial = API.RequestTarget(15)

    # Clean up cursor on timeout
    if not loom_serial:
        if API.HasTarget():
            API.CancelTarget()
        API.CancelPreTarget()
        API.SysMsg("Loom target cancelled", 33)
    else:
        # Get loom position
        loom = API.FindItem(loom_serial)
        if loom:
            loom_x = getattr(loom, 'X', 0)
            loom_y = getattr(loom, 'Y', 0)
            save_persistent_var("LoomSerial", str(loom_serial))
            save_persistent_var("LoomX", str(loom_x))
            save_persistent_var("LoomY", str(loom_y))
            API.SysMsg("Loom saved at ({}, {})!".format(loom_x, loom_y), 68)
        else:
            save_persistent_var("LoomSerial", str(loom_serial))
            API.SysMsg("Loom saved!", 68)

def start_spinning():
    """Start spinning cotton into spool."""
    global weaver_state, weaver_start_time, weaver_duration

    if not wheel_serial:
        API.SysMsg("No wheel set - use [Reset Wheel] button", 33)
        return False

    cotton = find_backpack_cotton()
    if not cotton:
        return False

    # Get serial - handle both object and direct serial
    if hasattr(cotton, 'Serial'):
        cotton_serial = cotton.Serial
    else:
        cotton_serial = cotton

    # Clear any existing targets
    if API.HasTarget():
        API.CancelTarget()
    API.CancelPreTarget()

    # Clear journal before action
    API.ClearJournal()

    # Use cotton bale - this generates a target cursor
    API.UseObject(cotton_serial, False)
    API.Pause(0.3)

    # Wait for target cursor and journal message
    wait_start = time.time()
    target_appeared = False
    while time.time() < wait_start + TARGET_TIMEOUT:
        API.ProcessCallbacks()

        # Check for target cursor prompt in journal
        if API.InJournal("What spinning wheel do you wish to spin this on"):
            target_appeared = True
            break

        if API.HasTarget():
            target_appeared = True
            break

        API.Pause(0.05)

    if not target_appeared:
        return False

    # Click the wheel with the active cursor
    API.Target(wheel_serial)
    API.Pause(0.2)

    # Check if wheel is busy
    if API.InJournal("That spinning wheel is being used"):
        API.SysMsg("Wheel busy, retrying...", 43)
        API.Pause(1.0)
        return False

    # Set state - spinning takes ~6 seconds
    weaver_state = "spinning"
    weaver_start_time = time.time()
    weaver_duration = SPIN_DELAY

    return True

def start_weaving():
    """Start weaving spool into cloth."""
    global weaver_state, weaver_start_time, weaver_duration

    if not loom_serial:
        API.SysMsg("No loom set - use [Reset Loom] button", 33)
        return False

    spool = find_backpack_spool()
    if not spool:
        return False

    # Get serial - handle both object and direct serial
    if hasattr(spool, 'Serial'):
        spool_serial = spool.Serial
    else:
        spool_serial = spool

    # Clear any existing targets
    if API.HasTarget():
        API.CancelTarget()
    API.CancelPreTarget()

    # Clear journal before action
    API.ClearJournal()

    # Use spool - this generates a target cursor
    API.UseObject(spool_serial, False)
    API.Pause(0.3)

    # Wait for target cursor to appear
    wait_start = time.time()
    target_appeared = False
    while time.time() < wait_start + TARGET_TIMEOUT:
        API.ProcessCallbacks()

        if API.HasTarget():
            target_appeared = True
            break

        API.Pause(0.05)

    if not target_appeared:
        return False

    # Click the loom with the active cursor
    API.Target(loom_serial)
    API.Pause(0.2)

    # Check if loom is busy
    if API.InJournal("That loom is being used"):
        API.SysMsg("Loom busy, retrying...", 43)
        API.Pause(1.0)
        return False

    # Set state
    weaver_state = "weaving"
    weaver_start_time = time.time()
    weaver_duration = WEAVE_DELAY

    return True

def weaver_logic():
    """Main weaver state machine."""
    global weaver_state, stats

    if paused or ui_closed:
        weaver_state = "idle"
        return

    if weaver_state == "idle":
        # Priority: spin cotton first, then weave spools
        cotton = find_backpack_cotton()

        if cotton:
            # Spin cotton - count on start (action begins immediately)
            if start_spinning():
                return

        # Check for spools to weave
        spool_count = count_spools()
        if spool_count > 0:
            # Weave spool - count on start (action begins immediately)
            if start_weaving():
                return

        # Nothing to do
        API.Pause(0.2)

    elif weaver_state == "spinning":
        # Check for completion message or timeout
        if API.InJournal("You put the spools of thread in your backpack"):
            stats["spools_made"] += 1
            weaver_state = "idle"
        elif time.time() > weaver_start_time + weaver_duration:
            # Timeout - assume completed
            spool_count_after = count_spools()
            if spool_count_after > 0:
                stats["spools_made"] += 1
            weaver_state = "idle"

    elif weaver_state == "weaving":
        # Check for completion message or timeout
        if API.InJournal("You create some cloth"):
            stats["bolts_created"] += 1
            weaver_state = "idle"
        elif time.time() > weaver_start_time + weaver_duration:
            # Timeout - assume completed
            stats["bolts_created"] += 1
            weaver_state = "idle"

# ============ AUTOPICK LOGIC ============
# AutoPick state machine - simplified approach
autopick_state = "scanning"  # scanning, moving, picking, waiting_for_loot, looting, recalling_home, at_home, recalling_to_farm
autopick_target_serial = None
autopick_target_graphic = None  # Store the graphic ID user targets
autopick_start_time = 0
autopick_move_timeout = 10.0  # Timeout for moving to plant

def autopick_logic():
    """AutoPick mode - automated pathfinding and picking with user-targeted graphic."""
    global autopick_state, autopick_target_serial, autopick_target_graphic, autopick_start_time, stats
    global no_plants_start_time, at_home

    if paused or ui_closed:
        autopick_state = "scanning"
        if API.Pathfinding():
            API.CancelPathfinding()
        return

    # If no target graphic set, wait (shouldn't happen if button callback worked)
    if not autopick_target_graphic:
        API.Pause(0.5)
        return

    px, py = get_player_pos()

    if autopick_state == "scanning":
        # Find nearest plant of target graphic using GetItemsOnGround
        try:
            plants = API.GetItemsOnGround(SCAN_RANGE, autopick_target_graphic)
        except:
            plants = None

        if plants and len(plants) > 0:
            # Reset no plants timer
            no_plants_start_time = 0

            # Find nearest plant not on cooldown
            nearest_plant = None
            nearest_distance = 999

            for plant in plants:
                if not plant:
                    continue

                plant_serial = getattr(plant, 'Serial', None)
                if not plant_serial:
                    continue

                # Check if on cooldown
                if is_on_cooldown(plant_serial):
                    continue

                # Check distance
                distance = getattr(plant, 'Distance', 999)
                if distance < nearest_distance:
                    nearest_plant = plant
                    nearest_distance = distance

            if nearest_plant:
                plant_serial = nearest_plant.Serial
                distance = getattr(nearest_plant, 'Distance', 999)

                # Check if in reach
                if distance <= PICK_REACH:
                    # In reach - pick immediately
                    debug_msg("Plant in reach - picking")
                    autopick_state = "picking"
                    autopick_target_serial = plant_serial
                    autopick_start_time = time.time()
                else:
                    # Pathfind to it
                    plant_x = getattr(nearest_plant, 'X', 0)
                    plant_y = getattr(nearest_plant, 'Y', 0)

                    debug_msg("Pathfinding to plant at distance " + str(distance))

                    # Cancel existing pathfinding
                    if API.Pathfinding():
                        API.CancelPathfinding()

                    # Start pathfinding to plant coordinates
                    API.Pathfind(plant_x, plant_y)
                    autopick_state = "moving"
                    autopick_target_serial = plant_serial
                    autopick_start_time = time.time()
            else:
                # All plants on cooldown
                debug_msg("All plants on cooldown")
                API.Pause(0.5)
        else:
            # No plants found - check if we should rotate to next farm
            debug_msg("No plants found of graphic 0x{:04X}".format(autopick_target_graphic))

            # Start timer if not already started
            if no_plants_start_time == 0:
                no_plants_start_time = time.time()

            # Check if timeout exceeded and we have farm rotation configured
            if num_farm_spots > 1 and not at_home:
                elapsed = time.time() - no_plants_start_time
                if elapsed >= NO_PLANTS_TIMEOUT:
                    API.SysMsg("No plants for " + str(int(NO_PLANTS_TIMEOUT)) + "s - rotating to next farm", 43)
                    no_plants_start_time = 0
                    autopick_state = "recalling_to_farm"
                    return

            API.Pause(0.5)

    elif autopick_state == "moving":
        # Wait until in reach or timeout
        plant = API.FindItem(autopick_target_serial)

        if not plant:
            # Plant disappeared
            debug_msg("Target plant disappeared")
            if API.Pathfinding():
                API.CancelPathfinding()
            autopick_state = "scanning"
            return

        distance = getattr(plant, 'Distance', 999)
        if distance <= PICK_REACH:
            # Reached plant
            debug_msg("Reached plant")
            if API.Pathfinding():
                API.CancelPathfinding()
            autopick_state = "picking"
            autopick_start_time = time.time()
        elif time.time() > autopick_start_time + autopick_move_timeout:
            # Timeout - mark as on cooldown and try next plant
            debug_msg("Move timeout")
            if API.Pathfinding():
                API.CancelPathfinding()
            last_clicked[autopick_target_serial] = time.time()
            autopick_state = "scanning"

    elif autopick_state == "picking":
        # Double-click plant to pick
        plant = API.FindItem(autopick_target_serial)
        if plant:
            distance = getattr(plant, 'Distance', 999)
            if distance <= PICK_REACH:
                API.UseObject(autopick_target_serial, False)
                last_clicked[autopick_target_serial] = time.time()

                debug_msg("Picking plant")

                autopick_state = "waiting_for_loot"
                autopick_start_time = time.time()
            else:
                # Out of reach
                autopick_state = "scanning"
        else:
            # Plant moved or disappeared
            autopick_state = "scanning"

    elif autopick_state == "waiting_for_loot":
        # Wait 2 seconds for cotton to drop to ground
        if time.time() > autopick_start_time + 2.0:
            autopick_state = "looting"

    elif autopick_state == "looting":
        # Find and pickup ground cotton using GetItemsOnGround
        collected_any = False
        distant_bales = []

        # Get backpack
        backpack = API.Player.Backpack
        if not backpack:
            API.SysMsg("ERROR: No backpack!", 33)
            autopick_state = "scanning"
            return

        # Search FULL scan range (20 tiles) for any cotton bales
        try:
            bales = API.GetItemsOnGround(SCAN_RANGE, COTTON_BALE_GRAPHIC)
            if bales and len(bales) > 0:
                debug_msg("Found " + str(len(bales)) + " cotton bales in area")

                # Separate into reachable and distant bales
                for bale in bales:
                    if bale:
                        bale_serial = getattr(bale, 'Serial', None)
                        distance = getattr(bale, 'Distance', 999)

                        if bale_serial:
                            if distance <= 2:
                                # Pick up immediately if within 2 tiles
                                try:
                                    API.MoveItem(bale_serial, backpack.Serial, 0)
                                    API.Pause(0.6)
                                    collected_any = True
                                    debug_msg("Picked up cotton at distance " + str(distance))
                                except Exception as e:
                                    debug_msg("Error moving item: " + str(e))
                            else:
                                # Save distant bales for pathfinding
                                distant_bales.append((bale, distance))

                # If there are distant bales, pathfind to nearest one
                if distant_bales:
                    # Sort by distance
                    distant_bales.sort(key=lambda x: x[1])
                    nearest_bale, nearest_dist = distant_bales[0]

                    API.SysMsg("Moving to cotton bale at distance " + str(nearest_dist), 68)

                    # Get position and pathfind to it
                    bale_x = getattr(nearest_bale, 'X', 0)
                    bale_y = getattr(nearest_bale, 'Y', 0)

                    if API.Pathfinding():
                        API.CancelPathfinding()

                    API.Pathfind(bale_x, bale_y)

                    # Stay in looting state, will check again next loop
                    autopick_start_time = time.time()  # Reset timer
                    return

            else:
                debug_msg("No cotton bales found in scan range")
        except Exception as e:
            API.SysMsg("Error looting: " + str(e), 33)

        if collected_any:
            stats["cotton_picked"] += 1
            API.SysMsg("Cotton collected! Scanning for next plant...", 68)

        # Check weight threshold after looting
        if check_weight_threshold() and not at_home and runebook_serial:
            API.SysMsg("Weight threshold reached - recalling home!", 43)
            autopick_state = "recalling_home"
            return

        # Return to scanning for next plant
        autopick_state = "scanning"
        autopick_target_serial = None
        debug_msg("Returned to scanning state, target_graphic = 0x{:04X}".format(autopick_target_graphic))

        # Prune cooldown dict periodically
        prune_cooldown_dict()

    elif autopick_state == "recalling_home":
        # Call pets to follow before recalling
        all_follow_me()
        API.Pause(1.0)

        # Recall to home
        if recall_home():
            autopick_state = "at_home"
            API.SysMsg("At home - ready to unload cotton", 68)
        else:
            API.SysMsg("Recall home failed - stopping AutoPick", 32)
            autopick_state = "scanning"

    elif autopick_state == "at_home":
        # Wait for player to unload cotton manually
        # Check if weight is back below threshold
        if not check_weight_threshold():
            API.SysMsg("Weight below threshold - returning to farm", 68)
            autopick_state = "recalling_to_farm"
        else:
            # Still heavy - wait
            API.Pause(1.0)

    elif autopick_state == "recalling_to_farm":
        # Call pets to follow before recalling
        all_follow_me()
        API.Pause(1.0)

        # Recall to farm spot
        if recall_to_farm():
            autopick_state = "scanning"
            no_plants_start_time = 0  # Reset no plants timer
            API.SysMsg("Back at farm - resuming picking", 68)
        else:
            API.SysMsg("Recall to farm failed - stopping AutoPick", 32)
            autopick_state = "scanning"

# ============ FULL AUTOMATION LOGIC ============
fullauto_state = "checking_inventory"
fullauto_start_time = 0
fullauto_timeout = 60.0
fullauto_target_graphic = None
fullauto_respawn_wait_start = 0  # Track when we started waiting for respawns

# Combat state
fullauto_recall_spot_x = 0
fullauto_recall_spot_y = 0
fullauto_last_hp = 0
fullauto_last_bandage_time = 0
fullauto_current_enemy_serial = None  # Track current enemy to avoid re-targeting
fullauto_last_guard_time = 0  # Track last guard command to avoid spam
fullauto_last_kill_time = 0  # Track last kill command to avoid spam
fullauto_enemies_killed = 0
fullauto_empty_farms_count = 0  # Track how many farms we've checked without finding plants

def fullauto_logic():
    """Full automation state machine - complete cotton farming cycle."""
    global fullauto_state, fullauto_start_time, fullauto_target_graphic, stats
    global at_home, autopick_target_serial, autopick_start_time, no_plants_start_time
    global weaver_state, weaver_start_time, weaver_duration, fullauto_respawn_wait_start
    global fullauto_recall_spot_x, fullauto_recall_spot_y, fullauto_last_hp, fullauto_enemies_killed
    global fullauto_empty_farms_count
    global fullauto_current_enemy_serial, fullauto_last_guard_time, fullauto_last_kill_time
    global paused

    if paused or ui_closed:
        fullauto_state = "checking_inventory"
        if API.Pathfinding():
            API.CancelPathfinding()
        return

    # CRITICAL: Check for bandages at the start of every cycle (search ALL containers)
    if not find_all_bandages_recursive():
        API.SysMsg("=== OUT OF BANDAGES - PAUSING FULL AUTO ===", 32)
        paused = True
        return

    # Global timeout per state (60s max)
    if fullauto_state != "checking_inventory" and fullauto_state != "waiting_for_respawn":
        if time.time() > fullauto_start_time + fullauto_timeout:
            API.SysMsg("State timeout - returning to inventory check", 43)
            fullauto_state = "checking_inventory"
            if API.Pathfinding():
                API.CancelPathfinding()
            return

    if fullauto_state == "checking_inventory":
        # Decision tree based on inventory (priority order)
        cloth_pieces = count_cloth_pieces()
        cloth_bolts = count_cloth_bolts()
        spools = count_spools()
        cotton = find_backpack_cotton()
        bandages_in_main = find_main_backpack_bandages_only()  # Only newly made bandages from main backpack

        # If we have any materials, we need to be at home to process them
        if cloth_pieces > 0 or cloth_bolts > 0 or spools > 0 or cotton or bandages_in_main:
            if not at_home:
                # Have materials but not at home -> recall home first
                API.SysMsg("Have materials - recalling home to process", 68)
                fullauto_state = "recalling_home"
                fullauto_start_time = time.time()
                return

        # Now decide what to do based on what we have (we're at home at this point)
        # Priority 1: Store bandages from main backpack (to avoid weight issues)
        # IMPORTANT: Only store newly made bandages from main backpack, NOT from loadout bag
        if bandages_in_main:
            API.SysMsg("Found newly made bandages in main backpack - going to storage", 68)
            fullauto_state = "pathfinding_to_storage"
            fullauto_start_time = time.time()
        elif cloth_pieces > 0:
            # Have cloth pieces
            if make_bandages:
                # Make bandages from cloth
                API.SysMsg("Found cloth pieces - making bandages", 68)
                fullauto_state = "making_bandages"
                fullauto_start_time = time.time()
            else:
                # Store cloth pieces
                API.SysMsg("Found cloth pieces - going to storage", 68)
                fullauto_state = "pathfinding_to_storage"
                fullauto_start_time = time.time()
        elif cloth_bolts > 0:
            # Have cloth bolts -> cut them
            API.SysMsg("Found cloth bolts - cutting...", 68)
            fullauto_state = "cutting_phase"
            fullauto_start_time = time.time()
        elif spools > 0:
            # Have spools -> weave them
            API.SysMsg("Found spools - going to loom", 68)
            fullauto_state = "pathfinding_to_loom"
            fullauto_start_time = time.time()
        elif cotton:
            # Have cotton -> spin it
            API.SysMsg("Found cotton - going to wheel", 68)
            fullauto_state = "pathfinding_to_wheel"
            fullauto_start_time = time.time()
        else:
            # Nothing in inventory - check if we're in a respawn wait period
            if fullauto_respawn_wait_start > 0:
                # Check if respawn wait is still active
                elapsed = time.time() - fullauto_respawn_wait_start
                remaining = RESPAWN_WAIT_TIME - elapsed

                if remaining > 0:
                    # Still waiting for respawn - return to waiting state
                    API.SysMsg("Materials processed - returning to respawn wait ({} min left)".format(int(remaining / 60)), 68)
                    fullauto_state = "waiting_for_respawn"
                    fullauto_start_time = time.time()
                else:
                    # Wait complete - reset timer and go to farm
                    API.SysMsg("Respawn wait complete during processing - ready to farm", 68)
                    fullauto_respawn_wait_start = 0
                    fullauto_state = "preflight_check"
                    fullauto_start_time = time.time()
            else:
                # Not waiting for respawn - normal preflight check before going to farm
                API.SysMsg("Empty inventory - running preflight check", 68)
                fullauto_state = "preflight_check"
                fullauto_start_time = time.time()

    elif fullauto_state == "preflight_check":
        # Check if ready to farm: bandages, pets alive and healthy
        result = preflight_check()

        if result == "ok":
            # Set pets to guard
            all_guard_me()
            API.Pause(0.5)

            # Ready to recall
            fullauto_state = "recalling_to_farm"
            fullauto_start_time = time.time()
        elif result == "needs_healing":
            # Injured - heal at home before going to farm
            API.SysMsg("=== PREFLIGHT: HEALING PETS/SELF AT HOME ===", 43)
            fullauto_state = "preflight_healing"
            fullauto_start_time = time.time()
        else:
            # Preflight failed (no bandages, dead pets)
            API.SysMsg("=== PREFLIGHT CHECK FAILED - PAUSING ===", 32)
            paused = True
            fullauto_state = "checking_inventory"

    elif fullauto_state == "preflight_healing":
        # Reset timeout at start of phase to prevent timeout during healing
        fullauto_start_time = time.time()

        # Heal player and pets at home before going to farm
        # Check if out of bandages
        if not find_all_bandages_recursive():
            API.SysMsg("=== OUT OF BANDAGES DURING HEALING - PAUSING ===", 32)
            paused = True
            fullauto_state = "checking_inventory"
            return

        # Heal self if injured
        player_hp = API.Player.Hits
        player_max_hp = getattr(API.Player, 'HitsMax', 1)
        player_hp_pct = (player_hp / player_max_hp * 100) if player_max_hp > 0 else 100

        if player_hp_pct < 100:
            if use_bandage_on_self():
                API.SysMsg("Healing self at home...", 68)
                API.Pause(BANDAGE_DELAY)
                return

        # Heal pets if injured
        if heal_pets():
            API.SysMsg("Healing pets at home...", 68)
            API.Pause(BANDAGE_DELAY)
            return

        # Check if everyone is healed
        all_healed = True

        # Check player
        if player_hp_pct < 95:
            all_healed = False

        # Check pets
        pets = get_player_pets()
        for pet in pets:
            pet_hp = getattr(pet, 'Hits', 0)
            pet_max_hp = getattr(pet, 'HitsMax', 1)
            pet_hp_pct = (pet_hp / pet_max_hp * 100) if pet_max_hp > 0 else 100
            if pet_hp_pct < 95:
                all_healed = False
                break

        if all_healed:
            API.SysMsg("All healed - ready to farm!", 68)
            # Set pets to guard
            all_guard_me()
            API.Pause(0.5)

            # Ready to recall
            fullauto_state = "recalling_to_farm"
            fullauto_start_time = time.time()
        else:
            # Still healing - wait a bit
            API.Pause(1.0)

    elif fullauto_state == "recalling_to_farm":
        # Call pets to follow before recalling
        all_follow_me()
        API.Pause(1.0)

        if recall_to_farm():
            # Save recall spot position and reset HP tracking
            fullauto_recall_spot_x = getattr(API.Player, 'X', 0)
            fullauto_recall_spot_y = getattr(API.Player, 'Y', 0)
            fullauto_last_hp = API.Player.Hits  # Initialize HP tracking
            fullauto_enemies_killed = 0

            # Reset respawn wait timer (we're at farm now)
            fullauto_respawn_wait_start = 0

            # Wait a moment for area to load
            API.Pause(1.0)

            # TODO: Pet summoning disabled (context menu option varies between 6 and 7)
            # Expected pets to follow since we called "all follow me" before recall

            fullauto_state = "checking_for_enemies"
            fullauto_start_time = time.time()
            no_plants_start_time = 0

            API.SysMsg("At farm - checking for enemies", 68)
        else:
            API.SysMsg("Recall to farm failed!", 32)
            API.Pause(2.0)
            fullauto_state = "checking_inventory"

    elif fullauto_state == "checking_for_enemies":
        # Check for hostile mobs before picking
        enemy = find_closest_hostile()

        if enemy:
            API.SysMsg("Enemy detected at " + str(enemy.Distance) + " tiles - attacking!", 32)

            # Call pets to guard
            all_guard_me()
            API.Pause(0.5)

            # Attack closest enemy
            all_kill_closest()
            API.Pause(0.5)

            # Flee 8-10 tiles away to let pets get aggro
            player_x = getattr(API.Player, 'X', 0)
            player_y = getattr(API.Player, 'Y', 0)
            enemy_x = getattr(enemy, 'X', player_x)
            enemy_y = getattr(enemy, 'Y', player_y)

            # Calculate direction away from enemy (multiply by 4 for ~8+ tiles distance)
            flee_x = player_x + (player_x - enemy_x) * 4
            flee_y = player_y + (player_y - enemy_y) * 4
            API.Pathfind(flee_x, flee_y)

            # Wait 4 seconds for pathfinding to move us far away
            API.Pause(4.0)

            # Cancel pathfinding if still active
            if API.Pathfinding():
                API.CancelPathfinding()

            fullauto_state = "combat_mode"
            fullauto_start_time = time.time()
        else:
            # No enemies - safe to pick
            fullauto_state = "picking_phase"
            fullauto_start_time = time.time()

    elif fullauto_state == "combat_mode":
        # CRITICAL HP CHECK - emergency recall if player or pets below 40%
        if check_critical_hp():
            API.SysMsg("=== EMERGENCY: CRITICAL HP - FLEEING ===", 32)
            fullauto_current_enemy_serial = None
            fullauto_state = "emergency_fleeing"
            fullauto_start_time = time.time()
            return

        # Check for bandages - pause if none (search ALL containers)
        if not find_all_bandages_recursive():
            API.SysMsg("=== OUT OF BANDAGES - PAUSING SCRIPT ===", 32)
            paused = True
            fullauto_current_enemy_serial = None
            fullauto_state = "checking_inventory"
            return

        # Monitor combat - check for damage and enemy status
        enemies = find_enemies()

        # Check if taking damage - call pets to guard ONLY if we haven't recently
        if is_taking_damage():
            # Only call all guard if it's been more than 10 seconds since last guard
            if time.time() > fullauto_last_guard_time + 10.0:
                API.SysMsg("Taking damage - all guard me!", 32)
                all_guard_me()
                fullauto_last_guard_time = time.time()

            # Flee to safety
            fullauto_state = "fleeing"
            fullauto_start_time = time.time()
            return

        # Heal self if injured
        current_hp = API.Player.Hits
        max_hp = getattr(API.Player, 'HitsMax', 1)
        hp_pct = (current_hp / max_hp * 100) if max_hp > 0 else 100

        if hp_pct < 80:
            use_bandage_on_self()

        # Check if all enemies dead
        if not enemies or len(enemies) == 0:
            API.SysMsg("All enemies dead - checking for dead pets", 68)

            # Call pets to guard after combat
            all_guard_me()
            API.Pause(0.5)

            fullauto_current_enemy_serial = None
            fullauto_state = "resurrecting_pets"
            fullauto_start_time = time.time()
        else:
            # Check if current enemy is still alive
            current_enemy_alive = False
            if fullauto_current_enemy_serial:
                current_enemy = API.FindMobile(fullauto_current_enemy_serial)
                if current_enemy and not current_enemy.IsDead:
                    current_enemy_alive = True

            # Only re-target if current enemy is dead or we don't have a target
            if not current_enemy_alive:
                enemy = find_closest_hostile()
                if enemy:
                    enemy_serial = getattr(enemy, 'Serial', None)
                    # Only attack if it's a different enemy or we haven't attacked recently (5s cooldown)
                    if enemy_serial != fullauto_current_enemy_serial or time.time() > fullauto_last_kill_time + 5.0:
                        API.SysMsg("Targeting hostile at " + str(enemy.Distance) + " tiles", 43)
                        if all_kill_closest():
                            fullauto_current_enemy_serial = enemy_serial
                            fullauto_last_kill_time = time.time()

            API.Pause(1.0)

    elif fullauto_state == "fleeing":
        # Check for critical HP during flee
        if check_critical_hp():
            API.SysMsg("=== EMERGENCY: CRITICAL HP DURING FLEE ===", 32)
            fullauto_current_enemy_serial = None
            fullauto_state = "emergency_fleeing"
            fullauto_start_time = time.time()
            return

        # Flee to random spot 8 tiles away
        import random

        current_x = getattr(API.Player, 'X', 0)
        current_y = getattr(API.Player, 'Y', 0)

        # Random direction
        flee_x = current_x + random.randint(-FLEE_DISTANCE, FLEE_DISTANCE)
        flee_y = current_y + random.randint(-FLEE_DISTANCE, FLEE_DISTANCE)

        # Cancel existing pathfinding
        if API.Pathfinding():
            API.CancelPathfinding()

        # Start fleeing
        API.Pathfind(flee_x, flee_y)
        API.Pause(2.0)

        # Heal while fleeing
        use_bandage_on_self()

        # After fleeing for 5 seconds, return to combat
        if time.time() > fullauto_start_time + 5.0:
            # Find and attack closest enemy (don't re-target same one immediately)
            enemy = find_closest_hostile()
            if enemy:
                enemy_serial = getattr(enemy, 'Serial', None)
                # Only attack if different enemy or enough time passed
                if enemy_serial != fullauto_current_enemy_serial or time.time() > fullauto_last_kill_time + 5.0:
                    if all_kill_closest():
                        fullauto_current_enemy_serial = enemy_serial
                        fullauto_last_kill_time = time.time()

            fullauto_state = "combat_mode"
            fullauto_start_time = time.time()

    elif fullauto_state == "emergency_fleeing":
        # Flee 15-20 tiles away before emergency recall
        import random

        current_x = getattr(API.Player, 'X', 0)
        current_y = getattr(API.Player, 'Y', 0)

        # Flee far away
        flee_x = current_x + random.randint(-EMERGENCY_FLEE_DISTANCE, EMERGENCY_FLEE_DISTANCE)
        flee_y = current_y + random.randint(-EMERGENCY_FLEE_DISTANCE, EMERGENCY_FLEE_DISTANCE)

        # Cancel existing pathfinding
        if API.Pathfinding():
            API.CancelPathfinding()

        # Start emergency flee
        API.Pathfind(flee_x, flee_y)
        API.SysMsg("FLEEING TO SAFE DISTANCE...", 32)
        API.Pause(3.0)

        # Heal while fleeing
        use_bandage_on_self()

        # After 5 seconds, emergency recall
        if time.time() > fullauto_start_time + 5.0:
            fullauto_state = "emergency_recalling"
            fullauto_start_time = time.time()

    elif fullauto_state == "emergency_recalling":
        # Emergency recall home
        API.SysMsg("=== EMERGENCY RECALL HOME ===", 32)

        # Call pets to follow
        all_follow_me()
        API.Pause(1.0)

        if recall_home():
            API.SysMsg("Emergency recall successful - healing", 68)
            fullauto_state = "resurrecting_pets"
            fullauto_start_time = time.time()
        else:
            API.SysMsg("Emergency recall FAILED - retrying", 32)
            API.Pause(2.0)

    elif fullauto_state == "resurrecting_pets":
        # Reset timeout at start of phase to prevent timeout during resurrection
        fullauto_start_time = time.time()

        # Check for dead pets and resurrect them
        dead_pets = get_dead_pets()

        if dead_pets and len(dead_pets) > 0:
            # Check for bandages (search ALL containers)
            if not find_all_bandages_recursive():
                API.SysMsg("=== OUT OF BANDAGES - CANNOT REZ PETS ===", 32)
                paused = True
                fullauto_state = "checking_inventory"
                return

            # Resurrect first dead pet
            pet = dead_pets[0]
            pet_serial = getattr(pet, 'Serial', None)
            if pet_serial:
                API.SysMsg("Resurrecting dead pet...", 68)
                if resurrect_pet(pet_serial):
                    API.Pause(2.0)
                    # Check again for more dead pets
                    return
                else:
                    API.Pause(1.0)
                    return
        else:
            # No dead pets - move to healing
            API.SysMsg("All pets alive - healing", 68)
            fullauto_state = "healing_after_combat"
            fullauto_start_time = time.time()

    elif fullauto_state == "healing_after_combat":
        # Reset timeout at start of phase to prevent timeout during healing
        fullauto_start_time = time.time()

        # Check for bandages (search ALL containers)
        if not find_all_bandages_recursive():
            API.SysMsg("=== OUT OF BANDAGES - PAUSING SCRIPT ===", 32)
            paused = True
            fullauto_state = "checking_inventory"
            return

        # Heal pets after combat
        healed = heal_pets()

        if healed:
            API.Pause(BANDAGE_DELAY)
            # Try to heal more pets if needed
            return

        # Check if player needs healing
        current_hp = API.Player.Hits
        max_hp = getattr(API.Player, 'HitsMax', 1)
        hp_pct = (current_hp / max_hp * 100) if max_hp > 0 else 100

        if hp_pct < 100:
            if use_bandage_on_self():
                API.Pause(BANDAGE_DELAY)
                return

        # All healed - return to recall spot (or go home if emergency recalled)
        current_x = getattr(API.Player, 'X', 0)
        current_y = getattr(API.Player, 'Y', 0)

        # Check if we're at home (emergency recalled)
        if at_home:
            # We emergency recalled - process materials at home
            API.SysMsg("Emergency recall complete - processing materials", 68)
            fullauto_state = "checking_inventory"
            fullauto_start_time = time.time()
            return

        # Check if we're at recall spot
        if abs(current_x - fullauto_recall_spot_x) <= 2 and abs(current_y - fullauto_recall_spot_y) <= 2:
            # Already at spot - start picking
            fullauto_state = "picking_phase"
            fullauto_start_time = time.time()
        else:
            # Need to return to spot
            fullauto_state = "returning_to_spot"
            fullauto_start_time = time.time()

    elif fullauto_state == "returning_to_spot":
        # Pathfind back to recall spot
        current_x = getattr(API.Player, 'X', 0)
        current_y = getattr(API.Player, 'Y', 0)

        # Check if we've arrived
        if abs(current_x - fullauto_recall_spot_x) <= 2 and abs(current_y - fullauto_recall_spot_y) <= 2:
            if API.Pathfinding():
                API.CancelPathfinding()
            API.SysMsg("Back at recall spot - starting to pick", 68)
            fullauto_state = "picking_phase"
            fullauto_start_time = time.time()
        else:
            # Still moving
            if not API.Pathfinding():
                API.Pathfind(fullauto_recall_spot_x, fullauto_recall_spot_y)
            API.Pause(0.5)

    elif fullauto_state == "picking_phase":
        # Reset timeout at start of phase to prevent timeout during long picking sessions
        fullauto_start_time = time.time()

        # FIRST: Check if taking damage (something is attacking)
        if is_taking_damage():
            API.SysMsg("=== TAKING DAMAGE - COMBAT MODE ===", 32)

            # Call pets to guard ONCE
            all_guard_me()
            API.Pause(0.5)

            # Find and attack closest enemy
            enemy = find_closest_hostile()
            if enemy:
                enemy_serial = getattr(enemy, 'Serial', None)
                API.SysMsg("Found hostile at " + str(enemy.Distance) + " tiles - attacking!", 32)

                # Attack and track this enemy
                if all_kill_closest():
                    fullauto_current_enemy_serial = enemy_serial
                    fullauto_last_kill_time = time.time()
                    fullauto_last_guard_time = time.time()

                API.Pause(0.5)

                # Flee 8-10 tiles away to let pets get aggro
                player_x = getattr(API.Player, 'X', 0)
                player_y = getattr(API.Player, 'Y', 0)
                enemy_x = getattr(enemy, 'X', player_x)
                enemy_y = getattr(enemy, 'Y', player_y)

                # Calculate direction away from enemy (multiply by 4 for ~8+ tiles distance)
                flee_x = player_x + (player_x - enemy_x) * 4
                flee_y = player_y + (player_y - enemy_y) * 4
                API.Pathfind(flee_x, flee_y)

                # Wait 4 seconds for pathfinding to move us far away
                API.Pause(4.0)

                # Cancel pathfinding if still active
                if API.Pathfinding():
                    API.CancelPathfinding()
            else:
                API.SysMsg("Taking damage but no hostile found!", 43)

            # Enter combat state
            fullauto_state = "combat_mode"
            fullauto_start_time = time.time()
            return

        # SECOND: Check for bandages - pause if none (search ALL containers)
        if not find_all_bandages_recursive():
            API.SysMsg("=== OUT OF BANDAGES - PAUSING SCRIPT ===", 32)
            paused = True
            fullauto_state = "checking_inventory"
            return

        # Use find_cotton_plants which searches ALL cotton graphics
        plants = find_cotton_plants()

        if plants and len(plants) > 0:
            no_plants_start_time = 0
            fullauto_empty_farms_count = 0  # Reset counter when we find plants

            # Find nearest plant not on cooldown
            nearest_plant = None
            nearest_distance = 999

            for plant in plants:
                if not plant:
                    continue

                plant_serial = getattr(plant, 'Serial', None)
                if not plant_serial or is_on_cooldown(plant_serial):
                    continue

                distance = getattr(plant, 'Distance', 999)
                if distance < nearest_distance:
                    nearest_plant = plant
                    nearest_distance = distance

            if nearest_plant:
                plant_serial = nearest_plant.Serial
                distance = getattr(nearest_plant, 'Distance', 999)

                if distance <= PICK_REACH:
                    # Pick plant
                    API.UseObject(plant_serial, False)
                    last_clicked[plant_serial] = time.time()
                    API.Pause(CLICK_DELAY)

                    # Wait for loot
                    API.Pause(2.0)

                    # Collect ground cotton
                    loot_ground_cotton()
                    stats["cotton_picked"] += 1

                    # Check weight threshold
                    if check_weight_threshold():
                        API.SysMsg("Weight threshold reached!", 43)
                        fullauto_state = "recalling_home"
                        fullauto_start_time = time.time()
                        return
                else:
                    # Pathfind to plant
                    plant_x = getattr(nearest_plant, 'X', 0)
                    plant_y = getattr(nearest_plant, 'Y', 0)

                    if not API.Pathfinding():
                        API.Pathfind(plant_x, plant_y)

                    API.Pause(0.5)
            else:
                # All plants on cooldown
                API.Pause(1.0)
        else:
            # No plants found
            if no_plants_start_time == 0:
                no_plants_start_time = time.time()

            if time.time() > no_plants_start_time + NO_PLANTS_TIMEOUT:
                if num_farm_spots > 1:
                    # Multiple farms - check if we've tried all of them
                    fullauto_empty_farms_count += 1

                    if fullauto_empty_farms_count >= num_farm_spots:
                        # All farms are empty - go home and wait 15 minutes
                        API.SysMsg("All farms empty - recalling home to wait 15 min", 43)
                        fullauto_empty_farms_count = 0
                        fullauto_state = "recalling_home_to_wait"
                        fullauto_start_time = time.time()
                    else:
                        # Try next farm
                        API.SysMsg("No plants for 5s - rotating to next farm ({}/{})".format(fullauto_empty_farms_count, num_farm_spots), 43)
                        no_plants_start_time = 0  # Reset timer for next farm
                        fullauto_state = "recalling_to_farm"
                        fullauto_start_time = time.time()
                else:
                    # Single farm - recall home and wait 15 minutes for respawn
                    API.SysMsg("No plants for 5s - recalling home to wait", 43)
                    fullauto_state = "recalling_home_to_wait"
                    fullauto_start_time = time.time()
            else:
                API.Pause(1.0)

    elif fullauto_state == "recalling_home":
        # Call pets to follow before recalling
        all_follow_me()
        API.Pause(1.0)

        if recall_home():
            fullauto_state = "checking_inventory"
            fullauto_start_time = time.time()
            API.SysMsg("At home - processing cotton", 68)
        else:
            API.SysMsg("Recall home failed!", 32)
            API.Pause(2.0)
            fullauto_state = "checking_inventory"

    elif fullauto_state == "pathfinding_to_wheel":
        if pathfind_to_wheel():
            fullauto_state = "spinning_phase"
            fullauto_start_time = time.time()
            API.SysMsg("At wheel - spinning...", 68)
        else:
            API.SysMsg("Pathfinding to wheel failed - recalling home!", 32)
            at_home = False  # We're clearly not at home
            fullauto_state = "recalling_home"
            fullauto_start_time = time.time()

    elif fullauto_state == "spinning_phase":
        # Reset timeout at start of phase to prevent timeout during retries
        fullauto_start_time = time.time()

        # Use existing weaver logic
        cotton = find_backpack_cotton()
        if cotton:
            if weaver_state == "idle":
                if start_spinning():
                    weaver_state = "spinning"
                    weaver_start_time = time.time()
                    weaver_duration = SPIN_DELAY
            elif weaver_state == "spinning":
                # Check completion
                if API.InJournal("You put the spools of thread in your backpack"):
                    stats["spools_made"] += 1
                    weaver_state = "idle"
                elif time.time() > weaver_start_time + weaver_duration:
                    stats["spools_made"] += 1
                    weaver_state = "idle"
        else:
            # No more cotton
            weaver_state = "idle"
            fullauto_state = "checking_inventory"
            fullauto_start_time = time.time()

    elif fullauto_state == "pathfinding_to_loom":
        if pathfind_to_loom():
            fullauto_state = "weaving_phase"
            fullauto_start_time = time.time()
            API.SysMsg("At loom - weaving...", 68)
        else:
            API.SysMsg("Pathfinding to loom failed - recalling home!", 32)
            at_home = False  # We're clearly not at home
            fullauto_state = "recalling_home"
            fullauto_start_time = time.time()

    elif fullauto_state == "weaving_phase":
        # Reset timeout at start of phase to prevent timeout during retries
        fullauto_start_time = time.time()

        # Use existing weaver logic
        spools = count_spools()
        if spools > 0:
            if weaver_state == "idle":
                if start_weaving():
                    weaver_state = "weaving"
                    weaver_start_time = time.time()
                    weaver_duration = WEAVE_DELAY
            elif weaver_state == "weaving":
                # Check completion
                if API.InJournal("You create some cloth"):
                    stats["bolts_created"] += 1
                    weaver_state = "idle"
                    # Reset state timeout after completing weave
                    fullauto_start_time = time.time()
                elif time.time() > weaver_start_time + weaver_duration:
                    stats["bolts_created"] += 1
                    weaver_state = "idle"
                    # Reset state timeout after completing weave
                    fullauto_start_time = time.time()
        else:
            # No more spools
            weaver_state = "idle"
            fullauto_state = "checking_inventory"
            fullauto_start_time = time.time()

    elif fullauto_state == "cutting_phase":
        # Reset timeout at start of phase to prevent timeout during retries
        fullauto_start_time = time.time()

        if cut_cloth_bolts():
            API.SysMsg("Cloth cut successfully!", 68)

            # Check if we should make bandages from the cloth
            if make_bandages:
                fullauto_state = "making_bandages"
                fullauto_start_time = time.time()
            else:
                fullauto_state = "checking_inventory"
                fullauto_start_time = time.time()
        else:
            # Check if we're out of bolts (success) or actual failure
            bolts = count_cloth_bolts()
            if bolts == 0:
                if make_bandages:
                    fullauto_state = "making_bandages"
                    fullauto_start_time = time.time()
                else:
                    fullauto_state = "checking_inventory"
                    fullauto_start_time = time.time()
            else:
                API.Pause(1.0)  # Wait and retry

    elif fullauto_state == "making_bandages":
        # Reset timeout at start of phase to prevent timeout during retries
        fullauto_start_time = time.time()

        if make_bandages_from_cloth():
            # After making bandages, need to store them
            fullauto_state = "storing_bandages"
            fullauto_start_time = time.time()
        else:
            # Check if we're out of cloth (success) or actual failure
            cloth = count_cloth_pieces()
            if cloth == 0:
                # No more cloth - check if we have bandages to store (only main backpack)
                if find_main_backpack_bandages_only():
                    fullauto_state = "storing_bandages"
                    fullauto_start_time = time.time()
                else:
                    fullauto_state = "checking_inventory"
                    fullauto_start_time = time.time()
            else:
                API.Pause(1.0)  # Wait and retry

    elif fullauto_state == "storing_bandages":
        # Reset timeout at start of phase to prevent timeout during storage retries
        fullauto_start_time = time.time()

        if store_bandages():
            # Check if more bandages to store (only main backpack)
            if find_main_backpack_bandages_only():
                API.Pause(0.5)  # Wait a bit and store next stack
            else:
                # All bandages stored from main backpack
                fullauto_state = "checking_inventory"
                fullauto_start_time = time.time()
        else:
            # Store failed - try again or give up
            if find_main_backpack_bandages_only():
                API.Pause(1.0)  # Wait and retry
            else:
                # No bandages left (or error) - continue
                fullauto_state = "checking_inventory"
                fullauto_start_time = time.time()

    elif fullauto_state == "pathfinding_to_storage":
        if pathfind_to_storage_bin():
            # Check what we need to store (only main backpack bandages)
            if find_main_backpack_bandages_only():
                fullauto_state = "storing_bandages"
                fullauto_start_time = time.time()
                API.SysMsg("At storage - storing bandages...", 68)
            elif count_cloth_pieces() > 0:
                fullauto_state = "storing_phase"
                fullauto_start_time = time.time()
                API.SysMsg("At storage - storing cloth...", 68)
            else:
                # Nothing to store? Go back to checking
                fullauto_state = "checking_inventory"
                fullauto_start_time = time.time()
        else:
            API.SysMsg("Pathfinding to storage failed - recalling home!", 32)
            at_home = False  # We're clearly not at home
            fullauto_state = "recalling_home"
            fullauto_start_time = time.time()

    elif fullauto_state == "storing_phase":
        # Reset timeout at start of phase to prevent timeout during storage retries
        fullauto_start_time = time.time()

        if store_resources():
            API.SysMsg("Cloth stored successfully!", 68)
            stats["cycles_completed"] += 1
            fullauto_state = "checking_inventory"
            fullauto_start_time = time.time()
        else:
            # Check if we're out of cloth (success) or actual failure
            cloth = count_cloth_pieces()
            if cloth == 0:
                stats["cycles_completed"] += 1
                fullauto_state = "checking_inventory"
                fullauto_start_time = time.time()
            else:
                API.Pause(1.0)  # Wait and retry

    elif fullauto_state == "recalling_home_to_wait":
        # Recall home before waiting for respawn
        all_follow_me()
        API.Pause(1.0)

        if recall_home():
            API.SysMsg("At home - waiting 15 min for farm respawn", 68)
            fullauto_state = "waiting_for_respawn"
            fullauto_start_time = time.time()
            fullauto_respawn_wait_start = time.time()
        else:
            API.SysMsg("Recall home failed - retrying", 32)
            API.Pause(2.0)

    elif fullauto_state == "waiting_for_respawn":
        # Non-blocking wait for plants to respawn (15 minutes) - AT HOME
        elapsed = time.time() - fullauto_respawn_wait_start
        remaining = RESPAWN_WAIT_TIME - elapsed

        if remaining <= 0:
            # Wait complete - return to farm
            API.SysMsg("Respawn wait complete - returning to farm", 68)
            fullauto_empty_farms_count = 0  # Reset farm counter
            fullauto_state = "recalling_to_farm"
            fullauto_start_time = time.time()
            no_plants_start_time = 0
        else:
            # Still waiting - show countdown every 60 seconds
            if int(elapsed) % 60 == 0 and int(elapsed) > 0:
                minutes_left = int(remaining / 60)
                API.SysMsg("Waiting for respawn: " + str(minutes_left) + " min left", 43)

            # Process any materials we have while waiting
            cloth_pieces = count_cloth_pieces()
            cloth_bolts = count_cloth_bolts()
            spools = count_spools()
            cotton = find_backpack_cotton()

            if cloth_pieces > 0 or cloth_bolts > 0 or spools > 0 or cotton:
                API.SysMsg("Have materials - processing while waiting", 68)
                fullauto_state = "checking_inventory"
                fullauto_start_time = time.time()
            else:
                API.Pause(5.0)  # Long pause since we're waiting

# ============ HOTKEY CALLBACKS ============
def toggle_pause():
    """Toggle pause state."""
    global paused
    paused = not paused

    if paused:
        API.SysMsg("Cotton Suite PAUSED", 43)
    else:
        API.SysMsg("Cotton Suite RESUMED", 68)

    update_display()

# ============ GUI CALLBACKS ============
def on_mode_picker():
    """Activate Picker mode."""
    global mode, STATE, weaver_state, autopick_state, autopick_target_graphic
    mode = "picker"
    STATE = "idle"
    weaver_state = "idle"
    autopick_state = "scanning"
    autopick_target_graphic = None

    # Cancel pathfinding if active
    if API.Pathfinding():
        API.CancelPathfinding()

    API.SysMsg("Picker mode activated", 68)
    update_display()

def on_mode_weaver():
    """Activate Weaver mode."""
    global mode, STATE, weaver_state, autopick_state, autopick_target_graphic
    mode = "weaver"
    STATE = "idle"
    weaver_state = "idle"
    autopick_state = "scanning"
    autopick_target_graphic = None

    # Cancel pathfinding if active
    if API.Pathfinding():
        API.CancelPathfinding()

    API.SysMsg("Weaver mode activated", 68)
    update_display()

def on_mode_autopick():
    """Activate AutoPick mode - request target in callback (non-blocking)."""
    global mode, STATE, weaver_state, autopick_state, autopick_target_graphic

    # Cancel pathfinding if active
    try:
        if API.Pathfinding():
            API.CancelPathfinding()
    except:
        pass

    # Request target NOW (in button callback, not main loop)
    API.SysMsg("Target a cotton plant to identify...", 68)

    try:
        target = API.RequestTarget(15)
    except Exception as e:
        API.SysMsg("ERROR: RequestTarget failed - " + str(e), 33)
        return

    # RequestTarget returns a serial (uint32)
    if not target or target == 0:
        API.SysMsg("AutoPick cancelled", 33)
        return

    # Find the item by serial
    try:
        item = API.FindItem(target)
    except Exception as e:
        API.SysMsg("ERROR: FindItem failed - " + str(e), 33)
        return

    if not item:
        API.SysMsg("ERROR: Could not find targeted item", 33)
        return

    # Get graphic from item
    try:
        graphic = item.Graphic
    except:
        try:
            graphic = getattr(item, 'Graphic', 0)
        except:
            graphic = 0

    if not graphic or graphic == 0:
        API.SysMsg("ERROR: Could not get item graphic", 33)
        return

    # Store graphic
    autopick_target_graphic = graphic
    API.SysMsg("Targeting plants with graphic 0x" + format(autopick_target_graphic, '04X'), 68)

    # Activate AutoPick mode
    mode = "autopick"
    STATE = "idle"
    weaver_state = "idle"
    autopick_state = "scanning"

    try:
        update_display()
    except:
        pass

def on_mode_fullautomation():
    """Activate Full Automation mode."""
    global mode, STATE, weaver_state, autopick_state, autopick_target_graphic, fullauto_state, fullauto_target_graphic, at_home

    # Check configuration
    if not wheel_serial or not loom_serial:
        API.SysMsg("ERROR: Wheel and loom must be set!", 32)
        return

    if not storage_box_serial:
        API.SysMsg("ERROR: Storage bin must be set!", 32)
        return

    if not runebook_serial:
        API.SysMsg("ERROR: Runebook must be set!", 32)
        return

    # Cancel pathfinding if active
    if API.Pathfinding():
        API.CancelPathfinding()

    # Activate mode
    mode = "fullautomation"
    STATE = "idle"
    weaver_state = "idle"
    autopick_state = "scanning"
    autopick_target_graphic = None
    fullauto_state = "checking_inventory"
    fullauto_target_graphic = COTTON_PLANT_GRAPHICS[0]  # Default to first cotton graphic

    # Detect if we're at home when starting
    at_home = check_if_at_home()
    if at_home:
        API.SysMsg("Full Automation activated - detected at home", 68)
    else:
        API.SysMsg("Full Automation activated - detected away from home", 68)

    update_display()

def on_mode_idle():
    """Deactivate all modes."""
    global mode, STATE, weaver_state, autopick_state, autopick_target_graphic, fullauto_state
    mode = "idle"
    STATE = "idle"
    weaver_state = "idle"
    autopick_state = "scanning"
    autopick_target_graphic = None
    fullauto_state = "checking_inventory"

    # Cancel pathfinding if active
    if API.Pathfinding():
        API.CancelPathfinding()

    API.SysMsg("All modes deactivated", 90)
    update_display()

def on_reset_wheel():
    """Reset wheel target and request new one (button callback)."""
    request_wheel_target_blocking()
    update_display()

def on_reset_loom():
    """Reset loom target and request new one (button callback)."""
    request_loom_target_blocking()
    update_display()

def on_set_storage_bin():
    """Request storage bin target from player (button callback)."""
    global storage_box_serial, storage_x, storage_y

    API.SysMsg("Target your STORAGE BIN", 55)
    storage_box_serial = API.RequestTarget(15)

    if not storage_box_serial:
        if API.HasTarget():
            API.CancelTarget()
        API.CancelPreTarget()
        API.SysMsg("Storage bin target cancelled", 33)
    else:
        # Get storage position
        storage_box = API.FindItem(storage_box_serial)
        if storage_box:
            storage_x = getattr(storage_box, 'X', 0)
            storage_y = getattr(storage_box, 'Y', 0)
            save_persistent_var("StorageSerial", str(storage_box_serial))
            save_persistent_var("StorageX", str(storage_x))
            save_persistent_var("StorageY", str(storage_y))
            API.SysMsg("Storage bin saved at ({}, {})!".format(storage_x, storage_y), 68)
        else:
            save_persistent_var("StorageSerial", str(storage_box_serial))
            API.SysMsg("Storage bin saved!", 68)
    update_display()

def on_toggle_bandages():
    """Toggle bandage making mode."""
    global make_bandages
    make_bandages = not make_bandages
    save_persistent_var("MakeBandages", str(make_bandages))

    if make_bandages:
        API.SysMsg("Bandage mode: ON - Will make bandages from cloth", 68)
    else:
        API.SysMsg("Bandage mode: OFF - Will store cloth pieces", 68)

def on_set_runebook():
    """Request runebook target from player (button callback)."""
    global runebook_serial

    API.SysMsg("Target your RUNEBOOK", 55)
    runebook_serial = API.RequestTarget(15)

    # Clean up cursor on timeout
    if not runebook_serial:
        if API.HasTarget():
            API.CancelTarget()
        API.CancelPreTarget()
        API.SysMsg("Runebook target cancelled", 33)
    else:
        save_persistent_var("RunebookSerial", str(runebook_serial))
        API.SysMsg("Runebook saved! Slot 1 = Home, Slots 2+ = Farms", 68)

def on_farm_spots_decrease():
    """Decrease number of farm spots."""
    global num_farm_spots
    if num_farm_spots > 1:
        num_farm_spots -= 1
        save_persistent_var("NumFarmSpots", str(num_farm_spots))
        API.SysMsg("Farm spots: " + str(num_farm_spots), 55)
        update_display()

def on_farm_spots_increase():
    """Increase number of farm spots."""
    global num_farm_spots
    if num_farm_spots < 14:  # Max 14 farms (runebook has 16 slots, 1 for home, 1 reserved)
        num_farm_spots += 1
        save_persistent_var("NumFarmSpots", str(num_farm_spots))
        API.SysMsg("Farm spots: " + str(num_farm_spots), 55)
        update_display()

def on_weight_decrease():
    """Decrease weight threshold."""
    global weight_threshold
    if weight_threshold > 50:
        weight_threshold -= 5
        save_persistent_var("WeightThreshold", str(weight_threshold))
        API.SysMsg("Weight threshold: " + str(weight_threshold) + "%", 55)
        update_display()

def on_weight_increase():
    """Increase weight threshold."""
    global weight_threshold
    if weight_threshold < 95:
        weight_threshold += 5
        save_persistent_var("WeightThreshold", str(weight_threshold))
        API.SysMsg("Weight threshold: " + str(weight_threshold) + "%", 55)
        update_display()

def on_test_home():
    """Test recall to home (slot 1)."""
    API.SysMsg("Testing home recall...", 55)
    all_follow_me()
    API.Pause(1.0)
    if recall_home():
        API.SysMsg("Home recall test successful!", 68)
    else:
        API.SysMsg("Home recall test failed!", 32)

def on_test_farm():
    """Test recall to current farm spot."""
    API.SysMsg("Testing farm recall...", 55)
    all_follow_me()
    API.Pause(1.0)
    if recall_to_farm():
        API.SysMsg("Farm recall test successful!", 68)
    else:
        API.SysMsg("Farm recall test failed!", 32)

def on_reset_stats():
    """Reset session stats."""
    global stats, session_start
    stats = {
        "cotton_picked": 0,
        "spools_made": 0,
        "bolts_created": 0,
        "ground_cotton_collected": 0,
        "cloth_cut": 0,
        "cloth_stored": 0,
        "bandages_made": 0,
        "bandages_stored": 0,
        "cycles_completed": 0
    }
    session_start = time.time()
    API.SysMsg("Stats reset", 55)
    update_display()

def on_closed():
    """Handle window close."""
    global ui_closed
    ui_closed = True

    # Save window position
    try:
        x = gump.GetX()
        y = gump.GetY()
        save_persistent_var("XY", str(x) + "," + str(y))
    except:
        pass

    cleanup()

# ============ PERSISTENCE ============
def save_persistent_var(key, value):
    """Save persistent variable."""
    API.SavePersistentVar(KEY_PREFIX + key, value, API.PersistentVar.Char)

def load_persistent_var(key, default):
    """Load persistent variable."""
    return API.GetPersistentVar(KEY_PREFIX + key, default, API.PersistentVar.Char)

def save_settings():
    """Save all settings."""
    save_persistent_var("Mode", mode)
    save_persistent_var("WheelSerial", str(wheel_serial) if wheel_serial else "")
    save_persistent_var("LoomSerial", str(loom_serial) if loom_serial else "")
    save_persistent_var("RunebookSerial", str(runebook_serial) if runebook_serial else "")
    save_persistent_var("StorageSerial", str(storage_box_serial) if storage_box_serial else "")
    save_persistent_var("NumFarmSpots", str(num_farm_spots))
    save_persistent_var("WeightThreshold", str(weight_threshold))
    save_persistent_var("CurrentFarmIndex", str(current_farm_index))

def load_settings():
    """Load all settings with defaults."""
    global wheel_serial, loom_serial, runebook_serial, num_farm_spots, weight_threshold, current_farm_index
    global storage_box_serial, wheel_x, wheel_y, loom_x, loom_y, storage_x, storage_y, make_bandages

    wheel_str = load_persistent_var("WheelSerial", "")
    if wheel_str:
        try:
            wheel_serial = int(wheel_str)
        except:
            wheel_serial = None

    wheel_x_str = load_persistent_var("WheelX", "0")
    try:
        wheel_x = int(wheel_x_str)
    except:
        wheel_x = 0

    wheel_y_str = load_persistent_var("WheelY", "0")
    try:
        wheel_y = int(wheel_y_str)
    except:
        wheel_y = 0

    loom_str = load_persistent_var("LoomSerial", "")
    if loom_str:
        try:
            loom_serial = int(loom_str)
        except:
            loom_serial = None

    loom_x_str = load_persistent_var("LoomX", "0")
    try:
        loom_x = int(loom_x_str)
    except:
        loom_x = 0

    loom_y_str = load_persistent_var("LoomY", "0")
    try:
        loom_y = int(loom_y_str)
    except:
        loom_y = 0

    storage_str = load_persistent_var("StorageSerial", "")
    if storage_str:
        try:
            storage_box_serial = int(storage_str)
        except:
            storage_box_serial = None

    storage_x_str = load_persistent_var("StorageX", "0")
    try:
        storage_x = int(storage_x_str)
    except:
        storage_x = 0

    storage_y_str = load_persistent_var("StorageY", "0")
    try:
        storage_y = int(storage_y_str)
    except:
        storage_y = 0

    runebook_str = load_persistent_var("RunebookSerial", "")
    if runebook_str:
        try:
            runebook_serial = int(runebook_str)
        except:
            runebook_serial = None

    num_farm_str = load_persistent_var("NumFarmSpots", "1")
    try:
        num_farm_spots = int(num_farm_str)
    except:
        num_farm_spots = 1

    weight_str = load_persistent_var("WeightThreshold", "80")
    try:
        weight_threshold = int(weight_str)
    except:
        weight_threshold = 80

    current_farm_str = load_persistent_var("CurrentFarmIndex", "0")
    try:
        current_farm_index = int(current_farm_str)
    except:
        current_farm_index = 0

    # Load make_bandages toggle
    make_bandages_str = load_persistent_var("MakeBandages", "False")
    make_bandages = (make_bandages_str == "True")

# ============ DISPLAY UPDATES ============
def get_status_text():
    """Get current status text."""
    if paused:
        return "PAUSED"

    if mode == "picker":
        if STATE == "picking":
            return "Picking cotton..."
        elif STATE == "looting":
            return "Looting cotton..."
        else:
            return "Scanning for plants..."

    elif mode == "weaver":
        if weaver_state == "spinning":
            return "Spinning cotton..."
        elif weaver_state == "weaving":
            return "Weaving cloth..."
        else:
            cotton = find_backpack_cotton()
            spools = count_spools()
            if cotton:
                return "Ready to spin (" + str(spools) + " spools)"
            elif spools > 0:
                return "Ready to weave (" + str(spools) + " spools)"
            else:
                return "No cotton or spools"

    elif mode == "autopick":
        if autopick_state == "moving":
            return "Moving to plant..."
        elif autopick_state == "picking":
            return "Picking cotton..."
        elif autopick_state == "waiting_for_loot":
            return "Waiting for loot..."
        elif autopick_state == "looting":
            return "Collecting cotton..."
        elif autopick_state == "recalling_home":
            return "Recalling home..."
        elif autopick_state == "at_home":
            return "At home - unload cotton"
        elif autopick_state == "recalling_to_farm":
            return "Recalling to farm..."
        elif autopick_state == "scanning":
            if autopick_target_graphic:
                return "Scanning for 0x{:04X}...".format(autopick_target_graphic)
            else:
                return "No target set"
        else:
            return "Idle"

    elif mode == "fullautomation":
        if fullauto_state == "checking_inventory":
            return "Checking inventory..."
        elif fullauto_state == "preflight_check":
            return "Preflight check..."
        elif fullauto_state == "preflight_healing":
            return "Healing at home..."
        elif fullauto_state == "recalling_to_farm":
            return "Recalling to farm..."
        elif fullauto_state == "checking_for_enemies":
            return "Checking for enemies..."
        elif fullauto_state == "combat_mode":
            return "In combat!"
        elif fullauto_state == "fleeing":
            return "Fleeing from enemies!"
        elif fullauto_state == "emergency_fleeing":
            return "EMERGENCY FLEE!"
        elif fullauto_state == "emergency_recalling":
            return "EMERGENCY RECALL!"
        elif fullauto_state == "resurrecting_pets":
            return "Resurrecting pets..."
        elif fullauto_state == "healing_after_combat":
            return "Healing after combat..."
        elif fullauto_state == "returning_to_spot":
            return "Returning to spot..."
        elif fullauto_state == "picking_phase":
            return "Picking cotton..."
        elif fullauto_state == "recalling_home_to_wait":
            return "Recalling home to wait..."
        elif fullauto_state == "waiting_for_respawn":
            elapsed = time.time() - fullauto_respawn_wait_start
            remaining = RESPAWN_WAIT_TIME - elapsed
            minutes_left = int(remaining / 60)
            return "Waiting for respawn ({} min)".format(minutes_left)
        elif fullauto_state == "recalling_home":
            return "Recalling home..."
        elif fullauto_state == "pathfinding_to_wheel":
            return "Going to wheel..."
        elif fullauto_state == "spinning_phase":
            return "Spinning cotton..."
        elif fullauto_state == "pathfinding_to_loom":
            return "Going to loom..."
        elif fullauto_state == "weaving_phase":
            return "Weaving cloth..."
        elif fullauto_state == "cutting_phase":
            return "Cutting cloth..."
        elif fullauto_state == "making_bandages":
            return "Making bandages..."
        elif fullauto_state == "storing_bandages":
            return "Storing bandages..."
        elif fullauto_state == "pathfinding_to_storage":
            return "Going to storage..."
        elif fullauto_state == "storing_phase":
            return "Storing cloth..."
        else:
            return "Full Auto Active"

    else:
        return "Idle"

def update_display():
    """Update GUI to reflect current state."""
    if ui_closed:
        return

    try:
        # Update mode buttons
        picker_btn.SetBackgroundHue(68 if mode == "picker" else 90)
        weaver_btn.SetBackgroundHue(68 if mode == "weaver" else 90)
        autopick_btn.SetBackgroundHue(68 if mode == "autopick" else 90)
        fullauto_btn.SetBackgroundHue(68 if mode == "fullautomation" else 90)
        idle_btn.SetBackgroundHue(68 if mode == "idle" else 90)

        # Update status
        status = get_status_text()
        status_label.SetText("Status: " + status)

        # Update stats
        runtime = time.time() - session_start
        runtime_label.SetText("Runtime: " + format_time(runtime))
        picked_label.SetText("Picked: " + format_number(stats['cotton_picked']))
        spools_label.SetText("Spools: " + format_number(stats['spools_made']))
        bolts_label.SetText("Bolts: " + format_number(stats['bolts_created']))
        collected_label.SetText("Collected: " + format_number(stats['ground_cotton_collected']))

        # Update full auto stats if available
        if 'cycles_completed' in stats:
            cycles_label.SetText("Cycles: " + format_number(stats['cycles_completed']))
        if 'bandages_made' in stats:
            bandages_made_label.SetText("Bandages Made: " + format_number(stats['bandages_made']))

        # Update pause button
        pause_btn.SetBackgroundHue(43 if paused else 90)
        pause_btn.SetText("[PAUSED]" if paused else "[PAUSE]")

        # Update runebook display
        farm_spots_display.SetText(str(num_farm_spots))
        weight_display.SetText(str(weight_threshold) + "%")
        current_farm_label.SetText("Current: Farm " + str(current_farm_index + 1) + "/" + str(num_farm_spots))
    except:
        # Gump disposed, ignore update errors
        pass

# ============ CLEANUP ============
def cleanup():
    """Cleanup on exit."""
    save_settings()

    # Cancel any active pathfinding
    if API.Pathfinding():
        API.CancelPathfinding()

    if API.HasTarget():
        API.CancelTarget()
    API.CancelPreTarget()

    API.SysMsg("Cotton Suite stopped", 33)

# ============ INITIALIZATION ============
load_settings()

# ============ BUILD GUI ============
gump = API.Gumps.CreateGump()

# Load saved position with error handling
try:
    saved_pos = load_persistent_var("XY", "100,100")
    pos_parts = saved_pos.split(',')
    x, y = int(pos_parts[0]), int(pos_parts[1])
except:
    x, y = 100, 100

gump.SetRect(x, y, 360, 700)

# Background
bg = API.Gumps.CreateGumpColorBox(0.85, COLOR_BG)
bg.SetRect(0, 0, 360, 700)
gump.Add(bg)

# Title
title = API.Gumps.CreateGumpTTFLabel("Cotton Suite v3.0", 16, COLOR_TITLE)
title.SetPos(110, 10)
gump.Add(title)

# Mode buttons (row 1)
y_pos = 45

mode_label = API.Gumps.CreateGumpTTFLabel("Mode:", 11, COLOR_GRAY)
mode_label.SetPos(10, y_pos + 2)
gump.Add(mode_label)

picker_btn = API.Gumps.CreateSimpleButton("[Picker]", 70, 22)
picker_btn.SetPos(60, y_pos)
picker_btn.SetBackgroundHue(68 if mode == "picker" else 90)
API.Gumps.AddControlOnClick(picker_btn, on_mode_picker)
gump.Add(picker_btn)

weaver_btn = API.Gumps.CreateSimpleButton("[Weaver]", 70, 22)
weaver_btn.SetPos(140, y_pos)
weaver_btn.SetBackgroundHue(68 if mode == "weaver" else 90)
API.Gumps.AddControlOnClick(weaver_btn, on_mode_weaver)
gump.Add(weaver_btn)

autopick_btn = API.Gumps.CreateSimpleButton("[AutoPick]", 80, 22)
autopick_btn.SetPos(220, y_pos)
autopick_btn.SetBackgroundHue(68 if mode == "autopick" else 90)
API.Gumps.AddControlOnClick(autopick_btn, on_mode_autopick)
gump.Add(autopick_btn)

# Row 2: Full Auto button
y_pos += 30

fullauto_btn = API.Gumps.CreateSimpleButton("[Full Auto]", 90, 22)
fullauto_btn.SetPos(10, y_pos)
fullauto_btn.SetBackgroundHue(68 if mode == "fullautomation" else 90)
API.Gumps.AddControlOnClick(fullauto_btn, on_mode_fullautomation)
gump.Add(fullauto_btn)

idle_btn = API.Gumps.CreateSimpleButton("[Stop All]", 80, 22)
idle_btn.SetPos(110, y_pos)
idle_btn.SetBackgroundHue(68 if mode == "idle" else 90)
API.Gumps.AddControlOnClick(idle_btn, on_mode_idle)
gump.Add(idle_btn)

pause_btn = API.Gumps.CreateSimpleButton("[PAUSE]", 80, 22)
pause_btn.SetPos(200, y_pos)
pause_btn.SetBackgroundHue(43 if paused else 90)
API.Gumps.AddControlOnClick(pause_btn, toggle_pause)
gump.Add(pause_btn)

# Status section
y_pos += 35

status_header = API.Gumps.CreateGumpTTFLabel("STATUS", 11, COLOR_YELLOW)
status_header.SetPos(10, y_pos)
gump.Add(status_header)

y_pos += 20

status_label = API.Gumps.CreateGumpTTFLabel("Status: Idle", 11, COLOR_GREEN)
status_label.SetPos(10, y_pos)
gump.Add(status_label)

y_pos += 20

runtime_label = API.Gumps.CreateGumpTTFLabel("Runtime: 00:00:00", 11, COLOR_GRAY)
runtime_label.SetPos(10, y_pos)
gump.Add(runtime_label)

# Stats section
y_pos += 30

stats_header = API.Gumps.CreateGumpTTFLabel("SESSION STATS", 11, COLOR_YELLOW)
stats_header.SetPos(10, y_pos)
gump.Add(stats_header)

y_pos += 20

picked_label = API.Gumps.CreateGumpTTFLabel("Picked: 0", 11, COLOR_GREEN)
picked_label.SetPos(10, y_pos)
gump.Add(picked_label)

y_pos += 18

spools_label = API.Gumps.CreateGumpTTFLabel("Spools: 0", 11, COLOR_PURPLE)
spools_label.SetPos(10, y_pos)
gump.Add(spools_label)

y_pos += 18

bolts_label = API.Gumps.CreateGumpTTFLabel("Bolts: 0", 11, COLOR_YELLOW)
bolts_label.SetPos(10, y_pos)
gump.Add(bolts_label)

y_pos += 18

collected_label = API.Gumps.CreateGumpTTFLabel("Collected: 0", 11, COLOR_GRAY)
collected_label.SetPos(10, y_pos)
gump.Add(collected_label)

y_pos += 18

cycles_label = API.Gumps.CreateGumpTTFLabel("Cycles: 0", 11, COLOR_PURPLE)
cycles_label.SetPos(10, y_pos)
gump.Add(cycles_label)

y_pos += 18

bandages_made_label = API.Gumps.CreateGumpTTFLabel("Bandages Made: 0", 11, COLOR_GRAY)
bandages_made_label.SetPos(10, y_pos)
gump.Add(bandages_made_label)

# Full automation setup section
y_pos += 30

fullauto_header = API.Gumps.CreateGumpTTFLabel("FULL AUTO SETUP", 11, COLOR_YELLOW)
fullauto_header.SetPos(10, y_pos)
gump.Add(fullauto_header)

y_pos += 20

reset_wheel_btn = API.Gumps.CreateSimpleButton("[Set Wheel]", 100, 22)
reset_wheel_btn.SetPos(10, y_pos)
reset_wheel_btn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(reset_wheel_btn, on_reset_wheel)
gump.Add(reset_wheel_btn)

reset_loom_btn = API.Gumps.CreateSimpleButton("[Set Loom]", 100, 22)
reset_loom_btn.SetPos(120, y_pos)
reset_loom_btn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(reset_loom_btn, on_reset_loom)
gump.Add(reset_loom_btn)

set_storage_btn = API.Gumps.CreateSimpleButton("[Set Storage]", 100, 22)
set_storage_btn.SetPos(230, y_pos)
set_storage_btn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(set_storage_btn, on_set_storage_bin)
gump.Add(set_storage_btn)

y_pos += 28

# Bandage making toggle
bandage_label = API.Gumps.CreateGumpTTFLabel("Make Bandages:", 11, COLOR_GRAY)
bandage_label.SetPos(10, y_pos + 2)
gump.Add(bandage_label)

bandage_toggle_btn = API.Gumps.CreateSimpleButton("[ON]" if make_bandages else "[OFF]", 60, 22)
bandage_toggle_btn.SetPos(110, y_pos)
bandage_toggle_btn.SetBackgroundHue(68 if make_bandages else 32)
API.Gumps.AddControlOnClick(bandage_toggle_btn, on_toggle_bandages)
gump.Add(bandage_toggle_btn)

# Runebook setup section
y_pos += 30

runebook_header = API.Gumps.CreateGumpTTFLabel("RUNEBOOK SETUP", 11, COLOR_YELLOW)
runebook_header.SetPos(10, y_pos)
gump.Add(runebook_header)

y_pos += 20

set_runebook_btn = API.Gumps.CreateSimpleButton("[SET]", 50, 22)
set_runebook_btn.SetPos(10, y_pos)
set_runebook_btn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(set_runebook_btn, on_set_runebook)
gump.Add(set_runebook_btn)

runebook_info = API.Gumps.CreateGumpTTFLabel("Slot 1=Home, 2+=Farms", 9, COLOR_GRAY)
runebook_info.SetPos(70, y_pos + 5)
gump.Add(runebook_info)

y_pos += 28

# Farm spots control
farm_spots_label = API.Gumps.CreateGumpTTFLabel("Farms:", 11, COLOR_GRAY)
farm_spots_label.SetPos(10, y_pos + 2)
gump.Add(farm_spots_label)

farm_spots_dec_btn = API.Gumps.CreateSimpleButton("[-]", 30, 22)
farm_spots_dec_btn.SetPos(60, y_pos)
farm_spots_dec_btn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(farm_spots_dec_btn, on_farm_spots_decrease)
gump.Add(farm_spots_dec_btn)

farm_spots_display = API.Gumps.CreateGumpTTFLabel(str(num_farm_spots), 11, COLOR_GREEN)
farm_spots_display.SetPos(100, y_pos + 2)
gump.Add(farm_spots_display)

farm_spots_inc_btn = API.Gumps.CreateSimpleButton("[+]", 30, 22)
farm_spots_inc_btn.SetPos(120, y_pos)
farm_spots_inc_btn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(farm_spots_inc_btn, on_farm_spots_increase)
gump.Add(farm_spots_inc_btn)

# Weight threshold control
weight_label = API.Gumps.CreateGumpTTFLabel("Weight:", 11, COLOR_GRAY)
weight_label.SetPos(170, y_pos + 2)
gump.Add(weight_label)

weight_dec_btn = API.Gumps.CreateSimpleButton("[-]", 30, 22)
weight_dec_btn.SetPos(230, y_pos)
weight_dec_btn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(weight_dec_btn, on_weight_decrease)
gump.Add(weight_dec_btn)

weight_display = API.Gumps.CreateGumpTTFLabel(str(weight_threshold) + "%", 11, COLOR_GREEN)
weight_display.SetPos(265, y_pos + 2)
gump.Add(weight_display)

weight_inc_btn = API.Gumps.CreateSimpleButton("[+]", 30, 22)
weight_inc_btn.SetPos(305, y_pos)
weight_inc_btn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(weight_inc_btn, on_weight_increase)
gump.Add(weight_inc_btn)

y_pos += 28

# Current farm display
current_farm_label = API.Gumps.CreateGumpTTFLabel("Current: Farm " + str(current_farm_index + 1) + "/" + str(num_farm_spots), 11, COLOR_PURPLE)
current_farm_label.SetPos(10, y_pos)
gump.Add(current_farm_label)

y_pos += 20

# Test buttons
test_home_btn = API.Gumps.CreateSimpleButton("[Test Home]", 90, 22)
test_home_btn.SetPos(10, y_pos)
test_home_btn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(test_home_btn, on_test_home)
gump.Add(test_home_btn)

test_farm_btn = API.Gumps.CreateSimpleButton("[Test Farm]", 90, 22)
test_farm_btn.SetPos(110, y_pos)
test_farm_btn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(test_farm_btn, on_test_farm)
gump.Add(test_farm_btn)

y_pos += 28

debug_pets_btn = API.Gumps.CreateSimpleButton("[Debug Pets]", 210, 22)
debug_pets_btn.SetPos(10, y_pos)
debug_pets_btn.SetBackgroundHue(43)
API.Gumps.AddControlOnClick(debug_pets_btn, debug_shared_pets)
gump.Add(debug_pets_btn)

# Utility buttons
y_pos += 30

reset_stats_btn = API.Gumps.CreateSimpleButton("[Reset Stats]", 110, 22)
reset_stats_btn.SetPos(10, y_pos)
reset_stats_btn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(reset_stats_btn, on_reset_stats)
gump.Add(reset_stats_btn)

# Help text
y_pos += 40

help1 = API.Gumps.CreateGumpTTFLabel("Picker: Auto-pick cotton plants in reach (1 tile)", 8, COLOR_GRAY)
help1.SetPos(10, y_pos)
gump.Add(help1)

y_pos += 12

help2 = API.Gumps.CreateGumpTTFLabel("Weaver: Spin cotton -> spools -> cloth bolts", 8, COLOR_GRAY)
help2.SetPos(10, y_pos)
gump.Add(help2)

y_pos += 12

help3 = API.Gumps.CreateGumpTTFLabel("AutoPick: Target plant type, auto-pathfind and pick", 8, COLOR_GRAY)
help3.SetPos(10, y_pos)
gump.Add(help3)

y_pos += 12

help4 = API.Gumps.CreateGumpTTFLabel("Full Auto: Complete cycle (pick -> spin -> weave -> cut -> store)", 8, COLOR_GRAY)
help4.SetPos(10, y_pos)
gump.Add(help4)

y_pos += 12

help5 = API.Gumps.CreateGumpTTFLabel("Hotkey: " + hotkeys['pause'] + " = Pause/Resume", 8, COLOR_YELLOW)
help5.SetPos(10, y_pos)
gump.Add(help5)

# Register close callback
API.Gumps.AddControlOnDisposed(gump, on_closed)

# Show GUI
API.Gumps.AddGump(gump)

# ============ REGISTER HOTKEYS ============
API.OnHotKey(hotkeys["pause"], toggle_pause)

# ============ MAIN LOOP ============
API.SysMsg("Cotton Suite started", 68)

while not API.StopRequested and not ui_closed:
    try:
        API.ProcessCallbacks()  # MUST be first - keeps hotkeys instant

        # Run appropriate mode logic
        if mode == "picker":
            picker_logic()
        elif mode == "weaver":
            weaver_logic()
        elif mode == "autopick":
            autopick_logic()
        elif mode == "fullautomation":
            fullauto_logic()
        else:
            # Idle mode
            API.Pause(0.2)

        # Update display
        update_display()

        # Short pause
        API.Pause(0.1)

    except Exception as e:
        API.SysMsg("Error: " + str(e), 32)
        API.Pause(1)

cleanup()
