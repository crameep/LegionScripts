# ============================================================
# Gold Manager v3.2 (UI_STANDARDS)
# by Coryigon for UO Unchained
# ============================================================
#
# Automatically moves gold from your backpack to a designated
# container, and banks container gold when needed.
#
# NEW v4.0: LegionUtils refactor + smart salvaging!
#   - Refactored with LegionUtils v3.0 (17% line reduction)
#   - Smart salvaging: Only salvages when 80%+ weight (with 30s cooldown)
#   - Config buttons to target wand and loot bag
#   - [R] button on main window to reset income counter (not banked total)
#
# NEW v3.1: Fixes and improvements!
#   - Fixed hotkey button truncation (78px wide buttons)
#   - Increased window width (165px normal, 195px config)
#   - Changed [<] to [M] for income mode toggle
#   - Renamed "Gold Satchel" to "Gold Manager"
#   - UI text: "Satchel" -> "Container" (works with any bag)
#
# Features:
#   - Click hotkey buttons to rebind keys
#   - Purple = listening | Green = bound | ESC = cancel
#   - Income tracking with [M] toggle (compact/full/detailed)
#   - All original features preserved
#
# ============================================================
import API
import time
import sys

# Add LegionUtils to path
sys.path.append(r"G:\Ultima Online\TazUO-Launcher.win-x64\TazUO\LegionScripts\CoryCustom\refactors")
from LegionUtils import (
    # Phase 1: Foundation utilities
    format_gold_compact, is_in_combat, get_item_safe,
    cancel_all_targets, request_target,
    load_bool, save_bool, load_int, save_int,
    # Phase 2: Standalone utilities
    ErrorManager, WindowPositionTracker, CooldownTracker,
    get_item_count,
    # Phase 4: Complex systems
    HotkeyManager
)

__version__ = "4.0"  # Refactored with LegionUtils v3.0

# ============ USER SETTINGS ============
GOLD_GRAPHIC = 0x0EED
CHECK_GRAPHIC = 0x14F0
SCAN_INTERVAL = 2.0
MOVE_PAUSE = 0.65
SALVAGE_INTERVAL = 30.0  # Salvage loot bag every 30 seconds
DEBUG = False

# ============ GUI DIMENSIONS ============
WINDOW_WIDTH_NORMAL = 165   # Was 155, increased for wider hotkey buttons
WINDOW_WIDTH_CONFIG = 195   # Was 190, proportional increase
COLLAPSED_HEIGHT = 24
NORMAL_HEIGHT = 118
CONFIG_HEIGHT = 266  # Normal height + config panel (148px - added wand/loot buttons)

# Button dimensions
HOTKEY_BTN_WIDTH = 78       # Was 70, increased to prevent truncation
INCOME_BTN_WIDTH = 22       # [M] mode button

# ============ PERSISTENCE KEYS ============
SATCHEL_KEY = "GoldSatchel_Serial"
ENABLED_KEY = "GoldSatchel_Enabled"
SETTINGS_KEY = "GoldSatchel_XY"
EXPANDED_KEY = "GoldSatchel_Expanded"
BANK_HOTKEY_KEY = "GoldSatchel_BankHotkey"
CHECK_HOTKEY_KEY = "GoldSatchel_CheckHotkey"
INCOME_MODE_KEY = "GoldSatchel_IncomeMode"
WAND_KEY = "GoldSatchel_WandSerial"
LOOT_BAG_KEY = "GoldSatchel_LootBagSerial"
SHARED_COMBAT_KEY = "SharedCombat_Active"  # Shared combat flag from Tamer Suite

# ============ RUNTIME STATE ============
satchel_serial = 0
enabled = True
is_expanded = True
show_config = False  # Config panel visibility
session_gold = 0
last_scan_time = 0

# Error management
errors = ErrorManager(cooldown=5.0)

# Salvaging
wand_serial = 0
loot_bag_serial = 0
salvage_cooldown = CooldownTracker(SALVAGE_INTERVAL)

# Income tracking
session_start_time = 0
total_income = 0  # Total gold looted (delta tracking)
last_known_gold = 0  # Last check amount
income_display_mode = 0  # 0=compact, 1=full, 2=detailed
INCOME_CHECK_INTERVAL = 2.0  # Check gold changes every 2s
last_income_check = 0

# GUI elements
gump = None
bg = None
statusLabel = None
satchelLabel = None
incomeLabel = None
sessionLabel = None
enableBtn = None
retargetBtn = None
resetBtn = None
configBtn = None  # NEW - toggle config panel
expandBtn = None
bankHotkeyBtn = None  # NEW - integrated hotkey button
checkHotkeyBtn = None  # NEW - integrated hotkey button
incomeModeBtn = None
resetIncomeBtn = None  # NEW v3.2 - reset income counter
configBg = None  # NEW - config panel background
doneBtn = None  # NEW - close config panel
targetWandBtn = None  # NEW v3.2 - target wand button
targetLootBtn = None  # NEW v3.2 - target loot bag button

# ============ UTILITY FUNCTIONS ============
def debug_msg(text):
    if DEBUG:
        API.SysMsg("DEBUG: " + text, 88)

def get_gold_item():
    """Returns PyItem of first gold pile in backpack (not satchel!), or None"""
    global satchel_serial

    try:
        backpack = API.Player.Backpack
        if not backpack:
            return None

        backpack_serial = backpack.Serial
        items = API.ItemsInContainer(backpack_serial, True)
        if not items:
            return None

        for item in items:
            if hasattr(item, 'Graphic') and item.Graphic == GOLD_GRAPHIC:
                if hasattr(item, 'Container') and satchel_serial > 0:
                    if item.Container == satchel_serial:
                        debug_msg("Skipping gold in satchel: " + str(item.Serial))
                        continue
                debug_msg("Found gold in backpack: " + str(item.Serial))
                return item

        return None

    except Exception as e:
        API.SysMsg("Error searching for gold: " + str(e), 32)
        debug_msg("Error finding gold: " + str(e))
        return None

def get_satchel():
    """Returns the container item if valid, None otherwise"""
    return get_item_safe(satchel_serial)

def count_all_gold():
    """Count total gold in backpack + satchel for income tracking"""
    try:
        # Count gold in backpack (non-recursive - only root level)
        backpack_gold = get_item_count(GOLD_GRAPHIC, recursive=False)

        # Count gold in satchel (non-recursive)
        satchel_gold = 0
        if satchel_serial > 0:
            satchel_gold = get_item_count(GOLD_GRAPHIC, container_serial=satchel_serial, recursive=False)

        return backpack_gold + satchel_gold
    except Exception as e:
        debug_msg("Error counting gold: " + str(e))
        return 0

def check_income_delta():
    """Check for gold increases and update total_income"""
    global total_income, last_known_gold, last_income_check

    # Only check every INCOME_CHECK_INTERVAL seconds
    if time.time() - last_income_check < INCOME_CHECK_INTERVAL:
        return

    last_income_check = time.time()

    current_gold = count_all_gold()

    # On first check, just set baseline
    if last_known_gold == 0:
        last_known_gold = current_gold
        return

    # Check for increase (looting)
    if current_gold > last_known_gold:
        delta = current_gold - last_known_gold
        total_income += delta
        # Only show message if significant amount (100+)
        if delta >= 100:
            API.SysMsg("+" + format_gold_compact(delta) + " gold looted!", 68)

    # Update baseline (handles both increases and decreases)
    last_known_gold = current_gold

def get_income_rates():
    """Calculate income rates (per min, per 10min, per hour)"""
    if session_start_time == 0:
        return (0, 0, 0)

    elapsed_seconds = time.time() - session_start_time
    elapsed_minutes = elapsed_seconds / 60.0

    if elapsed_minutes < 0.1:  # Less than 6 seconds
        return (0, 0, 0)

    gold_per_min = total_income / elapsed_minutes
    gold_per_10min = gold_per_min * 10
    gold_per_hour = gold_per_min * 60

    return (gold_per_min, gold_per_10min, gold_per_hour)

def move_gold_to_satchel():
    """Move one gold pile from backpack to container"""
    if not enabled:
        errors.clear_error()
        return

    if satchel_serial == 0:
        errors.set_error("No container set!")
        return

    satchel = get_satchel()
    if not satchel:
        errors.set_error("Container not found!")
        return

    gold_item = get_gold_item()
    if not gold_item:
        errors.clear_error()
        return

    try:
        gold_serial = gold_item.Serial
        amount = getattr(gold_item, 'Amount', 1)
        if amount <= 0:
            debug_msg("Invalid gold amount: " + str(amount))
            return

        debug_msg("Moving " + str(amount) + " gold (serial " + str(gold_serial) + ") to container " + str(satchel_serial))

        API.MoveItem(gold_serial, satchel_serial, amount, -1, -1)
        API.Pause(MOVE_PAUSE)

        check_item = get_gold_item()
        if check_item and check_item.Serial == gold_serial:
            errors.set_error("Move failed - container may be full")
            return

        API.SysMsg("Moved " + str(amount) + " gold", 68)
        errors.clear_error()

    except Exception as e:
        errors.set_error("Move failed: " + str(e))
        debug_msg("Error moving gold: " + str(e))

def make_check():
    """Convert container gold to check: bank gold, cash checks, make new check"""
    global session_gold, last_error_time, last_error_msg

    try:
        API.SysMsg("Opening bank...", 68)
        API.Msg("bank")
        API.Pause(1.5)

        bank_serial = API.Bank
        if not bank_serial or bank_serial == 0:
            API.SysMsg("Failed to open bank!", 32)
            return

        if satchel_serial == 0:
            API.SysMsg("No container set!", 32)
            return

        satchel = get_satchel()
        if not satchel:
            API.SysMsg("Container not found!", 32)
            return

        API.SysMsg("Checking balance...", 68)
        API.Msg("banker balance")
        API.Pause(1.0)

        API.SysMsg("Cashing checks...", 68)
        items = API.ItemsInContainer(bank_serial, False)
        checks_cashed = 0

        if items:
            for item in items:
                if hasattr(item, 'Graphic') and item.Graphic == CHECK_GRAPHIC:
                    debug_msg("Cashing check: " + str(item.Serial))
                    API.UseObject(item.Serial, False)
                    API.Pause(0.5)
                    checks_cashed += 1

        if checks_cashed > 0:
            API.SysMsg("Cashed " + str(checks_cashed) + " check(s)", 68)
            API.Pause(1.0)

        API.SysMsg("Moving gold to bank...", 68)
        satchel_items = API.ItemsInContainer(satchel_serial, False)
        gold_moved = 0

        if satchel_items:
            for item in satchel_items:
                if hasattr(item, 'Graphic') and item.Graphic == GOLD_GRAPHIC:
                    amount = getattr(item, 'Amount', 1)
                    debug_msg("Moving " + str(amount) + " gold to bank")
                    API.MoveItem(item.Serial, bank_serial, amount, -1, -1)
                    API.Pause(MOVE_PAUSE)
                    gold_moved += amount

        if gold_moved > 0:
            API.SysMsg("Moved " + format(gold_moved, ',') + " gold to bank", 68)
            API.Pause(1.0)

        bank_items = API.ItemsInContainer(bank_serial, False)
        total_gold = 0

        if bank_items:
            for item in bank_items:
                if hasattr(item, 'Graphic') and item.Graphic == GOLD_GRAPHIC:
                    amount = getattr(item, 'Amount', 1)
                    total_gold += amount

        if total_gold < 5000:
            API.SysMsg("Only " + format(total_gold, ',') + " gold in bank (need 5000+ for check)", 43)
            return

        API.SysMsg("Creating check for " + format(total_gold, ',') + " gold...", 68)
        API.Msg("check " + str(total_gold))
        API.Pause(1.5)

        session_gold += gold_moved
        update_display()

        API.SysMsg("Check created! Total: " + format(total_gold, ','), 68)

    except Exception as e:
        API.SysMsg("Error making check: " + str(e), 32)
        debug_msg("Error in make_check: " + str(e))

def move_satchel_to_bank():
    """Move all gold from container to bank"""
    global session_gold, last_error_time, last_error_msg

    try:
        API.SysMsg("Opening bank...", 68)
        API.Msg("bank")
        API.Pause(1.5)

        bank_serial = API.Bank
        if not bank_serial or bank_serial == 0:
            API.SysMsg("Bank is not open!", 32)
            return

        if satchel_serial == 0:
            API.SysMsg("No container set!", 32)
            return

        satchel = get_satchel()
        if not satchel:
            API.SysMsg("Container not found!", 32)
            return

        items = API.ItemsInContainer(satchel_serial, False)
        if not items:
            API.SysMsg("No items in container", 43)
            return

        gold_moved = 0
        gold_count = 0

        for item in items:
            if hasattr(item, 'Graphic') and item.Graphic == GOLD_GRAPHIC:
                amount = getattr(item, 'Amount', 1)
                gold_count += 1

                debug_msg("Moving " + str(amount) + " gold to bank")
                API.MoveItem(item.Serial, bank_serial, amount, -1, -1)
                API.Pause(MOVE_PAUSE)

                gold_moved += amount

        if gold_moved > 0:
            session_gold += gold_moved
            API.SysMsg("Banked " + format(gold_moved, ',') + " gold from container", 68)
            update_display()
        else:
            API.SysMsg("No gold found in container", 43)

    except Exception as e:
        API.SysMsg("Error banking gold: " + str(e), 32)
        debug_msg("Error in move_satchel_to_bank: " + str(e))

# ============ SALVAGING FUNCTIONS ============
def should_salvage():
    """Check if we should salvage based on weight and cooldown"""
    # Must have wand and loot bag configured
    if wand_serial == 0 or loot_bag_serial == 0:
        return False

    # Skip during combat
    if is_in_combat():
        return False

    # Check cooldown (prevent spam)
    if not salvage_cooldown.is_ready():
        return False

    # Check weight threshold (80% capacity)
    try:
        current_weight = API.Player.Weight
        max_weight = API.Player.MaxWeight

        if max_weight > 0:
            weight_pct = (current_weight / max_weight) * 100
            return weight_pct >= 80  # Salvage at 80% capacity
        return False
    except:
        return False

def salvage_loot_bag():
    """Use wand of dust on loot bag - game auto-salvages all items in bag"""
    try:
        wand = API.FindItem(wand_serial)
        if not wand:
            return

        loot_bag = API.FindItem(loot_bag_serial)
        if not loot_bag:
            return

        # Clear any existing targets
        cancel_all_targets()

        # Use the wand (this will bring up a target cursor)
        API.UseObject(wand_serial, False)
        API.Pause(0.5)  # Wait for target cursor to appear

        # Wait for target cursor to be active, then target the bag
        max_wait = 0
        while not API.HasTarget() and max_wait < 20:  # Wait up to 2 seconds
            API.Pause(0.1)
            max_wait += 1

        if API.HasTarget():
            # Target the loot bag
            API.Target(loot_bag_serial)
            API.Pause(2.0)  # Wait for salvage to complete

            # Calculate weight after salvage for feedback
            try:
                weight_pct = int((API.Player.Weight / API.Player.MaxWeight) * 100)
                API.SysMsg("Salvaged loot bag (Weight: " + str(weight_pct) + "%)", 68)
            except:
                API.SysMsg("Salvaged loot bag", 68)

            debug_msg("Auto-salvaged loot bag")
        else:
            debug_msg("Target cursor didn't appear")

    except Exception as e:
        debug_msg("Error salvaging: " + str(e))
        API.SysMsg("Salvage error: " + str(e), 32)

# ============ CONFIG PANEL ============
def toggle_config():
    """Toggle config panel visibility"""
    global show_config
    if show_config:
        hide_config_panel()
    else:
        show_config_panel()

def show_config_panel():
    """Show config panel and expand window width"""
    global show_config
    show_config = True

    # Show config elements
    configBg.IsVisible = True
    enableBtn.IsVisible = True
    retargetBtn.IsVisible = True
    resetBtn.IsVisible = True
    targetWandBtn.IsVisible = True
    targetLootBtn.IsVisible = True
    doneBtn.IsVisible = True

    # Update config button appearance
    configBtn.SetBackgroundHue(68)  # Green when active

    # Reposition title buttons for wider window
    configBtn.SetPos(145, 3)
    expandBtn.SetPos(170, 3)

    # Expand window width (only if expanded)
    if is_expanded:
        gump.SetRect(gump.GetX(), gump.GetY(), WINDOW_WIDTH_CONFIG, CONFIG_HEIGHT)
        bg.SetRect(0, 0, WINDOW_WIDTH_CONFIG, CONFIG_HEIGHT)
    else:
        # Just resize width when collapsed
        gump.SetRect(gump.GetX(), gump.GetY(), WINDOW_WIDTH_CONFIG, COLLAPSED_HEIGHT)
        bg.SetRect(0, 0, WINDOW_WIDTH_CONFIG, COLLAPSED_HEIGHT)

def hide_config_panel():
    """Hide config panel and shrink window width"""
    global show_config
    show_config = False

    # Hide config elements
    configBg.IsVisible = False
    enableBtn.IsVisible = False
    retargetBtn.IsVisible = False
    resetBtn.IsVisible = False
    targetWandBtn.IsVisible = False
    targetLootBtn.IsVisible = False
    doneBtn.IsVisible = False

    # Update config button appearance
    configBtn.SetBackgroundHue(90)  # Gray when inactive

    # Reposition title buttons for narrower window
    configBtn.SetPos(115, 3)
    expandBtn.SetPos(140, 3)

    # Shrink window width (only if expanded)
    if is_expanded:
        gump.SetRect(gump.GetX(), gump.GetY(), WINDOW_WIDTH_NORMAL, NORMAL_HEIGHT)
        bg.SetRect(0, 0, WINDOW_WIDTH_NORMAL, NORMAL_HEIGHT)
    else:
        # Just resize width when collapsed
        gump.SetRect(gump.GetX(), gump.GetY(), WINDOW_WIDTH_NORMAL, COLLAPSED_HEIGHT)
        bg.SetRect(0, 0, WINDOW_WIDTH_NORMAL, COLLAPSED_HEIGHT)

# ============ EXPAND/COLLAPSE ============
def toggle_expand():
    global is_expanded

    is_expanded = not is_expanded
    save_expanded_state()

    if is_expanded:
        expand_window()
    else:
        collapse_window()

def expand_window():
    expandBtn.SetText("[-]")

    # Show main content elements
    statusLabel.IsVisible = True
    satchelLabel.IsVisible = True
    incomeLabel.IsVisible = True
    incomeModeBtn.IsVisible = True
    resetIncomeBtn.IsVisible = True
    sessionLabel.IsVisible = True
    bankHotkeyBtn.IsVisible = True
    checkHotkeyBtn.IsVisible = True

    # Calculate dimensions based on config state
    if show_config:
        width = WINDOW_WIDTH_CONFIG
        height = CONFIG_HEIGHT
        # Show config elements
        configBg.IsVisible = True
        enableBtn.IsVisible = True
        retargetBtn.IsVisible = True
        resetBtn.IsVisible = True
        targetWandBtn.IsVisible = True
        targetLootBtn.IsVisible = True
        doneBtn.IsVisible = True
        # Position title buttons for wide window
        configBtn.SetPos(145, 3)
        expandBtn.SetPos(170, 3)
    else:
        width = WINDOW_WIDTH_NORMAL
        height = NORMAL_HEIGHT
        # Position title buttons for narrow window
        configBtn.SetPos(115, 3)
        expandBtn.SetPos(140, 3)

    x = gump.GetX()
    y = gump.GetY()
    gump.SetRect(x, y, width, height)
    bg.SetRect(0, 0, width, height)

def collapse_window():
    expandBtn.SetText("[+]")

    # Hide all main content
    statusLabel.IsVisible = False
    satchelLabel.IsVisible = False
    incomeLabel.IsVisible = False
    incomeModeBtn.IsVisible = False
    resetIncomeBtn.IsVisible = False
    sessionLabel.IsVisible = False
    bankHotkeyBtn.IsVisible = False
    checkHotkeyBtn.IsVisible = False

    # Hide config elements
    configBg.IsVisible = False
    enableBtn.IsVisible = False
    retargetBtn.IsVisible = False
    resetBtn.IsVisible = False
    targetWandBtn.IsVisible = False
    targetLootBtn.IsVisible = False
    doneBtn.IsVisible = False

    # Calculate width based on config state
    width = WINDOW_WIDTH_CONFIG if show_config else WINDOW_WIDTH_NORMAL

    # Position title buttons based on width
    if show_config:
        configBtn.SetPos(145, 3)
        expandBtn.SetPos(170, 3)
    else:
        configBtn.SetPos(115, 3)
        expandBtn.SetPos(140, 3)

    x = gump.GetX()
    y = gump.GetY()
    gump.SetRect(x, y, width, COLLAPSED_HEIGHT)
    bg.SetRect(0, 0, width, COLLAPSED_HEIGHT)

def save_expanded_state():
    API.SavePersistentVar(EXPANDED_KEY, str(is_expanded), API.PersistentVar.Char)

def load_expanded_state():
    global is_expanded
    saved = API.GetPersistentVar(EXPANDED_KEY, "True", API.PersistentVar.Char)
    is_expanded = (saved == "True")

# ============ GUI CALLBACKS ============
def toggle_enabled():
    global enabled
    enabled = not enabled
    save_bool(ENABLED_KEY, enabled)
    update_display()
    API.SysMsg("Gold Manager: " + ("ENABLED" if enabled else "DISABLED"), 68 if enabled else 32)

def retarget_satchel():
    global satchel_serial

    API.SysMsg("Target your gold container...", 68)

    target = request_target(timeout=10)
    if target:
        item = API.FindItem(target)
        if not item:
            API.SysMsg("Invalid target!", 32)
            return

        is_container = getattr(item, 'IsContainer', False)

        if not is_container:
            API.SysMsg("Warning: Target may not be a container", 43)

        satchel_serial = target
        save_int(SATCHEL_KEY, satchel_serial)
        debug_msg("Container serial set to: " + str(satchel_serial))
        errors.clear_error()
        update_display()
        API.SysMsg("Gold container set! Serial: 0x" + format(satchel_serial, 'X'), 68)
    else:
        API.SysMsg("Targeting cancelled", 53)

def reset_session():
    global session_gold, total_income, last_known_gold, session_start_time
    session_gold = 0
    total_income = 0
    last_known_gold = 0
    session_start_time = time.time()
    update_display()
    API.SysMsg("Counters reset (banked + income)", 68)

def reset_income():
    """Reset only the income counter, not the banked total"""
    global total_income, last_known_gold, session_start_time
    total_income = 0
    last_known_gold = count_all_gold()  # Reset baseline to current gold
    session_start_time = time.time()
    update_display()
    API.SysMsg("Income counter reset", 68)

def retarget_wand():
    """Target the wand of dust"""
    global wand_serial

    API.SysMsg("Target your Wand of Dust...", 68)

    target = request_target(timeout=10)
    if target:
        item = API.FindItem(target)
        if not item:
            API.SysMsg("Invalid target!", 32)
            return

        wand_serial = target
        save_int(WAND_KEY, wand_serial)
        debug_msg("Wand serial set to: " + str(wand_serial))
        API.SysMsg("Wand of Dust set! Serial: 0x" + format(wand_serial, 'X'), 68)
    else:
        API.SysMsg("Targeting cancelled", 53)

def retarget_loot_bag():
    """Target the loot bag for salvaging"""
    global loot_bag_serial

    API.SysMsg("Target your loot bag...", 68)

    target = request_target(timeout=10)
    if target:
        item = API.FindItem(target)
        if not item:
            API.SysMsg("Invalid target!", 32)
            return

        is_container = getattr(item, 'IsContainer', False)

        if not is_container:
            API.SysMsg("Warning: Target may not be a container", 43)

        loot_bag_serial = target
        save_int(LOOT_BAG_KEY, loot_bag_serial)
        debug_msg("Loot bag serial set to: " + str(loot_bag_serial))
        API.SysMsg("Loot bag set! Serial: 0x" + format(loot_bag_serial, 'X'), 68)
    else:
        API.SysMsg("Targeting cancelled", 53)

def toggle_income_mode():
    """Cycle through income display modes: compact -> full -> detailed"""
    global income_display_mode
    income_display_mode = (income_display_mode + 1) % 3
    API.SavePersistentVar(INCOME_MODE_KEY, str(income_display_mode), API.PersistentVar.Char)
    update_display()

    mode_names = ["Compact", "Full", "Detailed"]
    API.SysMsg("Income display: " + mode_names[income_display_mode], 68)

# ============ DISPLAY UPDATES ============
def update_display():
    if not gump:
        return

    try:
        if enabled:
            if satchel_serial == 0:
                statusLabel.SetText("Status: ENABLED (no container)")
            else:
                satchel = get_satchel()
                if satchel:
                    statusLabel.SetText("Status: ACTIVE")
                else:
                    statusLabel.SetText("Status: ENABLED (container not found)")
        else:
            statusLabel.SetText("Status: DISABLED")

        debug_msg("update_display: satchel_serial = " + str(satchel_serial))
        if satchel_serial == 0:
            satchelLabel.SetText("Container: [Not Set]")
        else:
            satchel = get_satchel()
            if satchel:
                satchelLabel.SetText("Container: 0x" + format(satchel_serial, 'X') + " [OK]")
            else:
                satchelLabel.SetText("Container: 0x" + format(satchel_serial, 'X') + " [NOT FOUND]")

        # Update income display
        per_min, per_10min, per_hour = get_income_rates()

        if income_display_mode == 0:  # Compact - rates only
            income_text = format_gold_compact(per_min) + "/m | " + format_gold_compact(per_hour) + "/hr"
        elif income_display_mode == 1:  # Full - total + main rate
            income_text = format_gold_compact(total_income) + " (" + format_gold_compact(per_min) + "/m)"
        else:  # Detailed (mode 2) - all rates
            income_text = format_gold_compact(per_min) + "/m | " + format_gold_compact(per_10min) + "/10m | " + format_gold_compact(per_hour) + "/hr"

        incomeLabel.SetText(income_text)

        sessionLabel.SetText("Banked: " + format(session_gold, ',') + " gold")

        enableBtn.SetText("[" + ("ON" if enabled else "OFF") + "]")
        enableBtn.SetBackgroundHue(68 if enabled else 32)

    except Exception as e:
        API.SysMsg("Error updating display: " + str(e), 32)

# ============ INITIALIZATION ============
satchel_serial = load_int(SATCHEL_KEY, 0)
enabled = load_bool(ENABLED_KEY, True)

# Load income display mode
income_display_mode = load_int(INCOME_MODE_KEY, 0)

# Load wand and loot bag serials
wand_serial = load_int(WAND_KEY, 0)
loot_bag_serial = load_int(LOOT_BAG_KEY, 0)

# Initialize session timer
session_start_time = time.time()

load_expanded_state()

# ============ BUILD GUI ============
initial_width = WINDOW_WIDTH_NORMAL
initial_height = NORMAL_HEIGHT if is_expanded else COLLAPSED_HEIGHT

gump = API.Gumps.CreateGump()

# Window position tracking
pos_tracker = WindowPositionTracker(gump, SETTINGS_KEY, 100, 100)
gump.SetRect(pos_tracker.last_x, pos_tracker.last_y, initial_width, initial_height)

API.Gumps.AddControlOnDisposed(gump, lambda: pos_tracker.save())

bg = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
bg.SetRect(0, 0, initial_width, initial_height)
gump.Add(bg)

# ============ TITLE BAR ============
titleLabel = API.Gumps.CreateGumpTTFLabel("Gold Manager", 16, "#ffaa00")
titleLabel.SetPos(5, 2)
gump.Add(titleLabel)

configBtn = API.Gumps.CreateSimpleButton("[C]", 20, 18)
configBtn.SetPos(115, 3)  # For 165px width
configBtn.SetBackgroundHue(90)  # Gray initially
API.Gumps.AddControlOnClick(configBtn, toggle_config)
gump.Add(configBtn)

expandBtn = API.Gumps.CreateSimpleButton("[-]" if is_expanded else "[+]", 20, 18)
expandBtn.SetPos(140, 3)  # For 165px width
expandBtn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(expandBtn, toggle_expand)
gump.Add(expandBtn)

# ============ MAIN CONTENT (always visible when expanded) ============
leftMargin = 5
y = 26

statusLabel = API.Gumps.CreateGumpTTFLabel("Status: ACTIVE", 11, "#00ff00")
statusLabel.SetPos(leftMargin, y)
statusLabel.IsVisible = is_expanded
gump.Add(statusLabel)

y += 13
satchelLabel = API.Gumps.CreateGumpTTFLabel("Container: [Not Set]", 11, "#ff6666")
satchelLabel.SetPos(leftMargin, y)
satchelLabel.IsVisible = is_expanded
gump.Add(satchelLabel)

y += 14
# Income display with mode toggle button and reset button
incomeLabel = API.Gumps.CreateGumpTTFLabel("0/m | 0/hr", 13, "#00ff88")
incomeLabel.SetPos(leftMargin, y)
incomeLabel.IsVisible = is_expanded
gump.Add(incomeLabel)

# Reset income button
resetIncomeBtn = API.Gumps.CreateSimpleButton("[R]", 20, 14)
resetIncomeBtn.SetPos(WINDOW_WIDTH_NORMAL - 46, y - 1)
resetIncomeBtn.SetBackgroundHue(53)  # Yellow-purple
resetIncomeBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(resetIncomeBtn, reset_income)
gump.Add(resetIncomeBtn)

# Income mode toggle button
incomeModeBtn = API.Gumps.CreateSimpleButton("[M]", INCOME_BTN_WIDTH, 14)
incomeModeBtn.SetPos(WINDOW_WIDTH_NORMAL - 24, y - 1)
incomeModeBtn.SetBackgroundHue(66)
incomeModeBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(incomeModeBtn, toggle_income_mode)
gump.Add(incomeModeBtn)

y += 16
sessionLabel = API.Gumps.CreateGumpTTFLabel("Banked: 0 gold", 14, "#ffcc00", aligned="center", maxWidth=WINDOW_WIDTH_NORMAL)
sessionLabel.SetPos(0, y)
sessionLabel.IsVisible = is_expanded
gump.Add(sessionLabel)

y += 16
# ============ INTEGRATED HOTKEY BUTTONS (HotkeyManager) ============
# Create buttons first
bankHotkeyBtn = API.Gumps.CreateSimpleButton("[BANK: B]", HOTKEY_BTN_WIDTH, 24)
bankHotkeyBtn.SetPos(leftMargin, y)
bankHotkeyBtn.IsVisible = is_expanded
gump.Add(bankHotkeyBtn)

checkHotkeyBtn = API.Gumps.CreateSimpleButton("[CHECK: C]", HOTKEY_BTN_WIDTH, 24)
checkHotkeyBtn.SetPos(leftMargin + HOTKEY_BTN_WIDTH + 2, y)
checkHotkeyBtn.IsVisible = is_expanded
gump.Add(checkHotkeyBtn)

# Initialize HotkeyManager
hotkeys = HotkeyManager()
bank_hk = hotkeys.add("bank", BANK_HOTKEY_KEY, "Bank", move_satchel_to_bank, bankHotkeyBtn, "B")
check_hk = hotkeys.add("check", CHECK_HOTKEY_KEY, "Make Check", make_check, checkHotkeyBtn, "C")

# Wire button clicks to start capture
API.Gumps.AddControlOnClick(bankHotkeyBtn, bank_hk.start_capture)
API.Gumps.AddControlOnClick(checkHotkeyBtn, check_hk.start_capture)

# ============ CONFIG PANEL (hidden by default, shown when [C] clicked) ============
config_y = 118

configBg = API.Gumps.CreateGumpColorBox(0.8, "#2a2a3e")
configBg.SetRect(0, config_y, WINDOW_WIDTH_CONFIG, 148)  # Increased height for new buttons
configBg.IsVisible = False
gump.Add(configBg)

btnW = 85
btnH = 20
config_y += 8

enableBtn = API.Gumps.CreateSimpleButton("[ON]", btnW, btnH)
enableBtn.SetPos(leftMargin, config_y)
enableBtn.SetBackgroundHue(68)
enableBtn.IsVisible = False
API.Gumps.AddControlOnClick(enableBtn, toggle_enabled)
gump.Add(enableBtn)

retargetBtn = API.Gumps.CreateSimpleButton("[Container]", btnW, btnH)
retargetBtn.SetPos(leftMargin + 90, config_y)
retargetBtn.SetBackgroundHue(66)
retargetBtn.IsVisible = False
API.Gumps.AddControlOnClick(retargetBtn, retarget_satchel)
gump.Add(retargetBtn)

config_y += 24
resetBtn = API.Gumps.CreateSimpleButton("[RESET]", 180, btnH)
resetBtn.SetPos(leftMargin, config_y)
resetBtn.SetBackgroundHue(53)
resetBtn.IsVisible = False
API.Gumps.AddControlOnClick(resetBtn, reset_session)
gump.Add(resetBtn)

config_y += 24
# Wand and Loot Bag targeting buttons
targetWandBtn = API.Gumps.CreateSimpleButton("[Dust Wand]", btnW, btnH)
targetWandBtn.SetPos(leftMargin, config_y)
targetWandBtn.SetBackgroundHue(66)
targetWandBtn.IsVisible = False
API.Gumps.AddControlOnClick(targetWandBtn, retarget_wand)
gump.Add(targetWandBtn)

targetLootBtn = API.Gumps.CreateSimpleButton("[Loot Bag]", btnW, btnH)
targetLootBtn.SetPos(leftMargin + 90, config_y)
targetLootBtn.SetBackgroundHue(66)
targetLootBtn.IsVisible = False
API.Gumps.AddControlOnClick(targetLootBtn, retarget_loot_bag)
gump.Add(targetLootBtn)

config_y += 24
doneBtn = API.Gumps.CreateSimpleButton("[DONE]", 180, 22)
doneBtn.SetPos(leftMargin, config_y)
doneBtn.SetBackgroundHue(90)
doneBtn.IsVisible = False
API.Gumps.AddControlOnClick(doneBtn, hide_config_panel)
gump.Add(doneBtn)

API.Gumps.AddGump(gump)

# Register all hotkeys
hotkeys.register_all()

update_display()

API.SysMsg("Gold Manager v4.0 (LegionUtils) loaded!", 68)
API.SysMsg("Bank: " + bank_hk.key + " | Check: " + check_hk.key + " | [M]=mode [R]=reset [C]=config", 43)
if satchel_serial > 0:
    API.SysMsg("Container: 0x" + format(satchel_serial, 'X'), 66)
else:
    API.SysMsg("Click [C] config button, then [Container] to set your container", 43)
if wand_serial > 0 and loot_bag_serial > 0:
    API.SysMsg("Auto-salvage: When 80%+ weight (30s cooldown)", 66)

# ============ MAIN LOOP ============
DISPLAY_UPDATE_INTERVAL = 0.5
next_scan = time.time() + SCAN_INTERVAL
next_display = time.time() + DISPLAY_UPDATE_INTERVAL

while not API.StopRequested:
    try:
        API.ProcessCallbacks()

        # Track income from looting
        check_income_delta()

        if enabled and time.time() >= next_scan:
            move_gold_to_satchel()
            next_scan = time.time() + SCAN_INTERVAL

        # Salvage loot bag when heavy (80%+ weight) and cooldown ready
        if should_salvage():
            salvage_loot_bag()
            salvage_cooldown.use()

        if time.time() >= next_display:
            update_display()
            next_display = time.time() + DISPLAY_UPDATE_INTERVAL

        API.Pause(0.1)

    except Exception as e:
        API.SysMsg("Error in main loop: " + str(e), 32)
        debug_msg("Main loop exception: " + str(e))
        API.Pause(1)
