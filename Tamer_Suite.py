# ============================================================
# Tamer Suite v2.0
# by Coryigon for UO Unchained
# ============================================================
#
# The all-in-one tamer script. Combines pet healing and commands
# into a single window with a non-blocking design - your hotkeys
# stay responsive even during long actions like resurrections.
#
# Features:
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
# Hotkeys: TAB (All Kill), 1 (Guard), 2 (Follow), PAUSE (toggle)
#
# ============================================================
import API
import time

__version__ = "2.0"

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

# === HOTKEYS ===
PAUSE_HOTKEY = "PAUSE"        # Pause/resume healing
ALL_KILL_HOTKEY = "TAB"       # All Kill
GUARD_HOTKEY = "1"            # Guard Me
FOLLOW_HOTKEY = "2"           # Follow Me
STAY_HOTKEY = ""              # All Stay (disabled)

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

# Friend rez
rez_friend_target = 0
rez_friend_active = False
rez_friend_attempts = 0
rez_friend_name = ""
MAX_REZ_ATTEMPTS = 50
REZ_FRIEND_DELAY = 8.0

# Journal messages for resurrection detection
JOURNAL_REZ_SUCCESS = [
    "You are able to resurrect your patient",  # Primary success message
    "You have resurrected",                     # Alternate shard message
    "returns to life"                           # Alternate shard message
]

JOURNAL_REZ_FAIL = [
    "You fail to resurrect your patient",       # Failed attempt
    "That being is not damaged",                # Target not dead
    "You cannot perform beneficial acts",       # Criminal/grey
    "That is too far away",                     # Out of range
    "Target cannot be seen"                     # Line of sight
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

        # Get all items in backpack recursively
        items = API.ItemsInContainer(backpack_serial, True)
        if not items:
            return 0

        # Count all matching potions
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
        # Try multiple attribute names for paralysis
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

    # Safety check - don't use if HP too low
    if API.Player.Hits < TRAPPED_POUCH_MIN_HP:
        API.SysMsg("HP too low for trapped pouch! (" + str(API.Player.Hits) + "/" + str(TRAPPED_POUCH_MIN_HP) + ")", 32)
        return False

    # Check if we have a pouch configured
    if trapped_pouch_serial == 0:
        API.SysMsg("No trapped pouch configured! Use [SET POUCH] button", 43)
        return False

    # Find the pouch
    pouch = API.FindItem(trapped_pouch_serial)
    if not pouch:
        API.SysMsg("Trapped pouch not found!", 32)
        return False

    try:
        # Open the pouch - this triggers the explosion
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
                update_potion_display()
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

    # Check if we have a current target
    if current_attack_target == 0:
        return

    # Check if current target is still valid
    target = API.FindMobile(current_attack_target)

    # If target is dead, gone, or out of range, find next target
    target_distance = target.Distance if target and hasattr(target, 'Distance') else 999
    if not target or target.IsDead or target_distance > AUTO_TARGET_RANGE:
        # Build notoriety list based on settings
        notorieties = [API.Notoriety.Enemy]
        if TARGET_GRAYS:
            notorieties.append(API.Notoriety.Gray)
            notorieties.append(API.Notoriety.Criminal)
        if TARGET_REDS:
            notorieties.append(API.Notoriety.Murderer)

        # Find next target within 3 tiles
        next_enemy = API.NearestMobile(notorieties, AUTO_TARGET_RANGE)

        if next_enemy and next_enemy.Serial != API.Player.Serial and not next_enemy.IsDead:
            API.Msg("all kill")
            if API.WaitForTarget(timeout=TARGET_TIMEOUT):
                API.Target(next_enemy.Serial)
                current_attack_target = next_enemy.Serial
                API.HeadMsg("NEXT!", next_enemy.Serial, 68)
                API.SysMsg("Auto-targeting: " + get_mob_name(next_enemy), 68)
        else:
            # No more targets in range
            current_attack_target = 0

def check_journal_for_message(msg):
    """Check if journal contains a message"""
    try:
        return API.InJournal(msg, False)  # Don't clear matches
    except:
        return False

def clear_journal_safe():
    """Safely clear journal"""
    try:
        API.ClearJournal()
    except:
        pass

def check_rez_success():
    """Check journal for resurrection success messages"""
    for msg in JOURNAL_REZ_SUCCESS:
        if check_journal_for_message(msg):
            return True
    return False

def check_rez_fail():
    """Check journal for resurrection failure messages"""
    for msg in JOURNAL_REZ_FAIL:
        if check_journal_for_message(msg):
            return msg  # Return the specific failure message
    return None

# ============ PERSISTENCE ============
def load_settings():
    global USE_MAGERY, USE_REZ, HEAL_SELF, SKIP_OUT_OF_RANGE, TANK_PET, VET_KIT_GRAPHIC
    global TARGET_REDS, TARGET_GRAYS, ATTACK_MODE, PETS, PET_NAMES, PET_ACTIVE, last_known_pets_str
    global USE_POTIONS, trapped_pouch_serial, use_trapped_pouch, auto_target

    USE_MAGERY = API.GetPersistentVar(MAGERY_KEY, "False", API.PersistentVar.Char) == "True"
    USE_REZ = API.GetPersistentVar(REZ_KEY, "False", API.PersistentVar.Char) == "True"
    HEAL_SELF = API.GetPersistentVar(HEALSELF_KEY, "True", API.PersistentVar.Char) == "True"
    SKIP_OUT_OF_RANGE = API.GetPersistentVar(SKIPOOR_KEY, "True", API.PersistentVar.Char) == "True"
    TARGET_REDS = API.GetPersistentVar(REDS_KEY, "False", API.PersistentVar.Char) == "True"
    TARGET_GRAYS = API.GetPersistentVar(GRAYS_KEY, "False", API.PersistentVar.Char) == "True"
    USE_POTIONS = API.GetPersistentVar(POTION_KEY, "True", API.PersistentVar.Char) == "True"
    use_trapped_pouch = API.GetPersistentVar(USE_TRAPPED_POUCH_KEY, "True", API.PersistentVar.Char) == "True"
    auto_target = API.GetPersistentVar(AUTO_TARGET_KEY, "False", API.PersistentVar.Char) == "True"
    ATTACK_MODE = API.GetPersistentVar(MODE_KEY, "ALL", API.PersistentVar.Char)
    if ATTACK_MODE not in ["ALL", "ORDER"]:
        ATTACK_MODE = "ALL"

    try:
        TANK_PET = int(API.GetPersistentVar(TANK_KEY, "0", API.PersistentVar.Char))
    except:
        TANK_PET = 0

    try:
        VET_KIT_GRAPHIC = int(API.GetPersistentVar(VETKIT_KEY, "0", API.PersistentVar.Char))
    except:
        VET_KIT_GRAPHIC = 0

    try:
        trapped_pouch_serial = int(API.GetPersistentVar(TRAPPED_POUCH_SERIAL_KEY, "0", API.PersistentVar.Char))
    except:
        trapped_pouch_serial = 0

    # Load shared pets
    PETS = []
    PET_NAMES = {}
    PET_ACTIVE = {}
    pets_str = API.GetPersistentVar(SHARED_PETS_KEY, "", API.PersistentVar.Char)
    last_known_pets_str = pets_str
    if pets_str:
        for part in pets_str.split("|"):
            if not part:
                continue
            try:
                pieces = part.split(":")
                if len(pieces) >= 2:
                    serial = int(pieces[1])
                    PETS.append(serial)
                    PET_NAMES[serial] = pieces[0]
                    PET_ACTIVE[serial] = True  # Default to active
            except:
                pass

    # Load pet active states
    active_str = API.GetPersistentVar(PETACTIVE_KEY, "", API.PersistentVar.Char)
    if active_str:
        for part in active_str.split("|"):
            if not part:
                continue
            try:
                pieces = part.split(":")
                if len(pieces) >= 2:
                    serial = int(pieces[0])
                    active = pieces[1] == "1"
                    if serial in PET_ACTIVE:
                        PET_ACTIVE[serial] = active
            except:
                pass

def save_pets():
    global last_known_pets_str
    parts = []
    for serial in PETS:
        name = PET_NAMES.get(serial, "Unknown")
        safe_name = name.replace("|", "_").replace(":", "_")
        parts.append(safe_name + ":" + str(serial) + ":1")
    pets_str = "|".join(parts)
    last_known_pets_str = pets_str
    API.SavePersistentVar(SHARED_PETS_KEY, pets_str, API.PersistentVar.Char)

    # Save active states
    active_parts = []
    for serial in PETS:
        active = PET_ACTIVE.get(serial, True)
        active_parts.append(str(serial) + ":" + ("1" if active else "0"))
    active_str = "|".join(active_parts)
    API.SavePersistentVar(PETACTIVE_KEY, active_str, API.PersistentVar.Char)

def sync_pets_from_storage():
    global PETS, PET_NAMES, PET_ACTIVE, last_known_pets_str
    current_str = API.GetPersistentVar(SHARED_PETS_KEY, "", API.PersistentVar.Char)
    if current_str == last_known_pets_str:
        return False

    old_count = len(PETS)
    PETS = []
    PET_NAMES = {}
    if current_str:
        for part in current_str.split("|"):
            if not part:
                continue
            try:
                pieces = part.split(":")
                if len(pieces) >= 2:
                    serial = int(pieces[1])
                    PETS.append(serial)
                    PET_NAMES[serial] = pieces[0]
                    # Initialize active state if not already set
                    if serial not in PET_ACTIVE:
                        PET_ACTIVE[serial] = True
            except:
                pass
    last_known_pets_str = current_str

    new_count = len(PETS)
    if old_count != new_count:
        API.SysMsg("Pet list synced: " + str(new_count) + " pets", 66)
        update_pet_display()
    return True

# ============ NON-BLOCKING HEAL ACTIONS ============
def start_heal_action(target_serial, action_type, duration, is_self=False):
    """Start a heal/rez action WITHOUT blocking. Returns True if started."""
    global HEAL_STATE, heal_start_time, heal_target, heal_duration, heal_action_type
    
    if HEAL_STATE != "idle":
        return False  # Already doing something
    
    if action_type == "heal":
        if USE_MAGERY:
            # Cast Greater Heal
            API.PreTarget(target_serial, "beneficial")
            API.Pause(0.1)
            API.CastSpell("Greater Heal")
            API.Pause(0.1)
            API.CancelPreTarget()
        else:
            # Use bandage
            if not check_bandages():
                return False
            API.PreTarget(target_serial, "beneficial")
            API.Pause(0.1)
            API.UseObject(API.Found, False)
            API.Pause(0.1)
            API.CancelPreTarget()
        
        mob = API.FindMobile(target_serial) if not is_self else None
        name = "Self" if is_self else get_mob_name(mob)
        API.HeadMsg("Healing!", target_serial, 68)
        statusLabel.SetText("Healing: " + name)
        
    elif action_type == "rez":
        if not check_bandages():
            return False
        API.PreTarget(target_serial, "beneficial")
        API.Pause(0.1)
        API.UseObject(API.Found, False)
        API.Pause(0.1)
        API.CancelPreTarget()
        
        mob = API.FindMobile(target_serial)
        name = get_mob_name(mob)
        API.HeadMsg("Rezzing!", target_serial, 38)
        statusLabel.SetText("Rezzing: " + name)
        
    elif action_type == "vetkit":
        if VET_KIT_GRAPHIC == 0 or not API.FindType(VET_KIT_GRAPHIC):
            return False
        API.UseObject(API.Found, False)
        API.Pause(0.1)
        if API.HasTarget():
            # Target first hurt pet
            for pet in PETS:
                mob = API.FindMobile(pet)
                if mob and not mob.IsDead and get_hp_percent(mob) < VET_KIT_HP_PERCENT:
                    API.Target(pet)
                    break
            else:
                clear_stray_cursor()
        API.HeadMsg("Vet Kit!", API.Player.Serial, 68)
        statusLabel.SetText("Using Vet Kit")

    elif action_type == "trapped_pouch":
        if not use_trapped_pouch():
            return False
        # Don't set healing state - this is instant

    elif action_type == "cure_potion":
        if not drink_potion(POTION_CURE, "Cure Potion"):
            return False
        # Don't set healing state - potions are instant

    elif action_type == "heal_potion":
        if not drink_potion(POTION_HEAL, "Heal Potion"):
            return False
        # Don't set healing state - potions are instant

    clear_stray_cursor()

    # Only set healing state for actions that take time (bandages, vet kit, rez)
    # Potions and trapped pouch are instant
    if action_type in ["heal", "rez", "vetkit"]:
        HEAL_STATE = "healing"
        heal_start_time = time.time()
        heal_target = target_serial
        heal_duration = duration
        heal_action_type = action_type

    return True

def check_heal_complete():
    """Check if current heal action is done. Returns True if done or idle."""
    global HEAL_STATE, last_vetkit_use
    
    if HEAL_STATE == "idle":
        return True
    
    if HEAL_STATE == "healing":
        if time.time() >= heal_start_time + heal_duration:
            if heal_action_type == "vetkit":
                last_vetkit_use = time.time()
            HEAL_STATE = "idle"
            statusLabel.SetText("Running")
            return True
    
    return False

def cancel_heal():
    """Cancel current heal action"""
    global HEAL_STATE
    HEAL_STATE = "idle"
    statusLabel.SetText("Running")
    clear_stray_cursor()

# ============ HEAL PRIORITY LOGIC ============
def get_next_heal_action():
    """
    Determine what to heal next. Returns (target, action_type, duration, is_self) or None.
    Does NOT block - just decides what to do.

    Priority:
    0. FRIEND REZ: Absolute highest priority (blocks all other healing)
    1. TRAPPED POUCH: Break paralyze (if safe HP)
    2. PLAYER POTIONS: Critical/poison/heal
    3. SELF BANDAGES: After potions
    4. VET KIT: Multiple pets hurt
    5. PET HEALING: Tank and others
    """
    # FRIEND REZ: Absolute highest priority - pauses all other healing
    if rez_friend_active:
        return None  # Don't do any other healing while rezzing friend

    # Skip if we're already healing
    if HEAL_STATE != "idle":
        return None

    # Skip if no bandages (and not using magery)
    if not USE_MAGERY and get_bandage_count() == 0:
        return None

    # TRAPPED POUCH: Break paralyze (HIGHEST PRIORITY)
    if use_trapped_pouch and trapped_pouch_serial > 0:
        if is_player_paralyzed() and API.Player.Hits >= TRAPPED_POUCH_MIN_HP:
            return (0, "trapped_pouch", 0.1, False)

    # Manual heal override
    global manual_heal_target
    if manual_heal_target != 0:
        target = manual_heal_target
        manual_heal_target = 0
        mob = API.FindMobile(target)
        if mob:
            if mob.IsDead and USE_REZ:
                return (target, "rez", REZ_DELAY, False)
            elif not mob.IsDead:
                return (target, "heal", VET_DELAY if not USE_MAGERY else CAST_DELAY, False)
    
    # Vet kit check (multiple pets hurt)
    if VET_KIT_GRAPHIC > 0 and time.time() - last_vetkit_use > VET_KIT_COOLDOWN:
        hurt_count = sum(1 for p in PETS if API.FindMobile(p) and not API.FindMobile(p).IsDead and 
                        (is_poisoned(API.FindMobile(p)) or get_hp_percent(API.FindMobile(p)) < VET_KIT_HP_PERCENT))
        if hurt_count >= VET_KIT_THRESHOLD:
            return (0, "vetkit", VET_KIT_DELAY, False)
    
    # Self heal (poison or damage) - BANDAGES ONLY
    if HEAL_SELF and not is_player_dead():
        player = API.Player
        if CURE_POISON and is_player_poisoned():
            return (player.Serial, "heal", SELF_DELAY if not USE_MAGERY else CAST_DELAY, True)
        if player.HitsDiff > SELF_HEAL_THRESHOLD:
            return (player.Serial, "heal", SELF_DELAY if not USE_MAGERY else CAST_DELAY, True)

    # PLAYER POTIONS: Critical/poison/heal (AFTER bandages, BEFORE pets)
    if HEAL_SELF and USE_POTIONS and not is_player_dead():
        # Cure poison (highest priority for potions)
        if is_player_poisoned() and potion_ready():
            if get_potion_count(POTION_CURE) > 0:
                return (0, "cure_potion", 0.1, False)

        # Heal if low HP (>= 15 missing HP)
        player_hits_diff = API.Player.HitsMax - API.Player.Hits
        if player_hits_diff >= 15 and potion_ready():
            if get_potion_count(POTION_HEAL) > 0:
                return (0, "heal_potion", 0.1, False)

    # Tank poison
    if TANK_PET and CURE_POISON:
        mob = API.FindMobile(TANK_PET)
        if mob and not mob.IsDead and is_poisoned(mob):
            if get_distance(mob) <= (SPELL_RANGE if USE_MAGERY else BANDAGE_RANGE):
                return (TANK_PET, "heal", VET_DELAY if not USE_MAGERY else CAST_DELAY, False)
    
    # Pet poison
    if CURE_POISON:
        for pet in PETS:
            if pet == TANK_PET:
                continue
            mob = API.FindMobile(pet)
            if mob and not mob.IsDead and is_poisoned(mob):
                if get_distance(mob) <= (SPELL_RANGE if USE_MAGERY else BANDAGE_RANGE):
                    return (pet, "heal", VET_DELAY if not USE_MAGERY else CAST_DELAY, False)
    
    # Tank critical
    if TANK_PET:
        mob = API.FindMobile(TANK_PET)
        if mob:
            if mob.IsDead and USE_REZ:
                if get_distance(mob) <= BANDAGE_RANGE:
                    return (TANK_PET, "rez", REZ_DELAY, False)
            elif not mob.IsDead and get_hp_percent(mob) < TANK_HP_PERCENT:
                if get_distance(mob) <= (SPELL_RANGE if USE_MAGERY else BANDAGE_RANGE):
                    return (TANK_PET, "heal", VET_DELAY if not USE_MAGERY else CAST_DELAY, False)
    
    # Other pets
    worst_pet = None
    worst_pct = 100
    for pet in PETS:
        if pet == TANK_PET:
            continue
        mob = API.FindMobile(pet)
        if not mob:
            continue
        dist = get_distance(mob)
        max_range = SPELL_RANGE if USE_MAGERY else BANDAGE_RANGE
        
        if mob.IsDead and USE_REZ:
            if dist <= BANDAGE_RANGE:
                return (pet, "rez", REZ_DELAY, False)
        elif not mob.IsDead:
            hp_pct = get_hp_percent(mob)
            if hp_pct < PET_HP_PERCENT and hp_pct < worst_pct and dist <= max_range:
                worst_pct = hp_pct
                worst_pet = pet
    
    if worst_pet:
        return (worst_pet, "heal", VET_DELAY if not USE_MAGERY else CAST_DELAY, False)
    
    # Tank top-off
    if TANK_PET:
        mob = API.FindMobile(TANK_PET)
        if mob and not mob.IsDead and mob.HitsDiff > 0:
            if get_distance(mob) <= (SPELL_RANGE if USE_MAGERY else BANDAGE_RANGE):
                return (TANK_PET, "heal", VET_DELAY if not USE_MAGERY else CAST_DELAY, False)

    return None

# ============ FRIEND REZ FUNCTIONS ============
def start_friend_rez():
    """Start the friend resurrection process"""
    global rez_friend_target, rez_friend_active, rez_friend_attempts, rez_friend_name

    API.SysMsg("Target a DEAD friend to resurrect...", 38)
    cancel_all_targets()

    target = API.RequestTarget(timeout=15)

    if not target:
        API.SysMsg("Targeting cancelled", 32)
        return

    mob = API.FindMobile(target)
    if not mob:
        API.SysMsg("Not a valid mobile!", 32)
        return

    # Check if they're dead
    if not mob.IsDead:
        API.SysMsg(get_mob_name(mob) + " is not dead!", 32)
        return

    # Start rezzing
    rez_friend_target = target
    rez_friend_name = get_mob_name(mob)
    rez_friend_attempts = 0
    rez_friend_active = True

    API.SysMsg("=== REZZING " + rez_friend_name.upper() + " ===", 38)
    API.SysMsg("Pet healing PAUSED until rez complete or cancelled", 43)

    update_rez_friend_display()

def cancel_friend_rez():
    """Cancel the friend resurrection process"""
    global rez_friend_target, rez_friend_active, rez_friend_attempts, rez_friend_name

    if rez_friend_active:
        API.SysMsg("Friend rez cancelled after " + str(rez_friend_attempts) + " attempts", 43)

    rez_friend_target = 0
    rez_friend_name = ""
    rez_friend_attempts = 0
    rez_friend_active = False

    update_rez_friend_display()

def attempt_friend_rez():
    """Attempt to resurrect the targeted friend"""
    global rez_friend_attempts, rez_friend_active

    if not rez_friend_active or rez_friend_target == 0:
        return False

    mob = API.FindMobile(rez_friend_target)
    if not mob:
        API.SysMsg("Lost target - " + rez_friend_name + " not found!", 32)
        cancel_friend_rez()
        return False

    # Check if they're still dead
    if not mob.IsDead:
        API.SysMsg("=== " + rez_friend_name.upper() + " IS ALIVE! ===", 68)
        API.HeadMsg("ALIVE!", rez_friend_target, 68)
        heal_friend_after_rez()
        cancel_friend_rez()
        return True

    # Check max attempts
    if rez_friend_attempts >= MAX_REZ_ATTEMPTS:
        API.SysMsg("Max attempts reached (" + str(MAX_REZ_ATTEMPTS) + ") - giving up on " + rez_friend_name, 32)
        cancel_friend_rez()
        return False

    # Increment attempt counter
    rez_friend_attempts += 1

    # Check distance
    distance = get_distance(mob)
    if distance > BANDAGE_RANGE:
        API.SysMsg("Following " + rez_friend_name + " (distance: " + str(distance) + ")", 53)
        # Simple follow - just move towards them
        API.AutoFollow(rez_friend_target)
        timeout = time.time() + 5.0
        while time.time() < timeout:
            mob = API.FindMobile(rez_friend_target)
            if not mob:
                API.CancelAutoFollow()
                return False
            if get_distance(mob) <= BANDAGE_RANGE:
                break
            API.Pause(0.2)
        API.CancelAutoFollow()

        # Re-check distance
        mob = API.FindMobile(rez_friend_target)
        if not mob or get_distance(mob) > BANDAGE_RANGE:
            API.SysMsg("Couldn't reach " + rez_friend_name + " - retrying...", 32)
            return False

    # Check bandages
    if not check_bandages():
        API.SysMsg("Out of bandages! Rez paused.", 32)
        return False

    # Attempt rez
    cancel_all_targets()
    clear_journal_safe()

    API.HeadMsg("Rez #" + str(rez_friend_attempts), rez_friend_target, 38)
    API.SysMsg("Rez attempt #" + str(rez_friend_attempts) + " on " + rez_friend_name, 38)

    API.PreTarget(rez_friend_target, "beneficial")
    API.Pause(0.2)
    API.UseObject(API.Found, False)
    API.Pause(0.5)
    API.CancelPreTarget()
    clear_stray_cursor()

    # Wait and check for success
    start_time = time.time()
    while time.time() - start_time < REZ_FRIEND_DELAY:
        # Check if they're alive now
        mob = API.FindMobile(rez_friend_target)
        if mob and not mob.IsDead:
            API.SysMsg("=== " + rez_friend_name.upper() + " RESURRECTED! ===", 68)
            API.HeadMsg("RESURRECTED!", rez_friend_target, 68)
            heal_friend_after_rez()
            cancel_friend_rez()
            return True

        # Check journal for success
        if check_rez_success():
            API.SysMsg("=== " + rez_friend_name.upper() + " RESURRECTED! (journal) ===", 68)
            API.HeadMsg("RESURRECTED!", rez_friend_target, 68)
            clear_journal_safe()
            heal_friend_after_rez()
            cancel_friend_rez()
            return True

        # Check for failures
        fail_msg = check_rez_fail()
        if fail_msg:
            if "not damaged" in fail_msg.lower():
                # Target is alive!
                API.SysMsg("=== " + rez_friend_name.upper() + " IS ALIVE! ===", 68)
                heal_friend_after_rez()
                cancel_friend_rez()
                return True
            else:
                API.SysMsg("Rez failed: " + fail_msg, 43)
                clear_journal_safe()
                break

        API.Pause(0.5)

    # Not successful yet, will retry on next loop
    update_rez_friend_display()
    return False

def heal_friend_after_rez():
    """Bandage the friend once after resurrection"""
    global rez_friend_target, rez_friend_name

    if rez_friend_target == 0:
        return

    API.SysMsg("Healing " + rez_friend_name + " after rez...", 68)
    API.HeadMsg("Healing!", rez_friend_target, 68)

    # Check bandages
    if not check_bandages():
        API.SysMsg("No bandages to heal after rez!", 32)
        return

    # Check if in range
    mob = API.FindMobile(rez_friend_target)
    if not mob:
        return

    distance = get_distance(mob)
    if distance > BANDAGE_RANGE:
        # Try to follow
        API.AutoFollow(rez_friend_target)
        timeout = time.time() + 5.0
        while time.time() < timeout:
            mob = API.FindMobile(rez_friend_target)
            if not mob:
                API.CancelAutoFollow()
                return
            if get_distance(mob) <= BANDAGE_RANGE:
                break
            API.Pause(0.2)
        API.CancelAutoFollow()

        # Re-check
        mob = API.FindMobile(rez_friend_target)
        if not mob or get_distance(mob) > BANDAGE_RANGE:
            API.SysMsg("Couldn't reach " + rez_friend_name + " to heal", 32)
            return

    # Bandage them
    cancel_all_targets()
    clear_journal_safe()

    API.PreTarget(rez_friend_target, "beneficial")
    API.Pause(0.2)
    API.UseObject(API.Found, False)
    API.Pause(0.5)
    API.CancelPreTarget()
    clear_stray_cursor()

    # Wait for bandage
    API.Pause(VET_DELAY)
    clear_stray_cursor()

    API.SysMsg("Post-rez heal complete!", 68)

def update_rez_friend_display():
    """Update the rez friend button and label"""
    if rez_friend_active:
        rezFriendBtn.SetText("[CANCEL REZ]")
        rezFriendBtn.SetBackgroundHue(32)
        rezFriendLabel.SetText("Rezzing: " + rez_friend_name + " (#" + str(rez_friend_attempts) + ")")
    else:
        rezFriendBtn.SetText("[REZ FRIEND]")
        rezFriendBtn.SetBackgroundHue(38)
        rezFriendLabel.SetText("Friend Rez: Inactive")

def toggle_rez_friend():
    """Toggle friend rez on/off"""
    if rez_friend_active:
        cancel_friend_rez()
    else:
        start_friend_rez()

# ============ PET COMMANDS (INSTANT) ============
def find_attack_target():
    """Find nearest hostile"""
    notorieties = [API.Notoriety.Enemy]
    if TARGET_GRAYS:
        notorieties.extend([API.Notoriety.Gray, API.Notoriety.Criminal])
    if TARGET_REDS:
        notorieties.append(API.Notoriety.Murderer)
    
    enemy = API.NearestMobile(notorieties, MAX_DISTANCE)
    if enemy and enemy.Serial != API.Player.Serial:
        return enemy
    return None

def all_kill():
    """Main attack command"""
    if ATTACK_MODE == "ORDER" and PETS:
        ordered_kill()
    else:
        all_kill_classic()

def all_kill_classic():
    """Classic all kill"""
    global current_attack_target
    enemy = find_attack_target()
    if enemy:
        API.Msg("all kill")
        if API.WaitForTarget(timeout=TARGET_TIMEOUT):
            API.Target(enemy)
            current_attack_target = enemy.Serial  # Track this target for auto-targeting
            API.HeadMsg("KILL!", enemy, 32)
            API.SysMsg("All kill: " + get_mob_name(enemy), 68)
        else:
            API.SysMsg("No target cursor", 32)
    else:
        API.SysMsg("No hostile - select manually", 53)
        API.Msg("all kill")

def ordered_kill():
    """Send each active pet by name to attack"""
    global current_attack_target
    if not PETS:
        all_kill_classic()
        return

    # Filter for active pets only
    active_pets = [s for s in PETS if PET_ACTIVE.get(s, True)]
    if not active_pets:
        API.SysMsg("No active pets in ORDER mode! Using ALL mode", 43)
        all_kill_classic()
        return

    enemy = find_attack_target()
    if not enemy:
        API.SysMsg("No hostile - select target manually", 53)
        target = API.RequestTarget(timeout=TARGET_TIMEOUT)
        if not target:
            API.SysMsg("No target selected", 32)
            return
        enemy_serial = target
        current_attack_target = target  # Track this target
        mob = API.FindMobile(target)
        if mob:
            API.HeadMsg("KILL!", target, 32)
    else:
        enemy_serial = enemy.Serial
        current_attack_target = enemy.Serial  # Track this target
        API.HeadMsg("KILL!", enemy, 32)
        API.SysMsg("Ordered attack: " + get_mob_name(enemy), 68)

    for i, pet_serial in enumerate(active_pets):
        name = PET_NAMES.get(pet_serial, "pet")
        if i > 0:
            API.Pause(COMMAND_DELAY)
        API.Msg(name + " kill")
        API.SysMsg("  " + str(i+1) + ". " + name + " -> attack", 88)
        if API.WaitForTarget(timeout=2.0):
            API.Target(enemy_serial)
        API.Pause(0.2)

    API.SysMsg("Ordered attack: " + str(len(active_pets)) + " pets sent", 68)

def all_follow():
    if ATTACK_MODE == "ORDER" and PETS:
        ordered_command("follow me", "Follow")
    else:
        API.Msg("all follow me")
        API.SysMsg("Pets: Follow Me", 88)

def all_guard():
    if ATTACK_MODE == "ORDER" and PETS:
        ordered_command("guard me", "Guard")
    else:
        API.Msg("all guard me")
        API.SysMsg("Pets: Guard Me", 88)

def all_stay():
    if ATTACK_MODE == "ORDER" and PETS:
        ordered_command("stay", "Stay")
    else:
        API.Msg("all stay")
        API.SysMsg("Pets: Stay", 88)

def ordered_command(cmd, display_name):
    """Send command to each active pet by name"""
    # Filter for active pets only
    active_pets = [s for s in PETS if PET_ACTIVE.get(s, True)]

    if not active_pets:
        API.Msg("all " + cmd)
        API.SysMsg(display_name + " (all)", 88)
        return

    for i, pet_serial in enumerate(active_pets):
        name = PET_NAMES.get(pet_serial, "pet")
        if i > 0:
            API.Pause(0.3)  # Small delay between commands
        API.Msg(name + " " + cmd)
        API.SysMsg("  " + name + " " + cmd, 88)
    API.SysMsg(display_name + " sent to " + str(len(active_pets)) + " pets", 68)

def pet_follow_by_click(index):
    """Send follow command to specific pet by clicking"""
    if index >= len(PETS):
        return
    serial = PETS[index]
    name = PET_NAMES.get(serial, "pet")
    mob = API.FindMobile(serial)
    if not mob:
        API.SysMsg(name + " not found!", 32)
        return
    API.Msg(name + " follow me")
    API.SysMsg(name + " follow!", 68)
    API.HeadMsg("Follow!", serial, 68)

def say_bank():
    API.Msg("bank")
    API.SysMsg("Opening bank...", 68)

def say_balance():
    API.Msg("balance")
    API.SysMsg("Checking balance...", 68)

def all_kill_manual():
    """Just say all kill - manual targeting"""
    API.Msg("all kill")
    API.SysMsg("All Kill - select target", 68)

def pet_follow_by_name(serial):
    """Send follow command to specific pet"""
    name = PET_NAMES.get(serial, "pet")
    API.Msg(name + " follow me")
    API.SysMsg(name + " follow!", 68)
    API.HeadMsg("Follow!", serial, 68)

# ============ GUI CALLBACKS ============
def toggle_pause():
    global PAUSED
    PAUSED = not PAUSED
    if PAUSED:
        cancel_heal()
        pauseBtn.SetText("[PAUSED]")
        pauseBtn.SetBackgroundHue(32)
        statusLabel.SetText("*** PAUSED ***")
        API.SysMsg("Healer PAUSED", 43)
    else:
        pauseBtn.SetText("[PAUSE]")
        pauseBtn.SetBackgroundHue(90)
        statusLabel.SetText("Running")
        API.SysMsg("Healer RESUMED", 68)

def toggle_magery():
    global USE_MAGERY
    USE_MAGERY = not USE_MAGERY
    API.SavePersistentVar(MAGERY_KEY, str(USE_MAGERY), API.PersistentVar.Char)
    mageryBtn.SetText("[MAGE]" if USE_MAGERY else "[BAND]")
    mageryBtn.SetBackgroundHue(66 if USE_MAGERY else 68)

def toggle_self():
    global HEAL_SELF
    HEAL_SELF = not HEAL_SELF
    API.SavePersistentVar(HEALSELF_KEY, str(HEAL_SELF), API.PersistentVar.Char)
    selfBtn.SetText("[SELF:" + ("ON" if HEAL_SELF else "OFF") + "]")
    selfBtn.SetBackgroundHue(68 if HEAL_SELF else 90)

def toggle_rez():
    global USE_REZ
    USE_REZ = not USE_REZ
    API.SavePersistentVar(REZ_KEY, str(USE_REZ), API.PersistentVar.Char)
    rezBtn.SetText("[REZ:" + ("ON" if USE_REZ else "OFF") + "]")
    rezBtn.SetBackgroundHue(38 if USE_REZ else 90)

def toggle_skip():
    global SKIP_OUT_OF_RANGE
    SKIP_OUT_OF_RANGE = not SKIP_OUT_OF_RANGE
    API.SavePersistentVar(SKIPOOR_KEY, str(SKIP_OUT_OF_RANGE), API.PersistentVar.Char)
    skipBtn.SetText("[SKIP:" + ("ON" if SKIP_OUT_OF_RANGE else "OFF") + "]")
    skipBtn.SetBackgroundHue(53 if SKIP_OUT_OF_RANGE else 90)

def toggle_reds():
    global TARGET_REDS
    TARGET_REDS = not TARGET_REDS
    API.SavePersistentVar(REDS_KEY, str(TARGET_REDS), API.PersistentVar.Char)
    redsBtn.SetText("[REDS:" + ("ON" if TARGET_REDS else "OFF") + "]")
    redsBtn.SetBackgroundHue(32 if TARGET_REDS else 90)

def toggle_grays():
    global TARGET_GRAYS
    TARGET_GRAYS = not TARGET_GRAYS
    API.SavePersistentVar(GRAYS_KEY, str(TARGET_GRAYS), API.PersistentVar.Char)
    graysBtn.SetText("[GRAYS:" + ("ON" if TARGET_GRAYS else "OFF") + "]")
    graysBtn.SetBackgroundHue(53 if TARGET_GRAYS else 90)

def toggle_mode():
    global ATTACK_MODE
    ATTACK_MODE = "ORDER" if ATTACK_MODE == "ALL" else "ALL"
    API.SavePersistentVar(MODE_KEY, ATTACK_MODE, API.PersistentVar.Char)
    modeBtn.SetText("[" + ATTACK_MODE + "]")
    modeBtn.SetBackgroundHue(66 if ATTACK_MODE == "ORDER" else 68)

def toggle_potions():
    global USE_POTIONS
    USE_POTIONS = not USE_POTIONS
    API.SavePersistentVar(POTION_KEY, str(USE_POTIONS), API.PersistentVar.Char)
    potionsBtn.SetText("[POTIONS:" + ("ON" if USE_POTIONS else "OFF") + "]")
    potionsBtn.SetBackgroundHue(68 if USE_POTIONS else 90)

def toggle_auto_target():
    global auto_target, current_attack_target
    auto_target = not auto_target
    API.SavePersistentVar(AUTO_TARGET_KEY, str(auto_target), API.PersistentVar.Char)
    autoTargetBtn.SetText("[AUTO-TARGET:" + ("ON" if auto_target else "OFF") + "]")
    autoTargetBtn.SetBackgroundHue(68 if auto_target else 90)
    if auto_target:
        API.SysMsg("Auto-Target: ON (3 tile range)", 68)
    else:
        API.SysMsg("Auto-Target: OFF", 32)
        current_attack_target = 0

def toggle_use_trapped_pouch():
    global use_trapped_pouch
    use_trapped_pouch = not use_trapped_pouch
    API.SavePersistentVar(USE_TRAPPED_POUCH_KEY, str(use_trapped_pouch), API.PersistentVar.Char)
    usePouchBtn.SetText("[USE POUCH:" + ("ON" if use_trapped_pouch else "OFF") + "]")
    usePouchBtn.SetBackgroundHue(68 if use_trapped_pouch else 90)

def on_set_trapped_pouch():
    target_trapped_pouch()

def set_tank():
    global TANK_PET, PET_NAMES
    API.SysMsg("Target your TANK pet...", 68)
    cancel_all_targets()
    target = API.RequestTarget(timeout=10)
    if target:
        mob = API.FindMobile(target)
        if mob:
            name = get_mob_name(mob)
            TANK_PET = target
            PET_NAMES[target] = name
            if target not in PETS and len(PETS) < MAX_PETS:
                PETS.append(target)
                save_pets()
            API.SavePersistentVar(TANK_KEY, str(TANK_PET), API.PersistentVar.Char)
            update_tank_display()
            update_pet_display()
            API.SysMsg("Tank set: " + name, 38)

def clear_tank():
    global TANK_PET
    TANK_PET = 0
    API.SavePersistentVar(TANK_KEY, "0", API.PersistentVar.Char)
    update_tank_display()
    update_pet_display()
    API.SysMsg("Tank cleared", 68)

def set_vetkit():
    global VET_KIT_GRAPHIC
    API.SysMsg("Target your VET KIT...", 68)
    cancel_all_targets()
    target = API.RequestTarget(timeout=10)
    if target:
        item = API.FindItem(target)
        if item:
            VET_KIT_GRAPHIC = item.Graphic
            API.SavePersistentVar(VETKIT_KEY, str(VET_KIT_GRAPHIC), API.PersistentVar.Char)
            update_vetkit_display()
            API.SysMsg("Vet Kit set! Graphic: " + str(VET_KIT_GRAPHIC), 68)

def clear_vetkit():
    global VET_KIT_GRAPHIC
    VET_KIT_GRAPHIC = 0
    API.SavePersistentVar(VETKIT_KEY, "0", API.PersistentVar.Char)
    update_vetkit_display()
    API.SysMsg("Vet Kit cleared", 68)

def add_pet():
    global PET_NAMES, PET_ACTIVE
    if len(PETS) >= MAX_PETS:
        API.SysMsg("Max pets reached!", 32)
        return
    API.SysMsg("Target a pet to add...", 68)
    cancel_all_targets()
    target = API.RequestTarget(timeout=10)
    if target:
        mob = API.FindMobile(target)
        if mob:
            if target in PETS:
                API.SysMsg("Already in list!", 32)
            else:
                name = get_mob_name(mob)
                PETS.append(target)
                PET_NAMES[target] = name
                PET_ACTIVE[target] = True  # Default to active
                save_pets()
                update_pet_display()
                API.SysMsg("Added: " + name, 68)

def remove_pet():
    global PET_NAMES, PET_ACTIVE, TANK_PET
    if not PETS:
        API.SysMsg("No pets to remove!", 32)
        return
    API.SysMsg("Target a pet to remove...", 68)
    cancel_all_targets()
    target = API.RequestTarget(timeout=10)
    if target and target in PETS:
        name = PET_NAMES.get(target, "Unknown")
        PETS.remove(target)
        if target in PET_NAMES:
            del PET_NAMES[target]
        if target in PET_ACTIVE:
            del PET_ACTIVE[target]
        if target == TANK_PET:
            TANK_PET = 0
            API.SavePersistentVar(TANK_KEY, "0", API.PersistentVar.Char)
        save_pets()
        update_pet_display()
        update_tank_display()
        API.SysMsg("Removed: " + name, 68)

def clear_all_pets():
    global PETS, PET_NAMES, PET_ACTIVE, TANK_PET
    PETS = []
    PET_NAMES = {}
    PET_ACTIVE = {}
    TANK_PET = 0
    save_pets()
    API.SavePersistentVar(TANK_KEY, "0", API.PersistentVar.Char)
    update_pet_display()
    update_tank_display()
    API.SysMsg("All pets cleared!", 68)

def toggle_pet_active(index):
    """Toggle a pet's active status for ORDER mode"""
    if index < 0 or index >= len(PETS):
        return
    serial = PETS[index]
    PET_ACTIVE[serial] = not PET_ACTIVE.get(serial, True)
    save_pets()
    update_pet_display()
    name = PET_NAMES.get(serial, "Pet")
    status = "ON" if PET_ACTIVE[serial] else "OFF"
    API.SysMsg(name + " ORDER mode: " + status, 68 if PET_ACTIVE[serial] else 32)

def make_pet_click_callback(index):
    def callback():
        global manual_heal_target
        if index < len(PETS):
            serial = PETS[index]
            mob = API.FindMobile(serial)
            if mob:
                name = PET_NAMES.get(serial, get_mob_name(mob))
                
                # Always send follow command first (instant)
                API.Msg(name + " follow me")
                API.HeadMsg("Follow!", serial, 68)
                
                # Also queue heal if needed
                if mob.IsDead and USE_REZ:
                    manual_heal_target = serial
                    API.SysMsg(name + " follow + REZ queued", 38)
                elif not mob.IsDead and (is_poisoned(mob) or get_hp_percent(mob) < 90):
                    manual_heal_target = serial
                    API.SysMsg(name + " follow + HEAL queued", 68)
                else:
                    API.SysMsg(name + " follow!", 68)
            else:
                API.SysMsg("Pet not found!", 32)
    return callback

# ============ DISPLAY UPDATES ============
def get_health_bar(hp_pct, width=8):
    filled = int((hp_pct / 100) * width)
    empty = width - filled
    return "|" * filled + "." * empty

def update_pet_display():
    for i, lbl in enumerate(pet_labels):
        if i < len(PETS):
            serial = PETS[i]
            mob = API.FindMobile(serial)
            is_active = PET_ACTIVE.get(serial, True)

            if mob:
                name = get_mob_name(mob)[:6]
                tank_marker = "T" if serial == TANK_PET else ""

                if mob.IsDead:
                    lbl.SetText(str(i+1) + tank_marker + "." + name + " [DEAD]")
                    lbl.SetBackgroundHue(32)
                else:
                    hp_pct = get_hp_percent(mob)
                    bar = get_health_bar(hp_pct)
                    poison = "[P]" if is_poisoned(mob) else ""
                    lbl.SetText(str(i+1) + tank_marker + "." + name + " " + bar + poison)

                    if is_poisoned(mob):
                        lbl.SetBackgroundHue(53)
                    elif hp_pct < 50:
                        lbl.SetBackgroundHue(32)
                    elif hp_pct < 80:
                        lbl.SetBackgroundHue(43)
                    else:
                        lbl.SetBackgroundHue(68)
            else:
                lbl.SetText(str(i+1) + ". [Not Found]")
                lbl.SetBackgroundHue(90)

            # Update toggle button
            if i < len(pet_toggles):
                if is_active:
                    pet_toggles[i].SetText("[ON]")
                    pet_toggles[i].SetBackgroundHue(68)
                else:
                    pet_toggles[i].SetText("[--]")
                    pet_toggles[i].SetBackgroundHue(32)
        else:
            lbl.SetText(str(i+1) + ". ---")
            lbl.SetBackgroundHue(90)

            # Gray out toggle button
            if i < len(pet_toggles):
                pet_toggles[i].SetText("[--]")
                pet_toggles[i].SetBackgroundHue(90)

def update_tank_display():
    if TANK_PET:
        mob = API.FindMobile(TANK_PET)
        if mob:
            hp_pct = get_hp_percent(mob)
            bar = get_health_bar(hp_pct, 6)
            poison = "[P]" if is_poisoned(mob) else ""
            if mob.IsDead:
                tankLabel.SetText("Tank: " + get_mob_name(mob)[:6] + " [DEAD]")
            else:
                tankLabel.SetText("Tank: " + get_mob_name(mob)[:6] + " " + bar + poison)
        else:
            tankLabel.SetText("Tank: [Not Found]")
    else:
        tankLabel.SetText("Tank: [None]")

def update_vetkit_display():
    if VET_KIT_GRAPHIC > 0:
        if API.FindType(VET_KIT_GRAPHIC):
            vetkitLabel.SetText("VetKit: Ready")
        else:
            vetkitLabel.SetText("VetKit: Not Found!")
    else:
        vetkitLabel.SetText("VetKit: [None]")

def update_bandage_display():
    count = get_bandage_count()
    if count == 0:
        bandageLabel.SetText("Bandages: NONE!")
    elif count < 0:
        bandageLabel.SetText("Bandages: ???")
    elif count <= LOW_BANDAGE_WARNING:
        bandageLabel.SetText("Bandages: " + str(count) + " LOW")
    else:
        bandageLabel.SetText("Bandages: " + str(count))

def update_potion_display():
    """Update potion count displays"""
    heal_count = get_potion_count(POTION_HEAL)
    cure_count = get_potion_count(POTION_CURE)

    healPotionLabel.SetText("Heal:" + str(heal_count))
    curePotionLabel.SetText("Cure:" + str(cure_count))

    # Update trapped pouch button color
    if trapped_pouch_serial > 0:
        setPouchBtn.SetBackgroundHue(68)  # Green if configured
    else:
        setPouchBtn.SetBackgroundHue(43)  # Yellow if not configured

def cleanup():
    if PAUSE_HOTKEY:
        try:
            API.OnHotKey(PAUSE_HOTKEY)
        except:
            pass
    if ALL_KILL_HOTKEY:
        try:
            API.OnHotKey(ALL_KILL_HOTKEY)
        except:
            pass
    if GUARD_HOTKEY:
        try:
            API.OnHotKey(GUARD_HOTKEY)
        except:
            pass
    if FOLLOW_HOTKEY:
        try:
            API.OnHotKey(FOLLOW_HOTKEY)
        except:
            pass
    if STAY_HOTKEY:
        try:
            API.OnHotKey(STAY_HOTKEY)
        except:
            pass

def onClosed():
    cleanup()
    cancel_heal()
    cancel_friend_rez()
    API.SavePersistentVar(SETTINGS_KEY, str(gump.GetX()) + "," + str(gump.GetY()), API.PersistentVar.Char)
    API.Stop()

# ============ LOAD AND INIT ============
load_settings()

# ============ BUILD GUI ============
gump = API.Gumps.CreateGump()
API.Gumps.AddControlOnDisposed(gump, onClosed)

savedPos = API.GetPersistentVar(SETTINGS_KEY, "100,100", API.PersistentVar.Char)
posXY = savedPos.split(',')
lastX = int(posXY[0])
lastY = int(posXY[1])
gump.SetRect(lastX, lastY, 400, 380)

bg = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
bg.SetRect(0, 0, 400, 380)
gump.Add(bg)

title = API.Gumps.CreateGumpTTFLabel("Tamer Suite v2", 16, "#00d4ff", aligned="center", maxWidth=400)
title.SetPos(0, 5)
gump.Add(title)

# Bandage count (top center)
bandageLabel = API.Gumps.CreateGumpTTFLabel("Bandages: ???", 9, "#AAFFAA", aligned="center", maxWidth=400)
bandageLabel.SetPos(0, 24)
gump.Add(bandageLabel)

# ========== LEFT PANEL (HEALER) ==========
leftX = 5
y = 42

healerTitle = API.Gumps.CreateGumpTTFLabel("=== HEALER ===", 9, "#ff8800", aligned="center", maxWidth=195)
healerTitle.SetPos(leftX, y)
gump.Add(healerTitle)

y += 16
btnW = 90
btnH = 20

mageryBtn = API.Gumps.CreateSimpleButton("[BAND]" if not USE_MAGERY else "[MAGE]", btnW, btnH)
mageryBtn.SetPos(leftX, y)
mageryBtn.SetBackgroundHue(68 if not USE_MAGERY else 66)
API.Gumps.AddControlOnClick(mageryBtn, toggle_magery)
gump.Add(mageryBtn)

selfBtn = API.Gumps.CreateSimpleButton("[SELF:" + ("ON" if HEAL_SELF else "OFF") + "]", btnW, btnH)
selfBtn.SetPos(leftX + 95, y)
selfBtn.SetBackgroundHue(68 if HEAL_SELF else 90)
API.Gumps.AddControlOnClick(selfBtn, toggle_self)
gump.Add(selfBtn)

y += 22
rezBtn = API.Gumps.CreateSimpleButton("[REZ:" + ("ON" if USE_REZ else "OFF") + "]", btnW, btnH)
rezBtn.SetPos(leftX, y)
rezBtn.SetBackgroundHue(38 if USE_REZ else 90)
API.Gumps.AddControlOnClick(rezBtn, toggle_rez)
gump.Add(rezBtn)

skipBtn = API.Gumps.CreateSimpleButton("[SKIP:" + ("ON" if SKIP_OUT_OF_RANGE else "OFF") + "]", btnW, btnH)
skipBtn.SetPos(leftX + 95, y)
skipBtn.SetBackgroundHue(53 if SKIP_OUT_OF_RANGE else 90)
API.Gumps.AddControlOnClick(skipBtn, toggle_skip)
gump.Add(skipBtn)

y += 26
tankLabel = API.Gumps.CreateGumpTTFLabel("Tank: [None]", 9, "#FFAAAA")
tankLabel.SetPos(leftX, y)
gump.Add(tankLabel)

y += 14
setTankBtn = API.Gumps.CreateSimpleButton("[SET]", 45, 18)
setTankBtn.SetPos(leftX, y)
setTankBtn.SetBackgroundHue(38)
API.Gumps.AddControlOnClick(setTankBtn, set_tank)
gump.Add(setTankBtn)

clrTankBtn = API.Gumps.CreateSimpleButton("[CLR]", 45, 18)
clrTankBtn.SetPos(leftX + 50, y)
clrTankBtn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(clrTankBtn, clear_tank)
gump.Add(clrTankBtn)

y += 22
vetkitLabel = API.Gumps.CreateGumpTTFLabel("VetKit: [None]", 9, "#AAAAFF")
vetkitLabel.SetPos(leftX, y)
gump.Add(vetkitLabel)

y += 14
setVetBtn = API.Gumps.CreateSimpleButton("[SET]", 45, 18)
setVetBtn.SetPos(leftX, y)
setVetBtn.SetBackgroundHue(68)
API.Gumps.AddControlOnClick(setVetBtn, set_vetkit)
gump.Add(setVetBtn)

clrVetBtn = API.Gumps.CreateSimpleButton("[CLR]", 45, 18)
clrVetBtn.SetPos(leftX + 50, y)
clrVetBtn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(clrVetBtn, clear_vetkit)
gump.Add(clrVetBtn)

y += 26
pauseBtn = API.Gumps.CreateSimpleButton("[PAUSE]", 90, btnH)
pauseBtn.SetPos(leftX, y)
pauseBtn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(pauseBtn, toggle_pause)
gump.Add(pauseBtn)

statusLabel = API.Gumps.CreateGumpTTFLabel("Running", 9, "#00ff00")
statusLabel.SetPos(leftX + 95, y + 3)
gump.Add(statusLabel)

# Friend Rez section
y += 28
friendRezTitle = API.Gumps.CreateGumpTTFLabel("=== FRIEND REZ ===", 9, "#ff66ff", aligned="center", maxWidth=195)
friendRezTitle.SetPos(leftX, y)
gump.Add(friendRezTitle)

y += 16
rezFriendLabel = API.Gumps.CreateGumpTTFLabel("Friend Rez: Inactive", 8, "#FFAAFF")
rezFriendLabel.SetPos(leftX, y)
gump.Add(rezFriendLabel)

y += 14
rezFriendBtn = API.Gumps.CreateSimpleButton("[REZ FRIEND]", 185, 20)
rezFriendBtn.SetPos(leftX, y)
rezFriendBtn.SetBackgroundHue(38)
API.Gumps.AddControlOnClick(rezFriendBtn, toggle_rez_friend)
gump.Add(rezFriendBtn)

# ========== RIGHT PANEL (COMMANDS) ==========
rightX = 205
y = 42

cmdTitle = API.Gumps.CreateGumpTTFLabel("=== COMMANDS ===", 9, "#ff6666", aligned="center", maxWidth=195)
cmdTitle.SetPos(rightX, y)
gump.Add(cmdTitle)

y += 16
redsBtn = API.Gumps.CreateSimpleButton("[REDS:" + ("ON" if TARGET_REDS else "OFF") + "]", btnW, btnH)
redsBtn.SetPos(rightX, y)
redsBtn.SetBackgroundHue(32 if TARGET_REDS else 90)
API.Gumps.AddControlOnClick(redsBtn, toggle_reds)
gump.Add(redsBtn)

graysBtn = API.Gumps.CreateSimpleButton("[GRAYS:" + ("ON" if TARGET_GRAYS else "OFF") + "]", btnW, btnH)
graysBtn.SetPos(rightX + 95, y)
graysBtn.SetBackgroundHue(53 if TARGET_GRAYS else 90)
API.Gumps.AddControlOnClick(graysBtn, toggle_grays)
gump.Add(graysBtn)

y += 22
modeBtn = API.Gumps.CreateSimpleButton("[" + ATTACK_MODE + "]", btnW, btnH)
modeBtn.SetPos(rightX, y)
modeBtn.SetBackgroundHue(66 if ATTACK_MODE == "ORDER" else 68)
API.Gumps.AddControlOnClick(modeBtn, toggle_mode)
gump.Add(modeBtn)

# Hotkey display
hotkeyText = "Kill:" + (ALL_KILL_HOTKEY or "-") + " G:" + (GUARD_HOTKEY or "-") + " F:" + (FOLLOW_HOTKEY or "-")
hotkeyLabel = API.Gumps.CreateGumpTTFLabel(hotkeyText, 8, "#888888")
hotkeyLabel.SetPos(rightX + 95, y + 4)
gump.Add(hotkeyLabel)

y += 26
# Bank buttons
bankBtn = API.Gumps.CreateSimpleButton("[BANK]", 60, btnH)
bankBtn.SetPos(rightX, y)
bankBtn.SetBackgroundHue(68)
API.Gumps.AddControlOnClick(bankBtn, say_bank)
gump.Add(bankBtn)

balanceBtn = API.Gumps.CreateSimpleButton("[BALANCE]", 70, btnH)
balanceBtn.SetPos(rightX + 65, y)
balanceBtn.SetBackgroundHue(66)
API.Gumps.AddControlOnClick(balanceBtn, say_balance)
gump.Add(balanceBtn)

# Manual command buttons
y += 24
allKillBtn = API.Gumps.CreateSimpleButton("[ALL KILL]", 90, btnH)
allKillBtn.SetPos(rightX, y)
allKillBtn.SetBackgroundHue(32)
API.Gumps.AddControlOnClick(allKillBtn, all_kill_manual)
gump.Add(allKillBtn)

y += 24
followAllBtn = API.Gumps.CreateSimpleButton("[FOLLOW]", 60, btnH)
followAllBtn.SetPos(rightX, y)
followAllBtn.SetBackgroundHue(68)
API.Gumps.AddControlOnClick(followAllBtn, all_follow)
gump.Add(followAllBtn)

guardAllBtn = API.Gumps.CreateSimpleButton("[GUARD]", 60, btnH)
guardAllBtn.SetPos(rightX + 65, y)
guardAllBtn.SetBackgroundHue(68)
API.Gumps.AddControlOnClick(guardAllBtn, all_guard)
gump.Add(guardAllBtn)

stayAllBtn = API.Gumps.CreateSimpleButton("[STAY]", 55, btnH)
stayAllBtn.SetPos(rightX + 130, y)
stayAllBtn.SetBackgroundHue(53)
API.Gumps.AddControlOnClick(stayAllBtn, all_stay)
gump.Add(stayAllBtn)

# New features
y += 26
potionsBtn = API.Gumps.CreateSimpleButton("[POTIONS:" + ("ON" if USE_POTIONS else "OFF") + "]", btnW, btnH)
potionsBtn.SetPos(rightX, y)
potionsBtn.SetBackgroundHue(68 if USE_POTIONS else 90)
API.Gumps.AddControlOnClick(potionsBtn, toggle_potions)
gump.Add(potionsBtn)

autoTargetBtn = API.Gumps.CreateSimpleButton("[AUTO-TARGET:" + ("ON" if auto_target else "OFF") + "]", btnW, btnH)
autoTargetBtn.SetPos(rightX + 95, y)
autoTargetBtn.SetBackgroundHue(68 if auto_target else 90)
API.Gumps.AddControlOnClick(autoTargetBtn, toggle_auto_target)
gump.Add(autoTargetBtn)

y += 24
setPouchBtn = API.Gumps.CreateSimpleButton("[SET POUCH]", 90, btnH)
setPouchBtn.SetPos(rightX, y)
setPouchBtn.SetBackgroundHue(43)
API.Gumps.AddControlOnClick(setPouchBtn, on_set_trapped_pouch)
gump.Add(setPouchBtn)

usePouchBtn = API.Gumps.CreateSimpleButton("[USE POUCH:" + ("ON" if use_trapped_pouch else "OFF") + "]", 95, btnH)
usePouchBtn.SetPos(rightX + 95, y)
usePouchBtn.SetBackgroundHue(68 if use_trapped_pouch else 90)
API.Gumps.AddControlOnClick(usePouchBtn, toggle_use_trapped_pouch)
gump.Add(usePouchBtn)

# Potion counts
y += 24
healPotionLabel = API.Gumps.CreateGumpTTFLabel("Heal:0", 8, "#ffaa00")
healPotionLabel.SetPos(rightX, y)
gump.Add(healPotionLabel)

curePotionLabel = API.Gumps.CreateGumpTTFLabel("Cure:0", 8, "#ffff00")
curePotionLabel.SetPos(rightX + 65, y)
gump.Add(curePotionLabel)

# ========== BOTTOM PANEL (SHARED PETS) ==========
y = 230
petsTitle = API.Gumps.CreateGumpTTFLabel("=== PETS (click=follow/heal) ===", 9, "#00ffaa", aligned="center", maxWidth=400)
petsTitle.SetPos(0, y)
gump.Add(petsTitle)

y += 16
pet_labels = []
pet_toggles = []
for i in range(MAX_PETS):
    lbl = API.Gumps.CreateSimpleButton(str(i+1) + ". ---", 340, 18)
    lbl.SetPos(5, y + (i * 20))
    lbl.SetBackgroundHue(90)
    API.Gumps.AddControlOnClick(lbl, make_pet_click_callback(i))
    gump.Add(lbl)
    pet_labels.append(lbl)

    # Add toggle button for ORDER mode
    def make_toggle_callback(idx):
        def callback():
            toggle_pet_active(idx)
        return callback

    toggleBtn = API.Gumps.CreateSimpleButton("[ON]", 45, 18)
    toggleBtn.SetPos(350, y + (i * 20))
    toggleBtn.SetBackgroundHue(68)
    API.Gumps.AddControlOnClick(toggleBtn, make_toggle_callback(i))
    gump.Add(toggleBtn)
    pet_toggles.append(toggleBtn)

y += (MAX_PETS * 20) + 4

# Pet management buttons
addBtn = API.Gumps.CreateSimpleButton("[ADD]", 60, 18)
addBtn.SetPos(5, y)
addBtn.SetBackgroundHue(68)
API.Gumps.AddControlOnClick(addBtn, add_pet)
gump.Add(addBtn)

removeBtn = API.Gumps.CreateSimpleButton("[DEL]", 60, 18)
removeBtn.SetPos(70, y)
removeBtn.SetBackgroundHue(32)
API.Gumps.AddControlOnClick(removeBtn, remove_pet)
gump.Add(removeBtn)

clearBtn = API.Gumps.CreateSimpleButton("[CLR ALL]", 70, 18)
clearBtn.SetPos(135, y)
clearBtn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(clearBtn, clear_all_pets)
gump.Add(clearBtn)

API.Gumps.AddGump(gump)

# ============ REGISTER HOTKEYS ============
if PAUSE_HOTKEY:
    API.OnHotKey(PAUSE_HOTKEY, toggle_pause)
if ALL_KILL_HOTKEY:
    API.OnHotKey(ALL_KILL_HOTKEY, all_kill)
if GUARD_HOTKEY:
    API.OnHotKey(GUARD_HOTKEY, all_guard)
if FOLLOW_HOTKEY:
    API.OnHotKey(FOLLOW_HOTKEY, all_follow)
if STAY_HOTKEY:
    API.OnHotKey(STAY_HOTKEY, all_stay)

# Initial display
update_pet_display()
update_tank_display()
update_vetkit_display()
update_bandage_display()
update_potion_display()
update_rez_friend_display()

API.SysMsg("Tamer Suite v2 loaded! NEW: Friend Rez, Potions, Trapped Pouch, Auto-Target", 68)
API.SysMsg("Kill:" + (ALL_KILL_HOTKEY or "-") + " Guard:" + (GUARD_HOTKEY or "-") + " Follow:" + (FOLLOW_HOTKEY or "-") + " Pause:" + (PAUSE_HOTKEY or "-"), 53)

# ============ MAIN LOOP (NON-BLOCKING) ============
DISPLAY_INTERVAL = 0.3
SYNC_INTERVAL = 2.0
SAVE_INTERVAL = 10.0

next_display = time.time() + DISPLAY_INTERVAL
next_sync = time.time() + SYNC_INTERVAL
next_save = time.time() + SAVE_INTERVAL

while not API.StopRequested:
    try:
        # Process GUI clicks and HOTKEYS - always instant!
        API.ProcessCallbacks()
        
        # Check if current heal is done
        check_heal_complete()
        
        # Save position
        if time.time() > next_save:
            API.SavePersistentVar(SETTINGS_KEY, str(gump.GetX()) + "," + str(gump.GetY()), API.PersistentVar.Char)
            next_save = time.time() + SAVE_INTERVAL
        
        # Sync pets
        if time.time() > next_sync:
            sync_pets_from_storage()
            next_sync = time.time() + SYNC_INTERVAL
        
        # Update displays
        if time.time() > next_display:
            update_pet_display()
            update_tank_display()
            update_vetkit_display()
            update_bandage_display()
            update_potion_display()
            if rez_friend_active:
                update_rez_friend_display()
            next_display = time.time() + DISPLAY_INTERVAL
        
        # Check alerts (even when paused)
        check_critical_alerts()

        # FRIEND REZ LOGIC (highest priority - pauses all other healing)
        if not PAUSED and rez_friend_active:
            statusLabel.SetText("Rezzing: " + rez_friend_name + " (#" + str(rez_friend_attempts) + ")")
            attempt_friend_rez()
            # Continue to next iteration - skip normal healing
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
        API.SysMsg("Error: " + str(e), 32)
        API.Pause(1)

cleanup()