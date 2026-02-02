# ============================================================
# Hotkey Tester v1.0
# by Coryigon for TazUO Legion Scripts
# ============================================================
#
# Test utility for capturing and testing hotkey bindings.
# Helps figure out key names and test hotkey callbacks.
#
# Features:
#   - Test common key names to see which work
#   - Register test hotkeys and see when they fire
#   - Display last key pressed
#   - Shows API.OnHotKey syntax examples
#
# ============================================================
import API
import time

__version__ = "1.0"

# ============ GUI COLORS ============
HUE_GREEN = 68
HUE_RED = 32
HUE_YELLOW = 43
HUE_GRAY = 90
HUE_BLUE = 66

# ============ PERSISTENCE KEYS ============
SETTINGS_KEY = "HotkeyTester_XY"
TEST_KEY_1 = "HotkeyTester_Key1"
TEST_KEY_2 = "HotkeyTester_Key2"
TEST_KEY_3 = "HotkeyTester_Key3"

# ============ STATE ============
test_hotkey_1 = "F1"
test_hotkey_2 = "F2"
test_hotkey_3 = "F3"
last_key_pressed = "None"
key_press_count = 0
listening_mode = False
listen_start_time = 0
LISTEN_TIMEOUT = 5.0

# ============ COMMON KEY NAMES ============
# Based on typical Legion/UO key names
COMMON_KEYS = [
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "0",
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
    "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",
    "TAB", "SPACE", "ENTER", "ESC", "PAUSE", "HOME", "END", "PAGEUP", "PAGEDOWN",
    "LEFT", "RIGHT", "UP", "DOWN", "INSERT", "DELETE",
    "NUMPAD0", "NUMPAD1", "NUMPAD2", "NUMPAD3", "NUMPAD4",
    "NUMPAD5", "NUMPAD6", "NUMPAD7", "NUMPAD8", "NUMPAD9",
    "CTRL+A", "CTRL+S", "CTRL+D", "CTRL+F",
    "SHIFT+A", "SHIFT+S", "SHIFT+D", "SHIFT+F",
    "ALT+A", "ALT+S", "ALT+D", "ALT+F"
]

# ============ HOTKEY CALLBACKS ============
def on_test_key_1():
    """Callback for test hotkey 1"""
    global last_key_pressed, key_press_count
    last_key_pressed = test_hotkey_1 + " (TEST 1)"
    key_press_count += 1
    API.SysMsg("TEST KEY 1 PRESSED: " + test_hotkey_1, HUE_GREEN)
    update_display()

def on_test_key_2():
    """Callback for test hotkey 2"""
    global last_key_pressed, key_press_count
    last_key_pressed = test_hotkey_2 + " (TEST 2)"
    key_press_count += 1
    API.SysMsg("TEST KEY 2 PRESSED: " + test_hotkey_2, HUE_BLUE)
    update_display()

def on_test_key_3():
    """Callback for test hotkey 3"""
    global last_key_pressed, key_press_count
    last_key_pressed = test_hotkey_3 + " (TEST 3)"
    key_press_count += 1
    API.SysMsg("TEST KEY 3 PRESSED: " + test_hotkey_3, HUE_YELLOW)
    update_display()

# ============ UTILITY FUNCTIONS ============
def register_test_hotkeys():
    """Register all test hotkeys"""
    try:
        if test_hotkey_1:
            API.OnHotKey(test_hotkey_1, on_test_key_1)
            API.SysMsg("Registered: " + test_hotkey_1, HUE_GRAY)
    except Exception as e:
        API.SysMsg("Failed to register " + test_hotkey_1 + ": " + str(e), HUE_RED)

    try:
        if test_hotkey_2:
            API.OnHotKey(test_hotkey_2, on_test_key_2)
            API.SysMsg("Registered: " + test_hotkey_2, HUE_GRAY)
    except Exception as e:
        API.SysMsg("Failed to register " + test_hotkey_2 + ": " + str(e), HUE_RED)

    try:
        if test_hotkey_3:
            API.OnHotKey(test_hotkey_3, on_test_key_3)
            API.SysMsg("Registered: " + test_hotkey_3, HUE_GRAY)
    except Exception as e:
        API.SysMsg("Failed to register " + test_hotkey_3 + ": " + str(e), HUE_RED)

# ============ GUI CALLBACKS ============
def cycle_test_key_1():
    """Cycle through common keys for test slot 1"""
    global test_hotkey_1
    try:
        current_index = COMMON_KEYS.index(test_hotkey_1)
        next_index = (current_index + 1) % len(COMMON_KEYS)
        test_hotkey_1 = COMMON_KEYS[next_index]
    except:
        test_hotkey_1 = COMMON_KEYS[0]

    API.SavePersistentVar(TEST_KEY_1, test_hotkey_1, API.PersistentVar.Char)
    update_display()
    API.SysMsg("Test Key 1: " + test_hotkey_1 + " (restart to apply)", HUE_YELLOW)

def cycle_test_key_2():
    """Cycle through common keys for test slot 2"""
    global test_hotkey_2
    try:
        current_index = COMMON_KEYS.index(test_hotkey_2)
        next_index = (current_index + 1) % len(COMMON_KEYS)
        test_hotkey_2 = COMMON_KEYS[next_index]
    except:
        test_hotkey_2 = COMMON_KEYS[0]

    API.SavePersistentVar(TEST_KEY_2, test_hotkey_2, API.PersistentVar.Char)
    update_display()
    API.SysMsg("Test Key 2: " + test_hotkey_2 + " (restart to apply)", HUE_YELLOW)

def cycle_test_key_3():
    """Cycle through common keys for test slot 3"""
    global test_hotkey_3
    try:
        current_index = COMMON_KEYS.index(test_hotkey_3)
        next_index = (current_index + 1) % len(COMMON_KEYS)
        test_hotkey_3 = COMMON_KEYS[next_index]
    except:
        test_hotkey_3 = COMMON_KEYS[0]

    API.SavePersistentVar(TEST_KEY_3, test_hotkey_3, API.PersistentVar.Char)
    update_display()
    API.SysMsg("Test Key 3: " + test_hotkey_3 + " (restart to apply)", HUE_YELLOW)

def reset_counter():
    """Reset key press counter"""
    global key_press_count, last_key_pressed
    key_press_count = 0
    last_key_pressed = "None"
    update_display()
    API.SysMsg("Counter reset", HUE_GRAY)

def show_api_help():
    """Show API usage examples"""
    API.SysMsg("=== Legion Hotkey API Examples ===", HUE_BLUE)
    API.SysMsg("", HUE_GRAY)
    API.SysMsg("Basic registration:", HUE_YELLOW)
    API.SysMsg('  API.OnHotKey("F1", my_callback)', HUE_GRAY)
    API.SysMsg("", HUE_GRAY)
    API.SysMsg("With modifiers:", HUE_YELLOW)
    API.SysMsg('  API.OnHotKey("CTRL+A", my_callback)', HUE_GRAY)
    API.SysMsg('  API.OnHotKey("SHIFT+1", my_callback)', HUE_GRAY)
    API.SysMsg('  API.OnHotKey("ALT+F1", my_callback)', HUE_GRAY)
    API.SysMsg("", HUE_GRAY)
    API.SysMsg("Common keys:", HUE_YELLOW)
    API.SysMsg("  F1-F12, TAB, SPACE, ENTER, ESC, PAUSE", HUE_GRAY)
    API.SysMsg("  Letters: A-Z, Numbers: 0-9", HUE_GRAY)
    API.SysMsg("  Arrows: LEFT, RIGHT, UP, DOWN", HUE_GRAY)
    API.SysMsg("  NUMPAD0-NUMPAD9, HOME, END, PAGEUP, PAGEDOWN", HUE_GRAY)

# ============ DISPLAY UPDATES ============
def update_display():
    """Update all display labels"""
    testKey1Label.SetText("Test Key 1: " + test_hotkey_1)
    testKey2Label.SetText("Test Key 2: " + test_hotkey_2)
    testKey3Label.SetText("Test Key 3: " + test_hotkey_3)
    lastKeyLabel.SetText("Last Key: " + last_key_pressed)
    counterLabel.SetText("Press Count: " + str(key_press_count))

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

test_hotkey_1 = API.GetPersistentVar(TEST_KEY_1, "F1", API.PersistentVar.Char)
test_hotkey_2 = API.GetPersistentVar(TEST_KEY_2, "F2", API.PersistentVar.Char)
test_hotkey_3 = API.GetPersistentVar(TEST_KEY_3, "F3", API.PersistentVar.Char)

# ============ BUILD GUI ============
gump = API.Gumps.CreateGump()
API.Gumps.AddControlOnDisposed(gump, onClosed)

win_width = 400
win_height = 380
gump.SetRect(lastX, lastY, win_width, win_height)

# Background
bg = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
bg.SetRect(0, 0, win_width, win_height)
gump.Add(bg)

# Title
title = API.Gumps.CreateGumpTTFLabel("Hotkey Tester v" + __version__, 16, "#00d4ff", aligned="center", maxWidth=win_width)
title.SetPos(0, 5)
gump.Add(title)

# Instructions
instructions = API.Gumps.CreateGumpTTFLabel("Click buttons to cycle through keys | Press keys to test | Restart to apply changes", 8, "#aaaaaa", aligned="center", maxWidth=win_width)
instructions.SetPos(0, 28)
gump.Add(instructions)

y = 55

# Test Key 1
testKey1Label = API.Gumps.CreateGumpTTFLabel("Test Key 1: " + test_hotkey_1, 11, "#00ff00")
testKey1Label.SetPos(10, y)
gump.Add(testKey1Label)

cycleBtn1 = API.Gumps.CreateSimpleButton("[Cycle Key]", 120, 22)
cycleBtn1.SetPos(260, y - 2)
cycleBtn1.SetBackgroundHue(HUE_GREEN)
API.Gumps.AddControlOnClick(cycleBtn1, cycle_test_key_1)
gump.Add(cycleBtn1)

y += 30

# Test Key 2
testKey2Label = API.Gumps.CreateGumpTTFLabel("Test Key 2: " + test_hotkey_2, 11, "#00aaff")
testKey2Label.SetPos(10, y)
gump.Add(testKey2Label)

cycleBtn2 = API.Gumps.CreateSimpleButton("[Cycle Key]", 120, 22)
cycleBtn2.SetPos(260, y - 2)
cycleBtn2.SetBackgroundHue(HUE_BLUE)
API.Gumps.AddControlOnClick(cycleBtn2, cycle_test_key_2)
gump.Add(cycleBtn2)

y += 30

# Test Key 3
testKey3Label = API.Gumps.CreateGumpTTFLabel("Test Key 3: " + test_hotkey_3, 11, "#ffaa00")
testKey3Label.SetPos(10, y)
gump.Add(testKey3Label)

cycleBtn3 = API.Gumps.CreateSimpleButton("[Cycle Key]", 120, 22)
cycleBtn3.SetPos(260, y - 2)
cycleBtn3.SetBackgroundHue(HUE_YELLOW)
API.Gumps.AddControlOnClick(cycleBtn3, cycle_test_key_3)
gump.Add(cycleBtn3)

y += 40

# Divider
divider = API.Gumps.CreateGumpColorBox(0.3, "#ffffff")
divider.SetRect(10, y, win_width - 20, 1)
gump.Add(divider)

y += 10

# Last key pressed
lastKeyLabel = API.Gumps.CreateGumpTTFLabel("Last Key: None", 11, "#ffffff")
lastKeyLabel.SetPos(10, y)
gump.Add(lastKeyLabel)

y += 25

# Counter
counterLabel = API.Gumps.CreateGumpTTFLabel("Press Count: 0", 11, "#ffffff")
counterLabel.SetPos(10, y)
gump.Add(counterLabel)

resetBtn = API.Gumps.CreateSimpleButton("[Reset]", 80, 22)
resetBtn.SetPos(300, y - 2)
resetBtn.SetBackgroundHue(HUE_GRAY)
API.Gumps.AddControlOnClick(resetBtn, reset_counter)
gump.Add(resetBtn)

y += 40

# Divider
divider2 = API.Gumps.CreateGumpColorBox(0.3, "#ffffff")
divider2.SetRect(10, y, win_width - 20, 1)
gump.Add(divider2)

y += 10

# Help section
helpTitle = API.Gumps.CreateGumpTTFLabel("Available Keys:", 10, "#ffaa00")
helpTitle.SetPos(10, y)
gump.Add(helpTitle)

y += 20

helpText1 = API.Gumps.CreateGumpTTFLabel("F1-F12, TAB, SPACE, ENTER, ESC, PAUSE", 8, "#aaaaaa")
helpText1.SetPos(10, y)
gump.Add(helpText1)

y += 15

helpText2 = API.Gumps.CreateGumpTTFLabel("A-Z, 0-9, LEFT, RIGHT, UP, DOWN", 8, "#aaaaaa")
helpText2.SetPos(10, y)
gump.Add(helpText2)

y += 15

helpText3 = API.Gumps.CreateGumpTTFLabel("NUMPAD0-9, HOME, END, PAGEUP, PAGEDOWN", 8, "#aaaaaa")
helpText3.SetPos(10, y)
gump.Add(helpText3)

y += 15

helpText4 = API.Gumps.CreateGumpTTFLabel("Modifiers: CTRL+, SHIFT+, ALT+", 8, "#aaaaaa")
helpText4.SetPos(10, y)
gump.Add(helpText4)

y += 30

# Show API help button
apiHelpBtn = API.Gumps.CreateSimpleButton("[Show API Examples]", 200, 25)
apiHelpBtn.SetPos(100, y)
apiHelpBtn.SetBackgroundHue(HUE_BLUE)
API.Gumps.AddControlOnClick(apiHelpBtn, show_api_help)
gump.Add(apiHelpBtn)

API.Gumps.AddGump(gump)

# Register test hotkeys
API.SysMsg("Hotkey Tester v" + __version__ + " loaded!", HUE_GREEN)
API.SysMsg("Registering test hotkeys...", HUE_YELLOW)
register_test_hotkeys()
API.SysMsg("Press your test keys to verify they work!", HUE_GREEN)
API.SysMsg("Use [Cycle Key] to change assignments (restart required)", HUE_YELLOW)

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
