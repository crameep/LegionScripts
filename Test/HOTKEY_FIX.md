# Hotkey Capture Fix - v2.4

## Problem
The screenshot showed repeated errors when trying to set hotkeys. The script was using `API.WaitForHotkey()` which **doesn't actually exist** in the Legion API.

## Solution
Replaced the broken blocking hotkey system with your proven **non-blocking pattern** from `Test/Util_HotkeyCapture.py`.

---

## What Changed

### ✅ New Hotkey System (Non-Blocking)

**Pattern Used:** Closure factory with state tracking (same as Util_HotkeyCapture.py)

1. **Register ALL possible keys** on startup (F1-F12, A-Z, 0-9, numpad, arrows, etc.)
2. **Each key handler** checks:
   - If `capturing_for` is set → assign key to that destination
   - If not capturing → execute recall if key matches a destination
3. **Click hotkey button** → sets `capturing_for` state and button turns PURPLE
4. **Press any key** → assigns it and saves
5. **Press ESC** → cancels capture mode

### ✅ Visual Feedback

- **Purple (38)** = Listening for key press
- **Green (68)** = Configured and ready
- **Gray (90)** = Not configured

### ✅ Removed Broken Code

- ❌ `API.WaitForHotkey()` - doesn't exist
- ❌ `API.UnregisterHotkey()` - not needed (auto-cleanup)
- ❌ `register_hotkeys()` - replaced with ALL_KEYS registration
- ❌ Blocking capture functions

### ✅ Added Features

- ESC to cancel hotkey capture
- Support for 70+ keys (including modifiers if supported)
- Non-blocking capture (UI stays responsive)
- Clear visual states during capture

---

## How It Works Now

### Setup Flow
1. Click [C] in title bar to open hotkey config panel
2. Click the button next to "Home" (turns PURPLE, says "[Listening...]")
3. Press F1 (or any key you want)
4. Button updates to "[F1]" and turns GREEN
5. Press F1 in-game to recall to Home

### Cancel Flow
- If you change your mind, press ESC while listening
- Button returns to previous state

### Technical Details

**Closure Factory Pattern:**
```python
def make_key_handler(key_name):
    def handler():
        if capturing_for is not None:
            # Assign key to destination
        else:
            # Execute recall if bound
    return handler

# Register all keys
for key in ALL_KEYS:
    API.OnHotKey(key, make_key_handler(key))
```

This creates a unique handler for each key that remembers which key it is.

---

## Files Modified

**Test/Util_Runebook_Hotkeys.py**
- Lines 69-158: Replaced entire hotkey system
- Lines 877-894: Changed initialization to register ALL_KEYS
- Line 28: Version → 2.4
- Lines 1-38: Updated header with new features

**Changes:**
- Added `ALL_KEYS` list (70+ keys)
- Added `make_key_handler()` closure factory
- Added `start_capture_home/bank/custom1/custom2()` functions
- Removed `capture_hotkey()`, `register_hotkeys()`, `cleanup_hotkeys()`
- Simplified cleanup (hotkeys auto-cleanup on script stop)

---

## Testing Checklist

- [ ] Launch script - should see "Registered XX keys" message
- [ ] Click [C] to open config panel
- [ ] Click hotkey button - should turn PURPLE and say "[Listening...]"
- [ ] Press a key - should bind and turn GREEN
- [ ] Press that key in-game - should recall
- [ ] Try ESC during capture - should cancel
- [ ] Close and reopen script - hotkeys should persist
- [ ] Try different keys (F1, NUMPAD5, TAB, etc.)

---

## Why This Pattern Works

1. **Non-Blocking** - No `WaitForHotkey()` call that freezes UI
2. **State-Based** - Simple `capturing_for` flag tracks mode
3. **Proven** - Already working in Util_HotkeyCapture.py
4. **Flexible** - Supports any key Legion recognizes
5. **Responsive** - UI and other hotkeys work during capture

---

## Version History

**v2.4** (2026-01-24)
- Fixed hotkey capture system using closure factory pattern
- Added ESC to cancel capture
- Unified button colors (green/gray semantic coding)
- Non-blocking hotkey registration

**v2.3**
- GUI hue unification
- Collapsible panels

**v2.0-2.2**
- Initial hotkey support (broken)
- Dual-mode UI

---

**Status:** ✅ Ready to test!

The hotkey capture should now work perfectly. Let me know if you see any errors!
