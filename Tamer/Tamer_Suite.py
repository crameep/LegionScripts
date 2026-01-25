# ============================================================
# Tamer Suite v3.0
# by Coryigon for UO Unchained
# ============================================================
#
# The all-in-one tamer script. Combines pet healing and commands
# into a single window with a non-blocking design - your hotkeys
# stay responsive even during long actions like resurrections.
#
# v3.0 Changes (Separate Config Window):
#   - MAJOR: Config window now opens as separate 520x450px window
#   - MAJOR: Main UI compacted to 280x250px (was 400x360px)
#   - IMPROVED: Config button changed to compact [C] next to minimize
#   - IMPROVED: All config buttons update instantly without window rebuild
#   - IMPROVED: Position saved separately for main and config windows
#   - IMPROVED: Trapped pouch shows hex serial (like vet kit)
#   - IMPROVED: Pet 4/5 labels repositioned to avoid overlap with skip buttons
#   - FIXED: Config buttons now update visually when hotkeys captured
#   - FIXED: ESC cancel restores button to current binding state
#   - REMOVED: 602 lines of inline config panel code
#
# v2.2 Changes (Per-Pet Hotkeys):
#   - ADDED: Per-pet hotkey system (5 customizable pet hotkeys)
#   - ADDED: Hotkey display buttons on each pet row [F1] or [---]
#   - ADDED: Arrow indicators [>] showing last selected pet
#   - ADDED: Pet Hotkeys config section with capture system
#   - ADDED: Normal press = Follow pet + set priority heal flag
#   - ADDED: Priority heal pet gets healed before tank pet
#
# Features:
#   - Collapsible interface (click [-] to minimize, [+] to expand)
#   - Smart healing priority (self > tank > poisoned > lowest HP)
#   - Potion support (heal/cure) with 10s cooldown tracking
#   - Trapped pouch to break paralyze (auto-use if safe HP)
#   - Auto-targeting for continuous combat (3 tile range)
#   - Pet commands via hotkeys or GUI buttons
#   - ORDER mode sends commands to each pet individually by name
#   - Vet kit support for healing multiple pets at once
#   - Sound alerts for critical HP, pet death, out of bandages
#   - Shared pet list syncs with other tamer scripts
#
# Setup:
#   1. Click [C] to open config panel
#   2. Configure toggles, hotkeys, and pet order mode
#   3. ESC cancels hotkey capture, [DONE] closes panel
#
# Default Hotkeys: TAB (Kill), 1 (Guard), 2 (Follow), PAUSE (toggle)
#
# ============================================================
import API
import time

__version__ = "3.0"

# ============ USER SETTINGS ============
# Item graphics
BANDAGE = 3617                # Bandage item ID
DEBUG = False

# === TIMING (adjust for your DEX) ===
# Reference: 8 - (DEX / 20) seconds
SELF_DELAY = 4.5              # Self bandage time
VET_DELAY = 4.5               # Pet bandage time
REZ_DELAY = 10.0              # Pet resurrection time
CAST_DELAY = 2.5              # Greater Heal spell time
VET_KIT_DELAY = 5.0           # Vet kit cooldown

# === RANGES ===
BANDAGE_RANGE = 2
SPELL_RANGE = 10
MAX_FOLLOW_RANGE = 15

# === HEALTH THRESHOLDS ===
SELF_HEAL_THRESHOLD = 15      # Heal self when missing this many HP
TANK_HP_PERCENT = 50          # Priority heal tank below this %
PET_HP_PERCENT = 90           # Heal pets below this %
VET_KIT_HP_PERCENT = 70       # Vet kit threshold
VET_KIT_THRESHOLD = 2         # Use vet kit when this many pets hurt
VET_KIT_COOLDOWN = 10.0       # Min seconds between vet kit uses

# === COMMANDS ===
MAX_DISTANCE = 10             # Max hostile search range
COMMAND_DELAY = 0.8           # Delay between ordered pet commands
TARGET_TIMEOUT = 3.0          # Target cursor timeout

# === SOUND ALERTS ===
USE_SOUND_ALERTS = True
CRITICAL_HP_PERCENT = 25
SOUND_CRITICAL = 0x1F5
SOUND_PET_DIED = 0x1F6
SOUND_NO_BANDAGES = 0x1F4

# === SHARED PERSISTENCE ===
SHARED_PETS_KEY = "SharedPets_List"
PET_SYNC_INTERVAL = 2.0
LOW_BANDAGE_WARNING = 10
MAX_PETS = 5

# === GUI DIMENSIONS (v2.2 - config panel height increased) ===
WINDOW_WIDTH_NORMAL = 280     # Compact single-column layout
WINDOW_WIDTH_CONFIG = 400     # Config panel same width
COLLAPSED_HEIGHT = 24
EXPANDED_HEIGHT = 250         # Compact layout height
CONFIG_HEIGHT = 1270          # Was 1100 in v2.1 (+170px for Pet Hotkeys)

# === POTIONS ===
POTION_HEAL = 0x0F0C          # Greater Heal
POTION_CURE = 0x0F07          # Greater Cure
POTION_REFRESH = 0x0F0B       # Greater Refresh
POTION_COOLDOWN = 10.0        # Universal potion cooldown

# === TRAPPED POUCH ===
TRAPPED_POUCH_MIN_HP = 30     # Min HP to safely use trapped pouch
AUTO_TARGET_RANGE = 3         # Range for auto-targeting next enemy
# =======================================

# Persistent storage keys
SETTINGS_KEY = "TamerSuite_XY"
CONFIG_XY_KEY = "TamerSuite_ConfigXY"
MAGERY_KEY = "TamerSuite_UseMagery"
REZ_KEY = "TamerSuite_UseRez"
HEALSELF_KEY = "TamerSuite_HealSelf"
TANK_KEY = "TamerSuite_Tank"
VETKIT_KEY = "TamerSuite_VetKitGraphic"
REDS_KEY = "TamerSuite_Reds"
GRAYS_KEY = "TamerSuite_Grays"
MODE_KEY = "TamerSuite_Mode"
SKIPOOR_KEY = "TamerSuite_SkipOOR"
PETACTIVE_KEY = "TamerSuite_PetActive"
POTION_KEY = "TamerSuite_UsePotions"
TRAPPED_POUCH_SERIAL_KEY = "TamerSuite_TrappedPouch"
USE_TRAPPED_POUCH_KEY = "TamerSuite_UseTrappedPouch"
AUTO_TARGET_KEY = "TamerSuite_AutoTarget"
EXPANDED_KEY = "TamerSuite_Expanded"

# Hotkey binding persistence (command hotkeys)
PAUSE_HOTKEY_KEY = "TamerSuite_HK_Pause"
KILL_HOTKEY_KEY = "TamerSuite_HK_Kill"
GUARD_HOTKEY_KEY = "TamerSuite_HK_Guard"
FOLLOW_HOTKEY_KEY = "TamerSuite_HK_Follow"
STAY_HOTKEY_KEY = "TamerSuite_HK_Stay"

# Pet hotkey binding persistence (NEW in v2.2)
PET1_HOTKEY_KEY = "TamerSuite_PetHK_1"
PET2_HOTKEY_KEY = "TamerSuite_PetHK_2"
PET3_HOTKEY_KEY = "TamerSuite_PetHK_3"
PET4_HOTKEY_KEY = "TamerSuite_PetHK_4"
PET5_HOTKEY_KEY = "TamerSuite_PetHK_5"

# ============ HEALER STATE MACHINE ============
# States: idle, healing, following, rezzing, vetkit
HEAL_STATE = "idle"
heal_start_time = 0
heal_target = 0
heal_duration = 0
heal_action_type = ""  # 'heal', 'rez', 'vetkit'

# ============ RUNTIME STATE ============
# Healer
USE_MAGERY = False
USE_REZ = False
HEAL_SELF = True
CURE_POISON = True
SKIP_OUT_OF_RANGE = True
PAUSED = False
TANK_PET = 0
VET_KIT_GRAPHIC = 0
last_vetkit_use = 0
last_no_bandage_warning = 0
NO_BANDAGE_COOLDOWN = 10.0
manual_heal_target = 0

# GUI
is_expanded = True
show_config = False  # Config panel visibility (deprecated - will use separate gump)
config_gump = None  # Separate config window
config_controls = {}  # Store config window button references for direct updates

# Commands
TARGET_REDS = False
TARGET_GRAYS = False
ATTACK_MODE = "ALL"  # "ALL" or "ORDER"

# Potions
USE_POTIONS = True
potion_cooldown_end = 0

# Trapped Pouch
trapped_pouch_serial = 0
use_trapped_pouch = True

# Auto-targeting
auto_target = False
current_attack_target = 0

# Shared
PETS = []
PET_NAMES = {}
PET_ACTIVE = {}  # Track which pets are active in ORDER mode
last_known_pets_str = ""

# Alert tracking
last_critical_alert = 0
last_pet_death_alerts = {}
ALERT_COOLDOWN = 5.0

# Position tracking (main window)
last_known_x = 100
last_known_y = 100
last_position_check = 0

# Position tracking (config window)
config_last_known_x = 150
config_last_known_y = 150
config_last_position_check = 0

# Friend rez
rez_friend_target = 0
rez_friend_active = False
rez_friend_attempts = 0
rez_friend_name = ""
MAX_REZ_ATTEMPTS = 50
REZ_FRIEND_DELAY = 8.0

# Hotkey capture system
capturing_for = None  # "pause", "kill", "guard", "follow", "stay", "pet0"-"pet4", or None
hotkeys = {
    "pause": "PAUSE",
    "kill": "TAB",
    "guard": "1",
    "follow": "2",
    "stay": ""  # Empty = unbound
}

# Pet hotkey system (NEW in v2.2)
pet_hotkeys = ["", "", "", "", ""]  # Empty string = unbound
priority_heal_pet = 0  # Serial of pet flagged for priority heal
last_selected_pet_index = -1  # Which pet row shows [>] arrow

# Journal messages for resurrection detection
JOURNAL_REZ_SUCCESS = [
    "You are able to resurrect your patient",
    "You have resurrected",
    "returns to life"
]

JOURNAL_REZ_FAIL = [
    "You fail to resurrect your patient",
    "That being is not damaged",
    "You cannot perform beneficial acts",
    "That is too far away",
    "Target cannot be seen"
]

# ============ ALL POSSIBLE KEYS ============
ALL_KEYS = [
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
    "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "NUMPAD0", "NUMPAD1", "NUMPAD2", "NUMPAD3", "NUMPAD4",
    "NUMPAD5", "NUMPAD6", "NUMPAD7", "NUMPAD8", "NUMPAD9",
    "TAB", "SPACE", "ENTER", "ESC", "PAUSE", "BACKSPACE",
    "HOME", "END", "PAGEUP", "PAGEDOWN", "INSERT", "DELETE",
    "LEFT", "RIGHT", "UP", "DOWN",
    "MULTIPLY", "ADD", "SUBTRACT", "DIVIDE", "DECIMAL",
]

# ============ UTILITY FUNCTIONS ============
def is_poisoned(mob):
    if not mob:
        return False
    try:
        if hasattr(mob, 'Poisoned') and mob.Poisoned:
            return True
        if hasattr(mob, 'IsPoisoned') and mob.IsPoisoned:
            return True
        return False
    except:
        return False

def is_player_poisoned():
    try:
        player = API.Player
        if player.Poisoned:
            return True
        if hasattr(player, 'IsPoisoned') and player.IsPoisoned:
            return True
        return False
    except:
        return False

def is_player_dead():
    try:
        return API.Player.IsDead
    except:
        return False

def get_mob_name(mob, default="Unknown"):
    if not mob:
        return default
    try:
        return mob.Name if mob.Name else default
    except:
        return default

def get_hp_percent(mob):
    if not mob:
        return 0
    try:
        if mob.HitsMax > 0:
            return int((mob.Hits / mob.HitsMax) * 100)
        return 100
    except:
        return 100

def get_distance(mob):
    if not mob:
        return 999
    try:
        return mob.Distance if hasattr(mob, 'Distance') else 999
    except:
        return 999

def get_bandage_count():
    try:
        if API.FindType(BANDAGE):
            if hasattr(API.Found, 'Amount'):
                return API.Found.Amount
            return -1
        return 0
    except:
        return -1

def check_bandages():
    global last_no_bandage_warning
    if not API.FindType(BANDAGE):
        if time.time() - last_no_bandage_warning < NO_BANDAGE_COOLDOWN:
            return False
        last_no_bandage_warning = time.time()
        API.SysMsg("OUT OF BANDAGES!", 32)
        play_sound_alert(SOUND_NO_BANDAGES)
        return False
    return True

def play_sound_alert(sound_id):
    if not USE_SOUND_ALERTS:
        return
    try:
        if hasattr(API, 'PlaySound'):
            API.PlaySound(sound_id)
    except:
        pass

def check_critical_alerts():
    global last_critical_alert, last_pet_death_alerts
    now = time.time()

    if HEAL_SELF and not is_player_dead():
        try:
            player = API.Player
            hp_pct = int((player.Hits / player.HitsMax) * 100) if player.HitsMax > 0 else 100
            if hp_pct < CRITICAL_HP_PERCENT and now - last_critical_alert > ALERT_COOLDOWN:
                last_critical_alert = now
                play_sound_alert(SOUND_CRITICAL)
        except:
            pass

    for pet in PETS:
        mob = API.FindMobile(pet)
        if mob and mob.IsDead:
            last_alert = last_pet_death_alerts.get(pet, 0)
            if now - last_alert > ALERT_COOLDOWN:
                last_pet_death_alerts[pet] = now
                play_sound_alert(SOUND_PET_DIED)

def clear_stray_cursor():
    try:
        API.CancelPreTarget()
    except:
        pass
    try:
        if API.HasTarget():
            API.CancelTarget()
    except:
        pass

def cancel_all_targets():
    clear_stray_cursor()
    API.Pause(0.1)

def get_potion_count(graphic):
    """Count total potions of given graphic in backpack"""
    try:
        backpack = API.Player.Backpack
        if not backpack:
            return 0

        backpack_serial = backpack.Serial if hasattr(backpack, 'Serial') else 0
        if backpack_serial == 0:
            return 0

        items = API.ItemsInContainer(backpack_serial, True)
        if not items:
            return 0

        total = 0
        for item in items:
            if hasattr(item, 'Graphic') and item.Graphic == graphic:
                if hasattr(item, 'Amount'):
                    total += item.Amount
                else:
                    total += 1

        return total
    except:
        return 0

def potion_ready():
    """Check if 10s cooldown expired"""
    return time.time() >= potion_cooldown_end

def drink_potion(graphic, label):
    """Use potion, start cooldown"""
    global potion_cooldown_end

    if not potion_ready():
        remaining = int(potion_cooldown_end - time.time())
        API.SysMsg("Potion on cooldown: " + str(remaining) + "s", 43)
        return False

    potion = None
    if API.FindType(graphic):
        potion = API.Found

    if not potion:
        API.SysMsg("Out of " + label + "!", 32)
        return False

    try:
        API.UseObject(potion, False)
        potion_cooldown_end = time.time() + POTION_COOLDOWN
        statusLabel.SetText(label + "!")
        return True
    except Exception as e:
        API.SysMsg("Potion error: " + str(e), 32)
        return False

def is_player_paralyzed():
    """Check if player is paralyzed"""
    try:
        player = API.Player
        if hasattr(player, 'IsParalyzed') and player.IsParalyzed:
            return True
        if hasattr(player, 'Paralyzed') and player.Paralyzed:
            return True
        if hasattr(player, 'Frozen') and player.Frozen:
            return True
        return False
    except:
        return False

def use_trapped_pouch():
    """Open trapped pouch to break paralyze (10-20 damage)"""
    global trapped_pouch_serial

    if API.Player.Hits < TRAPPED_POUCH_MIN_HP:
        API.SysMsg("HP too low for trapped pouch! (" + str(API.Player.Hits) + "/" + str(TRAPPED_POUCH_MIN_HP) + ")", 32)
        return False

    if trapped_pouch_serial == 0:
        API.SysMsg("No trapped pouch configured! Use [SET POUCH] button", 43)
        return False

    pouch = API.FindItem(trapped_pouch_serial)
    if not pouch:
        API.SysMsg("Trapped pouch not found!", 32)
        return False

    try:
        API.UseObject(trapped_pouch_serial, False)
        API.SysMsg("Opening trapped pouch to break paralyze!", 68)
        statusLabel.SetText("Trapped Pouch!")
        return True
    except Exception as e:
        API.SysMsg("Trapped pouch error: " + str(e), 32)
        return False

def target_trapped_pouch():
    """Allow user to target which trapped pouch to use"""
    global trapped_pouch_serial

    API.SysMsg("Target your trapped pouch container...", 68)
    cancel_all_targets()

    try:
        target = API.RequestTarget(timeout=10)
        if target:
            item = API.FindItem(target)
            if item:
                trapped_pouch_serial = target
                API.SavePersistentVar(TRAPPED_POUCH_SERIAL_KEY, str(trapped_pouch_serial), API.PersistentVar.Char)
                API.SysMsg("Trapped pouch set! Serial: " + hex(trapped_pouch_serial), 68)
                update_config_pouch_display()
                update_config_gump_state()
            else:
                API.SysMsg("Target not found!", 32)
        else:
            API.SysMsg("Target cancelled", 43)

        clear_stray_cursor()
    except Exception as e:
        API.SysMsg("Target error: " + str(e), 32)
        clear_stray_cursor()

def handle_auto_target():
    """Auto-target next enemy when current dies (continuous combat)"""
    global current_attack_target

    if not auto_target:
        return

    if current_attack_target == 0:
        return

    target = API.FindMobile(current_attack_target)

    target_distance = target.Distance if target and hasattr(target, 'Distance') else 999
    if not target or target.IsDead or target_distance > AUTO_TARGET_RANGE:
        notorieties = [API.Notoriety.Enemy]
        if TARGET_GRAYS:
            notorieties.extend([API.Notoriety.Gray, API.Notoriety.Criminal])
        if TARGET_REDS:
            notorieties.append(API.Notoriety.Murderer)

        next_enemy = API.NearestMobile(notorieties, AUTO_TARGET_RANGE)
        if next_enemy and next_enemy.Serial != API.Player.Serial and not next_enemy.IsDead:
            API.Msg("all kill")
            if API.WaitForTarget(timeout=TARGET_TIMEOUT):
                API.Target(next_enemy.Serial)
                current_attack_target = next_enemy.Serial
                API.HeadMsg("NEXT!", next_enemy.Serial, 68)
                API.SysMsg("Auto-targeting: " + get_mob_name(next_enemy), 68)
        else:
            current_attack_target = 0

# ============ SHARED PET STORAGE (READ/WRITE) ============
def save_pets_to_storage():
    global last_known_pets_str
    if len(PETS) == 0:
        API.SavePersistentVar(SHARED_PETS_KEY, "", API.PersistentVar.Char)
        last_known_pets_str = ""
        return

    pairs = []
    for serial in PETS:
        name = PET_NAMES.get(serial, "Pet")
        active_state = PET_ACTIVE.get(serial, True)
        active_str = "1" if active_state else "0"
        pairs.append(name + ":" + str(serial) + ":" + active_str)

    new_str = "|".join(pairs)
    if new_str != last_known_pets_str:
        API.SavePersistentVar(SHARED_PETS_KEY, new_str, API.PersistentVar.Char)
        last_known_pets_str = new_str

def sync_pets_from_storage():
    global PETS, PET_NAMES, PET_ACTIVE, last_known_pets_str
    stored = API.GetPersistentVar(SHARED_PETS_KEY, "", API.PersistentVar.Char)

    if stored == last_known_pets_str:
        return

    last_known_pets_str = stored

    if not stored:
        PETS = []
        PET_NAMES = {}
        PET_ACTIVE = {}
        return

    PETS = []
    PET_NAMES = {}
    PET_ACTIVE = {}

    pairs = [x for x in stored.split("|") if x]
    for pair in pairs:
        parts = pair.split(":")
        if len(parts) >= 2:
            name = parts[0]
            try:
                serial = int(parts[1])
                active = True
                if len(parts) >= 3:
                    active = (parts[2] == "1")

                PETS.append(serial)
                PET_NAMES[serial] = name
                PET_ACTIVE[serial] = active
            except:
                pass

# ============ HEALING ACTIONS ============
def get_next_heal_action():
    if HEAL_SELF:
        if is_player_poisoned():
            if drink_potion(POTION_CURE, "Cure"):
                return None
        player = API.Player
        if player.Hits < (player.HitsMax - SELF_HEAL_THRESHOLD):
            if USE_POTIONS and potion_ready():
                if drink_potion(POTION_HEAL, "Heal"):
                    return None
            return (API.Player.Serial, "heal_self", SELF_DELAY, True)

    if use_trapped_pouch and is_player_paralyzed():
        if use_trapped_pouch():
            return None

    # Priority heal pet (NEW in v2.2)
    if priority_heal_pet != 0:
        mob = API.FindMobile(priority_heal_pet)
        if mob and not mob.IsDead and get_distance(mob) <= SPELL_RANGE:
            if is_poisoned(mob):
                return (priority_heal_pet, "cure", CAST_DELAY if USE_MAGERY else VET_DELAY, False)
            hp_pct = get_hp_percent(mob)
            if hp_pct < PET_HP_PERCENT:
                return (priority_heal_pet, "heal", CAST_DELAY if USE_MAGERY else VET_DELAY, False)

    if TANK_PET != 0:
        mob = API.FindMobile(TANK_PET)
        if mob and not mob.IsDead and get_distance(mob) <= SPELL_RANGE:
            if is_poisoned(mob):
                return (TANK_PET, "cure", CAST_DELAY if USE_MAGERY else VET_DELAY, False)
            hp_pct = get_hp_percent(mob)
            if hp_pct < TANK_HP_PERCENT:
                return (TANK_PET, "heal", CAST_DELAY if USE_MAGERY else VET_DELAY, False)

    for pet in PETS:
        mob = API.FindMobile(pet)
        if not mob or mob.IsDead:
            continue
        dist = get_distance(mob)
        if SKIP_OUT_OF_RANGE and dist > SPELL_RANGE:
            continue

        if is_poisoned(mob):
            return (pet, "cure", CAST_DELAY if USE_MAGERY else VET_DELAY, False)

    lowest_hp = None
    lowest_pct = 100
    for pet in PETS:
        mob = API.FindMobile(pet)
        if not mob or mob.IsDead:
            continue
        dist = get_distance(mob)
        if SKIP_OUT_OF_RANGE and dist > SPELL_RANGE:
            continue

        hp_pct = get_hp_percent(mob)
        if hp_pct < PET_HP_PERCENT and hp_pct < lowest_pct:
            lowest_hp = pet
            lowest_pct = hp_pct

    if lowest_hp:
        return (lowest_hp, "heal", CAST_DELAY if USE_MAGERY else VET_DELAY, False)

    if VET_KIT_GRAPHIC != 0:
        hurt_count = 0
        for pet in PETS:
            mob = API.FindMobile(pet)
            if not mob or mob.IsDead:
                continue
            hp_pct = get_hp_percent(mob)
            if hp_pct < VET_KIT_HP_PERCENT:
                hurt_count += 1

        if hurt_count >= VET_KIT_THRESHOLD:
            if time.time() - last_vetkit_use > VET_KIT_COOLDOWN:
                return (0, "vetkit", VET_KIT_DELAY, False)

    if USE_REZ:
        for pet in PETS:
            mob = API.FindMobile(pet)
            if mob and mob.IsDead:
                dist = get_distance(mob)
                if dist <= SPELL_RANGE:
                    return (pet, "rez", REZ_DELAY, False)

    return None

def start_heal_action(target, action_type, duration, is_self):
    global HEAL_STATE, heal_start_time, heal_target, heal_duration, heal_action_type

    if action_type == "vetkit":
        if not API.FindType(VET_KIT_GRAPHIC):
            API.SysMsg("Vet kit not found!", 32)
            return
        try:
            API.UseObject(API.Found, False)
            API.HeadMsg("Vet Kit!", API.Player.Serial, 68)
            global last_vetkit_use
            last_vetkit_use = time.time()
            HEAL_STATE = "vetkit"
            heal_start_time = time.time()
            heal_duration = duration
            heal_action_type = action_type
            statusLabel.SetText("Vet Kit!")
        except Exception as e:
            API.SysMsg("Vet kit error: " + str(e), 32)
        return

    if is_self:
        if not check_bandages():
            return
        try:
            cancel_all_targets()
            API.PreTarget(target, "beneficial")
            API.Pause(0.1)
            if API.FindType(BANDAGE):
                API.UseObject(API.Found, False)
                API.Pause(0.1)
            API.CancelPreTarget()
            API.HeadMsg("Healing!", target, 68)

            HEAL_STATE = "healing"
            heal_start_time = time.time()
            heal_target = target
            heal_duration = duration
            heal_action_type = action_type
            statusLabel.SetText("Healing Self")
        except Exception as e:
            API.SysMsg("Heal error: " + str(e), 32)
            clear_stray_cursor()
        return

    mob = API.FindMobile(target)
    if not mob:
        return

    if action_type == "rez":
        try:
            cancel_all_targets()
            API.PreTarget(target, "beneficial")
            API.Pause(0.1)
            if API.FindType(BANDAGE):
                API.UseObject(API.Found, False)
                API.Pause(0.1)
            API.CancelPreTarget()
            API.HeadMsg("Rezzing!", target, 38)

            HEAL_STATE = "rezzing"
            heal_start_time = time.time()
            heal_target = target
            heal_duration = duration
            heal_action_type = action_type
            name = get_mob_name(mob)
            statusLabel.SetText("Rezzing: " + name)
        except Exception as e:
            API.SysMsg("Rez error: " + str(e), 32)
            clear_stray_cursor()
        return

    if action_type == "cure":
        if USE_MAGERY:
            try:
                cancel_all_targets()
                API.PreTarget(target, "beneficial")
                API.Pause(0.1)
                API.Cast("Cure")
                API.Pause(0.1)
                API.CancelPreTarget()
                API.HeadMsg("Curing!", target, 68)

                HEAL_STATE = "healing"
                heal_start_time = time.time()
                heal_target = target
                heal_duration = duration
                heal_action_type = action_type
                name = get_mob_name(mob)
                statusLabel.SetText("Curing: " + name)
            except Exception as e:
                API.SysMsg("Cure error: " + str(e), 32)
                clear_stray_cursor()
        else:
            if not check_bandages():
                return
            try:
                cancel_all_targets()
                API.PreTarget(target, "beneficial")
                API.Pause(0.1)
                if API.FindType(BANDAGE):
                    API.UseObject(API.Found, False)
                    API.Pause(0.1)
                API.CancelPreTarget()
                API.HeadMsg("Curing!", target, 68)

                HEAL_STATE = "healing"
                heal_start_time = time.time()
                heal_target = target
                heal_duration = duration
                heal_action_type = action_type
                name = get_mob_name(mob)
                statusLabel.SetText("Curing: " + name)
            except Exception as e:
                API.SysMsg("Heal error: " + str(e), 32)
                clear_stray_cursor()
        return

    if action_type == "heal":
        if USE_MAGERY:
            try:
                cancel_all_targets()
                API.PreTarget(target, "beneficial")
                API.Pause(0.1)
                API.Cast("Greater Heal")
                API.Pause(0.1)
                API.CancelPreTarget()
                API.HeadMsg("Healing!", target, 68)

                HEAL_STATE = "healing"
                heal_start_time = time.time()
                heal_target = target
                heal_duration = duration
                heal_action_type = action_type
                name = get_mob_name(mob)
                statusLabel.SetText("Healing: " + name)
            except Exception as e:
                API.SysMsg("Heal error: " + str(e), 32)
                clear_stray_cursor()
        else:
            if not check_bandages():
                return
            try:
                cancel_all_targets()
                API.PreTarget(target, "beneficial")
                API.Pause(0.1)
                if API.FindType(BANDAGE):
                    API.UseObject(API.Found, False)
                    API.Pause(0.1)
                API.CancelPreTarget()
                API.HeadMsg("Healing!", target, 68)

                HEAL_STATE = "healing"
                heal_start_time = time.time()
                heal_target = target
                heal_duration = duration
                heal_action_type = action_type
                name = get_mob_name(mob)
                statusLabel.SetText("Healing: " + name)
            except Exception as e:
                API.SysMsg("Heal error: " + str(e), 32)
                clear_stray_cursor()

def check_heal_complete():
    global HEAL_STATE

    if HEAL_STATE == "idle":
        return

    elapsed = time.time() - heal_start_time
    if elapsed >= heal_duration:
        HEAL_STATE = "idle"
        statusLabel.SetText("Running" if not PAUSED else "PAUSED")

# ============ FRIEND REZ LOGIC ============
def attempt_friend_rez():
    global rez_friend_active, rez_friend_attempts

    if rez_friend_target == 0:
        rez_friend_active = False
        statusLabel.SetText("Running")
        return

    mob = API.FindMobile(rez_friend_target)
    if not mob:
        API.SysMsg("Friend not found. Rez cancelled.", 43)
        rez_friend_active = False
        statusLabel.SetText("Running")
        return

    if not mob.IsDead:
        API.SysMsg("Friend is alive! Rez complete.", 68)
        rez_friend_active = False
        statusLabel.SetText("Running")
        return

    if rez_friend_attempts >= MAX_REZ_ATTEMPTS:
        API.SysMsg("Max attempts reached. Rez cancelled.", 32)
        rez_friend_active = False
        statusLabel.SetText("Running")
        return

    if not check_bandages():
        rez_friend_active = False
        statusLabel.SetText("Running")
        return

    try:
        cancel_all_targets()
        API.PreTarget(rez_friend_target, "beneficial")
        API.Pause(0.1)
        if API.FindType(BANDAGE):
            API.UseObject(API.Found, False)
            API.Pause(0.1)
        API.CancelPreTarget()

        rez_friend_attempts += 1
        API.Pause(REZ_FRIEND_DELAY)
    except Exception as e:
        API.SysMsg("Friend rez error: " + str(e), 32)
        clear_stray_cursor()

# ============ COMMANDS ============
def should_use_order_mode():
    """Check if ORDER mode should be used (either explicitly set OR any pet is inactive)"""
    if ATTACK_MODE == "ORDER":
        return True
    # Auto-trigger ORDER mode if any pet is set to skip
    for serial in PETS:
        if not PET_ACTIVE.get(serial, True):
            return True
    return False

def all_kill_manual():
    global current_attack_target
    if not should_use_order_mode():
        API.Msg("all kill")
        API.SysMsg("All Kill - select target", 68)
    else:
        API.SysMsg("Target enemy for ordered attack...", 32)
        cancel_all_targets()
        try:
            target = API.RequestTarget(timeout=TARGET_TIMEOUT)
            if target:
                current_attack_target = target
                execute_order_mode("all kill", target)
            else:
                API.SysMsg("Target cancelled", 43)
            clear_stray_cursor()
        except Exception as e:
            API.SysMsg("Target error: " + str(e), 32)
            clear_stray_cursor()

def all_kill_hotkey():
    global current_attack_target
    if not TARGET_REDS and not TARGET_GRAYS:
        API.SysMsg("Enable [REDS] or [GRAYS] first!", 43)
        return

    notorieties = [API.Notoriety.Enemy]
    if TARGET_GRAYS:
        notorieties.extend([API.Notoriety.Gray, API.Notoriety.Criminal])
    if TARGET_REDS:
        notorieties.append(API.Notoriety.Murderer)

    enemy = API.NearestMobile(notorieties, MAX_DISTANCE)

    if not enemy or enemy.Serial == API.Player.Serial:
        # Fallback to manual targeting
        API.SysMsg("No hostile found - select target manually", 53)
        if not should_use_order_mode():
            API.Msg("all kill")
        else:
            try:
                target = API.RequestTarget(timeout=TARGET_TIMEOUT)
                if not target:
                    API.SysMsg("No target selected", 32)
                    return
                current_attack_target = target
                execute_order_mode("all kill", target)
            except:
                API.SysMsg("Target cancelled", 43)
        return

    current_attack_target = enemy.Serial

    if not should_use_order_mode():
        API.Msg("all kill")
        if API.WaitForTarget(timeout=TARGET_TIMEOUT):
            API.Target(enemy.Serial)
            API.Attack(enemy.Serial)
            API.HeadMsg("KILL!", enemy.Serial, 32)
            API.SysMsg("All kill: " + get_mob_name(enemy), 68)
        else:
            API.SysMsg("No target cursor", 32)
    else:
        execute_order_mode("all kill", enemy.Serial)

def all_follow():
    if not should_use_order_mode():
        API.Msg("all follow me")
    else:
        execute_order_mode("all follow me", 0)

def all_guard():
    if not should_use_order_mode():
        API.Msg("all guard me")
    else:
        execute_order_mode("all guard me", 0)

def all_stay():
    if not should_use_order_mode():
        API.Msg("all stay")
    else:
        execute_order_mode("all stay", 0)

def execute_order_mode(base_cmd, attack_target):
    active_pets = [s for s in PETS if PET_ACTIVE.get(s, True)]

    if not active_pets:
        API.SysMsg("No active pets in ORDER mode!", 43)
        return

    for i, serial in enumerate(active_pets):
        name = PET_NAMES.get(serial, "Pet")
        mob = API.FindMobile(serial)
        if not mob:
            continue
        dist = get_distance(mob)
        if dist > MAX_FOLLOW_RANGE:
            continue

        if i > 0:
            API.Pause(COMMAND_DELAY)

        cmd = base_cmd.replace("all", name)
        API.Msg(cmd)
        API.SysMsg("  " + str(i+1) + ". " + name + " -> " + base_cmd.replace("all ", ""), 88)

        if attack_target != 0:
            if API.WaitForTarget(timeout=TARGET_TIMEOUT):
                API.Target(attack_target)
                API.HeadMsg("KILL!", attack_target, 32)
            API.Pause(0.2)

def say_bank():
    API.Msg("bank")

def say_balance():
    API.Msg("balance")

# ============ PET MANAGEMENT ============
def add_pet():
    API.SysMsg("Target a pet to add...", 68)
    cancel_all_targets()

    try:
        target = API.RequestTarget(timeout=10)
        if target:
            mob = API.FindMobile(target)
            if mob:
                name = get_mob_name(mob, "Pet")
                if target not in PETS:
                    PETS.append(target)
                    PET_NAMES[target] = name
                    PET_ACTIVE[target] = True
                    save_pets_to_storage()
                    API.SysMsg("Added: " + name, 68)
                else:
                    API.SysMsg("Already in list: " + name, 43)
            else:
                API.SysMsg("Target not found!", 32)
        else:
            API.SysMsg("Target cancelled", 43)
        clear_stray_cursor()
    except Exception as e:
        API.SysMsg("Target error: " + str(e), 32)
        clear_stray_cursor()

def remove_pet():
    API.SysMsg("Target a pet to remove...", 32)
    cancel_all_targets()

    try:
        target = API.RequestTarget(timeout=10)
        if target:
            if target in PETS:
                name = PET_NAMES.get(target, "Pet")
                PETS.remove(target)
                if target in PET_NAMES:
                    del PET_NAMES[target]
                if target in PET_ACTIVE:
                    del PET_ACTIVE[target]
                save_pets_to_storage()
                API.SysMsg("Removed: " + name, 68)
            else:
                API.SysMsg("Not in list!", 43)
        else:
            API.SysMsg("Target cancelled", 43)
        clear_stray_cursor()
    except Exception as e:
        API.SysMsg("Target error: " + str(e), 32)
        clear_stray_cursor()

def clear_all_pets():
    global PETS, PET_NAMES, PET_ACTIVE
    PETS = []
    PET_NAMES = {}
    PET_ACTIVE = {}
    save_pets_to_storage()
    API.SysMsg("Pet list cleared", 90)

def make_pet_click_callback(idx):
    def callback():
        if idx >= len(PETS):
            return
        serial = PETS[idx]
        mob = API.FindMobile(serial)
        if not mob:
            API.SysMsg("Pet not found!", 32)
            return

        name = get_mob_name(mob)
        if mob.IsDead:
            API.SysMsg(name + " is dead!", 32)
            return

        API.Msg(name + " follow me")
        API.HeadMsg("Follow!", serial, 68)
        API.Pause(0.3)

        global manual_heal_target
        manual_heal_target = serial
        API.SysMsg("Following + priority heal: " + name, 68)
    return callback

def toggle_pet_active(idx):
    """Toggle pet active state in ORDER mode"""
    if idx >= len(PETS):
        return

    serial = PETS[idx]
    current_state = PET_ACTIVE.get(serial, True)
    PET_ACTIVE[serial] = not current_state
    save_pets_to_storage()
    update_pet_order_display()
    update_pet_arrow_display()
    update_config_gump_state()

# ============ GUI CALLBACKS ============
def toggle_expand():
    global is_expanded
    is_expanded = not is_expanded
    API.SavePersistentVar(EXPANDED_KEY, str(is_expanded), API.PersistentVar.Char)

    if is_expanded:
        expand_window()
    else:
        collapse_window()

def expand_window():
    expandBtn.SetText("[-]")

    # Status row
    pauseBtn.IsVisible = True
    modeBtn.IsVisible = True
    statusLabel.IsVisible = True

    # Action buttons
    rezFriendBtn.IsVisible = True
    allKillBtn.IsVisible = True
    followAllBtn.IsVisible = True
    guardAllBtn.IsVisible = True
    stayAllBtn.IsVisible = True

    # Pets section
    petsTitle.IsVisible = True
    addBtn.IsVisible = True
    removeBtn.IsVisible = True
    clearBtn.IsVisible = True
    for lbl in pet_labels:
        lbl.IsVisible = True

    # Resize window
    x = gump.GetX()
    y = gump.GetY()
    gump.SetRect(x, y, WINDOW_WIDTH_NORMAL, EXPANDED_HEIGHT)
    bg.SetRect(0, 0, WINDOW_WIDTH_NORMAL, EXPANDED_HEIGHT)

def collapse_window():
    expandBtn.SetText("[+]")

    # Status row
    pauseBtn.IsVisible = False
    modeBtn.IsVisible = False
    statusLabel.IsVisible = False

    # Action buttons
    rezFriendBtn.IsVisible = False
    allKillBtn.IsVisible = False
    followAllBtn.IsVisible = False
    guardAllBtn.IsVisible = False
    stayAllBtn.IsVisible = False

    # Pets section
    petsTitle.IsVisible = False
    addBtn.IsVisible = False
    removeBtn.IsVisible = False
    clearBtn.IsVisible = False
    for lbl in pet_labels:
        lbl.IsVisible = False

    # Resize window
    x = gump.GetX()
    y = gump.GetY()
    gump.SetRect(x, y, WINDOW_WIDTH_NORMAL, COLLAPSED_HEIGHT)
    bg.SetRect(0, 0, WINDOW_WIDTH_NORMAL, COLLAPSED_HEIGHT)

def toggle_config():
    """Open separate config window (NEW v2.2 - uses separate gump)"""
    global config_gump
    if config_gump is None:
        build_config_gump()
    else:
        close_config_gump()

def show_config_panel():
    """Legacy function - inline config panel removed in v2.2"""
    pass

def hide_config_panel():
    """Legacy function - inline config panel removed in v2.2"""
    pass

# ============ NEW CONFIG WINDOW (SEPARATE GUMP) ============
def build_config_gump():
    """Create and display the separate config window (520x440px)"""
    global config_gump, config_controls, config_last_known_x, config_last_known_y

    # Don't create if already open
    if config_gump is not None:
        return

    # Clear button references
    config_controls = {}

    # Load saved position or use default (offset from main window)
    saved_pos = API.GetPersistentVar(CONFIG_XY_KEY, "150,150", API.PersistentVar.Char)
    pos_parts = saved_pos.split(',')
    cfg_x, cfg_y = int(pos_parts[0]), int(pos_parts[1])

    # Initialize position tracking
    config_last_known_x = cfg_x
    config_last_known_y = cfg_y

    # Create config gump
    config_gump = API.Gumps.CreateGump()
    config_gump.SetRect(cfg_x, cfg_y, 520, 450)

    # Main background
    cfg_bg = API.Gumps.CreateGumpColorBox(0.9, "#1a1a2e")
    cfg_bg.SetRect(0, 0, 520, 450)
    config_gump.Add(cfg_bg)

    # Title (no separate bar - integrated into background)
    title = API.Gumps.CreateGumpTTFLabel("Tamer Suite Configuration v3.0", 13, "#ffaa00")
    title.SetPos(100, 8)
    config_gump.Add(title)

    # === SECTION 1: TOP ROW (3 columns) ===
    y_start = 30

    # --- COLUMN 1: HEALING & PRIORITY (X: 8, W: 160) ---
    col1_x = 8
    col1_y = y_start

    # Section box
    heal_box = API.Gumps.CreateGumpColorBox(0.9, "#0f0f1a")
    heal_box.SetRect(col1_x, col1_y, 160, 150)
    config_gump.Add(heal_box)

    # Header
    heal_hdr = API.Gumps.CreateGumpTTFLabel("HEALING", 10, "#00ff88")
    heal_hdr.SetPos(col1_x + 45, col1_y + 3)
    config_gump.Add(heal_hdr)

    col1_y += 16

    # Magery toggle
    mag_lbl = API.Gumps.CreateGumpTTFLabel("Magery:", 9, "#dddddd")
    mag_lbl.SetPos(col1_x + 4, col1_y + 3)
    config_gump.Add(mag_lbl)

    config_controls["magery_band"] = API.Gumps.CreateSimpleButton("[BAND]", 55, 18)
    config_controls["magery_band"].SetPos(col1_x + 50, col1_y)
    config_controls["magery_band"].SetBackgroundHue(68 if not USE_MAGERY else 90)
    API.Gumps.AddControlOnClick(config_controls["magery_band"], lambda: toggle_magery_config(False))
    config_gump.Add(config_controls["magery_band"])

    config_controls["magery_mage"] = API.Gumps.CreateSimpleButton("[MAGE]", 52, 18)
    config_controls["magery_mage"].SetPos(col1_x + 105, col1_y)
    config_controls["magery_mage"].SetBackgroundHue(66 if USE_MAGERY else 90)
    API.Gumps.AddControlOnClick(config_controls["magery_mage"], lambda: toggle_magery_config(True))
    config_gump.Add(config_controls["magery_mage"])

    col1_y += 17

    # Heal Self
    hs_lbl = API.Gumps.CreateGumpTTFLabel("Heal Self:", 9, "#dddddd")
    hs_lbl.SetPos(col1_x + 4, col1_y + 3)
    config_gump.Add(hs_lbl)

    config_controls["heal_self_off"] = API.Gumps.CreateSimpleButton("[OFF]", 50, 18)
    config_controls["heal_self_off"].SetPos(col1_x + 60, col1_y)
    config_controls["heal_self_off"].SetBackgroundHue(32 if not HEAL_SELF else 90)
    API.Gumps.AddControlOnClick(config_controls["heal_self_off"], lambda: toggle_self(False))
    config_gump.Add(config_controls["heal_self_off"])

    config_controls["heal_self_on"] = API.Gumps.CreateSimpleButton("[ON]", 47, 18)
    config_controls["heal_self_on"].SetPos(col1_x + 110, col1_y)
    config_controls["heal_self_on"].SetBackgroundHue(68 if HEAL_SELF else 90)
    API.Gumps.AddControlOnClick(config_controls["heal_self_on"], lambda: toggle_self(True))
    config_gump.Add(config_controls["heal_self_on"])

    col1_y += 17

    # Pet Rez
    pr_lbl = API.Gumps.CreateGumpTTFLabel("Pet Rez:", 9, "#dddddd")
    pr_lbl.SetPos(col1_x + 4, col1_y + 3)
    config_gump.Add(pr_lbl)

    config_controls["pet_rez_off"] = API.Gumps.CreateSimpleButton("[OFF]", 50, 18)
    config_controls["pet_rez_off"].SetPos(col1_x + 60, col1_y)
    config_controls["pet_rez_off"].SetBackgroundHue(32 if not USE_REZ else 90)
    API.Gumps.AddControlOnClick(config_controls["pet_rez_off"], lambda: toggle_rez(False))
    config_gump.Add(config_controls["pet_rez_off"])

    config_controls["pet_rez_on"] = API.Gumps.CreateSimpleButton("[ON]", 47, 18)
    config_controls["pet_rez_on"].SetPos(col1_x + 110, col1_y)
    config_controls["pet_rez_on"].SetBackgroundHue(68 if USE_REZ else 90)
    API.Gumps.AddControlOnClick(config_controls["pet_rez_on"], lambda: toggle_rez(True))
    config_gump.Add(config_controls["pet_rez_on"])

    col1_y += 17

    # Skip OOR
    so_lbl = API.Gumps.CreateGumpTTFLabel("Skip OOR:", 9, "#dddddd")
    so_lbl.SetPos(col1_x + 4, col1_y + 3)
    config_gump.Add(so_lbl)

    config_controls["skip_oor_off"] = API.Gumps.CreateSimpleButton("[OFF]", 50, 18)
    config_controls["skip_oor_off"].SetPos(col1_x + 60, col1_y)
    config_controls["skip_oor_off"].SetBackgroundHue(32 if not SKIP_OUT_OF_RANGE else 90)
    API.Gumps.AddControlOnClick(config_controls["skip_oor_off"], lambda: toggle_skip(False))
    config_gump.Add(config_controls["skip_oor_off"])

    config_controls["skip_oor_on"] = API.Gumps.CreateSimpleButton("[ON]", 47, 18)
    config_controls["skip_oor_on"].SetPos(col1_x + 110, col1_y)
    config_controls["skip_oor_on"].SetBackgroundHue(68 if SKIP_OUT_OF_RANGE else 90)
    API.Gumps.AddControlOnClick(config_controls["skip_oor_on"], lambda: toggle_skip(True))
    config_gump.Add(config_controls["skip_oor_on"])

    col1_y += 17

    # Potions
    pot_lbl = API.Gumps.CreateGumpTTFLabel("Potions:", 9, "#dddddd")
    pot_lbl.SetPos(col1_x + 4, col1_y + 3)
    config_gump.Add(pot_lbl)

    config_controls["potions_off"] = API.Gumps.CreateSimpleButton("[OFF]", 50, 18)
    config_controls["potions_off"].SetPos(col1_x + 60, col1_y)
    config_controls["potions_off"].SetBackgroundHue(32 if not USE_POTIONS else 90)
    API.Gumps.AddControlOnClick(config_controls["potions_off"], lambda: toggle_potions(False))
    config_gump.Add(config_controls["potions_off"])

    config_controls["potions_on"] = API.Gumps.CreateSimpleButton("[ON]", 47, 18)
    config_controls["potions_on"].SetPos(col1_x + 110, col1_y)
    config_controls["potions_on"].SetBackgroundHue(68 if USE_POTIONS else 90)
    API.Gumps.AddControlOnClick(config_controls["potions_on"], lambda: toggle_potions(True))
    config_gump.Add(config_controls["potions_on"])

    col1_y += 20

    # Tank Priority
    tank_lbl = API.Gumps.CreateGumpTTFLabel("Tank Priority:", 9, "#dddddd")
    tank_lbl.SetPos(col1_x + 4, col1_y)
    config_gump.Add(tank_lbl)

    col1_y += 12
    tank_name = get_tank_name() if TANK_PET != 0 else "None"
    tank_val = API.Gumps.CreateGumpTTFLabel(tank_name, 9, "#ffaaff" if TANK_PET != 0 else "#aaaaaa")
    tank_val.SetPos(col1_x + 4, col1_y)
    config_gump.Add(tank_val)

    col1_y += 14
    tank_set = API.Gumps.CreateSimpleButton("[SET]", 50, 16)
    tank_set.SetPos(col1_x + 4, col1_y)
    tank_set.SetBackgroundHue(38)
    API.Gumps.AddControlOnClick(tank_set, set_tank)
    config_gump.Add(tank_set)

    tank_clr = API.Gumps.CreateSimpleButton("[CLEAR]", 50, 16)
    tank_clr.SetPos(col1_x + 57, col1_y)
    tank_clr.SetBackgroundHue(90)
    API.Gumps.AddControlOnClick(tank_clr, clear_tank)
    config_gump.Add(tank_clr)

    # --- COLUMN 2: COMMANDS (X: 176, W: 160) ---
    col2_x = 176
    col2_y = y_start

    # Section box
    cmd_box = API.Gumps.CreateGumpColorBox(0.9, "#0f0f1a")
    cmd_box.SetRect(col2_x, col2_y, 160, 114)
    config_gump.Add(cmd_box)

    # Header
    cmd_hdr = API.Gumps.CreateGumpTTFLabel("COMMANDS", 10, "#ff6666")
    cmd_hdr.SetPos(col2_x + 40, col2_y + 3)
    config_gump.Add(cmd_hdr)

    col2_y += 16

    # REDS
    red_lbl = API.Gumps.CreateGumpTTFLabel("REDS:", 9, "#dddddd")
    red_lbl.SetPos(col2_x + 4, col2_y + 3)
    config_gump.Add(red_lbl)

    config_controls["reds_off"] = API.Gumps.CreateSimpleButton("[OFF]", 50, 18)
    config_controls["reds_off"].SetPos(col2_x + 60, col2_y)
    config_controls["reds_off"].SetBackgroundHue(32 if not TARGET_REDS else 90)
    API.Gumps.AddControlOnClick(config_controls["reds_off"], lambda: toggle_reds(False))
    config_gump.Add(config_controls["reds_off"])

    config_controls["reds_on"] = API.Gumps.CreateSimpleButton("[ON]", 47, 18)
    config_controls["reds_on"].SetPos(col2_x + 110, col2_y)
    config_controls["reds_on"].SetBackgroundHue(68 if TARGET_REDS else 90)
    API.Gumps.AddControlOnClick(config_controls["reds_on"], lambda: toggle_reds(True))
    config_gump.Add(config_controls["reds_on"])

    col2_y += 17

    # GRAYS
    gray_lbl = API.Gumps.CreateGumpTTFLabel("GRAYS:", 9, "#dddddd")
    gray_lbl.SetPos(col2_x + 4, col2_y + 3)
    config_gump.Add(gray_lbl)

    config_controls["grays_off"] = API.Gumps.CreateSimpleButton("[OFF]", 50, 18)
    config_controls["grays_off"].SetPos(col2_x + 60, col2_y)
    config_controls["grays_off"].SetBackgroundHue(32 if not TARGET_GRAYS else 90)
    API.Gumps.AddControlOnClick(config_controls["grays_off"], lambda: toggle_grays(False))
    config_gump.Add(config_controls["grays_off"])

    config_controls["grays_on"] = API.Gumps.CreateSimpleButton("[ON]", 47, 18)
    config_controls["grays_on"].SetPos(col2_x + 110, col2_y)
    config_controls["grays_on"].SetBackgroundHue(68 if TARGET_GRAYS else 90)
    API.Gumps.AddControlOnClick(config_controls["grays_on"], lambda: toggle_grays(True))
    config_gump.Add(config_controls["grays_on"])

    col2_y += 17

    # Mode
    mode_lbl = API.Gumps.CreateGumpTTFLabel("Mode:", 9, "#dddddd")
    mode_lbl.SetPos(col2_x + 4, col2_y + 3)
    config_gump.Add(mode_lbl)

    config_controls["mode_all"] = API.Gumps.CreateSimpleButton("[ALL]", 50, 18)
    config_controls["mode_all"].SetPos(col2_x + 60, col2_y)
    config_controls["mode_all"].SetBackgroundHue(68 if ATTACK_MODE == "ALL" else 90)
    API.Gumps.AddControlOnClick(config_controls["mode_all"], toggle_mode)
    config_gump.Add(config_controls["mode_all"])

    config_controls["mode_order"] = API.Gumps.CreateSimpleButton("[ORDER]", 47, 18)
    config_controls["mode_order"].SetPos(col2_x + 110, col2_y)
    config_controls["mode_order"].SetBackgroundHue(68 if ATTACK_MODE == "ORDER" else 90)
    API.Gumps.AddControlOnClick(config_controls["mode_order"], toggle_mode)
    config_gump.Add(config_controls["mode_order"])

    col2_y += 17

    # Auto-Target
    at_lbl = API.Gumps.CreateGumpTTFLabel("Auto-Target:", 9, "#dddddd")
    at_lbl.SetPos(col2_x + 4, col2_y + 3)
    config_gump.Add(at_lbl)

    config_controls["auto_target_off"] = API.Gumps.CreateSimpleButton("[OFF]", 50, 18)
    config_controls["auto_target_off"].SetPos(col2_x + 60, col2_y)
    config_controls["auto_target_off"].SetBackgroundHue(32 if not auto_target else 90)
    API.Gumps.AddControlOnClick(config_controls["auto_target_off"], lambda: toggle_auto_target(False))
    config_gump.Add(config_controls["auto_target_off"])

    config_controls["auto_target_on"] = API.Gumps.CreateSimpleButton("[ON]", 47, 18)
    config_controls["auto_target_on"].SetPos(col2_x + 110, col2_y)
    config_controls["auto_target_on"].SetBackgroundHue(68 if auto_target else 90)
    API.Gumps.AddControlOnClick(config_controls["auto_target_on"], lambda: toggle_auto_target(True))
    config_gump.Add(config_controls["auto_target_on"])

    # --- COLUMN 3: EQUIPMENT (X: 344, W: 168) ---
    col3_x = 344
    col3_y = y_start

    # Section box
    eq_box = API.Gumps.CreateGumpColorBox(0.9, "#0f0f1a")
    eq_box.SetRect(col3_x, col3_y, 168, 165)
    config_gump.Add(eq_box)

    # Header
    eq_hdr = API.Gumps.CreateGumpTTFLabel("EQUIPMENT", 10, "#ffaa00")
    eq_hdr.SetPos(col3_x + 40, col3_y + 3)
    config_gump.Add(eq_hdr)

    col3_y += 16

    # Vet Kit
    vk_lbl = API.Gumps.CreateGumpTTFLabel("Vet Kit:", 9, "#dddddd")
    vk_lbl.SetPos(col3_x + 4, col3_y)
    config_gump.Add(vk_lbl)

    col3_y += 12
    vk_val_text = "#" + str(VET_KIT_GRAPHIC) if VET_KIT_GRAPHIC != 0 else "Not Set"
    vk_val = API.Gumps.CreateGumpTTFLabel(vk_val_text, 9, "#aaffaa" if VET_KIT_GRAPHIC != 0 else "#aaaaaa")
    vk_val.SetPos(col3_x + 4, col3_y)
    config_gump.Add(vk_val)

    col3_y += 14
    vk_set = API.Gumps.CreateSimpleButton("[SET]", 50, 16)
    vk_set.SetPos(col3_x + 4, col3_y)
    vk_set.SetBackgroundHue(68)
    API.Gumps.AddControlOnClick(vk_set, set_vetkit)
    config_gump.Add(vk_set)

    vk_clr = API.Gumps.CreateSimpleButton("[CLEAR]", 50, 16)
    vk_clr.SetPos(col3_x + 57, col3_y)
    vk_clr.SetBackgroundHue(90)
    API.Gumps.AddControlOnClick(vk_clr, clear_vetkit)
    config_gump.Add(vk_clr)

    col3_y += 22

    # Trapped Pouch
    tp_lbl = API.Gumps.CreateGumpTTFLabel("Pouch:", 9, "#dddddd")
    tp_lbl.SetPos(col3_x + 4, col3_y)
    config_gump.Add(tp_lbl)

    col3_y += 12
    tp_val_text = hex(trapped_pouch_serial) if trapped_pouch_serial != 0 else "Not Set"
    tp_val = API.Gumps.CreateGumpTTFLabel(tp_val_text, 9, "#aaffaa" if trapped_pouch_serial != 0 else "#aaaaaa")
    tp_val.SetPos(col3_x + 4, col3_y)
    config_gump.Add(tp_val)

    col3_y += 14
    tp_set = API.Gumps.CreateSimpleButton("[SET]", 50, 16)
    tp_set.SetPos(col3_x + 4, col3_y)
    tp_set.SetBackgroundHue(43)
    API.Gumps.AddControlOnClick(tp_set, on_set_trapped_pouch)
    config_gump.Add(tp_set)

    tp_clr = API.Gumps.CreateSimpleButton("[CLEAR]", 50, 16)
    tp_clr.SetPos(col3_x + 57, col3_y)
    tp_clr.SetBackgroundHue(90)
    API.Gumps.AddControlOnClick(tp_clr, clear_trapped_pouch)
    config_gump.Add(tp_clr)

    col3_y += 21

    # Use Pouch
    up_lbl = API.Gumps.CreateGumpTTFLabel("Use Pouch:", 9, "#dddddd")
    up_lbl.SetPos(col3_x + 4, col3_y + 3)
    config_gump.Add(up_lbl)

    config_controls["use_pouch_off"] = API.Gumps.CreateSimpleButton("[OFF]", 50, 18)
    config_controls["use_pouch_off"].SetPos(col3_x + 60, col3_y)
    config_controls["use_pouch_off"].SetBackgroundHue(32 if not use_trapped_pouch else 90)
    API.Gumps.AddControlOnClick(config_controls["use_pouch_off"], lambda: toggle_use_trapped_pouch(False))
    config_gump.Add(config_controls["use_pouch_off"])

    config_controls["use_pouch_on"] = API.Gumps.CreateSimpleButton("[ON]", 50, 18)
    config_controls["use_pouch_on"].SetPos(col3_x + 113, col3_y)
    config_controls["use_pouch_on"].SetBackgroundHue(68 if use_trapped_pouch else 90)
    API.Gumps.AddControlOnClick(config_controls["use_pouch_on"], lambda: toggle_use_trapped_pouch(True))
    config_gump.Add(config_controls["use_pouch_on"])

    # === SECTION 2: PET HOTKEYS ===
    sec2_y = 188

    pk_box = API.Gumps.CreateGumpColorBox(0.9, "#0f0f1a")
    pk_box.SetRect(8, sec2_y, 504, 75)
    config_gump.Add(pk_box)

    pk_hdr = API.Gumps.CreateGumpTTFLabel("PET HOTKEYS", 10, "#ffaa00")
    pk_hdr.SetPos(200, sec2_y + 3)
    config_gump.Add(pk_hdr)

    pk_row_y = sec2_y + 18

    # Left column (pets 1-3)
    for i in range(3):
        if i < len(PETS):
            serial = PETS[i]
            name = PET_NAMES.get(serial, "Pet")
            lbl_text = "Pet " + str(i+1) + " (" + name + "):"
        else:
            lbl_text = "Pet " + str(i+1) + ":"

        pk_lbl = API.Gumps.CreateGumpTTFLabel(lbl_text, 9, "#dddddd")
        pk_lbl.SetPos(15, pk_row_y + 3)
        config_gump.Add(pk_lbl)

        hk_text = "[" + (pet_hotkeys[i] if i < len(pet_hotkeys) and pet_hotkeys[i] else "---") + "]"
        config_controls["pet_hk_" + str(i)] = API.Gumps.CreateSimpleButton(hk_text, 40, 18)
        config_controls["pet_hk_" + str(i)].SetPos(160, pk_row_y)
        config_controls["pet_hk_" + str(i)].SetBackgroundHue(68 if (i < len(pet_hotkeys) and pet_hotkeys[i]) else 90)
        API.Gumps.AddControlOnClick(config_controls["pet_hk_" + str(i)], lambda idx=i: clear_pet_hotkey(idx))
        config_gump.Add(config_controls["pet_hk_" + str(i)])

        pk_set = API.Gumps.CreateSimpleButton("[SET]", 35, 18)
        pk_set.SetPos(203, pk_row_y)
        pk_set.SetBackgroundHue(43)
        API.Gumps.AddControlOnClick(pk_set, lambda idx=i: start_capture_pet_hotkey(idx))
        config_gump.Add(pk_set)

        pk_row_y += 18

    # Right column (pets 4-5)
    pk_row_y = sec2_y + 18
    for i in range(3, 5):
        if i < len(PETS):
            serial = PETS[i]
            name = PET_NAMES.get(serial, "Pet")
            lbl_text = "Pet " + str(i+1) + " (" + name + "):"
        else:
            lbl_text = "Pet " + str(i+1) + ":"

        pk_lbl = API.Gumps.CreateGumpTTFLabel(lbl_text, 9, "#dddddd")
        pk_lbl.SetPos(265, pk_row_y + 3)
        config_gump.Add(pk_lbl)

        hk_text = "[" + (pet_hotkeys[i] if i < len(pet_hotkeys) and pet_hotkeys[i] else "---") + "]"
        config_controls["pet_hk_" + str(i)] = API.Gumps.CreateSimpleButton(hk_text, 40, 18)
        config_controls["pet_hk_" + str(i)].SetPos(410, pk_row_y)
        config_controls["pet_hk_" + str(i)].SetBackgroundHue(68 if (i < len(pet_hotkeys) and pet_hotkeys[i]) else 90)
        API.Gumps.AddControlOnClick(config_controls["pet_hk_" + str(i)], lambda idx=i: clear_pet_hotkey(idx))
        config_gump.Add(config_controls["pet_hk_" + str(i)])

        pk_set = API.Gumps.CreateSimpleButton("[SET]", 35, 18)
        pk_set.SetPos(453, pk_row_y)
        pk_set.SetBackgroundHue(43)
        API.Gumps.AddControlOnClick(pk_set, lambda idx=i: start_capture_pet_hotkey(idx))
        config_gump.Add(pk_set)

        pk_row_y += 18

    # === SECTION 3: ORDER MODE ===
    sec3_y = 271

    om_box = API.Gumps.CreateGumpColorBox(0.9, "#0f0f1a")
    om_box.SetRect(8, sec3_y, 504, 75)
    config_gump.Add(om_box)

    om_hdr = API.Gumps.CreateGumpTTFLabel("ORDER MODE (any skip = individual cmds)", 10, "#66aaff")
    om_hdr.SetPos(115, sec3_y + 3)
    config_gump.Add(om_hdr)

    om_row_y = sec3_y + 18

    # Left column (pets 1-3)
    for i in range(3):
        if i < len(PETS):
            serial = PETS[i]
            name = PET_NAMES.get(serial, "Pet")
            lbl_text = "Pet " + str(i+1) + " (" + name + "):"
            is_active = PET_ACTIVE.get(serial, True)
        else:
            lbl_text = "Pet " + str(i+1) + ":"
            is_active = True

        om_lbl = API.Gumps.CreateGumpTTFLabel(lbl_text, 9, "#dddddd")
        om_lbl.SetPos(15, om_row_y + 3)
        config_gump.Add(om_lbl)

        om_act = API.Gumps.CreateSimpleButton("[ACTIVE]", 60, 18)
        om_act.SetPos(160, om_row_y)
        om_act.SetBackgroundHue(68 if is_active else 32)
        API.Gumps.AddControlOnClick(om_act, lambda idx=i: toggle_pet_active(idx))
        config_gump.Add(om_act)

        om_skip = API.Gumps.CreateSimpleButton("[SKIP]", 60, 18)
        om_skip.SetPos(223, om_row_y)
        om_skip.SetBackgroundHue(68 if not is_active else 32)
        API.Gumps.AddControlOnClick(om_skip, lambda idx=i: toggle_pet_active(idx))
        config_gump.Add(om_skip)

        om_row_y += 18

    # Right column (pets 4-5)
    om_row_y = sec3_y + 18
    for i in range(3, 5):
        if i < len(PETS):
            serial = PETS[i]
            name = PET_NAMES.get(serial, "Pet")
            lbl_text = "Pet " + str(i+1) + " (" + name + "):"
            is_active = PET_ACTIVE.get(serial, True)
        else:
            lbl_text = "Pet " + str(i+1) + ":"
            is_active = True

        om_lbl = API.Gumps.CreateGumpTTFLabel(lbl_text, 9, "#dddddd")
        om_lbl.SetPos(295, om_row_y + 3)
        config_gump.Add(om_lbl)

        om_act = API.Gumps.CreateSimpleButton("[ACTIVE]", 60, 18)
        om_act.SetPos(390, om_row_y)
        om_act.SetBackgroundHue(68 if is_active else 32)
        API.Gumps.AddControlOnClick(om_act, lambda idx=i: toggle_pet_active(idx))
        config_gump.Add(om_act)

        om_skip = API.Gumps.CreateSimpleButton("[SKIP]", 60, 18)
        om_skip.SetPos(452, om_row_y)
        om_skip.SetBackgroundHue(68 if not is_active else 32)
        API.Gumps.AddControlOnClick(om_skip, lambda idx=i: toggle_pet_active(idx))
        config_gump.Add(om_skip)

        om_row_y += 18

    # === SECTION 4: COMMAND HOTKEYS ===
    sec4_y = 354

    ch_box = API.Gumps.CreateGumpColorBox(0.9, "#0f0f1a")
    ch_box.SetRect(8, sec4_y, 504, 78)
    config_gump.Add(ch_box)

    ch_hdr = API.Gumps.CreateGumpTTFLabel("COMMAND HOTKEYS", 10, "#ff8800")
    ch_hdr.SetPos(185, sec4_y + 3)
    config_gump.Add(ch_hdr)

    # Row 1
    cmd_y = sec4_y + 18

    # Pause
    ch_pause_lbl = API.Gumps.CreateGumpTTFLabel("Pause:", 9, "#dddddd")
    ch_pause_lbl.SetPos(15, cmd_y + 3)
    config_gump.Add(ch_pause_lbl)

    pause_hk_text = "[" + (hotkeys.get("pause") or "---") + "]"
    config_controls["pause_hk_display"] = API.Gumps.CreateSimpleButton(pause_hk_text, 50, 18)
    config_controls["pause_hk_display"].SetPos(60, cmd_y)
    config_controls["pause_hk_display"].SetBackgroundHue(68 if hotkeys.get("pause") else 90)
    config_gump.Add(config_controls["pause_hk_display"])

    ch_pause_set = API.Gumps.CreateSimpleButton("[SET]", 35, 18)
    ch_pause_set.SetPos(113, cmd_y)
    ch_pause_set.SetBackgroundHue(43)
    API.Gumps.AddControlOnClick(ch_pause_set, start_capture_pause)
    config_gump.Add(ch_pause_set)

    # Kill
    ch_kill_lbl = API.Gumps.CreateGumpTTFLabel("Kill:", 9, "#dddddd")
    ch_kill_lbl.SetPos(170, cmd_y + 3)
    config_gump.Add(ch_kill_lbl)

    kill_hk_text = "[" + (hotkeys.get("kill") or "---") + "]"
    config_controls["kill_hk_display"] = API.Gumps.CreateSimpleButton(kill_hk_text, 40, 18)
    config_controls["kill_hk_display"].SetPos(200, cmd_y)
    config_controls["kill_hk_display"].SetBackgroundHue(68 if hotkeys.get("kill") else 90)
    config_gump.Add(config_controls["kill_hk_display"])

    ch_kill_set = API.Gumps.CreateSimpleButton("[SET]", 35, 18)
    ch_kill_set.SetPos(243, cmd_y)
    ch_kill_set.SetBackgroundHue(43)
    API.Gumps.AddControlOnClick(ch_kill_set, start_capture_kill)
    config_gump.Add(ch_kill_set)

    # Guard
    ch_guard_lbl = API.Gumps.CreateGumpTTFLabel("Guard:", 9, "#dddddd")
    ch_guard_lbl.SetPos(300, cmd_y + 3)
    config_gump.Add(ch_guard_lbl)

    guard_hk_text = "[" + (hotkeys.get("guard") or "---") + "]"
    config_controls["guard_hk_display"] = API.Gumps.CreateSimpleButton(guard_hk_text, 40, 18)
    config_controls["guard_hk_display"].SetPos(340, cmd_y)
    config_controls["guard_hk_display"].SetBackgroundHue(68 if hotkeys.get("guard") else 90)
    config_gump.Add(config_controls["guard_hk_display"])

    ch_guard_set = API.Gumps.CreateSimpleButton("[SET]", 35, 18)
    ch_guard_set.SetPos(383, cmd_y)
    ch_guard_set.SetBackgroundHue(43)
    API.Gumps.AddControlOnClick(ch_guard_set, start_capture_guard)
    config_gump.Add(ch_guard_set)

    # Row 2
    cmd_y += 20

    # Follow
    ch_follow_lbl = API.Gumps.CreateGumpTTFLabel("Follow:", 9, "#dddddd")
    ch_follow_lbl.SetPos(15, cmd_y + 3)
    config_gump.Add(ch_follow_lbl)

    follow_hk_text = "[" + (hotkeys.get("follow") or "---") + "]"
    config_controls["follow_hk_display"] = API.Gumps.CreateSimpleButton(follow_hk_text, 40, 18)
    config_controls["follow_hk_display"].SetPos(60, cmd_y)
    config_controls["follow_hk_display"].SetBackgroundHue(68 if hotkeys.get("follow") else 90)
    config_gump.Add(config_controls["follow_hk_display"])

    ch_follow_set = API.Gumps.CreateSimpleButton("[SET]", 35, 18)
    ch_follow_set.SetPos(103, cmd_y)
    ch_follow_set.SetBackgroundHue(43)
    API.Gumps.AddControlOnClick(ch_follow_set, start_capture_follow)
    config_gump.Add(ch_follow_set)

    # Stay
    ch_stay_lbl = API.Gumps.CreateGumpTTFLabel("Stay:", 9, "#dddddd")
    ch_stay_lbl.SetPos(160, cmd_y + 3)
    config_gump.Add(ch_stay_lbl)

    stay_hk_text = "[" + (hotkeys.get("stay") or "---") + "]"
    config_controls["stay_hk_display"] = API.Gumps.CreateSimpleButton(stay_hk_text, 40, 18)
    config_controls["stay_hk_display"].SetPos(195, cmd_y)
    config_controls["stay_hk_display"].SetBackgroundHue(68 if hotkeys.get("stay") else 90)
    config_gump.Add(config_controls["stay_hk_display"])

    ch_stay_set = API.Gumps.CreateSimpleButton("[SET]", 35, 18)
    ch_stay_set.SetPos(238, cmd_y)
    ch_stay_set.SetBackgroundHue(43)
    API.Gumps.AddControlOnClick(ch_stay_set, start_capture_stay)
    config_gump.Add(ch_stay_set)

    # === CLOSE BUTTON ===
    close_btn = API.Gumps.CreateSimpleButton("[CLOSE]", 100, 22)
    close_btn.SetPos(210, 420)
    close_btn.SetBackgroundHue(68)
    API.Gumps.AddControlOnClick(close_btn, close_config_gump)
    config_gump.Add(close_btn)

    # Register close callback
    API.Gumps.AddControlOnDisposed(config_gump, on_config_closed)

    # Display the gump
    API.Gumps.AddGump(config_gump)

    API.SysMsg("Config window opened", 68)

def close_config_gump():
    """Close the config window"""
    global config_gump, config_controls, config_last_known_x, config_last_known_y
    if config_gump is not None:
        # Always use tracked position - gump is being disposed so GetX/GetY returns 0
        if config_last_known_x >= 0 and config_last_known_y >= 0:
            API.SavePersistentVar(CONFIG_XY_KEY, str(config_last_known_x) + "," + str(config_last_known_y), API.PersistentVar.Char)

        config_gump.Dispose()
        config_gump = None
        config_controls = {}

def on_config_closed():
    """Called when config window is closed"""
    global config_gump, config_controls, config_last_known_x, config_last_known_y

    # Always use tracked position - gump is being disposed so GetX/GetY returns 0
    if config_last_known_x >= 0 and config_last_known_y >= 0:
        API.SavePersistentVar(CONFIG_XY_KEY, str(config_last_known_x) + "," + str(config_last_known_y), API.PersistentVar.Char)

    # Clear references
    config_gump = None
    config_controls = {}
    API.SysMsg("Config window closed", 90)

def update_config_gump_state():
    """Update config window button states WITHOUT rebuilding"""
    if config_gump is None:
        return  # Window not open, nothing to update

    c = config_controls

    # Magery toggle
    if "magery_band" in c:
        c["magery_band"].SetBackgroundHue(68 if not USE_MAGERY else 90)
    if "magery_mage" in c:
        c["magery_mage"].SetBackgroundHue(66 if USE_MAGERY else 90)

    # Heal Self toggle
    if "heal_self_off" in c:
        c["heal_self_off"].SetBackgroundHue(32 if not HEAL_SELF else 90)
    if "heal_self_on" in c:
        c["heal_self_on"].SetBackgroundHue(68 if HEAL_SELF else 90)

    # Pet Rez toggle
    if "pet_rez_off" in c:
        c["pet_rez_off"].SetBackgroundHue(32 if not USE_REZ else 90)
    if "pet_rez_on" in c:
        c["pet_rez_on"].SetBackgroundHue(68 if USE_REZ else 90)

    # Skip OOR toggle
    if "skip_oor_off" in c:
        c["skip_oor_off"].SetBackgroundHue(32 if not SKIP_OUT_OF_RANGE else 90)
    if "skip_oor_on" in c:
        c["skip_oor_on"].SetBackgroundHue(68 if SKIP_OUT_OF_RANGE else 90)

    # Potions toggle
    if "potions_off" in c:
        c["potions_off"].SetBackgroundHue(32 if not USE_POTIONS else 90)
    if "potions_on" in c:
        c["potions_on"].SetBackgroundHue(68 if USE_POTIONS else 90)

    # REDS toggle
    if "reds_off" in c:
        c["reds_off"].SetBackgroundHue(32 if not TARGET_REDS else 90)
    if "reds_on" in c:
        c["reds_on"].SetBackgroundHue(68 if TARGET_REDS else 90)

    # GRAYS toggle
    if "grays_off" in c:
        c["grays_off"].SetBackgroundHue(32 if not TARGET_GRAYS else 90)
    if "grays_on" in c:
        c["grays_on"].SetBackgroundHue(68 if TARGET_GRAYS else 90)

    # Mode toggle
    if "mode_all" in c:
        c["mode_all"].SetBackgroundHue(68 if ATTACK_MODE == "ALL" else 90)
    if "mode_order" in c:
        c["mode_order"].SetBackgroundHue(68 if ATTACK_MODE == "ORDER" else 90)

    # Auto-Target toggle
    if "auto_target_off" in c:
        c["auto_target_off"].SetBackgroundHue(32 if not auto_target else 90)
    if "auto_target_on" in c:
        c["auto_target_on"].SetBackgroundHue(68 if auto_target else 90)

    # Use Pouch toggle
    if "use_pouch_off" in c:
        c["use_pouch_off"].SetBackgroundHue(32 if not use_trapped_pouch else 90)
    if "use_pouch_on" in c:
        c["use_pouch_on"].SetBackgroundHue(68 if use_trapped_pouch else 90)

def toggle_magery_config(use_mage):
    """Toggle magery mode from config window"""
    global USE_MAGERY
    USE_MAGERY = use_mage
    API.SavePersistentVar(MAGERY_KEY, str(USE_MAGERY), API.PersistentVar.Char)
    update_config_gump_state()

def get_tank_name():
    """Get tank pet name for display"""
    if TANK_PET == 0:
        return "None"
    mob = API.FindMobile(TANK_PET)
    if mob:
        return get_mob_name(mob)
    return "Unknown"

# ============ EXISTING FUNCTIONS ============
def toggle_magery():
    global USE_MAGERY
    USE_MAGERY = not USE_MAGERY
    API.SavePersistentVar(MAGERY_KEY, str(USE_MAGERY), API.PersistentVar.Char)
    update_config_gump_state()

def toggle_self(state):
    global HEAL_SELF
    HEAL_SELF = state
    API.SavePersistentVar(HEALSELF_KEY, str(HEAL_SELF), API.PersistentVar.Char)
    update_config_healer_display()
    update_config_gump_state()

def toggle_rez(state):
    global USE_REZ
    USE_REZ = state
    API.SavePersistentVar(REZ_KEY, str(USE_REZ), API.PersistentVar.Char)
    update_config_healer_display()
    update_config_gump_state()

def toggle_skip(state):
    global SKIP_OUT_OF_RANGE
    SKIP_OUT_OF_RANGE = state
    API.SavePersistentVar(SKIPOOR_KEY, str(SKIP_OUT_OF_RANGE), API.PersistentVar.Char)
    update_config_healer_display()
    update_config_gump_state()

def toggle_reds(state):
    global TARGET_REDS
    TARGET_REDS = state
    API.SavePersistentVar(REDS_KEY, str(TARGET_REDS), API.PersistentVar.Char)
    update_config_cmd_display()
    update_config_gump_state()

def toggle_grays(state):
    global TARGET_GRAYS
    TARGET_GRAYS = state
    API.SavePersistentVar(GRAYS_KEY, str(TARGET_GRAYS), API.PersistentVar.Char)
    update_config_cmd_display()
    update_config_gump_state()

def toggle_potions(state):
    global USE_POTIONS
    USE_POTIONS = state
    API.SavePersistentVar(POTION_KEY, str(USE_POTIONS), API.PersistentVar.Char)
    update_config_cmd_display()
    update_config_gump_state()

def toggle_auto_target(state):
    global auto_target
    auto_target = state
    API.SavePersistentVar(AUTO_TARGET_KEY, str(auto_target), API.PersistentVar.Char)
    update_config_cmd_display()
    update_config_gump_state()

def toggle_use_trapped_pouch(state):
    global use_trapped_pouch
    use_trapped_pouch = state
    API.SavePersistentVar(USE_TRAPPED_POUCH_KEY, str(use_trapped_pouch), API.PersistentVar.Char)
    update_config_cmd_display()
    update_config_gump_state()

def toggle_pause():
    global PAUSED
    PAUSED = not PAUSED
    pauseBtn.SetBackgroundHue(32 if PAUSED else 90)
    statusLabel.SetText("PAUSED" if PAUSED else "Running")

def toggle_mode():
    global ATTACK_MODE
    ATTACK_MODE = "ORDER" if ATTACK_MODE == "ALL" else "ALL"
    API.SavePersistentVar(MODE_KEY, ATTACK_MODE, API.PersistentVar.Char)
    modeBtn.SetText("[" + ATTACK_MODE + "]")
    modeBtn.SetBackgroundHue(66 if ATTACK_MODE == "ORDER" else 68)
    update_config_gump_state()

def set_tank():
    global TANK_PET
    API.SysMsg("Target your tank pet...", 38)
    cancel_all_targets()

    try:
        target = API.RequestTarget(timeout=10)
        if target:
            mob = API.FindMobile(target)
            if mob:
                TANK_PET = target
                API.SavePersistentVar(TANK_KEY, str(TANK_PET), API.PersistentVar.Char)
                name = get_mob_name(mob)
                API.SysMsg("Tank set: " + name, 68)
                update_tank_display()
                update_config_tank_display()
                update_config_gump_state()
            else:
                API.SysMsg("Target not found!", 32)
        else:
            API.SysMsg("Target cancelled", 43)
        clear_stray_cursor()
    except Exception as e:
        API.SysMsg("Target error: " + str(e), 32)
        clear_stray_cursor()

def clear_tank():
    global TANK_PET
    TANK_PET = 0
    API.SavePersistentVar(TANK_KEY, "0", API.PersistentVar.Char)
    API.SysMsg("Tank cleared", 90)
    update_tank_display()
    update_config_tank_display()
    update_config_gump_state()

def set_vetkit():
    global VET_KIT_GRAPHIC
    API.SysMsg("Target your vet kit...", 68)
    cancel_all_targets()

    try:
        target = API.RequestTarget(timeout=10)
        if target:
            item = API.FindItem(target)
            if item:
                VET_KIT_GRAPHIC = item.Graphic if hasattr(item, 'Graphic') else 0
                API.SavePersistentVar(VETKIT_KEY, str(VET_KIT_GRAPHIC), API.PersistentVar.Char)
                API.SysMsg("Vet kit set! Graphic: " + hex(VET_KIT_GRAPHIC), 68)
                update_vetkit_display()
                update_config_vetkit_display()
                update_config_gump_state()
            else:
                API.SysMsg("Target not found!", 32)
        else:
            API.SysMsg("Target cancelled", 43)
        clear_stray_cursor()
    except Exception as e:
        API.SysMsg("Target error: " + str(e), 32)
        clear_stray_cursor()

def clear_vetkit():
    global VET_KIT_GRAPHIC
    VET_KIT_GRAPHIC = 0
    API.SavePersistentVar(VETKIT_KEY, "0", API.PersistentVar.Char)
    API.SysMsg("Vet kit cleared", 90)
    update_vetkit_display()
    update_config_vetkit_display()
    update_config_gump_state()

def on_set_trapped_pouch():
    target_trapped_pouch()

def clear_trapped_pouch():
    global trapped_pouch_serial
    trapped_pouch_serial = 0
    API.SavePersistentVar(TRAPPED_POUCH_SERIAL_KEY, "0", API.PersistentVar.Char)
    API.SysMsg("Trapped pouch cleared", 90)
    update_config_pouch_display()
    update_config_gump_state()

def toggle_rez_friend():
    global rez_friend_active, rez_friend_target, rez_friend_attempts, rez_friend_name

    if rez_friend_active:
        rez_friend_active = False
        rez_friend_target = 0
        rez_friend_attempts = 0
        API.SysMsg("Friend rez cancelled", 43)
        statusLabel.SetText("Running")
        return

    API.SysMsg("Target friend to resurrect...", 38)
    cancel_all_targets()

    try:
        target = API.RequestTarget(timeout=10)
        if target:
            mob = API.FindMobile(target)
            if mob:
                rez_friend_target = target
                rez_friend_name = get_mob_name(mob, "Friend")
                rez_friend_attempts = 0
                rez_friend_active = True
                API.SysMsg("Rezzing " + rez_friend_name + " continuously...", 68)
            else:
                API.SysMsg("Target not found!", 32)
        else:
            API.SysMsg("Target cancelled", 43)
        clear_stray_cursor()
    except Exception as e:
        API.SysMsg("Target error: " + str(e), 32)
        clear_stray_cursor()

# ============ HOTKEY CAPTURE SYSTEM ============
def make_key_handler(key_name):
    def handler():
        global capturing_for, priority_heal_pet, last_selected_pet_index

        if capturing_for is not None:
            if key_name == "ESC":
                # Restore button to current hotkey state
                if capturing_for in ["pause", "kill", "guard", "follow", "stay"]:
                    btn_key = capturing_for + "_hk_display"
                    current_key = hotkeys.get(capturing_for, "")
                    if btn_key in config_controls:
                        config_controls[btn_key].SetText("[" + (current_key or "---") + "]")
                        config_controls[btn_key].SetBackgroundHue(68 if current_key else 90)
                elif capturing_for.startswith("pet"):
                    pet_index = int(capturing_for[3])
                    btn_key = "pet_hk_" + str(pet_index)
                    current_key = pet_hotkeys[pet_index] if pet_index < len(pet_hotkeys) else ""
                    if btn_key in config_controls:
                        config_controls[btn_key].SetText("[" + (current_key or "---") + "]")
                        config_controls[btn_key].SetBackgroundHue(68 if current_key else 90)

                API.SysMsg("Hotkey capture cancelled", 90)
                capturing_for = None
                update_config_gump_state()
                return

            # Command hotkey capture
            if capturing_for in ["pause", "kill", "guard", "follow", "stay"]:
                hotkeys[capturing_for] = key_name
                save_hotkey(capturing_for, key_name)

                # Update button directly in config window
                btn_key = capturing_for + "_hk_display"
                if btn_key in config_controls:
                    config_controls[btn_key].SetText("[" + key_name + "]")
                    config_controls[btn_key].SetBackgroundHue(68)

                update_config_gump_state()
                API.SysMsg(capturing_for.capitalize() + " bound to: " + key_name, 68)
                capturing_for = None
                return

            # Pet hotkey capture (NEW v2.2)
            if capturing_for.startswith("pet"):
                pet_index = int(capturing_for[3])  # Extract index from "pet0", "pet1", etc.
                pet_hotkeys[pet_index] = key_name
                save_pet_hotkeys()

                # Update button directly in config window
                btn_key = "pet_hk_" + str(pet_index)
                if btn_key in config_controls:
                    config_controls[btn_key].SetText("[" + key_name + "]")
                    config_controls[btn_key].SetBackgroundHue(68)

                update_pet_hotkey_main_display()
                update_config_gump_state()
                API.SysMsg("Pet " + str(pet_index + 1) + " bound to: " + key_name, 68)
                capturing_for = None
                return

        # Not capturing - execute action if this key is bound
        # Check command hotkeys
        for cmd, bound_key in hotkeys.items():
            if bound_key == key_name:
                if cmd == "pause":
                    toggle_pause()
                elif cmd == "kill":
                    all_kill_hotkey()
                elif cmd == "guard":
                    all_guard()
                elif cmd == "follow":
                    all_follow()
                elif cmd == "stay":
                    all_stay()
                return

        # Check pet hotkeys (NEW v2.2)
        for i in range(5):
            if pet_hotkeys[i] == key_name:
                execute_pet_hotkey(i)
                return

    return handler

def start_capture_pause():
    global capturing_for
    capturing_for = "pause"
    if "pause_hk_display" in config_controls:
        config_controls["pause_hk_display"].SetBackgroundHue(38)
        config_controls["pause_hk_display"].SetText("[Listening...]")
    API.SysMsg("Press any key to bind to Pause (ESC cancel)...", 38)

def start_capture_kill():
    global capturing_for
    capturing_for = "kill"
    if "kill_hk_display" in config_controls:
        config_controls["kill_hk_display"].SetBackgroundHue(38)
        config_controls["kill_hk_display"].SetText("[Listening...]")
    API.SysMsg("Press any key to bind to Kill (ESC cancel)...", 38)

def start_capture_guard():
    global capturing_for
    capturing_for = "guard"
    if "guard_hk_display" in config_controls:
        config_controls["guard_hk_display"].SetBackgroundHue(38)
        config_controls["guard_hk_display"].SetText("[Listening...]")
    API.SysMsg("Press any key to bind to Guard (ESC cancel)...", 38)

def start_capture_follow():
    global capturing_for
    capturing_for = "follow"
    if "follow_hk_display" in config_controls:
        config_controls["follow_hk_display"].SetBackgroundHue(38)
        config_controls["follow_hk_display"].SetText("[Listening...]")
    API.SysMsg("Press any key to bind to Follow (ESC cancel)...", 38)

def start_capture_stay():
    global capturing_for
    capturing_for = "stay"
    if "stay_hk_display" in config_controls:
        config_controls["stay_hk_display"].SetBackgroundHue(38)
        config_controls["stay_hk_display"].SetText("[Listening...]")
    API.SysMsg("Press any key to bind to Stay (ESC cancel)...", 38)

# ============ PET HOTKEY CAPTURE (NEW v2.2) ============
def start_capture_pet_hotkey(pet_index):
    """Start listening for a key to bind to pet N (0-4)"""
    global capturing_for
    capturing_for = "pet" + str(pet_index)

    btn_key = "pet_hk_" + str(pet_index)
    if btn_key in config_controls:
        config_controls[btn_key].SetBackgroundHue(38)
        config_controls[btn_key].SetText("[Listening...]")

    API.SysMsg("Press any key to bind to Pet " + str(pet_index + 1) + " (ESC cancels)...", 38)

def clear_pet_hotkey(pet_index):
    """Unbind hotkey from pet N (0-4)"""
    global pet_hotkeys

    old_key = pet_hotkeys[pet_index]
    pet_hotkeys[pet_index] = ""
    save_pet_hotkeys()
    update_pet_hotkey_config_display()
    update_pet_hotkey_main_display()
    update_config_gump_state()

    API.SysMsg("Pet " + str(pet_index + 1) + " hotkey cleared (was: " + old_key + ")", 90)

def execute_pet_hotkey(pet_index):
    """Execute pet hotkey action (normal press = follow + heal priority)"""
    global priority_heal_pet, last_selected_pet_index

    if pet_index >= len(PETS):
        API.SysMsg("No pet in slot " + str(pet_index + 1) + "!", 43)
        return

    serial = PETS[pet_index]
    mob = API.FindMobile(serial)

    if not mob:
        API.SysMsg("Pet not found!", 32)
        return

    name = PET_NAMES.get(serial, "Pet")

    # Follow the pet
    API.Msg(name + " follow me")

    # Set as priority heal target
    priority_heal_pet = serial
    last_selected_pet_index = pet_index

    # Update arrow indicators
    update_pet_arrow_display()

    API.SysMsg("Following " + name + " (priority heal enabled)", 68)

def save_hotkey(cmd, key):
    if cmd == "pause":
        API.SavePersistentVar(PAUSE_HOTKEY_KEY, key, API.PersistentVar.Char)
    elif cmd == "kill":
        API.SavePersistentVar(KILL_HOTKEY_KEY, key, API.PersistentVar.Char)
    elif cmd == "guard":
        API.SavePersistentVar(GUARD_HOTKEY_KEY, key, API.PersistentVar.Char)
    elif cmd == "follow":
        API.SavePersistentVar(FOLLOW_HOTKEY_KEY, key, API.PersistentVar.Char)
    elif cmd == "stay":
        API.SavePersistentVar(STAY_HOTKEY_KEY, key, API.PersistentVar.Char)

def load_hotkeys():
    hotkeys["pause"] = API.GetPersistentVar(PAUSE_HOTKEY_KEY, "PAUSE", API.PersistentVar.Char)
    hotkeys["kill"] = API.GetPersistentVar(KILL_HOTKEY_KEY, "TAB", API.PersistentVar.Char)
    hotkeys["guard"] = API.GetPersistentVar(GUARD_HOTKEY_KEY, "1", API.PersistentVar.Char)
    hotkeys["follow"] = API.GetPersistentVar(FOLLOW_HOTKEY_KEY, "2", API.PersistentVar.Char)
    hotkeys["stay"] = API.GetPersistentVar(STAY_HOTKEY_KEY, "", API.PersistentVar.Char)

def save_pet_hotkeys():
    """Save pet hotkey bindings to persistence (NEW v2.2)"""
    keys = [PET1_HOTKEY_KEY, PET2_HOTKEY_KEY, PET3_HOTKEY_KEY, PET4_HOTKEY_KEY, PET5_HOTKEY_KEY]
    for i in range(5):
        value = pet_hotkeys[i] if i < len(pet_hotkeys) else ""
        API.SavePersistentVar(keys[i], value, API.PersistentVar.Char)

def load_pet_hotkeys():
    """Load pet hotkey bindings from persistence (NEW v2.2)"""
    global pet_hotkeys

    keys = [PET1_HOTKEY_KEY, PET2_HOTKEY_KEY, PET3_HOTKEY_KEY, PET4_HOTKEY_KEY, PET5_HOTKEY_KEY]
    pet_hotkeys = []

    for key in keys:
        value = API.GetPersistentVar(key, "", API.PersistentVar.Char)
        pet_hotkeys.append(value)

def update_config_buttons():
    """Legacy function - inline config panel removed in v2.2"""
    pass

def update_hotkey_label():
    # Hotkey label removed from compact main UI (now only in config window)
    pass

# ============ DISPLAY UPDATES ============
def update_pet_display():
    for i in range(MAX_PETS):
        if i < len(PETS):
            serial = PETS[i]
            name = PET_NAMES.get(serial, "Pet")
            mob = API.FindMobile(serial)

            if mob:
                hp_str = str(mob.Hits) + "/" + str(mob.HitsMax)
                status = " [DEAD]" if mob.IsDead else ""
                poison_mark = " [P]" if is_poisoned(mob) else ""
                btn_text = str(i+1) + ". " + name + " (" + hp_str + ")" + poison_mark + status
                hue = 32 if mob.IsDead else (53 if is_poisoned(mob) else 68)
            else:
                btn_text = str(i+1) + ". " + name + " [???]"
                hue = 90

            pet_labels[i].SetText(btn_text)
            pet_labels[i].SetBackgroundHue(hue)
        else:
            pet_labels[i].SetText(str(i+1) + ". ---")
            pet_labels[i].SetBackgroundHue(90)

def update_pet_hotkey_main_display():
    """Update hotkey display buttons on main UI (NEW v2.2)"""
    try:
        displays = [petHkDisplay1, petHkDisplay2, petHkDisplay3, petHkDisplay4, petHkDisplay5]

        for i in range(5):
            hotkey = pet_hotkeys[i] if i < len(pet_hotkeys) else ""

            if hotkey:
                text = "[" + hotkey + "]"
                hue = 68  # Green = bound
            else:
                text = "[---]"
                hue = 90  # Gray = unbound

            displays[i].SetText(text)
            displays[i].SetBackgroundHue(hue)
    except:
        pass

def update_pet_arrow_display():
    """Update arrow indicators to show pet active/skip status (NEW v2.2)"""
    try:
        arrows = [petArrow1, petArrow2, petArrow3, petArrow4, petArrow5]

        for i in range(5):
            if i < len(PETS):
                serial = PETS[i]
                is_active = PET_ACTIVE.get(serial, True)

                if is_active:
                    text = "[ON]"
                    hue = 68  # Green = active
                else:
                    text = "[--]"
                    hue = 32  # Red = skipped
            else:
                text = "[ ]"
                hue = 90  # Gray = empty slot

            arrows[i].SetText(text)
            arrows[i].SetBackgroundHue(hue)
    except:
        pass

def update_pet_hotkey_config_display():
    """Legacy function - inline config panel removed in v2.2"""
    pass

def update_pet_order_display():
    """Legacy function - inline config panel removed in v2.2"""
    pass

def update_tank_display():
    # No main UI display in v2.1 (removed)
    pass

def update_config_tank_display():
    """Legacy function - inline config panel removed in v2.2"""
    pass

def update_vetkit_display():
    # No main UI display in v2.1 (removed)
    pass

def update_config_vetkit_display():
    """Legacy function - inline config panel removed in v2.2"""
    pass

def update_config_pouch_display():
    """Legacy function - inline config panel removed in v2.2"""
    pass

def update_bandage_display():
    count = get_bandage_count()
    if count == -1:
        bandageLabel.SetText("Bandages: ???")
    elif count == 0:
        bandageLabel.SetText("Bandages: OUT!")
    else:
        bandageLabel.SetText("Bandages: " + str(count))

def update_potion_display():
    # No main UI display in v2.1 (removed)
    pass

def update_config_potion_display():
    """Legacy function - inline config panel removed in v2.2"""
    pass

def update_rez_friend_display():
    # No main UI display in v2.1 (removed)
    pass

def update_config_healer_display():
    """Legacy function - inline config panel removed in v2.2"""
    pass

def update_config_cmd_display():
    """Legacy function - inline config panel removed in v2.2"""
    pass

# ============ PERSISTENCE ============
def load_settings():
    global USE_MAGERY, USE_REZ, HEAL_SELF, TANK_PET, VET_KIT_GRAPHIC
    global TARGET_REDS, TARGET_GRAYS, ATTACK_MODE, SKIP_OUT_OF_RANGE
    global USE_POTIONS, trapped_pouch_serial, use_trapped_pouch, auto_target
    global is_expanded

    USE_MAGERY = API.GetPersistentVar(MAGERY_KEY, "False", API.PersistentVar.Char) == "True"
    USE_REZ = API.GetPersistentVar(REZ_KEY, "False", API.PersistentVar.Char) == "True"
    HEAL_SELF = API.GetPersistentVar(HEALSELF_KEY, "True", API.PersistentVar.Char) == "True"
    SKIP_OUT_OF_RANGE = API.GetPersistentVar(SKIPOOR_KEY, "True", API.PersistentVar.Char) == "True"

    tank_str = API.GetPersistentVar(TANK_KEY, "0", API.PersistentVar.Char)
    try:
        TANK_PET = int(tank_str)
    except:
        TANK_PET = 0

    vetkit_str = API.GetPersistentVar(VETKIT_KEY, "0", API.PersistentVar.Char)
    try:
        VET_KIT_GRAPHIC = int(vetkit_str)
    except:
        VET_KIT_GRAPHIC = 0

    TARGET_REDS = API.GetPersistentVar(REDS_KEY, "False", API.PersistentVar.Char) == "True"
    TARGET_GRAYS = API.GetPersistentVar(GRAYS_KEY, "False", API.PersistentVar.Char) == "True"
    ATTACK_MODE = API.GetPersistentVar(MODE_KEY, "ALL", API.PersistentVar.Char)

    USE_POTIONS = API.GetPersistentVar(POTION_KEY, "True", API.PersistentVar.Char) == "True"

    pouch_str = API.GetPersistentVar(TRAPPED_POUCH_SERIAL_KEY, "0", API.PersistentVar.Char)
    try:
        trapped_pouch_serial = int(pouch_str)
    except:
        trapped_pouch_serial = 0

    use_trapped_pouch = API.GetPersistentVar(USE_TRAPPED_POUCH_KEY, "True", API.PersistentVar.Char) == "True"
    auto_target = API.GetPersistentVar(AUTO_TARGET_KEY, "False", API.PersistentVar.Char) == "True"

    is_expanded = API.GetPersistentVar(EXPANDED_KEY, "True", API.PersistentVar.Char) == "True"

    load_hotkeys()
    load_pet_hotkeys()  # NEW v2.2
    sync_pets_from_storage()

    active_str = API.GetPersistentVar(PETACTIVE_KEY, "", API.PersistentVar.Char)
    if active_str:
        pairs = [x for x in active_str.split("|") if x]
        for pair in pairs:
            parts = pair.split(":")
            if len(parts) == 2:
                try:
                    serial = int(parts[0])
                    active = (parts[1] == "1")
                    if serial in PETS:
                        PET_ACTIVE[serial] = active
                except:
                    pass

def onClosed():
    global config_gump, last_known_x, last_known_y

    # Always use tracked position - gump is being disposed so GetX/GetY returns 0
    if last_known_x >= 0 and last_known_y >= 0:
        API.SavePersistentVar(SETTINGS_KEY, str(last_known_x) + "," + str(last_known_y), API.PersistentVar.Char)
        API.SysMsg("Saved position: " + str(last_known_x) + "," + str(last_known_y), 68)

    active_pairs = []
    for serial in PETS:
        active_state = PET_ACTIVE.get(serial, True)
        active_str = "1" if active_state else "0"
        active_pairs.append(str(serial) + ":" + active_str)

    if active_pairs:
        API.SavePersistentVar(PETACTIVE_KEY, "|".join(active_pairs), API.PersistentVar.Char)

    # Close config window if open
    if config_gump is not None:
        close_config_gump()

    clear_stray_cursor()

    # Stop the script when main window closes
    API.Stop()

# ============ LOAD SETTINGS ============
load_settings()

# ============ BUILD GUI ============
gump = API.Gumps.CreateGump()
API.Gumps.AddControlOnDisposed(gump, onClosed)

savedPos = API.GetPersistentVar(SETTINGS_KEY, "100,100", API.PersistentVar.Char)
posXY = savedPos.split(',')
lastX = int(posXY[0])
lastY = int(posXY[1])

last_known_x = lastX
last_known_y = lastY

API.SysMsg("Loading main window at position: " + str(lastX) + "," + str(lastY), 68)

initial_height = EXPANDED_HEIGHT if is_expanded else COLLAPSED_HEIGHT

gump.SetRect(lastX, lastY, WINDOW_WIDTH_NORMAL, initial_height)

bg = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
bg.SetRect(0, 0, WINDOW_WIDTH_NORMAL, initial_height)
gump.Add(bg)

title = API.Gumps.CreateGumpTTFLabel("Tamer Suite v3.0", 16, "#00d4ff", aligned="center", maxWidth=WINDOW_WIDTH_NORMAL)
title.SetPos(0, 5)
gump.Add(title)

# Config button - opens separate config window
configBtn = API.Gumps.CreateSimpleButton("[C]", 20, 18)
configBtn.SetPos(230, 3)
configBtn.SetBackgroundHue(66)
API.Gumps.AddControlOnClick(configBtn, toggle_config)
gump.Add(configBtn)

# Expand/collapse button
expandBtn = API.Gumps.CreateSimpleButton("[-]" if is_expanded else "[+]", 20, 18)
expandBtn.SetPos(255, 3)
expandBtn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(expandBtn, toggle_expand)
gump.Add(expandBtn)

# Bandage count (top center) - ALWAYS VISIBLE
bandageLabel = API.Gumps.CreateGumpTTFLabel("Bandages: ???", 9, "#AAFFAA", aligned="center", maxWidth=WINDOW_WIDTH_NORMAL)
bandageLabel.SetPos(0, 24)
gump.Add(bandageLabel)

# ========== COMPACT SINGLE-COLUMN LAYOUT ==========
x = 5
y = 42
btnH = 20

# Status row: [PAUSE] [MODE] Status text
pauseBtn = API.Gumps.CreateSimpleButton("[PAUSE]", 65, btnH)
pauseBtn.SetPos(x, y)
pauseBtn.SetBackgroundHue(90)
pauseBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(pauseBtn, toggle_pause)
gump.Add(pauseBtn)

modeBtn = API.Gumps.CreateSimpleButton("[" + ATTACK_MODE + "]", 65, btnH)
modeBtn.SetPos(x + 70, y)
modeBtn.SetBackgroundHue(66 if ATTACK_MODE == "ORDER" else 68)
modeBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(modeBtn, toggle_mode)
gump.Add(modeBtn)

statusLabel = API.Gumps.CreateGumpTTFLabel("Running", 9, "#00ff00")
statusLabel.SetPos(x + 145, y + 5)
statusLabel.IsVisible = is_expanded
gump.Add(statusLabel)

y += 22

# Action row 1: [REZ FRIEND] [ALL KILL]
rezFriendBtn = API.Gumps.CreateSimpleButton("[REZ FRIEND]", 130, btnH)
rezFriendBtn.SetPos(x, y)
rezFriendBtn.SetBackgroundHue(38)
rezFriendBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(rezFriendBtn, toggle_rez_friend)
gump.Add(rezFriendBtn)

allKillBtn = API.Gumps.CreateSimpleButton("[ALL KILL]", 135, btnH)
allKillBtn.SetPos(x + 135, y)
allKillBtn.SetBackgroundHue(32)
allKillBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(allKillBtn, all_kill_manual)
gump.Add(allKillBtn)

y += 22

# Command row: [FOLLOW] [GUARD] [STAY]
followAllBtn = API.Gumps.CreateSimpleButton("[FOLLOW]", 85, btnH)
followAllBtn.SetPos(x, y)
followAllBtn.SetBackgroundHue(68)
followAllBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(followAllBtn, all_follow)
gump.Add(followAllBtn)

guardAllBtn = API.Gumps.CreateSimpleButton("[GUARD]", 90, btnH)
guardAllBtn.SetPos(x + 90, y)
guardAllBtn.SetBackgroundHue(68)
guardAllBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(guardAllBtn, all_guard)
gump.Add(guardAllBtn)

stayAllBtn = API.Gumps.CreateSimpleButton("[STAY]", 85, btnH)
stayAllBtn.SetPos(x + 185, y)
stayAllBtn.SetBackgroundHue(53)
stayAllBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(stayAllBtn, all_stay)
gump.Add(stayAllBtn)

y += 24

# ========== PETS SECTION ==========
petsTitle = API.Gumps.CreateGumpTTFLabel("=== PETS ===", 9, "#00ffaa", aligned="center", maxWidth=WINDOW_WIDTH_NORMAL)
petsTitle.SetPos(0, y)
petsTitle.IsVisible = is_expanded
gump.Add(petsTitle)

y += 16

# Pet management buttons
addBtn = API.Gumps.CreateSimpleButton("[ADD]", 60, 18)
addBtn.SetPos(x, y)
addBtn.SetBackgroundHue(68)
addBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(addBtn, add_pet)
gump.Add(addBtn)

removeBtn = API.Gumps.CreateSimpleButton("[REMOVE]", 85, 18)
removeBtn.SetPos(x + 65, y)
removeBtn.SetBackgroundHue(32)
removeBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(removeBtn, remove_pet)
gump.Add(removeBtn)

clearBtn = API.Gumps.CreateSimpleButton("[CLEAR]", 75, 18)
clearBtn.SetPos(x + 155, y)
clearBtn.SetBackgroundHue(90)
clearBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(clearBtn, clear_all_pets)
gump.Add(clearBtn)

y += 20

# Pet rows (compact: 200px pet + 30px hotkey + 30px arrow)
pet_labels = []
petHkDisplay1 = None
petHkDisplay2 = None
petHkDisplay3 = None
petHkDisplay4 = None
petHkDisplay5 = None
petArrow1 = None
petArrow2 = None
petArrow3 = None
petArrow4 = None
petArrow5 = None

for i in range(MAX_PETS):
    row_y = y + (i * 18)

    # Pet button (200px wide)
    lbl = API.Gumps.CreateSimpleButton(str(i+1) + ". ---", 200, 18)
    lbl.SetPos(x, row_y)
    lbl.SetBackgroundHue(90)
    lbl.IsVisible = is_expanded
    API.Gumps.AddControlOnClick(lbl, make_pet_click_callback(i))
    gump.Add(lbl)
    pet_labels.append(lbl)

    # Hotkey display button (30px)
    hk_display = API.Gumps.CreateSimpleButton("[---]", 30, 18)
    hk_display.SetPos(x + 205, row_y)
    hk_display.SetBackgroundHue(90)
    hk_display.IsVisible = is_expanded
    gump.Add(hk_display)

    if i == 0:
        petHkDisplay1 = hk_display
    elif i == 1:
        petHkDisplay2 = hk_display
    elif i == 2:
        petHkDisplay3 = hk_display
    elif i == 3:
        petHkDisplay4 = hk_display
    elif i == 4:
        petHkDisplay5 = hk_display

    # Arrow indicator button (30px)
    arrow = API.Gumps.CreateSimpleButton("[ ]", 30, 18)
    arrow.SetPos(x + 240, row_y)
    arrow.SetBackgroundHue(90)
    arrow.IsVisible = is_expanded
    gump.Add(arrow)

    if i == 0:
        petArrow1 = arrow
    elif i == 1:
        petArrow2 = arrow
    elif i == 2:
        petArrow3 = arrow
    elif i == 3:
        petArrow4 = arrow
    elif i == 4:
        petArrow5 = arrow


API.Gumps.AddGump(gump)

# Apply initial expanded/collapsed state
if not is_expanded:
    collapse_window()

# Update config button labels with loaded hotkeys
update_config_buttons()

# Update config displays
update_config_healer_display()
update_config_cmd_display()
update_pet_order_display()

# ============ REGISTER HOTKEYS ============
API.SysMsg("Registering key handlers...", 53)

registered_count = 0
for key in ALL_KEYS:
    try:
        API.OnHotKey(key, make_key_handler(key))
        registered_count += 1
    except Exception as e:
        pass

API.SysMsg("Registered " + str(registered_count) + " keys", 68)

# Initial display
update_pet_display()
update_pet_arrow_display()
update_config_tank_display()
update_config_vetkit_display()
update_bandage_display()
update_config_potion_display()
update_config_pouch_display()
update_hotkey_label()

API.SysMsg("Tamer Suite v3.0 loaded! Separate config window ready", 68)
API.SysMsg("Kill:" + (hotkeys["kill"] or "-") + " Guard:" + (hotkeys["guard"] or "-") + " Follow:" + (hotkeys["follow"] or "-") + " Pause:" + (hotkeys["pause"] or "-"), 53)

# ============ MAIN LOOP (NON-BLOCKING) ============
DISPLAY_INTERVAL = 0.3
SYNC_INTERVAL = 2.0

next_display = time.time() + DISPLAY_INTERVAL
next_sync = time.time() + SYNC_INTERVAL

while not API.StopRequested:
    try:
        # Process GUI clicks and HOTKEYS - always instant!
        API.ProcessCallbacks()

        # Check if current heal is done
        check_heal_complete()

        # Periodically capture position (main window)
        if not API.StopRequested:
            current_time = time.time()
            if current_time - last_position_check > 2.0:
                last_position_check = current_time
                try:
                    last_known_x = gump.GetX()
                    last_known_y = gump.GetY()
                except:
                    pass

        # Periodically capture position (config window)
        if config_gump is not None and not API.StopRequested:
            current_time = time.time()
            if current_time - config_last_position_check > 2.0:
                config_last_position_check = current_time
                try:
                    config_last_known_x = config_gump.GetX()
                    config_last_known_y = config_gump.GetY()
                except:
                    pass

        # Sync pets
        if time.time() > next_sync:
            sync_pets_from_storage()
            next_sync = time.time() + SYNC_INTERVAL

        # Update displays
        if time.time() > next_display:
            update_pet_display()
            update_pet_hotkey_main_display()  # NEW v2.2
            update_pet_arrow_display()  # NEW v2.2
            update_bandage_display()
            if show_config:
                update_config_potion_display()
                update_pet_hotkey_config_display()  # NEW v2.2
            next_display = time.time() + DISPLAY_INTERVAL

        # Check alerts (even when paused)
        check_critical_alerts()

        # FRIEND REZ LOGIC (highest priority - pauses all other healing)
        if not PAUSED and rez_friend_active:
            statusLabel.SetText("Rezzing: " + rez_friend_name + " (#" + str(rez_friend_attempts) + ")")
            attempt_friend_rez()
            continue

        # HEALER LOGIC (non-blocking)
        if not PAUSED and HEAL_STATE == "idle":
            action = get_next_heal_action()
            if action:
                target, action_type, duration, is_self = action
                start_heal_action(target, action_type, duration, is_self)

        # AUTO-TARGET LOGIC (continuous combat)
        if not PAUSED and auto_target:
            handle_auto_target()

        # Short pause - loop runs ~10x/second
        API.Pause(0.1)

    except Exception as e:
        if "operation canceled" not in str(e).lower() and not API.StopRequested:
            API.SysMsg("Error: " + str(e), 32)
        API.Pause(1)
