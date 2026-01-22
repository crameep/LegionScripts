# Debug Console Integration Guide

## Overview

The Debug Console (`Util_DebugConsole.py`) provides centralized debug logging for all your scripts. Instead of spamming `API.SysMsg()` during development, scripts can send messages to the console where they can be filtered, reviewed, and exported.

## Quick Start

### 1. Start the Debug Console

Load `Util_DebugConsole.py` in TazUO - it runs standalone and monitors for messages from other scripts.

### 2. Add Debug Helper to Your Script

Copy this block into any script that needs debugging (place after imports, before your main code):

```python
# ============ DEBUG HELPER ============
DEBUG_QUEUE_KEY = "DebugConsole_Queue"
DEBUG_ENABLED_KEY = "DebugConsole_Enabled"
_debug_script_name = "YourScriptName"  # ← CHANGE THIS!

def _debug_log(level, message):
    """Send message to debug console if enabled"""
    try:
        # Fast path: check if console is enabled
        enabled = API.GetPersistentVar(DEBUG_ENABLED_KEY, "True", API.PersistentVar.Char)
        if enabled != "True":
            return  # Console disabled, skip entirely

        # Format message: timestamp|source|level|message
        timestamp = str(time.time())
        record = timestamp + "|" + _debug_script_name + "|" + level + "|" + str(message)

        # Append to queue
        queue = API.GetPersistentVar(DEBUG_QUEUE_KEY, "", API.PersistentVar.Char)
        if queue:
            records = queue.split("\x1E")  # ASCII Record Separator
            records.append(record)
            # Keep last 50 messages to prevent queue overflow
            if len(records) > 50:
                records = records[-50:]
            queue = "\x1E".join(records)
        else:
            queue = record

        API.SavePersistentVar(DEBUG_QUEUE_KEY, queue, API.PersistentVar.Char)
    except:
        pass  # Silent fail - don't crash main script

# Convenience functions
def debug_info(msg): _debug_log("INFO", msg)
def debug_warn(msg): _debug_log("WARN", msg)
def debug_error(msg): _debug_log("ERROR", msg)
def debug_debug(msg): _debug_log("DEBUG", msg)
# ============ END DEBUG HELPER ============
```

### 3. Use Debug Functions

Replace your `API.SysMsg()` debugging calls:

**Before:**
```python
if DEBUG:
    API.SysMsg("Healing pet: " + pet_name, 88)
    API.SysMsg("Bandage count: " + str(bandage_count), 88)
```

**After:**
```python
debug_info("Healing pet: " + pet_name)
debug_debug("Bandage count: " + str(bandage_count))
```

## Message Levels

| Level | When to Use | Color in Console |
|-------|-------------|------------------|
| **INFO** | Normal operations, state changes | Green |
| **WARN** | Warnings, low resources, retries | Yellow |
| **ERROR** | Errors, failures, exceptions | Red |
| **DEBUG** | Verbose debugging, loop iterations | Gray |

## Examples

### Example 1: Tamer Script Integration

```python
import API
import time

_debug_script_name = "TamerSuite"

# ... paste debug helper here ...

def heal_pet(pet_serial):
    pet = API.Mobiles.FindMobile(pet_serial)
    if not pet:
        debug_error("Pet not found: " + str(pet_serial))
        return False

    debug_info("Healing " + pet.Name + " (HP: " + str(pet.Hits) + "/" + str(pet.HitsMax) + ")")

    # Apply bandage...
    debug_debug("Bandage applied, waiting 4.5s")

    return True

def main_loop():
    while not API.StopRequested:
        debug_debug("Main loop tick")

        if need_heal():
            heal_pet(get_next_pet())

        API.Pause(0.1)
```

### Example 2: Error Tracking

```python
try:
    gold_amount = transfer_gold(source, dest)
    debug_info("Transferred " + str(gold_amount) + " gold")
except Exception as e:
    debug_error("Transfer failed: " + str(e))
```

### Example 3: State Machine Debugging

```python
def update_state():
    global state

    debug_debug("Current state: " + state)

    if state == "idle":
        if should_heal():
            state = "healing"
            debug_info("State change: idle -> healing")

    elif state == "healing":
        if heal_complete():
            state = "idle"
            debug_info("State change: healing -> idle")
```

## Console Features

### Filtering

- **Level Filter**: Click `[INFO]` `[WARN]` `[ERR]` `[DBG]` buttons to toggle visibility
- **Source Filter**: Click `[ALL]` button to cycle through scripts
- **Combine Filters**: Both filters work together

### Controls

- **[CLR]**: Clear display (doesn't delete queue)
- **[PAUSE]**: Stop reading new messages (review current messages)
- **[RESUME]**: Resume reading messages
- **[SCROLL:ON/OFF]**: Toggle auto-scroll (ON = follow new messages, OFF = stay at top)
- **[-]/[+]**: Collapse/expand window

### Export to File

1. Filter messages as desired (by level/source)
2. Click **[EXPORT TO FILE]**
3. File saved to `Utility/Logs/debug_export_YYYYMMDD_HHMMSS.txt`
4. Open file in text editor to copy/paste

Example export:
```
Debug Console Export
Date: 2026-01-22 15:45:30
Filter: INFO=ON WARN=ON ERROR=OFF DEBUG=OFF
Source: TamerSuite
============================================================

15:45:15 [TamerSuite] INFO: Healing pet Fluffy
15:45:20 [TamerSuite] WARN: Low bandages: 5 remaining
15:45:25 [TamerSuite] INFO: Healed Fluffy successfully

============================================================
Total: 3 messages exported
```

## Performance Impact

- **Console Disabled**: Zero overhead - early return before any processing
- **Console Enabled**: ~1ms per debug call (format + write to persistent var)
- **Queue Limit**: Automatically trims to last 50 messages
- **Console Polling**: 200ms interval, minimal CPU usage

## Disabling Debug Console

To temporarily disable ALL debug logging across all scripts:

1. Close the Debug Console
2. Or toggle the console's internal "enabled" state (future feature)

When disabled, `_debug_log()` returns immediately without any processing.

## Troubleshooting

### Messages not appearing

1. Verify Debug Console is running (`Util_DebugConsole.py`)
2. Check script name matches: `_debug_script_name = "YourScriptName"`
3. Verify level filter is enabled (e.g., `[DEBUG]` button is green)
4. Check source filter (cycle to `[ALL]` or your script name)

### Queue overflow

If you're logging hundreds of messages per second:
- Use `debug_debug()` sparingly (only for critical debug paths)
- Add rate limiting: don't log same message in rapid succession
- The queue auto-trims to 50 messages, so oldest messages will be lost

### Console lag

If GUI updates slowly:
- Reduce `POLL_INTERVAL` in console (default: 200ms)
- Use `[PAUSE]` to stop polling while reviewing logs
- Export to file and close console for better performance

## Advanced: Custom Helper Variations

### Add Timestamp to Messages

```python
def debug_info(msg):
    _debug_log("INFO", "[" + time.strftime("%H:%M:%S") + "] " + msg)
```

### Conditional Logging

```python
# Only log if local DEBUG flag is True
DEBUG_VERBOSE = False

def debug_verbose(msg):
    if DEBUG_VERBOSE:
        debug_debug(msg)
```

### Rate Limiting

```python
_last_debug_times = {}

def debug_rate_limited(level, msg, cooldown=1.0):
    """Only log if cooldown seconds have passed since last identical message"""
    now = time.time()
    key = level + msg
    if key in _last_debug_times:
        if now - _last_debug_times[key] < cooldown:
            return
    _last_debug_times[key] = now
    _debug_log(level, msg)
```

## Migration Checklist

For each script you want to add debugging to:

- [ ] Add debug helper block (adjust `_debug_script_name`)
- [ ] Replace `API.SysMsg()` debug calls with `debug_*()`
- [ ] Remove `if DEBUG:` conditionals (helper handles enable/disable)
- [ ] Test with Debug Console running
- [ ] Export logs to verify output format
- [ ] Adjust debug levels as needed (INFO vs DEBUG)

---

**Tip**: Start with INFO and WARN levels for production-ready messages. Use DEBUG for verbose tracing during development, then remove or keep disabled in production.
