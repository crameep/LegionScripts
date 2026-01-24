# ============================================================
# Gold Satchel Auto-Mover v2.1 (with Hotkeys)
# by Coryigon for UO Unchained
# ============================================================
#
# Automatically moves gold from your backpack to a designated
# Gold Satchel container, and banks satchel gold when needed.
#
# NEW: Customizable hotkeys for Bank and Make Check actions!
#
# Features:
#   - Customizable hotkeys - click blue [K] button to rebind
#   - Compact UI - hotkey buttons show current binding
#   - BANK GOLD button with hotkey (default: B)
#   - MAKE CHECK button with hotkey (default: C)
#   - Blue = click to change | Purple = listening for key
#   - All original features from v1.8
#
# ============================================================
import API
import time

__version__ = "2.1"

# ============ USER SETTINGS ============
GOLD_GRAPHIC = 0x0EED
CHECK_GRAPHIC = 0x14F0
SCAN_INTERVAL = 2.0
MOVE_PAUSE = 0.65
DEBUG = False

# ============ GUI DIMENSIONS ============
WINDOW_WIDTH = 140
COLLAPSED_HEIGHT = 24
EXPANDED_HEIGHT = 180  # Slightly taller for hotkey buttons

# ============ PERSISTENCE KEYS ============
SATCHEL_KEY = "GoldSatchel_Serial"
ENABLED_KEY = "GoldSatchel_Enabled"
SETTINGS_KEY = "GoldSatchel_XY"
EXPANDED_KEY = "GoldSatchel_Expanded"
BANK_HOTKEY_KEY = "GoldSatchel_BankHotkey"
CHECK_HOTKEY_KEY = "GoldSatchel_CheckHotkey"

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
]

# ============ RUNTIME STATE ============
satchel_serial = 0
enabled = True
is_expanded = True
session_gold = 0
last_scan_time = 0
last_error_time = 0
last_error_msg = ""
ERROR_COOLDOWN = 5.0

# GUI elements
gump = None
bg = None
statusLabel = None
satchelLabel = None
sessionLabel = None
errorLabel = None
enableBtn = None
bankBtn = None
checkBtn = None
retargetBtn = None
resetBtn = None
expandBtn = None
infoLabel = None
bankHotkeyBtn = None
checkHotkeyBtn = None

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
    """Returns the satchel item if valid, None otherwise"""
    if satchel_serial == 0:
        return None

    satchel = API.FindItem(satchel_serial)
    if not satchel:
        return None

    return satchel

def move_gold_to_satchel():
    """Move one gold pile from backpack to satchel"""
    global last_error_time, last_error_msg

    if not enabled:
        clear_error()
        return

    if satchel_serial == 0:
        set_error("No satchel set!")
        return

    satchel = get_satchel()
    if not satchel:
        set_error("Satchel not found!")
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

        debug_msg("Moving " + str(amount) + " gold (serial " + str(gold_serial) + ") to satchel " + str(satchel_serial))

        API.MoveItem(gold_serial, satchel_serial, amount, -1, -1)
        API.Pause(MOVE_PAUSE)

        check_item = get_gold_item()
        if check_item and check_item.Serial == gold_serial:
            set_error("Move failed - satchel may be full")
            return

        API.SysMsg("Moved " + str(amount) + " gold", 68)
        clear_error()

    except Exception as e:
        set_error("Move failed: " + str(e))
        debug_msg("Error moving gold: " + str(e))

def make_check():
    """Convert satchel gold to check: bank gold, cash checks, make new check"""
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
            API.SysMsg("No satchel set!", 32)
            return

        satchel = get_satchel()
        if not satchel:
            API.SysMsg("Satchel not found!", 32)
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
    """Move all gold from satchel to bank"""
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
            API.SysMsg("No satchel set!", 32)
            return

        satchel = get_satchel()
        if not satchel:
            API.SysMsg("Satchel not found!", 32)
            return

        items = API.ItemsInContainer(satchel_serial, False)
        if not items:
            API.SysMsg("No items in satchel", 43)
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
            API.SysMsg("Banked " + format(gold_moved, ',') + " gold from satchel", 68)
            update_display()
        else:
            API.SysMsg("No gold found in satchel", 43)

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
            if listening_for_action == "bank":
                bank_hotkey = key_name
                API.SavePersistentVar(BANK_HOTKEY_KEY, bank_hotkey, API.PersistentVar.Char)
                API.SysMsg("Bank bound to: " + key_name, 68)
                bankHotkeyBtn.SetBackgroundHue(66)  # Blue - more noticeable
                bankHotkeyBtn.SetText("[" + key_name + "]")
            elif listening_for_action == "check":
                check_hotkey = key_name
                API.SavePersistentVar(CHECK_HOTKEY_KEY, check_hotkey, API.PersistentVar.Char)
                API.SysMsg("Make Check bound to: " + key_name, 68)
                checkHotkeyBtn.SetBackgroundHue(66)  # Blue - more noticeable
                checkHotkeyBtn.SetText("[" + key_name + "]")

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
    bankHotkeyBtn.SetText("[?]")
    API.SysMsg("Press any key for Bank hotkey...", 38)

def start_capture_check_hotkey():
    """Start listening for check hotkey"""
    global listening_for_action
    listening_for_action = "check"
    checkHotkeyBtn.SetBackgroundHue(38)  # Purple
    checkHotkeyBtn.SetText("[?]")
    API.SysMsg("Press any key for Make Check hotkey...", 38)

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

    statusLabel.IsVisible = True
    satchelLabel.IsVisible = True
    sessionLabel.IsVisible = True
    errorLabel.IsVisible = True
    enableBtn.IsVisible = True
    retargetBtn.IsVisible = True
    resetBtn.IsVisible = True
    bankBtn.IsVisible = True
    checkBtn.IsVisible = True
    infoLabel.IsVisible = True
    bankHotkeyBtn.IsVisible = True
    checkHotkeyBtn.IsVisible = True

    x = gump.GetX()
    y = gump.GetY()
    gump.SetRect(x, y, WINDOW_WIDTH, EXPANDED_HEIGHT)
    bg.SetRect(0, 0, WINDOW_WIDTH, EXPANDED_HEIGHT)

def collapse_window():
    expandBtn.SetText("[+]")

    statusLabel.IsVisible = False
    satchelLabel.IsVisible = False
    sessionLabel.IsVisible = False
    errorLabel.IsVisible = False
    enableBtn.IsVisible = False
    retargetBtn.IsVisible = False
    resetBtn.IsVisible = False
    bankBtn.IsVisible = False
    checkBtn.IsVisible = False
    infoLabel.IsVisible = False
    bankHotkeyBtn.IsVisible = False
    checkHotkeyBtn.IsVisible = False

    x = gump.GetX()
    y = gump.GetY()
    gump.SetRect(x, y, WINDOW_WIDTH, COLLAPSED_HEIGHT)
    bg.SetRect(0, 0, WINDOW_WIDTH, COLLAPSED_HEIGHT)

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
    API.SysMsg("Gold Satchel: " + ("ENABLED" if enabled else "DISABLED"), 68 if enabled else 32)

def retarget_satchel():
    global satchel_serial

    API.SysMsg("Target your Gold Satchel container...", 68)

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
            debug_msg("Satchel serial set to: " + str(satchel_serial))
            clear_error()
            update_display()
            API.SysMsg("Gold Satchel set! Serial: 0x" + format(satchel_serial, 'X'), 68)
        else:
            API.SysMsg("Targeting cancelled", 53)
    except Exception as e:
        API.SysMsg("Error targeting: " + str(e), 32)

def reset_session():
    global session_gold
    session_gold = 0
    update_display()
    API.SysMsg("Banked counter reset", 68)

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
                statusLabel.SetText("Status: ENABLED (no satchel)")
            else:
                satchel = get_satchel()
                if satchel:
                    statusLabel.SetText("Status: ACTIVE")
                else:
                    statusLabel.SetText("Status: ENABLED (satchel not found)")
        else:
            statusLabel.SetText("Status: DISABLED")

        debug_msg("update_display: satchel_serial = " + str(satchel_serial))
        if satchel_serial == 0:
            satchelLabel.SetText("Satchel: [Not Set]")
        else:
            satchel = get_satchel()
            if satchel:
                satchelLabel.SetText("Satchel: 0x" + format(satchel_serial, 'X') + " [OK]")
            else:
                satchelLabel.SetText("Satchel: 0x" + format(satchel_serial, 'X') + " [NOT FOUND]")

        sessionLabel.SetText("Banked: " + format(session_gold, ',') + " gold")

        if last_error_msg:
            errorLabel.SetText("Error: " + last_error_msg)
        else:
            errorLabel.SetText("")

        enableBtn.SetText("[" + ("ON" if enabled else "OFF") + "]")
        enableBtn.SetBackgroundHue(68 if enabled else 32)

        bank_serial = API.Bank
        if bank_serial and bank_serial > 0:
            bankBtn.SetBackgroundHue(68)
        else:
            bankBtn.SetBackgroundHue(90)

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

load_expanded_state()

# ============ BUILD GUI ============
window_x = 100
window_y = 100

savedPos = API.GetPersistentVar(SETTINGS_KEY, str(window_x) + "," + str(window_y), API.PersistentVar.Char)
posXY = savedPos.split(',')
lastX = int(posXY[0])
lastY = int(posXY[1])

initial_height = EXPANDED_HEIGHT if is_expanded else COLLAPSED_HEIGHT

gump = API.Gumps.CreateGump()
gump.SetRect(lastX, lastY, WINDOW_WIDTH, initial_height)
API.Gumps.AddControlOnDisposed(gump, on_closed)

bg = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
bg.SetRect(0, 0, WINDOW_WIDTH, initial_height)
gump.Add(bg)

titleLabel = API.Gumps.CreateGumpTTFLabel("Gold Satchel", 16, "#ffaa00")
titleLabel.SetPos(5, 2)
gump.Add(titleLabel)

expandBtn = API.Gumps.CreateSimpleButton("[-]" if is_expanded else "[+]", 20, 18)
expandBtn.SetPos(115, 3)
expandBtn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(expandBtn, toggle_expand)
gump.Add(expandBtn)

leftMargin = 5
btnW = 65
btnH = 20
y = 26

statusLabel = API.Gumps.CreateGumpTTFLabel("Status: ACTIVE", 8, "#00ff00")
statusLabel.SetPos(leftMargin, y)
statusLabel.IsVisible = is_expanded
gump.Add(statusLabel)

y += 10
satchelLabel = API.Gumps.CreateGumpTTFLabel("Satchel: [Not Set]", 8, "#ff6666")
satchelLabel.SetPos(leftMargin, y)
satchelLabel.IsVisible = is_expanded
gump.Add(satchelLabel)

y += 14
sessionLabel = API.Gumps.CreateGumpTTFLabel("Banked: 0 gold", 12, "#ffcc00", aligned="center", maxWidth=WINDOW_WIDTH)
sessionLabel.SetPos(0, y)
sessionLabel.IsVisible = is_expanded
gump.Add(sessionLabel)

y += 16
errorLabel = API.Gumps.CreateGumpTTFLabel("", 7, "#ff3333")
errorLabel.SetPos(leftMargin, y)
errorLabel.IsVisible = is_expanded
gump.Add(errorLabel)

y += 14
enableBtn = API.Gumps.CreateSimpleButton("[ON]", btnW, btnH)
enableBtn.SetPos(leftMargin, y)
enableBtn.SetBackgroundHue(68)
enableBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(enableBtn, toggle_enabled)
gump.Add(enableBtn)

retargetBtn = API.Gumps.CreateSimpleButton("[TARGET]", btnW, btnH)
retargetBtn.SetPos(leftMargin + 65, y)
retargetBtn.SetBackgroundHue(66)
retargetBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(retargetBtn, retarget_satchel)
gump.Add(retargetBtn)

y += 22
resetBtn = API.Gumps.CreateSimpleButton("[RESET]", btnW, btnH)
resetBtn.SetPos(leftMargin, y)
resetBtn.SetBackgroundHue(53)
resetBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(resetBtn, reset_session)
gump.Add(resetBtn)

# BANK button with small hotkey button
bankBtn = API.Gumps.CreateSimpleButton("[BANK]", 45, btnH)
bankBtn.SetPos(leftMargin + 65, y)
bankBtn.SetBackgroundHue(90)
bankBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(bankBtn, move_satchel_to_bank)
gump.Add(bankBtn)

bankHotkeyBtn = API.Gumps.CreateSimpleButton("[" + bank_hotkey + "]", 18, btnH)
bankHotkeyBtn.SetPos(leftMargin + 65 + 47, y)
bankHotkeyBtn.SetBackgroundHue(66)  # Blue - stands out more
bankHotkeyBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(bankHotkeyBtn, start_capture_bank_hotkey)
gump.Add(bankHotkeyBtn)

y += 22
# MAKE CHECK button with small hotkey button
checkBtn = API.Gumps.CreateSimpleButton("[CHECK]", 110, btnH)
checkBtn.SetPos(leftMargin, y)
checkBtn.SetBackgroundHue(43)
checkBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(checkBtn, make_check)
gump.Add(checkBtn)

checkHotkeyBtn = API.Gumps.CreateSimpleButton("[" + check_hotkey + "]", 18, btnH)
checkHotkeyBtn.SetPos(leftMargin + 112, y)
checkHotkeyBtn.SetBackgroundHue(66)  # Blue - stands out more
checkHotkeyBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(checkHotkeyBtn, start_capture_check_hotkey)
gump.Add(checkHotkeyBtn)

y += 22
infoLabel = API.Gumps.CreateGumpTTFLabel("Blue [K] = click to rebind key", 7, "#888888", aligned="center", maxWidth=WINDOW_WIDTH)
infoLabel.SetPos(0, y)
infoLabel.IsVisible = is_expanded
gump.Add(infoLabel)

API.Gumps.AddGump(gump)

update_display()

# Register all possible keys
registered_count = 0
for key in ALL_KEYS:
    try:
        API.OnHotKey(key, make_key_handler(key))
        registered_count += 1
    except:
        pass

API.SysMsg("Gold Satchel v2.1 loaded! (" + str(registered_count) + " keys)", 68)
API.SysMsg("Bank: " + bank_hotkey + " | Check: " + check_hotkey + " | Blue [K]=rebind", 66)
if satchel_serial > 0:
    API.SysMsg("Satchel: 0x" + format(satchel_serial, 'X'), 66)
else:
    API.SysMsg("Click [TARGET] to set your satchel", 43)

# ============ MAIN LOOP ============
DISPLAY_UPDATE_INTERVAL = 0.5
next_scan = time.time() + SCAN_INTERVAL
next_display = time.time() + DISPLAY_UPDATE_INTERVAL

while not API.StopRequested:
    try:
        API.ProcessCallbacks()

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
