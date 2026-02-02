# Tamer Suite v2.0 Design Specification

**Script Architect:** Claude (design only - no implementation code)
**Target File:** `/mnt/g/Ultima Online/TazUO-Launcher.win-x64/TazUO/LegionScripts/CoryCustom/Test/Tamer_Suite_v2.py`
**Base Version:** Tamer_Suite v2.4 (Tamer/Tamer_Suite.py)
**Reference Patterns:** UI_STANDARDS.md, Util_Runebook_Hotkeys.py, Util_GoldSatchel.py

---

## Summary

Refactor Tamer_Suite to use modern UI patterns with:
1. Collapsible config panel [C] button
2. Customizable hotkeys via click-to-capture system
3. Dynamic window sizing (normal vs config mode)
4. All existing functionality preserved

---

## 1. Features

### Must Have (MVP)
- [x] All existing v2.4 functionality preserved (healing, commands, pets, etc.)
- [x] Config panel toggle via [C] button in title bar
- [x] Customizable hotkeys for: PAUSE, ALL KILL, GUARD, FOLLOW, STAY
- [x] Click-to-capture hotkey binding (purple = listening)
- [x] ESC to cancel hotkey capture
- [x] Persist hotkey bindings per-character
- [x] Dynamic window width (normal vs config mode)
- [x] [-]/[+] expand/collapse preserved

### Should Have
- [ ] Visual hotkey display on command buttons showing current binding
- [ ] Hotkey conflict warnings (same key for multiple actions)
- [ ] "Clear" option for each hotkey binding

### Could Have
- [ ] Import/export hotkey settings
- [ ] Hotkey modifier support display (CTRL+, ALT+, SHIFT+)
- [ ] Sound toggle in config panel

---

## 2. Architecture Overview

**Pattern**: State Machine (existing) + Hotkey Capture System (new)

**Components**:
- **Healing State Machine**: Unchanged - handles heal/rez/vetkit timing
- **Hotkey Capture System**: New - registers all keys, routes to capture or action
- **Config Panel Manager**: New - handles show/hide with window resizing
- **Display Manager**: Enhanced - updates button labels with hotkey info

**Data Flow**:
```
Key Press -> make_key_handler() -> capturing_for != None?
                                     Yes -> Assign hotkey, save, update UI
                                     No  -> Execute bound action
```

---

## 3. Window Layout

### Current Dimensions (v2.4)
```
WINDOW_WIDTH = 400
COLLAPSED_HEIGHT = 24
EXPANDED_HEIGHT = 430
```

### New Dimensions (v2.0)
```
WINDOW_WIDTH_NORMAL = 400   # Same as current
WINDOW_WIDTH_CONFIG = 435   # Expanded for hotkey column (35px extra)
COLLAPSED_HEIGHT = 24
EXPANDED_HEIGHT = 430
CONFIG_HEIGHT = 540         # Normal + config panel (110px for 5 hotkeys)
```

---

## 4. GUI Layout

### 4.1 Title Bar (y=3)
```
+-----------------------------------------------------------------+
| Tamer Suite v2.0                              [C]  [-]          |
+-----------------------------------------------------------------+
   ^                                             ^    ^
   Title (16pt cyan)                        Config  Expand
                                             (20x18) (20x18)
```

**Title bar button positions (normal 400px width):**
- [C] config button: x = 350, y = 3
- [-] expand button: x = 375, y = 3

**Title bar button positions (config 435px width):**
- [C] config button: x = 385, y = 3
- [-] expand button: x = 410, y = 3

### 4.2 Existing Main Content (y=24 to y=430)
All existing GUI elements stay exactly the same:
- Bandage count (centered top)
- Left panel: Healer controls
- Right panel: Commands
- Bottom panel: Pets list

### 4.3 New Config Panel (y=430, visible only in config mode)
```
+-----------------------------------------------------------------+
| === HOTKEY CONFIGURATION ===                                     |
| Click button, press key to bind (ESC to cancel)                  |
+-----------------------------------------------------------------+
| Pause:        [PAUSE]     <-- click to capture, shows current    |
| All Kill:     [TAB]                                              |
| Guard:        [1]                                                |
| Follow:       [2]                                                |
| Stay:         [---]       <-- gray if unbound                    |
+-----------------------------------------------------------------+
| [DONE]                                                           |
+-----------------------------------------------------------------+
```

**Config Panel Layout Details:**
```python
CONFIG_Y = 430  # Start of config panel

# Background
configBg: x=0, y=430, w=435, h=110

# Title
configTitle: x=5, y=433, text="=== HOTKEY CONFIGURATION ==="

# Help text
configHelp: x=5, y=448, text="Click button, press key to bind (ESC cancel)"

# Hotkey rows (y starts at 465, each row 20px apart)
row_y = 465
ROW_HEIGHT = 20
LABEL_X = 5
BUTTON_X = 70
BUTTON_W = 95
BUTTON_H = 18

# Row 1: Pause
pauseHkLabel: x=5, y=468, text="Pause:"
pauseHkBtn: x=70, y=465, w=95, h=18, text="[PAUSE]"

# Row 2: All Kill
killHkLabel: x=5, y=488, text="All Kill:"
killHkBtn: x=70, y=485, w=95, h=18, text="[TAB]"

# Row 3: Guard
guardHkLabel: x=5, y=508, text="Guard:"
guardHkBtn: x=70, y=505, w=95, h=18, text="[1]"

# Row 4: Follow
followHkLabel: x=5, y=528, text="Follow:"
followHkBtn: x=70, y=525, w=95, h=18, text="[2]"

# Row 5: Stay (column 2 to save space)
stayHkLabel: x=180, y=468, text="Stay:"
stayHkBtn: x=230, y=465, w=95, h=18, text="[---]"

# Done button
configDoneBtn: x=5, y=550, w=160, h=20, text="[DONE]"
```

**Alternative: 2-Column Layout (more compact):**
```
+-----------------------------------------------------------------+
| === HOTKEY CONFIG === (ESC to cancel)                            |
+-----------------------------------------------------------------+
|  Pause: [PAUSE]    |  Kill: [TAB]                                |
|  Guard: [1]        |  Follow: [2]                                |
|  Stay:  [---]      |  [DONE]                                     |
+-----------------------------------------------------------------+
```
This fits in 85px height instead of 110px.

---

## 5. State Variables (New)

```python
# Config panel state
show_config = False           # Is config panel visible?

# Hotkey capture state
capturing_for = None          # "pause", "kill", "guard", "follow", "stay", or None

# Hotkey bindings (loaded from persistence)
hotkeys = {
    "pause": "PAUSE",
    "kill": "TAB",
    "guard": "1",
    "follow": "2",
    "stay": ""              # Empty = unbound
}
```

---

## 6. Persistence Keys

### Existing Keys (preserve)
```python
SETTINGS_KEY = "TamerSuite_XY"
MAGERY_KEY = "TamerSuite_UseMagery"
REZ_KEY = "TamerSuite_UseRez"
HEALSELF_KEY = "TamerSuite_HealSelf"
TANK_KEY = "TamerSuite_Tank"
VETKIT_KEY = "TamerSuite_VetKitGraphic"
REDS_KEY = "TamerSuite_Reds"
GRAYS_KEY = "TamerSuite_Grays"
MODE_KEY = "TamerSuite_Mode"
SKIPOOR_KEY = "TamerSuite_SkipOOR"
PETACTIVE_KEY = "TamerSuite_PetActive"
POTION_KEY = "TamerSuite_UsePotions"
TRAPPED_POUCH_SERIAL_KEY = "TamerSuite_TrappedPouch"
USE_TRAPPED_POUCH_KEY = "TamerSuite_UseTrappedPouch"
AUTO_TARGET_KEY = "TamerSuite_AutoTarget"
EXPANDED_KEY = "TamerSuite_Expanded"
```

### New Keys (add)
```python
# Hotkey bindings - one key per action
PAUSE_HOTKEY_KEY = "TamerSuite_HK_Pause"       # Default: "PAUSE"
KILL_HOTKEY_KEY = "TamerSuite_HK_Kill"         # Default: "TAB"
GUARD_HOTKEY_KEY = "TamerSuite_HK_Guard"       # Default: "1"
FOLLOW_HOTKEY_KEY = "TamerSuite_HK_Follow"     # Default: "2"
STAY_HOTKEY_KEY = "TamerSuite_HK_Stay"         # Default: "" (unbound)
```

### Migration Path
1. On first load, check if new hotkey keys exist
2. If not, use DEFAULT values (same as current hardcoded)
3. Save defaults so user can modify them
4. Old scripts continue working with hardcoded keys

---

## 7. Hotkey Capture System

### 7.1 ALL_KEYS List (from UI_STANDARDS.md)
```python
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
```

### 7.2 Key Handler (Closure Pattern)
```python
def make_key_handler(key_name):
    def handler():
        global capturing_for

        # If capturing mode
        if capturing_for is not None:
            if key_name == "ESC":
                # Cancel capture
                capturing_for = None
                update_config_buttons()
                API.SysMsg("Hotkey capture cancelled", 90)
                return

            # Assign key to action
            hotkeys[capturing_for] = key_name
            save_hotkeys()
            update_config_buttons()
            update_hotkey_display()  # Update command buttons
            API.SysMsg(capturing_for + " bound to: " + key_name, 68)
            capturing_for = None
            return

        # Normal mode - execute action if key is bound
        for action, bound_key in hotkeys.items():
            if bound_key == key_name:
                execute_action(action)
                return

    return handler
```

### 7.3 Action Executor
```python
def execute_action(action):
    if action == "pause":
        toggle_pause()
    elif action == "kill":
        all_kill()
    elif action == "guard":
        all_guard()
    elif action == "follow":
        all_follow()
    elif action == "stay":
        all_stay()
```

### 7.4 Start Capture Functions
One for each action:
```python
def start_capture_pause():
    global capturing_for
    capturing_for = "pause"
    pauseHkBtn.SetBackgroundHue(38)  # Purple
    pauseHkBtn.SetText("[Listening...]")
    API.SysMsg("Press key for Pause hotkey...", 38)

def start_capture_kill():
    global capturing_for
    capturing_for = "kill"
    killHkBtn.SetBackgroundHue(38)
    killHkBtn.SetText("[Listening...]")
    API.SysMsg("Press key for All Kill hotkey...", 38)

# ... etc for guard, follow, stay
```

---

## 8. Config Panel Functions

### 8.1 Toggle Config
```python
def toggle_config():
    global show_config
    if show_config:
        hide_config_panel()
    else:
        show_config_panel()
```

### 8.2 Show Config Panel
```python
def show_config_panel():
    global show_config
    show_config = True

    # Show config elements
    configBg.IsVisible = True
    configTitle.IsVisible = True
    configHelp.IsVisible = True
    pauseHkLabel.IsVisible = True
    pauseHkBtn.IsVisible = True
    killHkLabel.IsVisible = True
    killHkBtn.IsVisible = True
    guardHkLabel.IsVisible = True
    guardHkBtn.IsVisible = True
    followHkLabel.IsVisible = True
    followHkBtn.IsVisible = True
    stayHkLabel.IsVisible = True
    stayHkBtn.IsVisible = True
    configDoneBtn.IsVisible = True

    # Update config button
    configBtn.SetBackgroundHue(68)  # Green = active

    # Reposition title bar buttons for wider window
    configBtn.SetPos(385, 3)
    expandBtn.SetPos(410, 3)

    # Expand window (only if already expanded)
    if is_expanded:
        x = gump.GetX()
        y = gump.GetY()
        gump.SetRect(x, y, WINDOW_WIDTH_CONFIG, CONFIG_HEIGHT)
        bg.SetRect(0, 0, WINDOW_WIDTH_CONFIG, CONFIG_HEIGHT)
```

### 8.3 Hide Config Panel
```python
def hide_config_panel():
    global show_config
    show_config = False

    # Hide all config elements
    configBg.IsVisible = False
    configTitle.IsVisible = False
    configHelp.IsVisible = False
    pauseHkLabel.IsVisible = False
    pauseHkBtn.IsVisible = False
    # ... etc
    configDoneBtn.IsVisible = False

    # Update config button
    configBtn.SetBackgroundHue(90)  # Gray = inactive

    # Reposition title bar buttons for narrower window
    configBtn.SetPos(350, 3)
    expandBtn.SetPos(375, 3)

    # Shrink window (only if expanded)
    if is_expanded:
        x = gump.GetX()
        y = gump.GetY()
        gump.SetRect(x, y, WINDOW_WIDTH_NORMAL, EXPANDED_HEIGHT)
        bg.SetRect(0, 0, WINDOW_WIDTH_NORMAL, EXPANDED_HEIGHT)
```

---

## 9. Updated Expand/Collapse

The existing expand/collapse must account for config panel:

```python
def expand_window():
    expandBtn.SetText("[-]")

    # Show all existing controls...
    # (same as current)

    # Calculate dimensions based on config state
    if show_config:
        width = WINDOW_WIDTH_CONFIG
        height = CONFIG_HEIGHT
        # Also show config elements
        configBg.IsVisible = True
        # ... etc
        configBtn.SetPos(385, 3)
        expandBtn.SetPos(410, 3)
    else:
        width = WINDOW_WIDTH_NORMAL
        height = EXPANDED_HEIGHT
        configBtn.SetPos(350, 3)
        expandBtn.SetPos(375, 3)

    x = gump.GetX()
    y = gump.GetY()
    gump.SetRect(x, y, width, height)
    bg.SetRect(0, 0, width, height)

def collapse_window():
    expandBtn.SetText("[+]")

    # Hide all existing controls...
    # (same as current)

    # Also hide config elements (but preserve show_config state)
    configBg.IsVisible = False
    # ... etc

    # Calculate width based on config state
    width = WINDOW_WIDTH_CONFIG if show_config else WINDOW_WIDTH_NORMAL

    if show_config:
        configBtn.SetPos(385, 3)
        expandBtn.SetPos(410, 3)
    else:
        configBtn.SetPos(350, 3)
        expandBtn.SetPos(375, 3)

    x = gump.GetX()
    y = gump.GetY()
    gump.SetRect(x, y, width, COLLAPSED_HEIGHT)
    bg.SetRect(0, 0, width, COLLAPSED_HEIGHT)
```

---

## 10. Button Visual States

### Config Button [C]
| State | Hue | Text |
|-------|-----|------|
| Config hidden | 90 (Gray) | [C] |
| Config visible | 68 (Green) | [C] |

### Hotkey Buttons
| State | Hue | Text |
|-------|-----|------|
| Unbound | 90 (Gray) | [---] |
| Bound | 68 (Green) | [KEY] (e.g., [TAB]) |
| Listening | 38 (Purple) | [Listening...] |

---

## 11. Edge Cases

| Scenario | Handling |
|----------|----------|
| Same key bound to multiple actions | Show warning, allow it (last registered wins) |
| ESC pressed while not capturing | Normal ESC behavior (if bound) |
| Config button clicked while collapsed | Expand first, then show config |
| User closes window while capturing | Cancel capture, save as-is |
| Invalid/unknown key pressed | Ignored (not in ALL_KEYS) |
| Empty hotkey string loaded | Treat as unbound, show [---] |

---

## 12. Files to Create/Modify

### New Files
1. `/Test/Tamer_Suite_v2.py` - Main refactored script
2. `/Test/Tamer_Suite_v2_DESIGN.md` - This design document

### Reference Files (read-only)
- `/Tamer/Tamer_Suite.py` - Original v2.4
- `/UI_STANDARDS.md` - UI patterns
- `/Utility/Util_Runebook.py` - Hotkey pattern reference
- `/Utility/Util_GoldSatchel.py` - Config panel reference

---

## 13. Implementation Checklist

### Phase 1: Copy and Verify
- [ ] Copy Tamer_Suite.py to Test/Tamer_Suite_v2.py
- [ ] Update version to "2.0"
- [ ] Verify it runs unchanged

### Phase 2: Add Config Panel Infrastructure
- [ ] Add new constants (widths, heights)
- [ ] Add show_config state variable
- [ ] Create config panel GUI elements (hidden initially)
- [ ] Add [C] button to title bar
- [ ] Implement toggle_config, show_config_panel, hide_config_panel
- [ ] Update expand_window/collapse_window for config state

### Phase 3: Add Hotkey Capture System
- [ ] Add ALL_KEYS list
- [ ] Add capturing_for state variable
- [ ] Add hotkeys dictionary
- [ ] Add persistence keys for hotkeys
- [ ] Implement make_key_handler closure
- [ ] Implement start_capture_* functions (one per action)
- [ ] Implement update_config_buttons
- [ ] Implement execute_action
- [ ] Register all keys in main loop setup
- [ ] Update cleanup to handle new keys

### Phase 4: Migrate Existing Hotkeys
- [ ] Remove hardcoded PAUSE_HOTKEY, ALL_KILL_HOTKEY, etc.
- [ ] Load hotkeys from persistence (with defaults)
- [ ] Save hotkeys on change
- [ ] Remove old cleanup code for hardcoded keys

### Phase 5: Polish and Test
- [ ] Update version number
- [ ] Update startup messages
- [ ] Test all hotkey captures
- [ ] Test config panel show/hide
- [ ] Test expand/collapse with config
- [ ] Test persistence across restarts
- [ ] Test migration from v2.4

---

## 14. Version Header Update

```python
# ============================================================
# Tamer Suite v2.0
# by Coryigon for UO Unchained
# ============================================================
#
# The all-in-one tamer script. Combines pet healing and commands
# into a single window with a non-blocking design - your hotkeys
# stay responsive even during long actions like resurrections.
#
# v2.0 Changes:
#   - NEW: Config panel [C] button for hotkey customization
#   - NEW: Click-to-capture hotkey binding system
#   - NEW: All 5 hotkeys now customizable (Pause, Kill, Guard, Follow, Stay)
#   - NEW: Dynamic window sizing (normal vs config mode)
#   - Hotkey bindings persist per-character
#   - All existing features preserved
#
# Features:
#   - Collapsible interface (click [-] to minimize, [+] to expand)
#   - Smart healing priority (self > tank > poisoned > lowest HP)
#   - Potion support (heal/cure) with 10s cooldown tracking
#   - Trapped pouch to break paralyze (auto-use if safe HP)
#   - Auto-targeting for continuous combat (3 tile range)
#   - Pet commands via hotkeys or GUI buttons
#   - ORDER mode sends commands to each pet individually by name
#   - Vet kit support for healing multiple pets at once
#   - Sound alerts for critical HP, pet death, out of bandages
#   - Shared pet list syncs with other tamer scripts
#
# Setup:
#   1. Click [C] to open hotkey config panel
#   2. Click any hotkey button (turns purple = listening)
#   3. Press desired key to bind
#   4. ESC cancels, [DONE] closes panel
#
# Default Hotkeys: TAB (Kill), 1 (Guard), 2 (Follow), PAUSE (toggle)
#
# ============================================================
```

---

## 15. Hand-off to Implementation

This design is complete and ready for implementation by `script-coder`.

**Key Implementation Notes:**
1. Use Pattern 1 for all buttons: `CreateSimpleButton(text, w, h)` + `SetPos(x, y)`
2. Use `gump.GetX()` and `gump.GetY()` for position (not .X/.Y properties)
3. Register all keys at startup, route through single handler
4. Config panel elements created hidden, shown only when [C] clicked
5. Title bar buttons MUST reposition when window width changes

**Testing Priority:**
1. Hotkey capture works (purple state, key assignment)
2. ESC cancels capture
3. Config panel show/hide resizes window correctly
4. Existing functionality unchanged
5. Persistence works across restarts

---

*End of Design Specification*
