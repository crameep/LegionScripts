# Phase 1 Utilities - Implementation Complete ✅

**Date:** 2026-01-27
**Status:** All Phase 1 utilities implemented in LegionUtils v3.0

---

## Summary

Successfully implemented all Phase 1 utilities from the deep dive analysis.

**LegionUtils:**
- **Before:** 406 lines (v2.0)
- **After:** 858 lines (v3.0)
- **Added:** 452 lines of reusable utilities

---

## What Was Added

### 1. ✅ Enhanced Item Counting

**Functions:**
- `get_item_count(graphic, container_serial=None, recursive=True)` - Universal item counter
- `has_item(graphic, min_count=1, container_serial=None)` - Quick predicate
- `count_items_by_type(*graphics, **kwargs)` - Batch count multiple items

**Replaces:**
- `get_potion_count()` in 3 scripts (150 lines)
- `count_gold_in_bag()` in 1 script (40 lines)
- `get_bandage_count()` (now a wrapper)
- Various other item counting code

**Estimated Savings:** 250 lines across codebase

**Usage Examples:**
```python
# Count any item type
heal_potions = get_item_count(HEAL_POTION_GRAPHIC)
gold = get_item_count(GOLD_GRAPHIC, container_serial=satchel)
bandages = get_item_count(BANDAGE_GRAPHIC)

# Quick checks
if has_item(HEAL_POTION_GRAPHIC, min_count=5):
    # Have at least 5 heal potions
    pass

# Batch count
counts = count_items_by_type(
    HEAL_POTION_GRAPHIC,
    CURE_POTION_GRAPHIC,
    REFRESH_POTION_GRAPHIC
)
# Returns: {0x0F0C: 15, 0x0F07: 8, 0x0F0B: 3}
```

---

### 2. ✅ WindowPositionTracker Class

**Purpose:** Manages window position with periodic updates and persistence

**Replaces:** ~40-50 lines per script of manual position tracking

**Features:**
- Loads saved position on init
- Periodic position updates (every 2 seconds default)
- Saves on window close

**Usage Example:**
```python
# Setup
pos_tracker = WindowPositionTracker(gump, SETTINGS_KEY, 100, 100)
gump.SetRect(pos_tracker.last_x, pos_tracker.last_y, WIDTH, HEIGHT)

# In main loop
pos_tracker.update()  # Auto-tracks position

# On window close
pos_tracker.save()  # Auto-saves position
```

**Before (50 lines):**
```python
last_known_x = 100
last_known_y = 100
last_position_check = 0

savedPos = API.GetPersistentVar(...)
posXY = savedPos.split(',')
lastX = int(posXY[0])
lastY = int(posXY[1])
# ... 40 more lines ...
```

**After (3 lines):**
```python
pos_tracker = WindowPositionTracker(gump, SETTINGS_KEY)
# In loop: pos_tracker.update()
# On close: pos_tracker.save()
```

**Estimated Savings:** 200 lines across 5 scripts

---

### 3. ✅ ToggleSetting Class

**Purpose:** Manages boolean settings with persistence and button updates

**Replaces:** ~20-25 lines per toggle function

**Features:**
- Automatic load/save persistence
- Button appearance updates (on/off pairs or single toggle)
- System messages
- Change callbacks

**Usage Example:**
```python
# Create toggle
auto_heal = ToggleSetting(
    AUTO_HEAL_KEY, True, "Auto Heal",
    {"off": auto_heal_off_btn, "on": auto_heal_on_btn},
    update_display
)

# Wire callbacks
API.Gumps.AddControlOnClick(auto_heal_on_btn, lambda: auto_heal.set(True))
API.Gumps.AddControlOnClick(auto_heal_off_btn, lambda: auto_heal.set(False))

# Use in code
if auto_heal.value:
    do_healing()
```

**Before (25 lines per toggle):**
```python
def toggle_auto_heal():
    global AUTO_HEAL
    AUTO_HEAL = not AUTO_HEAL
    API.SavePersistentVar(AUTO_HEAL_KEY, str(AUTO_HEAL), API.PersistentVar.Char)

    if "auto_heal_off" in config_controls:
        config_controls["auto_heal_off"].SetBackgroundHue(32 if not AUTO_HEAL else 90)
    if "auto_heal_on" in config_controls:
        config_controls["auto_heal_on"].SetBackgroundHue(68 if AUTO_HEAL else 90)

    API.SysMsg("Auto Heal: " + ("ON" if AUTO_HEAL else "OFF"), ...)
    update_display()
```

**After (5 lines):**
```python
auto_heal = ToggleSetting(AUTO_HEAL_KEY, True, "Auto Heal",
                          {"off": off_btn, "on": on_btn}, update_display)
API.Gumps.AddControlOnClick(on_btn, lambda: auto_heal.set(True))
```

**Estimated Savings:** 200 lines across scripts with toggles

---

### 4. ✅ ActionTimer Class

**Purpose:** Tracks timing for single actions with duration

**Replaces:** Manual start_time + duration tracking

**Simpler than CooldownTracker:** For one-time actions that complete (not recurring cooldowns)

**Usage Example:**
```python
bandage_timer = ActionTimer(BANDAGE_DELAY)

def start_bandage():
    bandage_timer.start()
    statusLabel.SetText("Healing...")

# In main loop
if bandage_timer.is_complete():
    # Ready for next action
    do_next_action()
else:
    # Show remaining time
    remaining = int(bandage_timer.time_remaining())
    statusLabel.SetText("Healing (" + str(remaining) + "s)")
```

**Before (15-20 lines):**
```python
heal_start_time = 0
HEAL_STATE = "idle"

def start_heal():
    global heal_start_time, HEAL_STATE
    heal_start_time = time.time()
    HEAL_STATE = "healing"

def check_heal_complete():
    global HEAL_STATE
    if HEAL_STATE == "healing":
        if time.time() >= heal_start_time + BANDAGE_DELAY:
            HEAL_STATE = "idle"
            return True
    return False
```

**After (5 lines):**
```python
heal_timer = ActionTimer(BANDAGE_DELAY)
# Later: heal_timer.start()
# Check: heal_timer.is_complete()
```

**Estimated Savings:** 60-80 lines across scripts with manual timing

---

### 5. ✅ ExpandableWindow Class

**Purpose:** Manages window expand/collapse with control visibility

**Replaces:** ~80-120 lines per script of expand/collapse code

**Features:**
- Load/save expanded state
- Toggle button updates
- Show/hide controls
- Resize window

**Usage Example:**
```python
expander = ExpandableWindow(
    gump, expandBtn, EXPANDED_KEY,
    width=280, expanded_height=600, collapsed_height=24
)

# Register collapsible controls
expander.add_controls(
    hpLabel, stamLabel, manaLabel,
    healBtn, cureBtn, buffBtn
)

# Wire button
API.Gumps.AddControlOnClick(expandBtn, expander.toggle)
```

**Before (120 lines):**
```python
is_expanded = True

def toggle_expand():
    global is_expanded
    is_expanded = not is_expanded
    API.SavePersistentVar(...)

    if is_expanded:
        expandBtn.SetText("[-]")
        hpLabel.IsVisible = True
        stamLabel.IsVisible = True
        # ... 40 more lines of .IsVisible = True
        gump.SetRect(x, y, width, expanded_height)
    else:
        expandBtn.SetText("[+]")
        hpLabel.IsVisible = False
        # ... 40 more lines of .IsVisible = False
        gump.SetRect(x, y, width, collapsed_height)
```

**After (8 lines):**
```python
expander = ExpandableWindow(gump, expandBtn, EXPANDED_KEY, 280, 600, 24)
expander.add_controls(hpLabel, stamLabel, manaLabel, healBtn, cureBtn, buffBtn)
API.Gumps.AddControlOnClick(expandBtn, expander.toggle)
```

**Estimated Savings:** 320 lines across 4 scripts

---

## Total Impact Summary

| Utility | Scripts Benefit | Lines Saved | Complexity |
|---------|-----------------|-------------|------------|
| Enhanced item counting | 5 | 250 | Medium |
| WindowPositionTracker | 5 | 200 | Low |
| ToggleSetting | 5 | 200 | Medium |
| ActionTimer | 4 | 80 | Low |
| ExpandableWindow | 4 | 320 | Medium |
| **TOTAL** | | **1,050** | |

**Note:** These are conservative estimates. Actual savings may be higher.

---

## Version History

**v3.0 (2026-01-27) - Phase 1 Complete**
- Added 452 lines of reusable utilities
- 5 major pattern classes implemented
- Ready for script refactoring

**v2.0 (2026-01-25) - Tamer Suite Enhancements**
- CooldownTracker, player state, potion management
- Pet list helpers

**v1.0 (2026-01-24) - Initial Release**
- Basic utilities, ErrorManager, persistence helpers

---

## Next Steps

### Ready to Refactor

Now that utilities are implemented, we can:

1. **Pick a script to refactor first**
   - Recommend: Dexer_Suite.py (biggest win - 250+ lines)
   - Alternative: Util_Runebook_v1.py (highest % - 22%)

2. **Start with one pattern**
   - Recommend: Item counting (easiest, safest)
   - Then: Window position tracker
   - Then: Toggle settings

3. **Test thoroughly**
   - In-game testing after each refactor
   - Compare with original script behavior

---

## Testing Checklist

Before using in scripts:

- [ ] Test get_item_count() with various graphics
- [ ] Test has_item() predicate
- [ ] Test count_items_by_type() batch counting
- [ ] Test WindowPositionTracker in simple test script
- [ ] Test ToggleSetting with button pairs
- [ ] Test ActionTimer timing accuracy
- [ ] Test ExpandableWindow expand/collapse

---

## Usage Notes

### Import Pattern

```python
import API
import time
import sys

sys.path.append(r"G:\Ultima Online\TazUO-Launcher.win-x64\TazUO\LegionScripts\CoryCustom\refactors")
from LegionUtils import *
```

### Backward Compatibility

All existing functions still work:
- `get_potion_count(graphic)` - Still available (wraps get_item_count)
- `get_bandage_count()` - Still available
- All v2.0 utilities unchanged

New utilities are additive - won't break existing scripts.

---

## What's Next

Choose your path:

**Option A: Start Refactoring**
- Pick Dexer_Suite.py
- Start with item counting
- Test and iterate

**Option B: More Testing**
- Create test scripts for new utilities
- Verify all functions work as expected
- Then proceed to refactoring

**Option C: Continue with Phase 2**
- Implement HotkeyManager class
- Add more advanced patterns
- Expand library further

---

**Status:** ✅ All Phase 1 utilities implemented and ready for use!

Let me know which script you'd like to refactor first, or if you want to test the utilities before proceeding.
