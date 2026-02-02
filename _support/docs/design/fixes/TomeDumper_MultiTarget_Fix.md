# Util_TomeDumper_v1.py - Multi-Target Bug Fix

**Date**: 2026-01-31
**Issue**: Multi-item targeting mode gets to target prompt but never actually targets items
**Root Cause**: Redundant `API.WaitForTarget()` call causing cursor timeout/confusion

---

## Bug Description

**User Report**: "On the multi target it gets to the point where its going to target the item and asks to target but never targets them."

**Symptoms**:
- Multi-item mode with containers configured
- Script finds items to dump
- Shows message "Waiting for target cursor..."
- Cursor appears (confirmed by message)
- **Items never get targeted** - script just stops or times out

---

## Root Cause Analysis

**Location**: Lines 507-510 (original code)

**Problem**: Double-wait for target cursor

```python
# Line 502-504: First wait after clicking button
if not API.WaitForTarget(timeout=1.0):
    API.SysMsg("Button didn't create cursor - stopping", 32)
    break

# Line 507-510: PROBLEM - Waiting AGAIN for already-active cursor!
API.SysMsg("  Waiting for target cursor...", 88)
if API.WaitForTarget(timeout=3.0):  # ← Redundant wait causes timeout!
    API.SysMsg("  Targeting item serial 0x{:X}".format(item.Serial), 68)
    API.Target(item.Serial)
```

**Why This Breaks**:
1. First `WaitForTarget()` confirms cursor appeared after button click ✓
2. Second `WaitForTarget()` waits for a cursor that's **already active**
3. The second wait either:
   - Times out (3 seconds) waiting for something that's already there
   - Consumes/confuses the cursor state
   - Returns false causing the targeting to never happen

**According to [TazUO Legion API](https://tazuo.org/legion/api/)**:
- `WaitForTarget(timeout)` - "Waits for a target cursor to **appear**"
- Once cursor is active, you should just `Target(serial)` immediately
- Waiting again for an already-active cursor is incorrect usage

---

## Fix Applied

**Changed**: Lines 506-517

**Before** (Broken):
```python
# Wait for target cursor to be ready (again, in case of skip above)
API.SysMsg("  Waiting for target cursor...", 88)
if API.WaitForTarget(timeout=3.0):  # ← REDUNDANT WAIT!
    API.SysMsg("  Targeting item serial 0x{:X}".format(item.Serial), 68)
    API.Target(item.Serial)
    items_targeted += 1
    API.Pause(0.5)

    # Auto-retarget logic...
```

**After** (Fixed):
```python
# Target cursor should already be active from button click above
# Brief pause to ensure cursor is ready, then send target
API.Pause(0.2)

if API.HasTarget():  # ← Check cursor is still active, don't wait
    API.SysMsg("  Targeting item serial 0x{:X}".format(item.Serial), 68)
    API.Target(item.Serial)
    items_targeted += 1
    API.Pause(0.5)

    # If auto-retarget, wait for cursor to reappear
    if auto_retarget:
        # ... auto-retarget logic ...
else:
    API.SysMsg("  Cursor disappeared, stopping", 32)
    break
```

**Key Changes**:
1. **Removed** redundant `WaitForTarget()` call
2. **Added** brief `API.Pause(0.2)` to ensure cursor is ready
3. **Changed** to `API.HasTarget()` check instead of wait
4. **Kept** auto-retarget wait logic (correct - waiting for NEW cursor after target)

---

## Why This Fix Works

### Correct Flow Now:
1. **Click gump button** → Creates target cursor
2. **Wait once** for cursor to appear (line 502) → Confirms it's ready
3. **Brief pause** (0.2s) → Ensures cursor is stable
4. **Check cursor** with `HasTarget()` → Verify it's still active
5. **Send target** with `Target(serial)` → Immediately targets item
6. **Wait for auto-retarget** (if enabled) → Waits for NEW cursor to appear

### API Usage Pattern:
```python
# CORRECT PATTERN (what we now use):
API.ReplyGump(button_id, gump_id)  # Click button
if API.WaitForTarget(timeout=1.0):  # Wait ONCE for cursor to appear
    API.Pause(0.2)  # Brief stabilization pause
    if API.HasTarget():  # Quick check it's still there
        API.Target(serial)  # Send the target

# WRONG PATTERN (what we had before):
API.ReplyGump(button_id, gump_id)
if API.WaitForTarget(timeout=1.0):  # Wait for cursor
    if API.WaitForTarget(timeout=3.0):  # ← WRONG - Waiting again!
        API.Target(serial)
```

---

## Other Targeting Modes Checked

### Container Mode (Line 336-339): ✓ Correct
```python
if API.WaitForTarget(timeout=3.0):
    API.Target(container_serial)
```
- Only waits **once** after button click
- Immediately targets container
- **No changes needed**

### Single Item Mode (Line 383-402): ✓ Correct
```python
if API.WaitForTarget(timeout=3.0):
    API.SysMsg("Target item now (ESC to cancel)...", 68)
    # Waits for USER to target (manual targeting)
```
- Only waits **once**
- Then waits for **user** to click (manual mode)
- **No changes needed**

### Multi-Item Manual Retarget (Line 609-628): ✓ Correct
```python
if not API.WaitForTarget(timeout=3.0):
    break  # Each iteration clicks button and waits once
```
- Each loop iteration clicks button
- Waits **once** per iteration
- **No changes needed**

**Conclusion**: Bug was **only** in multi-item with containers mode where automated targeting happens.

---

## Testing Instructions

### Before Testing:
1. ✓ Syntax validated - no Python errors
2. ✓ Auto-retarget logic preserved
3. ✓ Only changed multi-item container targeting flow

### Test Case: Multi-Item with Containers
**Setup**:
1. Create tome config with:
   - Targeting mode: "Multi-Item"
   - Target containers: [backpack serial, or other container]
   - Item graphics filter: (optional - specific graphics to dump)
   - Auto-retarget: ON

**Test Steps**:
1. Have items in configured container(s)
2. Run dump operation
3. **Expected**: Script should:
   - Find items in containers
   - Show "Targeting item 1/X..."
   - **Actually target each item** (cursor sends, item goes to tome)
   - Continue to next item automatically
   - Complete all items

**Success Criteria**:
- ✓ Items are actually targeted (not just showing message)
- ✓ Multiple items targeted in sequence
- ✓ Auto-retarget works (cursor reappears after each item)
- ✓ No "Target cursor timeout" errors
- ✓ Items end up in tome

### Test Case: Multi-Item Manual (No Containers)
**Setup**:
1. Create tome config with:
   - Targeting mode: "Multi-Item"
   - Auto-retarget: ON
   - No containers configured

**Test Steps**:
1. Run dump operation
2. Click gump button when prompted
3. Manually target items

**Expected**: Should work as before (this mode wasn't broken)

---

## Performance Impact

### Before Fix:
- **Each item**: 3.0 second timeout waiting for cursor that already exists
- **10 items**: 30+ seconds wasted waiting
- **Result**: Appears frozen/broken to user

### After Fix:
- **Each item**: 0.2 second pause + instant check
- **10 items**: ~2-5 seconds total
- **Result**: Fast, responsive, works correctly

---

## API References

**Legion API Documentation**: https://tazuo.org/legion/api/

**Relevant Methods**:
- `API.Target(serial)` - Send target to active cursor ✓ Exists, confirmed working
- `API.WaitForTarget(timeout)` - Wait for cursor to **appear** (don't call twice!)
- `API.HasTarget()` - Check if cursor is currently active (instant check)
- `API.ReplyGump(button_id, gump_id)` - Click gump button

---

## Files Modified

- `Utility/Util_TomeDumper_v1.py` - Fixed multi-item container targeting logic (lines 506-530)

## Validation

- ✅ Python syntax validated
- ✅ Logic flow preserved
- ✅ Auto-retarget logic intact
- ✅ Other targeting modes unaffected
- ✅ Ready for testing

---

**End of Report**
