# ============================================================
# Dexer Suite v1.6
# by Coryigon for UO Unchained
# ============================================================
#
# All-in-one dexer automation. Manages HP/stamina/poison with
# potions and bandages using a non-blocking design - hotkeys
# stay responsive even during bandage timers.
#
# Features:
#   - Smart priority healing (critical > poison > HP > stamina)
#   - Potion cooldown tracking (10s server cooldown)
#   - TAB to attack nearest hostile
#   - Hotkeys configured in code constants (F1-F3, F6, PAUSE, TAB)
#   - Resource tracking (potions, bandages, HP, stamina)
#   - Modern GUI with status bars and cooldown timers
#   - Collapsible interface to save screen space
#   - Default thresholds: Bandage <100% HP, Potions <50% HP
#
# NO CHIVALRY - designed for UOR-based server
#
# ============================================================

import API
import time
from LegionUtils import *

__version__ = "1.6"

# ============ USER SETTINGS ============
DEBUG = False

# === TIMING (server-enforced) ===
BANDAGE_DELAY = 4.5           # Approximate, DEX-based
POTION_COOLDOWN = 10.0        # Server-enforced potion cooldown
BUFF_DURATION = 120.0         # Stat buff duration (2 minutes exactly)
BUFF_REFRESH_WINDOW = 15.0    # Start rebuffing 15s before expiration (allows cooldown buffer)
GREATER_BUFF_AMOUNT = 20      # Greater potions give +20 to stat
DISPLAY_UPDATE_INTERVAL = 0.3
MAX_DISTANCE = 12             # Max distance for target search

# === GUI DIMENSIONS ===
COLLAPSED_HEIGHT = 24
EXPANDED_HEIGHT = 610
WINDOW_WIDTH = 280

AUTO_TARGET_RANGE = 3         # Range for auto-targeting next enemy when current dies
TARGET_TIMEOUT = 2.0          # Timeout for target cursor

# === POTION GRAPHICS ===
POTION_HEAL = 0x0F0C          # Greater Heal (orange)
POTION_CURE = 0x0F07          # Greater Cure (yellow)
POTION_REFRESH = 0x0F0B       # Greater Refresh (red)
POTION_STRENGTH = 0x0F09      # Greater Strength (white)
POTION_AGILITY = 0x0F08       # Greater Agility (blue)
POTION_EXPLOSION_LESSER = 0x0F0A    # Lesser Explosion (5-10 damage)
POTION_EXPLOSION = 0x0F0D           # Explosion (10-20 damage)
POTION_EXPLOSION_GREATER = 0x0F0E   # Greater Explosion (15-30 damage)
BANDAGE = 0x0E21              # Bandages

# Throwable defaults (can be overridden in config)
DEFAULT_THROWABLES = {
    "lesser_explosion": {"graphic": 0x0F0A, "label": "Lesser Explosion"},
    "explosion": {"graphic": 0x0F0D, "label": "Explosion"},
    "greater_explosion": {"graphic": 0x0F0E, "label": "Greater Explosion"},
    "confusion_blast": {"graphic": 0x0000, "label": "Confusion Blast"},
    "custom1": {"graphic": 0x0000, "label": "Custom 1"},
    "custom2": {"graphic": 0x0000, "label": "Custom 2"}
}

# === TRAPPED POUCH ===
TRAPPED_POUCH_MIN_HP = 30     # Minimum HP to safely use trapped pouch (10-20 damage)

# === DEFAULT THRESHOLDS ===
DEFAULT_HEAL_THRESHOLD = 50    # Potion at 50% HP
DEFAULT_CRITICAL_THRESHOLD = 30
DEFAULT_STAMINA_THRESHOLD = 30
DEFAULT_BANDAGE_DIFF = 1       # Bandage at any HP loss (<100%)

# ============ PERSISTENCE KEYS ============
SETTINGS_KEY = "DexerSuite_XY"
HEAL_THRESHOLD_KEY = "DexerSuite_HealThreshold"
CRITICAL_THRESHOLD_KEY = "DexerSuite_CriticalThreshold"
STAMINA_THRESHOLD_KEY = "DexerSuite_StaminaThreshold"
BANDAGE_DIFF_KEY = "DexerSuite_BandageDiff"
AUTO_HEAL_KEY = "DexerSuite_AutoHeal"
AUTO_BUFF_KEY = "DexerSuite_AutoBuff"
AUTO_TARGET_KEY = "DexerSuite_AutoTarget"
AUTO_EXPLO_KEY = "DexerSuite_AutoExplo"
TARGET_REDS_KEY = "DexerSuite_TargetReds"
TARGET_GRAYS_KEY = "DexerSuite_TargetGrays"
BASE_STR_KEY = "DexerSuite_BaseStr"
BASE_DEX_KEY = "DexerSuite_BaseDex"
TRAPPED_POUCH_SERIAL_KEY = "DexerSuite_TrappedPouch"
USE_TRAPPED_POUCH_KEY = "DexerSuite_UseTrappedPouch"
EXPANDED_KEY = "DexerSuite_Expanded"
THROWABLES_KEY = "DexerSuite_Throwables"
THROWABLE_PRIORITY_KEY = "DexerSuite_ThrowablePriority"
CONFIG_XY_KEY = "DexerSuite_ConfigXY"

# Schema versioning for throwables persistence
THROWABLES_SCHEMA_VERSION = 1

# Hotkey keys
HOTKEY_HEAL_POTION_KEY = "DexerSuite_HK_HealPotion"
HOTKEY_CURE_POTION_KEY = "DexerSuite_HK_CurePotion"
HOTKEY_REFRESH_POTION_KEY = "DexerSuite_HK_RefreshPotion"
HOTKEY_BANDAGE_KEY = "DexerSuite_HK_Bandage"
HOTKEY_EXPLO_POTION_KEY = "DexerSuite_HK_ExploPotion"
HOTKEY_PAUSE_KEY = "DexerSuite_HK_Pause"
HOTKEY_ATTACK_KEY = "DexerSuite_HK_Attack"

# ============ RUNTIME STATE ============
# State machine
HEAL_STATE = "idle"           # "idle" or "healing"
heal_start_time = 0
potion_cooldown_end = 0

# Buff tracking
str_buff_end = 0              # Timestamp when STR buff expires
agi_buff_end = 0              # Timestamp when AGI buff expires
last_buff_was_str = False     # Alternate between STR and AGI to maintain both
last_str_drink_time = 0       # When we last drank STR (grace period for stats)
last_agi_drink_time = 0       # When we last drank AGI (grace period for stats)
BUFF_GRACE_PERIOD = 5.0       # Seconds to wait before checking stats after drinking

# Settings
heal_threshold = DEFAULT_HEAL_THRESHOLD
critical_threshold = DEFAULT_CRITICAL_THRESHOLD
stamina_threshold = DEFAULT_STAMINA_THRESHOLD
bandage_diff_threshold = DEFAULT_BANDAGE_DIFF
auto_heal = True
auto_buff = True              # Auto-maintain STR/AGI buffs
auto_target = False           # Continuous auto-targeting when target dies
auto_explo = False            # Auto-throw explosion potions at enemies
target_reds = True
target_grays = True

# Base stats (for buff detection)
base_str = 100  # Will be loaded from persistent storage
base_dex = 100  # Will be loaded from persistent storage

# Trapped pouch
trapped_pouch_serial = 0      # Serial of the trapped pouch to use
use_trapped_pouch = True      # Whether to use trapped pouch for paralyze

# Combat tracking
current_attack_target = 0     # Serial of current attack target
last_explo_attempt = 0        # Timestamp of last explosion attempt
EXPLO_RETRY_DELAY = 1.0       # Seconds to wait before retrying failed throw

# Config window tracking
config_gump = None
config_controls = {}
config_pos_tracker = None

# Throwables system (user-configurable graphic IDs and priority)
throwables = {
    "lesser_explosion": {"graphic": 0x0F0A, "label": "Lesser Explosion"},
    "explosion": {"graphic": 0x0F0D, "label": "Explosion"},
    "greater_explosion": {"graphic": 0x0F0E, "label": "Greater Explosion"},
    "confusion_blast": {"graphic": 0x0000, "label": "Confusion Blast"},
    "custom1": {"graphic": 0x0000, "label": "Custom 1"},
    "custom2": {"graphic": 0x0000, "label": "Custom 2"}
}

# Throwable priority (list of keys from throwables dict, in preference order)
throwable_priority = [
    "confusion_blast",
    "greater_explosion",
    "explosion",
    "lesser_explosion",
    "custom1",
    "custom2"
]

# Hotkeys
HOTKEY_HEAL_POTION = "F1"
HOTKEY_CURE_POTION = "F2"
HOTKEY_REFRESH_POTION = "F3"
HOTKEY_BANDAGE = "F6"
HOTKEY_EXPLO_POTION = "F7"
HOTKEY_PAUSE = "PAUSE"
HOTKEY_ATTACK = "TAB"  # TAB works, backtick (`) doesn't register

# Control
PAUSED = False
next_display_update = 0

# ============ UTILITY FUNCTIONS ============
def debug_msg(text):
    if DEBUG:
        API.SysMsg("DEBUG: " + text, 88)

def get_hp_percent():
    try:
        player = API.Player
        if player.HitsMax > 0:
            return int((player.Hits / player.HitsMax) * 100)
        return 100
    except (AttributeError, ZeroDivisionError, TypeError):
        return 100

def get_stam_percent():
    try:
        player = API.Player
        # Try multiple attribute names
        stam = getattr(player, 'Stam', getattr(player, 'Stamina', 0))
        stam_max = getattr(player, 'StamMax', getattr(player, 'StaminaMax', 1))

        if stam_max > 0:
            return int((stam / stam_max) * 100)
        return 100
    except (AttributeError, ZeroDivisionError, TypeError):
        return 100

def get_stam_values():
    """Get current stam and max stam values"""
    try:
        player = API.Player
        stam = getattr(player, 'Stam', getattr(player, 'Stamina', 0))
        stam_max = getattr(player, 'StamMax', getattr(player, 'StaminaMax', 0))
        return (stam, stam_max)
    except (AttributeError, TypeError):
        return (0, 0)

def get_mana_percent():
    try:
        player = API.Player
        # Try multiple attribute names
        mana = getattr(player, 'Mana', 0)
        mana_max = getattr(player, 'ManaMax', 1)

        if mana_max > 0:
            return int((mana / mana_max) * 100)
        return 100
    except (AttributeError, ZeroDivisionError, TypeError):
        return 100

def get_mana_values():
    """Get current mana and max mana values"""
    try:
        player = API.Player
        mana = getattr(player, 'Mana', 0)
        mana_max = getattr(player, 'ManaMax', 0)
        return (mana, mana_max)
    except (AttributeError, TypeError):
        return (0, 0)

def get_player_hits_diff():
    try:
        player = API.Player
        return player.HitsMax - player.Hits
    except (AttributeError, TypeError):
        return 0

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

    # Cancel any existing targets
    cancel_all_targets()

    try:
        target = API.RequestTarget(timeout=10)
        if target:
            item = API.FindItem(target)
            if item:
                trapped_pouch_serial = target
                API.SavePersistentVar(TRAPPED_POUCH_SERIAL_KEY, str(trapped_pouch_serial), API.PersistentVar.Char)
                API.SysMsg("Trapped pouch set! Serial: " + hex(trapped_pouch_serial), 68)
                update_display()
            else:
                API.SysMsg("Target not found!", 32)
        else:
            API.SysMsg("Target cancelled", 43)

        cancel_all_targets()
    except Exception as e:
        API.SysMsg("Target error: " + str(e), 32)
        cancel_all_targets()

# ============ STATE MANAGEMENT ============
def check_heal_complete():
    """Check if bandage timer elapsed, transition to idle"""
    global HEAL_STATE

    if HEAL_STATE == "healing":
        if time.time() >= heal_start_time + BANDAGE_DELAY:
            HEAL_STATE = "idle"
            statusLabel.SetText("Running")
            return True

    return HEAL_STATE == "idle"

def start_bandage():
    """Begin bandage, set state to healing, record start time"""
    global HEAL_STATE, heal_start_time

    if HEAL_STATE != "idle":
        return False

    if is_player_dead():
        return False

    bandage = None
    if API.FindType(BANDAGE):
        bandage = API.Found

    if not bandage:
        API.SysMsg("Out of bandages!", 32)
        return False

    try:
        # Bandage self
        API.PreTarget(API.Player.Serial, "beneficial")
        API.Pause(0.1)
        API.UseObject(bandage, False)
        API.Pause(0.1)
        API.CancelPreTarget()
        cancel_all_targets()

        HEAL_STATE = "healing"
        heal_start_time = time.time()
        statusLabel.SetText("Bandaging...")

        # Create cooldown bar
        try:
            API.CreateCooldownBar(BANDAGE_DELAY, "Bandaging...", 68)
        except (AttributeError, Exception):
            pass

        debug_msg("Started bandage")
        return True
    except Exception as e:
        API.SysMsg("Bandage error: " + str(e), 32)
        return False

def potion_ready():
    """Check if 10s cooldown expired"""
    return time.time() >= potion_cooldown_end

def drink_potion(graphic, label):
    """Use potion, start cooldown, create cooldown bar"""
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

        # Create cooldown bar
        try:
            API.CreateCooldownBar(POTION_COOLDOWN, label, 32)
        except (AttributeError, Exception):
            pass

        return True
    except Exception as e:
        API.SysMsg("Potion error: " + str(e), 32)
        return False

def is_str_buffed():
    """Check if STR buff is currently active by reading stats"""
    try:
        current_str = API.Player.Str
        # Consider buffed if current STR is at least 15 above base (accounts for variance)
        return current_str >= base_str + 15
    except (AttributeError, TypeError):
        return False

def is_agi_buffed():
    """Check if AGI buff is currently active by reading stats (DEX)"""
    try:
        current_dex = getattr(API.Player, 'Dex', getattr(API.Player, 'Dexterity', 0))
        # Consider buffed if current DEX is at least 15 above base (accounts for variance)
        return current_dex >= base_dex + 15
    except (AttributeError, TypeError):
        return False

def needs_str_buff():
    """Check if STR buff needs refreshing (time-based + stat verification)"""
    # If we just drank STR recently (grace period), trust the timer
    if time.time() < last_str_drink_time + BUFF_GRACE_PERIOD:
        return False  # Don't rebuff during grace period

    # If stat check shows no buff, need to rebuff
    if not is_str_buffed():
        return True

    # If buff expires soon (within refresh window), rebuff
    if time.time() >= str_buff_end - BUFF_REFRESH_WINDOW:
        return True

    return False

def needs_agi_buff():
    """Check if AGI buff needs refreshing (time-based + stat verification)"""
    # If we just drank AGI recently (grace period), trust the timer
    if time.time() < last_agi_drink_time + BUFF_GRACE_PERIOD:
        return False  # Don't rebuff during grace period

    # If stat check shows no buff, need to rebuff
    if not is_agi_buffed():
        return True

    # If buff expires soon (within refresh window), rebuff
    if time.time() >= agi_buff_end - BUFF_REFRESH_WINDOW:
        return True

    return False

def drink_str_potion():
    """Drink strength potion and track buff"""
    global str_buff_end, potion_cooldown_end, last_buff_was_str, last_str_drink_time

    if not potion_ready():
        return False

    potion = None
    if API.FindType(POTION_STRENGTH):
        potion = API.Found

    if not potion:
        return False

    try:
        API.UseObject(potion, False)
        now = time.time()
        potion_cooldown_end = now + POTION_COOLDOWN
        str_buff_end = now + BUFF_DURATION
        last_str_drink_time = now  # Grace period starts now
        last_buff_was_str = True  # Track that we just drank STR
        statusLabel.SetText("STR Buff!")

        API.SysMsg("STR Buff active for 120s", 68)
        return True
    except Exception as e:
        API.SysMsg("STR potion error: " + str(e), 32)
        return False

def drink_agi_potion():
    """Drink agility potion and track buff"""
    global agi_buff_end, potion_cooldown_end, last_buff_was_str, last_agi_drink_time

    if not potion_ready():
        return False

    potion = None
    if API.FindType(POTION_AGILITY):
        potion = API.Found

    if not potion:
        return False

    try:
        API.UseObject(potion, False)
        now = time.time()
        potion_cooldown_end = now + POTION_COOLDOWN
        agi_buff_end = now + BUFF_DURATION
        last_agi_drink_time = now  # Grace period starts now
        last_buff_was_str = False  # Track that we just drank AGI
        statusLabel.SetText("AGI Buff!")

        API.SysMsg("AGI Buff active for 120s", 68)
        return True
    except Exception as e:
        API.SysMsg("AGI potion error: " + str(e), 32)
        return False

# ============ PRIORITY LOGIC ============
def get_priority_action():
    """
    Determine what action to take next based on priority.
    Returns (action_type, param) or None.

    Priority:
    0. PARALYZE: Break paralyze with trapped pouch (if safe HP)
    1. CRITICAL: Poisoned + HP < 30% -> Cure Potion (always)
    2. CRITICAL: HP < 30% -> Heal Potion (always)
    3. CURE: Poisoned -> Cure Potion (always)
    4. HEAL POTION: HP < 50% threshold -> Heal Potion (always)
    5. BANDAGE: Any HP loss (<100%) -> Bandage (only if auto_heal enabled)
    6. STAMINA: Stamina < threshold -> Refresh Potion (always)
    7. STR BUFF: Maintain strength buff (only if auto_buff enabled)
    8. AGI BUFF: Maintain agility buff (only if auto_buff enabled)

    Note: AUTO-BAND toggle controls bandages. AUTO-BUFF toggle controls buffs. Healing/curing always active.
    """

    if is_player_dead():
        return None

    hp_pct = get_hp_percent()
    stam_pct = get_stam_percent()
    poisoned = is_player_poisoned()
    paralyzed = is_player_paralyzed()
    hits_diff = get_player_hits_diff()

    # PARALYZE: Break with trapped pouch if safe (HIGHEST PRIORITY)
    if paralyzed and use_trapped_pouch and trapped_pouch_serial > 0:
        if API.Player.Hits >= TRAPPED_POUCH_MIN_HP:
            return ("trapped_pouch", None)
        else:
            debug_msg("Paralyzed but HP too low for trapped pouch!")

    # CRITICAL: Poisoned + Low HP -> Cure first (ALWAYS)
    if poisoned and hp_pct < critical_threshold:
        if potion_ready() and get_item_count(POTION_CURE) > 0:
            return ("cure_potion", None)

    # CRITICAL: Low HP -> Heal potion (ALWAYS)
    if hp_pct < critical_threshold:
        if potion_ready() and get_item_count(POTION_HEAL) > 0:
            return ("heal_potion", None)

    # CURE: Poisoned -> Cure potion (ALWAYS)
    if poisoned:
        if potion_ready() and get_item_count(POTION_CURE) > 0:
            return ("cure_potion", None)

    # HEAL POTION: HP below potion threshold (ALWAYS)
    if hp_pct < heal_threshold:
        if potion_ready() and get_item_count(POTION_HEAL) > 0:
            return ("heal_potion", None)

    # BANDAGE: Any HP loss (ONLY if auto_heal enabled)
    if auto_heal and HEAL_STATE == "idle" and hits_diff >= bandage_diff_threshold:
        return ("bandage", None)

    # STAMINA: Below threshold (ALWAYS)
    if stam_pct < stamina_threshold:
        if potion_ready() and get_item_count(POTION_REFRESH) > 0:
            return ("refresh_potion", None)

    # BUFF MAINTENANCE: Alternate between STR and AGI to maintain both
    # Since all potions share 10s cooldown, we must alternate to keep both up
    if auto_buff and potion_ready():
        str_needs_buff = needs_str_buff()
        agi_needs_buff = needs_agi_buff()

        # If both need buffing, alternate between them
        if str_needs_buff and agi_needs_buff:
            global last_buff_was_str
            if last_buff_was_str:
                # Last buff was STR, now do AGI
                if get_item_count(POTION_AGILITY) > 0:
                    return ("agi_potion", None)
                elif get_item_count(POTION_STRENGTH) > 0:
                    return ("str_potion", None)
            else:
                # Last buff was AGI (or first time), now do STR
                if get_item_count(POTION_STRENGTH) > 0:
                    return ("str_potion", None)
                elif get_item_count(POTION_AGILITY) > 0:
                    return ("agi_potion", None)
        # Only one needs buffing
        elif str_needs_buff:
            if get_item_count(POTION_STRENGTH) > 0:
                return ("str_potion", None)
        elif agi_needs_buff:
            if get_item_count(POTION_AGILITY) > 0:
                return ("agi_potion", None)

    return None

def execute_action(action):
    """Dispatch action"""
    if not action:
        return False

    action_type, param = action

    if action_type == "trapped_pouch":
        return use_trapped_pouch()
    elif action_type == "heal_potion":
        return drink_potion(POTION_HEAL, "Heal Potion")
    elif action_type == "cure_potion":
        return drink_potion(POTION_CURE, "Cure Potion")
    elif action_type == "refresh_potion":
        return drink_potion(POTION_REFRESH, "Refresh Potion")
    elif action_type == "bandage":
        return start_bandage()
    elif action_type == "str_potion":
        return drink_str_potion()
    elif action_type == "agi_potion":
        return drink_agi_potion()

    return False

# ============ GUI CALLBACKS ============
def toggle_pause():
    global PAUSED
    PAUSED = not PAUSED
    if PAUSED:
        pauseBtn.SetText("[PAUSED]")
        pauseBtn.SetBackgroundHue(32)
        statusLabel.SetText("*** PAUSED ***")
        API.SysMsg("Dexer Suite PAUSED", 43)
    else:
        pauseBtn.SetText("[PAUSE]")
        pauseBtn.SetBackgroundHue(90)
        statusLabel.SetText("Running")
        API.SysMsg("Dexer Suite RESUMED", 68)

def toggle_auto_heal():
    global auto_heal
    auto_heal = not auto_heal
    API.SavePersistentVar(AUTO_HEAL_KEY, str(auto_heal), API.PersistentVar.Char)
    autoHealBtn.SetText("[AUTO-BAND:" + ("ON" if auto_heal else "OFF") + "]")
    autoHealBtn.SetBackgroundHue(68 if auto_heal else 90)
    API.SysMsg("Auto-Bandage: " + ("ON" if auto_heal else "OFF"), 68)

def toggle_auto_buff():
    global auto_buff
    auto_buff = not auto_buff
    API.SavePersistentVar(AUTO_BUFF_KEY, str(auto_buff), API.PersistentVar.Char)
    autoBuffBtn.SetText("[AUTO-BUFF:" + ("ON" if auto_buff else "OFF") + "]")
    autoBuffBtn.SetBackgroundHue(68 if auto_buff else 90)
    API.SysMsg("Auto-Buff: " + ("ON" if auto_buff else "OFF"), 68)

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
        current_attack_target = 0  # Clear current target

def toggle_auto_explo():
    global auto_explo
    auto_explo = not auto_explo
    API.SavePersistentVar(AUTO_EXPLO_KEY, str(auto_explo), API.PersistentVar.Char)
    autoExploBtn.SetText("[AUTO-EXPLO:" + ("ON" if auto_explo else "OFF") + "]")
    autoExploBtn.SetBackgroundHue(68 if auto_explo else 90)
    API.SysMsg("Auto-Explosion: " + ("ON" if auto_explo else "OFF"), 68 if auto_explo else 32)

def toggle_use_trapped_pouch():
    global use_trapped_pouch
    use_trapped_pouch = not use_trapped_pouch
    API.SavePersistentVar(USE_TRAPPED_POUCH_KEY, str(use_trapped_pouch), API.PersistentVar.Char)
    usePouchBtn.SetText("[USE POUCH:" + ("ON" if use_trapped_pouch else "OFF") + "]")
    usePouchBtn.SetBackgroundHue(68 if use_trapped_pouch else 90)
    API.SysMsg("Use Trapped Pouch: " + ("ON" if use_trapped_pouch else "OFF"), 68)

def on_set_trapped_pouch():
    target_trapped_pouch()

def on_drink_heal():
    drink_potion(POTION_HEAL, "Heal Potion")

def on_drink_cure():
    drink_potion(POTION_CURE, "Cure Potion")

def on_drink_refresh():
    drink_potion(POTION_REFRESH, "Refresh Potion")

def on_bandage_button():
    start_bandage()

# ============ EXPLOSION POTIONS ============
def get_best_explosion_potion():
    """Get best available throwable based on priority order"""
    global throwables, throwable_priority

    # Check each throwable in priority order
    for key in throwable_priority:
        if key not in throwables:
            continue

        data = throwables.get(key, {})
        if not isinstance(data, dict):
            continue

        # Use .get() with defaults for safety
        graphic = data.get("graphic", 0)

        # Skip if not configured (0x0000)
        if graphic == 0x0000:
            continue

        # Check if we have this throwable
        if get_item_count(graphic) > 0:
            return (graphic, data.get("label", "Unknown"))

    return (None, None)

def throw_explosion_potion(target_serial=None):
    """Throw explosion potion at target (USE POTION FIRST, then target)"""
    global potion_cooldown_end, last_explo_attempt

    if not potion_ready():
        remaining = int(potion_cooldown_end - time.time())
        API.SysMsg("Potion on cooldown: " + str(remaining) + "s", 43)
        return False

    # Get target
    if target_serial is None:
        if current_attack_target != 0:
            target = API.FindMobile(current_attack_target)
            if target and not target.IsDead:
                target_serial = current_attack_target

        if target_serial is None:
            enemy = find_attack_target()
            if enemy:
                target_serial = enemy.Serial

    if target_serial is None:
        API.SysMsg("No target for explosion potion!", 43)
        return False

    # Check target is valid and in range
    target = API.FindMobile(target_serial)
    if not target or target.IsDead:
        API.SysMsg("Target invalid!", 32)
        return False

    target_distance = getattr(target, 'Distance', 999) if target else 999
    if target_distance > 12:
        API.SysMsg("Target out of range!", 32)
        return False

    # Get best potion
    potion_graphic, potion_label = get_best_explosion_potion()
    if potion_graphic is None:
        API.SysMsg("Out of explosion potions!", 32)
        return False

    potion = None
    if API.FindType(potion_graphic):
        potion = API.Found

    if not potion:
        API.SysMsg("Out of " + potion_label + "!", 32)
        return False

    try:
        # Standard targeting pattern: PreTarget BEFORE UseObject
        # PreTarget sets up the target, UseObject triggers with that target
        cancel_all_targets()

        # Step 1: Set the target FIRST (longer pause for server response)
        API.PreTarget(target_serial, "harmful")
        API.Pause(0.4)  # Increased to allow PreTarget to register

        # Step 2: Use the potion (will use the pre-targeted enemy)
        API.UseObject(potion, False)
        API.Pause(0.3)  # Wait for action to complete

        # Clean up
        API.CancelPreTarget()

        potion_cooldown_end = time.time() + POTION_COOLDOWN
        statusLabel.SetText(potion_label + "!")
        API.HeadMsg("BOOM!", target_serial, 32)

        # Create cooldown bar
        try:
            API.CreateCooldownBar(POTION_COOLDOWN, potion_label, 32)
        except (AttributeError, Exception):
            pass

        return True
    except Exception as e:
        API.SysMsg("Explosion error: " + str(e), 32)
        cancel_all_targets()
        return False

def on_throw_explo():
    """Hotkey callback for manual explosion potion throw"""
    throw_explosion_potion()

# ============ ATTACK/TARGETING ============
def find_attack_target():
    """Find nearest hostile based on target settings"""
    notorieties = [API.Notoriety.Enemy]
    if target_grays:
        notorieties.extend([API.Notoriety.Gray, API.Notoriety.Criminal])
    if target_reds:
        notorieties.append(API.Notoriety.Murderer)

    enemy = API.NearestMobile(notorieties, MAX_DISTANCE)
    if enemy and enemy.Serial != API.Player.Serial:
        return enemy
    return None

def attack_nearest():
    """Attack nearest hostile (TAB hotkey)"""
    global current_attack_target
    enemy = find_attack_target()
    if enemy:
        API.Attack(enemy)
        current_attack_target = enemy.Serial  # Track this target
        API.HeadMsg("ATTACK!", enemy.Serial, 32)
        API.SysMsg("Attacking: " + get_mob_name(enemy), 68)
    else:
        API.SysMsg("No hostile target found", 53)

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
    target_distance = getattr(target, 'Distance', 999) if target else 999
    if not target or target.IsDead or target_distance > AUTO_TARGET_RANGE:
        # Build notoriety list based on settings
        notorieties = [API.Notoriety.Enemy]
        if target_grays:
            notorieties.append(API.Notoriety.Gray)
            notorieties.append(API.Notoriety.Criminal)
        if target_reds:
            notorieties.append(API.Notoriety.Murderer)

        # Find next target within 3 tiles
        next_enemy = API.NearestMobile(notorieties, AUTO_TARGET_RANGE)

        if next_enemy and next_enemy.Serial != API.Player.Serial and not next_enemy.IsDead:
            API.Attack(next_enemy)
            current_attack_target = next_enemy.Serial
            API.HeadMsg("NEXT!", next_enemy.Serial, 68)
            API.SysMsg("Auto-targeting: " + get_mob_name(next_enemy), 68)
        else:
            # No more targets in range
            current_attack_target = 0

def toggle_target_reds():
    """Toggle red targeting"""
    global target_reds
    target_reds = not target_reds
    API.SavePersistentVar(TARGET_REDS_KEY, str(target_reds), API.PersistentVar.Char)
    update_display()
    API.SysMsg("Target Reds: " + ("ON" if target_reds else "OFF"), 68 if target_reds else 32)

def toggle_target_grays():
    """Toggle gray targeting"""
    global target_grays
    target_grays = not target_grays
    API.SavePersistentVar(TARGET_GRAYS_KEY, str(target_grays), API.PersistentVar.Char)
    update_display()
    API.SysMsg("Target Grays: " + ("ON" if target_grays else "OFF"), 68 if target_grays else 32)

# ============ HOTKEY CALLBACKS ============
def on_heal_potion_hotkey():
    drink_potion(POTION_HEAL, "Heal Potion")

def on_cure_potion_hotkey():
    drink_potion(POTION_CURE, "Cure Potion")

def on_refresh_potion_hotkey():
    drink_potion(POTION_REFRESH, "Refresh Potion")

def on_bandage_hotkey():
    start_bandage()

def on_explo_potion_hotkey():
    throw_explosion_potion()

def on_pause_hotkey():
    toggle_pause()

def on_attack_hotkey():
    attack_nearest()

# ============ PERSISTENCE ============
def load_settings():
    global heal_threshold, critical_threshold, stamina_threshold, bandage_diff_threshold
    global auto_heal, auto_buff, auto_target, auto_explo, target_reds, target_grays
    global HOTKEY_HEAL_POTION, HOTKEY_CURE_POTION, HOTKEY_REFRESH_POTION
    global HOTKEY_BANDAGE, HOTKEY_EXPLO_POTION, HOTKEY_PAUSE, HOTKEY_ATTACK
    global base_str, base_dex
    global trapped_pouch_serial, use_trapped_pouch
    global throwables, throwable_priority

    # Thresholds
    try:
        heal_threshold = int(API.GetPersistentVar(HEAL_THRESHOLD_KEY, str(DEFAULT_HEAL_THRESHOLD), API.PersistentVar.Char))
    except (ValueError, TypeError):
        heal_threshold = DEFAULT_HEAL_THRESHOLD

    try:
        critical_threshold = int(API.GetPersistentVar(CRITICAL_THRESHOLD_KEY, str(DEFAULT_CRITICAL_THRESHOLD), API.PersistentVar.Char))
    except (ValueError, TypeError):
        critical_threshold = DEFAULT_CRITICAL_THRESHOLD

    try:
        stamina_threshold = int(API.GetPersistentVar(STAMINA_THRESHOLD_KEY, str(DEFAULT_STAMINA_THRESHOLD), API.PersistentVar.Char))
    except (ValueError, TypeError):
        stamina_threshold = DEFAULT_STAMINA_THRESHOLD

    try:
        bandage_diff_threshold = int(API.GetPersistentVar(BANDAGE_DIFF_KEY, str(DEFAULT_BANDAGE_DIFF), API.PersistentVar.Char))
    except (ValueError, TypeError):
        bandage_diff_threshold = DEFAULT_BANDAGE_DIFF

    # Toggles
    auto_heal = API.GetPersistentVar(AUTO_HEAL_KEY, "True", API.PersistentVar.Char) == "True"
    auto_buff = API.GetPersistentVar(AUTO_BUFF_KEY, "True", API.PersistentVar.Char) == "True"
    auto_target = API.GetPersistentVar(AUTO_TARGET_KEY, "False", API.PersistentVar.Char) == "True"
    auto_explo = API.GetPersistentVar(AUTO_EXPLO_KEY, "False", API.PersistentVar.Char) == "True"
    target_reds = API.GetPersistentVar(TARGET_REDS_KEY, "True", API.PersistentVar.Char) == "True"
    target_grays = API.GetPersistentVar(TARGET_GRAYS_KEY, "True", API.PersistentVar.Char) == "True"
    use_trapped_pouch = API.GetPersistentVar(USE_TRAPPED_POUCH_KEY, "True", API.PersistentVar.Char) == "True"

    # Trapped pouch
    try:
        trapped_pouch_serial = int(API.GetPersistentVar(TRAPPED_POUCH_SERIAL_KEY, "0", API.PersistentVar.Char))
    except (ValueError, TypeError):
        trapped_pouch_serial = 0

    # Base stats (load or detect from current stats)
    try:
        base_str = int(API.GetPersistentVar(BASE_STR_KEY, "0", API.PersistentVar.Char))
        if base_str == 0:
            # First run - try to read current stats as base
            base_str = API.Player.Str
            API.SavePersistentVar(BASE_STR_KEY, str(base_str), API.PersistentVar.Char)
    except (ValueError, TypeError, AttributeError):
        base_str = 100  # Fallback default

    try:
        base_dex = int(API.GetPersistentVar(BASE_DEX_KEY, "0", API.PersistentVar.Char))
        if base_dex == 0:
            # First run - try to read current stats as base
            base_dex = getattr(API.Player, 'Dex', getattr(API.Player, 'Dexterity', 100))
            API.SavePersistentVar(BASE_DEX_KEY, str(base_dex), API.PersistentVar.Char)
    except (ValueError, TypeError, AttributeError):
        base_dex = 100  # Fallback default

    # Hotkeys
    HOTKEY_HEAL_POTION = API.GetPersistentVar(HOTKEY_HEAL_POTION_KEY, "F1", API.PersistentVar.Char)
    HOTKEY_CURE_POTION = API.GetPersistentVar(HOTKEY_CURE_POTION_KEY, "F2", API.PersistentVar.Char)
    HOTKEY_REFRESH_POTION = API.GetPersistentVar(HOTKEY_REFRESH_POTION_KEY, "F3", API.PersistentVar.Char)
    HOTKEY_BANDAGE = API.GetPersistentVar(HOTKEY_BANDAGE_KEY, "F6", API.PersistentVar.Char)
    HOTKEY_EXPLO_POTION = API.GetPersistentVar(HOTKEY_EXPLO_POTION_KEY, "F7", API.PersistentVar.Char)
    HOTKEY_PAUSE = API.GetPersistentVar(HOTKEY_PAUSE_KEY, "PAUSE", API.PersistentVar.Char)
    HOTKEY_ATTACK = API.GetPersistentVar(HOTKEY_ATTACK_KEY, "TAB", API.PersistentVar.Char)

    # Load throwables with validation and schema versioning
    throwables_str = API.GetPersistentVar(THROWABLES_KEY, "", API.PersistentVar.Char)
    if throwables_str:
        try:
            parts = throwables_str.split("|")
            schema_ver = 0  # Default to v0 (no version) for backward compatibility
            start_idx = 0

            # Check if first part is a version identifier
            if parts and parts[0].startswith("v"):
                try:
                    schema_ver = int(parts[0][1:])
                    start_idx = 1  # Skip version entry
                except (ValueError, IndexError):
                    pass

            # Parse based on schema version
            if schema_ver == 1:
                # Format: "v1|key:graphic:label|key:graphic:label|..."
                for entry in parts[start_idx:]:
                    if not entry:
                        continue
                    entry_parts = entry.split(":")
                    if len(entry_parts) == 3:
                        key, graphic_hex, label = entry_parts
                        if key not in throwables:
                            continue

                        # Validate graphic ID
                        try:
                            graphic = int(graphic_hex, 16)
                            if graphic < 0 or graphic > 0xFFFF:
                                continue  # Invalid range
                        except (ValueError, TypeError):
                            continue

                        # Sanitize label (remove delimiters, limit length)
                        label = str(label).replace("|", "").replace(":", "")[:50]

                        throwables[key]["graphic"] = graphic
                        throwables[key]["label"] = label
            else:
                # Legacy format (v0): "key:graphic:label|key:graphic:label|..."
                for entry in parts:
                    if not entry:
                        continue
                    entry_parts = entry.split(":")
                    if len(entry_parts) == 3:
                        key, graphic_hex, label = entry_parts
                        if key not in throwables:
                            continue

                        try:
                            graphic = int(graphic_hex, 16)
                            if graphic < 0 or graphic > 0xFFFF:
                                continue
                        except (ValueError, TypeError):
                            continue

                        label = str(label).replace("|", "").replace(":", "")[:50]
                        throwables[key]["graphic"] = graphic
                        throwables[key]["label"] = label
        except Exception as e:
            API.SysMsg("Error loading throwables (using defaults): " + str(e), 32)

    # Load throwable priority with validation
    priority_str = API.GetPersistentVar(THROWABLE_PRIORITY_KEY, "", API.PersistentVar.Char)
    if priority_str:
        try:
            loaded_priority = [x for x in priority_str.split(",") if x and x in throwables]
            if loaded_priority:
                throwable_priority = loaded_priority
        except Exception:
            pass  # Use default if corrupted

    # Validate loaded thresholds are in bounds
    heal_threshold = max(20, min(90, heal_threshold))
    critical_threshold = max(10, min(50, critical_threshold))
    stamina_threshold = max(10, min(80, stamina_threshold))

def save_throwables():
    """Save throwables configuration with schema version"""
    global throwables, throwable_priority

    # Save throwables: "v1|key:graphic:label|key:graphic:label|..."
    entries = ["v{}".format(THROWABLES_SCHEMA_VERSION)]  # Add version prefix
    for key, data in throwables.items():
        entries.append("{}:0x{:04X}:{}".format(key, data["graphic"], data["label"]))
    throwables_str = "|".join(entries)
    API.SavePersistentVar(THROWABLES_KEY, throwables_str, API.PersistentVar.Char)

    # Save priority order
    priority_str = ",".join(throwable_priority)
    API.SavePersistentVar(THROWABLE_PRIORITY_KEY, priority_str, API.PersistentVar.Char)

    API.SysMsg("Throwables saved", 68)

def adjust_heal_threshold(increment):
    """Adjust heal threshold by 5% (range: 20-90%)"""
    global heal_threshold
    if increment:
        heal_threshold = min(90, heal_threshold + 5)
    else:
        heal_threshold = max(20, heal_threshold - 5)

    API.SavePersistentVar(HEAL_THRESHOLD_KEY, str(heal_threshold), API.PersistentVar.Char)

    # Update config window display
    if "heal_val" in config_controls:
        config_controls["heal_val"].SetText(str(heal_threshold) + "%")

    # Update main window display
    healThresholdLabel.SetText("Heal: " + str(heal_threshold) + "%")

def adjust_critical_threshold(increment):
    """Adjust critical threshold by 5% (range: 10-50%)"""
    global critical_threshold
    if increment:
        critical_threshold = min(50, critical_threshold + 5)
    else:
        critical_threshold = max(10, critical_threshold - 5)

    API.SavePersistentVar(CRITICAL_THRESHOLD_KEY, str(critical_threshold), API.PersistentVar.Char)

    if "critical_val" in config_controls:
        config_controls["critical_val"].SetText(str(critical_threshold) + "%")

    criticalThresholdLabel.SetText("Critical: " + str(critical_threshold) + "%")

def adjust_stamina_threshold(increment):
    """Adjust stamina threshold by 5% (range: 10-80%)"""
    global stamina_threshold
    if increment:
        stamina_threshold = min(80, stamina_threshold + 5)
    else:
        stamina_threshold = max(10, stamina_threshold - 5)

    API.SavePersistentVar(STAMINA_THRESHOLD_KEY, str(stamina_threshold), API.PersistentVar.Char)

    if "stam_val" in config_controls:
        config_controls["stam_val"].SetText(str(stamina_threshold) + "%")

    stamThresholdLabel.SetText("Stam: " + str(stamina_threshold) + "%")

def capture_throwable_graphic(throwable_key):
    """Capture a throwable item's graphic ID via targeting"""
    global throwables, config_controls

    # Call blocking API directly - this is safe in button callback context
    API.SysMsg("Target the " + throwables[throwable_key]["label"] + "...", 68)

    try:
        # RequestTarget is safe to call from GUI callbacks (blocking is OK here)
        target = API.RequestTarget(timeout=15)
        if target:
            item = API.FindItem(target)
            if item:
                graphic = getattr(item, 'Graphic', 0)
                if graphic > 0:
                    throwables[throwable_key]["graphic"] = graphic
                    save_throwables()

                    # Update config window display
                    if throwable_key + "_graphic" in config_controls:
                        config_controls[throwable_key + "_graphic"].SetText("0x{:04X}".format(graphic))

                    API.SysMsg("Captured: 0x{:04X}".format(graphic), 68)
                else:
                    API.SysMsg("Invalid item graphic", 32)
            else:
                API.SysMsg("Item not found", 32)
        else:
            API.SysMsg("Target cancelled", 32)
    except Exception as e:
        API.SysMsg("Capture error: " + str(e), 32)

def clear_throwable_graphic(throwable_key):
    """Clear a throwable item's graphic ID (set to 0x0000)"""
    global throwables, config_controls

    throwables[throwable_key]["graphic"] = 0x0000
    save_throwables()

    # Update config window display
    if throwable_key + "_graphic" in config_controls:
        config_controls[throwable_key + "_graphic"].SetText("Not Set")

    API.SysMsg("Cleared " + throwables[throwable_key]["label"], 68)

def build_config_gump():
    """Create and display the separate config window"""
    global config_gump, config_controls, config_pos_tracker

    # Don't create if already open
    if config_gump is not None:
        return

    # Clear button references
    config_controls = {}

    # Create config gump (500x580px - larger for throwables section)
    config_gump = API.Gumps.CreateGump()

    # Setup window position tracker (using LegionUtils)
    config_pos_tracker = WindowPositionTracker(config_gump, CONFIG_XY_KEY, default_x=150, default_y=150)
    config_gump.SetRect(config_pos_tracker.last_x, config_pos_tracker.last_y, 500, 580)

    # Main background
    cfg_bg = API.Gumps.CreateGumpColorBox(0.9, "#1a1a2e")
    cfg_bg.SetRect(0, 0, 500, 580)
    config_gump.Add(cfg_bg)

    # Title
    title = API.Gumps.CreateGumpTTFLabel("Dexer Suite Configuration", 16, "#ffaa00")
    title.SetPos(130, 8)
    config_gump.Add(title)

    # Close button
    close_btn = API.Gumps.CreateSimpleButton("[X]", 30, 22)
    close_btn.SetPos(460, 5)
    close_btn.SetBackgroundHue(32)
    API.Gumps.AddControlOnClick(close_btn, close_config_gump)
    config_gump.Add(close_btn)

    y = 50
    left_x = 20

    # === HEALING THRESHOLDS SECTION ===
    section_title = API.Gumps.CreateGumpTTFLabel("=== Healing Thresholds ===", 15, "#00ffaa")
    section_title.SetPos(150, y)
    config_gump.Add(section_title)

    y += 25

    # Heal Threshold (Potion)
    heal_lbl = API.Gumps.CreateGumpTTFLabel("Heal Potion:", 15, "#dddddd")
    heal_lbl.SetPos(left_x, y + 3)
    config_gump.Add(heal_lbl)

    heal_dec = API.Gumps.CreateSimpleButton("[-]", 30, 18)
    heal_dec.SetPos(left_x + 100, y)
    heal_dec.SetBackgroundHue(90)
    API.Gumps.AddControlOnClick(heal_dec, lambda: adjust_heal_threshold(False))
    config_gump.Add(heal_dec)

    config_controls["heal_val"] = API.Gumps.CreateGumpTTFLabel(str(heal_threshold) + "%", 15, "#ffaa00")
    config_controls["heal_val"].SetPos(left_x + 135, y + 3)
    config_gump.Add(config_controls["heal_val"])

    heal_inc = API.Gumps.CreateSimpleButton("[+]", 30, 18)
    heal_inc.SetPos(left_x + 175, y)
    heal_inc.SetBackgroundHue(90)
    API.Gumps.AddControlOnClick(heal_inc, lambda: adjust_heal_threshold(True))
    config_gump.Add(heal_inc)

    # Help text
    heal_help = API.Gumps.CreateGumpTTFLabel("(20-90%) Drink heal potion", 15, "#888888")
    heal_help.SetPos(left_x + 215, y + 3)
    config_gump.Add(heal_help)

    y += 30

    # Critical Threshold
    crit_lbl = API.Gumps.CreateGumpTTFLabel("Critical:", 15, "#dddddd")
    crit_lbl.SetPos(left_x, y + 3)
    config_gump.Add(crit_lbl)

    crit_dec = API.Gumps.CreateSimpleButton("[-]", 30, 18)
    crit_dec.SetPos(left_x + 100, y)
    crit_dec.SetBackgroundHue(90)
    API.Gumps.AddControlOnClick(crit_dec, lambda: adjust_critical_threshold(False))
    config_gump.Add(crit_dec)

    config_controls["critical_val"] = API.Gumps.CreateGumpTTFLabel(str(critical_threshold) + "%", 15, "#ff0000")
    config_controls["critical_val"].SetPos(left_x + 135, y + 3)
    config_gump.Add(config_controls["critical_val"])

    crit_inc = API.Gumps.CreateSimpleButton("[+]", 30, 18)
    crit_inc.SetPos(left_x + 175, y)
    crit_inc.SetBackgroundHue(90)
    API.Gumps.AddControlOnClick(crit_inc, lambda: adjust_critical_threshold(True))
    config_gump.Add(crit_inc)

    crit_help = API.Gumps.CreateGumpTTFLabel("(10-50%) Emergency HP", 15, "#888888")
    crit_help.SetPos(left_x + 215, y + 3)
    config_gump.Add(crit_help)

    y += 30

    # Stamina Threshold
    stam_lbl = API.Gumps.CreateGumpTTFLabel("Stamina:", 15, "#dddddd")
    stam_lbl.SetPos(left_x, y + 3)
    config_gump.Add(stam_lbl)

    stam_dec = API.Gumps.CreateSimpleButton("[-]", 30, 18)
    stam_dec.SetPos(left_x + 100, y)
    stam_dec.SetBackgroundHue(90)
    API.Gumps.AddControlOnClick(stam_dec, lambda: adjust_stamina_threshold(False))
    config_gump.Add(stam_dec)

    config_controls["stam_val"] = API.Gumps.CreateGumpTTFLabel(str(stamina_threshold) + "%", 15, "#00ffff")
    config_controls["stam_val"].SetPos(left_x + 135, y + 3)
    config_gump.Add(config_controls["stam_val"])

    stam_inc = API.Gumps.CreateSimpleButton("[+]", 30, 18)
    stam_inc.SetPos(left_x + 175, y)
    stam_inc.SetBackgroundHue(90)
    API.Gumps.AddControlOnClick(stam_inc, lambda: adjust_stamina_threshold(True))
    config_gump.Add(stam_inc)

    stam_help = API.Gumps.CreateGumpTTFLabel("(10-80%) Drink refresh", 15, "#888888")
    stam_help.SetPos(left_x + 215, y + 3)
    config_gump.Add(stam_help)

    y += 40

    # === THROWABLES SECTION ===
    section_title2 = API.Gumps.CreateGumpTTFLabel("=== Throwable Items ===", 15, "#ffaa00")
    section_title2.SetPos(180, y)
    config_gump.Add(section_title2)

    y += 25

    # Header labels
    header1 = API.Gumps.CreateGumpTTFLabel("Item", 15, "#888888")
    header1.SetPos(left_x, y)
    config_gump.Add(header1)

    header2 = API.Gumps.CreateGumpTTFLabel("Graphic ID", 15, "#888888")
    header2.SetPos(left_x + 180, y)
    config_gump.Add(header2)

    header3 = API.Gumps.CreateGumpTTFLabel("Action", 15, "#888888")
    header3.SetPos(left_x + 280, y)
    config_gump.Add(header3)

    y += 22

    # Display each throwable with [Set] button and priority indicators
    throwable_keys = ["confusion_blast", "greater_explosion", "explosion",
                      "lesser_explosion", "custom1", "custom2"]

    for idx, key in enumerate(throwable_keys):
        data = throwables[key]

        # Priority number (1-6)
        try:
            priority_num = throwable_priority.index(key) + 1
        except ValueError:
            priority_num = 99

        priority_lbl = API.Gumps.CreateGumpTTFLabel(str(priority_num) + ".", 15, "#00ffff")
        priority_lbl.SetPos(left_x, y + 3)
        config_gump.Add(priority_lbl)

        # Item label
        item_lbl = API.Gumps.CreateGumpTTFLabel(data["label"], 15, "#dddddd")
        item_lbl.SetPos(left_x + 25, y + 3)
        config_gump.Add(item_lbl)

        # Graphic ID display
        graphic_text = "0x{:04X}".format(data["graphic"]) if data["graphic"] > 0 else "Not Set"
        graphic_color = "#00ff00" if data["graphic"] > 0 else "#888888"
        config_controls[key + "_graphic"] = API.Gumps.CreateGumpTTFLabel(graphic_text, 15, graphic_color)
        config_controls[key + "_graphic"].SetPos(left_x + 180, y + 3)
        config_gump.Add(config_controls[key + "_graphic"])

        # [Set] button
        set_btn = API.Gumps.CreateSimpleButton("[Set]", 50, 18)
        set_btn.SetPos(left_x + 280, y)
        set_btn.SetBackgroundHue(68)
        API.Gumps.AddControlOnClick(set_btn, lambda k=key: capture_throwable_graphic(k))
        config_gump.Add(set_btn)

        # [Clear] button (to reset to 0x0000)
        clear_btn = API.Gumps.CreateSimpleButton("[X]", 30, 18)
        clear_btn.SetPos(left_x + 340, y)
        clear_btn.SetBackgroundHue(32)
        API.Gumps.AddControlOnClick(clear_btn, lambda k=key: clear_throwable_graphic(k))
        config_gump.Add(clear_btn)

        y += 25

    y += 15

    # === INFO SECTION ===
    info_title = API.Gumps.CreateGumpTTFLabel("Changes save automatically", 15, "#00ff00")
    info_title.SetPos(165, y)
    config_gump.Add(info_title)

    y += 20

    help_text = API.Gumps.CreateGumpTTFLabel("Click [Set] and target item in backpack", 15, "#888888")
    help_text.SetPos(115, y)
    config_gump.Add(help_text)

    # Position tracking callback
    API.Gumps.AddControlOnDisposed(config_gump, on_config_closed)

    # Add gump to screen
    API.Gumps.AddGump(config_gump)

    API.SysMsg("Configuration window opened", 68)

def close_config_gump():
    """Close the config window and save position"""
    global config_gump, config_pos_tracker
    if config_gump is not None:
        # Save position using WindowPositionTracker
        if config_pos_tracker:
            config_pos_tracker.save()
        config_gump.Dispose()
        config_gump = None
        API.SysMsg("Configuration saved", 68)

def on_config_closed():
    """Callback when config window is closed (via [X] or manual close)"""
    global config_gump, config_pos_tracker
    # Save position using WindowPositionTracker
    if config_pos_tracker:
        config_pos_tracker.save()
    config_gump = None

# ============ DISPLAY UPDATES ============
def create_resource_bar(current, max_val, width=10):
    """Generate ASCII bar like [====----]"""
    if max_val <= 0:
        return "[" + "-" * width + "]"

    pct = current / max_val
    filled = int(pct * width)
    empty = width - filled
    return "[" + "=" * filled + "-" * empty + "]"

def update_display():
    """Refresh all GUI elements"""
    try:
        player = API.Player

        # HP bar
        hp_pct = get_hp_percent()
        hp_bar = create_resource_bar(player.Hits, player.HitsMax, 12)
        hpLabel.SetText("HP: " + str(player.Hits) + "/" + str(player.HitsMax) + " (" + str(hp_pct) + "%)")
        hpBar.SetText(hp_bar)

        # Stamina bar
        stam_pct = get_stam_percent()
        stam, stam_max = get_stam_values()
        stam_bar = create_resource_bar(stam, stam_max, 12)
        stamLabel.SetText("Stam: " + str(stam) + "/" + str(stam_max) + " (" + str(stam_pct) + "%)")
        stamBar.SetText(stam_bar)

        # Mana bar
        mana_pct = get_mana_percent()
        mana, mana_max = get_mana_values()
        mana_bar = create_resource_bar(mana, mana_max, 12)
        manaLabel.SetText("Mana: " + str(mana) + "/" + str(mana_max) + " (" + str(mana_pct) + "%)")
        manaBar.SetText(mana_bar)

        # Poison status
        if is_player_poisoned():
            poisonLabel.SetText("POISONED!")
        else:
            poisonLabel.SetText("Clear")

        # Potion counts
        healPotionLabel.SetText("Heal: " + str(get_item_count(POTION_HEAL)))
        curePotionLabel.SetText("Cure: " + str(get_item_count(POTION_CURE)))
        refreshPotionLabel.SetText("Refresh: " + str(get_item_count(POTION_REFRESH)))

        # Explosion potion counts (Lesser/Normal/Greater)
        explo_l = get_item_count(POTION_EXPLOSION_LESSER)
        explo_n = get_item_count(POTION_EXPLOSION)
        explo_g = get_item_count(POTION_EXPLOSION_GREATER)
        exploPotionLabel.SetText("Explo: L" + str(explo_l) + "/N" + str(explo_n) + "/G" + str(explo_g))

        # Buff potions with timer display and progress bars
        str_count = get_item_count(POTION_STRENGTH)
        str_active = is_str_buffed()
        if str_active and time.time() < str_buff_end:
            str_remaining = int(str_buff_end - time.time())
            str_bar = create_resource_bar(str_remaining, BUFF_DURATION, 10)
            strPotionLabel.SetText("Str: " + str(str_count) + " [" + str(str_remaining) + "s]")
            strBuffBar.SetText(str_bar)
        elif str_active:
            # Stats show buffed but timer expired - show as active but unknown time
            strPotionLabel.SetText("Str: " + str(str_count) + " [ACTIVE]")
            strBuffBar.SetText("[==========]")
        else:
            strPotionLabel.SetText("Str: " + str(str_count))
            strBuffBar.SetText("[----------]")

        agi_count = get_item_count(POTION_AGILITY)
        agi_active = is_agi_buffed()
        if agi_active and time.time() < agi_buff_end:
            agi_remaining = int(agi_buff_end - time.time())
            agi_bar = create_resource_bar(agi_remaining, BUFF_DURATION, 10)
            agiPotionLabel.SetText("Agi: " + str(agi_count) + " [" + str(agi_remaining) + "s]")
            agiBuffBar.SetText(agi_bar)
        elif agi_active:
            # Stats show buffed but timer expired - show as active but unknown time
            agiPotionLabel.SetText("Agi: " + str(agi_count) + " [ACTIVE]")
            agiBuffBar.SetText("[==========]")
        else:
            agiPotionLabel.SetText("Agi: " + str(agi_count))
            agiBuffBar.SetText("[----------]")

        # Bandage count
        bandageLabel.SetText("Bandages: " + str(get_item_count(BANDAGE)))

        # Heal state
        if HEAL_STATE == "healing":
            healStateLabel.SetText("Healing...")
        else:
            healStateLabel.SetText("Idle")

        # Cooldown timer
        if not potion_ready():
            remaining = int(potion_cooldown_end - time.time())
            cooldownLabel.SetText("Potion CD: " + str(remaining) + "s")
        else:
            cooldownLabel.SetText("Ready")

        # Threshold displays
        healThresholdLabel.SetText("Heal: " + str(heal_threshold) + "%")
        criticalThresholdLabel.SetText("Critical: " + str(critical_threshold) + "%")
        stamThresholdLabel.SetText("Stam: " + str(stamina_threshold) + "%")

        # Targeting buttons
        redsBtn.SetText("[REDS:" + ("ON" if target_reds else "OFF") + "]")
        redsBtn.SetBackgroundHue(68 if target_reds else 90)
        graysBtn.SetText("[GRAYS:" + ("ON" if target_grays else "OFF") + "]")
        graysBtn.SetBackgroundHue(68 if target_grays else 90)

        # Trapped pouch button - change background hue if configured
        if trapped_pouch_serial > 0:
            setPouchBtn.SetBackgroundHue(68)  # Green if configured
        else:
            setPouchBtn.SetBackgroundHue(43)  # Yellow if not configured

    except Exception as e:
        debug_msg("Display update error: " + str(e))

# ============ CLEANUP ============
def cleanup():
    """Cleanup on exit"""
    # Close config window if open
    if config_gump is not None:
        close_config_gump()

    # Unregister hotkeys using API.UnregisterHotkey (FIXED)
    try:
        if HOTKEY_HEAL_POTION:
            API.UnregisterHotkey(HOTKEY_HEAL_POTION)
    except Exception:
        pass

    try:
        if HOTKEY_CURE_POTION:
            API.UnregisterHotkey(HOTKEY_CURE_POTION)
    except Exception:
        pass

    try:
        if HOTKEY_REFRESH_POTION:
            API.UnregisterHotkey(HOTKEY_REFRESH_POTION)
    except Exception:
        pass

    try:
        if HOTKEY_BANDAGE:
            API.UnregisterHotkey(HOTKEY_BANDAGE)
    except Exception:
        pass

    try:
        if HOTKEY_EXPLO_POTION:
            API.UnregisterHotkey(HOTKEY_EXPLO_POTION)
    except Exception:
        pass

    try:
        if HOTKEY_PAUSE:
            API.UnregisterHotkey(HOTKEY_PAUSE)
    except Exception:
        pass

    try:
        if HOTKEY_ATTACK:
            API.UnregisterHotkey(HOTKEY_ATTACK)
    except Exception:
        pass

def onClosed():
    cleanup()
    pos_tracker.save()
    API.Stop()

# ============ INITIALIZATION ============
load_settings()

# ============ BUILD GUI ============
gump = API.Gumps.CreateGump()
API.Gumps.AddControlOnDisposed(gump, onClosed)

# Setup window position tracker (using LegionUtils)
pos_tracker = WindowPositionTracker(gump, SETTINGS_KEY, 100, 100)

# Load expanded state
is_expanded = load_bool(EXPANDED_KEY, True)

# Set initial position and height
initial_height = EXPANDED_HEIGHT if is_expanded else COLLAPSED_HEIGHT
gump.SetRect(pos_tracker.last_x, pos_tracker.last_y, WINDOW_WIDTH, initial_height)

bg = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
bg.SetRect(0, 0, WINDOW_WIDTH, initial_height)
gump.Add(bg)

title = API.Gumps.CreateGumpTTFLabel("Dexer Suite v1.6", 16, "#ff8800", aligned="center", maxWidth=280)
title.SetPos(0, 5)
gump.Add(title)

# Create expand/collapse button FIRST
expandBtn = API.Gumps.CreateSimpleButton("[-]" if is_expanded else "[+]", 20, 18)
expandBtn.SetPos(255, 3)
expandBtn.SetBackgroundHue(90)
gump.Add(expandBtn)

# NOW setup expandable window with the button (using LegionUtils)
expander = ExpandableWindow(
    gump, expandBtn, EXPANDED_KEY,
    width=WINDOW_WIDTH,
    expanded_height=EXPANDED_HEIGHT,
    collapsed_height=COLLAPSED_HEIGHT
)

# Wire button to expander
API.Gumps.AddControlOnClick(expandBtn, expander.toggle)

y = 30

# ========== TOP SECTION - RESOURCE BARS ==========
resourceTitle = API.Gumps.CreateGumpTTFLabel("=== STATUS ===", 15, "#00ffaa", aligned="center", maxWidth=280)
resourceTitle.SetPos(0, y)
gump.Add(resourceTitle)
expander.add_control(resourceTitle)

y += 16

# HP
hpLabel = API.Gumps.CreateGumpTTFLabel("HP: 0/0 (0%)", 15, "#00ff00")
hpLabel.SetPos(10, y)
gump.Add(hpLabel)
expander.add_control(hpLabel)

hpBar = API.Gumps.CreateGumpTTFLabel("[------------]", 15, "#00ff00")
hpBar.SetPos(170, y)
gump.Add(hpBar)
expander.add_control(hpBar)

y += 14

# Stamina
stamLabel = API.Gumps.CreateGumpTTFLabel("Stam: 0/0 (0%)", 15, "#00ffff")
stamLabel.SetPos(10, y)
gump.Add(stamLabel)
expander.add_control(stamLabel)

stamBar = API.Gumps.CreateGumpTTFLabel("[------------]", 15, "#00ffff")
stamBar.SetPos(170, y)
gump.Add(stamBar)
expander.add_control(stamBar)

y += 14

# Mana
manaLabel = API.Gumps.CreateGumpTTFLabel("Mana: 0/0 (0%)", 15, "#8888ff")
manaLabel.SetPos(10, y)
gump.Add(manaLabel)
expander.add_control(manaLabel)

manaBar = API.Gumps.CreateGumpTTFLabel("[------------]", 15, "#8888ff")
manaBar.SetPos(170, y)
gump.Add(manaBar)
expander.add_control(manaBar)

y += 14

# Poison status
poisonTitleLabel = API.Gumps.CreateGumpTTFLabel("Poison:", 15, "#ffffff")
poisonTitleLabel.SetPos(10, y)
gump.Add(poisonTitleLabel)
expander.add_control(poisonTitleLabel)

poisonLabel = API.Gumps.CreateGumpTTFLabel("Clear", 15, "#00ff00")
poisonLabel.SetPos(60, y)
gump.Add(poisonLabel)
expander.add_control(poisonLabel)

y += 20

# ========== MIDDLE SECTION - POTIONS ==========
middleTitle = API.Gumps.CreateGumpTTFLabel("=== POTIONS ===", 15, "#ff8800", aligned="center", maxWidth=280)
middleTitle.SetPos(0, y)
gump.Add(middleTitle)
expander.add_control(middleTitle)

y += 16
leftX = 10

# Heal Potion
healPotionLabel = API.Gumps.CreateGumpTTFLabel("Heal: 0", 15, "#ffaa00")
healPotionLabel.SetPos(leftX, y)
gump.Add(healPotionLabel)
expander.add_control(healPotionLabel)

drinkHealBtn = API.Gumps.CreateSimpleButton("[DRINK]", 60, 18)
drinkHealBtn.SetPos(leftX + 90, y - 2)
drinkHealBtn.SetBackgroundHue(68)
API.Gumps.AddControlOnClick(drinkHealBtn, on_drink_heal)
gump.Add(drinkHealBtn)
expander.add_control(drinkHealBtn)

y += 20

# Cure Potion
curePotionLabel = API.Gumps.CreateGumpTTFLabel("Cure: 0", 15, "#ffff00")
curePotionLabel.SetPos(leftX, y)
gump.Add(curePotionLabel)
expander.add_control(curePotionLabel)

drinkCureBtn = API.Gumps.CreateSimpleButton("[DRINK]", 60, 18)
drinkCureBtn.SetPos(leftX + 90, y - 2)
drinkCureBtn.SetBackgroundHue(68)
API.Gumps.AddControlOnClick(drinkCureBtn, on_drink_cure)
gump.Add(drinkCureBtn)
expander.add_control(drinkCureBtn)

y += 20

# Refresh Potion
refreshPotionLabel = API.Gumps.CreateGumpTTFLabel("Refresh: 0", 15, "#ff0000")
refreshPotionLabel.SetPos(leftX, y)
gump.Add(refreshPotionLabel)
expander.add_control(refreshPotionLabel)

drinkRefreshBtn = API.Gumps.CreateSimpleButton("[DRINK]", 60, 18)
drinkRefreshBtn.SetPos(leftX + 90, y - 2)
drinkRefreshBtn.SetBackgroundHue(68)
API.Gumps.AddControlOnClick(drinkRefreshBtn, on_drink_refresh)
gump.Add(drinkRefreshBtn)
expander.add_control(drinkRefreshBtn)

y += 20

# Explosion Potion
exploPotionLabel = API.Gumps.CreateGumpTTFLabel("Explo: L0/N0/G0", 15, "#ff00ff")
exploPotionLabel.SetPos(leftX, y)
gump.Add(exploPotionLabel)
expander.add_control(exploPotionLabel)

throwExploBtn = API.Gumps.CreateSimpleButton("[THROW]", 60, 18)
throwExploBtn.SetPos(leftX + 120, y - 2)
throwExploBtn.SetBackgroundHue(32)
API.Gumps.AddControlOnClick(throwExploBtn, on_throw_explo)
gump.Add(throwExploBtn)
expander.add_control(throwExploBtn)

y += 20

# Strength potion with buff bar
strPotionLabel = API.Gumps.CreateGumpTTFLabel("Str: 0", 15, "#aaaaaa")
strPotionLabel.SetPos(leftX, y)
gump.Add(strPotionLabel)
expander.add_control(strPotionLabel)

# Agility potion (display only)
agiPotionLabel = API.Gumps.CreateGumpTTFLabel("Agi: 0", 15, "#aaaaaa")
agiPotionLabel.SetPos(leftX + 90, y)
gump.Add(agiPotionLabel)
expander.add_control(agiPotionLabel)

y += 14

# STR Buff Bar
strBuffBar = API.Gumps.CreateGumpTTFLabel("[----------]", 15, "#555555")
strBuffBar.SetPos(leftX, y)
gump.Add(strBuffBar)
expander.add_control(strBuffBar)

# AGI Buff Bar
agiBuffBar = API.Gumps.CreateGumpTTFLabel("[----------]", 15, "#555555")
agiBuffBar.SetPos(leftX + 90, y)
gump.Add(agiBuffBar)
expander.add_control(agiBuffBar)

y += 20

# ========== BOTTOM SECTION - HEALING + SETTINGS ==========
healingTitle = API.Gumps.CreateGumpTTFLabel("=== HEALING ===", 15, "#00ff00", aligned="center", maxWidth=280)
healingTitle.SetPos(0, y)
gump.Add(healingTitle)
expander.add_control(healingTitle)

y += 16

# Bandage
bandageLabel = API.Gumps.CreateGumpTTFLabel("Bandages: 0", 15, "#ffffff")
bandageLabel.SetPos(leftX, y)
gump.Add(bandageLabel)
expander.add_control(bandageLabel)

bandageBtn = API.Gumps.CreateSimpleButton("[BANDAGE]", 70, 18)
bandageBtn.SetPos(leftX + 80, y - 2)
bandageBtn.SetBackgroundHue(68)
API.Gumps.AddControlOnClick(bandageBtn, on_bandage_button)
gump.Add(bandageBtn)
expander.add_control(bandageBtn)

autoHealBtn = API.Gumps.CreateSimpleButton("[AUTO-BAND:" + ("ON" if auto_heal else "OFF") + "]", 110, 18)
autoHealBtn.SetPos(leftX + 155, y - 2)
autoHealBtn.SetBackgroundHue(68 if auto_heal else 90)
API.Gumps.AddControlOnClick(autoHealBtn, toggle_auto_heal)
gump.Add(autoHealBtn)
expander.add_control(autoHealBtn)

y += 20

# Heal state
healStateLabel = API.Gumps.CreateGumpTTFLabel("Idle", 15, "#00ff00")
healStateLabel.SetPos(leftX, y)
gump.Add(healStateLabel)
expander.add_control(healStateLabel)

y += 20

# Thresholds
healThresholdLabel = API.Gumps.CreateGumpTTFLabel("Heal: " + str(heal_threshold) + "%", 15, "#ffaa00")
healThresholdLabel.SetPos(leftX, y)
gump.Add(healThresholdLabel)
expander.add_control(healThresholdLabel)

criticalThresholdLabel = API.Gumps.CreateGumpTTFLabel("Critical: " + str(critical_threshold) + "%", 15, "#ff0000")
criticalThresholdLabel.SetPos(leftX + 100, y)
gump.Add(criticalThresholdLabel)
expander.add_control(criticalThresholdLabel)

y += 14

stamThresholdLabel = API.Gumps.CreateGumpTTFLabel("Stam: " + str(stamina_threshold) + "%", 15, "#00ffff")
stamThresholdLabel.SetPos(leftX, y)
gump.Add(stamThresholdLabel)
expander.add_control(stamThresholdLabel)

y += 20

# ========== TARGETING SECTION ==========
targetingTitle = API.Gumps.CreateGumpTTFLabel("=== TARGETING ===", 15, "#ff6666", aligned="center", maxWidth=280)
targetingTitle.SetPos(0, y)
gump.Add(targetingTitle)
expander.add_control(targetingTitle)

y += 16

redsBtn = API.Gumps.CreateSimpleButton("[REDS:" + ("ON" if target_reds else "OFF") + "]", 80, 18)
redsBtn.SetPos(leftX, y)
redsBtn.SetBackgroundHue(68 if target_reds else 90)
API.Gumps.AddControlOnClick(redsBtn, toggle_target_reds)
gump.Add(redsBtn)
expander.add_control(redsBtn)

graysBtn = API.Gumps.CreateSimpleButton("[GRAYS:" + ("ON" if target_grays else "OFF") + "]", 80, 18)
graysBtn.SetPos(leftX + 90, y)
graysBtn.SetBackgroundHue(68 if target_grays else 90)
API.Gumps.AddControlOnClick(graysBtn, toggle_target_grays)
gump.Add(graysBtn)
expander.add_control(graysBtn)

y += 22

# Auto-Target Toggle
autoTargetBtn = API.Gumps.CreateSimpleButton("[AUTO-TARGET:" + ("ON" if auto_target else "OFF") + "]", 180, 18)
autoTargetBtn.SetPos(leftX, y)
autoTargetBtn.SetBackgroundHue(68 if auto_target else 90)
API.Gumps.AddControlOnClick(autoTargetBtn, toggle_auto_target)
gump.Add(autoTargetBtn)
expander.add_control(autoTargetBtn)

y += 22

# Auto-Explo Toggle
autoExploBtn = API.Gumps.CreateSimpleButton("[AUTO-EXPLO:" + ("ON" if auto_explo else "OFF") + "]", 180, 18)
autoExploBtn.SetPos(leftX, y)
autoExploBtn.SetBackgroundHue(68 if auto_explo else 90)
API.Gumps.AddControlOnClick(autoExploBtn, toggle_auto_explo)
gump.Add(autoExploBtn)
expander.add_control(autoExploBtn)

y += 24

# ========== UTILITIES SECTION ==========
utilTitle = API.Gumps.CreateGumpTTFLabel("=== UTILITIES ===", 15, "#00aaff", aligned="center", maxWidth=280)
utilTitle.SetPos(0, y)
gump.Add(utilTitle)
expander.add_control(utilTitle)

y += 16

# Auto-Buff Toggle
autoBuffBtn = API.Gumps.CreateSimpleButton("[AUTO-BUFF:" + ("ON" if auto_buff else "OFF") + "]", 130, 18)
autoBuffBtn.SetPos(leftX, y)
autoBuffBtn.SetBackgroundHue(68 if auto_buff else 90)
API.Gumps.AddControlOnClick(autoBuffBtn, toggle_auto_buff)
gump.Add(autoBuffBtn)
expander.add_control(autoBuffBtn)

y += 22

# Config Button
configBtn = API.Gumps.CreateSimpleButton("[CONFIG]", 90, 18)
configBtn.SetPos(leftX, y)
configBtn.SetBackgroundHue(43)
API.Gumps.AddControlOnClick(configBtn, build_config_gump)
gump.Add(configBtn)
expander.add_control(configBtn)

y += 22

# Trapped Pouch Controls
setPouchBtn = API.Gumps.CreateSimpleButton("[SET POUCH]", 90, 18)
setPouchBtn.SetPos(leftX, y)
setPouchBtn.SetBackgroundHue(43)
API.Gumps.AddControlOnClick(setPouchBtn, on_set_trapped_pouch)
gump.Add(setPouchBtn)
expander.add_control(setPouchBtn)

usePouchBtn = API.Gumps.CreateSimpleButton("[USE POUCH:" + ("ON" if use_trapped_pouch else "OFF") + "]", 130, 18)
usePouchBtn.SetPos(leftX + 95, y)
usePouchBtn.SetBackgroundHue(68 if use_trapped_pouch else 90)
API.Gumps.AddControlOnClick(usePouchBtn, toggle_use_trapped_pouch)
gump.Add(usePouchBtn)
expander.add_control(usePouchBtn)

y += 24

# ========== FOOTER - PAUSE + COOLDOWN ==========
footerTitle = API.Gumps.CreateGumpTTFLabel("=== CONTROL ===", 15, "#ff6666", aligned="center", maxWidth=280)
footerTitle.SetPos(0, y)
gump.Add(footerTitle)
expander.add_control(footerTitle)

y += 16

pauseBtn = API.Gumps.CreateSimpleButton("[PAUSE]", 90, 22)
pauseBtn.SetPos(10, y)
pauseBtn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(pauseBtn, toggle_pause)
gump.Add(pauseBtn)
expander.add_control(pauseBtn)

statusLabel = API.Gumps.CreateGumpTTFLabel("Running", 15, "#00ff00")
statusLabel.SetPos(110, y + 4)
gump.Add(statusLabel)
expander.add_control(statusLabel)

cooldownLabel = API.Gumps.CreateGumpTTFLabel("Ready", 15, "#00ff00")
cooldownLabel.SetPos(250, y + 4)
gump.Add(cooldownLabel)
expander.add_control(cooldownLabel)

y += 28

# ========== HOTKEYS DISPLAY ==========
hotkeyTitle = API.Gumps.CreateGumpTTFLabel("=== HOTKEYS ===", 15, "#ffff00", aligned="center", maxWidth=280)
hotkeyTitle.SetPos(0, y)
gump.Add(hotkeyTitle)
expander.add_control(hotkeyTitle)

y += 16

# Row 1 - Potions & Attack
hotkeyRow1 = API.Gumps.CreateGumpTTFLabel("Heal:" + HOTKEY_HEAL_POTION + " | Cure:" + HOTKEY_CURE_POTION + " | Refresh:" + HOTKEY_REFRESH_POTION, 15, "#aaaaaa")
hotkeyRow1.SetPos(leftX, y)
gump.Add(hotkeyRow1)
expander.add_control(hotkeyRow1)

y += 14

# Row 2 - Bandage, Pause, Attack
hotkeyRow2 = API.Gumps.CreateGumpTTFLabel("Bandage:" + HOTKEY_BANDAGE + " | Attack:" + HOTKEY_ATTACK + " | Pause:" + HOTKEY_PAUSE, 15, "#aaaaaa")
hotkeyRow2.SetPos(leftX, y)
gump.Add(hotkeyRow2)
expander.add_control(hotkeyRow2)

API.Gumps.AddGump(gump)

# Apply initial expanded/collapsed state
expander.update_state(animate=False)

# ============ REGISTER HOTKEYS ============
if HOTKEY_HEAL_POTION:
    API.OnHotKey(HOTKEY_HEAL_POTION, on_heal_potion_hotkey)
if HOTKEY_CURE_POTION:
    API.OnHotKey(HOTKEY_CURE_POTION, on_cure_potion_hotkey)
if HOTKEY_REFRESH_POTION:
    API.OnHotKey(HOTKEY_REFRESH_POTION, on_refresh_potion_hotkey)
if HOTKEY_BANDAGE:
    API.OnHotKey(HOTKEY_BANDAGE, on_bandage_hotkey)
if HOTKEY_EXPLO_POTION:
    API.OnHotKey(HOTKEY_EXPLO_POTION, on_explo_potion_hotkey)
if HOTKEY_PAUSE:
    API.OnHotKey(HOTKEY_PAUSE, on_pause_hotkey)
if HOTKEY_ATTACK:
    API.OnHotKey(HOTKEY_ATTACK, on_attack_hotkey)

# Initial display update
update_display()

API.SysMsg("Dexer Suite v1.6 loaded!", 68)
API.SysMsg("Base Stats: STR=" + str(base_str) + " DEX=" + str(base_dex), 53)

# Show current stats for comparison
try:
    current_str = API.Player.Str
    current_dex = getattr(API.Player, 'Dex', getattr(API.Player, 'Dexterity', 0))
    API.SysMsg("Current Stats: STR=" + str(current_str) + " DEX=" + str(current_dex), 53)
    if current_str >= base_str + 15:
        API.SysMsg("STR buff detected!", 68)
    if current_dex >= base_dex + 15:
        API.SysMsg("AGI buff detected!", 68)
except:
    pass

API.SysMsg("Hotkeys: Heal=" + HOTKEY_HEAL_POTION + " Cure=" + HOTKEY_CURE_POTION + " Refresh=" + HOTKEY_REFRESH_POTION, 53)
API.SysMsg("Bandage=" + HOTKEY_BANDAGE + " Explo=" + HOTKEY_EXPLO_POTION + " Attack=" + HOTKEY_ATTACK + " Pause=" + HOTKEY_PAUSE, 53)

# ============ MAIN LOOP (NON-BLOCKING) ============
while not API.StopRequested:
    try:
        # CRITICAL: Process GUI clicks and hotkeys - always instant!
        API.ProcessCallbacks()

        # Check if bandage is complete
        check_heal_complete()

        # Update window position tracker
        pos_tracker.update()

        # Track config window position if open
        if config_gump is not None and config_pos_tracker:
            config_pos_tracker.update()

        # Update display periodically
        if time.time() > next_display_update:
            update_display()
            next_display_update = time.time() + DISPLAY_UPDATE_INTERVAL

        # HEALER LOGIC (non-blocking)
        if not PAUSED and HEAL_STATE == "idle":
            action = get_priority_action()
            if action:
                execute_action(action)

        # AUTO-TARGET LOGIC (continuous combat when enabled)
        if not PAUSED:
            handle_auto_target()

        # AUTO-EXPLO LOGIC (throw explosion potions at target with retry backoff)
        if not PAUSED and auto_explo and potion_ready():
            if time.time() - last_explo_attempt > EXPLO_RETRY_DELAY:
                if current_attack_target != 0:
                    target = API.FindMobile(current_attack_target)
                    if target and not target.IsDead and getattr(target, 'Distance', 999) <= 12:
                        if throw_explosion_potion(current_attack_target):
                            last_explo_attempt = time.time()

        # Short pause - loop runs ~10x/second
        API.Pause(0.1)

    except Exception as e:
        API.SysMsg("Error: " + str(e), 32)
        API.Pause(1)

cleanup()
