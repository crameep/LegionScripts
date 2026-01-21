# ============================================================
# Pet Healer v7.0 (Experimental)
# by Coryigon for UO Unchained
# ============================================================
#
# EXPERIMENTAL VERSION - Testing new features before merging
# into the stable healer. May have bugs or incomplete features.
#
# Based on Pet Healer v7 with additional experimental features:
#   - Manual healing mode
#   - Enhanced pause/resume controls
#   - Extended debugging options
#
# See Tamer_Healer_v7.py for the stable version.
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
VET_KIT_GRAPHIC = 0           # Vet kit GRAPHIC ID (0 = not set, use [SET VET KIT] button)
VET_KIT_THRESHOLD = 2         # Use vet kit when this many pets need healing (default 2)
VET_KIT_HP_PERCENT = 70       # HP% threshold - pets below this count as "hurt"
VET_KIT_DELAY = 5.0           # Seconds to wait after using vet kit
VET_KIT_COOLDOWN = 10.0       # Minimum seconds between vet kit uses

# === PAUSE / HOTKEY ===
PAUSE_HOTKEY = "PAUSE"        # Hotkey to pause/resume healing (set to "" to disable)

# === SOUND ALERTS ===
USE_SOUND_ALERTS = True       # Play sound alerts for critical events
CRITICAL_HP_PERCENT = 25      # Alert when self HP below this %
SOUND_CRITICAL = 0x1F5        # Sound for critical HP (0x1F5 = alarm)
SOUND_PET_DIED = 0x1F6        # Sound for pet death
SOUND_NO_BANDAGES = 0x1F4     # Sound for out of bandages

# === SHARED PET LIST ===
# Both Pet Healer and Tamer Commands can use this shared list
SHARED_PETS_KEY = "SharedPets_List"  # Format: "name:serial|name:serial|..."
PET_SYNC_INTERVAL = 2.0              # How often to check for pet list changes (seconds)
# =========================================

# Named tuple for cleaner heal action returns
HealAction = namedtuple('HealAction', ['target', 'is_self', 'status', 'action_type'])
# action_type: 'none', 'heal', 'rez', 'vetkit', 'rez_friend'

# Persistent storage keys
SETTINGS_KEY = "PetHealer_XY"
MAGERY_KEY = "PetHealer_UseMagery"
REZ_KEY = "PetHealer_UseRez"
FOLLOW_KEY = "PetHealer_Follow"
TANK_KEY = "PetHealer_Tank"
HEALSELF_KEY = "PetHealer_HealSelf"
VETKIT_KEY = "PetHealer_VetKitGraphic"  # Changed: stores GRAPHIC not serial
JOURNAL_KEY = "PetHealer_UseJournal"
SKIPOOR_KEY = "PetHealer_SkipOOR"

# Runtime state
USE_MAGERY = False
USE_REZ = False
HEAL_SELF = True
PETS = []
PET_NAMES = {}                        # Map serial -> name for shared list
TANK_PET = 0
pet_labels = []
last_vetkit_use = 0                   # Timestamp of last vet kit use
last_no_bandage_warning = 0           # Timestamp of last "no bandages" warning
NO_BANDAGE_COOLDOWN = 10.0            # Seconds to wait before warning again about no bandages
VET_KIT_GRAPHIC = 0                   # Vet kit GRAPHIC ID (not serial!)

# Manual heal override - click a pet to heal it immediately
manual_heal_target = 0                # Serial of pet to heal next (0 = none)

# Pause state
PAUSED = False

# Sound alert cooldowns
last_critical_alert = 0
last_pet_death_alerts = {}            # serial -> timestamp
ALERT_COOLDOWN = 5.0                  # Seconds between same alert

# Auto-sync tracking
last_known_pets_str = ""              # Track last known pet string for sync detection

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
        play_sound_alert(SOUND_NO_BANDAGES)
        return False
    
    # Try to get count if API supports it
    try:
        count = API.Found.Amount if hasattr(API.Found, 'Amount') else -1
        if count > 0 and count <= LOW_BANDAGE_WARNING:
            API.SysMsg("Low bandages: " + str(count) + " remaining", 53)
    except:
        pass
    
    return True

def get_bandage_count():
    """Get current bandage count, returns -1 if unknown, 0 if none"""
    try:
        if API.FindType(BANDAGE):
            if hasattr(API.Found, 'Amount'):
                return API.Found.Amount
            return -1  # Found but can't count
        return 0  # None found
    except:
        return -1

def play_sound_alert(sound_id):
    """Play a sound alert if enabled"""
    if not USE_SOUND_ALERTS:
        return
    try:
        if hasattr(API, 'PlaySound'):
            API.PlaySound(sound_id)
    except:
        pass  # Sound not supported

def check_critical_alerts():
    """Check for critical situations and play alerts"""
    global last_critical_alert, last_pet_death_alerts
    
    now = time.time()
    
    # Check self HP critical
    if HEAL_SELF and not is_player_dead():
        try:
            player = API.Player
            hp_pct = int((player.Hits / player.HitsMax) * 100) if player.HitsMax > 0 else 100
            if hp_pct < CRITICAL_HP_PERCENT and now - last_critical_alert > ALERT_COOLDOWN:
                last_critical_alert = now
                play_sound_alert(SOUND_CRITICAL)
                API.HeadMsg("CRITICAL!", player.Serial, 32)
        except:
            pass
    
    # Check for newly dead pets
    for pet in PETS:
        mob = API.FindMobile(pet)
        if mob and mob.IsDead:
            last_alert = last_pet_death_alerts.get(pet, 0)
            if now - last_alert > ALERT_COOLDOWN:
                last_pet_death_alerts[pet] = now
                play_sound_alert(SOUND_PET_DIED)
                API.SysMsg("PET DIED: " + get_mob_name(mob), 32)

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
    """Quick check and clear of any stray target cursor or pre-target"""
    try:
        # Cancel any pre-target
        API.CancelPreTarget()
    except:
        pass
    try:
        # Cancel any active target cursor
        if API.HasTarget():
            API.CancelTarget()
            if DEBUG:
                API.SysMsg("DEBUG: Cleared stray cursor", 43)
            return True
    except:
        pass
    return False

# ============ PERSISTENCE ============
def load_settings():
    global USE_MAGERY, USE_REZ, FOLLOW_PET, PETS, PET_NAMES, TANK_PET, HEAL_SELF, VET_KIT_GRAPHIC, USE_JOURNAL_TRACKING, SKIP_OUT_OF_RANGE, last_known_pets_str
    
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
        VET_KIT_GRAPHIC = int(vetkit_str)
    except:
        VET_KIT_GRAPHIC = 0
    
    # Load SHARED pet list (format: "name:serial:active|name:serial:active|...")
    PETS = []
    PET_NAMES = {}
    pets_str = API.GetPersistentVar(SHARED_PETS_KEY, "", API.PersistentVar.Char)
    last_known_pets_str = pets_str  # Track for auto-sync
    if pets_str:
        for part in pets_str.split("|"):
            if not part:
                continue
            try:
                pieces = part.split(":")
                if len(pieces) >= 2:
                    name = pieces[0]
                    serial = int(pieces[1])
                    PETS.append(serial)
                    PET_NAMES[serial] = name
            except:
                pass

def save_pets():
    """Save pets in SHARED format: name:serial:active|..."""
    global last_known_pets_str
    parts = []
    for serial in PETS:
        # Get name from cache or look up
        if serial in PET_NAMES:
            name = PET_NAMES[serial]
        else:
            mob = API.FindMobile(serial)
            name = get_mob_name(mob) if mob else "Unknown"
            PET_NAMES[serial] = name
        # Escape special chars
        safe_name = name.replace("|", "_").replace(":", "_")
        parts.append(safe_name + ":" + str(serial) + ":1")  # :1 = active for TamerCommands
    
    pets_str = "|".join(parts)
    last_known_pets_str = pets_str  # Track what we saved
    API.SavePersistentVar(SHARED_PETS_KEY, pets_str, API.PersistentVar.Char)

def sync_pets_from_storage():
    """Check if pet list changed externally and reload if needed"""
    global PETS, PET_NAMES, last_known_pets_str
    
    current_str = API.GetPersistentVar(SHARED_PETS_KEY, "", API.PersistentVar.Char)
    
    # If unchanged, nothing to do
    if current_str == last_known_pets_str:
        return False
    
    # Pet list changed externally! Reload it
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
                    name = pieces[0]
                    serial = int(pieces[1])
                    PETS.append(serial)
                    PET_NAMES[serial] = name
            except:
                pass
    
    last_known_pets_str = current_str
    
    # Notify user if list changed
    new_count = len(PETS)
    if old_count != new_count:
        API.SysMsg("Pet list synced: " + str(new_count) + " pets", 66)
        update_pet_display()
    
    return True

def save_tank():
    API.SavePersistentVar(TANK_KEY, str(TANK_PET), API.PersistentVar.Char)

def save_vetkit():
    API.SavePersistentVar(VETKIT_KEY, str(VET_KIT_GRAPHIC), API.PersistentVar.Char)

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
    
    # PreTarget then cast - don't cancel user's targets
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
        
        # Range pre-check for non-self targets (before we do anything)
        if not USE_MAGERY:  # Bandage range check
            distance = get_distance(mob)
            if distance > BANDAGE_RANGE:
                if SKIP_OUT_OF_RANGE or not FOLLOW_PET:
                    if DEBUG:
                        API.SysMsg("DEBUG: " + name + " out of range (" + str(distance) + "), skipping", 43)
                    return False
        
        if DEBUG:
            API.SysMsg("DEBUG: Healing " + name, 88)
    
    # Don't cancel user's targets - just show head message
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
    """Update the rez friend button"""
    if rez_friend_active:
        rezFriendBtn.SetText("[CANC]")
        rezFriendBtn.SetBackgroundHue(32)
    else:
        rezFriendBtn.SetText("[FREZ]")
        rezFriendBtn.SetBackgroundHue(38)

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
    
    if VET_KIT_GRAPHIC == 0:
        return False
    
    # Check cooldown
    if time.time() - last_vetkit_use < VET_KIT_COOLDOWN:
        if DEBUG:
            remaining = round(VET_KIT_COOLDOWN - (time.time() - last_vetkit_use), 1)
            API.SysMsg("DEBUG: Vet kit on cooldown (" + str(remaining) + "s)", 53)
        return False
    
    # Check if we have one
    if not API.FindType(VET_KIT_GRAPHIC):
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
    global VET_KIT_GRAPHIC
    
    API.SysMsg("Target your VET KIT item...", 68)
    cancel_all_targets()
    
    target = API.RequestTarget(timeout=10)
    
    if target:
        item = API.FindItem(target)
        if item:
            VET_KIT_GRAPHIC = item.Graphic
            save_vetkit()
            update_vetkit_display()
            API.SysMsg("Vet Kit set! ID: " + str(VET_KIT_GRAPHIC), 68)
        else:
            API.SysMsg("Not a valid item!", 32)
    else:
        API.SysMsg("Targeting cancelled", 32)

def clear_vetkit():
    global VET_KIT_GRAPHIC
    VET_KIT_GRAPHIC = 0
    save_vetkit()
    update_vetkit_display()
    API.SysMsg("Vet Kit cleared", 68)

def add_pet():
    global PETS, PET_NAMES
    
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
                name = get_mob_name(mob)
                PETS.append(target)
                PET_NAMES[target] = name
                save_pets()
                update_pet_display()
                API.SysMsg("Added: " + name, 68)
        else:
            API.SysMsg("Not a valid mobile!", 32)
    else:
        API.SysMsg("Targeting cancelled", 32)

def remove_pet():
    global PETS, PET_NAMES, TANK_PET
    
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
            if target in PET_NAMES:
                del PET_NAMES[target]
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
            save_tank()
            update_pet_display()
            API.SysMsg("Tank set: " + name, 38)
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
    global PETS, PET_NAMES, TANK_PET
    PETS = []
    PET_NAMES = {}
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
    if VET_KIT_GRAPHIC > 0 and can_use_vetkit():
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

# ============ MANUAL HEAL CLICK HANDLERS ============
def make_pet_click_callback(index):
    """Create a callback for clicking on a pet button"""
    def callback():
        global manual_heal_target
        if index < len(PETS):
            pet_serial = PETS[index]
            mob = API.FindMobile(pet_serial)
            if mob:
                name = get_mob_name(mob)
                if mob.IsDead:
                    if USE_REZ:
                        manual_heal_target = pet_serial
                        API.SysMsg("Manual REZ queued: " + name, 38)
                        API.HeadMsg("REZ QUEUED!", pet_serial, 38)
                    else:
                        API.SysMsg("Rez is disabled!", 32)
                else:
                    manual_heal_target = pet_serial
                    API.SysMsg("Manual HEAL queued: " + name, 68)
                    API.HeadMsg("HEAL QUEUED!", pet_serial, 68)
            else:
                API.SysMsg("Pet not found!", 32)
    return callback

def process_manual_heal():
    """Process manual heal if one is queued. Returns True if handled."""
    global manual_heal_target
    
    if manual_heal_target == 0:
        return False
    
    target = manual_heal_target
    manual_heal_target = 0  # Clear immediately
    
    mob = API.FindMobile(target)
    if not mob:
        API.SysMsg("Manual heal target lost!", 32)
        return True
    
    name = get_mob_name(mob)
    
    if mob.IsDead:
        if USE_REZ:
            statusLabel.SetText("Manual REZ: " + name)
            API.SysMsg("Manual rezzing: " + name, 38)
            resurrect_pet(target)
            statusLabel.SetText("Status: Running")
        else:
            API.SysMsg("Cannot rez - rez disabled", 32)
    else:
        statusLabel.SetText("Manual HEAL: " + name)
        API.SysMsg("Manual healing: " + name, 68)
        heal_target(target, is_self=False)
        statusLabel.SetText("Status: Running")
    
    return True

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
    followBtn.SetText("[FLLW:" + ("ON" if FOLLOW_PET else "OFF") + "]")
    followBtn.SetBackgroundHue(68 if FOLLOW_PET else 90)

def toggle_rez():
    global USE_REZ
    USE_REZ = not USE_REZ
    API.SavePersistentVar(REZ_KEY, "True" if USE_REZ else "False", API.PersistentVar.Char)
    rezBtn.SetText("[REZ:" + ("ON" if USE_REZ else "OFF") + "]")
    rezBtn.SetBackgroundHue(38 if USE_REZ else 90)

def toggle_heal_self():
    global HEAL_SELF
    HEAL_SELF = not HEAL_SELF
    API.SavePersistentVar(HEALSELF_KEY, "True" if HEAL_SELF else "False", API.PersistentVar.Char)
    selfBtn.SetText("[SELF:" + ("ON" if HEAL_SELF else "OFF") + "]")
    selfBtn.SetBackgroundHue(68 if HEAL_SELF else 90)

def toggle_journal():
    global USE_JOURNAL_TRACKING
    USE_JOURNAL_TRACKING = not USE_JOURNAL_TRACKING
    save_journal_setting()
    journalBtn.SetText("[JRNL:" + ("ON" if USE_JOURNAL_TRACKING else "OFF") + "]")
    journalBtn.SetBackgroundHue(66 if USE_JOURNAL_TRACKING else 90)
    mode = "Journal tracking" if USE_JOURNAL_TRACKING else "Fixed timers"
    API.SysMsg("Bandage timing: " + mode, 66)

def toggle_skipoor():
    global SKIP_OUT_OF_RANGE
    SKIP_OUT_OF_RANGE = not SKIP_OUT_OF_RANGE
    save_skipoor_setting()
    skipoorBtn.SetText("[SKIP:" + ("ON" if SKIP_OUT_OF_RANGE else "OFF") + "]")
    skipoorBtn.SetBackgroundHue(53 if SKIP_OUT_OF_RANGE else 90)
    API.SysMsg("Skip OOR: " + ("ON" if SKIP_OUT_OF_RANGE else "OFF"), 53)

def toggle_pause():
    """Toggle pause/resume healing"""
    global PAUSED
    PAUSED = not PAUSED
    if PAUSED:
        pauseBtn.SetText("[PAUSED]")
        pauseBtn.SetBackgroundHue(32)
        statusLabel.SetText("*** PAUSED ***")
        API.SysMsg("Pet Healer PAUSED - press " + PAUSE_HOTKEY + " to resume", 43)
    else:
        pauseBtn.SetText("[PAUSE]")
        pauseBtn.SetBackgroundHue(90)
        statusLabel.SetText("Status: Running")
        API.SysMsg("Pet Healer RESUMED", 68)

def cleanup():
    """Cleanup when script closes"""
    if PAUSE_HOTKEY:
        try:
            API.OnHotKey(PAUSE_HOTKEY)  # Unregister hotkey
        except:
            pass

def onClosed():
    cleanup()
    cancel_all_targets()
    cancel_friend_rez()
    API.SavePersistentVar(SETTINGS_KEY, str(gump.GetX()) + "," + str(gump.GetY()), API.PersistentVar.Char)
    API.Stop()

# ============ DISPLAY UPDATES ============
def get_health_bar(hp_pct, width=10):
    """Create a text-based health bar using ASCII"""
    filled = int((hp_pct / 100) * width)
    empty = width - filled
    return "|" * filled + "." * empty

def update_bandage_display():
    """Update bandage count display"""
    count = get_bandage_count()
    if count == 0:
        bandageLabel.SetText("Bandages: NONE!")
    elif count < 0:
        bandageLabel.SetText("Bandages: ???")
    elif count <= LOW_BANDAGE_WARNING:
        bandageLabel.SetText("Bandages: " + str(count) + " LOW!")
    else:
        bandageLabel.SetText("Bandages: " + str(count))

def update_pet_display():
    for i, btn in enumerate(pet_labels):
        if i < len(PETS):
            mob = API.FindMobile(PETS[i])
            if mob:
                name = get_mob_name(mob)[:8]
                tank_marker = "T" if PETS[i] == TANK_PET else ""
                distance = get_distance(mob)
                
                # Range indicator
                if USE_MAGERY:
                    in_range = distance <= SPELL_RANGE
                else:
                    in_range = distance <= BANDAGE_RANGE
                
                if mob.IsDead:
                    btn.SetText(str(i+1) + tank_marker + ". " + name + " [DEAD]")
                    btn.SetBackgroundHue(32)
                else:
                    hp_pct = get_hp_percent(mob)
                    poison_marker = "[P]" if is_poisoned(mob) else ""
                    bar = get_health_bar(hp_pct)
                    range_marker = " >" + str(distance) if not in_range else ""
                    btn.SetText(str(i+1) + tank_marker + ". " + name + " " + bar + poison_marker + range_marker)
                    
                    # Color based on health
                    if is_poisoned(mob):
                        btn.SetBackgroundHue(53)  # Purple-ish for poison
                    elif hp_pct < 50:
                        btn.SetBackgroundHue(32)  # Red for low
                    elif hp_pct < 80:
                        btn.SetBackgroundHue(43)  # Yellow for medium
                    else:
                        btn.SetBackgroundHue(68)  # Green for good
            else:
                btn.SetText(str(i+1) + ". [Not Found]")
                btn.SetBackgroundHue(90)
        else:
            btn.SetText(str(i+1) + ". ---")
            btn.SetBackgroundHue(90)

def update_tank_display():
    if TANK_PET:
        mob = API.FindMobile(TANK_PET)
        if mob:
            hp_pct = get_hp_percent(mob)
            distance = get_distance(mob)
            poison_marker = "[P]" if is_poisoned(mob) else ""
            
            # Range check
            if USE_MAGERY:
                in_range = distance <= SPELL_RANGE
            else:
                in_range = distance <= BANDAGE_RANGE
            range_marker = "" if in_range else ">" + str(distance)
            
            if mob.IsDead:
                tankLabel.SetText("Tank: " + get_mob_name(mob)[:7] + " [DEAD]")
            else:
                bar = get_health_bar(hp_pct)
                tankLabel.SetText("Tank: " + get_mob_name(mob)[:7] + " " + bar + poison_marker + range_marker)
        else:
            tankLabel.SetText("Tank: [Not Found]")
    else:
        tankLabel.SetText("Tank: [None Set]")

def update_vetkit_display():
    if VET_KIT_GRAPHIC > 0:
        if API.FindType(VET_KIT_GRAPHIC):
            vetkitLabel.SetText("Vet: Ready")
        else:
            vetkitLabel.SetText("Vet: Empty!")
    else:
        vetkitLabel.SetText("Vet: [Not Set]")

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
gump.SetRect(lastX, lastY, 200, 380)  # Taller for new elements

bg = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
bg.SetRect(0, 0, 200, 380)
gump.Add(bg)

title = API.Gumps.CreateGumpTTFLabel("Pet Healer v7", 16, "#00d4ff", aligned="center", maxWidth=200)
title.SetPos(0, 5)
gump.Add(title)

# Bandage count label (top right area)
bandageLabel = API.Gumps.CreateGumpTTFLabel("Bandages: ???", 9, "#AAFFAA", aligned="center", maxWidth=200)
bandageLabel.SetPos(0, 22)
gump.Add(bandageLabel)

# Layout constants
col1X = 5
col2X = 100
buttonWidth = 90
buttonHeight = 22
smallBtnW = 45
smallBtnH = 20

# === TOGGLES SECTION ===
y = 38
toggleLabel = API.Gumps.CreateGumpTTFLabel("=== TOGGLES ===", 9, "#ff8800", aligned="center", maxWidth=200)
toggleLabel.SetPos(0, y)
gump.Add(toggleLabel)

y += 16
mageryBtn = API.Gumps.CreateSimpleButton("[BAND]" if not USE_MAGERY else "[MAGE]", buttonWidth, buttonHeight)
mageryBtn.SetPos(col1X, y)
mageryBtn.SetBackgroundHue(68 if not USE_MAGERY else 66)
def toggle_method():
    global USE_MAGERY
    USE_MAGERY = not USE_MAGERY
    API.SavePersistentVar(MAGERY_KEY, "True" if USE_MAGERY else "False", API.PersistentVar.Char)
    mageryBtn.SetText("[MAGE]" if USE_MAGERY else "[BAND]")
    mageryBtn.SetBackgroundHue(66 if USE_MAGERY else 68)
API.Gumps.AddControlOnClick(mageryBtn, toggle_method)
gump.Add(mageryBtn)

selfBtn = API.Gumps.CreateSimpleButton("[SELF:" + ("ON" if HEAL_SELF else "OFF") + "]", buttonWidth, buttonHeight)
selfBtn.SetPos(col2X, y)
selfBtn.SetBackgroundHue(68 if HEAL_SELF else 90)
API.Gumps.AddControlOnClick(selfBtn, toggle_heal_self)
gump.Add(selfBtn)

y += 24
followBtn = API.Gumps.CreateSimpleButton("[FLLW:" + ("ON" if FOLLOW_PET else "OFF") + "]", buttonWidth, buttonHeight)
followBtn.SetPos(col1X, y)
followBtn.SetBackgroundHue(68 if FOLLOW_PET else 90)
API.Gumps.AddControlOnClick(followBtn, toggle_follow)
gump.Add(followBtn)

rezBtn = API.Gumps.CreateSimpleButton("[REZ:" + ("ON" if USE_REZ else "OFF") + "]", buttonWidth, buttonHeight)
rezBtn.SetPos(col2X, y)
rezBtn.SetBackgroundHue(38 if USE_REZ else 90)
API.Gumps.AddControlOnClick(rezBtn, toggle_rez)
gump.Add(rezBtn)

y += 24
journalBtn = API.Gumps.CreateSimpleButton("[JRNL:" + ("ON" if USE_JOURNAL_TRACKING else "OFF") + "]", buttonWidth, buttonHeight)
journalBtn.SetPos(col1X, y)
journalBtn.SetBackgroundHue(66 if USE_JOURNAL_TRACKING else 90)
API.Gumps.AddControlOnClick(journalBtn, toggle_journal)
gump.Add(journalBtn)

skipoorBtn = API.Gumps.CreateSimpleButton("[SKIP:" + ("ON" if SKIP_OUT_OF_RANGE else "OFF") + "]", buttonWidth, buttonHeight)
skipoorBtn.SetPos(col2X, y)
skipoorBtn.SetBackgroundHue(53 if SKIP_OUT_OF_RANGE else 90)
API.Gumps.AddControlOnClick(skipoorBtn, toggle_skipoor)
gump.Add(skipoorBtn)

# === TANK & VET SECTION ===
y += 28
tankLabel = API.Gumps.CreateGumpTTFLabel("=== TANK & VET ===", 9, "#ff6666", aligned="center", maxWidth=200)
tankLabel.SetPos(0, y)
gump.Add(tankLabel)

y += 16
tankDisplayLabel = API.Gumps.CreateGumpTTFLabel("Tank: [None Set]", 10, "#FFAAAA", aligned="center", maxWidth=200)
tankDisplayLabel.SetPos(0, y)
gump.Add(tankDisplayLabel)
tankLabel = tankDisplayLabel  # Rename for update function

y += 16
setTankBtn = API.Gumps.CreateSimpleButton("[SET TANK]", buttonWidth, smallBtnH)
setTankBtn.SetPos(col1X, y)
setTankBtn.SetBackgroundHue(38)
API.Gumps.AddControlOnClick(setTankBtn, set_tank)
gump.Add(setTankBtn)

clearTankBtn = API.Gumps.CreateSimpleButton("[CLR TANK]", buttonWidth, smallBtnH)
clearTankBtn.SetPos(col2X, y)
clearTankBtn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(clearTankBtn, clear_tank)
gump.Add(clearTankBtn)

y += 22
vetkitLabel = API.Gumps.CreateGumpTTFLabel("Vet Kit: [Not Set]", 10, "#AAFFAA", aligned="center", maxWidth=200)
vetkitLabel.SetPos(0, y)
gump.Add(vetkitLabel)

y += 16
setVetkitBtn = API.Gumps.CreateSimpleButton("[SET VET]", buttonWidth, smallBtnH)
setVetkitBtn.SetPos(col1X, y)
setVetkitBtn.SetBackgroundHue(68)
API.Gumps.AddControlOnClick(setVetkitBtn, set_vetkit)
gump.Add(setVetkitBtn)

clearVetkitBtn = API.Gumps.CreateSimpleButton("[CLR VET]", buttonWidth, smallBtnH)
clearVetkitBtn.SetPos(col2X, y)
clearVetkitBtn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(clearVetkitBtn, clear_vetkit)
gump.Add(clearVetkitBtn)

# === PETS SECTION ===
y += 26
petHeader = API.Gumps.CreateGumpTTFLabel("=== PETS ===", 9, "#00d4ff", aligned="center", maxWidth=200)
petHeader.SetPos(0, y)
gump.Add(petHeader)

y += 16
for i in range(MAX_PETS):
    lbl = API.Gumps.CreateSimpleButton(str(i+1) + ". ---", 190, 18)
    lbl.SetPos(col1X, y + (i * 20))
    lbl.SetBackgroundHue(90)
    API.Gumps.AddControlOnClick(lbl, make_pet_click_callback(i))  # Click to heal!
    gump.Add(lbl)
    pet_labels.append(lbl)

y += (MAX_PETS * 20) + 4

# Pet management buttons
addBtn = API.Gumps.CreateSimpleButton("[ADD]", smallBtnW, smallBtnH)
addBtn.SetPos(col1X, y)
addBtn.SetBackgroundHue(68)
API.Gumps.AddControlOnClick(addBtn, add_pet)
gump.Add(addBtn)

removeBtn = API.Gumps.CreateSimpleButton("[DEL]", smallBtnW, smallBtnH)
removeBtn.SetPos(55, y)
removeBtn.SetBackgroundHue(32)
API.Gumps.AddControlOnClick(removeBtn, remove_pet)
gump.Add(removeBtn)

clearBtn = API.Gumps.CreateSimpleButton("[CLR]", smallBtnW, smallBtnH)
clearBtn.SetPos(105, y)
clearBtn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(clearBtn, clear_all_pets)
gump.Add(clearBtn)

rezFriendBtn = API.Gumps.CreateSimpleButton("[FREZ]", smallBtnW, smallBtnH)
rezFriendBtn.SetPos(155, y)
rezFriendBtn.SetBackgroundHue(38)
API.Gumps.AddControlOnClick(rezFriendBtn, toggle_rez_friend)
gump.Add(rezFriendBtn)

# === STATUS ===
y += 26
pauseBtn = API.Gumps.CreateSimpleButton("[PAUSE]", 60, smallBtnH)
pauseBtn.SetPos(col1X, y)
pauseBtn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(pauseBtn, toggle_pause)
gump.Add(pauseBtn)

statusLabel = API.Gumps.CreateGumpTTFLabel("Running", 10, "#00ff00")
statusLabel.SetPos(70, y + 3)
gump.Add(statusLabel)

API.Gumps.AddGump(gump)

# Register pause hotkey
if PAUSE_HOTKEY:
    API.OnHotKey(PAUSE_HOTKEY, toggle_pause)

# Initial display update
update_pet_display()
update_tank_display()
update_vetkit_display()
update_rez_friend_display()
update_bandage_display()

API.SysMsg("Pet Healer v7 loaded!", 68)
API.SysMsg("Hotkey: " + PAUSE_HOTKEY + " to pause/resume", 66)

# ============ MAIN LOOP ============
next_save = time.time() + SETTINGS_SAVE_INTERVAL
next_display_update = time.time() + DISPLAY_UPDATE_INTERVAL
next_pet_sync = time.time() + PET_SYNC_INTERVAL

while not API.StopRequested:
    try:
        API.ProcessCallbacks()
        
        # Save window position periodically
        if time.time() > next_save:
            lastX = gump.GetX()
            lastY = gump.GetY()
            next_save = time.time() + SETTINGS_SAVE_INTERVAL
        
        # Auto-sync pet list from storage (check if changed by other script)
        if time.time() > next_pet_sync:
            sync_pets_from_storage()
            next_pet_sync = time.time() + PET_SYNC_INTERVAL
        
        # Update displays more frequently for responsive HP tracking
        if time.time() > next_display_update:
            update_pet_display()
            update_tank_display()
            update_vetkit_display()
            update_bandage_display()
            if rez_friend_active:
                update_rez_friend_display()
            next_display_update = time.time() + DISPLAY_UPDATE_INTERVAL
        
        # Check for critical alerts (even when paused)
        check_critical_alerts()
        
        # Skip healing if paused (but still update displays)
        if PAUSED:
            API.Pause(0.2)
            continue
        
        # URGENT: Fast-path for self poison - check every loop iteration
        if HEAL_SELF and CURE_POISON and not is_player_dead():
            if is_player_poisoned():
                statusLabel.SetText("URGENT: Curing SELF (poisoned)")
                heal_target(API.Player.Serial, is_self=True)
                clear_stray_cursor()  # Cleanup after action
                statusLabel.SetText("Status: Running")
                API.Pause(0.1)  # Minimal pause after urgent action
                continue  # Skip normal priority check, loop immediately
        
        # MANUAL HEAL: Check if user clicked a pet to heal (after self-heal)
        if manual_heal_target != 0:
            process_manual_heal()
            clear_stray_cursor()
            API.Pause(0.2)
            continue  # Loop immediately after manual heal
        
        # URGENT: Fast-path for vet kit - use when multiple pets hurt
        if VET_KIT_GRAPHIC > 0 and can_use_vetkit():
            hurt_count = count_pets_needing_heal()
            if hurt_count >= VET_KIT_THRESHOLD:
                statusLabel.SetText("Vet Kit (" + str(hurt_count) + " pets)")
                use_vetkit()
                clear_stray_cursor()  # Cleanup after action
                statusLabel.SetText("Status: Running")
                API.Pause(0.2)
                continue  # Loop immediately after vet kit
        
        # Get priority heal action
        action = get_priority_heal_target()
        
        if action.action_type == 'rez_friend':
            # Friend rez takes absolute priority
            statusLabel.SetText(action.status + " #" + str(rez_friend_attempts))
            attempt_friend_rez()
            clear_stray_cursor()  # Cleanup after action
            statusLabel.SetText("Status: Running")
        
        elif action.action_type == 'vetkit':
            if DEBUG:
                API.SysMsg("DEBUG: " + str(action.status), 88)
            statusLabel.SetText(action.status)
            use_vetkit()
            clear_stray_cursor()  # Cleanup after action
            statusLabel.SetText("Status: Running")
            
        elif action.action_type == 'rez':
            if DEBUG:
                API.SysMsg("DEBUG: " + str(action.status), 88)
            statusLabel.SetText(action.status)
            resurrect_pet(action.target)
            clear_stray_cursor()  # Cleanup after action
            statusLabel.SetText("Status: Running")
            
        elif action.action_type == 'heal':
            if DEBUG:
                API.SysMsg("DEBUG: " + str(action.status), 88)
            statusLabel.SetText(action.status)
            heal_target(action.target, is_self=action.is_self)
            clear_stray_cursor()  # Cleanup after action
            statusLabel.SetText("Status: Running")
        
        else:
            # No action needed
            pass
        
        API.Pause(0.2)  # Reduced from 0.5s for faster response
        
    except Exception as e:
        if DEBUG:
            API.SysMsg("ERROR: " + str(e), 32)
        else:
            API.SysMsg("Script error - enable DEBUG for details", 32)
        API.Pause(1)  # Prevent rapid error spam