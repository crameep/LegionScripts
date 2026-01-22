# ============================================================
# Gold Satchel Auto-Mover v1.6
# by Coryigon for UO Unchained
# ============================================================
#
# Automatically moves gold from your backpack to a designated
# Gold Satchel container, and banks satchel gold when needed.
#
# Features:
#   - Collapsible interface (click [-] to minimize, [+] to expand)
#   - 2-second polling interval for backpack scans
#   - Searches ALL containers in backpack recursively (pouches, bags, etc.)
#   - Excludes gold already in the satchel (won't move satchel gold back to satchel)
#   - Moves one gold pile per scan (multiple piles handled across scans)
#   - BANK GOLD button - moves all gold from satchel to bank when bank is open
#   - MAKE CHECK button - automates: open bank, cash checks, bank satchel gold, make check
#   - Bank button turns green when bank is open
#   - Large readable counter shows total gold banked this session
#   - Enable/Disable toggle with persistent state
#   - Retarget button for changing satchel
#   - Unified UI design matching other utility scripts
#   - Safe handling of full satchels, missing satchels, and edge cases
#
# Hotkeys: None (GUI-driven)
#
# ============================================================
import API
import time

__version__ = "1.6"

# ============ USER SETTINGS ============
GOLD_GRAPHIC = 0x0EED          # Gold pile graphic ID
CHECK_GRAPHIC = 0x14F0         # Bank check graphic ID
SCAN_INTERVAL = 2.0            # Seconds between backpack scans
MOVE_PAUSE = 0.65              # Pause after each gold move for server response
DEBUG = False                  # Enable debug messages

# ============ GUI DIMENSIONS ============
WINDOW_WIDTH = 140
COLLAPSED_HEIGHT = 24
EXPANDED_HEIGHT = 235

# ============ PERSISTENCE KEYS ============
SATCHEL_KEY = "GoldSatchel_Serial"
ENABLED_KEY = "GoldSatchel_Enabled"
SETTINGS_KEY = "GoldSatchel_XY"
EXPANDED_KEY = "GoldSatchel_Expanded"

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

# ============ UTILITY FUNCTIONS ============
def debug_msg(text):
    """Print debug message if DEBUG is enabled"""
    if DEBUG:
        API.SysMsg("DEBUG: " + text, 88)

def get_gold_item():
    """Returns PyItem of first gold pile in backpack (not satchel!), or None

    Searches backpack AND all sub-containers recursively (pouches, bags, etc.)
    but excludes gold already in the satchel.

    Uses ItemsInContainer with recursive=True to properly search all nested
    containers and filter out satchel gold before returning.
    """
    global satchel_serial

    try:
        backpack = API.Player.Backpack
        if not backpack:
            return None

        backpack_serial = backpack.Serial

        # Get ALL items in backpack recursively (includes sub-containers)
        items = API.ItemsInContainer(backpack_serial, True)
        if not items:
            return None

        # Find first gold pile that's NOT in the satchel
        for item in items:
            # Check if it's gold
            if hasattr(item, 'Graphic') and item.Graphic == GOLD_GRAPHIC:
                # Exclude gold that's in the satchel
                if hasattr(item, 'Container') and satchel_serial > 0:
                    if item.Container == satchel_serial:
                        debug_msg("Skipping gold in satchel: " + str(item.Serial))
                        continue

                # Found valid gold pile!
                debug_msg("Found gold in backpack: " + str(item.Serial))
                return item

        # No gold found outside satchel
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
        clear_error()  # Clear any stale errors when disabled
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

        # CORRECT API: MoveItem(serial, destination, amt, x, y)
        # x and y are optional (default -1, -1 for auto-stack)
        debug_msg("Moving " + str(amount) + " gold (serial " + str(gold_serial) + ") to satchel " + str(satchel_serial))

        API.MoveItem(gold_serial, satchel_serial, amount, -1, -1)
        API.Pause(MOVE_PAUSE)

        # Verify it moved - if get_gold_item() returns the SAME serial, move failed
        check_item = get_gold_item()
        if check_item and check_item.Serial == gold_serial:
            set_error("Move failed - satchel may be full")
            return

        # Success! (don't count here, only count banked gold)
        API.SysMsg("Moved " + str(amount) + " gold", 68)
        clear_error()

    except Exception as e:
        set_error("Move failed: " + str(e))
        debug_msg("Error moving gold: " + str(e))

def make_check():
    """Convert satchel gold to check: bank gold, cash checks, make new check"""
    global session_gold, last_error_time, last_error_msg

    try:
        # Step 1: Say "bank" to open bank
        API.SysMsg("Opening bank...", 68)
        API.Msg("bank")
        API.Pause(1.5)

        # Check if bank opened
        bank_serial = API.Bank
        if not bank_serial or bank_serial == 0:
            API.SysMsg("Failed to open bank!", 32)
            return

        # Step 2: Check if satchel exists
        if satchel_serial == 0:
            API.SysMsg("No satchel set!", 32)
            return

        satchel = get_satchel()
        if not satchel:
            API.SysMsg("Satchel not found!", 32)
            return

        # Step 3: Say "banker balance" to see current balance
        API.SysMsg("Checking balance...", 68)
        API.Msg("banker balance")
        API.Pause(1.0)

        # Step 4: Cash all checks in bank
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

        # Step 5: Move all gold from satchel to bank
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

        # Step 6: Count total gold in bank
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

        # Step 7: Create check with all gold
        API.SysMsg("Creating check for " + format(total_gold, ',') + " gold...", 68)
        API.Msg("check " + str(total_gold))
        API.Pause(1.5)

        # Update session counter
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
        # Step 1: Say "bank" to open bank
        API.SysMsg("Opening bank...", 68)
        API.Msg("bank")
        API.Pause(1.5)

        # Step 2: Check if bank opened
        bank_serial = API.Bank
        if not bank_serial or bank_serial == 0:
            API.SysMsg("Bank is not open!", 32)
            return

        # Step 3: Check if satchel exists
        if satchel_serial == 0:
            API.SysMsg("No satchel set!", 32)
            return

        satchel = get_satchel()
        if not satchel:
            API.SysMsg("Satchel not found!", 32)
            return

        # Step 4: Get all items in satchel
        items = API.ItemsInContainer(satchel_serial, False)
        if not items:
            API.SysMsg("No items in satchel", 43)
            return

        # Step 5: Find and move all gold from satchel to bank
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
    """Set error message with cooldown"""
    global last_error_time, last_error_msg

    # Only update if different message or cooldown expired
    if msg != last_error_msg or (time.time() - last_error_time) > ERROR_COOLDOWN:
        last_error_msg = msg
        last_error_time = time.time()
        if msg:
            API.SysMsg(msg, 32)

def clear_error():
    """Clear error message"""
    global last_error_msg
    last_error_msg = ""

# ============ EXPAND/COLLAPSE ============
def toggle_expand():
    """Toggle between collapsed and expanded states"""
    global is_expanded

    is_expanded = not is_expanded
    save_expanded_state()

    if is_expanded:
        expand_window()
    else:
        collapse_window()

def expand_window():
    """Show all controls and resize window"""
    expandBtn.SetText("[-]")

    # Show all controls
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

    # Resize gump and background
    x = gump.GetX()
    y = gump.GetY()
    gump.SetRect(x, y, WINDOW_WIDTH, EXPANDED_HEIGHT)
    bg.SetRect(0, 0, WINDOW_WIDTH, EXPANDED_HEIGHT)

def collapse_window():
    """Hide all controls and shrink window"""
    expandBtn.SetText("[+]")

    # Hide all controls
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

    # Resize gump and background
    x = gump.GetX()
    y = gump.GetY()
    gump.SetRect(x, y, WINDOW_WIDTH, COLLAPSED_HEIGHT)
    bg.SetRect(0, 0, WINDOW_WIDTH, COLLAPSED_HEIGHT)

def save_expanded_state():
    """Save expanded state to persistence"""
    API.SavePersistentVar(EXPANDED_KEY, str(is_expanded), API.PersistentVar.Char)

def load_expanded_state():
    """Load expanded state from persistence"""
    global is_expanded
    saved = API.GetPersistentVar(EXPANDED_KEY, "True", API.PersistentVar.Char)
    is_expanded = (saved == "True")

# ============ GUI CALLBACKS ============
def toggle_enabled():
    """Toggle auto-move on/off"""
    global enabled
    enabled = not enabled
    API.SavePersistentVar(ENABLED_KEY, str(enabled), API.PersistentVar.Char)
    update_display()
    API.SysMsg("Gold Satchel: " + ("ENABLED" if enabled else "DISABLED"), 68 if enabled else 32)

def retarget_satchel():
    """Let user target a new satchel"""
    global satchel_serial  # CRITICAL: Must declare global to modify it!

    API.SysMsg("Target your Gold Satchel container...", 68)

    # Cancel any existing targets
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

            # Verify it's actually a container
            # Check for IsContainer attribute (some containers may not have it in Legion API)
            is_container = getattr(item, 'IsContainer', False)

            if not is_container:
                # Some containers might not have the IsContainer flag
                # Just warn but allow it - the user knows what they're targeting
                API.SysMsg("Warning: Target may not be a container", 43)

            # Save the satchel
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
    """Reset banked gold counter"""
    global session_gold
    session_gold = 0
    update_display()
    API.SysMsg("Banked counter reset", 68)

def on_closed():
    """Called when gump is closed"""
    try:
        # Save window position
        if gump:
            x = gump.GetX()
            y = gump.GetY()
            API.SavePersistentVar(SETTINGS_KEY, str(x) + "," + str(y), API.PersistentVar.Char)
    except:
        pass

# ============ DISPLAY UPDATES ============
def update_display():
    """Update all GUI elements"""
    if not gump:
        return

    try:
        # Update status (color set at creation, can't change dynamically)
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

        # Update satchel info
        debug_msg("update_display: satchel_serial = " + str(satchel_serial))
        if satchel_serial == 0:
            satchelLabel.SetText("Satchel: [Not Set]")
        else:
            satchel = get_satchel()
            if satchel:
                satchelLabel.SetText("Satchel: 0x" + format(satchel_serial, 'X') + " [OK]")
            else:
                satchelLabel.SetText("Satchel: 0x" + format(satchel_serial, 'X') + " [NOT FOUND]")

        # Update banked counter
        sessionLabel.SetText("Banked: " + format(session_gold, ',') + " gold")

        # Update error display
        if last_error_msg:
            errorLabel.SetText("Error: " + last_error_msg)
        else:
            errorLabel.SetText("")

        # Update enable button
        enableBtn.SetText("[" + ("ON" if enabled else "OFF") + "]")
        enableBtn.SetBackgroundHue(68 if enabled else 32)

        # Update bank button - green if bank is open, gray if closed
        bank_serial = API.Bank
        if bank_serial and bank_serial > 0:
            bankBtn.SetBackgroundHue(68)  # Green when bank is open
        else:
            bankBtn.SetBackgroundHue(90)  # Gray when bank is closed

    except Exception as e:
        API.SysMsg("Error updating display: " + str(e), 32)

# ============ INITIALIZATION ============
# Load persistent settings
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

# Load expanded state
load_expanded_state()

# ============ BUILD GUI ============
# Default window position
window_x = 100
window_y = 100

# Load window position
savedPos = API.GetPersistentVar(SETTINGS_KEY, str(window_x) + "," + str(window_y), API.PersistentVar.Char)
posXY = savedPos.split(',')
lastX = int(posXY[0])
lastY = int(posXY[1])

# Determine initial height
initial_height = EXPANDED_HEIGHT if is_expanded else COLLAPSED_HEIGHT

# Create gump with background
gump = API.Gumps.CreateGump()
gump.SetRect(lastX, lastY, WINDOW_WIDTH, initial_height)
API.Gumps.AddControlOnDisposed(gump, on_closed)

# Background
bg = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
bg.SetRect(0, 0, WINDOW_WIDTH, initial_height)
gump.Add(bg)

# Title bar
titleLabel = API.Gumps.CreateGumpTTFLabel("Gold Satchel", 10, "#ffaa00")
titleLabel.SetPos(5, 4)
gump.Add(titleLabel)

# Expand/collapse button
expandBtn = API.Gumps.CreateSimpleButton("[-]" if is_expanded else "[+]", 20, 18)
expandBtn.SetPos(115, 3)
expandBtn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(expandBtn, toggle_expand)
gump.Add(expandBtn)

# Constants
leftMargin = 5
btnW = 65
btnH = 20
y = 26

# Status
statusLabel = API.Gumps.CreateGumpTTFLabel("Status: ACTIVE", 8, "#00ff00")
statusLabel.SetPos(leftMargin, y)
statusLabel.IsVisible = is_expanded
gump.Add(statusLabel)

# Satchel info
y += 12
satchelLabel = API.Gumps.CreateGumpTTFLabel("Satchel: [Not Set]", 8, "#ff6666")
satchelLabel.SetPos(leftMargin, y)
satchelLabel.IsVisible = is_expanded
gump.Add(satchelLabel)

# Banked counter - BIG and centered
y += 16
sessionLabel = API.Gumps.CreateGumpTTFLabel("Banked: 0 gold", 13, "#ffcc00", aligned="center", maxWidth=WINDOW_WIDTH)
sessionLabel.SetPos(0, y)
sessionLabel.IsVisible = is_expanded
gump.Add(sessionLabel)

# Error display
y += 20
errorLabel = API.Gumps.CreateGumpTTFLabel("", 7, "#ff3333")
errorLabel.SetPos(leftMargin, y)
errorLabel.IsVisible = is_expanded
gump.Add(errorLabel)

# Buttons row 1
y += 16
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

# Buttons row 2
y += 24
resetBtn = API.Gumps.CreateSimpleButton("[RESET]", btnW, btnH)
resetBtn.SetPos(leftMargin, y)
resetBtn.SetBackgroundHue(53)
resetBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(resetBtn, reset_session)
gump.Add(resetBtn)

bankBtn = API.Gumps.CreateSimpleButton("[BANK]", btnW, btnH)
bankBtn.SetPos(leftMargin + 65, y)
bankBtn.SetBackgroundHue(90)
bankBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(bankBtn, move_satchel_to_bank)
gump.Add(bankBtn)

# Buttons row 3
y += 24
checkBtn = API.Gumps.CreateSimpleButton("[MAKE CHECK]", 130, btnH)
checkBtn.SetPos(leftMargin, y)
checkBtn.SetBackgroundHue(43)
checkBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(checkBtn, make_check)
gump.Add(checkBtn)

# Info label
y += 25
infoLabel = API.Gumps.CreateGumpTTFLabel("Scans every 2s", 7, "#888888", aligned="center", maxWidth=WINDOW_WIDTH)
infoLabel.SetPos(0, y)
infoLabel.IsVisible = is_expanded
gump.Add(infoLabel)

API.Gumps.AddGump(gump)

# Initial display update
update_display()

API.SysMsg("Gold Satchel v1.6 loaded!", 68)
if satchel_serial > 0:
    API.SysMsg("Satchel: 0x" + format(satchel_serial, 'X'), 66)
else:
    API.SysMsg("Click [RETARGET] to set your satchel", 43)

# ============ MAIN LOOP ============
DISPLAY_UPDATE_INTERVAL = 0.5
next_scan = time.time() + SCAN_INTERVAL
next_display = time.time() + DISPLAY_UPDATE_INTERVAL

while not API.StopRequested:
    try:
        # Process GUI callbacks - keeps buttons responsive
        API.ProcessCallbacks()

        # Scan for gold and move to satchel
        if enabled and time.time() >= next_scan:
            move_gold_to_satchel()
            next_scan = time.time() + SCAN_INTERVAL

        # Update display
        if time.time() >= next_display:
            update_display()
            next_display = time.time() + DISPLAY_UPDATE_INTERVAL

        # Small pause to prevent CPU spinning
        API.Pause(0.1)

    except Exception as e:
        API.SysMsg("Error in main loop: " + str(e), 32)
        debug_msg("Main loop exception: " + str(e))
        API.Pause(1)
