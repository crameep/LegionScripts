# Tamer Suite v2.2 - Phase 2: Per-Pet Hotkey System Design Spec

## Executive Summary

Add per-pet hotkey system to Tamer Suite v2.1, allowing quick access to individual pets via customizable hotkeys. Normal press = follow pet + set priority heal flag. Shift+press = emergency heal (bypass all priority). This enables rapid pet management during combat without clicking through the UI.

**Key Goals:**
1. Add hotkey display buttons to each pet row (shows `[F1]` or `[---]`)
2. Add visual arrow indicators `[>]` to show last selected pet
3. Add "Pet Hotkeys" config section with capture system
4. Implement dual-mode hotkey execution (normal vs shift)
5. Persist all 5 pet hotkey bindings

**Estimated Scope:**
- +200 lines for GUI additions
- +150 lines for hotkey capture logic
- +100 lines for execution and priority tracking
- Total: ~450 new lines

---

## Changes from v2.1 to v2.2

### Window Dimensions
- **Normal width**: 400px (unchanged)
- **Config width**: 400px (unchanged)
- **Collapsed height**: 24px (unchanged)
- **Expanded height**: 360px (unchanged)
- **Config height**: 1220px (up from 1100px - adds 120px for Pet Hotkeys section)

### New Persistence Keys (5 total)

```python
PET1_HOTKEY_KEY = "TamerSuite_PetHK_1"
PET2_HOTKEY_KEY = "TamerSuite_PetHK_2"
PET3_HOTKEY_KEY = "TamerSuite_PetHK_3"
PET4_HOTKEY_KEY = "TamerSuite_PetHK_4"
PET5_HOTKEY_KEY = "TamerSuite_PetHK_5"
```

### New Runtime State Variables

```python
# Pet hotkey bindings (index 0-4)
pet_hotkeys = ["", "", "", "", ""]  # Empty string = unbound

# Priority heal tracking
priority_heal_pet = 0  # Serial of pet flagged for priority heal (normal hotkey press)

# Visual indicator tracking
last_selected_pet_index = -1  # Which pet row shows [>] arrow
```

---

## Main UI Layout Changes (Expanded Mode)

### Current v2.1 Pet Row Layout

```
┌────────────────────────────────────────────────┐
│ 1. Dragon (12/15) [P]                  [390px]│ 18px tall
│ 2. Mare (8/8)                          [390px]│ 18px
│ 3. Beetle (4/5)                        [390px]│ 18px
│ 4. ---                                 [390px]│ 18px
│ 5. ---                                 [390px]│ 18px
└────────────────────────────────────────────────┘
```

### New v2.2 Pet Row Layout

```
┌────────────────────────────────────────────────┐
│ 1. Dragon (12/15) [P]  [F1] [>]       [5+300+35+35+5]│ 18px tall
│ 2. Mare (8/8)          [F2] [ ]       [5+300+35+35+5]│ 18px
│ 3. Beetle (4/5)        [---][ ]       [5+300+35+35+5]│ 18px
│ 4. ---                 [---][ ]       [5+300+35+35+5]│ 18px
│ 5. ---                 [---][ ]       [5+300+35+35+5]│ 18px
└────────────────────────────────────────────────┘
Total row width: 380px (fits in 400px window with 10px margins)
```

**Layout breakdown per row:**
- 5px left margin
- 300px: Pet name/HP button (clickable, shows status)
- 35px: Hotkey display button (shows `[F1]` or `[---]`, NOT clickable)
- 35px: Arrow indicator (shows `[>]` or `[ ]`, NOT clickable)
- 10px right margin (implicit)

### Pet Row Y Positions (Unchanged)

```python
y_pets_title = 195
y_pet1 = 211  # Title + 16
y_pet2 = 229  # +18
y_pet3 = 247  # +18
y_pet4 = 265  # +18
y_pet5 = 283  # +18

y_add_btn = 305  # +22
```

---

## Config Panel Layout Changes

### Current v2.1 Config Panel Structure

```
CONFIG_PANEL_Y = 360 (starts after expanded content)

Section 1: Healer Settings       (y: 370-520)   150px
Section 2: Command Settings       (y: 530-730)   200px
Section 3: Command Hotkeys        (y: 740-860)   120px
Section 4: Pet Order Mode         (y: 870-1070)  200px
Done button                       (y: 1080)       20px

Total height: 720px → Config height: 1080px
```

### New v2.2 Config Panel Structure

```
CONFIG_PANEL_Y = 360 (unchanged)

Section 1: Healer Settings        (y: 370-520)   150px (unchanged)
Section 2: Command Settings        (y: 530-730)   200px (unchanged)
Section 3: Command Hotkeys         (y: 740-860)   120px (unchanged)
Section 4: Pet Hotkeys (NEW)       (y: 870-990)   120px (NEW)
Section 5: Pet Order Mode          (y: 1000-1200) 200px (moved down)
Done button                        (y: 1210)       20px

Total height: 860px → Config height: 1220px
```

### New Section 4: Pet Hotkeys (y: 870-990)

```
┌─────────────────────────────────────────────────┐
│ ─── PET HOTKEYS ───                              │ y=870 (title)
│                                                   │
│ Assign hotkeys to quickly follow/heal each pet.  │ y=890 (help line 1)
│ Normal press: Follow pet + set heal priority     │ y=900 (help line 2)
│ SHIFT+press: Emergency heal (bypass priority)    │ y=910 (help line 3)
│                                                   │
│ Pet 1 (Dragon):    [F1]          [CLR]            │ y=930
│ Pet 2 (Mare):      [F2]          [CLR]            │ y=950
│ Pet 3 (Beetle):    [---]         [CLR]            │ y=970
│ Pet 4:             [---]         [CLR]            │ y=990
│ Pet 5:             [---]         [CLR]            │ y=1010 (OOPS - need to adjust!)
└─────────────────────────────────────────────────┘
```

**CORRECTION**: 5 pet rows at 20px each = 100px, plus title (20px) + help text (30px) = 150px total.
Let's adjust:

```
Section 4: Pet Hotkeys (NEW)       (y: 870-1020)  150px (revised)
Section 5: Pet Order Mode          (y: 1030-1230) 200px (moved down)
Done button                        (y: 1240)       20px

Total config height: 1260px
```

**Updated constants:**
```python
CONFIG_HEIGHT = 1260  # Was 1100 in v2.1
```

---

## Pet Hotkeys Section - Detailed Layout

### Y Position Calculations

```python
# Section 4: Pet Hotkeys
y_pet_hk_title = 870
y_pet_hk_help1 = 890
y_pet_hk_help2 = 900
y_pet_hk_help3 = 910

y_pet_hk_1 = 935   # First row (title + help + 5px gap)
y_pet_hk_2 = 955   # +20
y_pet_hk_3 = 975   # +20
y_pet_hk_4 = 995   # +20
y_pet_hk_5 = 1015  # +20

# Section 5: Pet Order Mode (moved down)
y_order_title = 1040
y_order_help = 1060
y_order_pet1 = 1085
y_order_pet2 = 1110
y_order_pet3 = 1135
y_order_pet4 = 1160
y_order_pet5 = 1185

# Done button
y_done = 1215
```

### Control Positioning (X coordinates)

```python
# Pet hotkey config row layout
label_x = 15           # "Pet 1 (Dragon):"
hk_btn_x = 130         # [F1] button
clr_btn_x = 225        # [CLR] button

# Button dimensions
hk_btn_width = 90      # Hotkey button
hk_btn_height = 20
clr_btn_width = 45     # Clear button
clr_btn_height = 20
```

### Example: Pet 1 Hotkey Row

```python
# Pet 1 label
petHkLabel1 = API.Gumps.CreateGumpTTFLabel("Pet 1 (Dragon):", 11, "#888888")
petHkLabel1.SetPos(15, 935)
petHkLabel1.IsVisible = False
gump.Add(petHkLabel1)

# Pet 1 hotkey button (click to capture)
petHkBtn1 = API.Gumps.CreateSimpleButton("[F1]", 90, 20)
petHkBtn1.SetPos(130, 935)
petHkBtn1.SetBackgroundHue(68)  # Green = bound
petHkBtn1.IsVisible = False
API.Gumps.AddControlOnClick(petHkBtn1, lambda: start_capture_pet_hotkey(0))
gump.Add(petHkBtn1)

# Pet 1 clear button
petHkClrBtn1 = API.Gumps.CreateSimpleButton("[CLR]", 45, 20)
petHkClrBtn1.SetPos(225, 935)
petHkClrBtn1.SetBackgroundHue(32)  # Red
petHkClrBtn1.IsVisible = False
API.Gumps.AddControlOnClick(petHkClrBtn1, lambda: clear_pet_hotkey(0))
gump.Add(petHkClrBtn1)
```

---

## New GUI Elements - Complete List

### Main UI Additions (10 new controls)

**Pet hotkey display buttons (5):**
```python
petHkDisplay1 = None  # Shows [F1] or [---], NOT clickable
petHkDisplay2 = None
petHkDisplay3 = None
petHkDisplay4 = None
petHkDisplay5 = None
```

**Pet arrow indicators (5):**
```python
petArrow1 = None  # Shows [>] or [ ], NOT clickable
petArrow2 = None
petArrow3 = None
petArrow4 = None
petArrow5 = None
```

### Config Panel Additions (20 new controls)

**Section title and help text (4):**
```python
petHkTitle = None        # "─── PET HOTKEYS ───"
petHkHelp1 = None        # "Assign hotkeys to quickly follow/heal each pet."
petHkHelp2 = None        # "Normal press: Follow pet + set heal priority"
petHkHelp3 = None        # "SHIFT+press: Emergency heal (bypass priority)"
```

**Pet labels (5):**
```python
petHkLabel1 = None  # "Pet 1 (Dragon):"
petHkLabel2 = None  # "Pet 2 (Mare):"
petHkLabel3 = None  # "Pet 3 (Beetle):"
petHkLabel4 = None  # "Pet 4:"
petHkLabel5 = None  # "Pet 5:"
```

**Hotkey capture buttons (5):**
```python
petHkBtn1 = None  # Click to capture hotkey
petHkBtn2 = None
petHkBtn3 = None
petHkBtn4 = None
petHkBtn5 = None
```

**Clear hotkey buttons (5):**
```python
petHkClrBtn1 = None  # Clear binding
petHkClrBtn2 = None
petHkClrBtn3 = None
petHkClrBtn4 = None
petHkClrBtn5 = None
```

**Pet order controls (moved, not new):**
- Move petOrderLabels, petOrderActiveBtn, petOrderSkipBtn down by 170px

---

## Hotkey Capture System

### Capture State Variable

```python
capturing_for = None  # Can be: "pause", "kill", "guard", "follow", "stay", "pet0", "pet1", "pet2", "pet3", "pet4"
```

### Start Capture Functions (5 new)

```python
def start_capture_pet_hotkey(pet_index):
    """Start listening for a key to bind to pet N (0-4)"""
    global capturing_for
    capturing_for = "pet" + str(pet_index)

    # Update button appearance
    if pet_index == 0:
        petHkBtn1.SetBackgroundHue(38)  # Purple = listening
        petHkBtn1.SetText("[Listening...]")
    elif pet_index == 1:
        petHkBtn2.SetBackgroundHue(38)
        petHkBtn2.SetText("[Listening...]")
    # ... repeat for pets 2-4 ...

    API.SysMsg("Press any key to bind to Pet " + str(pet_index + 1) + " (ESC cancels)...", 38)
```

### Clear Hotkey Functions (5 new)

```python
def clear_pet_hotkey(pet_index):
    """Unbind hotkey from pet N (0-4)"""
    global pet_hotkeys

    old_key = pet_hotkeys[pet_index]
    pet_hotkeys[pet_index] = ""
    save_pet_hotkeys()
    update_pet_hotkey_config_display()
    update_pet_hotkey_main_display()

    API.SysMsg("Pet " + str(pet_index + 1) + " hotkey cleared (was: " + old_key + ")", 90)
```

### Updated Key Handler (Modify Existing)

```python
def make_key_handler(key_name):
    """Create a callback for a specific key - handles both capture and execution"""
    def handler():
        global capturing_for, pet_hotkeys, priority_heal_pet, last_selected_pet_index

        # If we're in capture mode
        if capturing_for is not None:
            # ESC cancels capture
            if key_name == "ESC":
                API.SysMsg("Hotkey capture cancelled", 90)
                capturing_for = None
                update_config_hotkey_buttons()
                update_pet_hotkey_config_display()
                return

            # Command hotkey capture (existing logic)
            if capturing_for in ["pause", "kill", "guard", "follow", "stay"]:
                hotkeys[capturing_for] = key_name
                save_hotkeys()
                update_config_hotkey_buttons()
                update_hotkey_label()
                API.SysMsg(capturing_for.capitalize() + " bound to: " + key_name, 68)
                capturing_for = None
                return

            # Pet hotkey capture (NEW)
            if capturing_for.startswith("pet"):
                pet_index = int(capturing_for[3])  # Extract index from "pet0", "pet1", etc.
                pet_hotkeys[pet_index] = key_name
                save_pet_hotkeys()
                update_pet_hotkey_config_display()
                update_pet_hotkey_main_display()
                API.SysMsg("Pet " + str(pet_index + 1) + " bound to: " + key_name, 68)
                capturing_for = None
                return

        # Not capturing - execute action if this key is bound
        # Check command hotkeys (existing)
        if hotkeys["pause"] == key_name:
            toggle_pause()
            return
        if hotkeys["kill"] == key_name:
            all_kill_hotkey()
            return
        if hotkeys["guard"] == key_name:
            all_guard()
            return
        if hotkeys["follow"] == key_name:
            all_follow()
            return
        if hotkeys["stay"] == key_name:
            all_stay()
            return

        # Check pet hotkeys (NEW)
        for i in range(5):
            if pet_hotkeys[i] == key_name:
                execute_pet_hotkey(i)
                return

    return handler
```

---

## Pet Hotkey Execution Logic

### Normal Press: Follow + Priority Heal

```python
def execute_pet_hotkey(pet_index):
    """Execute pet hotkey action (normal press = follow + heal priority)"""
    global priority_heal_pet, last_selected_pet_index

    # Check if we have a pet at this index
    if pet_index >= len(PETS):
        API.SysMsg("No pet in slot " + str(pet_index + 1) + "!", 43)
        return

    serial = PETS[pet_index]
    mob = API.FindMobile(serial)

    if not mob:
        API.SysMsg("Pet not found!", 32)
        return

    name = PET_NAMES.get(serial, "Pet")

    # Check for SHIFT modifier (emergency heal)
    # NOTE: Need to investigate if Legion API exposes modifier keys
    # For now, implement normal behavior only

    # Follow the pet
    API.Msg(name + " follow me")

    # Set as priority heal target
    priority_heal_pet = serial
    last_selected_pet_index = pet_index

    # Update arrow indicators
    update_pet_arrow_display()

    API.SysMsg("Following " + name + " (priority heal enabled)", 68)
```

**NOTE**: SHIFT modifier detection may not be possible with current Legion API. If not available, we can implement a toggle button in the config panel: `[EMERGENCY MODE]` that when enabled, next pet hotkey press triggers emergency heal instead of follow.

### Emergency Heal Mode (Alternative Implementation)

If SHIFT detection not available:

```python
emergency_heal_mode = False  # Toggle state

def toggle_emergency_mode():
    """Toggle emergency heal mode (next pet hotkey = instant heal)"""
    global emergency_heal_mode
    emergency_heal_mode = not emergency_heal_mode

    if emergency_heal_mode:
        emergencyModeBtn.SetBackgroundHue(32)  # Red = active
        API.SysMsg("EMERGENCY MODE: Next pet hotkey = instant heal!", 32)
    else:
        emergencyModeBtn.SetBackgroundHue(90)  # Gray = inactive
        API.SysMsg("Emergency mode off", 90)

def execute_pet_hotkey(pet_index):
    """Execute pet hotkey action"""
    global priority_heal_pet, last_selected_pet_index, emergency_heal_mode

    if pet_index >= len(PETS):
        API.SysMsg("No pet in slot " + str(pet_index + 1) + "!", 43)
        return

    serial = PETS[pet_index]
    mob = API.FindMobile(serial)

    if not mob:
        API.SysMsg("Pet not found!", 32)
        return

    name = PET_NAMES.get(serial, "Pet")

    # Emergency heal mode (bypass all priority)
    if emergency_heal_mode:
        emergency_heal_mode = False  # One-shot
        emergencyModeBtn.SetBackgroundHue(90)

        if mob.IsDead:
            API.SysMsg("Cannot heal dead pet!", 32)
            return

        # Force immediate heal
        start_heal_action(serial, "heal", CAST_DELAY if USE_MAGERY else VET_DELAY, False)
        API.SysMsg("EMERGENCY HEAL: " + name, 32)
        return

    # Normal mode: Follow + priority heal
    API.Msg(name + " follow me")
    priority_heal_pet = serial
    last_selected_pet_index = pet_index
    update_pet_arrow_display()
    API.SysMsg("Following " + name + " (priority heal enabled)", 68)
```

---

## Priority Heal Integration

### Modified get_next_heal_action()

```python
def get_next_heal_action():
    """Get next healing action with priority system"""

    # 1. Self heal (existing - unchanged)
    if HEAL_SELF:
        if is_player_poisoned():
            if drink_potion(POTION_CURE, "Cure"):
                return None
        player = API.Player
        if player.Hits < (player.HitsMax - SELF_HEAL_THRESHOLD):
            if USE_POTIONS and potion_ready():
                if drink_potion(POTION_HEAL, "Heal"):
                    return None
            return (API.Player.Serial, "heal_self", SELF_DELAY, True)

    # 2. Trapped pouch (existing - unchanged)
    if use_trapped_pouch and is_player_paralyzed():
        if use_trapped_pouch():
            return None

    # 3. Priority heal pet (NEW - check before tank)
    if priority_heal_pet != 0:
        mob = API.FindMobile(priority_heal_pet)
        if mob and not mob.IsDead and get_distance(mob) <= SPELL_RANGE:
            if is_poisoned(mob):
                return (priority_heal_pet, "cure", CAST_DELAY if USE_MAGERY else VET_DELAY, False)
            hp_pct = get_hp_percent(mob)
            if hp_pct < PET_HP_PERCENT:
                return (priority_heal_pet, "heal", CAST_DELAY if USE_MAGERY else VET_DELAY, False)

    # 4. Tank pet (existing - unchanged)
    if TANK_PET != 0:
        mob = API.FindMobile(TANK_PET)
        if mob and not mob.IsDead and get_distance(mob) <= SPELL_RANGE:
            if is_poisoned(mob):
                return (TANK_PET, "cure", CAST_DELAY if USE_MAGERY else VET_DELAY, False)
            hp_pct = get_hp_percent(mob)
            if hp_pct < TANK_HP_PERCENT:
                return (TANK_PET, "heal", CAST_DELAY if USE_MAGERY else VET_DELAY, False)

    # 5-8. Rest of priority (existing - unchanged)
    # ... poisoned pets, lowest HP, vet kit, rez ...
```

**Note**: Priority heal pet is checked AFTER self but BEFORE tank. Once the pet is healed above threshold, it drops out of priority automatically.

---

## Display Update Functions

### Main UI: Pet Hotkey Display Buttons

```python
def update_pet_hotkey_main_display():
    """Update hotkey display buttons on main UI (shows [F1] or [---])"""
    try:
        for i in range(5):
            hotkey = pet_hotkeys[i] if i < len(pet_hotkeys) else ""

            if hotkey:
                text = "[" + hotkey + "]"
                hue = 68  # Green = bound
            else:
                text = "[---]"
                hue = 90  # Gray = unbound

            if i == 0:
                petHkDisplay1.SetText(text)
                petHkDisplay1.SetBackgroundHue(hue)
            elif i == 1:
                petHkDisplay2.SetText(text)
                petHkDisplay2.SetBackgroundHue(hue)
            elif i == 2:
                petHkDisplay3.SetText(text)
                petHkDisplay3.SetBackgroundHue(hue)
            elif i == 3:
                petHkDisplay4.SetText(text)
                petHkDisplay4.SetBackgroundHue(hue)
            elif i == 4:
                petHkDisplay5.SetText(text)
                petHkDisplay5.SetBackgroundHue(hue)
    except:
        pass
```

### Main UI: Pet Arrow Indicators

```python
def update_pet_arrow_display():
    """Update arrow indicators to show last selected pet"""
    try:
        for i in range(5):
            text = "[>]" if i == last_selected_pet_index else "[ ]"
            hue = 68 if i == last_selected_pet_index else 90

            if i == 0:
                petArrow1.SetText(text)
                petArrow1.SetBackgroundHue(hue)
            elif i == 1:
                petArrow2.SetText(text)
                petArrow2.SetBackgroundHue(hue)
            elif i == 2:
                petArrow3.SetText(text)
                petArrow3.SetBackgroundHue(hue)
            elif i == 3:
                petArrow4.SetText(text)
                petArrow4.SetBackgroundHue(hue)
            elif i == 4:
                petArrow5.SetText(text)
                petArrow5.SetBackgroundHue(hue)
    except:
        pass
```

### Config Panel: Pet Hotkey Config Display

```python
def update_pet_hotkey_config_display():
    """Update pet hotkey config buttons in config panel"""
    try:
        for i in range(5):
            # Update label with current pet name
            if i < len(PETS):
                serial = PETS[i]
                name = PET_NAMES.get(serial, "Pet")
                label_text = "Pet " + str(i+1) + " (" + name + "):"
            else:
                label_text = "Pet " + str(i+1) + ":"

            # Update hotkey button
            hotkey = pet_hotkeys[i] if i < len(pet_hotkeys) else ""
            if hotkey:
                btn_text = "[" + hotkey + "]"
                hue = 68  # Green = bound
            else:
                btn_text = "[---]"
                hue = 90  # Gray = unbound

            # Don't update if currently capturing
            if capturing_for == "pet" + str(i):
                btn_text = "[Listening...]"
                hue = 38  # Purple = listening

            if i == 0:
                petHkLabel1.SetText(label_text)
                petHkBtn1.SetText(btn_text)
                petHkBtn1.SetBackgroundHue(hue)
            elif i == 1:
                petHkLabel2.SetText(label_text)
                petHkBtn2.SetText(btn_text)
                petHkBtn2.SetBackgroundHue(hue)
            # ... repeat for pets 2-4 ...
    except:
        pass
```

---

## Persistence Functions

### Save Pet Hotkeys

```python
def save_pet_hotkeys():
    """Save pet hotkey bindings to persistence"""
    for i in range(5):
        key = [PET1_HOTKEY_KEY, PET2_HOTKEY_KEY, PET3_HOTKEY_KEY, PET4_HOTKEY_KEY, PET5_HOTKEY_KEY][i]
        value = pet_hotkeys[i] if i < len(pet_hotkeys) else ""
        API.SavePersistentVar(key, value, API.PersistentVar.Char)
```

### Load Pet Hotkeys

```python
def load_pet_hotkeys():
    """Load pet hotkey bindings from persistence"""
    global pet_hotkeys

    keys = [PET1_HOTKEY_KEY, PET2_HOTKEY_KEY, PET3_HOTKEY_KEY, PET4_HOTKEY_KEY, PET5_HOTKEY_KEY]
    pet_hotkeys = []

    for key in keys:
        value = API.GetPersistentVar(key, "", API.PersistentVar.Char)
        pet_hotkeys.append(value)
```

### Update load_settings()

```python
def load_settings():
    # ... existing loads ...

    load_hotkeys()
    load_pet_hotkeys()  # NEW
    sync_pets_from_storage()

    # ... rest of function ...
```

---

## Show/Hide Config Panel Updates

### Show Config Panel

```python
def show_config_panel():
    """Show the config panel"""
    global show_config

    if not is_expanded:
        expand_window()
        return

    show_config = True

    # Show existing config controls (unchanged)
    configBg.IsVisible = True
    configTitle.IsVisible = True
    # ... all existing controls ...

    # Show new pet hotkey controls (NEW)
    petHkTitle.IsVisible = True
    petHkHelp1.IsVisible = True
    petHkHelp2.IsVisible = True
    petHkHelp3.IsVisible = True

    petHkLabel1.IsVisible = True
    petHkBtn1.IsVisible = True
    petHkClrBtn1.IsVisible = True

    petHkLabel2.IsVisible = True
    petHkBtn2.IsVisible = True
    petHkClrBtn2.IsVisible = True

    petHkLabel3.IsVisible = True
    petHkBtn3.IsVisible = True
    petHkClrBtn3.IsVisible = True

    petHkLabel4.IsVisible = True
    petHkBtn4.IsVisible = True
    petHkClrBtn4.IsVisible = True

    petHkLabel5.IsVisible = True
    petHkBtn5.IsVisible = True
    petHkClrBtn5.IsVisible = True

    # Update displays
    update_pet_hotkey_config_display()

    # Update config button
    configBtn.SetBackgroundHue(68)

    # Expand window height for config panel
    x = gump.GetX()
    y = gump.GetY()
    gump.SetRect(x, y, WINDOW_WIDTH_NORMAL, CONFIG_HEIGHT)
    bg.SetRect(0, 0, WINDOW_WIDTH_NORMAL, CONFIG_HEIGHT)
```

### Hide Config Panel

```python
def hide_config_panel():
    """Hide the config panel"""
    global show_config

    show_config = False

    # Hide existing config controls (unchanged)
    configBg.IsVisible = False
    configTitle.IsVisible = False
    # ... all existing controls ...

    # Hide new pet hotkey controls (NEW)
    petHkTitle.IsVisible = False
    petHkHelp1.IsVisible = False
    petHkHelp2.IsVisible = False
    petHkHelp3.IsVisible = False

    petHkLabel1.IsVisible = False
    petHkBtn1.IsVisible = False
    petHkClrBtn1.IsVisible = False

    petHkLabel2.IsVisible = False
    petHkBtn2.IsVisible = False
    petHkClrBtn2.IsVisible = False

    petHkLabel3.IsVisible = False
    petHkBtn3.IsVisible = False
    petHkClrBtn3.IsVisible = False

    petHkLabel4.IsVisible = False
    petHkBtn4.IsVisible = False
    petHkClrBtn4.IsVisible = False

    petHkLabel5.IsVisible = False
    petHkBtn5.IsVisible = False
    petHkClrBtn5.IsVisible = False

    # Update config button
    configBtn.SetBackgroundHue(90)

    # Shrink window back to normal height
    x = gump.GetX()
    y = gump.GetY()
    gump.SetRect(x, y, WINDOW_WIDTH_NORMAL, EXPANDED_HEIGHT)
    bg.SetRect(0, 0, WINDOW_WIDTH_NORMAL, EXPANDED_HEIGHT)
```

---

## Main Loop Updates

### Call Display Updates

```python
# In main loop (after API.ProcessCallbacks())
if is_expanded:
    update_pet_display()  # Existing
    update_pet_hotkey_main_display()  # NEW
    update_pet_arrow_display()  # NEW
    update_bandage_display()  # Existing

    if show_config:
        update_pet_hotkey_config_display()  # NEW
        # ... other config updates ...
```

---

## Color Scheme Summary

### Hotkey Display Buttons (Main UI)

| State | Hue | Text | Meaning |
|-------|-----|------|---------|
| Hotkey bound | 68 (Green) | `[F1]` | Ready to use |
| No hotkey | 90 (Gray) | `[---]` | Not configured |

### Arrow Indicators (Main UI)

| State | Hue | Text | Meaning |
|-------|-----|------|---------|
| Selected | 68 (Green) | `[>]` | Last selected pet (priority heal) |
| Not selected | 90 (Gray) | `[ ]` | Inactive |

### Config Panel Buttons

| State | Hue | Text | Meaning |
|-------|-----|------|---------|
| Hotkey bound | 68 (Green) | `[F1]` | Ready to reconfigure |
| No hotkey | 90 (Gray) | `[---]` | Not configured |
| Listening | 38 (Purple) | `[Listening...]` | Waiting for key press |
| Clear button | 32 (Red) | `[CLR]` | Delete binding |

---

## Testing Checklist (v2.2)

### Main UI Pet Rows
- [ ] Pet hotkey display buttons show correct keys or `[---]`
- [ ] Pet hotkey display buttons have correct colors (green/gray)
- [ ] Arrow indicators show `[>]` on last selected pet only
- [ ] Arrow indicators show `[ ]` on non-selected pets
- [ ] Pet row layout fits in 400px window (no overflow)
- [ ] Buttons are NOT clickable (display only)

### Config Panel - Pet Hotkeys Section
- [ ] Section title and help text visible when config shown
- [ ] Pet labels show correct names from pet list
- [ ] Empty slots show "Pet N:" without name
- [ ] Hotkey buttons show current bindings or `[---]`
- [ ] Hotkey buttons have correct colors (green/gray)
- [ ] Clicking hotkey button starts capture (turns purple)
- [ ] Pressing key during capture binds to slot
- [ ] ESC during capture cancels without binding
- [ ] [CLR] buttons clear bindings
- [ ] Display updates immediately after binding/clearing

### Hotkey Execution - Normal Mode
- [ ] Pressing bound pet hotkey sends follow command
- [ ] Pet becomes priority heal target
- [ ] Arrow indicator moves to selected pet
- [ ] System message confirms action
- [ ] Priority heal pet gets healed before tank
- [ ] Priority clears when pet is full HP

### Hotkey Execution - Emergency Mode (if implemented)
- [ ] Emergency mode toggle works
- [ ] Emergency mode button shows correct state (red/gray)
- [ ] Emergency press triggers immediate heal
- [ ] Emergency mode auto-disables after use
- [ ] Dead pets show error message

### Persistence
- [ ] Pet hotkey bindings save on close
- [ ] Pet hotkey bindings load on startup
- [ ] Bindings persist per-character
- [ ] Cleared bindings don't restore on reload

### Config Panel Layout
- [ ] Pet Hotkeys section at y=870-1020
- [ ] Pet Order Mode section moved to y=1030-1230
- [ ] Done button at y=1240
- [ ] Total config height 1260px
- [ ] No control overlap

### Integration
- [ ] Hotkey capture doesn't conflict with command hotkeys
- [ ] Pet hotkeys work alongside command hotkeys
- [ ] Paused mode still allows pet hotkeys
- [ ] All existing v2.1 features work unchanged

---

## Known Limitations & Future Enhancements

### SHIFT Modifier Detection
- Legion API may not expose modifier keys (SHIFT, CTRL, ALT)
- Current design uses toggle mode for emergency heal
- If modifier detection becomes available, upgrade to SHIFT+key pattern

### Potential Enhancements (v2.3+)
1. **Double-tap detection**: Tap hotkey twice quickly for emergency heal
2. **Priority heal timeout**: Auto-clear priority after N seconds
3. **Visual HP bars**: Show mini HP bar on pet rows
4. **Pet hotkey in ORDER mode**: Make pet active in ORDER mode when hotkey pressed
5. **Hotkey grouping**: Assign same hotkey to multiple pets (cycle through)

---

## Migration from v2.1 to v2.2

### User Experience
- All settings preserved (existing persistence keys unchanged)
- 5 new persistence keys for pet hotkeys (default = unbound)
- Config panel 120px taller
- Main UI shows hotkey status and priority indicator
- No functionality lost, only additions

### Code Changes Summary
- Add 5 pet hotkey persistence keys
- Add 3 new runtime state variables
- Add 10 main UI controls (5 hotkey displays, 5 arrows)
- Add 20 config panel controls (title, help, 5 rows of label/button/clear)
- Modify `make_key_handler()` to handle pet hotkeys
- Add `execute_pet_hotkey()` function
- Modify `get_next_heal_action()` to check priority heal pet
- Add 5 display update functions
- Modify show/hide config panel functions
- Update CONFIG_HEIGHT constant to 1260
- Move Pet Order Mode section Y positions down by 170px

---

## Implementation Order

1. **Add persistence keys and state variables** (10 lines)
2. **Create main UI pet row modifications** (60 lines)
   - Reduce pet label width to 300px
   - Add 5 hotkey display buttons
   - Add 5 arrow indicator buttons
3. **Create config panel Pet Hotkeys section** (100 lines)
   - Title and help text
   - 5 pet rows (label + button + clear)
   - Move Pet Order Mode down
4. **Add hotkey capture functions** (80 lines)
   - `start_capture_pet_hotkey()`
   - `clear_pet_hotkey()`
   - Modify `make_key_handler()`
5. **Add execution logic** (60 lines)
   - `execute_pet_hotkey()`
   - Modify `get_next_heal_action()`
6. **Add display update functions** (80 lines)
   - `update_pet_hotkey_main_display()`
   - `update_pet_arrow_display()`
   - `update_pet_hotkey_config_display()`
7. **Add persistence functions** (30 lines)
   - `save_pet_hotkeys()`
   - `load_pet_hotkeys()`
   - Modify `load_settings()`
8. **Update show/hide config panel** (40 lines)
9. **Update main loop display calls** (10 lines)
10. **Testing and refinement** (variable)

**Total estimated: ~470 lines**

---

## End of v2.2 Design Spec

This design focuses solely on Phase 2: adding per-pet hotkey system with priority heal mechanics. Phase 3 (if needed) could add advanced features like double-tap detection, HP bars, or hotkey grouping.

Ready for implementation once approved.
