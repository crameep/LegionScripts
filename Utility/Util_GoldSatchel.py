# ============================================================
# Gold Manager v3.1 (UI_STANDARDS)
# by Coryigon for UO Unchained
# ============================================================
#
# Automatically moves gold from your backpack to a designated
# container, and banks container gold when needed.
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

__version__ = "3.1"

# ============ USER SETTINGS ============
GOLD_GRAPHIC = 0x0EED
CHECK_GRAPHIC = 0x14F0
SCAN_INTERVAL = 2.0
MOVE_PAUSE = 0.65
DEBUG = False

# ============ GUI DIMENSIONS ============
WINDOW_WIDTH_NORMAL = 165   # Was 155, increased for wider hotkey buttons
WINDOW_WIDTH_CONFIG = 195   # Was 190, proportional increase
COLLAPSED_HEIGHT = 24
NORMAL_HEIGHT = 118
CONFIG_HEIGHT = 218  # Normal height + config panel (100px)

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

# ============ HOTKEY STATE ============
bank_hotkey = "B"
check_hotkey = "C"
listening_for_action = None  # "bank", "check", or None

# ============ ALL POSSIBLE KEYS ============
ALL_KEYS = [
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
    "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "NUMPAD0", "NUMPAD1", "NUMPAD2", "NUMPAD3", "NUMPAD4",
    "NUMPAD5", "NUMPAD6", "NUMPAD7", "NUMPAD8", "NUMPAD9",
    "ESC",  # For canceling hotkey capture
]

# ============ RUNTIME STATE ============
satchel_serial = 0
enabled = True
is_expanded = True
show_config = False  # Config panel visibility
session_gold = 0
last_scan_time = 0
last_error_time = 0
last_error_msg = ""
ERROR_COOLDOWN = 5.0

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
configBg = None  # NEW - config panel background
doneBtn = None  # NEW - close config panel

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
    if satchel_serial == 0:
        return None

    satchel = API.FindItem(satchel_serial)
    if not satchel:
        return None

    return satchel

def count_all_gold():
    """Count total gold in backpack + satchel for income tracking"""
    total = 0

    try:
        backpack = API.Player.Backpack
        if not backpack:
            return 0

        # Count gold in backpack (loose gold)
        backpack_items = API.ItemsInContainer(backpack.Serial, False)  # Non-recursive for backpack root
        backpack_gold = 0
        if backpack_items:
            for item in backpack_items:
                if hasattr(item, 'Graphic') and item.Graphic == GOLD_GRAPHIC:
                    amount = getattr(item, 'Amount', 1)
                    backpack_gold += amount

        # Count gold in satchel (if set)
        satchel_gold = 0
        if satchel_serial > 0:
            satchel = get_satchel()
            if satchel:
                satchel_items = API.ItemsInContainer(satchel_serial, False)
                if satchel_items:
                    for item in satchel_items:
                        if hasattr(item, 'Graphic') and item.Graphic == GOLD_GRAPHIC:
                            amount = getattr(item, 'Amount', 1)
                            satchel_gold += amount

        total = backpack_gold + satchel_gold
        return total
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

def format_gold_compact(amount):
    """Format gold in compact form: 1234 -> 1.2k, 123456 -> 123k"""
    if amount < 1000:
        return str(int(amount))
    elif amount < 10000:
        # 1000-9999: show 1 decimal, but strip .0
        val = round(amount / 1000.0, 1)
        if val == int(val):  # If it's a whole number like 2.0
            return str(int(val)) + "k"
        else:
            return "{:.1f}".format(val) + "k"  # Force exactly 1 decimal place
    elif amount < 1000000:
        # 10000+: no decimals (12k, 123k)
        return str(int(amount / 1000)) + "k"
    else:
        # Million+: show 1 decimal, but strip .0
        val = round(amount / 1000000.0, 1)
        if val == int(val):
            return str(int(val)) + "m"
        else:
            return "{:.1f}".format(val) + "m"  # Force exactly 1 decimal place

def move_gold_to_satchel():
    """Move one gold pile from backpack to container"""
    global last_error_time, last_error_msg

    if not enabled:
        clear_error()
        return

    if satchel_serial == 0:
        set_error("No container set!")
        return

    satchel = get_satchel()
    if not satchel:
        set_error("Container not found!")
        return

    gold_item = get_gold_item()
    if not gold_item:
        clear_error()
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
            set_error("Move failed - container may be full")
            return

        API.SysMsg("Moved " + str(amount) + " gold", 68)
        clear_error()

    except Exception as e:
        set_error("Move failed: " + str(e))
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

def set_error(msg):
    global last_error_time, last_error_msg

    if msg != last_error_msg or (time.time() - last_error_time) > ERROR_COOLDOWN:
        last_error_msg = msg
        last_error_time = time.time()
        if msg:
            API.SysMsg(msg, 32)

def clear_error():
    global last_error_msg
    last_error_msg = ""

# ============ HOTKEY SYSTEM ============
def make_key_handler(key_name):
    """Create a callback for a specific key"""
    def handler():
        global listening_for_action, bank_hotkey, check_hotkey

        # If we're listening for a key assignment
        if listening_for_action is not None:
            # ESC cancels listening mode
            if key_name == "ESC":
                if listening_for_action == "bank":
                    update_hotkey_buttons()
                    API.SysMsg("Cancelled - kept " + bank_hotkey, 53)
                elif listening_for_action == "check":
                    update_hotkey_buttons()
                    API.SysMsg("Cancelled - kept " + check_hotkey, 53)
                listening_for_action = None
                return

            # Assign the key
            if listening_for_action == "bank":
                # Warn if duplicate
                if key_name == check_hotkey:
                    API.SysMsg("Warning: " + key_name + " already used for Make Check", 43)
                bank_hotkey = key_name
                API.SavePersistentVar(BANK_HOTKEY_KEY, bank_hotkey, API.PersistentVar.Char)
                API.SysMsg("Bank bound to: " + key_name, 68)
            elif listening_for_action == "check":
                # Warn if duplicate
                if key_name == bank_hotkey:
                    API.SysMsg("Warning: " + key_name + " already used for Bank", 43)
                check_hotkey = key_name
                API.SavePersistentVar(CHECK_HOTKEY_KEY, check_hotkey, API.PersistentVar.Char)
                API.SysMsg("Make Check bound to: " + key_name, 68)

            update_hotkey_buttons()
            listening_for_action = None
            return

        # Not listening - execute the action if this key is bound
        if key_name == bank_hotkey:
            move_satchel_to_bank()
        elif key_name == check_hotkey:
            make_check()

    return handler

def start_capture_bank_hotkey():
    """Start listening for bank hotkey"""
    global listening_for_action
    listening_for_action = "bank"
    bankHotkeyBtn.SetBackgroundHue(38)  # Purple
    bankHotkeyBtn.SetText("[Listening...]")
    API.SysMsg("Press key for Bank hotkey (ESC to cancel)...", 38)

def start_capture_check_hotkey():
    """Start listening for check hotkey"""
    global listening_for_action
    listening_for_action = "check"
    checkHotkeyBtn.SetBackgroundHue(38)  # Purple
    checkHotkeyBtn.SetText("[Listening...]")
    API.SysMsg("Press key for Check hotkey (ESC to cancel)...", 38)

def update_hotkey_buttons():
    """Update hotkey button labels based on current bindings"""
    bankHotkeyBtn.SetText("[BANK: " + bank_hotkey + "]")
    bankHotkeyBtn.SetBackgroundHue(68)  # Green when bound

    checkHotkeyBtn.SetText("[CHECK: " + check_hotkey + "]")
    checkHotkeyBtn.SetBackgroundHue(68)  # Green when bound

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
    sessionLabel.IsVisible = False
    bankHotkeyBtn.IsVisible = False
    checkHotkeyBtn.IsVisible = False

    # Hide config elements
    configBg.IsVisible = False
    enableBtn.IsVisible = False
    retargetBtn.IsVisible = False
    resetBtn.IsVisible = False
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
    API.SavePersistentVar(ENABLED_KEY, str(enabled), API.PersistentVar.Char)
    update_display()
    API.SysMsg("Gold Manager: " + ("ENABLED" if enabled else "DISABLED"), 68 if enabled else 32)

def retarget_satchel():
    global satchel_serial

    API.SysMsg("Target your gold container...", 68)

    if API.HasTarget():
        API.CancelTarget()
    API.CancelPreTarget()

    try:
        target = API.RequestTarget(timeout=10)
        if target:
            item = API.FindItem(target)
            if not item:
                API.SysMsg("Invalid target!", 32)
                return

            is_container = getattr(item, 'IsContainer', False)

            if not is_container:
                API.SysMsg("Warning: Target may not be a container", 43)

            satchel_serial = target
            API.SavePersistentVar(SATCHEL_KEY, str(satchel_serial), API.PersistentVar.Char)
            debug_msg("Container serial set to: " + str(satchel_serial))
            clear_error()
            update_display()
            API.SysMsg("Gold container set! Serial: 0x" + format(satchel_serial, 'X'), 68)
        else:
            API.SysMsg("Targeting cancelled", 53)
    except Exception as e:
        API.SysMsg("Error targeting: " + str(e), 32)

def reset_session():
    global session_gold, total_income, last_known_gold, session_start_time
    session_gold = 0
    total_income = 0
    last_known_gold = 0
    session_start_time = time.time()
    update_display()
    API.SysMsg("Counters reset (banked + income)", 68)

def toggle_income_mode():
    """Cycle through income display modes: compact -> full -> detailed"""
    global income_display_mode
    income_display_mode = (income_display_mode + 1) % 3
    API.SavePersistentVar(INCOME_MODE_KEY, str(income_display_mode), API.PersistentVar.Char)
    update_display()

    mode_names = ["Compact", "Full", "Detailed"]
    API.SysMsg("Income display: " + mode_names[income_display_mode], 68)

def on_closed():
    try:
        if gump:
            x = gump.GetX()
            y = gump.GetY()
            API.SavePersistentVar(SETTINGS_KEY, str(x) + "," + str(y), API.PersistentVar.Char)
    except:
        pass

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
try:
    satchel_str = API.GetPersistentVar(SATCHEL_KEY, "0", API.PersistentVar.Char)
    satchel_serial = int(satchel_str) if satchel_str.isdigit() else 0
except Exception as e:
    debug_msg("Failed to load satchel serial: " + str(e))
    satchel_serial = 0

try:
    enabled_str = API.GetPersistentVar(ENABLED_KEY, "True", API.PersistentVar.Char)
    enabled = (enabled_str == "True")
except Exception as e:
    debug_msg("Failed to load enabled state: " + str(e))
    enabled = True

# Load hotkeys
bank_hotkey = API.GetPersistentVar(BANK_HOTKEY_KEY, "B", API.PersistentVar.Char)
check_hotkey = API.GetPersistentVar(CHECK_HOTKEY_KEY, "C", API.PersistentVar.Char)

# Load income display mode
try:
    income_display_mode = int(API.GetPersistentVar(INCOME_MODE_KEY, "0", API.PersistentVar.Char))
except:
    income_display_mode = 0

# Initialize session timer
session_start_time = time.time()

load_expanded_state()

# ============ BUILD GUI ============
window_x = 100
window_y = 100

savedPos = API.GetPersistentVar(SETTINGS_KEY, str(window_x) + "," + str(window_y), API.PersistentVar.Char)
posXY = savedPos.split(',')
lastX = int(posXY[0])
lastY = int(posXY[1])

initial_width = WINDOW_WIDTH_NORMAL
initial_height = NORMAL_HEIGHT if is_expanded else COLLAPSED_HEIGHT

gump = API.Gumps.CreateGump()
gump.SetRect(lastX, lastY, initial_width, initial_height)
API.Gumps.AddControlOnDisposed(gump, on_closed)

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
# Income display with mode toggle button
incomeLabel = API.Gumps.CreateGumpTTFLabel("0/m | 0/hr", 13, "#00ff88")
incomeLabel.SetPos(leftMargin, y)
incomeLabel.IsVisible = is_expanded
gump.Add(incomeLabel)

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
# ============ INTEGRATED HOTKEY BUTTONS ============
# Bank button with integrated hotkey
bankHotkeyBtn = API.Gumps.CreateSimpleButton("[BANK: B]", HOTKEY_BTN_WIDTH, 24)
bankHotkeyBtn.SetPos(leftMargin, y)
bankHotkeyBtn.SetBackgroundHue(68)  # Green
bankHotkeyBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(bankHotkeyBtn, start_capture_bank_hotkey)
gump.Add(bankHotkeyBtn)

# Check button with integrated hotkey
checkHotkeyBtn = API.Gumps.CreateSimpleButton("[CHECK: C]", HOTKEY_BTN_WIDTH, 24)
checkHotkeyBtn.SetPos(leftMargin + HOTKEY_BTN_WIDTH + 2, y)
checkHotkeyBtn.SetBackgroundHue(68)  # Green
checkHotkeyBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(checkHotkeyBtn, start_capture_check_hotkey)
gump.Add(checkHotkeyBtn)

# ============ CONFIG PANEL (hidden by default, shown when [C] clicked) ============
config_y = 118

configBg = API.Gumps.CreateGumpColorBox(0.8, "#2a2a3e")
configBg.SetRect(0, config_y, WINDOW_WIDTH_CONFIG, 100)
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

retargetBtn = API.Gumps.CreateSimpleButton("[TARGET]", btnW, btnH)
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
doneBtn = API.Gumps.CreateSimpleButton("[DONE]", 180, 22)
doneBtn.SetPos(leftMargin, config_y)
doneBtn.SetBackgroundHue(90)
doneBtn.IsVisible = False
API.Gumps.AddControlOnClick(doneBtn, hide_config_panel)
gump.Add(doneBtn)

API.Gumps.AddGump(gump)

# Update button labels to show current bindings
update_hotkey_buttons()

update_display()

# Register all possible keys
registered_count = 0
for key in ALL_KEYS:
    try:
        API.OnHotKey(key, make_key_handler(key))
        registered_count += 1
    except:
        pass

API.SysMsg("Gold Manager v3.1 loaded! (" + str(registered_count) + " keys)", 68)
API.SysMsg("Bank: " + bank_hotkey + " | Check: " + check_hotkey + " | [M]=mode [C]=config", 43)
if satchel_serial > 0:
    API.SysMsg("Container: 0x" + format(satchel_serial, 'X'), 66)
else:
    API.SysMsg("Click [C] config button, then [TARGET] to set your container", 43)

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

        if time.time() >= next_display:
            update_display()
            next_display = time.time() + DISPLAY_UPDATE_INTERVAL

        API.Pause(0.1)

    except Exception as e:
        API.SysMsg("Error in main loop: " + str(e), 32)
        debug_msg("Main loop exception: " + str(e))
        API.Pause(1)
