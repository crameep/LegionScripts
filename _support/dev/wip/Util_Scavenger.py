# ============================================================
# Scavenger v1.0
# by Coryigon for UO Unchained
# ============================================================
#
# Automated scavenging using skinning knife AOE mechanic.
# Target yourself with the knife to scavenge nearby corpses.
#
# Features:
#   - Set your skinning knife (persistent storage)
#   - Auto-scavenge toggle with configurable cooldown
#   - Displays knife status and cooldown timer
#   - Manual scavenge button
#
# ============================================================
import API
import time

__version__ = "1.0"

# ============ USER SETTINGS ============
SCAVENGE_COOLDOWN = 2.0       # Seconds between auto-scavenges
TARGET_TIMEOUT = 5.0          # Timeout for knife targeting

# ============ PERSISTENCE KEYS ============
SETTINGS_KEY = "Scavenger_XY"
KNIFE_KEY = "Scavenger_KnifeSerial"
AUTO_SCAVENGE_KEY = "Scavenger_AutoScavenge"

# ============ GUI COLORS ============
HUE_GREEN = 68
HUE_RED = 32
HUE_YELLOW = 43
HUE_GRAY = 90
HUE_BLUE = 66

# ============ STATE ============
knife_serial = 0
auto_scavenge = False
last_scavenge_time = 0
status_message = "Ready"

# ============ UTILITY FUNCTIONS ============
def debug_msg(text):
    """Debug logging"""
    if False:  # Set to True for debugging
        API.SysMsg("DEBUG: " + text, 88)

def cancel_all_targets():
    """Cancel any active target cursors"""
    try:
        API.CancelTarget()
    except:
        pass
    try:
        API.CancelPreTarget()
    except:
        pass

def get_knife():
    """Get the knife item object"""
    global knife_serial
    if knife_serial == 0:
        return None
    return API.FindItem(knife_serial)

def scavenge():
    """Perform scavenge action - use knife on self"""
    global last_scavenge_time, status_message

    knife = get_knife()
    if not knife:
        API.SysMsg("No knife set! Click [Set Knife] first.", HUE_RED)
        status_message = "No knife set"
        update_status_display()
        return False

    try:
        # Use knife on self for AOE scavenge
        API.PreTarget(API.Player.Serial, "neutral")
        API.Pause(0.1)
        API.UseObject(knife, False)
        API.Pause(0.2)
        API.CancelPreTarget()

        last_scavenge_time = time.time()
        status_message = "Scavenging..."
        update_status_display()
        API.SysMsg("Scavenging...", HUE_GREEN)
        debug_msg("Used knife on self")
        return True

    except Exception as e:
        API.SysMsg("Scavenge error: " + str(e), HUE_RED)
        status_message = "Error"
        update_status_display()
        return False

# ============ GUI CALLBACKS ============
def on_set_knife():
    """Prompt user to target a knife"""
    global knife_serial, status_message

    API.SysMsg("Target your skinning knife...", HUE_YELLOW)
    status_message = "Target knife..."
    update_status_display()

    cancel_all_targets()
    target = API.RequestTarget(timeout=TARGET_TIMEOUT)

    if target:
        item = API.FindItem(target)
        if item:
            knife_serial = target
            API.SavePersistentVar(KNIFE_KEY, str(knife_serial), API.PersistentVar.Char)
            API.SysMsg("Knife set! Serial: 0x" + hex(knife_serial)[2:].upper(), HUE_GREEN)
            status_message = "Knife set!"
        else:
            API.SysMsg("Target not found!", HUE_RED)
            status_message = "Target not found"
    else:
        API.SysMsg("Knife targeting cancelled", HUE_YELLOW)
        status_message = "Cancelled"

    update_knife_display()
    update_status_display()

def on_manual_scavenge():
    """Manual scavenge button"""
    scavenge()

def toggle_auto_scavenge():
    """Toggle auto-scavenge"""
    global auto_scavenge
    auto_scavenge = not auto_scavenge

    # Save to persistence
    API.SavePersistentVar(AUTO_SCAVENGE_KEY, str(auto_scavenge), API.PersistentVar.Char)

    # Update button
    color = HUE_GREEN if auto_scavenge else HUE_GRAY
    text = "[AUTO-SCAVENGE:" + ("ON" if auto_scavenge else "OFF") + "]"
    autoScavengeBtn.SetBackgroundHue(color)
    autoScavengeBtn.SetText(text)

    API.SysMsg("Auto-scavenge: " + ("ON" if auto_scavenge else "OFF"), color)

# ============ DISPLAY UPDATES ============
def update_status_display():
    """Update status label"""
    statusLabel.SetText(status_message)

def update_knife_display():
    """Update knife serial display"""
    if knife_serial > 0:
        knife = get_knife()
        if knife:
            text = "Knife: 0x" + hex(knife_serial)[2:].upper() + " (Found)"
            knifeLabel.SetText(text)
        else:
            text = "Knife: 0x" + hex(knife_serial)[2:].upper() + " (NOT FOUND)"
            knifeLabel.SetText(text)
    else:
        knifeLabel.SetText("Knife: Not Set")

def update_cooldown_display():
    """Update cooldown timer"""
    if last_scavenge_time == 0:
        cooldownLabel.SetText("Cooldown: Ready")
        return

    elapsed = time.time() - last_scavenge_time
    remaining = max(0, SCAVENGE_COOLDOWN - elapsed)

    if remaining > 0:
        cooldownLabel.SetText("Cooldown: " + str(round(remaining, 1)) + "s")
    else:
        cooldownLabel.SetText("Cooldown: Ready")

# ============ CLEANUP ============
def cleanup():
    """Cleanup on exit"""
    pass

def onClosed():
    """GUI closed callback"""
    cleanup()
    # Save window position
    try:
        pos = str(gump.GetX()) + "," + str(gump.GetY())
        API.SavePersistentVar(SETTINGS_KEY, pos, API.PersistentVar.Char)
    except:
        pass
    API.Stop()

# ============ INITIALIZATION ============
# Load settings
savedPos = API.GetPersistentVar(SETTINGS_KEY, "100,100", API.PersistentVar.Char)
posXY = savedPos.split(',')
lastX = int(posXY[0])
lastY = int(posXY[1])

knife_serial = int(API.GetPersistentVar(KNIFE_KEY, "0", API.PersistentVar.Char))
auto_scavenge = API.GetPersistentVar(AUTO_SCAVENGE_KEY, "False", API.PersistentVar.Char) == "True"

# ============ BUILD GUI ============
gump = API.Gumps.CreateGump()
API.Gumps.AddControlOnDisposed(gump, onClosed)

# Window size
win_width = 280
win_height = 160
gump.SetRect(lastX, lastY, win_width, win_height)

# Background
bg = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
bg.SetRect(0, 0, win_width, win_height)
gump.Add(bg)

# Title
title = API.Gumps.CreateGumpTTFLabel("Scavenger v" + __version__, 16, "#00d4ff", aligned="center", maxWidth=win_width)
title.SetPos(0, 5)
gump.Add(title)

# Instructions
instructions = API.Gumps.CreateGumpTTFLabel("Set knife then toggle auto-scavenge | AOE scavenge on self", 8, "#aaaaaa", aligned="center", maxWidth=win_width)
instructions.SetPos(0, 28)
gump.Add(instructions)

y = 55

# Knife display
knifeLabel = API.Gumps.CreateGumpTTFLabel("Knife: Not Set", 10, "#ffaa00")
knifeLabel.SetPos(10, y)
gump.Add(knifeLabel)

y += 20

# Cooldown display
cooldownLabel = API.Gumps.CreateGumpTTFLabel("Cooldown: Ready", 10, "#00ff00")
cooldownLabel.SetPos(10, y)
gump.Add(cooldownLabel)

y += 30

# Set Knife button
setKnifeBtn = API.Gumps.CreateSimpleButton("[Set Knife]", 130, 22)
setKnifeBtn.SetPos(10, y)
setKnifeBtn.SetBackgroundHue(HUE_YELLOW)
API.Gumps.AddControlOnClick(setKnifeBtn, on_set_knife)
gump.Add(setKnifeBtn)

# Manual Scavenge button
manualBtn = API.Gumps.CreateSimpleButton("[Scavenge Now]", 130, 22)
manualBtn.SetPos(145, y)
manualBtn.SetBackgroundHue(HUE_BLUE)
API.Gumps.AddControlOnClick(manualBtn, on_manual_scavenge)
gump.Add(manualBtn)

y += 27

# Auto-scavenge toggle
autoScavengeBtn = API.Gumps.CreateSimpleButton("[AUTO-SCAVENGE:" + ("ON" if auto_scavenge else "OFF") + "]", 265, 22)
autoScavengeBtn.SetPos(10, y)
autoScavengeBtn.SetBackgroundHue(HUE_GREEN if auto_scavenge else HUE_GRAY)
API.Gumps.AddControlOnClick(autoScavengeBtn, toggle_auto_scavenge)
gump.Add(autoScavengeBtn)

y += 27

# Status bar
statusBg = API.Gumps.CreateGumpColorBox(0.9, "#000000")
statusBg.SetRect(5, y, win_width - 10, 20)
gump.Add(statusBg)

statusLabel = API.Gumps.CreateGumpTTFLabel("Ready", 9, "#00ff00")
statusLabel.SetPos(10, y + 3)
gump.Add(statusLabel)

API.Gumps.AddGump(gump)

# Initial display update
update_knife_display()
update_cooldown_display()
API.SysMsg("Scavenger v" + __version__ + " loaded!", HUE_GREEN)

# ============ MAIN LOOP ============
DISPLAY_INTERVAL = 0.3
next_display = time.time() + DISPLAY_INTERVAL

while not API.StopRequested:
    try:
        # Process GUI clicks
        API.ProcessCallbacks()

        # Auto-scavenge logic
        if auto_scavenge:
            elapsed = time.time() - last_scavenge_time
            if elapsed >= SCAVENGE_COOLDOWN:
                scavenge()

        # Update display periodically
        if time.time() > next_display:
            update_cooldown_display()
            update_knife_display()
            next_display = time.time() + DISPLAY_INTERVAL

        # Short pause
        API.Pause(0.1)

    except Exception as e:
        if "operation canceled" not in str(e).lower() and not API.StopRequested:
            API.SysMsg("Error: " + str(e), HUE_RED)
            status_message = "Error: " + str(e)
            update_status_display()
        API.Pause(1)

cleanup()
