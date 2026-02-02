# ============================================================

# Dexer Suite v1.0

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

#   - Default thresholds: Bandage <100% HP, Potions <50% HP

#

# NO CHIVALRY - designed for UOR-based server

#

# ============================================================

import API

import time



__version__ = "1.0"



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

AUTO_TARGET_RANGE = 3         # Range for auto-targeting next enemy when current dies

TARGET_TIMEOUT = 2.0          # Timeout for target cursor



# === POTION GRAPHICS ===

POTION_HEAL = 0x0F0C          # Greater Heal (orange)

POTION_CURE = 0x0F07          # Greater Cure (yellow)

POTION_REFRESH = 0x0F0B       # Greater Refresh (red)

POTION_STRENGTH = 0x0F09      # Greater Strength (white)

POTION_AGILITY = 0x0F08       # Greater Agility (blue)

POTION_EXPLOSION = 0x0F0D     # Explosion (purple)

BANDAGE = 0x0E21              # Bandages



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

TARGET_REDS_KEY = "DexerSuite_TargetReds"

TARGET_GRAYS_KEY = "DexerSuite_TargetGrays"

BASE_STR_KEY = "DexerSuite_BaseStr"

BASE_DEX_KEY = "DexerSuite_BaseDex"

TRAPPED_POUCH_SERIAL_KEY = "DexerSuite_TrappedPouch"

USE_TRAPPED_POUCH_KEY = "DexerSuite_UseTrappedPouch"



# Hotkey keys

HOTKEY_HEAL_POTION_KEY = "DexerSuite_HK_HealPotion"

HOTKEY_CURE_POTION_KEY = "DexerSuite_HK_CurePotion"

HOTKEY_REFRESH_POTION_KEY = "DexerSuite_HK_RefreshPotion"

HOTKEY_BANDAGE_KEY = "DexerSuite_HK_Bandage"

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



# Hotkeys

HOTKEY_HEAL_POTION = "F1"

HOTKEY_CURE_POTION = "F2"

HOTKEY_REFRESH_POTION = "F3"

HOTKEY_BANDAGE = "F6"

HOTKEY_PAUSE = "PAUSE"

HOTKEY_ATTACK = "TAB"  # TAB works, backtick (`) doesn't register



# Control

PAUSED = False

next_display_update = 0

hotkeys_registered = False



# ============ UTILITY FUNCTIONS ============

def debug_msg(text):

    if DEBUG:

        API.SysMsg("DEBUG: " + text, 88)



def is_player_poisoned():

    try:

        player = API.Player

        if hasattr(player, 'Poisoned') and player.Poisoned:

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



def get_hp_percent():

    try:

        player = API.Player

        if player.HitsMax > 0:

            return int((player.Hits / player.HitsMax) * 100)

        return 100

    except:

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

    except:

        return 100



def get_stam_values():

    """Get current stam and max stam values"""

    try:

        player = API.Player

        stam = getattr(player, 'Stam', getattr(player, 'Stamina', 0))

        stam_max = getattr(player, 'StamMax', getattr(player, 'StaminaMax', 0))

        return (stam, stam_max)

    except:

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

    except:

        return 100



def get_mana_values():

    """Get current mana and max mana values"""

    try:

        player = API.Player

        mana = getattr(player, 'Mana', 0)

        mana_max = getattr(player, 'ManaMax', 0)

        return (mana, mana_max)

    except:

        return (0, 0)



def get_player_hits_diff():

    try:

        player = API.Player

        return player.HitsMax - player.Hits

    except:

        return 0



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

    except Exception as e:

        return 0



def get_bandage_count():

    """Count total bandages in backpack"""

    try:

        backpack = API.Player.Backpack

        if not backpack or not hasattr(backpack, 'Serial'):

            return 0



        # Get all items in backpack recursively

        items = API.ItemsInContainer(backpack.Serial, True)

        if not items:

            return 0



        # Count all bandages

        total = 0

        for item in items:

            if hasattr(item, 'Graphic') and item.Graphic == BANDAGE:

                if hasattr(item, 'Amount'):

                    total += item.Amount

                else:

                    total += 1



        return total

    except:

        return 0



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

    if API.HasTarget():

        API.CancelTarget()

    API.CancelPreTarget()



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



        clear_stray_cursor()

    except Exception as e:

        API.SysMsg("Target error: " + str(e), 32)

        clear_stray_cursor()



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

        clear_stray_cursor()



        HEAL_STATE = "healing"

        heal_start_time = time.time()

        statusLabel.SetText("Bandaging...")



        # Create cooldown bar

        try:

            API.CreateCooldownBar(BANDAGE_DELAY, "Bandaging...", 68)

        except:

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

        except:

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

    except:

        return False



def is_agi_buffed():

    """Check if AGI buff is currently active by reading stats (DEX)"""

    try:

        current_dex = getattr(API.Player, 'Dex', getattr(API.Player, 'Dexterity', 0))

        # Consider buffed if current DEX is at least 15 above base (accounts for variance)

        return current_dex >= base_dex + 15

    except:

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

        if potion_ready() and get_potion_count(POTION_CURE) > 0:

            return ("cure_potion", None)



    # CRITICAL: Low HP -> Heal potion (ALWAYS)

    if hp_pct < critical_threshold:

        if potion_ready() and get_potion_count(POTION_HEAL) > 0:

            return ("heal_potion", None)



    # CURE: Poisoned -> Cure potion (ALWAYS)

    if poisoned:

        if potion_ready() and get_potion_count(POTION_CURE) > 0:

            return ("cure_potion", None)



    # HEAL POTION: HP below potion threshold (ALWAYS)

    if hp_pct < heal_threshold:

        if potion_ready() and get_potion_count(POTION_HEAL) > 0:

            return ("heal_potion", None)



    # BANDAGE: Any HP loss (ONLY if auto_heal enabled)

    if auto_heal and HEAL_STATE == "idle" and hits_diff >= bandage_diff_threshold:

        return ("bandage", None)



    # STAMINA: Below threshold (ALWAYS)

    if stam_pct < stamina_threshold:

        if potion_ready() and get_potion_count(POTION_REFRESH) > 0:

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

                if get_potion_count(POTION_AGILITY) > 0:

                    return ("agi_potion", None)

                elif get_potion_count(POTION_STRENGTH) > 0:

                    return ("str_potion", None)

            else:

                # Last buff was AGI (or first time), now do STR

                if get_potion_count(POTION_STRENGTH) > 0:

                    return ("str_potion", None)

                elif get_potion_count(POTION_AGILITY) > 0:

                    return ("agi_potion", None)

        # Only one needs buffing

        elif str_needs_buff:

            if get_potion_count(POTION_STRENGTH) > 0:

                return ("str_potion", None)

        elif agi_needs_buff:

            if get_potion_count(POTION_AGILITY) > 0:

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



# ============ ATTACK/TARGETING ============

def get_mob_name(mob, default="Unknown"):

    """Get mobile name safely"""

    if not mob:

        return default

    try:

        return mob.Name if mob.Name else default

    except:

        return default



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

    target_distance = target.Distance if target and hasattr(target, 'Distance') else 999

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



def on_pause_hotkey():

    toggle_pause()



def on_attack_hotkey():

    attack_nearest()



# ============ PERSISTENCE ============

def load_settings():

    global heal_threshold, critical_threshold, stamina_threshold, bandage_diff_threshold

    global auto_heal, auto_buff, auto_target, target_reds, target_grays

    global HOTKEY_HEAL_POTION, HOTKEY_CURE_POTION, HOTKEY_REFRESH_POTION

    global HOTKEY_BANDAGE, HOTKEY_PAUSE, HOTKEY_ATTACK

    global base_str, base_dex

    global trapped_pouch_serial, use_trapped_pouch



    # Thresholds

    try:

        heal_threshold = int(API.GetPersistentVar(HEAL_THRESHOLD_KEY, str(DEFAULT_HEAL_THRESHOLD), API.PersistentVar.Char))

    except:

        heal_threshold = DEFAULT_HEAL_THRESHOLD



    try:

        critical_threshold = int(API.GetPersistentVar(CRITICAL_THRESHOLD_KEY, str(DEFAULT_CRITICAL_THRESHOLD), API.PersistentVar.Char))

    except:

        critical_threshold = DEFAULT_CRITICAL_THRESHOLD



    try:

        stamina_threshold = int(API.GetPersistentVar(STAMINA_THRESHOLD_KEY, str(DEFAULT_STAMINA_THRESHOLD), API.PersistentVar.Char))

    except:

        stamina_threshold = DEFAULT_STAMINA_THRESHOLD



    try:

        bandage_diff_threshold = int(API.GetPersistentVar(BANDAGE_DIFF_KEY, str(DEFAULT_BANDAGE_DIFF), API.PersistentVar.Char))

    except:

        bandage_diff_threshold = DEFAULT_BANDAGE_DIFF



    # Toggles

    auto_heal = API.GetPersistentVar(AUTO_HEAL_KEY, "True", API.PersistentVar.Char) == "True"

    auto_buff = API.GetPersistentVar(AUTO_BUFF_KEY, "True", API.PersistentVar.Char) == "True"

    auto_target = API.GetPersistentVar(AUTO_TARGET_KEY, "False", API.PersistentVar.Char) == "True"

    target_reds = API.GetPersistentVar(TARGET_REDS_KEY, "True", API.PersistentVar.Char) == "True"

    target_grays = API.GetPersistentVar(TARGET_GRAYS_KEY, "True", API.PersistentVar.Char) == "True"

    use_trapped_pouch = API.GetPersistentVar(USE_TRAPPED_POUCH_KEY, "True", API.PersistentVar.Char) == "True"



    # Trapped pouch

    try:

        trapped_pouch_serial = int(API.GetPersistentVar(TRAPPED_POUCH_SERIAL_KEY, "0", API.PersistentVar.Char))

    except:

        trapped_pouch_serial = 0



    # Base stats (load or detect from current stats)

    try:

        base_str = int(API.GetPersistentVar(BASE_STR_KEY, "0", API.PersistentVar.Char))

        if base_str == 0:

            # First run - try to read current stats as base

            base_str = API.Player.Str

            API.SavePersistentVar(BASE_STR_KEY, str(base_str), API.PersistentVar.Char)

    except:

        base_str = 100  # Fallback default



    try:

        base_dex = int(API.GetPersistentVar(BASE_DEX_KEY, "0", API.PersistentVar.Char))

        if base_dex == 0:

            # First run - try to read current stats as base

            base_dex = getattr(API.Player, 'Dex', getattr(API.Player, 'Dexterity', 100))

            API.SavePersistentVar(BASE_DEX_KEY, str(base_dex), API.PersistentVar.Char)

    except:

        base_dex = 100  # Fallback default



    # Hotkeys

    HOTKEY_HEAL_POTION = API.GetPersistentVar(HOTKEY_HEAL_POTION_KEY, "F1", API.PersistentVar.Char)

    HOTKEY_CURE_POTION = API.GetPersistentVar(HOTKEY_CURE_POTION_KEY, "F2", API.PersistentVar.Char)

    HOTKEY_REFRESH_POTION = API.GetPersistentVar(HOTKEY_REFRESH_POTION_KEY, "F3", API.PersistentVar.Char)

    HOTKEY_BANDAGE = API.GetPersistentVar(HOTKEY_BANDAGE_KEY, "F6", API.PersistentVar.Char)

    HOTKEY_PAUSE = API.GetPersistentVar(HOTKEY_PAUSE_KEY, "PAUSE", API.PersistentVar.Char)

    HOTKEY_ATTACK = API.GetPersistentVar(HOTKEY_ATTACK_KEY, "TAB", API.PersistentVar.Char)



def save_threshold(key, value):

    API.SavePersistentVar(key, str(value), API.PersistentVar.Char)



# ============ DISPLAY UPDATES ============

def create_resource_bar(current, max_val, width=10):

    """Generate ASCII bar like [====----]"""

    if max_val <= 0:

        return "[" + "-" * width + "]"



    pct = current / max_val

    filled = int(pct * width)

    empty = width - filled

    return "[" + "=" * filled + "-" * empty + "]"



def get_color_for_hp(pct):

    """Get color hue based on HP percentage"""

    if pct >= 70:

        return "#00ff00"  # Green

    elif pct >= 30:

        return "#ffff00"  # Yellow

    else:

        return "#ff0000"  # Red



def get_color_for_stam(pct):

    """Get color for stamina"""

    if pct >= 50:

        return "#00ffff"  # Cyan

    else:

        return "#ffff00"  # Yellow



def get_color_for_mana(pct):

    """Get color for mana"""

    if pct >= 50:

        return "#8888ff"  # Blue

    else:

        return "#ff88ff"  # Purple



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

        healPotionLabel.SetText("Heal: " + str(get_potion_count(POTION_HEAL)))

        curePotionLabel.SetText("Cure: " + str(get_potion_count(POTION_CURE)))

        refreshPotionLabel.SetText("Refresh: " + str(get_potion_count(POTION_REFRESH)))



        # Buff potions with timer display and progress bars

        str_count = get_potion_count(POTION_STRENGTH)

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



        agi_count = get_potion_count(POTION_AGILITY)

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

        bandageLabel.SetText("Bandages: " + str(get_bandage_count()))



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

def unregister_hotkeys():

    """Unregister all hotkeys"""

    global hotkeys_registered



    if not hotkeys_registered:

        return



    try:

        if HOTKEY_HEAL_POTION:

            API.OnHotKey(HOTKEY_HEAL_POTION)

    except:

        pass



    try:

        if HOTKEY_CURE_POTION:

            API.OnHotKey(HOTKEY_CURE_POTION)

    except:

        pass



    try:

        if HOTKEY_REFRESH_POTION:

            API.OnHotKey(HOTKEY_REFRESH_POTION)

    except:

        pass



    try:

        if HOTKEY_BANDAGE:

            API.OnHotKey(HOTKEY_BANDAGE)

    except:

        pass



    try:

        if HOTKEY_PAUSE:

            API.OnHotKey(HOTKEY_PAUSE)

    except:

        pass



    hotkeys_registered = False



def cleanup():

    unregister_hotkeys()



def onClosed():

    cleanup()

    API.SavePersistentVar(SETTINGS_KEY, str(gump.GetX()) + "," + str(gump.GetY()), API.PersistentVar.Char)

    API.Stop()



# ============ INITIALIZATION ============

load_settings()



# ============ BUILD GUI ============

gump = API.Gumps.CreateGump()

API.Gumps.AddControlOnDisposed(gump, onClosed)



savedPos = API.GetPersistentVar(SETTINGS_KEY, "100,100", API.PersistentVar.Char)

posXY = savedPos.split(',')

lastX = int(posXY[0])

lastY = int(posXY[1])

gump.SetRect(lastX, lastY, 280, 610)



bg = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")

bg.SetRect(0, 0, 280, 610)

gump.Add(bg)



title = API.Gumps.CreateGumpTTFLabel("Dexer Suite v1", 16, "#ff8800", aligned="center", maxWidth=280)

title.SetPos(0, 5)

gump.Add(title)



y = 30



# ========== TOP SECTION - RESOURCE BARS ==========

resourceTitle = API.Gumps.CreateGumpTTFLabel("=== STATUS ===", 9, "#00ffaa", aligned="center", maxWidth=280)

resourceTitle.SetPos(0, y)

gump.Add(resourceTitle)



y += 16



# HP

hpLabel = API.Gumps.CreateGumpTTFLabel("HP: 0/0 (0%)", 9, "#00ff00")

hpLabel.SetPos(10, y)

gump.Add(hpLabel)



hpBar = API.Gumps.CreateGumpTTFLabel("[------------]", 9, "#00ff00")

hpBar.SetPos(170, y)

gump.Add(hpBar)



y += 14



# Stamina

stamLabel = API.Gumps.CreateGumpTTFLabel("Stam: 0/0 (0%)", 9, "#00ffff")

stamLabel.SetPos(10, y)

gump.Add(stamLabel)



stamBar = API.Gumps.CreateGumpTTFLabel("[------------]", 9, "#00ffff")

stamBar.SetPos(170, y)

gump.Add(stamBar)



y += 14



# Mana

manaLabel = API.Gumps.CreateGumpTTFLabel("Mana: 0/0 (0%)", 9, "#8888ff")

manaLabel.SetPos(10, y)

gump.Add(manaLabel)



manaBar = API.Gumps.CreateGumpTTFLabel("[------------]", 9, "#8888ff")

manaBar.SetPos(170, y)

gump.Add(manaBar)



y += 14



# Poison status

poisonTitleLabel = API.Gumps.CreateGumpTTFLabel("Poison:", 9, "#ffffff")

poisonTitleLabel.SetPos(10, y)

gump.Add(poisonTitleLabel)



poisonLabel = API.Gumps.CreateGumpTTFLabel("Clear", 9, "#00ff00")

poisonLabel.SetPos(60, y)

gump.Add(poisonLabel)



y += 20



# ========== MIDDLE SECTION - POTIONS ==========

middleTitle = API.Gumps.CreateGumpTTFLabel("=== POTIONS ===", 9, "#ff8800", aligned="center", maxWidth=280)

middleTitle.SetPos(0, y)

gump.Add(middleTitle)



y += 16

leftX = 10



# Heal Potion

healPotionLabel = API.Gumps.CreateGumpTTFLabel("Heal: 0", 9, "#ffaa00")

healPotionLabel.SetPos(leftX, y)

gump.Add(healPotionLabel)



drinkHealBtn = API.Gumps.CreateSimpleButton("[DRINK]", 60, 18)

drinkHealBtn.SetPos(leftX + 90, y - 2)

drinkHealBtn.SetBackgroundHue(68)

API.Gumps.AddControlOnClick(drinkHealBtn, on_drink_heal)

gump.Add(drinkHealBtn)



y += 20



# Cure Potion

curePotionLabel = API.Gumps.CreateGumpTTFLabel("Cure: 0", 9, "#ffff00")

curePotionLabel.SetPos(leftX, y)

gump.Add(curePotionLabel)



drinkCureBtn = API.Gumps.CreateSimpleButton("[DRINK]", 60, 18)

drinkCureBtn.SetPos(leftX + 90, y - 2)

drinkCureBtn.SetBackgroundHue(68)

API.Gumps.AddControlOnClick(drinkCureBtn, on_drink_cure)

gump.Add(drinkCureBtn)



y += 20



# Refresh Potion

refreshPotionLabel = API.Gumps.CreateGumpTTFLabel("Refresh: 0", 9, "#ff0000")

refreshPotionLabel.SetPos(leftX, y)

gump.Add(refreshPotionLabel)



drinkRefreshBtn = API.Gumps.CreateSimpleButton("[DRINK]", 60, 18)

drinkRefreshBtn.SetPos(leftX + 90, y - 2)

drinkRefreshBtn.SetBackgroundHue(68)

API.Gumps.AddControlOnClick(drinkRefreshBtn, on_drink_refresh)

gump.Add(drinkRefreshBtn)



y += 20



# Strength potion with buff bar

strPotionLabel = API.Gumps.CreateGumpTTFLabel("Str: 0", 9, "#aaaaaa")

strPotionLabel.SetPos(leftX, y)

gump.Add(strPotionLabel)



# Agility potion (display only)

agiPotionLabel = API.Gumps.CreateGumpTTFLabel("Agi: 0", 9, "#aaaaaa")

agiPotionLabel.SetPos(leftX + 90, y)

gump.Add(agiPotionLabel)



y += 14



# STR Buff Bar

strBuffBar = API.Gumps.CreateGumpTTFLabel("[----------]", 9, "#555555")

strBuffBar.SetPos(leftX, y)

gump.Add(strBuffBar)



# AGI Buff Bar

agiBuffBar = API.Gumps.CreateGumpTTFLabel("[----------]", 9, "#555555")

agiBuffBar.SetPos(leftX + 90, y)

gump.Add(agiBuffBar)



y += 20



# ========== BOTTOM SECTION - HEALING + SETTINGS ==========

healingTitle = API.Gumps.CreateGumpTTFLabel("=== HEALING ===", 9, "#00ff00", aligned="center", maxWidth=280)

healingTitle.SetPos(0, y)

gump.Add(healingTitle)



y += 16



# Bandage

bandageLabel = API.Gumps.CreateGumpTTFLabel("Bandages: 0", 9, "#ffffff")

bandageLabel.SetPos(leftX, y)

gump.Add(bandageLabel)



bandageBtn = API.Gumps.CreateSimpleButton("[BANDAGE]", 70, 18)

bandageBtn.SetPos(leftX + 80, y - 2)

bandageBtn.SetBackgroundHue(68)

API.Gumps.AddControlOnClick(bandageBtn, on_bandage_button)

gump.Add(bandageBtn)



autoHealBtn = API.Gumps.CreateSimpleButton("[AUTO-BAND:" + ("ON" if auto_heal else "OFF") + "]", 110, 18)

autoHealBtn.SetPos(leftX + 155, y - 2)

autoHealBtn.SetBackgroundHue(68 if auto_heal else 90)

API.Gumps.AddControlOnClick(autoHealBtn, toggle_auto_heal)

gump.Add(autoHealBtn)



y += 20



# Heal state

healStateLabel = API.Gumps.CreateGumpTTFLabel("Idle", 9, "#00ff00")

healStateLabel.SetPos(leftX, y)

gump.Add(healStateLabel)



y += 20



# Thresholds

healThresholdLabel = API.Gumps.CreateGumpTTFLabel("Heal: " + str(heal_threshold) + "%", 9, "#ffaa00")

healThresholdLabel.SetPos(leftX, y)

gump.Add(healThresholdLabel)



criticalThresholdLabel = API.Gumps.CreateGumpTTFLabel("Critical: " + str(critical_threshold) + "%", 9, "#ff0000")

criticalThresholdLabel.SetPos(leftX + 100, y)

gump.Add(criticalThresholdLabel)



y += 14



stamThresholdLabel = API.Gumps.CreateGumpTTFLabel("Stam: " + str(stamina_threshold) + "%", 9, "#00ffff")

stamThresholdLabel.SetPos(leftX, y)

gump.Add(stamThresholdLabel)



y += 20



# ========== TARGETING SECTION ==========

targetingTitle = API.Gumps.CreateGumpTTFLabel("=== TARGETING ===", 9, "#ff6666", aligned="center", maxWidth=280)

targetingTitle.SetPos(0, y)

gump.Add(targetingTitle)



y += 16



redsBtn = API.Gumps.CreateSimpleButton("[REDS:" + ("ON" if target_reds else "OFF") + "]", 80, 18)

redsBtn.SetPos(leftX, y)

redsBtn.SetBackgroundHue(68 if target_reds else 90)

API.Gumps.AddControlOnClick(redsBtn, toggle_target_reds)

gump.Add(redsBtn)



graysBtn = API.Gumps.CreateSimpleButton("[GRAYS:" + ("ON" if target_grays else "OFF") + "]", 80, 18)

graysBtn.SetPos(leftX + 90, y)

graysBtn.SetBackgroundHue(68 if target_grays else 90)

API.Gumps.AddControlOnClick(graysBtn, toggle_target_grays)

gump.Add(graysBtn)



y += 22



# Auto-Target Toggle

autoTargetBtn = API.Gumps.CreateSimpleButton("[AUTO-TARGET:" + ("ON" if auto_target else "OFF") + "]", 180, 18)

autoTargetBtn.SetPos(leftX, y)

autoTargetBtn.SetBackgroundHue(68 if auto_target else 90)

API.Gumps.AddControlOnClick(autoTargetBtn, toggle_auto_target)

gump.Add(autoTargetBtn)



y += 24



# ========== UTILITIES SECTION ==========

utilTitle = API.Gumps.CreateGumpTTFLabel("=== UTILITIES ===", 9, "#00aaff", aligned="center", maxWidth=280)

utilTitle.SetPos(0, y)

gump.Add(utilTitle)



y += 16



# Auto-Buff Toggle

autoBuffBtn = API.Gumps.CreateSimpleButton("[AUTO-BUFF:" + ("ON" if auto_buff else "OFF") + "]", 130, 18)

autoBuffBtn.SetPos(leftX, y)

autoBuffBtn.SetBackgroundHue(68 if auto_buff else 90)

API.Gumps.AddControlOnClick(autoBuffBtn, toggle_auto_buff)

gump.Add(autoBuffBtn)



y += 22



# Trapped Pouch Controls

setPouchBtn = API.Gumps.CreateSimpleButton("[SET POUCH]", 90, 18)

setPouchBtn.SetPos(leftX, y)

setPouchBtn.SetBackgroundHue(43)

API.Gumps.AddControlOnClick(setPouchBtn, on_set_trapped_pouch)

gump.Add(setPouchBtn)



usePouchBtn = API.Gumps.CreateSimpleButton("[USE POUCH:" + ("ON" if use_trapped_pouch else "OFF") + "]", 130, 18)

usePouchBtn.SetPos(leftX + 95, y)

usePouchBtn.SetBackgroundHue(68 if use_trapped_pouch else 90)

API.Gumps.AddControlOnClick(usePouchBtn, toggle_use_trapped_pouch)

gump.Add(usePouchBtn)



y += 24



# ========== FOOTER - PAUSE + COOLDOWN ==========

footerTitle = API.Gumps.CreateGumpTTFLabel("=== CONTROL ===", 9, "#ff6666", aligned="center", maxWidth=280)

footerTitle.SetPos(0, y)

gump.Add(footerTitle)



y += 16



pauseBtn = API.Gumps.CreateSimpleButton("[PAUSE]", 90, 22)

pauseBtn.SetPos(10, y)

pauseBtn.SetBackgroundHue(90)

API.Gumps.AddControlOnClick(pauseBtn, toggle_pause)

gump.Add(pauseBtn)



statusLabel = API.Gumps.CreateGumpTTFLabel("Running", 9, "#00ff00")

statusLabel.SetPos(110, y + 4)

gump.Add(statusLabel)



cooldownLabel = API.Gumps.CreateGumpTTFLabel("Ready", 9, "#00ff00")

cooldownLabel.SetPos(250, y + 4)

gump.Add(cooldownLabel)



y += 28



# ========== HOTKEYS DISPLAY ==========

hotkeyTitle = API.Gumps.CreateGumpTTFLabel("=== HOTKEYS ===", 9, "#ffff00", aligned="center", maxWidth=280)

hotkeyTitle.SetPos(0, y)

gump.Add(hotkeyTitle)



y += 16



# Row 1 - Potions & Attack

hotkeyRow1 = API.Gumps.CreateGumpTTFLabel("Heal:" + HOTKEY_HEAL_POTION + " | Cure:" + HOTKEY_CURE_POTION + " | Refresh:" + HOTKEY_REFRESH_POTION, 9, "#aaaaaa")

hotkeyRow1.SetPos(leftX, y)

gump.Add(hotkeyRow1)



y += 14



# Row 2 - Bandage, Pause, Attack

hotkeyRow2 = API.Gumps.CreateGumpTTFLabel("Bandage:" + HOTKEY_BANDAGE + " | Attack:" + HOTKEY_ATTACK + " | Pause:" + HOTKEY_PAUSE, 9, "#aaaaaa")

hotkeyRow2.SetPos(leftX, y)

gump.Add(hotkeyRow2)



API.Gumps.AddGump(gump)



# ============ REGISTER HOTKEYS ============

def register_hotkeys():

    global hotkeys_registered



    if HOTKEY_HEAL_POTION:

        API.OnHotKey(HOTKEY_HEAL_POTION, on_heal_potion_hotkey)

    if HOTKEY_CURE_POTION:

        API.OnHotKey(HOTKEY_CURE_POTION, on_cure_potion_hotkey)

    if HOTKEY_REFRESH_POTION:

        API.OnHotKey(HOTKEY_REFRESH_POTION, on_refresh_potion_hotkey)

    if HOTKEY_BANDAGE:

        API.OnHotKey(HOTKEY_BANDAGE, on_bandage_hotkey)

    if HOTKEY_PAUSE:

        API.OnHotKey(HOTKEY_PAUSE, on_pause_hotkey)

    if HOTKEY_ATTACK:

        API.OnHotKey(HOTKEY_ATTACK, on_attack_hotkey)



    hotkeys_registered = True



register_hotkeys()



# Initial display update

update_display()



API.SysMsg("Dexer Suite v1 loaded!", 68)

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

API.SysMsg("Bandage=" + HOTKEY_BANDAGE + " Attack=" + HOTKEY_ATTACK + " Pause=" + HOTKEY_PAUSE, 53)



# ============ MAIN LOOP (NON-BLOCKING) ============

SAVE_INTERVAL = 10.0

next_save = time.time() + SAVE_INTERVAL



while not API.StopRequested:

    try:

        # CRITICAL: Process GUI clicks and hotkeys - always instant!

        API.ProcessCallbacks()



        # Check if bandage is complete

        check_heal_complete()



        # Save window position periodically

        if time.time() > next_save:

            API.SavePersistentVar(SETTINGS_KEY, str(gump.GetX()) + "," + str(gump.GetY()), API.PersistentVar.Char)

            next_save = time.time() + SAVE_INTERVAL



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



        # Short pause - loop runs ~10x/second

        API.Pause(0.1)



    except Exception as e:

        API.SysMsg("Error: " + str(e), 32)

        API.Pause(1)



cleanup()

