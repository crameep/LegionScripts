# Util_TomeDumper_v1.py - Comprehensive Gump Management Fix Plan

**Date**: 2026-01-31
**Based on**: Complete gump audit

---

## Critical Issues Found

### 🔴 CRITICAL #1: Tome Gumps Never Closed After Dumps
**Impact**: HIGH - UI clutter, potential performance degradation
**Severity**: CRITICAL

**Problem**:
- `dump_single_tome()` opens tome gumps
- Clicks buttons, performs actions
- Returns True/False
- **NEVER closes the tome gump!**

**Result**: After dumping to 5 tomes, you have 5 open tome gumps cluttering the screen.

### 🟡 MEDIUM #2: Config Gump Duplication
**Impact**: MEDIUM - Annoying but not breaking
**Severity**: MEDIUM

**Problem**:
- Config gump uses 0.3s pause after disposal
- Main/tester gumps use immediate disposal (no pause)
- Inconsistent patterns lead to race conditions

### 🟡 MEDIUM #3: Unnecessary Rebuilds
**Impact**: MEDIUM - Performance and UX
**Severity**: LOW-MEDIUM

**Problems**:
1. `on_capture_graphic_clicked()` - Always rebuilds (should update label)
2. `on_toggle_tome_clicked()` - Rebuilds both windows (should update button)
3. `update_config_display()` - Lazy implementation (dead code?)

---

## Fix Plan

### Fix #1: Close Tome Gumps After Operations (CRITICAL)

**Add cleanup to end of `dump_single_tome()`:**

```python
def dump_single_tome(tome_config):
    # ... existing dump logic ...

    try:
        # ... all the dump code ...

        return True

    except Exception as e:
        error_mgr.set_error("Dump error: " + str(e))
        return False

    finally:
        # CLEANUP: Close tome gump if it's open
        gump_id = tome_config.get("gump_id", 0)
        if gump_id > 0 and API.HasGump(gump_id):
            try:
                API.CloseGump(gump_id)
                API.Pause(0.2)  # Brief pause to ensure closure
                debug_msg("Closed tome gump: ID " + str(gump_id))
            except:
                pass  # Ignore errors closing gump
```

**Why `finally` block**:
- Runs whether dump succeeds or fails
- Runs whether function returns early or not
- Ensures gump is ALWAYS cleaned up

**Alternative approach** (if CloseGump doesn't work):
```python
# If API.CloseGump() doesn't exist, use button 0 (close button)
if gump_id > 0 and API.HasGump(gump_id):
    API.ReplyGump(0, gump_id)  # Button 0 is usually close
    API.Pause(0.2)
```

---

### Fix #2: Standardize Gump Disposal Pattern

**Problem**: Three different patterns:
1. Config gump: Set to None, then dispose, then 0.3s pause
2. Main gump: Dispose immediately
3. Tester gump: Dispose immediately

**Solution**: Use ONE consistent pattern everywhere

**Recommended Pattern** (based on what works best):

```python
def build_any_gump():
    global gump_var

    # Save old reference
    old_gump = gump_var

    # Clear global immediately (prevents callbacks from using stale reference)
    gump_var = None

    # Dispose old if exists
    if old_gump:
        try:
            old_gump.Dispose()
            # NO PAUSE - disposal is synchronous
        except:
            pass

    # Create new gump
    gump_var = API.Gumps.CreateGump()
    # ... build gump ...
    API.Gumps.AddGump(gump_var)
```

**Apply to all three gumps**:
- Remove 0.3s pause from config_gump
- Remove debug messages (or keep for testing)
- Use immediate disposal pattern everywhere

---

### Fix #3: Optimize Graphic Capture

**Current** (Line 1128):
```python
editing_tome["target_graphic"] = graphic
editing_dirty = True
build_config_gump()  # ← Always rebuilds
```

**Fixed**:
```python
editing_tome["target_graphic"] = graphic
editing_dirty = True

# Update label directly instead of rebuilding
if "graphic_label" in config_controls:
    config_controls["graphic_label"].SetText("Graphic: 0x{:X}".format(graphic))
    if editing_tome.get("target_hue_specific", False) and "hue_label" in config_controls:
        config_controls["hue_label"].SetText("Hue: 0x{:X}".format(editing_tome.get("target_hue", 0)))
else:
    # First time - rebuild to create labels
    build_config_gump()

# Update button color
if "capture_graphic_btn" in config_controls:
    config_controls["capture_graphic_btn"].SetBackgroundHue(68)
```

**Also store label during build** (around line 1797):
```python
if has_graphic:
    graphicLabel = API.Gumps.CreateGumpTTFLabel("Graphic: 0x{:X}".format(editing_tome["target_graphic"]), 10, "#00ff00")
    graphicLabel.SetPos(165, y_pos + 5)
    config_gump.Add(graphicLabel)
    config_controls["graphic_label"] = graphicLabel  # ← Store reference
```

---

### Fix #4: Optimize Tome Toggle

**Current** (Line 1266):
```python
tomes[index]["enabled"] = not tomes[index].get("enabled", True)
save_tomes()
build_config_gump()  # ← Rebuilds entire window
build_main_gump()    # ← Rebuilds entire window
```

**Fixed** - Option A (Simple):
```python
tomes[index]["enabled"] = not tomes[index].get("enabled", True)
enabled = tomes[index]["enabled"]
save_tomes()

# Update button colors directly
if "tome_enable_" + str(index) in config_controls:
    config_controls["tome_enable_" + str(index)].SetText("[ON]" if enabled else "[OFF]")
    config_controls["tome_enable_" + str(index)].SetBackgroundHue(68 if enabled else 32)

if "tome_enable_main_" + str(index) in main_controls:
    main_controls["tome_enable_main_" + str(index)].SetText("[ON]" if enabled else "[OFF]")
    main_controls["tome_enable_main_" + str(index)].SetBackgroundHue(68 if enabled else 32)
```

**Fixed** - Option B (Fallback):
```python
# If buttons aren't stored, just update main window (config shows tome list, not individual toggles)
tomes[index]["enabled"] = not tomes[index].get("enabled", True)
save_tomes()
build_main_gump()  # Only rebuild main (shows enabled state)
# Don't rebuild config if in edit mode
```

**Note**: Need to check if config window even shows tome toggles - might only be in main window!

---

### Fix #5: Remove Dead Code

**Line 1288** - `update_config_display()`:
```python
def update_config_display():
    """Update config window display without rebuilding"""
    if config_gump is None:
        return

    # Just rebuild the whole window for now
    # (In a more optimized version, we'd update controls directly)
    build_config_gump()
```

**Search for calls**:
```bash
grep "update_config_display()" Util_TomeDumper_v1.py
```

**If no calls found**: Delete the function entirely.

**If calls found**: Convert to direct updates or rebuild as needed.

---

## Implementation Priority

### Phase 1: Critical Fixes (Do First!)
1. ✅ **Close tome gumps after dumps** - Prevents UI clutter
2. ✅ **Standardize disposal pattern** - Fixes duplicate windows

### Phase 2: Performance Optimizations
3. ⚠️ **Optimize graphic capture** - Same pattern as tome/gump capture
4. ⚠️ **Optimize tome toggle** - Direct button update
5. ⚠️ **Remove dead code** - Cleanup

---

## Testing Plan

### Test 1: Tome Gump Cleanup
**Steps**:
1. Configure 3 tomes
2. Run dump operation on all 3
3. **Check**: Are tome gumps closed after dump completes?

**Expected**: All tome gumps close automatically
**Current**: All 3 tome gumps stay open

### Test 2: Config Window Duplication
**Steps**:
1. Add new tome
2. Rapidly: Target tome → Detect gump → Capture graphic

**Expected**: Only 1 config window visible
**Current**: Can get 2-3 windows

### Test 3: Graphic Capture
**Steps**:
1. Edit tome
2. Enable graphic targeting
3. Click capture graphic
4. Target a container

**Expected**: Label updates instantly, no window rebuild
**Current**: Window rebuilds

### Test 4: Tome Toggle
**Steps**:
1. Have 3 tomes configured
2. Toggle one tome on/off

**Expected**: Button color changes, no rebuild
**Current**: Both windows rebuild

---

## Code References

**Tome gump cleanup**:
- Add `finally` block to `dump_single_tome()` (after line 659)

**Gump disposal standardization**:
- `build_config_gump()` - lines 1475-1491
- `build_main_gump()` - lines 1391-1396
- `build_tester_gump()` - lines 1971-1976

**Graphic capture optimization**:
- Callback: line 1128
- Build: line 1797 (create label)

**Tome toggle optimization**:
- Callback: line 1266
- Check where toggles are shown (main window?)

**Dead code removal**:
- Line 1288 - `update_config_display()`

---

## Summary

**Total Issues**: 5
**Critical**: 1 (tome gumps)
**Medium**: 2 (duplicates, unnecessary rebuilds)
**Low**: 2 (minor optimizations, dead code)

**Estimated Fixes**:
- Critical fixes: 30 minutes
- All fixes: 1-2 hours

**Expected Improvements**:
- ✅ No more tome gump clutter
- ✅ No more duplicate config windows
- ✅ Faster UI updates during setup
- ✅ Cleaner, more maintainable code

---

**End of Fix Plan**
