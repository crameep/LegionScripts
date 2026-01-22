# ============================================================
# Debug Console v1.2
# by Coryigon for UO Unchained
# ============================================================
#
# A debugging console for script developers. Monitors debug
# messages from all running scripts via persistent variable queue.
#
# Features:
#   - Collapsible interface (click [-] to minimize, [+] to expand)
#   - Real-time message monitoring (polls queue every 200ms)
#   - Filter by level: INFO, WARN, ERROR, DEBUG
#   - Filter by source script (cycle through scripts)
#   - Auto-scroll toggle
#   - Pause/resume monitoring
#   - Export filtered messages to timestamped file
#   - Keeps last 500 messages in memory
#
# Usage:
#   Scripts write to queue via:
#     DebugConsole_Queue = "timestamp|source|level|message\x1E..."
#   Console reads and displays messages with filtering and export.
#
# ============================================================
import API
import time
import os
import hashlib

__version__ = "1.2"

# ============ CONSTANTS ============
WINDOW_WIDTH = 400
COLLAPSED_HEIGHT = 24
EXPANDED_HEIGHT = 480
POLL_INTERVAL = 0.2
MAX_MESSAGES = 500
VISIBLE_LINES = 15
DEBUG_QUEUE_KEY = "DebugConsole_Queue"
DEBUG_ENABLED_KEY = "DebugConsole_Enabled"
SETTINGS_KEY = "DebugConsole"

# Record separator for queue format
RECORD_SEPARATOR = "\x1E"

# Level colors (for display formatting)
LEVEL_COLORS = {
    "INFO": "#00ff00",
    "WARN": "#ffff00",
    "ERROR": "#ff3333",
    "DEBUG": "#888888",
}

# ============ RUNTIME STATE ============
is_expanded = True
state = "polling"  # States: polling, paused
messages = []  # List of parsed message dicts: {timestamp, source, level, message, raw_time}
last_queue_hash = ""
next_poll = 0
next_display_update = 0
last_position_check = 0
last_known_x = 100
last_known_y = 100

# Filter states
show_info = True
show_warn = True
show_error = True
show_debug = True
auto_scroll = True
current_source_filter = "ALL"  # "ALL" or specific source name
available_sources = set()  # Set of discovered source names

# ============ PERSISTENCE KEYS ============
def load_settings():
    """Load all persistent settings"""
    global show_info, show_warn, show_error, show_debug, auto_scroll

    show_info = API.GetPersistentVar(SETTINGS_KEY + "_ShowInfo", "True", API.PersistentVar.Char) == "True"
    show_warn = API.GetPersistentVar(SETTINGS_KEY + "_ShowWarn", "True", API.PersistentVar.Char) == "True"
    show_error = API.GetPersistentVar(SETTINGS_KEY + "_ShowError", "True", API.PersistentVar.Char) == "True"
    show_debug = API.GetPersistentVar(SETTINGS_KEY + "_ShowDebug", "True", API.PersistentVar.Char) == "True"
    auto_scroll = API.GetPersistentVar(SETTINGS_KEY + "_AutoScroll", "True", API.PersistentVar.Char) == "True"

def save_filter_state(key, value):
    """Save a filter setting"""
    API.SavePersistentVar(key, str(value), API.PersistentVar.Char)

def load_expanded_state():
    """Load expanded state from persistence"""
    global is_expanded
    saved = API.GetPersistentVar(SETTINGS_KEY + "_Expanded", "True", API.PersistentVar.Char)
    is_expanded = (saved == "True")

def save_expanded_state():
    """Save expanded state to persistence"""
    API.SavePersistentVar(SETTINGS_KEY + "_Expanded", str(is_expanded), API.PersistentVar.Char)

def load_window_position():
    """Load window position from persistence"""
    global last_known_x, last_known_y
    saved = API.GetPersistentVar(SETTINGS_KEY + "_XY", "100,100", API.PersistentVar.Char)
    parts = saved.split(',')
    x = int(parts[0])
    y = int(parts[1])
    last_known_x = x
    last_known_y = y
    return x, y

def save_window_position():
    """Save window position using last known coordinates"""
    global last_known_x, last_known_y
    if last_known_x > 0 and last_known_y > 0:
        pos = str(last_known_x) + "," + str(last_known_y)
        API.SavePersistentVar(SETTINGS_KEY + "_XY", pos, API.PersistentVar.Char)

# ============ UTILITY FUNCTIONS ============
def parse_queue():
    """Read queue from persistent var and parse messages"""
    global last_queue_hash, messages, available_sources

    try:
        queue_data = API.GetPersistentVar(DEBUG_QUEUE_KEY, "", API.PersistentVar.Char)

        # Hash-based change detection
        current_hash = hashlib.md5(queue_data.encode()).hexdigest()
        if current_hash == last_queue_hash:
            return  # No changes

        last_queue_hash = current_hash

        if not queue_data:
            return

        # Parse records
        records = queue_data.split(RECORD_SEPARATOR)
        new_messages = []

        for record in records:
            if not record.strip():
                continue

            parts = record.split("|")
            if len(parts) >= 4:
                timestamp_str = parts[0]
                source = parts[1]
                level = parts[2]
                message = "|".join(parts[3:])  # Rejoin in case message contains |

                # Extract raw time for sorting
                try:
                    raw_time = float(timestamp_str)
                except:
                    raw_time = time.time()

                msg_dict = {
                    "timestamp": time.strftime("%H:%M:%S", time.localtime(raw_time)),
                    "source": source,
                    "level": level,
                    "message": message,
                    "raw_time": raw_time,
                }
                new_messages.append(msg_dict)
                available_sources.add(source)

        # Add new messages and trim to MAX_MESSAGES
        messages.extend(new_messages)
        if len(messages) > MAX_MESSAGES:
            messages = messages[-MAX_MESSAGES:]

    except Exception as e:
        API.SysMsg("Queue parse error: " + str(e)[:40], 32)

def get_visible_messages():
    """Get messages that pass current filters"""
    visible = []

    for msg in messages:
        # Level filter
        level = msg["level"]
        if level == "INFO" and not show_info:
            continue
        if level == "WARN" and not show_warn:
            continue
        if level == "ERROR" and not show_error:
            continue
        if level == "DEBUG" and not show_debug:
            continue

        # Source filter
        if current_source_filter != "ALL" and msg["source"] != current_source_filter:
            continue

        visible.append(msg)

    return visible

def format_message(msg):
    """Format a message for display"""
    ts = msg["timestamp"]
    source = msg["source"]
    level = msg["level"]
    text = msg["message"]

    # Truncate long messages (longer now that we have wrapping)
    if len(text) > 80:
        text = text[:77] + "..."

    # Format with visual level indicators
    # Use distinct symbols/brackets per level for visual differentiation
    if level == "INFO":
        prefix = "[i]"  # info
    elif level == "WARN":
        prefix = "[!]"  # warning/alert
    elif level == "ERROR":
        prefix = "[X]"  # error/failure
    elif level == "DEBUG":
        prefix = "[.]"  # debug/trace
    else:
        prefix = "[?]"

    # Format: HH:MM:SS [Symbol] Source: message
    return ts + " " + prefix + " " + source[:10].ljust(10) + ": " + text

def update_message_display():
    """Update the message display labels"""
    visible = get_visible_messages()
    total_messages = len(messages)
    visible_count = len(visible)

    # Update status line
    statusLabel.SetText("Showing " + str(visible_count) + " of " + str(total_messages) + " messages")

    # Get messages to display (last VISIBLE_LINES if auto-scroll, else first VISIBLE_LINES)
    if auto_scroll:
        display_msgs = visible[-VISIBLE_LINES:] if len(visible) > VISIBLE_LINES else visible
    else:
        display_msgs = visible[:VISIBLE_LINES] if len(visible) > VISIBLE_LINES else visible

    # Build display text
    display_text = ""
    for msg in display_msgs:
        display_text += format_message(msg) + "\n"

    if not display_text:
        display_text = "No messages match current filters\n\nAdjust filters or wait for messages\n\nLegend: [i]=INFO [!]=WARN [X]=ERROR [.]=DEBUG"

    messageTextBox.SetText(display_text.strip())

def export_to_file():
    """Export visible messages to timestamped file"""
    try:
        # Get script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        logs_dir = os.path.join(script_dir, "Logs")

        # Create Logs directory if needed
        if not os.path.exists(logs_dir):
            try:
                os.makedirs(logs_dir)
            except Exception as e:
                API.SysMsg("Failed to create Logs directory: " + str(e)[:40], 32)
                return

        # Generate filename with timestamp
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = "debug_export_" + timestamp + ".txt"
        filepath = os.path.join(logs_dir, filename)

        # Get visible messages
        visible = get_visible_messages()

        if not visible:
            API.SysMsg("No messages to export!", 43)
            return

        # Build export content
        content = "Debug Console Export\n"
        content += "Date: " + time.strftime("%Y-%m-%d %H:%M:%S") + "\n"
        content += "Filter: INFO=" + ("ON" if show_info else "OFF")
        content += " WARN=" + ("ON" if show_warn else "OFF")
        content += " ERROR=" + ("ON" if show_error else "OFF")
        content += " DEBUG=" + ("ON" if show_debug else "OFF") + "\n"
        content += "Source: " + current_source_filter + "\n"
        content += "=" * 60 + "\n\n"

        for msg in visible:
            ts = msg["timestamp"]
            source = msg["source"]
            level = msg["level"]
            text = msg["message"]
            content += ts + " [" + source + "] " + level + ": " + text + "\n"

        content += "\n" + "=" * 60 + "\n"
        content += "Total: " + str(len(visible)) + " messages exported\n"

        # Write file
        with open(filepath, 'w') as f:
            f.write(content)

        API.SysMsg("Exported " + str(len(visible)) + " messages to " + filename, 68)

    except Exception as e:
        API.SysMsg("Export failed: " + str(e)[:50], 32)

# ============ GUI CALLBACKS ============
def toggle_info():
    """Toggle INFO filter"""
    global show_info
    show_info = not show_info
    save_filter_state(SETTINGS_KEY + "_ShowInfo", show_info)
    infoBtn.SetBackgroundHue(68 if show_info else 32)
    update_message_display()

def toggle_warn():
    """Toggle WARN filter"""
    global show_warn
    show_warn = not show_warn
    save_filter_state(SETTINGS_KEY + "_ShowWarn", show_warn)
    warnBtn.SetBackgroundHue(43 if show_warn else 32)
    update_message_display()

def toggle_error():
    """Toggle ERROR filter"""
    global show_error
    show_error = not show_error
    save_filter_state(SETTINGS_KEY + "_ShowError", show_error)
    errorBtn.SetBackgroundHue(32 if show_error else 90)
    update_message_display()

def toggle_debug():
    """Toggle DEBUG filter"""
    global show_debug
    show_debug = not show_debug
    save_filter_state(SETTINGS_KEY + "_ShowDebug", show_debug)
    debugBtn.SetBackgroundHue(90 if show_debug else 32)
    update_message_display()

def cycle_source_filter():
    """Cycle through source filters"""
    global current_source_filter

    sources_list = ["ALL"] + sorted(list(available_sources))

    if current_source_filter in sources_list:
        idx = sources_list.index(current_source_filter)
        idx = (idx + 1) % len(sources_list)
        current_source_filter = sources_list[idx]
    else:
        current_source_filter = "ALL"

    # Update button text
    filter_text = "[" + current_source_filter[:8] + "]"
    sourceBtn.SetText(filter_text)
    update_message_display()

def toggle_pause():
    """Toggle pause/resume monitoring"""
    global state

    if state == "polling":
        state = "paused"
        pauseBtn.SetText("[RESUME]")
        pauseBtn.SetBackgroundHue(68)
    else:
        state = "polling"
        pauseBtn.SetText("[PAUSE]")
        pauseBtn.SetBackgroundHue(43)

def toggle_scroll():
    """Toggle auto-scroll"""
    global auto_scroll
    auto_scroll = not auto_scroll
    save_filter_state(SETTINGS_KEY + "_AutoScroll", auto_scroll)

    scroll_text = "[SCROLL:" + ("ON" if auto_scroll else "OFF") + "]"
    scrollBtn.SetText(scroll_text)
    scrollBtn.SetBackgroundHue(68 if auto_scroll else 90)
    update_message_display()

def clear_display():
    """Clear message list"""
    global messages, available_sources, current_source_filter
    messages = []
    available_sources = set()
    current_source_filter = "ALL"
    sourceBtn.SetText("[ALL]")
    update_message_display()
    API.SysMsg("Display cleared", 68)

def export_messages():
    """Export button handler"""
    export_to_file()

# ============ EXPAND/COLLAPSE ============
def toggle_expand():
    """Toggle between collapsed and expanded states"""
    global is_expanded
    is_expanded = not is_expanded
    save_expanded_state()

    if is_expanded:
        expand_window()
    else:
        collapse_window()

def expand_window():
    """Show all controls and resize window"""
    expandBtn.SetText("[-]")

    # Show filter controls
    infoBtn.IsVisible = True
    warnBtn.IsVisible = True
    errorBtn.IsVisible = True
    debugBtn.IsVisible = True
    sourceBtn.IsVisible = True
    pauseBtn.IsVisible = True
    scrollBtn.IsVisible = True
    clearBtn.IsVisible = True

    # Show message display
    messageBg.IsVisible = True
    messageTextBox.IsVisible = True
    statusLabel.IsVisible = True

    # Show export and close buttons
    exportBtn.IsVisible = True
    closeBtn.IsVisible = True

    # Resize gump and background
    x = gump.GetX()
    y = gump.GetY()
    gump.SetRect(x, y, WINDOW_WIDTH, EXPANDED_HEIGHT)
    bg.SetRect(0, 0, WINDOW_WIDTH, EXPANDED_HEIGHT)

def collapse_window():
    """Hide all controls and shrink window"""
    expandBtn.SetText("[+]")

    # Hide filter controls
    infoBtn.IsVisible = False
    warnBtn.IsVisible = False
    errorBtn.IsVisible = False
    debugBtn.IsVisible = False
    sourceBtn.IsVisible = False
    pauseBtn.IsVisible = False
    scrollBtn.IsVisible = False
    clearBtn.IsVisible = False

    # Hide message display
    messageBg.IsVisible = False
    messageTextBox.IsVisible = False
    statusLabel.IsVisible = False

    # Hide export and close buttons
    exportBtn.IsVisible = False
    closeBtn.IsVisible = False

    # Resize gump and background
    x = gump.GetX()
    y = gump.GetY()
    gump.SetRect(x, y, WINDOW_WIDTH, COLLAPSED_HEIGHT)
    bg.SetRect(0, 0, WINDOW_WIDTH, COLLAPSED_HEIGHT)

# ============ CLEANUP ============
def stop_script():
    """Stop script and cleanup"""
    save_window_position()
    gump.Dispose()
    API.Stop()

def onClosed():
    """Handle window close event"""
    save_window_position()
    API.Stop()

# ============ INITIALIZATION ============
# Load settings and position
load_settings()
load_expanded_state()
x, y = load_window_position()

# ============ BUILD GUI ============
gump = API.Gumps.CreateGump()
API.Gumps.AddControlOnDisposed(gump, onClosed)

initial_height = EXPANDED_HEIGHT if is_expanded else COLLAPSED_HEIGHT
gump.SetRect(x, y, WINDOW_WIDTH, initial_height)

# Background
bg = API.Gumps.CreateGumpColorBox(0.95, "#000000")
bg.SetRect(0, 0, WINDOW_WIDTH, initial_height)
gump.Add(bg)

# Title bar
title = API.Gumps.CreateGumpTTFLabel("Debug Console", 16, "#00d4ff")
title.SetPos(5, 2)
gump.Add(title)

# Expand/collapse button
expandBtn = API.Gumps.CreateSimpleButton("[-]" if is_expanded else "[+]", 20, 18)
expandBtn.SetPos(375, 3)
expandBtn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(expandBtn, toggle_expand)
gump.Add(expandBtn)

# === FILTER CONTROLS (Row 1) ===
y = 26

# Level filter buttons
infoBtn = API.Gumps.CreateSimpleButton("[INFO]", 50, 20)
infoBtn.SetPos(5, y)
infoBtn.SetBackgroundHue(68 if show_info else 32)
infoBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(infoBtn, toggle_info)
gump.Add(infoBtn)

warnBtn = API.Gumps.CreateSimpleButton("[WARN]", 50, 20)
warnBtn.SetPos(58, y)
warnBtn.SetBackgroundHue(43 if show_warn else 32)
warnBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(warnBtn, toggle_warn)
gump.Add(warnBtn)

errorBtn = API.Gumps.CreateSimpleButton("[ERR]", 45, 20)
errorBtn.SetPos(111, y)
errorBtn.SetBackgroundHue(32 if show_error else 90)
errorBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(errorBtn, toggle_error)
gump.Add(errorBtn)

debugBtn = API.Gumps.CreateSimpleButton("[DBG]", 45, 20)
debugBtn.SetPos(159, y)
debugBtn.SetBackgroundHue(90 if show_debug else 32)
debugBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(debugBtn, toggle_debug)
gump.Add(debugBtn)

# Source filter button
sourceBtn = API.Gumps.CreateSimpleButton("[ALL]", 80, 20)
sourceBtn.SetPos(207, y)
sourceBtn.SetBackgroundHue(53)
sourceBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(sourceBtn, cycle_source_filter)
gump.Add(sourceBtn)

# Clear button
clearBtn = API.Gumps.CreateSimpleButton("[CLR]", 45, 20)
clearBtn.SetPos(290, y)
clearBtn.SetBackgroundHue(32)
clearBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(clearBtn, clear_display)
gump.Add(clearBtn)

# Pause/resume and scroll controls (Row 2)
y += 23

pauseBtn = API.Gumps.CreateSimpleButton("[PAUSE]", 75, 20)
pauseBtn.SetPos(5, y)
pauseBtn.SetBackgroundHue(43)
pauseBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(pauseBtn, toggle_pause)
gump.Add(pauseBtn)

scrollBtn = API.Gumps.CreateSimpleButton("[SCROLL:ON]" if auto_scroll else "[SCROLL:OFF]", 95, 20)
scrollBtn.SetPos(83, y)
scrollBtn.SetBackgroundHue(68 if auto_scroll else 90)
scrollBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(scrollBtn, toggle_scroll)
gump.Add(scrollBtn)

# === MESSAGE DISPLAY AREA ===
y += 25

# Black background for messages
messageBg = API.Gumps.CreateGumpColorBox(1.0, "#000000")
messageBg.SetRect(5, y, 390, 340)
messageBg.IsVisible = is_expanded
gump.Add(messageBg)

# Message textbox (better for multi-line display with wrapping)
messageTextBox = API.Gumps.CreateGumpTextBox(380, 335, "Waiting for messages...\n\nMonitoring queue every 200ms", "#aaaaaa")
messageTextBox.SetPos(8, y + 3)
messageTextBox.IsVisible = is_expanded
gump.Add(messageTextBox)

# Status line
y += 343
statusLabel = API.Gumps.CreateGumpTTFLabel("Showing 0 of 0 messages", 9, "#888888")
statusLabel.SetPos(5, y)
statusLabel.IsVisible = is_expanded
gump.Add(statusLabel)

# === EXPORT AND CLOSE BUTTONS ===
y += 18

exportBtn = API.Gumps.CreateSimpleButton("[EXPORT TO FILE]", 140, 22)
exportBtn.SetPos(5, y)
exportBtn.SetBackgroundHue(68)
exportBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(exportBtn, export_messages)
gump.Add(exportBtn)

closeBtn = API.Gumps.CreateSimpleButton("[CLOSE CONSOLE]", 140, 22)
closeBtn.SetPos(150, y)
closeBtn.SetBackgroundHue(32)
closeBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(closeBtn, stop_script)
gump.Add(closeBtn)

API.Gumps.AddGump(gump)

# Apply initial collapsed state if needed
if not is_expanded:
    collapse_window()

# ============ MAIN LOOP ============
API.SysMsg("=== Debug Console v1.2 Started ===", 68)
API.SysMsg("Monitoring queue: " + DEBUG_QUEUE_KEY, 53)

next_poll = time.time()
next_display_update = time.time()
last_position_check = time.time()

while not API.StopRequested:
    try:
        API.ProcessCallbacks()

        # Poll queue if in polling state
        if state == "polling" and time.time() >= next_poll:
            parse_queue()
            next_poll = time.time() + POLL_INTERVAL

        # Update display periodically
        if time.time() >= next_display_update:
            update_message_display()
            next_display_update = time.time() + 0.3

        # Position tracking
        if time.time() - last_position_check > 2.0:
            try:
                last_known_x = gump.GetX()
                last_known_y = gump.GetY()
            except:
                pass
            last_position_check = time.time()

        API.Pause(0.1)

    except Exception as e:
        if "operation canceled" not in str(e).lower() and not API.StopRequested:
            API.SysMsg("Console error: " + str(e)[:50], 32)
        API.Pause(1)
