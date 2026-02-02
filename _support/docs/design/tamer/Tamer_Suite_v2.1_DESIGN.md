# Tamer Suite v2.1+ UI Refactor Design Spec

## Executive Summary

Refactor Tamer Suite v2.0 to save vertical space by moving infrequently-used toggles into the config panel and adding per-pet hotkey assignment capability. Target is to reduce expanded window height from 430px to ~360px while improving usability.

---

## Implementation Phases

### Phase 1: v2.1 - Move Toggles to Config Panel
- Move infrequently-used toggles from main UI to config panel
- Reduce expanded window height from 430px to ~360px
- Reorganize config panel into sections
- Keep width at 400px (no width change)

### Phase 2: v2.2 - Add Pet Hotkey System
- Add pet hotkey display buttons and arrows to main UI
- Add pet hotkey capture in config panel
- Implement pet hotkey execution (normal and SHIFT+ variants)
- Add 5 new persistence keys for pet hotkeys

---

## Current State Analysis (v2.0)

### Current Window Dimensions
- **Normal width**: 400px
- **Config width**: 435px
- **Collapsed height**: 24px
- **Expanded height**: 430px
- **Config height**: 540px (expanded + 110px config panel)

### Current Main UI Elements (42 controls visible when expanded)

**Title Bar** (always visible):
- Title label
- [C] config button
- [-]/[+] expand/collapse button
- Bandage count label

**LEFT PANEL - Healer Section** (~165px tall):
1. Healer title
2. [BAND]/[MAGE] toggle button (90px)
3. [SELF:ON/OFF] toggle button (90px) ← **MOVE TO CONFIG**
4. [REZ:ON/OFF] toggle button (90px) ← **MOVE TO CONFIG**
5. [SKIP:ON/OFF] toggle button (90px) ← **MOVE TO CONFIG**
6. Tank label ← **MOVE TO CONFIG**
7. Tank [SET] button (45px) ← **MOVE TO CONFIG**
8. Tank [CLR] button (45px) ← **MOVE TO CONFIG**
9. VetKit label ← **MOVE TO CONFIG**
10. VetKit [SET] button (45px) ← **MOVE TO CONFIG**
11. VetKit [CLR] button (45px) ← **MOVE TO CONFIG**
12. [PAUSE] button (90px) ✓ **KEEP**
13. Status label ✓ **KEEP**

**RIGHT PANEL - Commands Section** (~165px tall):
14. Commands title
15. Friend Rez label ← **REMOVE (redundant)**
16. [REZ FRIEND] button (185px) ✓ **KEEP**
17. [REDS:ON/OFF] toggle button (90px) ← **MOVE TO CONFIG**
18. [GRAYS:ON/OFF] toggle button (90px) ← **MOVE TO CONFIG**
19. [ALL]/[ORDER] mode button (90px) ✓ **KEEP**
20. Hotkey display label (small text) ✓ **KEEP**
21. [BANK] button (60px) ✓ **KEEP**
22. [BALANCE] button (70px) ✓ **KEEP**
23. [ALL KILL] button (90px) ✓ **KEEP**
24. [FOLLOW] button (60px) ✓ **KEEP**
25. [GUARD] button (60px) ✓ **KEEP**
26. [STAY] button (55px) ✓ **KEEP**
27. [POTIONS:ON/OFF] toggle (90px) ← **MOVE TO CONFIG**
28. [AUTO-TARGET:ON/OFF] toggle (90px) ← **MOVE TO CONFIG**
29. [SET POUCH] button (90px) ← **MOVE TO CONFIG**
30. [USE POUCH:ON/OFF] toggle (95px) ← **MOVE TO CONFIG**
31. Heal potion count label ← **MOVE TO CONFIG**
32. Cure potion count label ← **MOVE TO CONFIG**

**BOTTOM PANEL - Pets** (~165px tall):
33. Pets title ✓ **KEEP**
34-38. 5x pet buttons (340px each) ✓ **KEEP**
39-43. 5x pet ON/OFF toggles (45px each) ← **MOVE TO CONFIG**
44. [ADD] button ✓ **KEEP**
45. [DEL] button ✓ **KEEP**
46. [CLR ALL] button ← **MOVE TO CONFIG**

---

## Phase 1: v2.1 Implementation

### Goal
Move 15+ controls from main UI to config panel, reduce expanded height by ~70px.

### New Window Dimensions (v2.1)
- **Normal width**: 400px (unchanged)
- **Config width**: 400px (changed from 435px - no width change needed!)
- **Collapsed height**: 24px (unchanged)
- **Expanded height**: ~360px (down from 430px - saves 70px)
- **Config height**: ~600px (expanded + 240px config panel)

### Main Window Layout (v2.1 Expanded Mode)

```
┌─────────────────────────────────────────────────────┐
│ Tamer Suite v2.1              [C] [-]   Bands: 123 │ 24px title bar
├─────────────────────────────────────────────────────┤
│ === HEALER ===   │   === COMMANDS ===               │
│                  │                                   │
│ [BAND/MAGE] 90px │ [REZ FRIEND] 185px               │ 22px
│                  │                                   │
│ [PAUSE] 90px     │ [MODE:ALL/ORDER] 90px            │ 22px
│ Status: Running  │ Hotkeys: K:TAB G:1 F:2           │ 14px
│                  │                                   │
│                  │ [BANK] [BALANCE]                 │ 22px
│                  │ [ALL KILL] 90px                  │ 22px
│                  │ [FOLLOW] [GUARD] [STAY]          │ 22px
│                  │                                   │
├─────────────────────────────────────────────────────┤
│              === PETS ===                           │
│                                                      │
│ 1. Dragon (12/15) [1234]                           │ 20px each
│ 2. Mare (8/8) [1234]                               │ 20px
│ 3. Beetle (4/5) [1234]                             │ 20px
│ 4. ---                                             │ 20px
│ 5. ---                                             │ 20px
│                                                      │
│ [ADD] [DEL]                                         │ 20px
│                                                      │
└─────────────────────────────────────────────────────┘
Total: ~360px (saves 70px from v2.0)
```

### Config Panel Layout (v2.1)

```
┌─────────────────────────────────────────────────────┐
│ === CONFIGURATION ===                               │
│ Settings organized by category                      │
├─────────────────────────────────────────────────────┤
│                                                      │
│ ─── HEALER SETTINGS ───                             │
│                                                      │
│ Self Heal:  [ON ] [OFF]   (Heal yourself: ON)      │
│ Pet Rez:    [ON ] [OFF]   (Resurrect pets: ON)     │
│ Skip OOR:   [ON ] [OFF]   (Skip out of range: ON)  │
│                                                      │
│ Tank Pet:   [Dragon - 0x12AB3456]  [SET] [CLR]     │
│ Vet Kit:    [0x0E9F]                [SET] [CLR]     │
│                                                      │
│ ─── COMMAND SETTINGS ───                            │
│                                                      │
│ Target Reds:    [ON ] [OFF]   (Attack reds: OFF)    │
│ Target Grays:   [ON ] [OFF]   (Attack grays: OFF)   │
│ Use Potions:    [ON ] [OFF]   (Auto-potion: ON)     │
│ Auto-Target:    [ON ] [OFF]   (Auto re-target: OFF) │
│                                                      │
│ Trapped Pouch:  [0x23BC4567]    [SET]               │
│ Use Pouch:      [ON ] [OFF]   (Auto-use: ON)        │
│                                                      │
│ Potion Counts:  Heal: 12  Cure: 8                   │
│                                                      │
│ ─── COMMAND HOTKEYS ───                             │
│                                                      │
│ Pause:   [PAUSE]      Kill:    [TAB]                │
│ Guard:   [1    ]      Follow:  [2  ]                │
│ Stay:    [---  ]                                    │
│                                                      │
│ ─── PET ORDER MODE ───                              │
│ (Controls which pets respond to ALL KILL command)   │
│                                                      │
│ Pet 1 (Dragon):  [ACTIVE] [SKIP]                    │
│ Pet 2 (Mare):    [ACTIVE] [SKIP]                    │
│ Pet 3 (Beetle):  [ACTIVE] [SKIP]                    │
│ Pet 4:           [SKIP  ] (no pet)                  │
│ Pet 5:           [SKIP  ] (no pet)                  │
│                                                      │
│            [DONE - Close Config]                    │
└─────────────────────────────────────────────────────┘
Config panel: ~240px tall
Total with main UI: ~600px
```

### Controls Removed from Main UI (v2.1)

1. ❌ [SELF:ON/OFF] button (22px)
2. ❌ [REZ:ON/OFF] button (22px)
3. ❌ [SKIP:ON/OFF] button (22px)
4. ❌ Tank label + [SET]/[CLR] (38px total)
5. ❌ VetKit label + [SET]/[CLR] (38px total)
6. ❌ [REDS:ON/OFF] button (22px)
7. ❌ [GRAYS:ON/OFF] button (22px)
8. ❌ [POTIONS:ON/OFF] button (22px)
9. ❌ [AUTO-TARGET:ON/OFF] button (22px)
10. ❌ [SET POUCH]/[USE POUCH:ON/OFF] (44px total)
11. ❌ Heal/Cure potion count labels (22px)
12. ❌ Friend Rez label (16px)
13. ❌ Pet toggle buttons (5x 20px = 100px)
14. ❌ [CLR ALL] button (20px)

**Total vertical space saved: ~70px**

### New Config Panel Controls (v2.1)

**Section 1: Healer Settings (130px)**
- Section title label
- Self Heal: [ON] [OFF] buttons + status label
- Pet Rez: [ON] [OFF] buttons + status label
- Skip OOR: [ON] [OFF] buttons + status label
- Tank Pet: display label + [SET] [CLR] buttons
- Vet Kit: display label + [SET] [CLR] buttons

**Section 2: Command Settings (150px)**
- Section title label
- Target Reds: [ON] [OFF] buttons + status label
- Target Grays: [ON] [OFF] buttons + status label
- Use Potions: [ON] [OFF] buttons + status label
- Auto-Target: [ON] [OFF] buttons + status label
- Trapped Pouch: display label + [SET] button
- Use Pouch: [ON] [OFF] buttons + status label
- Potion counts: display label

**Section 3: Command Hotkeys (60px)**
- Section title label
- 5 hotkey config buttons (existing from v2.0)

**Section 4: Pet Order Mode (120px)**
- Section title label + help text
- 5x pet rows: name label + [ACTIVE] [SKIP] buttons

**Total new config controls: ~50 controls**
**Total config panel height: ~240px**

---

## Phase 2: v2.2 Implementation (Future)

### Goal
Add per-pet hotkey assignment with visual indicators and execution system.

### New Elements for v2.2

**Main UI additions:**
- Pet hotkey display buttons (5x, shows "[F1]" or "[---]")
- Pet arrow indicators [>] (5x, clickable)

**Config panel additions:**
- Pet Hotkeys section (110px)
  - Title + help text
  - 5x pet rows: name + [KEY] button + [CLR] button
  - Capture system (click → purple → press key)

**New functionality:**
- Pet hotkey execution (normal press = follow + heal priority)
- Shift+hotkey execution (emergency heal, bypass priority)
- Persistence (5 new keys)

**Details deferred to v2.2 design spec**

---

## v2.1 Technical Implementation

### Window Sizing Changes

**Constants:**
```python
# v2.1 changes
WINDOW_WIDTH_NORMAL = 400  # unchanged
WINDOW_WIDTH_CONFIG = 400  # changed from 435px - no width change!
COLLAPSED_HEIGHT = 24      # unchanged
EXPANDED_HEIGHT = 360      # changed from 430px - saves 70px
CONFIG_HEIGHT = 600        # changed from 540px - expanded config
```

### Config Panel Y Position
```python
# Start config panel right after expanded content
CONFIG_PANEL_Y = EXPANDED_HEIGHT  # 360px
CONFIG_PANEL_HEIGHT = 240
```

### New Config Panel Controls

```python
# Healer settings section
self_heal_on_btn = None
self_heal_off_btn = None
self_heal_status_label = None
pet_rez_on_btn = None
pet_rez_off_btn = None
pet_rez_status_label = None
skip_oor_on_btn = None
skip_oor_off_btn = None
skip_oor_status_label = None
tank_display_label = None
tank_set_btn = None
tank_clr_btn = None
vetkit_display_label = None
vetkit_set_btn = None
vetkit_clr_btn = None

# Command settings section
reds_on_btn = None
reds_off_btn = None
reds_status_label = None
grays_on_btn = None
grays_off_btn = None
grays_status_label = None
potions_on_btn = None
potions_off_btn = None
potions_status_label = None
autotarget_on_btn = None
autotarget_off_btn = None
autotarget_status_label = None
pouch_display_label = None
pouch_set_btn = None
usepouch_on_btn = None
usepouch_off_btn = None
usepouch_status_label = None
potion_counts_label = None

# Pet order mode section
pet_order_labels = [None] * 5
pet_order_active_btns = [None] * 5
pet_order_skip_btns = [None] * 5
```

### Control Positioning (Config Panel)

**Y coordinates:**
```python
# Section 1: Healer Settings
y_healer_title = 370       # CONFIG_PANEL_Y + 10
y_self_heal = 395
y_pet_rez = 420
y_skip_oor = 445
y_tank = 470
y_vetkit = 495

# Section 2: Command Settings
y_cmd_title = 525
y_reds = 550
y_grays = 575
y_potions = 600
y_autotarget = 625
y_pouch = 650
y_use_pouch = 675
y_potion_counts = 700

# Section 3: Command Hotkeys
y_hotkey_title = 725
y_hotkey_row1 = 750
y_hotkey_row2 = 775
y_hotkey_row3 = 800

# Section 4: Pet Order Mode
y_order_title = 825
y_order_pet1 = 855
y_order_pet2 = 880
y_order_pet3 = 905
y_order_pet4 = 930
y_order_pet5 = 955

# Done button
y_done = 985
```

### Toggle Button Pattern

**Standard ON/OFF toggle pair:**
```python
# Example: Self Heal toggle
label_x = 15
on_btn_x = 110
off_btn_x = 160
status_x = 210

label = API.Gumps.CreateGumpTTFLabel("Self Heal:", 11, "#888888")
label.SetPos(label_x, y_self_heal)
label.IsVisible = False
gump.Add(label)

on_btn = API.Gumps.CreateSimpleButton("[ON ]", 45, 22)
on_btn.SetPos(on_btn_x, y_self_heal - 2)
on_btn.SetBackgroundHue(68 if HEAL_SELF else 90)
on_btn.IsVisible = False
API.Gumps.AddControlOnClick(on_btn, lambda: toggle_heal_self(True))
gump.Add(on_btn)

off_btn = API.Gumps.CreateSimpleButton("[OFF]", 45, 22)
off_btn.SetPos(off_btn_x, y_self_heal - 2)
off_btn.SetBackgroundHue(32 if not HEAL_SELF else 90)
off_btn.IsVisible = False
API.Gumps.AddControlOnClick(off_btn, lambda: toggle_heal_self(False))
gump.Add(off_btn)

status = API.Gumps.CreateGumpTTFLabel("(Heal yourself: ON)", 11, "#00ff00")
status.SetPos(status_x, y_self_heal)
status.IsVisible = False
gump.Add(status)
```

### Visibility Management

**Show config panel function updates:**
```python
def show_config_panel():
    global show_config

    if not is_expanded:
        expand_window()
        return

    show_config = True

    # Show command hotkey controls (existing)
    configBg.IsVisible = True
    configTitle.IsVisible = True
    # ... existing hotkey controls ...

    # Show healer settings controls (NEW v2.1)
    self_heal_on_btn.IsVisible = True
    self_heal_off_btn.IsVisible = True
    self_heal_status_label.IsVisible = True
    pet_rez_on_btn.IsVisible = True
    # ... etc for all healer controls ...

    # Show command settings controls (NEW v2.1)
    reds_on_btn.IsVisible = True
    reds_off_btn.IsVisible = True
    # ... etc for all command settings ...

    # Show pet order controls (NEW v2.1)
    for i in range(5):
        pet_order_labels[i].IsVisible = True
        pet_order_active_btns[i].IsVisible = True
        pet_order_skip_btns[i].IsVisible = True

    # Update config button
    configBtn.SetText("[C]")
    configBtn.SetBackgroundHue(68)

    # NO title bar repositioning needed (width unchanged in v2.1)

    # Expand window height for config panel
    x = gump.GetX()
    y = gump.GetY()
    gump.SetRect(x, y, WINDOW_WIDTH_NORMAL, CONFIG_HEIGHT)
    bg.SetRect(0, 0, WINDOW_WIDTH_NORMAL, CONFIG_HEIGHT)
```

### Color Scheme

**Button hues:**
- ON button (active): 68 (green)
- ON button (inactive): 90 (gray)
- OFF button (active): 32 (red)
- OFF button (inactive): 90 (gray)
- SET buttons: 53 (purple/yellow)
- CLR buttons: 32 (red)
- ACTIVE buttons: 68 (green)
- SKIP buttons: 90 (gray)

**Label colors:**
- Section titles: "#ffaa00" (orange)
- Control labels: "#888888" (gray)
- Status text (on): "#00ff00" (green)
- Status text (off): "#888888" (gray)

### Persistence

**No new persistence keys in v2.1** - all moved controls use existing keys.

---

## Testing Checklist (v2.1)

### Window Sizing
- [ ] Expanded height is ~360px (down from 430px)
- [ ] Config height is ~600px when config shown
- [ ] Width stays 400px in all modes (no title bar repositioning)
- [ ] Collapse still works correctly

### Main UI
- [ ] Only frequently-used controls visible on main UI
- [ ] Healer section: Mode toggle + Pause + Status only
- [ ] Commands section: Core combat buttons + Bank/Balance
- [ ] Pets section: Pet buttons + Add/Del only
- [ ] No toggle buttons visible on main UI

### Config Panel - Healer Settings
- [ ] Self Heal toggle works (ON/OFF buttons)
- [ ] Pet Rez toggle works
- [ ] Skip OOR toggle works
- [ ] Tank [SET] button opens target cursor
- [ ] Tank [CLR] button clears tank
- [ ] Tank display shows current tank pet
- [ ] VetKit [SET] button opens target cursor
- [ ] VetKit [CLR] button clears vet kit
- [ ] VetKit display shows current item

### Config Panel - Command Settings
- [ ] Target Reds toggle works
- [ ] Target Grays toggle works
- [ ] Use Potions toggle works
- [ ] Auto-Target toggle works
- [ ] Trapped Pouch [SET] works
- [ ] Use Pouch toggle works
- [ ] Potion counts display correctly

### Config Panel - Pet Order Mode
- [ ] Pet names display correctly in config
- [ ] [ACTIVE] button works per pet
- [ ] [SKIP] button works per pet
- [ ] Button hues update correctly
- [ ] ORDER mode still filters pets correctly

### Functionality Preservation
- [ ] All healing logic works identically
- [ ] All pet commands work identically
- [ ] All hotkeys work identically
- [ ] All persistence works identically
- [ ] Tank pet targeting works
- [ ] Vet kit targeting works
- [ ] Trapped pouch targeting works
- [ ] Friend rez works
- [ ] Potions work
- [ ] Auto-target works

---

## Migration from v2.0 to v2.1

### User Experience
- All settings preserved (same persistence keys)
- Window is visually cleaner (70px less clutter)
- Config panel is longer but better organized
- No functionality lost, only relocated

### Code Changes Summary
- Remove ~15 controls from main UI build
- Add ~50 controls to config panel build
- Update show/hide config panel functions
- Adjust window height constants
- NO changes to core logic/functionality

---

## Future: v2.2 Design Preview

**Major additions in v2.2:**
- Pet hotkey display buttons on main UI (5x)
- Pet arrow indicators [>] on main UI (5x)
- Pet hotkey config section in config panel
- Pet hotkey capture system
- Pet hotkey execution (normal + SHIFT variants)
- 5 new persistence keys

**Estimated scope:**
- +200 lines for pet hotkey UI
- +150 lines for pet hotkey capture system
- +100 lines for pet hotkey execution

**Full v2.2 design spec to be created before implementation**

---

## End of v2.1 Design Spec

This design focuses solely on Phase 1: moving toggles to config panel to save UI real estate. Phase 2 (pet hotkeys) will be designed and implemented separately as v2.2.
