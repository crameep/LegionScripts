# ============================================================
# Pet Healer v7.0
# by Coryigon for UO Unchained
# ============================================================
#
# A standalone pet healer with a sophisticated priority system.
# Uses blocking waits for simplicity - if you need instant hotkeys
# during heals, use Tamer Suite instead.
#
# Healing Priority (highest to lowest):
#   1. Friend resurrection (if enabled)
#   2. Self (poison first, then HP damage)
#   3. Tank pet (poison, then low HP)
#   4. Other poisoned pets
#   5. Lowest HP pet
#   6. Top-off healing
#   7. Vet kit (when tank + N other pets are hurt)
#
# Features:
#   - Range checking with auto-follow
#   - Journal tracking for heal confirmations
#   - Vet kit support for multi-pet healing
#   - Configurable thresholds and timing
#
# ============================================================
import API
import time
from collections import namedtuple

__version__ = "7.0"

# ============ USER SETTINGS ============
# Item graphic
BANDAGE = 3617                # Bandage item ID
DEBUG = False

# General options
FOLLOW_PET = True             # Auto-follow pets to heal them
MAX_PETS = 5                  # Maximum pets to track

# === TIMING CONSTANTS (adjust for your DEX) ===
# Reference: 8 - (DEX / 20) seconds
# 100 DEX = 3s, 80 DEX = 4s, 60 DEX = 5s
SELF_DELAY = 4.5
VET_DELAY = 4.5
REZ_DELAY = 10.0              # Seconds to wait for pet resurrection
CAST_DELAY = 2.5              # Seconds for Greater Heal spell

# === TIMING CONSTANTS (internal) ===
FOLLOW_TIMEOUT = 5.0          # Max seconds to follow a pet
TARGET_SETTLE_DELAY = 0.3     # Delay after canceling targets
ACTION_REGISTER_DELAY = 0.5   # Delay for action to register
JOURNAL_CHECK_INTERVAL = 0.3  # How often to check journal
JOURNAL_INITIAL_DELAY = 0.5   # Initial delay before checking journal
DISPLAY_UPDATE_INTERVAL = 0.3 # How often to update GUI displays (faster for poison)
SETTINGS_SAVE_INTERVAL = 10   # How often to save window position
LOW_BANDAGE_WARNING = 10      # Warn when bandages fall below this count

# === RANGE SETTINGS ===
BANDAGE_RANGE = 2             # Max tiles for bandaging (1-2 in most shards)
SPELL_RANGE = 10              # Max tiles for Greater Heal spell
SKIP_OUT_OF_RANGE = True      # Skip out-of-range targets instead of following
MAX_FOLLOW_RANGE = 15         # Don't even try to follow if further than this

# === HEALTH THRESHOLDS ===
SELF_HEAL_THRESHOLD = 15      # Heal yourself when missing this many HP
TANK_HP_PERCENT = 50          # Priority heal tank when below this % HP
PET_HP_PERCENT = 90           # Heal other pets when below this % HP

# === JOURNAL TRACKING ===
USE_JOURNAL_TRACKING = False  # Use journal to detect bandage finish (False = fixed timers only)

# Journal messages for bandage detection (customize for your shard)
JOURNAL_FINISH_MESSAGES = [
    "You finish applying the bandages",
    "You heal what little damage",
    "You apply the bandages, but they barely help",
    "You have cured the target of all poisons"
]

JOURNAL_FAIL_MESSAGES = [
    "You are too far away",
    "You did not stay close enough",
    "You were disturbed",
    "That is too far away",
    "Target cannot be seen"
]

# === POISON CURING ===
CURE_POISON = True            # Cure poisoned pets before healing

# === VET KIT ===
VET_KIT_ID = 0                # Vet kit item ID (0 = not set, use [SET VET KIT] button)
VET_KIT_THRESHOLD = 2         # Use vet kit when this many pets need healing (default 2)
VET_KIT_HP_PERCENT = 70       # HP% threshold - pets below this count as "hurt"
VET_KIT_DELAY = 5.0           # Seconds to wait after using vet kit
VET_KIT_COOLDOWN = 10.0       # Minimum seconds between vet kit uses
# Vet kit triggers when: VET_KIT_THRESHOLD or more pets are below VET_KIT_HP_PERCENT
# =========================================

# Named tuple for cleaner heal action returns
HealAction = namedtuple('HealAction', ['target', 'is_self', 'status', 'action_type'])
# action_type: 'none', 'heal', 'rez', 'vetkit', 'rez_friend'

# Persistent storage keys
SETTINGS_KEY = "PetHealer_XY"
MAGERY_KEY = "PetHealer_UseMagery"
PETS_KEY = "PetHealer_Pets"
REZ_KEY = "PetHealer_UseRez"
FOLLOW_KEY = "PetHealer_Follow"
TANK_KEY = "PetHealer_Tank"
HEALSELF_KEY = "PetHealer_HealSelf"
VETKIT_KEY = "PetHealer_VetKitID"
JOURNAL_KEY = "PetHealer_UseJournal"
SKIPOOR_KEY = "PetHealer_SkipOOR"

# Runtime state
USE_MAGERY = False
USE_REZ = False
HEAL_SELF = True
PETS = []
TANK_PET = 0
pet_labels = []
last_vetkit_use = 0  # Timestamp of last vet kit use
last_no_bandage_warning = 0  # Timestamp of last "no bandages" warning
NO_BANDAGE_COOLDOWN = 10.0  # Seconds to wait before warning again about no bandages

# Friend Rez state
rez_friend_target = 0       # Serial of friend to resurrect
rez_friend_active = False   # Whether we're actively trying to rez a friend
rez_friend_attempts = 0     # Number of rez attempts made
rez_friend_name = ""        # Name of friend being rezzed
MAX_REZ_ATTEMPTS = 50       # Give up after this many attempts
REZ_FRIEND_DELAY = 8.0      # Delay between rez attempts on friends

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

# ============ VALIDATION ============
def validate_settings():
    """Ensure all settings are within valid ranges"""
    global SELF_DELAY, VET_DELAY, REZ_DELAY, CAST_DELAY
    global TANK_HP_PERCENT, PET_HP_PERCENT, SELF_HEAL_THRESHOLD
    global VET_KIT_THRESHOLD, VET_KIT_HP_PERCENT, VET_KIT_DELAY, VET_KIT_COOLDOWN
    
    # Timing (minimum 0.5 seconds)
    SELF_DELAY = max(0.5, SELF_DELAY)
    VET_DELAY = max(0.5, VET_DELAY)
    REZ_DELAY = max(1.0, REZ_DELAY)
    CAST_DELAY = max(0.5, CAST_DELAY)
    VET_KIT_DELAY = max(1.0, VET_KIT_DELAY)
    VET_KIT_COOLDOWN = max(1.0, VET_KIT_COOLDOWN)
    
    # Percentages (1-100)
    TANK_HP_PERCENT = max(1, min(100, TANK_HP_PERCENT))
    PET_HP_PERCENT = max(1, min(100, PET_HP_PERCENT))
    VET_KIT_HP_PERCENT = max(1, min(100, VET_KIT_HP_PERCENT))
    
    # Thresholds (positive values)
    SELF_HEAL_THRESHOLD = max(1, SELF_HEAL_THRESHOLD)
    VET_KIT_THRESHOLD = max(1, VET_KIT_THRESHOLD)

# ============ UTILITY FUNCTIONS ============
def is_poisoned(mob):
    """Safely check if a mobile is poisoned - tries multiple detection methods"""
    if not mob:
        return False
    try:
        # Primary check
        if hasattr(mob, 'Poisoned') and mob.Poisoned:
            return True
        # Some APIs use IsPoisoned
        if hasattr(mob, 'IsPoisoned') and mob.IsPoisoned:
            return True
        # Check for poison flag in status flags if available
        if hasattr(mob, 'StatusFlags'):
            # Poison flag is typically 0x04 in UO
            if mob.StatusFlags & 0x04:
                return True
        return False
    except:
        return False

def is_player_poisoned():
    """Fast check specifically for player poison status"""
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
    """Check if the player is dead"""
    try:
        return API.Player.IsDead
    except:
        # Fallback: check if hits are 0
        try:
            return API.Player.Hits <= 0
        except:
            return False

def get_mob_name(mob, default="Unknown"):
    """Safely get mobile name"""
    if not mob:
        return default
    try:
        return mob.Name if mob.Name else default
    except:
        return default

def get_hp_percent(mob):
    """Safely calculate HP percentage"""
    if not mob:
        return 0
    try:
        if mob.HitsMax > 0:
            return int((mob.Hits / mob.HitsMax) * 100)
        return 100
    except:
        return 100

def get_distance(mob):
    """Safely get distance to mobile"""
    if not mob:
        return 999
    try:
        return mob.Distance if hasattr(mob, 'Distance') else 999
    except:
        return 999

def is_in_heal_range(mob, use_magery=False):
    """Check if mobile is in range for healing"""
    if not mob:
        return False
    
    distance = get_distance(mob)
    max_range = SPELL_RANGE if use_magery else BANDAGE_RANGE
    return distance <= max_range

def is_worth_following(mob):
    """Check if mobile is close enough to be worth following"""
    if not mob:
        return False
    if not FOLLOW_PET:
        return False
    if SKIP_OUT_OF_RANGE:
        return False
    
    distance = get_distance(mob)
    return distance <= MAX_FOLLOW_RANGE

def can_heal_target(serial, use_magery=False):
    """
    Check if we can heal a target (in range or worth following).
    Returns: (can_heal, reason)
    """
    mob = API.FindMobile(serial)
    if not mob:
        return (False, "not_found")
    
    if is_in_heal_range(mob, use_magery):
        return (True, "in_range")
    
    if is_worth_following(mob):
        return (True, "will_follow")
    
    return (False, "out_of_range")

def check_bandages():
    """
    Check if bandages are available. 
    Returns False and sets cooldown if none found (prevents spam).
    """
    global last_no_bandage_warning
    
    if not API.FindType(BANDAGE):
        # Check if we're still in cooldown
        if time.time() - last_no_bandage_warning < NO_BANDAGE_COOLDOWN:
            # Silent fail - already warned recently
            return False
        
        # Warn and set cooldown
        last_no_bandage_warning = time.time()
        API.SysMsg("OUT OF BANDAGES!", 32)
        API.HeadMsg("NO BANDAGES!", API.Player.Serial, 32)
        return False
    
    # Try to get count if API supports it
    try:
        count = API.Found.Amount if hasattr(API.Found, 'Amount') else -1
        if count > 0 and count <= LOW_BANDAGE_WARNING:
            API.SysMsg("Low bandages: " + str(count) + " remaining", 53)
    except:
        pass
    
    return True

def has_bandages_available():
    """
    Quick check if bandages exist without warnings.
    Used to skip healing entirely when we know there's none.
    """
    # If we recently warned about no bandages, assume still none
    if time.time() - last_no_bandage_warning < NO_BANDAGE_COOLDOWN:
        return False
    
    # FindType returns PyItem if found, None/falsy if not
    return bool(API.FindType(BANDAGE))

def cancel_all_targets():
    """Safely cancel any pending targets - call before AND after actions"""
    try:
        API.CancelPreTarget()
    except:
        pass
    try:
        if API.HasTarget():
            API.CancelTarget()
    except:
        pass
    # Small delay to let it register
    API.Pause(0.1)

def clear_stray_cursor():
    """Quick check and clear of any stray target cursor"""
    try:
        if API.HasTarget():
            API.CancelTarget()
            if DEBUG:
                API.SysMsg("DEBUG: Cleared stray cursor", 43)
    except:
        pass

# ============ PERSISTENCE ============
def load_settings():
    global USE_MAGERY, USE_REZ, FOLLOW_PET, PETS, TANK_PET, HEAL_SELF, VET_KIT_ID, USE_JOURNAL_TRACKING, SKIP_OUT_OF_RANGE
    
    usemag = API.GetPersistentVar(MAGERY_KEY, "False", API.PersistentVar.Char)
    USE_MAGERY = (usemag == "True")
    
    userez = API.GetPersistentVar(REZ_KEY, "False", API.PersistentVar.Char)
    USE_REZ = (userez == "True")
    
    follow = API.GetPersistentVar(FOLLOW_KEY, "True", API.PersistentVar.Char)
    FOLLOW_PET = (follow == "True")
    
    healself = API.GetPersistentVar(HEALSELF_KEY, "True", API.PersistentVar.Char)
    HEAL_SELF = (healself == "True")
    
    usejournal = API.GetPersistentVar(JOURNAL_KEY, "False", API.PersistentVar.Char)
    USE_JOURNAL_TRACKING = (usejournal == "True")
    
    skipoor = API.GetPersistentVar(SKIPOOR_KEY, "True", API.PersistentVar.Char)
    SKIP_OUT_OF_RANGE = (skipoor == "True")
    
    tank_str = API.GetPersistentVar(TANK_KEY, "0", API.PersistentVar.Char)
    try:
        TANK_PET = int(tank_str)
    except:
        TANK_PET = 0
    
    vetkit_str = API.GetPersistentVar(VETKIT_KEY, "0", API.PersistentVar.Char)
    try:
        VET_KIT_ID = int(vetkit_str)
    except:
        VET_KIT_ID = 0
    
    pets_str = API.GetPersistentVar(PETS_KEY, "", API.PersistentVar.Char)
    if pets_str:
        try:
            PETS = [int(p) for p in pets_str.split(',') if p.strip()]
        except:
            PETS = []

def save_pets():
    pets_str = ','.join(str(p) for p in PETS)
    API.SavePersistentVar(PETS_KEY, pets_str, API.PersistentVar.Char)

def save_tank():
    API.SavePersistentVar(TANK_KEY, str(TANK_PET), API.PersistentVar.Char)

def save_vetkit():
    API.SavePersistentVar(VETKIT_KEY, str(VET_KIT_ID), API.PersistentVar.Char)

def save_journal_setting():
    API.SavePersistentVar(JOURNAL_KEY, "True" if USE_JOURNAL_TRACKING else "False", API.PersistentVar.Char)

def save_skipoor_setting():
    API.SavePersistentVar(SKIPOOR_KEY, "True" if SKIP_OUT_OF_RANGE else "False", API.PersistentVar.Char)

# ============ JOURNAL TRACKING ============
def check_journal_for_message(msg):
    """
    Check if journal contains a message using API.InJournal.
    Returns True if found, False if not found.
    """
    try:
        return API.InJournal(msg, False)  # Don't clear matches
    except Exception as e:
        if DEBUG:
            API.SysMsg("DEBUG: Journal check error: " + str(e), 32)
        return False

def clear_journal_safe():
    """Safely clear journal"""
    try:
        API.ClearJournal()
    except:
        pass

def wait_for_bandage(target_name, max_wait):
    """
    Wait for bandage to finish using journal tracking or fixed timer.
    Returns True if successful, False if interrupted.
    """
    if not USE_JOURNAL_TRACKING:
        if DEBUG:
            API.SysMsg("DEBUG: Using fixed timer (" + str(max_wait) + "s)", 88)
        API.Pause(max_wait)
        return True
    
    if DEBUG:
        API.SysMsg("DEBUG: Watching journal (max " + str(max_wait) + "s)", 88)
    
    start_time = time.time()
    
    # Initial delay to let the action register before checking
    API.Pause(JOURNAL_INITIAL_DELAY)
    
    while time.time() - start_time < max_wait:
        # Check for success messages
        for msg in JOURNAL_FINISH_MESSAGES:
            if check_journal_for_message(msg):
                clear_journal_safe()
                elapsed = round(time.time() - start_time, 1)
                if DEBUG:
                    API.SysMsg("DEBUG: Bandage finished (" + str(elapsed) + "s)", 68)
                return True
        
        # Check for failure messages
        for msg in JOURNAL_FAIL_MESSAGES:
            if check_journal_for_message(msg):
                clear_journal_safe()
                if DEBUG:
                    API.SysMsg("DEBUG: Bandage failed - " + msg, 32)
                return False
        
        API.Pause(JOURNAL_CHECK_INTERVAL)
    
    # Timeout - fall back to assuming it worked
    if DEBUG:
        API.SysMsg("DEBUG: Journal timeout, assuming success", 53)
    clear_journal_safe()
    return True

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

# ============ FOLLOWING ============
def follow_to_target(target_serial, max_distance=1):
    """
    Follow a mobile until within range or timeout.
    Returns the mobile if successful, None if failed.
    """
    mob = API.FindMobile(target_serial)
    if not mob:
        return None
    
    current_distance = get_distance(mob)
    if current_distance <= max_distance:
        return mob
    
    if DEBUG:
        API.SysMsg("DEBUG: Following " + get_mob_name(mob) + ", distance=" + str(current_distance), 88)
    
    API.AutoFollow(target_serial)
    timeout = time.time() + FOLLOW_TIMEOUT
    
    while time.time() < timeout:
        mob = API.FindMobile(target_serial)
        if not mob:
            API.CancelAutoFollow()
            if DEBUG:
                API.SysMsg("DEBUG: Lost target while following", 32)
            return None
        
        if get_distance(mob) <= max_distance:
            break
        
        API.Pause(0.2)
    
    API.CancelAutoFollow()
    return mob

# ============ HEALING FUNCTIONS ============
def heal_with_magery(target_serial):
    """Heal target using Greater Heal spell"""
    if DEBUG:
        API.SysMsg("DEBUG: Casting Greater Heal", 88)
    
    # Clear any existing cursor
    cancel_all_targets()
    
    API.PreTarget(target_serial, "beneficial")
    API.CastSpell("Greater Heal")
    API.Pause(CAST_DELAY)
    
    # Cleanup
    clear_stray_cursor()
    
    return True

def heal_self_with_bandage():
    """Heal self using BandageSelf() API"""
    if DEBUG:
        API.SysMsg("DEBUG: Using BandageSelf()", 88)
    
    # Clear any existing cursor first
    clear_stray_cursor()
    
    clear_journal_safe()
    result = API.BandageSelf()
    
    if not result:
        if DEBUG:
            API.SysMsg("DEBUG: BandageSelf failed - no bandages?", 32)
        return False
    
    wait_for_bandage("Self", SELF_DELAY)
    
    # Cleanup
    clear_stray_cursor()
    
    return True

def heal_pet_with_bandage(target_serial):
    """Heal pet using PreTarget + UseObject method"""
    mob = API.FindMobile(target_serial)
    if not mob:
        if DEBUG:
            API.SysMsg("DEBUG: Target not found", 32)
        return False
    
    # Check range FIRST - before doing anything
    distance = get_distance(mob)
    if distance > BANDAGE_RANGE:
        if FOLLOW_PET and not SKIP_OUT_OF_RANGE:
            # Follow to get in range
            if DEBUG:
                API.SysMsg("DEBUG: Following " + get_mob_name(mob) + " (" + str(distance) + " tiles)", 88)
            mob = follow_to_target(target_serial, BANDAGE_RANGE)
            if not mob:
                if DEBUG:
                    API.SysMsg("DEBUG: Failed to reach target", 32)
                return False
        else:
            # Out of range and not following - skip silently
            if DEBUG:
                API.SysMsg("DEBUG: " + get_mob_name(mob) + " out of range (" + str(distance) + ")", 43)
            return False
    
    # Re-check distance after potential follow
    mob = API.FindMobile(target_serial)
    if not mob or get_distance(mob) > BANDAGE_RANGE:
        if DEBUG:
            API.SysMsg("DEBUG: Still out of range after follow", 32)
        return False
    
    if DEBUG:
        API.SysMsg("DEBUG: Bandaging " + get_mob_name(mob), 88)
    
    # Check bandages
    if not check_bandages():
        return False
    
    # Clear any existing target cursor first
    cancel_all_targets()
    
    # PreTarget + UseObject (confirmed working method)
    if DEBUG:
        API.SysMsg("DEBUG: PreTarget + UseObject", 88)
    
    clear_journal_safe()
    API.PreTarget(target_serial, "beneficial")
    API.Pause(0.2)
    
    # Use the bandage
    API.UseObject(API.Found, False)
    API.Pause(ACTION_REGISTER_DELAY)
    
    # IMPORTANT: Cancel the pre-target after use
    API.CancelPreTarget()
    
    # Clear any stray cursor that might have appeared
    clear_stray_cursor()
    
    wait_for_bandage(get_mob_name(mob), VET_DELAY)
    
    # Final cleanup
    clear_stray_cursor()
    
    return True

def heal_target(target_serial, is_self=False):
    """Main healing dispatcher"""
    if is_self:
        target_serial = API.Player.Serial
        name = "Self"
        if DEBUG:
            API.SysMsg("DEBUG: Healing self", 88)
    else:
        mob = API.FindMobile(target_serial)
        if not mob:
            if DEBUG:
                API.SysMsg("DEBUG: Mob not found", 32)
            clear_stray_cursor()
            return False
        name = get_mob_name(mob)
        if DEBUG:
            API.SysMsg("DEBUG: Healing " + name, 88)
    
    cancel_all_targets()
    API.HeadMsg("Healing: " + name, target_serial, 68)
    
    result = False
    if USE_MAGERY:
        result = heal_with_magery(target_serial)
    elif is_self:
        result = heal_self_with_bandage()
    else:
        result = heal_pet_with_bandage(target_serial)
    
    # Always cleanup after healing attempt
    clear_stray_cursor()
    
    return result

def resurrect_pet(pet_serial):
    """Attempt to resurrect a dead pet using bandages"""
    mob = API.FindMobile(pet_serial)
    if not mob:
        return False
    
    if not mob.IsDead:
        return False
    
    # Check range FIRST
    distance = get_distance(mob)
    if distance > BANDAGE_RANGE:
        if FOLLOW_PET and not SKIP_OUT_OF_RANGE:
            mob = follow_to_target(pet_serial, BANDAGE_RANGE)
            if not mob:
                return False
        else:
            if DEBUG:
                API.SysMsg("DEBUG: Dead pet out of range (" + str(distance) + ")", 43)
            return False
    
    # Re-check after follow
    mob = API.FindMobile(pet_serial)
    if not mob or get_distance(mob) > BANDAGE_RANGE:
        return False
    
    cancel_all_targets()
    
    name = get_mob_name(mob)
    API.HeadMsg("Resurrecting: " + name, pet_serial, 38)
    API.SysMsg("Attempting to resurrect " + name, 38)
    
    # Check bandages
    if not check_bandages():
        return False
    
    # PreTarget + UseObject
    clear_journal_safe()
    API.PreTarget(pet_serial, "beneficial")
    API.Pause(0.2)
    API.UseObject(API.Found, False)
    API.Pause(ACTION_REGISTER_DELAY)
    API.CancelPreTarget()
    
    # Clear stray cursor
    clear_stray_cursor()
    
    wait_for_bandage(name, REZ_DELAY)
    
    # Final cleanup
    clear_stray_cursor()
    
    API.SysMsg("Rez attempt complete", 68)
    return True

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
    """
    Attempt to resurrect the targeted friend. Returns True if successful.
    Detection methods:
    1. Primary: mob.IsDead property (works if we can see the mobile's health bar)
    2. Secondary: Journal messages (especially useful with journal mode ON)
    """
    global rez_friend_attempts, rez_friend_active
    
    if not rez_friend_active or rez_friend_target == 0:
        return False
    
    mob = API.FindMobile(rez_friend_target)
    if not mob:
        API.SysMsg("Lost target - " + rez_friend_name + " not found!", 32)
        cancel_friend_rez()
        return False
    
    # PRIMARY CHECK: Are they still dead? (works if their health bar is visible)
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
    
    # Follow if needed
    distance = get_distance(mob)
    if distance > BANDAGE_RANGE:
        API.SysMsg("Following " + rez_friend_name + " (distance: " + str(distance) + ")", 53)
        mob = follow_to_target(rez_friend_target, BANDAGE_RANGE)
        if not mob:
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
    API.Pause(ACTION_REGISTER_DELAY)
    API.CancelPreTarget()
    
    # Clear any stray cursor
    clear_stray_cursor()
    
    # Wait and check for success using multiple methods
    start_time = time.time()
    while time.time() - start_time < REZ_FRIEND_DELAY:
        # PRIMARY: Check if they're alive now via IsDead property
        mob = API.FindMobile(rez_friend_target)
        if mob and not mob.IsDead:
            API.SysMsg("=== " + rez_friend_name.upper() + " RESURRECTED! ===", 68)
            API.HeadMsg("RESURRECTED!", rez_friend_target, 68)
            heal_friend_after_rez()
            cancel_friend_rez()
            return True
        
        # SECONDARY: Check journal for success (useful if journal mode is ON)
        if USE_JOURNAL_TRACKING and check_rez_success():
            API.SysMsg("=== " + rez_friend_name.upper() + " RESURRECTED! (journal) ===", 68)
            API.HeadMsg("RESURRECTED!", rez_friend_target, 68)
            clear_journal_safe()
            heal_friend_after_rez()
            cancel_friend_rez()
            return True
        
        # Check for failures - don't wait the full time if we failed
        if USE_JOURNAL_TRACKING:
            fail_msg = check_rez_fail()
            if fail_msg:
                if "not damaged" in fail_msg.lower():
                    # Target is alive!
                    API.SysMsg("=== " + rez_friend_name.upper() + " IS ALIVE! ===", 68)
                    heal_friend_after_rez()
                    cancel_friend_rez()
                    return True
                else:
                    # Other failure - log and retry
                    API.SysMsg("Rez failed: " + fail_msg, 43)
                    clear_journal_safe()
                    break  # Exit wait loop, will retry
        
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
    
    # Check if in range, follow only if enabled
    mob = API.FindMobile(rez_friend_target)
    if not mob:
        return
    
    distance = get_distance(mob)
    if distance > BANDAGE_RANGE:
        if FOLLOW_PET:
            mob = follow_to_target(rez_friend_target, BANDAGE_RANGE)
            if not mob:
                API.SysMsg("Couldn't reach " + rez_friend_name + " to heal", 32)
                return
        else:
            API.SysMsg(rez_friend_name + " out of range for post-rez heal", 43)
            return
    
    # Re-check distance
    mob = API.FindMobile(rez_friend_target)
    if not mob or get_distance(mob) > BANDAGE_RANGE:
        API.SysMsg(rez_friend_name + " moved out of range", 43)
        return
    
    # Bandage them
    cancel_all_targets()
    clear_journal_safe()
    
    API.PreTarget(rez_friend_target, "beneficial")
    API.Pause(0.2)
    API.UseObject(API.Found, False)
    API.Pause(ACTION_REGISTER_DELAY)
    API.CancelPreTarget()
    
    # Clear stray cursor
    clear_stray_cursor()
    
    # Wait for bandage to finish
    wait_for_bandage(rez_friend_name, VET_DELAY)
    
    # Final cleanup
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

# ============ VET KIT ============
def count_pets_needing_heal():
    """
    Count ALL pets needing healing (below VET_KIT_HP_PERCENT or poisoned).
    Returns: total count of hurt pets
    """
    hurt_count = 0
    
    for pet in PETS:
        mob = API.FindMobile(pet)
        if not mob or mob.IsDead:
            continue
        
        # Skip out of range pets if setting enabled
        if SKIP_OUT_OF_RANGE:
            can_heal, _ = can_heal_target(pet, USE_MAGERY)
            if not can_heal:
                continue
        
        if is_poisoned(mob) or get_hp_percent(mob) < VET_KIT_HP_PERCENT:
            hurt_count += 1
    
    return hurt_count

def can_use_vetkit():
    """Check if vet kit can be used (cooldown and availability)"""
    global last_vetkit_use
    
    if VET_KIT_ID == 0:
        return False
    
    # Check cooldown
    if time.time() - last_vetkit_use < VET_KIT_COOLDOWN:
        if DEBUG:
            remaining = round(VET_KIT_COOLDOWN - (time.time() - last_vetkit_use), 1)
            API.SysMsg("DEBUG: Vet kit on cooldown (" + str(remaining) + "s)", 53)
        return False
    
    # Check if we have one
    if not API.FindType(VET_KIT_ID):
        if DEBUG:
            API.SysMsg("DEBUG: No vet kit found in backpack!", 32)
        return False
    
    return True

def use_vetkit():
    """Use the vet kit to heal multiple pets at once"""
    global last_vetkit_use
    
    if not can_use_vetkit():
        return False
    
    if DEBUG:
        API.SysMsg("DEBUG: Using Vet Kit", 88)
    API.HeadMsg("Using Vet Kit!", API.Player.Serial, 68)
    
    # Clear any existing cursor first
    cancel_all_targets()
    
    clear_journal_safe()
    API.UseObject(API.Found, False)
    
    # Vet kit might auto-target all pets or need a target
    API.Pause(ACTION_REGISTER_DELAY)
    if API.HasTarget():
        # If it needs a target, target the first hurt pet
        for pet in PETS:
            mob = API.FindMobile(pet)
            if mob and not mob.IsDead:
                if is_poisoned(mob) or get_hp_percent(mob) < VET_KIT_HP_PERCENT:
                    if DEBUG:
                        API.SysMsg("DEBUG: Targeting " + get_mob_name(mob), 88)
                    API.Target(pet)
                    break
        else:
            # No valid target found, cancel the cursor
            clear_stray_cursor()
    
    wait_for_bandage("Vet Kit", VET_KIT_DELAY)
    last_vetkit_use = time.time()
    
    # Final cleanup
    clear_stray_cursor()
    
    return True

# ============ TARGET SELECTION ============
def set_vetkit():
    global VET_KIT_ID
    
    API.SysMsg("Target your VET KIT item...", 68)
    cancel_all_targets()
    
    target = API.RequestTarget(timeout=10)
    
    if target:
        item = API.FindItem(target)
        if item:
            VET_KIT_ID = item.Graphic
            save_vetkit()
            update_vetkit_display()
            API.SysMsg("Vet Kit set! ID: " + str(VET_KIT_ID), 68)
        else:
            API.SysMsg("Not a valid item!", 32)
    else:
        API.SysMsg("Targeting cancelled", 32)

def clear_vetkit():
    global VET_KIT_ID
    VET_KIT_ID = 0
    save_vetkit()
    update_vetkit_display()
    API.SysMsg("Vet Kit cleared", 68)

def add_pet():
    global PETS
    
    if len(PETS) >= MAX_PETS:
        API.SysMsg("Maximum pets reached. Remove one first.", 32)
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
                PETS.append(target)
                save_pets()
                update_pet_display()
                API.SysMsg("Added: " + get_mob_name(mob), 68)
        else:
            API.SysMsg("Not a valid mobile!", 32)
    else:
        API.SysMsg("Targeting cancelled", 32)

def remove_pet():
    global PETS, TANK_PET
    
    if not PETS:
        API.SysMsg("No pets to remove!", 32)
        return
    
    API.SysMsg("Target a pet to remove...", 68)
    cancel_all_targets()
    
    target = API.RequestTarget(timeout=10)
    
    if target:
        if target in PETS:
            mob = API.FindMobile(target)
            name = get_mob_name(mob) if mob else str(target)
            PETS.remove(target)
            if target == TANK_PET:
                TANK_PET = 0
                save_tank()
            save_pets()
            update_pet_display()
            API.SysMsg("Removed: " + name, 68)
        else:
            API.SysMsg("Not in list!", 32)
    else:
        API.SysMsg("Targeting cancelled", 32)

def set_tank():
    global TANK_PET
    
    API.SysMsg("Target your TANK pet...", 68)
    cancel_all_targets()
    
    target = API.RequestTarget(timeout=10)
    
    if target:
        mob = API.FindMobile(target)
        if mob:
            TANK_PET = target
            if target not in PETS and len(PETS) < MAX_PETS:
                PETS.append(target)
                save_pets()
            save_tank()
            update_pet_display()
            API.SysMsg("Tank set: " + get_mob_name(mob), 38)
        else:
            API.SysMsg("Not a valid mobile!", 32)
    else:
        API.SysMsg("Targeting cancelled", 32)

def clear_tank():
    global TANK_PET
    TANK_PET = 0
    save_tank()
    update_pet_display()
    API.SysMsg("Tank cleared", 68)

def clear_all_pets():
    global PETS, TANK_PET
    PETS = []
    TANK_PET = 0
    save_pets()
    save_tank()
    update_pet_display()
    API.SysMsg("All pets cleared!", 68)

# ============ PRIORITY SYSTEM ============
def get_priority_heal_target():
    """
    Determine the highest priority healing target.
    Returns HealAction namedtuple with (target, is_self, status, action_type)
    Skips out-of-range targets when SKIP_OUT_OF_RANGE is enabled.
    """
    # HIGHEST PRIORITY: Friend rez in progress
    if rez_friend_active:
        return HealAction(rez_friend_target, False, "Rezzing: " + rez_friend_name, 'rez_friend')
    
    # EARLY EXIT: If using bandages and we have none, skip all healing
    if not USE_MAGERY and not has_bandages_available():
        return HealAction(None, False, None, 'none')
    
    # 0. CHECK IF VET KIT SHOULD BE USED (before individual heals)
    # Triggers when: VET_KIT_THRESHOLD or more pets are hurt
    if VET_KIT_ID > 0 and can_use_vetkit():
        hurt_count = count_pets_needing_heal()
        if hurt_count >= VET_KIT_THRESHOLD:
            status = "Using Vet Kit (" + str(hurt_count) + " pets hurt)"
            return HealAction(None, False, status, 'vetkit')
    
    # 1. CHECK SELF (poison or damage) - but NOT if dead!
    if HEAL_SELF and not is_player_dead():
        player = API.Player
        if CURE_POISON and is_player_poisoned():
            return HealAction(player.Serial, True, "Curing SELF (poisoned)", 'heal')
        if player.HitsDiff > SELF_HEAL_THRESHOLD:
            return HealAction(player.Serial, True, "Healing: SELF", 'heal')
    
    # 2. CHECK FOR ANY POISONED PETS (urgent!) - with range check
    if CURE_POISON:
        # Check tank first
        if TANK_PET:
            mob = API.FindMobile(TANK_PET)
            if mob and not mob.IsDead and is_poisoned(mob):
                can_heal, reason = can_heal_target(TANK_PET, USE_MAGERY)
                if can_heal:
                    status = "Curing TANK: " + get_mob_name(mob) + " (poisoned)"
                    return HealAction(TANK_PET, False, status, 'heal')
                elif DEBUG:
                    API.SysMsg("DEBUG: Tank poisoned but out of range", 53)
        
        # Check other pets
        for pet in PETS:
            if pet == TANK_PET:
                continue
            mob = API.FindMobile(pet)
            if mob and not mob.IsDead and is_poisoned(mob):
                can_heal, reason = can_heal_target(pet, USE_MAGERY)
                if can_heal:
                    status = "Curing: " + get_mob_name(mob) + " (poisoned)"
                    return HealAction(pet, False, status, 'heal')
    
    # 3. CHECK TANK PET (priority if under TANK_HP_PERCENT) - with range check
    tank_needs_topoff = False
    tank_in_range = False
    if TANK_PET:
        mob = API.FindMobile(TANK_PET)
        if mob:
            can_heal, reason = can_heal_target(TANK_PET, USE_MAGERY)
            tank_in_range = can_heal
            
            if mob.IsDead and USE_REZ:
                if can_heal:
                    status = "Rezzing TANK: " + get_mob_name(mob)
                    return HealAction(TANK_PET, False, status, 'rez')
                elif DEBUG:
                    API.SysMsg("DEBUG: Tank dead but out of range (" + str(get_distance(mob)) + " tiles)", 53)
            elif not mob.IsDead:
                hp_pct = get_hp_percent(mob)
                if hp_pct < TANK_HP_PERCENT:
                    if can_heal:
                        status = "Healing TANK: " + get_mob_name(mob) + " (" + str(hp_pct) + "%)"
                        return HealAction(TANK_PET, False, status, 'heal')
                    elif DEBUG:
                        API.SysMsg("DEBUG: Tank hurt but out of range (" + str(get_distance(mob)) + " tiles)", 53)
                elif mob.HitsDiff > 0:
                    tank_needs_topoff = True
    
    # 4. CHECK OTHER PETS - find lowest HP percentage IN RANGE
    worst_pet = None
    worst_pct = 100
    worst_name = ""
    
    # Also track best out-of-range target for debug info
    oor_pet_name = None
    oor_pet_pct = 100
    
    for pet in PETS:
        if pet == TANK_PET:
            continue
        
        mob = API.FindMobile(pet)
        if not mob:
            continue
        
        can_heal, reason = can_heal_target(pet, USE_MAGERY)
        
        if mob.IsDead and USE_REZ:
            if can_heal:
                status = "Rezzing: " + get_mob_name(mob)
                return HealAction(pet, False, status, 'rez')
            # Track out of range dead pet
            continue
        
        if not mob.IsDead:
            hp_pct = get_hp_percent(mob)
            
            if can_heal:
                # In range - track for healing
                if hp_pct < worst_pct:
                    worst_pet = pet
                    worst_pct = hp_pct
                    worst_name = get_mob_name(mob)
            else:
                # Out of range - track for debug
                if hp_pct < oor_pet_pct:
                    oor_pet_name = get_mob_name(mob)
                    oor_pet_pct = hp_pct
    
    if worst_pet and worst_pct < PET_HP_PERCENT:
        status = "Healing: " + worst_name + " (" + str(worst_pct) + "%)"
        return HealAction(worst_pet, False, status, 'heal')
    
    # Debug: mention if we skipped an out-of-range pet
    if DEBUG and oor_pet_name and oor_pet_pct < PET_HP_PERCENT:
        API.SysMsg("DEBUG: " + oor_pet_name + " (" + str(oor_pet_pct) + "%) out of range, skipped", 53)
    
    # 5. TOP OFF TANK (if in range)
    if tank_needs_topoff and tank_in_range:
        mob = API.FindMobile(TANK_PET)
        if mob:
            hp_pct = get_hp_percent(mob)
            status = "Topping off TANK: " + get_mob_name(mob) + " (" + str(hp_pct) + "%)"
            return HealAction(TANK_PET, False, status, 'heal')
    
    return HealAction(None, False, None, 'none')

# ============ GUI CALLBACKS ============
def enableMagery():
    global USE_MAGERY
    USE_MAGERY = True
    API.SavePersistentVar(MAGERY_KEY, "True", API.PersistentVar.Char)
    API.SysMsg("Using Magery", 66)

def enableBandies():
    global USE_MAGERY
    USE_MAGERY = False
    API.SavePersistentVar(MAGERY_KEY, "False", API.PersistentVar.Char)
    API.SysMsg("Using Bandages", 66)

def toggle_follow():
    global FOLLOW_PET
    FOLLOW_PET = not FOLLOW_PET
    API.SavePersistentVar(FOLLOW_KEY, "True" if FOLLOW_PET else "False", API.PersistentVar.Char)
    followBtn.SetText("[FOLLOW:" + ("ON" if FOLLOW_PET else "OFF") + "]")
    followBtn.SetBackgroundHue(68 if FOLLOW_PET else 32)

def toggle_rez():
    global USE_REZ
    USE_REZ = not USE_REZ
    API.SavePersistentVar(REZ_KEY, "True" if USE_REZ else "False", API.PersistentVar.Char)
    rezBtn.SetText("[REZ:" + ("ON" if USE_REZ else "OFF") + "]")
    rezBtn.SetBackgroundHue(38 if USE_REZ else 32)

def toggle_heal_self():
    global HEAL_SELF
    HEAL_SELF = not HEAL_SELF
    API.SavePersistentVar(HEALSELF_KEY, "True" if HEAL_SELF else "False", API.PersistentVar.Char)
    selfBtn.SetText("[SELF:" + ("ON" if HEAL_SELF else "OFF") + "]")
    selfBtn.SetBackgroundHue(68 if HEAL_SELF else 32)

def toggle_journal():
    global USE_JOURNAL_TRACKING
    USE_JOURNAL_TRACKING = not USE_JOURNAL_TRACKING
    save_journal_setting()
    journalBtn.SetText("[JOURNAL:" + ("ON" if USE_JOURNAL_TRACKING else "OFF") + "]")
    journalBtn.SetBackgroundHue(66 if USE_JOURNAL_TRACKING else 32)
    mode = "Journal tracking" if USE_JOURNAL_TRACKING else "Fixed timers"
    API.SysMsg("Bandage timing: " + mode, 66)

def toggle_skipoor():
    global SKIP_OUT_OF_RANGE
    SKIP_OUT_OF_RANGE = not SKIP_OUT_OF_RANGE
    save_skipoor_setting()
    skipoorBtn.SetText("[SKIP OOR:" + ("ON" if SKIP_OUT_OF_RANGE else "OFF") + "]")
    skipoorBtn.SetBackgroundHue(53 if SKIP_OUT_OF_RANGE else 32)
    mode = "Skip out-of-range targets" if SKIP_OUT_OF_RANGE else "Follow to heal"
    API.SysMsg("Range mode: " + mode, 66)

def onClosed():
    cancel_all_targets()
    cancel_friend_rez()  # Clean up any active friend rez
    API.SavePersistentVar(SETTINGS_KEY, str(gump.GetX()) + "," + str(gump.GetY()), API.PersistentVar.Char)
    API.Stop()

# ============ DISPLAY UPDATES ============
def update_pet_display():
    for i, label in enumerate(pet_labels):
        if i < len(PETS):
            mob = API.FindMobile(PETS[i])
            if mob:
                name = get_mob_name(mob)[:10]
                tank_marker = " [T]" if PETS[i] == TANK_PET else ""
                distance = get_distance(mob)
                
                # Range indicator
                if USE_MAGERY:
                    in_range = distance <= SPELL_RANGE
                else:
                    in_range = distance <= BANDAGE_RANGE
                range_marker = "" if in_range else " [FAR:" + str(distance) + "]"
                
                if mob.IsDead:
                    label.SetText(str(i+1) + ". " + name + " [DEAD]" + tank_marker + range_marker)
                else:
                    hp_pct = get_hp_percent(mob)
                    poison_marker = " [P]" if is_poisoned(mob) else ""
                    label.SetText(str(i+1) + ". " + name + " (" + str(hp_pct) + "%)" + poison_marker + tank_marker + range_marker)
            else:
                label.SetText(str(i+1) + ". [Not Found]")
        else:
            label.SetText(str(i+1) + ". ---")

def update_tank_display():
    if TANK_PET:
        mob = API.FindMobile(TANK_PET)
        if mob:
            hp_pct = get_hp_percent(mob)
            distance = get_distance(mob)
            poison_marker = " [P]" if is_poisoned(mob) else ""
            dead_marker = " [DEAD]" if mob.IsDead else ""
            
            # Range check
            if USE_MAGERY:
                in_range = distance <= SPELL_RANGE
            else:
                in_range = distance <= BANDAGE_RANGE
            range_marker = "" if in_range else " [FAR:" + str(distance) + "]"
            
            tankLabel.SetText("Tank: " + get_mob_name(mob) + " (" + str(hp_pct) + "%)" + poison_marker + dead_marker + range_marker)
        else:
            tankLabel.SetText("Tank: [Not Found]")
    else:
        tankLabel.SetText("Tank: [None Set]")

def update_vetkit_display():
    if VET_KIT_ID > 0:
        if API.FindType(VET_KIT_ID):
            vetkitLabel.SetText("Vet Kit: ID " + str(VET_KIT_ID) + " [READY]")
        else:
            vetkitLabel.SetText("Vet Kit: ID " + str(VET_KIT_ID) + " [NOT FOUND]")
    else:
        vetkitLabel.SetText("Vet Kit: [Not Set]")

# ============ INITIALIZATION ============
# Validate settings on load
validate_settings()

# Load persistent settings
load_settings()

# Build GUI
savedPos = API.GetPersistentVar(SETTINGS_KEY, "100,100", API.PersistentVar.Char)
posXY = savedPos.split(',')
lastX = int(posXY[0])
lastY = int(posXY[1])

gump = API.Gumps.CreateGump()
API.Gumps.AddControlOnDisposed(gump, onClosed)
gump.SetRect(lastX, lastY, 300, 470)

bg = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
bg.SetRect(0, 0, 300, 470)
gump.Add(bg)

title = API.Gumps.CreateGumpTTFLabel("Pet Healer v7.0", 18, "#FF8800", aligned="center", maxWidth=300)
title.SetPos(0, 5)
gump.Add(title)

priorityLabel = API.Gumps.CreateGumpTTFLabel("Rez > SelfPoison > VetKit(2+) > Tank > Pets", 8, "#888888", aligned="center", maxWidth=300)
priorityLabel.SetPos(0, 25)
gump.Add(priorityLabel)

timingLabel = API.Gumps.CreateGumpTTFLabel("Self:" + str(SELF_DELAY) + "s | Vet:" + str(VET_DELAY) + "s | Rez:" + str(REZ_DELAY) + "s", 9, "#AAFFAA", aligned="center", maxWidth=300)
timingLabel.SetPos(0, 40)
gump.Add(timingLabel)

rangeLabel = API.Gumps.CreateGumpTTFLabel("Range: Bandage=" + str(BANDAGE_RANGE) + " | Spell=" + str(SPELL_RANGE) + " tiles", 8, "#FFAAFF", aligned="center", maxWidth=300)
rangeLabel.SetPos(0, 52)
gump.Add(rangeLabel)

methodLabel = API.Gumps.CreateGumpTTFLabel("Heal:", 11, "#AAAAAA", aligned="left", maxWidth=50)
methodLabel.SetPos(10, 65)
gump.Add(methodLabel)

mageryBtn = API.Gumps.CreateGumpRadioButton("Magery", 0)
mageryBtn.IsChecked = USE_MAGERY
mageryBtn.SetRect(45, 63, 70, 22)
API.Gumps.AddControlOnClick(mageryBtn, enableMagery)
gump.Add(mageryBtn)

bandiesBtn = API.Gumps.CreateGumpRadioButton("Bandages", 0)
bandiesBtn.IsChecked = not USE_MAGERY
bandiesBtn.SetRect(115, 63, 80, 22)
API.Gumps.AddControlOnClick(bandiesBtn, enableBandies)
gump.Add(bandiesBtn)

# Row 1: Self, Follow, Rez
selfBtn = API.Gumps.CreateSimpleButton("[SELF:" + ("ON" if HEAL_SELF else "OFF") + "]", 90, 20)
selfBtn.SetPos(5, 88)
selfBtn.SetBackgroundHue(68 if HEAL_SELF else 32)
API.Gumps.AddControlOnClick(selfBtn, toggle_heal_self)
gump.Add(selfBtn)

followBtn = API.Gumps.CreateSimpleButton("[FOLLOW:" + ("ON" if FOLLOW_PET else "OFF") + "]", 90, 20)
followBtn.SetPos(100, 88)
followBtn.SetBackgroundHue(68 if FOLLOW_PET else 32)
API.Gumps.AddControlOnClick(followBtn, toggle_follow)
gump.Add(followBtn)

rezBtn = API.Gumps.CreateSimpleButton("[REZ:" + ("ON" if USE_REZ else "OFF") + "]", 90, 20)
rezBtn.SetPos(195, 88)
rezBtn.SetBackgroundHue(38 if USE_REZ else 32)
API.Gumps.AddControlOnClick(rezBtn, toggle_rez)
gump.Add(rezBtn)

# Row 2: Journal toggle and Skip OOR toggle
journalBtn = API.Gumps.CreateSimpleButton("[JOURNAL:" + ("ON" if USE_JOURNAL_TRACKING else "OFF") + "]", 140, 20)
journalBtn.SetPos(5, 111)
journalBtn.SetBackgroundHue(66 if USE_JOURNAL_TRACKING else 32)
API.Gumps.AddControlOnClick(journalBtn, toggle_journal)
gump.Add(journalBtn)

skipoorBtn = API.Gumps.CreateSimpleButton("[SKIP OOR:" + ("ON" if SKIP_OUT_OF_RANGE else "OFF") + "]", 140, 20)
skipoorBtn.SetPos(150, 111)
skipoorBtn.SetBackgroundHue(53 if SKIP_OUT_OF_RANGE else 32)
API.Gumps.AddControlOnClick(skipoorBtn, toggle_skipoor)
gump.Add(skipoorBtn)

# === FRIEND REZ SECTION ===
rezFriendSection = API.Gumps.CreateGumpTTFLabel("=== FRIEND REZ ===", 10, "#ff66ff", aligned="center", maxWidth=300)
rezFriendSection.SetPos(0, 136)
gump.Add(rezFriendSection)

rezFriendLabel = API.Gumps.CreateGumpTTFLabel("Friend Rez: Inactive", 10, "#FFAAFF", aligned="center", maxWidth=300)
rezFriendLabel.SetPos(0, 152)
gump.Add(rezFriendLabel)

rezFriendBtn = API.Gumps.CreateSimpleButton("[REZ FRIEND]", 285, 22)
rezFriendBtn.SetPos(5, 168)
rezFriendBtn.SetBackgroundHue(38)
API.Gumps.AddControlOnClick(rezFriendBtn, toggle_rez_friend)
gump.Add(rezFriendBtn)

# Tank section
tankSection = API.Gumps.CreateGumpTTFLabel("=== TANK PET ===", 10, "#ff6666", aligned="center", maxWidth=300)
tankSection.SetPos(0, 196)
gump.Add(tankSection)

tankLabel = API.Gumps.CreateGumpTTFLabel("Tank: [None Set]", 11, "#FFAAAA", aligned="center", maxWidth=300)
tankLabel.SetPos(0, 212)
gump.Add(tankLabel)

setTankBtn = API.Gumps.CreateSimpleButton("[SET TANK]", 140, 20)
setTankBtn.SetPos(5, 230)
setTankBtn.SetBackgroundHue(38)
API.Gumps.AddControlOnClick(setTankBtn, set_tank)
gump.Add(setTankBtn)

clearTankBtn = API.Gumps.CreateSimpleButton("[CLEAR TANK]", 140, 20)
clearTankBtn.SetPos(150, 230)
clearTankBtn.SetBackgroundHue(32)
API.Gumps.AddControlOnClick(clearTankBtn, clear_tank)
gump.Add(clearTankBtn)

# Vet Kit section
vetkitSection = API.Gumps.CreateGumpTTFLabel("=== VET KIT ===", 10, "#66ff66", aligned="center", maxWidth=300)
vetkitSection.SetPos(0, 256)
gump.Add(vetkitSection)

vetkitLabel = API.Gumps.CreateGumpTTFLabel("Vet Kit: [Not Set]", 11, "#AAFFAA", aligned="center", maxWidth=300)
vetkitLabel.SetPos(0, 272)
gump.Add(vetkitLabel)

setVetkitBtn = API.Gumps.CreateSimpleButton("[SET VET KIT]", 140, 20)
setVetkitBtn.SetPos(5, 290)
setVetkitBtn.SetBackgroundHue(68)
API.Gumps.AddControlOnClick(setVetkitBtn, set_vetkit)
gump.Add(setVetkitBtn)

clearVetkitBtn = API.Gumps.CreateSimpleButton("[CLEAR]", 140, 20)
clearVetkitBtn.SetPos(150, 290)
clearVetkitBtn.SetBackgroundHue(32)
API.Gumps.AddControlOnClick(clearVetkitBtn, clear_vetkit)
gump.Add(clearVetkitBtn)

# Pet section
petSection = API.Gumps.CreateGumpTTFLabel("=== PETS ===", 10, "#00d4ff", aligned="center", maxWidth=300)
petSection.SetPos(0, 316)
gump.Add(petSection)

petListY = 332
for i in range(MAX_PETS):
    lbl = API.Gumps.CreateGumpTTFLabel(str(i+1) + ". ---", 11, "#CCCCCC", aligned="left", maxWidth=280)
    lbl.SetPos(15, petListY + (i * 16))
    gump.Add(lbl)
    pet_labels.append(lbl)

btnY = petListY + (MAX_PETS * 16) + 5

addBtn = API.Gumps.CreateSimpleButton("[ADD PET]", 90, 22)
addBtn.SetPos(5, btnY)
addBtn.SetBackgroundHue(68)
API.Gumps.AddControlOnClick(addBtn, add_pet)
gump.Add(addBtn)

removeBtn = API.Gumps.CreateSimpleButton("[REMOVE]", 90, 22)
removeBtn.SetPos(100, btnY)
removeBtn.SetBackgroundHue(53)
API.Gumps.AddControlOnClick(removeBtn, remove_pet)
gump.Add(removeBtn)

clearBtn = API.Gumps.CreateSimpleButton("[CLEAR ALL]", 90, 22)
clearBtn.SetPos(195, btnY)
clearBtn.SetBackgroundHue(32)
API.Gumps.AddControlOnClick(clearBtn, clear_all_pets)
gump.Add(clearBtn)

statusLabel = API.Gumps.CreateGumpTTFLabel("Status: Running", 10, "#00ff00", aligned="center", maxWidth=300)
statusLabel.SetPos(0, btnY + 28)
gump.Add(statusLabel)

API.Gumps.AddGump(gump)

# Initial display update
update_pet_display()
update_tank_display()
update_vetkit_display()
update_rez_friend_display()

API.SysMsg("Pet Healer v7.0 loaded!", 68)
API.SysMsg("NEW: [REZ FRIEND] button for player resurrection!", 38)
API.SysMsg("Journal: " + ("ON" if USE_JOURNAL_TRACKING else "OFF") + " | Skip OOR: " + ("ON" if SKIP_OUT_OF_RANGE else "OFF"), 66)

# ============ MAIN LOOP ============
next_save = time.time() + SETTINGS_SAVE_INTERVAL
next_display_update = time.time() + DISPLAY_UPDATE_INTERVAL

while not API.StopRequested:
    try:
        API.ProcessCallbacks()
        
        # Save window position periodically
        if time.time() > next_save:
            lastX = gump.GetX()
            lastY = gump.GetY()
            next_save = time.time() + SETTINGS_SAVE_INTERVAL
        
        # Update displays more frequently for responsive HP tracking
        if time.time() > next_display_update:
            update_pet_display()
            update_tank_display()
            update_vetkit_display()
            if rez_friend_active:
                update_rez_friend_display()
            next_display_update = time.time() + DISPLAY_UPDATE_INTERVAL
        
        # URGENT: Fast-path for self poison - check every loop iteration
        if HEAL_SELF and CURE_POISON and not is_player_dead():
            if is_player_poisoned():
                statusLabel.SetText("URGENT: Curing SELF (poisoned)")
                heal_target(API.Player.Serial, is_self=True)
                statusLabel.SetText("Status: Running")
                API.Pause(0.1)  # Minimal pause after urgent action
                continue  # Skip normal priority check, loop immediately
        
        # URGENT: Fast-path for vet kit - use when multiple pets hurt
        if VET_KIT_ID > 0 and can_use_vetkit():
            hurt_count = count_pets_needing_heal()
            if hurt_count >= VET_KIT_THRESHOLD:
                statusLabel.SetText("Vet Kit (" + str(hurt_count) + " pets)")
                use_vetkit()
                statusLabel.SetText("Status: Running")
                API.Pause(0.2)
                continue  # Loop immediately after vet kit
        
        # Get priority heal action
        action = get_priority_heal_target()
        
        if action.action_type == 'rez_friend':
            # Friend rez takes absolute priority
            statusLabel.SetText(action.status + " #" + str(rez_friend_attempts))
            attempt_friend_rez()
            statusLabel.SetText("Status: Running")
        
        elif action.action_type == 'vetkit':
            if DEBUG:
                API.SysMsg("DEBUG: " + str(action.status), 88)
            statusLabel.SetText(action.status)
            use_vetkit()
            statusLabel.SetText("Status: Running")
            
        elif action.action_type == 'rez':
            if DEBUG:
                API.SysMsg("DEBUG: " + str(action.status), 88)
            statusLabel.SetText(action.status)
            resurrect_pet(action.target)
            statusLabel.SetText("Status: Running")
            
        elif action.action_type == 'heal':
            if DEBUG:
                API.SysMsg("DEBUG: " + str(action.status), 88)
            statusLabel.SetText(action.status)
            heal_target(action.target, is_self=action.is_self)
            statusLabel.SetText("Status: Running")
        
        else:
            # No action needed - clear any stray cursors
            clear_stray_cursor()
        
        API.Pause(0.2)  # Reduced from 0.5s for faster response
        
    except Exception as e:
        if DEBUG:
            API.SysMsg("ERROR: " + str(e), 32)
        else:
            API.SysMsg("Script error - enable DEBUG for details", 32)
        API.Pause(1)  # Prevent rapid error spam