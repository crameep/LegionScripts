# Util_TomeDumper_v1.py - Set Fill Button UI Update Fix

**Date**: 2026-01-31
**Issue**: Clicking "[SET AS FILL]" in tester window doesn't update config window to show new button ID
**Root Cause**: Comment said "Don't rebuild", but config window label wasn't being updated

---

## Bug Description

**User Report**: "When clicking set as fill UI doesn't update"

**Symptoms**:
- Open tester window, test buttons, click "[SET AS FILL]"
- Button ID gets saved (confirmed by success message)
- Tester window closes
- **Config window still shows old button ID** (or no button if first time)
- Must close and reopen config window to see new value

---

## Root Cause Analysis

**Location**: Lines 1301-1322 (`on_set_custom_button`) and 1324-1336 (`on_use_button_clicked`)

**Problem**: Callbacks update the data but don't update the UI

```python
def on_set_custom_button():
    # ...
    editing_tome["fill_button_id"] = button_id  # ✓ Updates data
    editing_dirty = True
    API.SysMsg("Fill button set to: " + str(button_id), 68)  # ✓ Shows message
    # Don't rebuild - just close tester  # ✗ WRONG - UI not updated!

    # Close tester
    if tester_gump:
        tester_gump.Dispose()
```

**Comment on line 1314**: "Don't rebuild - just close tester"
**Comment on line 1332**: "Don't rebuild - value is saved, user can verify in config window"

**The Problem**: Config window **can't verify** because it shows a label created during build (line 1586):
```python
buttonLabel = API.Gumps.CreateGumpTTFLabel("Button: " + str(editing_tome["fill_button_id"]), 10, "#00ff00")
```

This label is created once and never updated!

---

## Fix Applied

### Change 1: Store Label Reference (Line 1589)

**Before**:
```python
if btn_captured:
    buttonLabel = API.Gumps.CreateGumpTTFLabel("Button: " + str(editing_tome["fill_button_id"]), 10, "#00ff00")
    buttonLabel.SetPos(145, y_pos + 5)
    config_gump.Add(buttonLabel)
    # Label reference lost!
```

**After**:
```python
if btn_captured:
    buttonLabel = API.Gumps.CreateGumpTTFLabel("Button: " + str(editing_tome["fill_button_id"]), 10, "#00ff00")
    buttonLabel.SetPos(145, y_pos + 5)
    config_gump.Add(buttonLabel)
    config_controls["fill_button_label"] = buttonLabel  # ✓ Store for updates
```

### Change 2: Update Label in `on_set_custom_button()` (Lines 1314-1324)

**Before**:
```python
editing_tome["fill_button_id"] = button_id
editing_dirty = True
API.SysMsg("Fill button set to: " + str(button_id), 68)
# Don't rebuild - just close tester

# Close tester
if tester_gump:
    tester_gump.Dispose()
```

**After**:
```python
editing_tome["fill_button_id"] = button_id
editing_dirty = True
API.SysMsg("Fill button set to: " + str(button_id), 68)

# Update config window label directly instead of rebuilding
if "fill_button_label" in config_controls:
    config_controls["fill_button_label"].SetText("Button: " + str(button_id))
else:
    # If label doesn't exist (button not previously set), rebuild to show it
    build_config_gump()

# Update test button color in config if it exists
if "test_buttons_btn" in config_controls:
    config_controls["test_buttons_btn"].SetBackgroundHue(68)  # Green when button set

# Close tester
if tester_gump:
    tester_gump.Dispose()
```

### Change 3: Update Label in `on_use_button_clicked()` (Lines 1332-1352)

**Same changes applied** - update label directly instead of rebuilding.

---

## Why This Fix Works

### Correct Flow Now:

1. **User clicks "[SET AS FILL]"** in tester window
2. **Updates data**: `editing_tome["fill_button_id"] = button_id` ✓
3. **Checks if label exists**:
   - **If exists**: Updates text directly with `SetText("Button: X")` → **Instant update!**
   - **If doesn't exist**: Rebuilds config to show new label (first-time setup)
4. **Updates button color**: "[TEST BUTTONS]" turns green (indicates button is set)
5. **Closes tester window**

**Result**: Config window shows new button ID **immediately**, no rebuild needed!

### Two Paths:

**Path 1: Label Already Exists** (button was previously set)
- Direct update with `SetText()`
- Fast, no window rebuild
- **This is the common case!**

**Path 2: Label Doesn't Exist** (first time setting button)
- Rebuild config to create label
- Necessary because label wasn't there before
- **Rare case** (only happens once per tome)

---

## Pattern Consistency

This follows the same optimization pattern used elsewhere:

**Similar Fixes in This Session**:
1. ✅ Gump detection - Update button text instead of rebuild
2. ✅ Hue-specific toggle - Update button colors instead of rebuild
3. ✅ **Fill button set** - Update label text instead of rebuild

**Pattern**:
```python
# GOOD - Direct update (instant)
if "label_key" in controls:
    controls["label_key"].SetText("New text")
else:
    # Fallback rebuild if control doesn't exist
    build_window()

# BAD - Always rebuild (slow, causes duplicates)
build_window()
```

---

## Testing Instructions

### Test Case: Set Fill Button (Button Already Set)

**Setup**:
1. Edit a tome that already has a fill button set
2. Config window shows "Button: 1"

**Test Steps**:
1. Click "[TEST BUTTONS]" in config
2. Type "5" in custom input
3. Click "[TEST]" to verify button 5 works
4. Click "[SET AS FILL]"

**Expected**:
- ✅ Message: "Fill button set to: 5"
- ✅ Tester window closes
- ✅ **Config window immediately shows "Button: 5"** (no rebuild!)
- ✅ "[TEST BUTTONS]" button turns green

**Success Criteria**:
- Config window updates instantly
- No window rebuild/flicker
- No duplicate windows

### Test Case: Set Fill Button (First Time)

**Setup**:
1. Edit a tome with no fill button set
2. Config window shows no button label

**Test Steps**:
1. Click "[TEST BUTTONS]"
2. Set button to "1"
3. Click "[SET AS FILL]"

**Expected**:
- ✅ Message: "Fill button set to: 1"
- ✅ Tester window closes
- ✅ **Config window rebuilds to show "Button: 1" label** (necessary - label didn't exist)
- ✅ "[TEST BUTTONS]" button turns green

**Success Criteria**:
- Label appears in config window
- Only 1 config window visible (no duplicates)

---

## Additional Improvements

Also updates "[TEST BUTTONS]" button color:
- **Gray (90)**: No button set, gump not ready
- **Yellow (43)**: Gump ready, no button set
- **Green (68)**: Button set and ready to use

This provides visual feedback that button configuration is complete.

---

## Related Fixes in This Session

1. **UI rebuild optimization** - Gump detection updates directly
2. **Multi-target bug** - Fixed redundant WaitForTarget()
3. **Container pre-check** - Fixed hardcoded backpack check
4. **Duplicate windows** - Added disposal pause
5. **Set fill button** - This fix (updates label directly)

All following the same pattern: **Update controls directly, avoid unnecessary rebuilds**.

---

## Files Modified

- `Utility/Util_TomeDumper_v1.py` - Updated `on_set_custom_button()`, `on_use_button_clicked()`, and config gump build

## Validation

- ✅ Python syntax validated
- ✅ Pattern consistency maintained
- ✅ Fallback rebuild for first-time setup
- ✅ Ready for testing

---

**End of Report**
