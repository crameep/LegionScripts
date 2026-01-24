# UI Standards & Reusable Patterns

This document provides copy-paste ready patterns for Legion API GUI development. All patterns are verified working in production scripts.

**Last Updated**: 2026-01-24
**Source Scripts**: Util_Runebook_Hotkeys v2.4-v2.7, Util_Gold_Manager v3.1

---

## Table of Contents

1. [Button Creation Reference](#button-creation-reference)
2. [Dynamic Window Sizing Pattern](#dynamic-window-sizing-pattern)
3. [Title Bar Buttons Pattern](#title-bar-buttons-pattern)
4. [Hotkey Capture System Pattern](#hotkey-capture-system-pattern)
5. [Collapsible Window Pattern](#collapsible-window-pattern)
6. [Standard Button Dimensions](#standard-button-dimensions)
7. [Color Hue Standards](#color-hue-standards)
8. [Version History & Lessons Learned](#version-history--lessons-learned)

---

## Button Creation Reference

### The Two Valid Patterns

Legion API has TWO ways to create and position buttons. You MUST pick one pattern and stick with it. Mixing patterns will cause errors.

#### Pattern 1: Create WITH Dimensions + SetPos (RECOMMENDED)

```python
# Create button with fixed dimensions
btn = API.Gumps.CreateSimpleButton("Text", 100, 22)

# Position it (x, y ONLY - no width/height)
btn.SetPos(10, 50)

# Add to gump
gump.Add(btn)
```

**When to use**: Standard pattern for most buttons. Clearest and least error-prone.

#### Pattern 2: Create WITHOUT Dimensions + SetRect

```python
# Create button without dimensions
btn = API.Gumps.CreateSimpleButton("Text")

# Set position AND size together
btn.SetRect(10, 50, 100, 22)

# Add to gump
gump.Add(btn)
```

**When to use**: When button size needs to be calculated dynamically at creation time.

### What NOT to Do (WILL FAIL)

```python
# BROKEN - Dimensions in create, then SetRect()
btn = API.Gumps.CreateSimpleButton("Text", 100, 22)
btn.SetRect(10, 50, 100, 22)  # ERROR: Cannot mix patterns!

# BROKEN - No SetSize() method exists
btn.SetSize(100, 22)  # ERROR: No such method

# BROKEN - Cannot change dimensions after creation
btn = API.Gumps.CreateSimpleButton("Text", 100, 22)
btn.width = 150  # ERROR: No such property
```

### Quick Reference Table

| Creation Method | Positioning Method | Valid? |
|----------------|-------------------|--------|
| `CreateSimpleButton("Text", w, h)` | `SetPos(x, y)` | ✅ YES (RECOMMENDED) |
| `CreateSimpleButton("Text")` | `SetRect(x, y, w, h)` | ✅ YES |
| `CreateSimpleButton("Text", w, h)` | `SetRect(x, y, w, h)` | ❌ NO - Error |
| Any creation | `SetSize(w, h)` | ❌ NO - Method doesn't exist |

---

## Dynamic Window Sizing Pattern

Automatically resize window and reposition buttons when showing/hiding panels.

**Use Case**: Config panels, setup panels, or any collapsible UI section.

### Constants

```python
# Define two window widths
WINDOW_WIDTH_NORMAL = 155   # Normal mode (no extra panels)
WINDOW_WIDTH_CONFIG = 190   # Config mode (with SET buttons or config panel)

# Button layout (for config mode)
BTN_WIDTH = 147             # Main button width
SET_BTN_WIDTH = 36          # SET button width
SET_BTN_X = 154             # Position of SET button (5px margin + 147px + 2px gap)

# Heights
NORMAL_HEIGHT = 145
CONFIG_HEIGHT = 265  # Normal height + config panel height (120px)
```

### Show Config Panel (Expand Window)

```python
def show_config_panel():
    """Show the hotkey config panel"""
    global show_config

    show_config = True

    # Show all config controls
    configBg.IsVisible = True
    configBtn1.IsVisible = True
    configBtn2.IsVisible = True
    # ... more controls ...

    # Update config button appearance
    configBtn.SetText("[C]")
    configBtn.SetBackgroundHue(68)  # Green = active

    # Reposition title bar buttons for wider window
    configBtn.SetPos(140, 3)   # Move right for 190px width
    expandBtn.SetPos(165, 3)   # Move right for 190px width

    # Expand window to wider config width
    if is_expanded:
        gump.SetRect(gump.GetX(), gump.GetY(), WINDOW_WIDTH_CONFIG, CONFIG_HEIGHT)
        bg.SetRect(0, 0, WINDOW_WIDTH_CONFIG, CONFIG_HEIGHT)
```

### Hide Config Panel (Shrink Window)

```python
def hide_config_panel():
    """Hide the hotkey config panel"""
    global show_config

    show_config = False

    # Hide all config controls
    configBg.IsVisible = False
    configBtn1.IsVisible = False
    configBtn2.IsVisible = False
    # ... more controls ...

    # Update config button appearance
    configBtn.SetText("[C]")
    configBtn.SetBackgroundHue(90)  # Gray = inactive

    # Reposition title bar buttons for narrower window
    configBtn.SetPos(105, 3)   # Move left for 155px width
    expandBtn.SetPos(130, 3)   # Move left for 155px width

    # Shrink window back to normal width
    if is_expanded:
        gump.SetRect(gump.GetX(), gump.GetY(), WINDOW_WIDTH_NORMAL, NORMAL_HEIGHT)
        bg.SetRect(0, 0, WINDOW_WIDTH_NORMAL, NORMAL_HEIGHT)
```

### Key Points

- Title bar buttons MUST move when window width changes
- Background control MUST resize with window
- Use `gump.GetX()` and `gump.GetY()` to preserve position during resize
- Check `is_expanded` state before resizing (don't resize if collapsed)

---

## Title Bar Buttons Pattern

Standard pattern for config/minimize buttons in the title bar.

### Standard Layout

```python
# Constants
TITLE_BAR_BTN_WIDTH = 20
TITLE_BAR_BTN_HEIGHT = 18
TITLE_BAR_Y = 3  # Standard y position for title bar buttons

# For 155px wide window:
CONFIG_BTN_X_NORMAL = 105   # 155 - 20 - 20 - 10
EXPAND_BTN_X_NORMAL = 130   # 155 - 20 - 5

# For 190px wide window:
CONFIG_BTN_X_CONFIG = 140   # 190 - 20 - 20 - 10
EXPAND_BTN_X_CONFIG = 165   # 190 - 20 - 5
```

### Creating Title Bar Buttons

```python
# Title text
title = API.Gumps.CreateGumpTTFLabel("Script Name", 16, "#00d4ff")
title.SetPos(5, 2)
gump.Add(title)

# Config button [C]
configBtn = API.Gumps.CreateSimpleButton("[C]", 20, 18)
configBtn.SetPos(105, 3)  # For 155px width
configBtn.SetBackgroundHue(90)  # Gray = inactive initially
API.Gumps.AddControlOnClick(configBtn, toggle_config)
gump.Add(configBtn)

# Expand/collapse button [-]/[+]
expandBtn = API.Gumps.CreateSimpleButton("[-]", 20, 18)
expandBtn.SetPos(130, 3)  # For 155px width
expandBtn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(expandBtn, toggle_expand)
gump.Add(expandBtn)
```

### Repositioning on Width Change

```python
def reposition_title_buttons(window_width):
    """Reposition title bar buttons based on current window width"""
    if window_width == WINDOW_WIDTH_CONFIG:
        # Wide mode
        configBtn.SetPos(140, 3)
        expandBtn.SetPos(165, 3)
    else:
        # Normal mode
        configBtn.SetPos(105, 3)
        expandBtn.SetPos(130, 3)
```

### Color States

- **90 (Gray)**: Inactive/disabled
- **68 (Green)**: Active/enabled
- **38 (Purple)**: Listening/capturing input

---

## Hotkey Capture System Pattern

Complete working pattern for click-to-capture hotkey binding system.

### Step 1: Define All Possible Keys

```python
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
```

### Step 2: State Variable

```python
# Track which destination is capturing a hotkey
capturing_for = None  # String identifier or None
```

### Step 3: Key Handler Factory (Closure Pattern)

```python
def make_key_handler(key_name):
    """Create a callback for a specific key - handles both capture and execution"""
    def handler():
        global capturing_for

        # If we're in capture mode
        if capturing_for is not None:
            # ESC cancels capture
            if key_name == "ESC":
                API.SysMsg("Hotkey capture cancelled", 90)
                capturing_for = None
                update_config_buttons()
                return

            # Assign this key to the destination
            destinations[capturing_for]["hotkey"] = key_name
            save_destinations()
            update_config_buttons()
            update_button_labels()

            API.SysMsg(capturing_for + " bound to: " + key_name, 68)
            capturing_for = None
            return

        # Not capturing - execute action if this key is bound
        for dest_key, dest in destinations.items():
            if dest.get("hotkey", "") == key_name:
                do_action(dest_key)
                return

    return handler
```

### Step 4: Start Capture Functions

```python
def start_capture_home():
    """Start listening for a key to bind to Home"""
    global capturing_for
    capturing_for = "Home"
    homeHkBtn.SetBackgroundHue(38)  # Purple = listening
    homeHkBtn.SetText("[Listening...]")
    API.SysMsg("Press any key to bind to Home...", 38)

def start_capture_bank():
    """Start listening for a key to bind to Bank"""
    global capturing_for
    capturing_for = "Bank"
    bankHkBtn.SetBackgroundHue(38)  # Purple = listening
    bankHkBtn.SetText("[Listening...]")
    API.SysMsg("Press any key to bind to Bank...", 38)

# ... repeat for other destinations ...
```

### Step 5: Update Config Buttons

```python
def update_config_buttons():
    """Update hotkey config button labels and hues"""
    try:
        for key, dest in destinations.items():
            hotkey = dest.get("hotkey", "")
            if hotkey:
                label = "[" + hotkey + "]"
                hue = 68  # Green = hotkey bound
            else:
                label = "[---]"
                hue = 90  # Gray = no hotkey

            if key == "Home":
                homeHkBtn.SetText(label)
                homeHkBtn.SetBackgroundHue(hue)
            elif key == "Bank":
                bankHkBtn.SetText(label)
                bankHkBtn.SetBackgroundHue(hue)
            # ... more destinations ...
    except Exception as e:
        API.SysMsg("Error updating config buttons: " + str(e), 32)
```

### Step 6: Register All Keys at Startup

```python
# In initialization section
API.SysMsg("Registering key handlers...", 53)

registered_count = 0
for key in ALL_KEYS:
    try:
        API.OnHotKey(key, make_key_handler(key))
        registered_count += 1
    except Exception as e:
        # Skip keys that don't work
        pass

API.SysMsg("Registered " + str(registered_count) + " keys", 68)
```

### Complete Example

```python
# Config panel UI (one row example)
homeHkLabel = API.Gumps.CreateGumpTTFLabel("Home:", 8, "#aaaaaa")
homeHkLabel.SetPos(5, y)
homeHkLabel.IsVisible = False
gump.Add(homeHkLabel)

homeHkBtn = API.Gumps.CreateSimpleButton("[F1]", 95, 20)
homeHkBtn.SetPos(40, y)
homeHkBtn.SetBackgroundHue(90)  # Will update on load
homeHkBtn.IsVisible = False
API.Gumps.AddControlOnClick(homeHkBtn, start_capture_home)
gump.Add(homeHkBtn)
```

### Visual States

| State | Hue | Button Text | Meaning |
|-------|-----|-------------|---------|
| No hotkey bound | 90 (Gray) | `[---]` | Not configured |
| Hotkey bound | 68 (Green) | `[F1]` | Ready to use |
| Listening for key | 38 (Purple) | `[Listening...]` | Waiting for input |

---

## Collapsible Window Pattern

Standard expand/collapse functionality with state persistence.

### State Variables

```python
is_expanded = True  # Current expanded state
```

### Toggle Function

```python
def toggle_expand():
    """Toggle between collapsed and expanded states"""
    global is_expanded

    is_expanded = not is_expanded
    save_expanded_state()

    if is_expanded:
        expand_window()
    else:
        collapse_window()
```

### Expand Window

```python
def expand_window():
    """Show all controls and resize window"""
    expandBtn.SetText("[-]")

    # Show all content controls
    btn1.IsVisible = True
    btn2.IsVisible = True
    # ... more controls ...

    # Resize gump and background
    x = gump.GetX()
    y = gump.GetY()

    # Choose height and width based on active panels
    height = NORMAL_HEIGHT
    width = WINDOW_WIDTH_NORMAL
    if show_config:
        height = CONFIG_HEIGHT
        width = WINDOW_WIDTH_CONFIG

    gump.SetRect(x, y, width, height)
    bg.SetRect(0, 0, width, height)
```

### Collapse Window

```python
def collapse_window():
    """Hide all controls and shrink window"""
    expandBtn.SetText("[+]")

    # Hide all content controls
    btn1.IsVisible = False
    btn2.IsVisible = False
    # ... more controls ...

    # Resize to title bar only
    x = gump.GetX()
    y = gump.GetY()
    width = WINDOW_WIDTH_CONFIG if show_config else WINDOW_WIDTH_NORMAL

    gump.SetRect(x, y, width, COLLAPSED_HEIGHT)
    bg.SetRect(0, 0, width, COLLAPSED_HEIGHT)
```

### Persistence

```python
def save_expanded_state():
    """Save expanded state to persistence"""
    API.SavePersistentVar(KEY_PREFIX + "Expanded", str(is_expanded), API.PersistentVar.Char)

def load_expanded_state():
    """Load expanded state from persistence"""
    global is_expanded
    saved = API.GetPersistentVar(KEY_PREFIX + "Expanded", "True", API.PersistentVar.Char)
    is_expanded = (saved == "True")
```

### Initialization

```python
# Load state before creating gump
load_expanded_state()

# Create gump with correct initial height
initial_height = NORMAL_HEIGHT if is_expanded else COLLAPSED_HEIGHT
gump.SetRect(x, y, WINDOW_WIDTH_NORMAL, initial_height)

# Set button text based on state
expandBtn = API.Gumps.CreateSimpleButton("[-]" if is_expanded else "[+]", 20, 18)
```

---

## Standard Button Dimensions

Consistent button sizes used across scripts.

### Common Widths

| Button Type | Width | Height | Usage |
|------------|-------|--------|-------|
| Title bar buttons | 20px | 18px | Config, minimize, close |
| Destination buttons | 147px | 22px | Main action buttons (runebook, spells) |
| SET buttons | 36px | 22px | Configuration setup buttons |
| Action buttons | 130px | 22px | Wide buttons (Done, Cancel full-width) |
| Small buttons | 62px | 20px | OK/Cancel side-by-side |
| Hotkey display | 95px | 20px | Hotkey config buttons |

### Layout Examples

#### Destination + SET Button (Config Mode)

```
[5px margin][147px Destination Button][2px gap][36px SET][5px margin] = 195px total
```

```python
BTN_WIDTH = 147
SET_BTN_WIDTH = 36
BTN_X = 5
SET_BTN_X = 154  # 5 + 147 + 2

destBtn = API.Gumps.CreateSimpleButton("Destination [1]", BTN_WIDTH, 22)
destBtn.SetPos(BTN_X, y)

setBtn = API.Gumps.CreateSimpleButton("[SET]", SET_BTN_WIDTH, 22)
setBtn.SetPos(SET_BTN_X, y)
```

#### Side-by-Side Small Buttons

```
[5px margin][62px OK][6px gap][62px CANCEL][5px margin] = 140px total
```

```python
okBtn = API.Gumps.CreateSimpleButton("[OK]", 62, 20)
okBtn.SetPos(5, y)

cancelBtn = API.Gumps.CreateSimpleButton("[CANCEL]", 62, 20)
cancelBtn.SetPos(73, y)  # 5 + 62 + 6
```

#### Full-Width Button

```
[5px margin][130px DONE][5px margin] = 140px total
```

```python
doneBtn = API.Gumps.CreateSimpleButton("[DONE]", 130, 20)
doneBtn.SetPos(5, y)
```

---

## Color Hue Standards

Semantic color coding for consistent UI.

### Primary Hues

| Hue | Color | Hex Equivalent | Semantic Meaning |
|-----|-------|----------------|------------------|
| 68 | Green | #00ff00 | Active, configured, enabled, success |
| 90 | Gray | #888888 | Inactive, not configured, disabled, neutral |
| 38 | Purple/Magenta | #ff00ff | Listening/capturing input, resurrection, tank |
| 32 | Red | #ff0000 | Danger, delete, error, disabled |
| 43 | Yellow | #ffff00 | Warning, medium priority, cooldown |
| 53 | Purple/Yellow | #ffff00 | Special actions, poison, setup mode |
| 66 | Blue-Green | #00ffff | Magery, special abilities, info |

### Usage Examples

```python
# Configured destination - green
btn.SetBackgroundHue(68)

# Not configured - gray
btn.SetBackgroundHue(90)

# Listening for hotkey - purple
btn.SetBackgroundHue(38)

# Delete/cancel button - red
deleteBtn.SetBackgroundHue(32)

# Warning message - yellow
API.SysMsg("Cooldown active", 43)

# Setup mode - purple/yellow
setupBtn.SetBackgroundHue(53)
```

### Labels

```python
# Title text - cyan/blue
title = API.Gumps.CreateGumpTTFLabel("Title", 16, "#00d4ff")

# Normal text - light gray
label = API.Gumps.CreateGumpTTFLabel("Label:", 8, "#aaaaaa")

# Help text - medium gray
help = API.Gumps.CreateGumpTTFLabel("Help text", 7, "#888888")

# Success message - green
success = API.Gumps.CreateGumpTTFLabel("Ready!", 8, "#00ff00")

# Error message - red
error = API.Gumps.CreateGumpTTFLabel("Failed", 8, "#ff0000")
```

**Note**: Label colors are set at creation and CANNOT be changed later. No SetColor() method exists.

---

## 8. Standard Font Sizes

Use these font sizes for consistent, readable UIs across all scripts.

### Font Size Reference Table

| Element Type | Font Size | Color Context | Example |
|-------------|-----------|---------------|---------|
| **Title Bar** | 16pt | Gold/Orange (#ffaa00) | Script name |
| **Prominent Counter** | 14pt | Yellow (#ffcc00) | "Banked: 12,345 gold" |
| **Important Data** | 13pt | Bright colors | "1.2k/m \| 72k/hr" |
| **Standard Labels** | 11pt | Semantic colors | "Status: ACTIVE" |
| **Help Text** | 7-8pt | Gray (#888888) | Instructions |

### Example Implementation

```python
# Title bar (16pt)
titleLabel = API.Gumps.CreateGumpTTFLabel("Gold Manager", 16, "#ffaa00")

# Prominent counter (14pt) - main totals
sessionLabel = API.Gumps.CreateGumpTTFLabel("Banked: 12,345 gold", 14, "#ffcc00")

# Important data (13pt) - key metrics
incomeLabel = API.Gumps.CreateGumpTTFLabel("1.2k/m | 72k/hr", 13, "#00ff88")

# Standard labels (11pt) - status info
statusLabel = API.Gumps.CreateGumpTTFLabel("Status: ACTIVE", 11, "#00ff00")
satchelLabel = API.Gumps.CreateGumpTTFLabel("Container: 0x12AB [OK]", 11, "#ff6666")

# Help text (7-8pt) - instructions
helpLabel = API.Gumps.CreateGumpTTFLabel("Click button to rebind", 7, "#888888")
```

### Vertical Spacing Guidelines

Larger fonts need more vertical spacing to prevent overlap:

| Font Size | Recommended Spacing After | Notes |
|-----------|--------------------------|-------|
| 11pt | 13-14px | Standard label spacing |
| 13pt | 14-16px | Important data spacing |
| 14pt | 16-18px | Counter spacing |
| 16pt | 18-20px | Title bar spacing |

**Example Spacing:**
```python
y = 26
statusLabel.SetPos(5, y)         # 11pt label

y += 13                          # +13px spacing after 11pt
satchelLabel.SetPos(5, y)        # 11pt label

y += 14                          # +14px spacing after 11pt
incomeLabel.SetPos(5, y)         # 13pt label

y += 16                          # +16px spacing after 13pt
sessionLabel.SetPos(5, y)        # 14pt counter

y += 18                          # +18px spacing after 14pt
# Next element at y=88
```

### Common Mistakes to Avoid

❌ **Don't use 8pt for standard labels** - too small, hard to read
❌ **Don't use same size for all text** - loses hierarchy
❌ **Don't forget to adjust spacing** - larger text needs more room
✅ **Use 11pt minimum for readable labels**
✅ **Use 14pt for prominent numbers/counters**
✅ **Increase spacing proportionally with font size**

---

## Version History & Lessons Learned

### Util_Runebook_Hotkeys Evolution

#### v2.4 (Working Baseline)
- Hotkey capture system implemented
- Dynamic panel showing/hiding
- All buttons created with: `CreateSimpleButton(text, width, height)` + `SetPos(x, y)`
- Gump position accessed via: `gump.GetX()` and `gump.GetY()`

#### v2.5 (BROKEN - Learn from these mistakes!)

**What went wrong**:
1. Changed button positioning to use `SetRect()` after creating with dimensions
2. Changed gump position access from `GetX()/GetY()` methods to `.X/.Y` properties
3. Changed text input from `SetText()` method to `.Text` assignment

**Errors encountered**:
```
AttributeError: 'PyBaseGump' object has no attribute 'X'
AttributeError: 'PyBaseGump' object has no attribute 'Y'
AttributeError: can't assign to read-only property 'Text'
[ERROR] Cannot mix button creation patterns (dimensions + SetRect)
```

**Impact**: Script completely broken, wouldn't run.

#### v2.6 (FIXED)

**What was fixed**:
1. Reverted ALL buttons to: `CreateSimpleButton(text, width, height)` + `SetPos(x, y)`
2. Reverted gump coordinates back to: `GetX()` and `GetY()` methods
3. Reverted text input to: `SetText()` method

**Result**: Script working again, back to v2.4 functionality.

#### v2.7 (IMPROVED)

**Enhancements added**:
1. Dynamic window width: 155px normal mode, 190px config mode
2. Title bar buttons reposition based on width
3. Destination buttons fill space in normal mode (147px wide)
4. SET buttons increased to 36px (no truncation)
5. Window expands/shrinks smoothly when toggling config panel

**New constants**:
```python
WINDOW_WIDTH_NORMAL = 155   # Narrow mode - no empty space
WINDOW_WIDTH_CONFIG = 190   # Wide mode - room for SET buttons
BTN_WIDTH = 147             # Wider destination buttons
SET_BTN_WIDTH = 36          # Full [SET] text visible
```

### Key Lessons

1. **Never mix button creation patterns** - If you create with dimensions, use SetPos(). Period.
2. **Properties vs Methods matter** - Gumps use GetX()/GetY() methods, not .X/.Y properties
3. **Text inputs are read-only** - Must use SetText() method, cannot assign to .Text
4. **Test incrementally** - Change one thing at a time, test immediately
5. **Keep working versions** - Version numbers are cheap, broken scripts are expensive
6. **Dynamic sizing works** - Windows CAN resize smoothly if you:
   - Track state properly
   - Update ALL affected elements (buttons, background, gump)
   - Use GetX()/GetY() to preserve position

### Latest Updates (2026-01-24)

- Added standard font size guidelines based on Gold Manager v3.1
- 11pt minimum for readable labels (was 8pt - too small)
- 13pt for important metrics, 14pt for prominent counters
- Vertical spacing guidelines for larger fonts

### Debugging Checklist

When UI breaks, check these in order:

1. ✅ Button creation pattern consistent? (dimensions + SetPos OR no dimensions + SetRect)
2. ✅ Using `gump.GetX()` and `gump.GetY()` (not `.X` or `.Y`)?
3. ✅ Using `textInput.SetText()` (not `.Text = value`)?
4. ✅ All resizing updates both `gump.SetRect()` AND `bg.SetRect()`?
5. ✅ Title bar buttons repositioned when width changes?
6. ✅ All controls have correct `IsVisible` state?

---

## Complete Working Example

Minimal script showing all patterns together:

```python
import API

# ============ CONSTANTS ============
WINDOW_WIDTH_NORMAL = 155
WINDOW_WIDTH_CONFIG = 190
NORMAL_HEIGHT = 100
CONFIG_HEIGHT = 180
COLLAPSED_HEIGHT = 24

KEY_PREFIX = "Example_"

# ============ STATE ============
is_expanded = True
show_config = False
capturing_for = None

destinations = {
    "Dest1": {"hotkey": "F1"},
    "Dest2": {"hotkey": "F2"},
}

ALL_KEYS = ["F1", "F2", "F3", "ESC", "A", "B", "C"]

# ============ HOTKEY SYSTEM ============
def make_key_handler(key_name):
    def handler():
        global capturing_for
        if capturing_for is not None:
            if key_name == "ESC":
                capturing_for = None
                return
            destinations[capturing_for]["hotkey"] = key_name
            API.SysMsg(capturing_for + " bound to: " + key_name, 68)
            capturing_for = None
        else:
            for dest_key, dest in destinations.items():
                if dest.get("hotkey", "") == key_name:
                    API.SysMsg("Action: " + dest_key, 68)
    return handler

# ============ CONFIG PANEL ============
def show_config_panel():
    global show_config
    show_config = True
    configBg.IsVisible = True
    configBtn.SetBackgroundHue(68)
    configBtn.SetPos(140, 3)
    expandBtn.SetPos(165, 3)
    if is_expanded:
        gump.SetRect(gump.GetX(), gump.GetY(), WINDOW_WIDTH_CONFIG, CONFIG_HEIGHT)
        bg.SetRect(0, 0, WINDOW_WIDTH_CONFIG, CONFIG_HEIGHT)

def hide_config_panel():
    global show_config
    show_config = False
    configBg.IsVisible = False
    configBtn.SetBackgroundHue(90)
    configBtn.SetPos(105, 3)
    expandBtn.SetPos(130, 3)
    if is_expanded:
        gump.SetRect(gump.GetX(), gump.GetY(), WINDOW_WIDTH_NORMAL, NORMAL_HEIGHT)
        bg.SetRect(0, 0, WINDOW_WIDTH_NORMAL, NORMAL_HEIGHT)

def toggle_config():
    if show_config:
        hide_config_panel()
    else:
        show_config_panel()

# ============ EXPAND/COLLAPSE ============
def toggle_expand():
    global is_expanded
    is_expanded = not is_expanded
    if is_expanded:
        expandBtn.SetText("[-]")
        btn1.IsVisible = True
        height = CONFIG_HEIGHT if show_config else NORMAL_HEIGHT
        width = WINDOW_WIDTH_CONFIG if show_config else WINDOW_WIDTH_NORMAL
        gump.SetRect(gump.GetX(), gump.GetY(), width, height)
        bg.SetRect(0, 0, width, height)
    else:
        expandBtn.SetText("[+]")
        btn1.IsVisible = False
        width = WINDOW_WIDTH_CONFIG if show_config else WINDOW_WIDTH_NORMAL
        gump.SetRect(gump.GetX(), gump.GetY(), width, COLLAPSED_HEIGHT)
        bg.SetRect(0, 0, width, COLLAPSED_HEIGHT)

# ============ BUILD GUI ============
gump = API.Gumps.CreateGump()
gump.SetRect(100, 100, WINDOW_WIDTH_NORMAL, NORMAL_HEIGHT)

bg = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
bg.SetRect(0, 0, WINDOW_WIDTH_NORMAL, NORMAL_HEIGHT)
gump.Add(bg)

title = API.Gumps.CreateGumpTTFLabel("Example", 16, "#00d4ff")
title.SetPos(5, 2)
gump.Add(title)

configBtn = API.Gumps.CreateSimpleButton("[C]", 20, 18)
configBtn.SetPos(105, 3)
configBtn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(configBtn, toggle_config)
gump.Add(configBtn)

expandBtn = API.Gumps.CreateSimpleButton("[-]", 20, 18)
expandBtn.SetPos(130, 3)
expandBtn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(expandBtn, toggle_expand)
gump.Add(expandBtn)

btn1 = API.Gumps.CreateSimpleButton("Button 1", 147, 22)
btn1.SetPos(5, 26)
btn1.SetBackgroundHue(68)
gump.Add(btn1)

configBg = API.Gumps.CreateGumpColorBox(0.8, "#2a2a3e")
configBg.SetRect(0, 100, WINDOW_WIDTH_CONFIG, 80)
configBg.IsVisible = False
gump.Add(configBg)

API.Gumps.AddGump(gump)

# ============ REGISTER KEYS ============
for key in ALL_KEYS:
    try:
        API.OnHotKey(key, make_key_handler(key))
    except:
        pass

# ============ MAIN LOOP ============
while not API.StopRequested:
    API.ProcessCallbacks()
    API.Pause(0.1)
```

---

## Quick Copy-Paste Snippets

### Standard Title Bar

```python
title = API.Gumps.CreateGumpTTFLabel("Script Name", 16, "#00d4ff")
title.SetPos(5, 2)
gump.Add(title)

configBtn = API.Gumps.CreateSimpleButton("[C]", 20, 18)
configBtn.SetPos(105, 3)
configBtn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(configBtn, toggle_config)
gump.Add(configBtn)

expandBtn = API.Gumps.CreateSimpleButton("[-]", 20, 18)
expandBtn.SetPos(130, 3)
expandBtn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(expandBtn, toggle_expand)
gump.Add(expandBtn)
```

### Standard Destination Button Row

```python
destBtn = API.Gumps.CreateSimpleButton("Home [---]", 147, 22)
destBtn.SetPos(5, y)
destBtn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(destBtn, do_action)
gump.Add(destBtn)

setBtn = API.Gumps.CreateSimpleButton("[SET]", 36, 22)
setBtn.SetPos(154, y)
setBtn.SetBackgroundHue(53)
setBtn.IsVisible = False  # Show in config mode only
API.Gumps.AddControlOnClick(setBtn, setup_action)
gump.Add(setBtn)
```

### Standard Config Panel Row

```python
label = API.Gumps.CreateGumpTTFLabel("Home:", 8, "#aaaaaa")
label.SetPos(5, y + 3)
label.IsVisible = False
gump.Add(label)

hkBtn = API.Gumps.CreateSimpleButton("[F1]", 95, 20)
hkBtn.SetPos(40, y)
hkBtn.SetBackgroundHue(68)
hkBtn.IsVisible = False
API.Gumps.AddControlOnClick(hkBtn, start_capture)
gump.Add(hkBtn)
```

---

**End of UI Standards Document**

For questions or issues, reference the source scripts in `/Test/` directory, especially `Util_Runebook_Hotkeys.py` versions 2.4-2.7.
