# ============================================================
# Debug Console Test Script
# by Coryigon for UO Unchained
# ============================================================
#
# Simple test script that sends various debug messages to the
# Debug Console to verify functionality.
#
# Usage: Run this alongside Util_DebugConsole.py to see messages
# ============================================================
import API
import time

__version__ = "1.0"

# ============ DEBUG HELPER ============
DEBUG_QUEUE_KEY = "DebugConsole_Queue"
DEBUG_ENABLED_KEY = "DebugConsole_Enabled"
_debug_script_name = "DebugTest"

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

# Test message counter
test_counter = 0

API.SysMsg("Debug Console Test started! Watch messages in Util_DebugConsole.py", 68)
debug_info("Debug Console Test script initialized")

# Main test loop
while not API.StopRequested:
    API.ProcessCallbacks()

    test_counter += 1

    # Send different message types every few seconds
    if test_counter % 30 == 0:  # Every 3 seconds
        debug_info("Test message #" + str(test_counter // 30))

    if test_counter % 50 == 0:  # Every 5 seconds
        debug_warn("Warning test message (every 5s)")

    if test_counter % 70 == 0:  # Every 7 seconds
        debug_error("Error test message (every 7s)")

    if test_counter % 10 == 0:  # Every 1 second
        debug_debug("Debug tick: " + str(test_counter))

    # Example: Simulated state machine
    if test_counter == 100:
        debug_info("State transition: idle -> active")
    elif test_counter == 200:
        debug_warn("Low resource warning triggered")
    elif test_counter == 300:
        debug_info("State transition: active -> idle")
        test_counter = 0  # Reset

    API.Pause(0.1)

debug_info("Debug Console Test stopped")
API.SysMsg("Debug Console Test stopped", 43)
