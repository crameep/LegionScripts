# ============================================================
# Captcha Solver v1.0
# by Coryigon for UO Unchained
# ============================================================
#
# Helps solve the in-game Anti-Bot Captcha System (server-approved automation).
#
# Features:
#   - Watches journal for captcha messages
#   - Auto-screenshots when captcha detected
#   - Manual screenshot test button
#   - Saves screenshots to: captcha_current.png
#
# Usage:
#   1. Run script - it watches journal automatically
#   2. When captcha appears, screenshot is taken automatically
#   3. Use [TEST SCREENSHOT] button to test manually
#   4. Screenshot saved to: CoryCustom/captcha_current.png
#
# Next steps (TODO):
#   - Add Claude Code CLI integration to read numbers
#   - Auto-submit solution to captcha gump
#
# ============================================================

import API
import time
import os

__version__ = "1.0"

# ============ CONSTANTS ============
WINDOW_WIDTH = 200
NORMAL_HEIGHT = 165
CONFIG_HEIGHT = 440
JOURNAL_CHECK_INTERVAL = 1.0

# Captcha detection keywords
CAPTCHA_KEYWORDS = ["captcha", "anti-bot", "enter the numbers", "verification", "restricted from looting", "solve a puzzle", "prove you"]

# ============ PERSISTENCE KEYS ============
KEY_PREFIX = "CaptchaSolver_"

# ============ RUNTIME STATE ============
watching_enabled = True
last_screenshot_time = None
captcha_detected = False
captcha_detect_time = 0
config_visible = False
next_journal_check = time.time()
last_journal_index = 0
CAPTCHA_COOLDOWN = 30  # Don't re-detect for 30 seconds

# Screenshot region (default: full screen, use 0 for full)
capture_x = 0
capture_y = 0
capture_width = 0
capture_height = 0

# GUI references
gump = None
statusLabel = None
timeLabel = None
watchBtn = None
inputX = None
inputY = None
inputWidth = None
inputHeight = None
overlay_gump = None

# ============ UTILITY FUNCTIONS ============
def debug_msg(text):
    """Debug message helper."""
    API.SysMsg("[Captcha] " + text, 88)

# ============ SCREENSHOT FUNCTIONS ============
def get_screenshot_path():
    """Get absolute path for screenshot in script directory."""
    import os
    # Try to get script directory
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
    except:
        # Fallback to current directory
        script_dir = os.getcwd()

    return os.path.join(script_dir, "captcha_current.png")

def take_screenshot():
    """Take screenshot and save to file using PowerShell."""
    global last_screenshot_time

    try:
        import subprocess

        # Get absolute path for screenshot
        abs_path = get_screenshot_path()

        # Determine capture region
        if capture_width > 0 and capture_height > 0:
            # Capture specific region
            ps_cmd = '''
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$x = ''' + str(capture_x) + '''
$y = ''' + str(capture_y) + '''
$width = ''' + str(capture_width) + '''
$height = ''' + str(capture_height) + '''

$bitmap = New-Object System.Drawing.Bitmap($width, $height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($x, $y, 0, 0, $bitmap.Size)

$bitmap.Save("''' + abs_path + '''", [System.Drawing.Imaging.ImageFormat]::Png)

$graphics.Dispose()
$bitmap.Dispose()

Write-Host "Screenshot saved"
'''
        else:
            # Capture full screen
            ps_cmd = '''
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)

$bitmap.Save("''' + abs_path + '''", [System.Drawing.Imaging.ImageFormat]::Png)

$graphics.Dispose()
$bitmap.Dispose()

Write-Host "Screenshot saved"
'''

        # Use Popen for older Python compatibility
        # Hide the PowerShell window so it doesn't appear in screenshot
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE

        proc = subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-Command", ps_cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo
        )

        # Wait for completion (with timeout simulation)
        import time as time_module
        start = time_module.time()
        while proc.poll() is None:
            if time_module.time() - start > 10:
                proc.kill()
                API.SysMsg("Screenshot timeout (10s)", 32)
                return False
            time_module.sleep(0.1)

        # Check if successful
        if proc.returncode == 0:
            last_screenshot_time = time.time()

            if capture_width > 0 and capture_height > 0:
                API.SysMsg("Screenshot saved (region): " + abs_path, 68)
                API.SysMsg("Region: " + str(capture_x) + "," + str(capture_y) + " " + str(capture_width) + "x" + str(capture_height), 88)
            else:
                API.SysMsg("Screenshot saved (full): " + abs_path, 68)
            return True
        else:
            API.SysMsg("PowerShell failed!", 32)
            stderr = proc.stderr.read()
            if stderr:
                API.SysMsg("Error: " + str(stderr)[:100], 32)
            return False

    except Exception as e:
        API.SysMsg("Screenshot error: " + str(e), 32)
        return False

# ============ JOURNAL WATCHING ============
def on_captcha_detected():
    """Called when captcha message seen in journal."""
    global captcha_detected, captcha_detect_time

    # Check cooldown - don't re-trigger within cooldown period
    if captcha_detected and (time.time() - captcha_detect_time) < CAPTCHA_COOLDOWN:
        return  # Still in cooldown, don't spam

    captcha_detected = True
    captcha_detect_time = time.time()

    # Clear the journal entry so we don't re-detect it
    try:
        API.ClearJournal()
    except:
        pass

    API.SysMsg("=== CAPTCHA DETECTED ===", 43)

    # Auto-open captcha gump
    API.Msg("[captcha")
    API.SysMsg("Opening captcha gump...", 88)

    # Auto-screenshot after delay for gump to appear
    API.Pause(1.5)  # Delay for gump to appear
    take_screenshot()
    API.SysMsg("Screenshot taken automatically", 68)

def watch_journal():
    """Check journal for captcha messages."""
    if not watching_enabled:
        return

    # Reset captcha detected flag after cooldown expires
    global captcha_detected, captcha_detect_time
    if captcha_detected and (time.time() - captcha_detect_time) >= CAPTCHA_COOLDOWN:
        captcha_detected = False

    # Don't check if we just detected one recently
    if captcha_detected:
        return

    try:
        # Check for the main captcha message (clearMatches=False to not clear it yet)
        if API.InJournal("You are currently restricted from looting corpses", False):
            on_captcha_detected()
            return

        # Check for alternate messages
        if API.InJournal("solve a puzzle", False):
            on_captcha_detected()
            return

        if API.InJournal("anti-bot", False):
            on_captcha_detected()
            return

    except Exception as e:
        # Silently ignore journal errors
        pass

# ============ GUI CALLBACKS ============
def on_screenshot_click():
    """Handle screenshot button click."""
    global captcha_detected, captcha_detect_time
    API.SysMsg("Taking screenshot...", 68)
    captcha_detected = False  # Reset flag
    captcha_detect_time = 0
    take_screenshot()

def on_open_captcha_click():
    """Type [captcha command in chat."""
    API.Msg("[captcha")
    API.SysMsg("Sent: [captcha", 88)

def on_capture_overlay_click():
    """Capture position from overlay gump."""
    global capture_x, capture_y, capture_width, capture_height, overlay_gump

    if not overlay_gump:
        API.SysMsg("No overlay active!", 32)
        return

    # Get overlay position
    x = overlay_gump.GetX()
    y = overlay_gump.GetY()

    # Overlay is always 400x300
    w = 400
    h = 300

    # Apply to capture region
    capture_x = x
    capture_y = y
    capture_width = w
    capture_height = h

    API.SysMsg("Region captured from overlay!", 68)
    API.SysMsg(str(w) + "x" + str(h) + " at " + str(x) + "," + str(y), 88)

    # Close overlay
    overlay_gump.Dispose()
    overlay_gump = None

    save_settings()
    rebuild_gump()

def on_overlay_closed():
    """Handle overlay close."""
    global overlay_gump
    overlay_gump = None

def on_show_overlay_click():
    """Show positioning overlay gump."""
    global overlay_gump

    if overlay_gump:
        API.SysMsg("Overlay already open!", 32)
        return

    API.SysMsg("=== POSITIONING OVERLAY ===", 43)
    API.SysMsg("1. Type [captcha to open captcha gump", 88)
    API.SysMsg("2. Drag RED overlay to cover captcha", 88)
    API.SysMsg("3. Click [CAPTURE FROM OVERLAY] button", 88)

    # Open captcha for reference
    API.Msg("[captcha")
    API.Pause(1.0)

    # Create overlay gump
    overlay_gump = API.Gumps.CreateGump()

    # Position near center of screen
    start_x = 400
    start_y = 300
    overlay_width = 400
    overlay_height = 300

    overlay_gump.SetRect(start_x, start_y, overlay_width, overlay_height)

    # Semi-transparent red background
    bg = API.Gumps.CreateGumpColorBox(0.5, "#ff0000")
    bg.SetRect(0, 0, overlay_width, overlay_height)
    overlay_gump.Add(bg)

    # Border
    border = API.Gumps.CreateGumpColorBox(1.0, "#ffffff")
    border.SetRect(0, 0, overlay_width, 2)  # Top
    overlay_gump.Add(border)

    border2 = API.Gumps.CreateGumpColorBox(1.0, "#ffffff")
    border2.SetRect(0, overlay_height - 2, overlay_width, 2)  # Bottom
    overlay_gump.Add(border2)

    border3 = API.Gumps.CreateGumpColorBox(1.0, "#ffffff")
    border3.SetRect(0, 0, 2, overlay_height)  # Left
    overlay_gump.Add(border3)

    border4 = API.Gumps.CreateGumpColorBox(1.0, "#ffffff")
    border4.SetRect(overlay_width - 2, 0, 2, overlay_height)  # Right
    overlay_gump.Add(border4)

    # Title
    titleLabel = API.Gumps.CreateGumpTTFLabel("DRAG ME TO COVER CAPTCHA", 16, "#ffffff")
    titleLabel.SetPos(50, 10)
    overlay_gump.Add(titleLabel)

    # Instructions
    infoLabel = API.Gumps.CreateGumpTTFLabel("Drag this window over the captcha gump", 11, "#ffffff")
    infoLabel.SetPos(50, 140)
    overlay_gump.Add(infoLabel)

    infoLabel2 = API.Gumps.CreateGumpTTFLabel("Then click [CAPTURE FROM OVERLAY]", 11, "#ffffff")
    infoLabel2.SetPos(50, 160)
    overlay_gump.Add(infoLabel2)

    # Register close callback
    API.Gumps.AddControlOnDisposed(overlay_gump, on_overlay_closed)

    # Show overlay
    API.Gumps.AddGump(overlay_gump)

def on_help_set_region_click():
    """Help user set the capture region."""
    global capture_x, capture_y, capture_width, capture_height

    API.SysMsg("=== SET REGION HELPER ===", 43)
    API.SysMsg("Step 1: Opening captcha gump...", 88)

    # Open captcha
    API.Msg("[captcha")
    API.Pause(1.5)

    # Take full screenshot for reference
    API.SysMsg("Step 2: Taking full reference screenshot...", 88)

    # Temporarily set to full screen
    old_x, old_y, old_w, old_h = capture_x, capture_y, capture_width, capture_height
    capture_x = 0
    capture_y = 0
    capture_width = 0
    capture_height = 0

    # Take screenshot
    import os
    ref_path = os.path.join(os.path.dirname(get_screenshot_path()), "captcha_reference_fullscreen.png")

    try:
        import subprocess
        abs_path = os.path.abspath(ref_path)

        ps_cmd = '''
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)

$bitmap.Save("''' + abs_path + '''", [System.Drawing.Imaging.ImageFormat]::Png)

$graphics.Dispose()
$bitmap.Dispose()

Write-Host "Screenshot saved"
'''

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0

        proc = subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-Command", ps_cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo
        )

        start = time.time()
        while proc.poll() is None:
            if time.time() - start > 10:
                proc.kill()
                break
            time.sleep(0.1)

        if proc.returncode == 0:
            API.SysMsg("Reference saved: captcha_reference_fullscreen.png", 68)
            API.SysMsg("", 88)
            API.SysMsg("Step 3: How to find coordinates:", 43)
            API.SysMsg("1. Open captcha_reference_fullscreen.png", 88)
            API.SysMsg("2. Hover over TOP-LEFT of captcha gump", 88)
            API.SysMsg("3. Note X,Y coordinates (shown in image viewer)", 88)
            API.SysMsg("4. Hover over BOTTOM-RIGHT corner", 88)
            API.SysMsg("5. Width = (right X) - (left X)", 88)
            API.SysMsg("6. Height = (bottom Y) - (top Y)", 88)
            API.SysMsg("7. Enter values in config panel and click APPLY", 88)
        else:
            API.SysMsg("Screenshot failed!", 32)

    except Exception as e:
        API.SysMsg("Error: " + str(e), 32)

    # Restore old region
    capture_x, capture_y, capture_width, capture_height = old_x, old_y, old_w, old_h

def toggle_watching():
    """Toggle journal watching on/off."""
    global watching_enabled, captcha_detected, captcha_detect_time
    watching_enabled = not watching_enabled
    captcha_detected = False  # Reset on toggle
    captcha_detect_time = 0
    API.SysMsg("Journal watching: " + ("ON" if watching_enabled else "OFF"), 68 if watching_enabled else 32)
    save_settings()
    rebuild_gump()

def on_config_click():
    """Toggle config panel visibility."""
    global config_visible
    config_visible = not config_visible
    rebuild_gump()

def on_done_click():
    """Close config panel."""
    on_config_click()

def on_expand_click():
    """Expand to show config."""
    on_config_click()

def on_apply_region_click():
    """Apply region from text inputs."""
    global capture_x, capture_y, capture_width, capture_height

    try:
        # Read values from text inputs
        x_str = inputX.Text.strip()
        y_str = inputY.Text.strip()
        w_str = inputWidth.Text.strip()
        h_str = inputHeight.Text.strip()

        # Parse integers
        new_x = int(x_str) if x_str else 0
        new_y = int(y_str) if y_str else 0
        new_w = int(w_str) if w_str else 0
        new_h = int(h_str) if h_str else 0

        # Validate
        if new_w < 0 or new_h < 0:
            API.SysMsg("Width/Height cannot be negative", 32)
            return

        # Apply
        capture_x = new_x
        capture_y = new_y
        capture_width = new_w
        capture_height = new_h

        if capture_width > 0 and capture_height > 0:
            API.SysMsg("Region set: " + str(capture_width) + "x" + str(capture_height), 68)
            API.SysMsg("at " + str(capture_x) + "," + str(capture_y), 88)
        else:
            API.SysMsg("Region set to: Full Screen", 68)

        save_settings()
        rebuild_gump()

    except ValueError:
        API.SysMsg("Invalid numbers in region fields", 32)
    except Exception as e:
        API.SysMsg("Error: " + str(e), 32)

def on_reset_region_click():
    """Reset to full screen capture."""
    global capture_x, capture_y, capture_width, capture_height
    capture_x = 0
    capture_y = 0
    capture_width = 0
    capture_height = 0
    API.SysMsg("Region reset to: Full Screen", 68)
    save_settings()
    rebuild_gump()

def on_closed():
    """Handle window close."""
    global gump
    if gump:
        # Save window position
        API.SavePersistentVar(KEY_PREFIX + "XY", f"{gump.GetX()},{gump.GetY()}", API.PersistentVar.Char)
    cleanup()

# ============ PERSISTENCE ============
def save_settings():
    """Save all settings."""
    API.SavePersistentVar(KEY_PREFIX + "Watching", str(watching_enabled), API.PersistentVar.Char)
    API.SavePersistentVar(KEY_PREFIX + "Region", str(capture_x) + "," + str(capture_y) + "," + str(capture_width) + "," + str(capture_height), API.PersistentVar.Char)

def load_settings():
    """Load all settings with defaults."""
    global watching_enabled, capture_x, capture_y, capture_width, capture_height

    watching_enabled = API.GetPersistentVar(KEY_PREFIX + "Watching", "True", API.PersistentVar.Char) == "True"

    region_str = API.GetPersistentVar(KEY_PREFIX + "Region", "0,0,0,0", API.PersistentVar.Char)
    region_parts = region_str.split(',')
    if len(region_parts) == 4:
        capture_x = int(region_parts[0])
        capture_y = int(region_parts[1])
        capture_width = int(region_parts[2])
        capture_height = int(region_parts[3])

# ============ GUI REBUILD ============
def rebuild_gump():
    """Rebuild entire gump with current state."""
    global gump, statusLabel, timeLabel, watchBtn, inputX, inputY, inputWidth, inputHeight

    # Save position if gump exists
    saved_x, saved_y = 100, 100
    if gump:
        saved_x = gump.GetX()
        saved_y = gump.GetY()
        gump.Dispose()
    else:
        # Load saved position
        saved_pos = API.GetPersistentVar(KEY_PREFIX + "XY", "100,100", API.PersistentVar.Char)
        pos_parts = saved_pos.split(',')
        saved_x, saved_y = int(pos_parts[0]), int(pos_parts[1])

    # Create new gump
    gump = API.Gumps.CreateGump()
    height = CONFIG_HEIGHT if config_visible else NORMAL_HEIGHT
    gump.SetRect(saved_x, saved_y, WINDOW_WIDTH, height)

    # Background
    bg = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
    bg.SetRect(0, 0, WINDOW_WIDTH, height)
    gump.Add(bg)

    # Title bar
    titleLabel = API.Gumps.CreateGumpTTFLabel("Captcha Solver", 16, "#ffaa00")
    titleLabel.SetPos(10, 5)
    gump.Add(titleLabel)

    # Config button
    configBtn = API.Gumps.CreateSimpleButton("[C]", 30, 22)
    configBtn.SetPos(WINDOW_WIDTH - 70, 3)
    configBtn.SetBackgroundHue(68 if config_visible else 90)
    API.Gumps.AddControlOnClick(configBtn, on_config_click)
    gump.Add(configBtn)

    # Expand button (only show when not in config)
    if not config_visible:
        expandBtn = API.Gumps.CreateSimpleButton("[-]", 30, 22)
        expandBtn.SetPos(WINDOW_WIDTH - 35, 3)
        expandBtn.SetBackgroundHue(90)
        API.Gumps.AddControlOnClick(expandBtn, on_expand_click)
        gump.Add(expandBtn)

    # Status label
    status_text = "Status: CAPTCHA DETECTED!" if captcha_detected else ("Status: Watching journal..." if watching_enabled else "Status: Idle")
    statusLabel = API.Gumps.CreateGumpTTFLabel(status_text, 11, "#00ff00")
    statusLabel.SetPos(10, 35)
    gump.Add(statusLabel)

    # Last screenshot time
    if last_screenshot_time:
        elapsed = int(time.time() - last_screenshot_time)
        if elapsed < 60:
            time_text = "Last: " + str(elapsed) + "s ago"
        else:
            mins = elapsed // 60
            time_text = "Last: " + str(mins) + "m ago"
    else:
        time_text = "Last: Never"
    timeLabel = API.Gumps.CreateGumpTTFLabel(time_text, 11, "#ffcc00")
    timeLabel.SetPos(10, 52)
    gump.Add(timeLabel)

    # Screenshot button (big and prominent)
    screenshotBtn = API.Gumps.CreateSimpleButton("[TEST SCREENSHOT]", 180, 30)
    screenshotBtn.SetPos(10, 75)
    screenshotBtn.SetBackgroundHue(68)
    API.Gumps.AddControlOnClick(screenshotBtn, on_screenshot_click)
    gump.Add(screenshotBtn)

    # Open Captcha button
    captchaBtn = API.Gumps.CreateSimpleButton("[OPEN CAPTCHA]", 180, 22)
    captchaBtn.SetPos(10, 110)
    captchaBtn.SetBackgroundHue(43)
    API.Gumps.AddControlOnClick(captchaBtn, on_open_captcha_click)
    gump.Add(captchaBtn)

    # Config panel (only if visible)
    if config_visible:
        # Config background
        configBg = API.Gumps.CreateGumpColorBox(0.90, "#16213e")
        configBg.SetRect(5, 115, WINDOW_WIDTH - 10, CONFIG_HEIGHT - 120)
        gump.Add(configBg)

        # Config title
        configTitle = API.Gumps.CreateGumpTTFLabel("Configuration", 11, "#ffaa00")
        configTitle.SetPos(15, 120)
        gump.Add(configTitle)

        # Watching toggle
        watchBtn = API.Gumps.CreateSimpleButton("Watching: [" + ("ON" if watching_enabled else "OFF") + "]", 170, 22)
        watchBtn.SetPos(15, 145)
        watchBtn.SetBackgroundHue(68 if watching_enabled else 32)
        API.Gumps.AddControlOnClick(watchBtn, toggle_watching)
        gump.Add(watchBtn)

        # Region section title
        regionTitle = API.Gumps.CreateGumpTTFLabel("Capture Region (0=full)", 11, "#ffaa00")
        regionTitle.SetPos(15, 175)
        gump.Add(regionTitle)

        # X position
        xLabel = API.Gumps.CreateGumpTTFLabel("X:", 11, "#888888")
        xLabel.SetPos(15, 195)
        gump.Add(xLabel)

        inputX = API.Gumps.CreateGumpTextBox(str(capture_x), 40, 18)
        inputX.SetPos(35, 193)
        gump.Add(inputX)

        # Y position
        yLabel = API.Gumps.CreateGumpTTFLabel("Y:", 11, "#888888")
        yLabel.SetPos(100, 195)
        gump.Add(yLabel)

        inputY = API.Gumps.CreateGumpTextBox(str(capture_y), 40, 18)
        inputY.SetPos(120, 193)
        gump.Add(inputY)

        # Width
        wLabel = API.Gumps.CreateGumpTTFLabel("W:", 11, "#888888")
        wLabel.SetPos(15, 220)
        gump.Add(wLabel)

        inputWidth = API.Gumps.CreateGumpTextBox(str(capture_width), 40, 18)
        inputWidth.SetPos(35, 218)
        gump.Add(inputWidth)

        # Height
        hLabel = API.Gumps.CreateGumpTTFLabel("H:", 11, "#888888")
        hLabel.SetPos(100, 220)
        gump.Add(hLabel)

        inputHeight = API.Gumps.CreateGumpTextBox(str(capture_height), 40, 18)
        inputHeight.SetPos(120, 218)
        gump.Add(inputHeight)

        # Current region display
        if capture_width > 0 and capture_height > 0:
            currentLabel = API.Gumps.CreateGumpTTFLabel("Current: " + str(capture_width) + "x" + str(capture_height) + " at " + str(capture_x) + "," + str(capture_y), 11, "#88ff88")
        else:
            currentLabel = API.Gumps.CreateGumpTTFLabel("Current: Full Screen", 11, "#888888")
        currentLabel.SetPos(15, 245)
        gump.Add(currentLabel)

        # Apply button
        applyBtn = API.Gumps.CreateSimpleButton("[APPLY]", 80, 22)
        applyBtn.SetPos(15, 270)
        applyBtn.SetBackgroundHue(68)
        API.Gumps.AddControlOnClick(applyBtn, on_apply_region_click)
        gump.Add(applyBtn)

        # Reset button
        resetBtn = API.Gumps.CreateSimpleButton("[RESET]", 80, 22)
        resetBtn.SetPos(105, 270)
        resetBtn.SetBackgroundHue(43)
        API.Gumps.AddControlOnClick(resetBtn, on_reset_region_click)
        gump.Add(resetBtn)

        # Show overlay button
        overlayBtn = API.Gumps.CreateSimpleButton("[SHOW OVERLAY]", 80, 22)
        overlayBtn.SetPos(15, 300)
        overlayBtn.SetBackgroundHue(66)
        API.Gumps.AddControlOnClick(overlayBtn, on_show_overlay_click)
        gump.Add(overlayBtn)

        # Capture from overlay button
        captureBtn = API.Gumps.CreateSimpleButton("[CAPTURE]", 80, 22)
        captureBtn.SetPos(105, 300)
        captureBtn.SetBackgroundHue(68)
        API.Gumps.AddControlOnClick(captureBtn, on_capture_overlay_click)
        gump.Add(captureBtn)

        # Help button (old method)
        helpBtn = API.Gumps.CreateSimpleButton("[HELP: MANUAL]", 170, 22)
        helpBtn.SetPos(15, 330)
        helpBtn.SetBackgroundHue(90)
        API.Gumps.AddControlOnClick(helpBtn, on_help_set_region_click)
        gump.Add(helpBtn)

        # Done button
        doneBtn = API.Gumps.CreateSimpleButton("[DONE]", 170, 22)
        doneBtn.SetPos(15, 400)
        doneBtn.SetBackgroundHue(90)
        API.Gumps.AddControlOnClick(doneBtn, on_done_click)
        gump.Add(doneBtn)

    # Register close callback
    API.Gumps.AddControlOnDisposed(gump, on_closed)

    # Show GUI
    API.Gumps.AddGump(gump)

# ============ DISPLAY UPDATES ============
def update_display():
    """Update status labels."""
    if not statusLabel or not timeLabel:
        return

    if captcha_detected:
        statusLabel.SetText("Status: CAPTCHA DETECTED!")
    elif watching_enabled:
        statusLabel.SetText("Status: Watching journal...")
    else:
        statusLabel.SetText("Status: Idle")

    if last_screenshot_time:
        elapsed = int(time.time() - last_screenshot_time)
        if elapsed < 60:
            timeLabel.SetText("Last: " + str(elapsed) + "s ago")
        else:
            mins = elapsed // 60
            timeLabel.SetText("Last: " + str(mins) + "m ago")
    else:
        timeLabel.SetText("Last: Never")

# ============ CLEANUP ============
def cleanup():
    """Cleanup on exit."""
    save_settings()

# ============ INITIALIZATION ============
load_settings()

# ============ BUILD GUI ============
rebuild_gump()

# ============ STARTUP MESSAGE ============
API.SysMsg("Captcha Solver v" + __version__ + " started", 68)
API.SysMsg("Screenshots: " + get_screenshot_path(), 88)
if watching_enabled:
    API.SysMsg("Journal watching: ENABLED", 68)
if capture_width > 0 and capture_height > 0:
    API.SysMsg("Capture region: " + str(capture_width) + "x" + str(capture_height) + " at " + str(capture_x) + "," + str(capture_y), 88)

# ============ MAIN LOOP ============
while not API.StopRequested:
    try:
        API.ProcessCallbacks()

        # Check journal periodically
        if time.time() >= next_journal_check:
            watch_journal()
            next_journal_check = time.time() + JOURNAL_CHECK_INTERVAL

        update_display()
        API.Pause(0.1)

    except Exception as e:
        if "operation canceled" not in str(e).lower() and not API.StopRequested:
            API.SysMsg("Error: " + str(e), 32)
        API.Pause(1)

cleanup()
