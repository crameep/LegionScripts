# ============================================================
# Hotkey Capture v1.1
# by Coryigon for TazUO Legion Scripts
# ============================================================
#
# Dynamic hotkey binding system. Click "Set Hotkey" button,
# then press any key to bind it to that action.
#
# Features:
#   - Click-to-capture hotkey assignment
#   - Visual feedback during capture mode
#   - Persistent hotkey storage
#   - Multiple action slots for testing
#   - Shows which key is bound to which action
#
# Pattern for implementing in your scripts:
#   1. Register all possible keys on startup
#   2. Check if in "listening mode" when key pressed
#   3. If listening, assign key to action
#   4. If not listening, execute the action
#
# ============================================================
import API
import time

__version__ = "1.1"

# ============ GUI COLORS ============
HUE_GREEN = 68
HUE_RED = 32
HUE_YELLOW = 43
HUE_GRAY = 90
HUE_BLUE = 66
HUE_PURPLE = 38

# ============ PERSISTENCE KEYS ============
SETTINGS_KEY = "HotkeyCapture_XY"
ACTION1_KEY = "HotkeyCapture_Action1Key"
ACTION2_KEY = "HotkeyCapture_Action2Key"
ACTION3_KEY = "HotkeyCapture_Action3Key"

# ============ STATE ============
action1_hotkey = "T"
action2_hotkey = "I"
action3_hotkey = "B"
listening_for_action = None  # Which action slot is waiting for a key (1, 2, 3, or None)
action_press_counts = {1: 0, 2: 0, 3: 0}

# ============ ALL POSSIBLE KEYS ============
# Register all these keys to capture any press
ALL_KEYS = [
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
    "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "NUMPAD0", "NUMPAD1", "NUMPAD2", "NUMPAD3", "NUMPAD4",
    "NUMPAD5", "NUMPAD6", "NUMPAD7", "NUMPAD8", "NUMPAD9",
    "TAB", "SPACE", "ENTER", "ESC", "PAUSE", "BACKSPACE",
    "HOME", "END", "PAGEUP", "PAGEDOWN", "INSERT", "DELETE",
    "LEFT", "RIGHT", "UP", "DOWN",
    "MULTIPLY", "ADD", "SUBTRACT", "DIVIDE", "DECIMAL",
]

# ============ ACTION CALLBACKS ============
def execute_action_1():
    """Example action 1 - Bandage Self"""
    global action_press_counts
    action_press_counts[1] += 1
    API.SysMsg("ACTION 1: Bandage Self (simulated)", HUE_GREEN)
    API.SysMsg("  Press count: " + str(action_press_counts[1]), HUE_GRAY)
    update_display()

def execute_action_2():
    """Example action 2 - Drink Heal Potion"""
    global action_press_counts
    action_press_counts[2] += 1
    API.SysMsg("ACTION 2: Drink Heal Potion (simulated)", HUE_BLUE)
    API.SysMsg("  Press count: " + str(action_press_counts[2]), HUE_GRAY)
    update_display()

def execute_action_3():
    """Example action 3 - Attack Target"""
    global action_press_counts
    action_press_counts[3] += 1
    API.SysMsg("ACTION 3: Attack Target (simulated)", HUE_YELLOW)
    API.SysMsg("  Press count: " + str(action_press_counts[3]), HUE_GRAY)
    update_display()

# ============ KEY CAPTURE SYSTEM ============
def make_key_handler(key_name):
    """Create a callback for a specific key"""
    def handler():
        global listening_for_action, action1_hotkey, action2_hotkey, action3_hotkey

        # If we're listening for a key assignment
        if listening_for_action is not None:
            # Assign this key to the action
            if listening_for_action == 1:
                action1_hotkey = key_name
                API.SavePersistentVar(ACTION1_KEY, action1_hotkey, API.PersistentVar.Char)
                API.SysMsg("Action 1 bound to: " + key_name, HUE_GREEN)
                setBtn1.SetBackgroundHue(HUE_GRAY)
                setBtn1.SetText("[Change: " + key_name + "]")
            elif listening_for_action == 2:
                action2_hotkey = key_name
                API.SavePersistentVar(ACTION2_KEY, action2_hotkey, API.PersistentVar.Char)
                API.SysMsg("Action 2 bound to: " + key_name, HUE_BLUE)
                setBtn2.SetBackgroundHue(HUE_GRAY)
                setBtn2.SetText("[Change: " + key_name + "]")
            elif listening_for_action == 3:
                action3_hotkey = key_name
                API.SavePersistentVar(ACTION3_KEY, action3_hotkey, API.PersistentVar.Char)
                API.SysMsg("Action 3 bound to: " + key_name, HUE_YELLOW)
                setBtn3.SetBackgroundHue(HUE_GRAY)
                setBtn3.SetText("[Change: " + key_name + "]")

            listening_for_action = None
            update_display()
            return

        # Not listening - execute the action if this key is bound
        if key_name == action1_hotkey:
            execute_action_1()
        elif key_name == action2_hotkey:
            execute_action_2()
        elif key_name == action3_hotkey:
            execute_action_3()

    return handler

# ============ GUI CALLBACKS ============
def start_capture_action_1():
    """Start listening for a key to bind to action 1"""
    global listening_for_action
    listening_for_action = 1
    setBtn1.SetBackgroundHue(HUE_PURPLE)
    setBtn1.SetText("[Listening...]")
    API.SysMsg("Press any key to bind to Action 1...", HUE_PURPLE)

def start_capture_action_2():
    """Start listening for a key to bind to action 2"""
    global listening_for_action
    listening_for_action = 2
    setBtn2.SetBackgroundHue(HUE_PURPLE)
    setBtn2.SetText("[Listening...]")
    API.SysMsg("Press any key to bind to Action 2...", HUE_PURPLE)

def start_capture_action_3():
    """Start listening for a key to bind to action 3"""
    global listening_for_action
    listening_for_action = 3
    setBtn3.SetBackgroundHue(HUE_PURPLE)
    setBtn3.SetText("[Listening...]")
    API.SysMsg("Press any key to bind to Action 3...", HUE_PURPLE)

def cancel_capture():
    """Cancel hotkey capture mode"""
    global listening_for_action
    if listening_for_action is not None:
        API.SysMsg("Hotkey capture cancelled", HUE_GRAY)
        listening_for_action = None
        setBtn1.SetBackgroundHue(HUE_GRAY)
        setBtn1.SetText("[Change: " + action1_hotkey + "]")
        setBtn2.SetBackgroundHue(HUE_GRAY)
        setBtn2.SetText("[Change: " + action2_hotkey + "]")
        setBtn3.SetBackgroundHue(HUE_GRAY)
        setBtn3.SetText("[Change: " + action3_hotkey + "]")

def reset_counts():
    """Reset action press counters"""
    global action_press_counts
    action_press_counts = {1: 0, 2: 0, 3: 0}
    update_display()
    API.SysMsg("Counters reset", HUE_GRAY)

def execute_action_1_manual():
    """Manually trigger action 1 from GUI"""
    execute_action_1()

def execute_action_2_manual():
    """Manually trigger action 2 from GUI"""
    execute_action_2()

def execute_action_3_manual():
    """Manually trigger action 3 from GUI"""
    execute_action_3()

# ============ DISPLAY UPDATES ============
def update_display():
    """Update all display labels"""
    action1Label.SetText("Action 1: Bandage Self [" + action1_hotkey + "] - Count: " + str(action_press_counts[1]))
    action2Label.SetText("Action 2: Heal Potion [" + action2_hotkey + "] - Count: " + str(action_press_counts[2]))
    action3Label.SetText("Action 3: Attack Target [" + action3_hotkey + "] - Count: " + str(action_press_counts[3]))

# ============ CLEANUP ============
def cleanup():
    """Cleanup on exit"""
    pass

def onClosed():
    """GUI closed callback"""
    cleanup()
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

action1_hotkey = API.GetPersistentVar(ACTION1_KEY, "T", API.PersistentVar.Char)
action2_hotkey = API.GetPersistentVar(ACTION2_KEY, "I", API.PersistentVar.Char)
action3_hotkey = API.GetPersistentVar(ACTION3_KEY, "B", API.PersistentVar.Char)

# ============ BUILD GUI ============
gump = API.Gumps.CreateGump()
API.Gumps.AddControlOnDisposed(gump, onClosed)

win_width = 500
win_height = 340
gump.SetRect(lastX, lastY, win_width, win_height)

# Background
bg = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
bg.SetRect(0, 0, win_width, win_height)
gump.Add(bg)

# Title
title = API.Gumps.CreateGumpTTFLabel("Hotkey Capture v" + __version__, 16, "#00d4ff", aligned="center", maxWidth=win_width)
title.SetPos(0, 5)
gump.Add(title)

# Instructions
instructions = API.Gumps.CreateGumpTTFLabel("Click [Set Hotkey] then press any key to bind | Purple = listening for key", 8, "#aaaaaa", aligned="center", maxWidth=win_width)
instructions.SetPos(0, 28)
gump.Add(instructions)

y = 55

# Action 1
action1Label = API.Gumps.CreateGumpTTFLabel("Action 1: Bandage Self [T] - Count: 0", 10, "#00ff00")
action1Label.SetPos(10, y)
gump.Add(action1Label)

y += 25

setBtn1 = API.Gumps.CreateSimpleButton("[Change: " + action1_hotkey + "]", 120, 22)
setBtn1.SetPos(10, y)
setBtn1.SetBackgroundHue(HUE_GRAY)
API.Gumps.AddControlOnClick(setBtn1, start_capture_action_1)
gump.Add(setBtn1)

testBtn1 = API.Gumps.CreateSimpleButton("[Test Action]", 100, 22)
testBtn1.SetPos(135, y)
testBtn1.SetBackgroundHue(HUE_GREEN)
API.Gumps.AddControlOnClick(testBtn1, execute_action_1_manual)
gump.Add(testBtn1)

y += 35

# Action 2
action2Label = API.Gumps.CreateGumpTTFLabel("Action 2: Heal Potion [I] - Count: 0", 10, "#00aaff")
action2Label.SetPos(10, y)
gump.Add(action2Label)

y += 25

setBtn2 = API.Gumps.CreateSimpleButton("[Change: " + action2_hotkey + "]", 120, 22)
setBtn2.SetPos(10, y)
setBtn2.SetBackgroundHue(HUE_GRAY)
API.Gumps.AddControlOnClick(setBtn2, start_capture_action_2)
gump.Add(setBtn2)

testBtn2 = API.Gumps.CreateSimpleButton("[Test Action]", 100, 22)
testBtn2.SetPos(135, y)
testBtn2.SetBackgroundHue(HUE_BLUE)
API.Gumps.AddControlOnClick(testBtn2, execute_action_2_manual)
gump.Add(testBtn2)

y += 35

# Action 3
action3Label = API.Gumps.CreateGumpTTFLabel("Action 3: Attack Target [B] - Count: 0", 10, "#ffaa00")
action3Label.SetPos(10, y)
gump.Add(action3Label)

y += 25

setBtn3 = API.Gumps.CreateSimpleButton("[Change: " + action3_hotkey + "]", 120, 22)
setBtn3.SetPos(10, y)
setBtn3.SetBackgroundHue(HUE_GRAY)
API.Gumps.AddControlOnClick(setBtn3, start_capture_action_3)
gump.Add(setBtn3)

testBtn3 = API.Gumps.CreateSimpleButton("[Test Action]", 100, 22)
testBtn3.SetPos(135, y)
testBtn3.SetBackgroundHue(HUE_YELLOW)
API.Gumps.AddControlOnClick(testBtn3, execute_action_3_manual)
gump.Add(testBtn3)

y += 40

# Divider
divider = API.Gumps.CreateGumpColorBox(0.3, "#ffffff")
divider.SetRect(10, y, win_width - 20, 1)
gump.Add(divider)

y += 15

# Control buttons
cancelBtn = API.Gumps.CreateSimpleButton("[Cancel Capture]", 140, 25)
cancelBtn.SetPos(10, y)
cancelBtn.SetBackgroundHue(HUE_RED)
API.Gumps.AddControlOnClick(cancelBtn, cancel_capture)
gump.Add(cancelBtn)

resetBtn = API.Gumps.CreateSimpleButton("[Reset Counters]", 140, 25)
resetBtn.SetPos(155, y)
resetBtn.SetBackgroundHue(HUE_GRAY)
API.Gumps.AddControlOnClick(resetBtn, reset_counts)
gump.Add(resetBtn)

y += 35

# Help text
helpLabel = API.Gumps.CreateGumpTTFLabel("How to use:", 10, "#ffaa00")
helpLabel.SetPos(10, y)
gump.Add(helpLabel)

y += 20

help1 = API.Gumps.CreateGumpTTFLabel("1. Click [Change: X] next to an action", 8, "#aaaaaa")
help1.SetPos(15, y)
gump.Add(help1)

y += 15

help2 = API.Gumps.CreateGumpTTFLabel("2. Button turns PURPLE - now press any key", 8, "#aaaaaa")
help2.SetPos(15, y)
gump.Add(help2)

y += 15

help3 = API.Gumps.CreateGumpTTFLabel("3. That key is now bound to the action", 8, "#aaaaaa")
help3.SetPos(15, y)
gump.Add(help3)

y += 15

help4 = API.Gumps.CreateGumpTTFLabel("4. Press the key in-game to trigger the action", 8, "#aaaaaa")
help4.SetPos(15, y)
gump.Add(help4)

API.Gumps.AddGump(gump)

# Register ALL possible keys with the handler system
API.SysMsg("Hotkey Capture v" + __version__ + " loaded!", HUE_GREEN)
API.SysMsg("Registering key handlers...", HUE_YELLOW)

registered_count = 0
for key in ALL_KEYS:
    try:
        API.OnHotKey(key, make_key_handler(key))
        registered_count += 1
    except Exception as e:
        # Skip keys that don't work
        pass

API.SysMsg("Registered " + str(registered_count) + " keys", HUE_GREEN)
API.SysMsg("", HUE_GRAY)
API.SysMsg("Current bindings:", HUE_YELLOW)
API.SysMsg("  Action 1 (Bandage): " + action1_hotkey, HUE_GREEN)
API.SysMsg("  Action 2 (Heal Pot): " + action2_hotkey, HUE_BLUE)
API.SysMsg("  Action 3 (Attack): " + action3_hotkey, HUE_YELLOW)

# Initial display update
update_display()

# ============ MAIN LOOP ============
while not API.StopRequested:
    try:
        # Process GUI clicks
        API.ProcessCallbacks()

        # Short pause
        API.Pause(0.1)

    except Exception as e:
        if "operation canceled" not in str(e).lower() and not API.StopRequested:
            API.SysMsg("Error: " + str(e), HUE_RED)
        API.Pause(1)

cleanup()
