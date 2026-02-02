# ============================================================
# Gump Inspector v2.0
# by Coryigon for UO Unchained
# ============================================================
#
# A debugging tool for script developers. Inspect game UI
# elements (gumps) to find button IDs, track events, and
# test interactions.
#
# Features:
#   - Auto-monitors gump opens and closes
#   - Discovers gump IDs and button numbers
#   - Event hooking for button press monitoring
#   - Activity logging with history
#   - Quick scan to test button ranges
#
# Useful for: Finding button IDs for runebooks, vendor menus,
# skill gumps, and any other in-game UI you want to automate.
#
# ============================================================
import API
import time

__version__ = "2.0"

# ============ SETTINGS ============
SETTINGS_KEY = "GumpInspector_XY"
MONITOR_INTERVAL = 0.2   # How often to check for gump changes
MAX_LOG_ENTRIES = 100    # Maximum log entries to keep

# ============ STATE ============
selected_gump_id = 0
custom_button_num = 0
monitoring_enabled = True
last_gump_snapshot = {}  # {gump_id: timestamp}
activity_log = []        # [(timestamp, type, message)]
events_registered = False
discovered_events = []   # List of discovered event names

# ============ LOGGING ============
def log_activity(activity_type, message):
    """Log an activity with timestamp"""
    global activity_log
    timestamp = time.strftime("%H:%M:%S")
    entry = (timestamp, activity_type, message)
    activity_log.append(entry)
    
    # Trim log if too long
    if len(activity_log) > MAX_LOG_ENTRIES:
        activity_log = activity_log[-MAX_LOG_ENTRIES:]
    
    # Color code by type
    hue_map = {
        "OPEN": 68,     # Green
        "CLOSE": 32,    # Red  
        "BTN": 88,      # Blue
        "EVENT": 53,    # Purple-ish
        "INFO": 43,     # Yellow
        "WARN": 38,     # Orange
    }
    hue = hue_map.get(activity_type, 53)
    
    API.SysMsg("[" + timestamp + "] " + activity_type + ": " + message, hue)
    update_log_display()

def update_log_display():
    """Update the activity log display"""
    if not activity_log:
        logLabel.SetText("Waiting for activity...")
        return
    
    # Show last 10 entries
    text = ""
    for ts, atype, msg in activity_log[-10:]:
        # Truncate message if too long
        short_msg = msg[:40] + "..." if len(msg) > 43 else msg
        text += ts + " " + atype[:4] + ": " + short_msg + "\n"
    
    logLabel.SetText(text.strip())

# ============ EVENT DISCOVERY & REGISTRATION ============
def discover_events():
    """Discover available events in API.Events"""
    global discovered_events
    discovered_events = []
    
    try:
        events = API.Events
        if events:
            # Get all attributes that might be event handlers
            for attr in dir(events):
                if not attr.startswith('_'):
                    discovered_events.append(attr)
            
            if discovered_events:
                log_activity("INFO", "Found " + str(len(discovered_events)) + " event attrs")
                # Log first few
                for evt in discovered_events[:5]:
                    API.SysMsg("  Event: " + evt, 53)
                if len(discovered_events) > 5:
                    API.SysMsg("  ...and " + str(len(discovered_events) - 5) + " more", 53)
            return True
    except Exception as e:
        log_activity("WARN", "Events not available: " + str(e)[:30])
    
    return False

def try_register_events():
    """Try to register event handlers for gump events"""
    global events_registered
    
    try:
        events = API.Events
        if not events:
            return False
        
        # Common event names to try
        event_handlers = {
            'OnGumpOpen': on_gump_open_event,
            'OnGumpClose': on_gump_close_event,
            'OnGumpResponse': on_gump_response_event,
            'OnServerGump': on_server_gump_event,
            'GumpOpened': on_gump_open_event,
            'GumpClosed': on_gump_close_event,
            'GumpResponse': on_gump_response_event,
        }
        
        registered_count = 0
        for event_name, handler in event_handlers.items():
            try:
                if hasattr(events, event_name):
                    event_attr = getattr(events, event_name)
                    # Try different registration patterns
                    if callable(event_attr):
                        event_attr(handler)
                        log_activity("EVENT", "Registered: " + event_name)
                        registered_count += 1
                    elif hasattr(event_attr, 'Add'):
                        event_attr.Add(handler)
                        log_activity("EVENT", "Registered: " + event_name)
                        registered_count += 1
                    elif hasattr(event_attr, 'append'):
                        event_attr.append(handler)
                        log_activity("EVENT", "Registered: " + event_name)
                        registered_count += 1
            except Exception as e:
                pass  # Silent fail, try next
        
        if registered_count > 0:
            events_registered = True
            return True
            
    except Exception as e:
        log_activity("INFO", "Event registration: " + str(e)[:30])
    
    return False

# Event handlers
def on_gump_open_event(*args):
    """Event handler for gump open"""
    try:
        gump_id = args[0] if args else "unknown"
        log_activity("EVENT", "GUMP OPEN: " + str(gump_id))
    except:
        log_activity("EVENT", "GUMP OPEN (args: " + str(len(args)) + ")")

def on_gump_close_event(*args):
    """Event handler for gump close"""
    try:
        gump_id = args[0] if args else "unknown"
        log_activity("EVENT", "GUMP CLOSE: " + str(gump_id))
    except:
        log_activity("EVENT", "GUMP CLOSE (args: " + str(len(args)) + ")")

def on_gump_response_event(*args):
    """Event handler for gump button response - THIS IS THE KEY ONE"""
    try:
        # Try to extract gump_id and button_id from args
        if len(args) >= 2:
            gump_id = args[0]
            button_id = args[1]
            log_activity("BTN", "RESPONSE: gump=" + str(gump_id) + " btn=" + str(button_id))
        elif len(args) == 1:
            log_activity("BTN", "RESPONSE: " + str(args[0]))
        else:
            log_activity("BTN", "RESPONSE event fired")
    except Exception as e:
        log_activity("BTN", "RESPONSE: " + str(e)[:30])

def on_server_gump_event(*args):
    """Generic server gump event"""
    log_activity("EVENT", "SERVER GUMP: args=" + str(len(args)))

# ============ GUMP MONITORING (POLLING) ============
def get_current_gumps():
    """Get dictionary of current gump IDs -> info"""
    gumps_dict = {}
    try:
        gumps = API.GetAllGumps()
        if gumps:
            for g in gumps:
                try:
                    gid = 0
                    if hasattr(g, 'ServerSerial'):
                        gid = g.ServerSerial
                    elif hasattr(g, 'LocalSerial'):
                        gid = g.LocalSerial
                    if gid and gid > 0:
                        gumps_dict[gid] = {
                            'gump': g,
                            'time': time.time()
                        }
                except:
                    pass
    except:
        pass
    return gumps_dict

def check_for_gump_changes():
    """Check for new/closed gumps - main monitoring function"""
    global last_gump_snapshot, selected_gump_id
    
    if not monitoring_enabled:
        return
    
    current_gumps = get_current_gumps()
    current_ids = set(current_gumps.keys())
    last_ids = set(last_gump_snapshot.keys())
    
    # Find new gumps (OPENED)
    new_gumps = current_ids - last_ids
    for gid in new_gumps:
        log_activity("OPEN", "Gump ID: " + str(gid) + " (0x" + format(gid, 'X') + ")")
        # Auto-select new gump
        selected_gump_id = gid
        selectedLabel.SetText("Sel: " + str(gid))
    
    # Find closed gumps (CLOSED - possibly due to button press!)
    closed_gumps = last_ids - current_ids
    for gid in closed_gumps:
        # Calculate how long the gump was open
        if gid in last_gump_snapshot:
            duration = time.time() - last_gump_snapshot[gid].get('time', time.time())
            log_activity("CLOSE", "Gump ID: " + str(gid) + " (was open " + str(round(duration, 1)) + "s)")
        else:
            log_activity("CLOSE", "Gump ID: " + str(gid))
        
        # Clear selection if our selected gump closed
        if selected_gump_id == gid:
            if current_ids:
                selected_gump_id = list(current_ids)[0]
            else:
                selected_gump_id = 0
            selectedLabel.SetText("Sel: " + (str(selected_gump_id) if selected_gump_id else "(none)"))
    
    last_gump_snapshot = current_gumps
    update_gump_list_display()

def update_gump_list_display():
    """Update the gump list label"""
    current_gumps = get_current_gumps()
    
    gumpCountLabel.SetText("Open: " + str(len(current_gumps)))
    
    if not current_gumps:
        gumpListLabel.SetText("No gumps detected\n\nOpen a runebook or\nother gump to inspect")
        return
    
    text = ""
    for i, gid in enumerate(list(current_gumps.keys())[:6]):
        marker = ">" if gid == selected_gump_id else " "
        # Show both decimal and hex
        text += marker + str(gid) + "\n"
        text += "  (0x" + format(gid, 'X') + ")\n"
    
    if len(current_gumps) > 6:
        text += "...+" + str(len(current_gumps) - 6) + " more"
    
    gumpListLabel.SetText(text.strip())

# ============ GUMP FUNCTIONS ============
def refresh_gumps():
    """Manual refresh"""
    check_for_gump_changes()
    current = get_current_gumps()
    log_activity("INFO", "Manual refresh - " + str(len(current)) + " gump(s)")

def check_gump():
    """Quick HasGump check"""
    gump_id = API.HasGump()
    if gump_id:
        log_activity("INFO", "HasGump: " + str(gump_id) + " (0x" + format(gump_id, 'X') + ")")
        global selected_gump_id
        selected_gump_id = gump_id
        selectedLabel.SetText("Sel: " + str(gump_id))
    else:
        log_activity("INFO", "No server gump open")

def show_gump_contents():
    """Show text contents of current gump"""
    try:
        if selected_gump_id > 0:
            contents = API.GetGumpContents(selected_gump_id)
        else:
            contents = API.GetGumpContents()
        
        if contents:
            log_activity("INFO", "=== GUMP " + str(selected_gump_id) + " CONTENTS ===")
            lines = contents.split('\n')
            for i, line in enumerate(lines[:20]):
                if line.strip():
                    API.SysMsg("[" + str(i) + "] " + line[:60], 53)
            if len(lines) > 20:
                API.SysMsg("... (" + str(len(lines) - 20) + " more lines)", 43)
        else:
            log_activity("INFO", "No gump contents found")
    except Exception as e:
        log_activity("WARN", "Contents error: " + str(e)[:30])

def close_target_gump():
    """Close the selected gump"""
    if selected_gump_id > 0:
        result = API.CloseGump(selected_gump_id)
        log_activity("INFO", "Closed " + str(selected_gump_id) + ": " + str(result))
    else:
        result = API.CloseGump()
        log_activity("INFO", "Closed last gump: " + str(result))

def target_item_for_gump():
    """Target an item to open its gump"""
    log_activity("INFO", "Target an item to use...")
    target = API.RequestTarget(timeout=30)
    if target:
        log_activity("INFO", "Using item: " + str(target))
        API.UseObject(target)
    else:
        log_activity("INFO", "Targeting cancelled")

def select_next_gump():
    """Cycle through available gumps"""
    global selected_gump_id
    
    current_gumps = get_current_gumps()
    ids = list(current_gumps.keys())
    
    if not ids:
        log_activity("INFO", "No gumps to cycle")
        return
    
    if selected_gump_id in ids:
        idx = ids.index(selected_gump_id)
        idx = (idx + 1) % len(ids)
        selected_gump_id = ids[idx]
    else:
        selected_gump_id = ids[0]
    
    selectedLabel.SetText("Sel: " + str(selected_gump_id))
    log_activity("INFO", "Selected: " + str(selected_gump_id) + " (0x" + format(selected_gump_id, 'X') + ")")
    update_gump_list_display()

# ============ BUTTON TESTING ============
def try_button(button_num):
    """Try clicking a button number on the selected gump"""
    log_activity("BTN", "Testing btn " + str(button_num) + " on gump " + str(selected_gump_id))
    
    if selected_gump_id > 0:
        result = API.ReplyGump(button_num, selected_gump_id)
    else:
        result = API.ReplyGump(button_num)
    
    status = "OK" if result else "FAIL"
    log_activity("BTN", "Btn " + str(button_num) + " = " + status)
    lastClickLabel.SetText("Last: btn " + str(button_num) + "=" + status)

# Pre-made button handlers
def btn_0(): try_button(0)
def btn_1(): try_button(1)
def btn_2(): try_button(2)
def btn_3(): try_button(3)
def btn_4(): try_button(4)
def btn_5(): try_button(5)
def btn_6(): try_button(6)
def btn_7(): try_button(7)
def btn_8(): try_button(8)
def btn_9(): try_button(9)
def btn_10(): try_button(10)
def btn_11(): try_button(11)
def btn_12(): try_button(12)
def btn_13(): try_button(13)
def btn_14(): try_button(14)
def btn_15(): try_button(15)
def btn_16(): try_button(16)
def btn_17(): try_button(17)
def btn_18(): try_button(18)
def btn_19(): try_button(19)
def btn_20(): try_button(20)
def btn_21(): try_button(21)
def btn_22(): try_button(22)
def btn_23(): try_button(23)
def btn_24(): try_button(24)
def btn_25(): try_button(25)
def btn_50(): try_button(50)
def btn_51(): try_button(51)
def btn_100(): try_button(100)
def btn_101(): try_button(101)
def btn_102(): try_button(102)
def btn_200(): try_button(200)

def try_custom_button():
    """Try the custom button number"""
    global custom_button_num
    try:
        num = int(customInput.GetText())
        custom_button_num = num
        try_button(num)
    except:
        log_activity("WARN", "Invalid number!")

def increment_and_try():
    """Increment and try next button"""
    global custom_button_num
    custom_button_num += 1
    customInput.SetText(str(custom_button_num))
    try_button(custom_button_num)

def decrement_and_try():
    """Decrement and try previous button"""
    global custom_button_num
    custom_button_num -= 1
    if custom_button_num < 0:
        custom_button_num = 0
    customInput.SetText(str(custom_button_num))
    try_button(custom_button_num)

def scan_buttons():
    """Scan buttons 0-20 quickly"""
    log_activity("INFO", "Scanning buttons 0-20...")
    for i in range(21):
        # Check if gump still exists
        if not API.HasGump(selected_gump_id) and selected_gump_id > 0:
            log_activity("INFO", "Gump closed at button " + str(i-1) + "!")
            break
        try_button(i)
        API.Pause(0.3)

# ============ MONITORING TOGGLE ============
def toggle_monitoring():
    """Toggle gump monitoring on/off"""
    global monitoring_enabled
    monitoring_enabled = not monitoring_enabled
    status = "ON" if monitoring_enabled else "OFF"
    monitorBtn.SetText("[MON:" + status + "]")
    monitorBtn.SetBackgroundHue(68 if monitoring_enabled else 32)
    log_activity("INFO", "Monitoring " + status)

# ============ UTILITY ============
def clear_log():
    """Clear activity log"""
    global activity_log
    activity_log = []
    update_log_display()
    API.SysMsg("Log cleared", 68)

def show_events():
    """Show discovered events"""
    discover_events()
    if discovered_events:
        API.SysMsg("=== API.Events attributes ===", 68)
        for evt in discovered_events:
            API.SysMsg("  " + evt, 53)
    else:
        API.SysMsg("No events discovered or API.Events not available", 32)

def show_help():
    """Show help"""
    API.SysMsg("=== GUMP INSPECTOR v2 HELP ===", 68)
    API.SysMsg("1. Open a gump (runebook, etc)", 53)
    API.SysMsg("2. Watch the LOG - it auto-detects opens/closes", 53)
    API.SysMsg("3. Click buttons to test responses", 53)
    API.SysMsg("4. Use +/- to scan through button numbers", 53)
    API.SysMsg("5. [SCAN] tests buttons 0-20 rapidly", 53)
    API.SysMsg("6. Watch for gump CLOSE = button worked!", 43)

# ============ CLEANUP ============
def stop_script():
    API.SavePersistentVar(SETTINGS_KEY, str(gump.GetX()) + "," + str(gump.GetY()), API.PersistentVar.Char)
    gump.Dispose()
    API.Stop()

def onClosed():
    API.SavePersistentVar(SETTINGS_KEY, str(gump.GetX()) + "," + str(gump.GetY()), API.PersistentVar.Char)
    API.Stop()

# ============ BUILD GUI ============
gump = API.Gumps.CreateGump()
API.Gumps.AddControlOnDisposed(gump, onClosed)

savedPos = API.GetPersistentVar(SETTINGS_KEY, "100,100", API.PersistentVar.Char)
posXY = savedPos.split(',')
gump.SetRect(int(posXY[0]), int(posXY[1]), 380, 520)

# Background
bg = API.Gumps.CreateGumpColorBox(0.92, "#1a1a2e")
bg.SetRect(0, 0, 380, 520)
gump.Add(bg)

# Title
title = API.Gumps.CreateGumpTTFLabel("Gump Inspector v2.0", 14, "#00d4ff", aligned="center", maxWidth=380)
title.SetPos(0, 5)
gump.Add(title)

subtitle = API.Gumps.CreateGumpTTFLabel("Monitors gump opens/closes & button presses", 8, "#888888", aligned="center", maxWidth=380)
subtitle.SetPos(0, 22)
gump.Add(subtitle)

# === TOP ROW - Detection Buttons ===
y = 38
targetBtn = API.Gumps.CreateSimpleButton("[TARGET]", 58, 20)
targetBtn.SetPos(5, y)
targetBtn.SetBackgroundHue(68)
API.Gumps.AddControlOnClick(targetBtn, target_item_for_gump)
gump.Add(targetBtn)

refreshBtn = API.Gumps.CreateSimpleButton("[REFRESH]", 58, 20)
refreshBtn.SetPos(66, y)
refreshBtn.SetBackgroundHue(53)
API.Gumps.AddControlOnClick(refreshBtn, refresh_gumps)
gump.Add(refreshBtn)

monitorBtn = API.Gumps.CreateSimpleButton("[MON:ON]", 58, 20)
monitorBtn.SetPos(127, y)
monitorBtn.SetBackgroundHue(68)
API.Gumps.AddControlOnClick(monitorBtn, toggle_monitoring)
gump.Add(monitorBtn)

checkBtn = API.Gumps.CreateSimpleButton("[CHECK]", 50, 20)
checkBtn.SetPos(188, y)
checkBtn.SetBackgroundHue(43)
API.Gumps.AddControlOnClick(checkBtn, check_gump)
gump.Add(checkBtn)

contentsBtn = API.Gumps.CreateSimpleButton("[TEXT]", 45, 20)
contentsBtn.SetPos(241, y)
contentsBtn.SetBackgroundHue(63)
API.Gumps.AddControlOnClick(contentsBtn, show_gump_contents)
gump.Add(contentsBtn)

closeGumpBtn = API.Gumps.CreateSimpleButton("[CLOSE]", 45, 20)
closeGumpBtn.SetPos(289, y)
closeGumpBtn.SetBackgroundHue(32)
API.Gumps.AddControlOnClick(closeGumpBtn, close_target_gump)
gump.Add(closeGumpBtn)

eventsBtn = API.Gumps.CreateSimpleButton("[EVT]", 38, 20)
eventsBtn.SetPos(337, y)
eventsBtn.SetBackgroundHue(88)
API.Gumps.AddControlOnClick(eventsBtn, show_events)
gump.Add(eventsBtn)

# === LEFT COLUMN - Gump List ===
y = 65
colLeftX = 5
colRightX = 190

gumpCountLabel = API.Gumps.CreateGumpTTFLabel("Open: 0", 10, "#00ff00")
gumpCountLabel.SetPos(colLeftX, y)
gump.Add(gumpCountLabel)

y += 14
gumpListBg = API.Gumps.CreateGumpColorBox(0.5, "#000000")
gumpListBg.SetRect(colLeftX, y, 178, 95)
gump.Add(gumpListBg)

gumpListLabel = API.Gumps.CreateGumpTTFLabel("Monitoring...\n\nOpen a gump to\ninspect it", 9, "#aaaaaa")
gumpListLabel.SetPos(colLeftX + 3, y + 2)
gump.Add(gumpListLabel)

y += 97
selectNextBtn = API.Gumps.CreateSimpleButton("[SELECT NEXT GUMP]", 178, 20)
selectNextBtn.SetPos(colLeftX, y)
selectNextBtn.SetBackgroundHue(88)
API.Gumps.AddControlOnClick(selectNextBtn, select_next_gump)
gump.Add(selectNextBtn)

y += 22
selectedLabel = API.Gumps.CreateGumpTTFLabel("Sel: (none)", 9, "#00ff00")
selectedLabel.SetPos(colLeftX, y)
gump.Add(selectedLabel)

# === RIGHT COLUMN - Button Testing ===
y = 65
sectionLabel2 = API.Gumps.CreateGumpTTFLabel("=== BUTTON TESTING ===", 9, "#ff8800")
sectionLabel2.SetPos(colRightX, y)
gump.Add(sectionLabel2)

# Button grid - 6 columns x 6 rows
y += 14
btnW = 28
btnH = 20
btnSpaceX = 30
btnSpaceY = 22

button_funcs = [
    (0, btn_0), (1, btn_1), (2, btn_2), (3, btn_3), (4, btn_4), (5, btn_5),
    (6, btn_6), (7, btn_7), (8, btn_8), (9, btn_9), (10, btn_10), (11, btn_11),
    (12, btn_12), (13, btn_13), (14, btn_14), (15, btn_15), (16, btn_16), (17, btn_17),
    (18, btn_18), (19, btn_19), (20, btn_20), (21, btn_21), (22, btn_22), (23, btn_23),
    (24, btn_24), (25, btn_25), (50, btn_50), (51, btn_51), (100, btn_100), (101, btn_101),
    (102, btn_102), (200, btn_200),
]

for i, (num, func) in enumerate(button_funcs):
    row = i // 6
    col = i % 6
    btn = API.Gumps.CreateSimpleButton(str(num), btnW, btnH)
    btn.SetPos(colRightX + (col * btnSpaceX), y + (row * btnSpaceY))
    btn.SetBackgroundHue(43)
    API.Gumps.AddControlOnClick(btn, func)
    gump.Add(btn)

# Custom button input
y += (6 * btnSpaceY) + 2
customLabel = API.Gumps.CreateGumpTTFLabel("Custom:", 9, "#aaaaaa")
customLabel.SetPos(colRightX, y + 3)
gump.Add(customLabel)

customInput = API.Gumps.CreateGumpTextBox("0", 45, 20)
customInput.SetPos(colRightX + 48, y)
gump.Add(customInput)

tryCustomBtn = API.Gumps.CreateSimpleButton("TRY", 30, 20)
tryCustomBtn.SetPos(colRightX + 96, y)
tryCustomBtn.SetBackgroundHue(68)
API.Gumps.AddControlOnClick(tryCustomBtn, try_custom_button)
gump.Add(tryCustomBtn)

decBtn = API.Gumps.CreateSimpleButton("-", 22, 20)
decBtn.SetPos(colRightX + 128, y)
decBtn.SetBackgroundHue(32)
API.Gumps.AddControlOnClick(decBtn, decrement_and_try)
gump.Add(decBtn)

incBtn = API.Gumps.CreateSimpleButton("+", 22, 20)
incBtn.SetPos(colRightX + 152, y)
incBtn.SetBackgroundHue(68)
API.Gumps.AddControlOnClick(incBtn, increment_and_try)
gump.Add(incBtn)

y += 23
scanBtn = API.Gumps.CreateSimpleButton("[SCAN 0-20]", 90, 20)
scanBtn.SetPos(colRightX, y)
scanBtn.SetBackgroundHue(88)
API.Gumps.AddControlOnClick(scanBtn, scan_buttons)
gump.Add(scanBtn)

lastClickLabel = API.Gumps.CreateGumpTTFLabel("Last: -", 9, "#ffff00")
lastClickLabel.SetPos(colRightX + 95, y + 3)
gump.Add(lastClickLabel)

# === ACTIVITY LOG SECTION ===
y = 300
divider = API.Gumps.CreateGumpColorBox(1.0, "#444444")
divider.SetRect(5, y, 370, 1)
gump.Add(divider)

y += 5
logTitle = API.Gumps.CreateGumpTTFLabel("=== ACTIVITY LOG (auto-monitors gumps) ===", 9, "#ff8800")
logTitle.SetPos(5, y)
gump.Add(logTitle)

clearLogBtn = API.Gumps.CreateSimpleButton("[CLR]", 35, 18)
clearLogBtn.SetPos(340, y - 2)
clearLogBtn.SetBackgroundHue(32)
API.Gumps.AddControlOnClick(clearLogBtn, clear_log)
gump.Add(clearLogBtn)

y += 16
logBg = API.Gumps.CreateGumpColorBox(0.6, "#000000")
logBg.SetRect(5, y, 370, 150)
gump.Add(logBg)

logLabel = API.Gumps.CreateGumpTTFLabel("Monitoring for gump activity...\n\nOPEN = Gump detected\nCLOSE = Gump closed (button pressed!)\nBTN = Button test result", 9, "#aaaaaa")
logLabel.SetPos(8, y + 2)
gump.Add(logLabel)

# Bottom buttons
y = 490
helpBtn = API.Gumps.CreateSimpleButton("[HELP]", 50, 22)
helpBtn.SetPos(5, y)
helpBtn.SetBackgroundHue(88)
API.Gumps.AddControlOnClick(helpBtn, show_help)
gump.Add(helpBtn)

closeScriptBtn = API.Gumps.CreateSimpleButton("[CLOSE INSPECTOR]", 110, 22)
closeScriptBtn.SetPos(265, y)
closeScriptBtn.SetBackgroundHue(32)
API.Gumps.AddControlOnClick(closeScriptBtn, stop_script)
gump.Add(closeScriptBtn)

API.Gumps.AddGump(gump)

# ============ INITIALIZATION ============
log_activity("INFO", "Gump Inspector v2.0 started")
log_activity("INFO", "Monitoring for gump activity...")

# Try to discover and register events
discover_events()
try_register_events()

# Initial snapshot
last_gump_snapshot = get_current_gumps()
if last_gump_snapshot:
    log_activity("INFO", "Found " + str(len(last_gump_snapshot)) + " existing gump(s)")
    for gid in last_gump_snapshot:
        log_activity("INFO", "  Existing: " + str(gid) + " (0x" + format(gid, 'X') + ")")
        selected_gump_id = gid
        selectedLabel.SetText("Sel: " + str(gid))

# ============ MAIN LOOP ============
last_check = time.time()

while not API.StopRequested:
    try:
        API.ProcessCallbacks()
        
        # Periodic gump monitoring
        if monitoring_enabled and time.time() - last_check > MONITOR_INTERVAL:
            check_for_gump_changes()
            last_check = time.time()
        
        API.Pause(0.1)
    except Exception as e:
        API.SysMsg("Error: " + str(e), 32)
        API.Pause(1)