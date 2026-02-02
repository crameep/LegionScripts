# ============================================================
# Captcha Solver v2.1
# by Coryigon for UO Unchained
# Claude Code integration with sample reference images
# ============================================================
#
# Helps solve the in-game Anti-Bot Captcha System (server-approved automation).
#
# Features:
#   - Watches journal for captcha messages
#   - Auto-screenshots when captcha detected
#   - Uses Claude Code CLI to read the 3-digit code
#   - Supports reference sample images for better accuracy
#   - Auto-submits the solution
#
# Requirements:
#   - Claude Code CLI installed: npm install -g @anthropic-ai/claude-code
#   - Claude Code authenticated (run `claude` once to set up)
#
# Sample Images (for better accuracy):
#   Create a "samples" folder next to this script.
#   Add captcha screenshots and name them with the 3-digit answer:
#     samples/
#       308.png   <- captcha showing 3, 0, 8
#       472.png   <- captcha showing 4, 7, 2
#       159.png   <- captcha showing 1, 5, 9
#       ...etc
#   The more samples covering all digits 0-9, the better!
#
# Usage:
#   1. Run script - it watches journal automatically
#   2. When captcha appears, it auto-solves and submits!
#   3. Use [SCREENSHOT] button to capture manually
#   4. Use [SOLVE] to test Claude integration
#
# ============================================================

import API
import time
import os
import subprocess
import re

__version__ = "2.1"

# ============ CONSTANTS ============
WINDOW_WIDTH = 200
NORMAL_HEIGHT = 195
CONFIG_HEIGHT = 445
JOURNAL_CHECK_INTERVAL = 1.0

# Captcha detection keywords
CAPTCHA_KEYWORDS = ["captcha", "anti-bot", "enter the numbers", "verification", "restricted from looting", "solve a puzzle", "prove you"]

# Claude Code prompt for reading the captcha
# This prompt is used when we have reference samples (full captcha examples)
CLAUDE_PROMPT_WITH_SAMPLES = """I have attached multiple captcha images as files. The reference images (named with their answers like 308.png) show solved examples. The LAST attached image (captcha_current.png) is the one to solve.

Study the reference images to learn what each digit 0-9 looks like in this gem/crystal style. Then read the 3 digits in the final captcha image.

CRITICAL: Respond with ONLY 3 digits, nothing else.
Example: 317"""

# Simpler prompt when no samples available
CLAUDE_PROMPT_NO_SAMPLES = """I have attached a captcha screenshot (captcha_current.png). It shows 3 gem-styled digits that you need to read.

CRITICAL: Respond with ONLY the 3 digits you see, nothing else.
Example: 317"""

# Folder containing sample captcha images (relative to script)
# Filename should be the answer, e.g., 308.png, 472.png
SAMPLES_FOLDER = "samples"

# ============ PERSISTENCE KEYS ============
KEY_PREFIX = "CaptchaSolver_"

# ============ RUNTIME STATE ============
watching_enabled = True
auto_solve_enabled = True  # Auto-solve toggle
debug_enabled = False  # Debug mode toggle
last_screenshot_time = None
last_solve_result = None  # Store last solve result
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
solveLabel = None  # NEW: Label for solve result
watchBtn = None
inputX = None
inputY = None
inputWidth = None
inputHeight = None
overlay_gump = None

# ============ UTILITY FUNCTIONS ============
def debug_msg(text):
    """Debug message helper - only shows if debug mode enabled."""
    if debug_enabled:
        API.SysMsg("[DEBUG] " + text, 88)

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
                debug_msg("Region: " + str(capture_x) + "," + str(capture_y) + " " + str(capture_width) + "x" + str(capture_height))
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

# ============ CLAUDE CODE INTEGRATION ============
def get_samples_path():
    """Get path to samples folder."""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
    except:
        script_dir = os.getcwd()
    return os.path.join(script_dir, SAMPLES_FOLDER)

def get_sample_images():
    """
    Get list of sample captcha images.
    Files should be named with the 3-digit answer, e.g., 308.png, 472.png
    """
    samples_dir = get_samples_path()
    
    if not os.path.exists(samples_dir):
        return []
    
    samples = []
    
    # Look for files named with 3-digit answers: 308.png, 472.png, etc.
    for filename in os.listdir(samples_dir):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            filepath = os.path.join(samples_dir, filename)
            
            # Extract the answer from filename (e.g., "308" from "308.png")
            name_without_ext = os.path.splitext(filename)[0]
            
            # Check if it's a valid 3-digit number
            if len(name_without_ext) == 3 and name_without_ext.isdigit():
                answer = name_without_ext
                samples.append((int(answer), filepath, filename, answer))
    
    # Sort by numeric value
    samples.sort(key=lambda x: x[0])
    
    return [(path, name, answer) for _, path, name, answer in samples]

def call_claude_code(image_path):
    """
    Call Claude Code CLI to analyze the captcha image.
    Includes sample reference images if available.
    Returns the 3-digit code or None on failure.
    """
    global last_solve_result

    try:
        import os
        import re

        # Get sample images
        sample_images = get_sample_images()

        # Build the command
        # Convert Windows paths to WSL paths using wslpath command
        def win_to_wsl_path(win_path):
            # Use wslpath for proper conversion
            win_path = os.path.abspath(win_path)
            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0

                proc = subprocess.Popen(
                    ["wsl", "wslpath", "-a", win_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    startupinfo=startupinfo
                )
                output = proc.stdout.read()
                wsl_path = output.decode('utf-8', errors='ignore').strip() if isinstance(output, bytes) else str(output).strip()

                if wsl_path and not wsl_path.startswith('wslpath:'):
                    return wsl_path
            except:
                pass

            # Fallback to manual conversion
            if len(win_path) > 1 and win_path[1] == ':':
                drive = win_path[0].lower()
                rest = win_path[2:].replace('\\', '/')
                return '/mnt/' + drive + rest
            return win_path.replace('\\', '/')

        # Verify the captcha image exists
        if not os.path.exists(image_path):
            API.SysMsg("ERROR: Captcha image not found at: " + image_path, 32)
            last_solve_result = "NO IMAGE"
            return None

        wsl_image_path = win_to_wsl_path(image_path)

        # Build command - images as arguments, prompt via stdin
        cmd = ["wsl", "claude"]

        if sample_images:
            # Use prompt with samples
            prompt = CLAUDE_PROMPT_WITH_SAMPLES
            debug_msg("Using " + str(len(sample_images)) + " sample captchas")

            # Add all sample images first
            for sample_path, sample_name, sample_answer in sample_images:
                wsl_path = win_to_wsl_path(sample_path)
                cmd.append(wsl_path)
                debug_msg("Sample: " + sample_answer + " -> " + wsl_path)

            # Add captcha image last
            cmd.append(wsl_image_path)
            debug_msg("Captcha: " + wsl_image_path)
        else:
            # No samples - just captcha image
            prompt = CLAUDE_PROMPT_NO_SAMPLES
            cmd.append(wsl_image_path)
            debug_msg("No samples, captcha: " + wsl_image_path)

        debug_msg("Calling Claude CLI...")

        # Hide console window on Windows
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE

        # Get system environment to access PATH
        env = os.environ.copy()

        # Run Claude Code via WSL with prompt via stdin
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo,
            env=env
        )

        # Write prompt to stdin
        try:
            proc.stdin.write(prompt.encode('utf-8'))
            proc.stdin.close()
        except:
            pass
        
        # Wait for completion with timeout
        import time as time_module
        start = time_module.time()
        while proc.poll() is None:
            if time_module.time() - start > 60:  # 60 second timeout (more images = more time)
                proc.kill()
                API.SysMsg("Claude timed out (60s)", 32)
                last_solve_result = "TIMEOUT"
                return None
            time_module.sleep(0.1)
        
        # Read both stdout and stderr
        stdout_bytes = proc.stdout.read()
        stderr_bytes = proc.stderr.read()

        stdout_str = stdout_bytes.decode('utf-8', errors='ignore') if isinstance(stdout_bytes, bytes) else str(stdout_bytes)
        stderr_str = stderr_bytes.decode('utf-8', errors='ignore') if isinstance(stderr_bytes, bytes) else str(stderr_bytes)

        if proc.returncode != 0:
            API.SysMsg("Claude error: " + stderr_str[:100], 32)
            debug_msg("Full stderr: " + stderr_str)
            last_solve_result = "ERROR"
            return None

        response = stdout_str.strip()
        debug_msg("Claude response: " + response[:100])

        # Extract 3-digit code from response
        match = re.search(r'(\d{3})', response)
        if match:
            code = match.group(1)
            last_solve_result = code
            return code

        API.SysMsg("Could not extract code", 32)
        last_solve_result = "NO DIGITS"
        return None
        
    except FileNotFoundError:
        API.SysMsg("Claude CLI not found!", 32)
        API.SysMsg("Install: npm i -g @anthropic-ai/claude-code", 43)
        last_solve_result = "NOT INSTALLED"
        return None
    except Exception as e:
        API.SysMsg("Error calling Claude: " + str(e), 32)
        last_solve_result = "ERROR"
        return None

def submit_captcha_answer(code):
    """Submit the captcha answer to the game."""
    if not code or len(code) != 3:
        API.SysMsg("Invalid code: " + str(code), 32)
        return False
    
    API.SysMsg("Submitting answer: " + code, 68)
    
    # Method 1: Use PromptResponse (if captcha uses text prompt)
    try:
        API.PromptResponse(code)
        debug_msg("Sent via PromptResponse")
        return True
    except:
        pass

    # Method 2: Just type it (some servers accept this)
    try:
        API.Msg(code)
        debug_msg("Sent via Msg")
        return True
    except:
        pass
    
    return False

def solve_captcha():
    """Full solve routine: screenshot -> Claude -> submit."""
    global last_solve_result
    
    API.SysMsg("=== AUTO-SOLVING CAPTCHA ===", 43)
    
    # Get screenshot path
    image_path = get_screenshot_path()
    
    # Check if screenshot exists
    if not os.path.exists(image_path):
        API.SysMsg("No screenshot found!", 32)
        last_solve_result = "NO IMAGE"
        return False
    
    # Call Claude
    code = call_claude_code(image_path)
    
    if code:
        API.SysMsg("Claude says: " + code, 68)
        # Submit the answer
        submit_captcha_answer(code)
        return True
    else:
        API.SysMsg("Could not solve captcha", 32)
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
    debug_msg("Opening captcha gump...")

    # Auto-screenshot after delay for gump to appear
    API.Pause(1.5)  # Delay for gump to appear
    take_screenshot()
    API.SysMsg("Screenshot taken automatically", 68)
    
    # NEW: Auto-solve if enabled
    if auto_solve_enabled:
        API.Pause(0.5)  # Small delay to ensure screenshot is saved
        solve_captcha()

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

def on_solve_click():
    """Handle solve button click - test Claude integration."""
    API.SysMsg("Testing Claude solve...", 68)
    solve_captcha()
    rebuild_gump()  # Update display with result

def on_open_captcha_click():
    """Type [captcha command in chat."""
    API.Msg("[captcha")
    debug_msg("Sent: [captcha")

def toggle_auto_solve():
    """Toggle auto-solve on/off."""
    global auto_solve_enabled
    auto_solve_enabled = not auto_solve_enabled
    API.SysMsg("Auto-solve: " + ("ENABLED" if auto_solve_enabled else "DISABLED"), 68)
    save_settings()
    rebuild_gump()

def toggle_debug():
    """Toggle debug mode on/off."""
    global debug_enabled
    debug_enabled = not debug_enabled
    API.SysMsg("Debug mode: " + ("ENABLED" if debug_enabled else "DISABLED"), 68)
    save_settings()
    rebuild_gump()

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
    debug_msg(str(w) + "x" + str(h) + " at " + str(x) + "," + str(y))

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
    debug_msg("1. Type [captcha to open captcha gump")
    debug_msg("2. Drag RED overlay to cover captcha")
    debug_msg("3. Click [CAPTURE FROM OVERLAY] button")

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
    debug_msg("Step 1: Opening captcha gump...")

    # Open captcha
    API.Msg("[captcha")
    API.Pause(1.5)

    # Take full screenshot for reference
    debug_msg("Step 2: Taking full reference screenshot...")

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
        proc.wait()

        API.SysMsg("Reference saved: " + abs_path, 68)
        API.SysMsg("Open it to find captcha coordinates!", 43)

    except Exception as e:
        API.SysMsg("Error: " + str(e), 32)

    # Restore region
    capture_x, capture_y, capture_width, capture_height = old_x, old_y, old_w, old_h

def toggle_watching():
    """Toggle journal watching on/off."""
    global watching_enabled
    watching_enabled = not watching_enabled
    API.SysMsg("Journal watching: " + ("ENABLED" if watching_enabled else "DISABLED"), 68)
    save_settings()
    rebuild_gump()

def on_expand_click():
    """Toggle config panel."""
    global config_visible
    config_visible = not config_visible
    rebuild_gump()

def on_config_click():
    """Toggle config panel."""
    global config_visible
    config_visible = not config_visible
    rebuild_gump()

def on_apply_region_click():
    """Apply region values from text inputs."""
    global capture_x, capture_y, capture_width, capture_height

    try:
        new_x = int(inputX.Text)
        new_y = int(inputY.Text)
        new_w = int(inputWidth.Text)
        new_h = int(inputHeight.Text)

        capture_x = new_x
        capture_y = new_y
        capture_width = new_w
        capture_height = new_h

        API.SysMsg("Region updated!", 68)
        save_settings()
        rebuild_gump()
    except ValueError:
        API.SysMsg("Invalid numbers!", 32)

def on_reset_region_click():
    """Reset to full screen capture."""
    global capture_x, capture_y, capture_width, capture_height
    capture_x = 0
    capture_y = 0
    capture_width = 0
    capture_height = 0
    API.SysMsg("Region reset to full screen", 68)
    save_settings()
    rebuild_gump()

def on_done_click():
    """Close config panel."""
    global config_visible
    config_visible = False
    rebuild_gump()

def on_closed():
    """Handle gump close."""
    global gump
    gump = None

# ============ PERSISTENCE ============
def save_settings():
    """Save settings to TazUO storage."""
    try:
        API.SetPersistentProperty(KEY_PREFIX + "watching", "true" if watching_enabled else "false")
        API.SetPersistentProperty(KEY_PREFIX + "auto_solve", "true" if auto_solve_enabled else "false")
        API.SetPersistentProperty(KEY_PREFIX + "debug", "true" if debug_enabled else "false")
        API.SetPersistentProperty(KEY_PREFIX + "capture_x", str(capture_x))
        API.SetPersistentProperty(KEY_PREFIX + "capture_y", str(capture_y))
        API.SetPersistentProperty(KEY_PREFIX + "capture_width", str(capture_width))
        API.SetPersistentProperty(KEY_PREFIX + "capture_height", str(capture_height))
    except:
        pass

def load_settings():
    """Load settings from TazUO storage."""
    global watching_enabled, auto_solve_enabled, debug_enabled, capture_x, capture_y, capture_width, capture_height

    try:
        val = API.GetPersistentProperty(KEY_PREFIX + "watching")
        if val:
            watching_enabled = val.lower() == "true"
    except:
        pass

    try:
        val = API.GetPersistentProperty(KEY_PREFIX + "auto_solve")
        if val:
            auto_solve_enabled = val.lower() == "true"
    except:
        pass

    try:
        val = API.GetPersistentProperty(KEY_PREFIX + "debug")
        if val:
            debug_enabled = val.lower() == "true"
    except:
        pass

    try:
        val = API.GetPersistentProperty(KEY_PREFIX + "capture_x")
        if val:
            capture_x = int(val)
    except:
        pass

    try:
        val = API.GetPersistentProperty(KEY_PREFIX + "capture_y")
        if val:
            capture_y = int(val)
    except:
        pass

    try:
        val = API.GetPersistentProperty(KEY_PREFIX + "capture_width")
        if val:
            capture_width = int(val)
    except:
        pass

    try:
        val = API.GetPersistentProperty(KEY_PREFIX + "capture_height")
        if val:
            capture_height = int(val)
    except:
        pass

# ============ GUI BUILDING ============
def rebuild_gump():
    """Rebuild the main gump."""
    global gump, statusLabel, timeLabel, solveLabel, watchBtn, inputX, inputY, inputWidth, inputHeight

    # Dispose old gump
    if gump:
        gump.Dispose()
        gump = None

    # Create new gump
    gump = API.Gumps.CreateGump()

    # Calculate height
    height = CONFIG_HEIGHT if config_visible else NORMAL_HEIGHT

    # Position
    gump.SetRect(100, 100, WINDOW_WIDTH, height)

    # Main background
    bg = API.Gumps.CreateGumpColorBox(0.95, "#1a1a2e")
    bg.SetRect(0, 0, WINDOW_WIDTH, height)
    gump.Add(bg)

    # Title bar
    sample_count = len(get_sample_images())
    title_text = "Captcha v2.1" + (" [" + str(sample_count) + " samples]" if sample_count > 0 else "")
    titleLabel = API.Gumps.CreateGumpTTFLabel(title_text, 14, "#ffaa00")
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
    status_text = "Status: CAPTCHA DETECTED!" if captcha_detected else ("Status: Watching..." if watching_enabled else "Status: Idle")
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

    # Last solve result
    solve_text = "Solve: " + (last_solve_result if last_solve_result else "---")
    solve_color = "#00ff00" if (last_solve_result and last_solve_result.isdigit()) else "#ff6666"
    solveLabel = API.Gumps.CreateGumpTTFLabel(solve_text, 11, solve_color)
    solveLabel.SetPos(100, 52)
    gump.Add(solveLabel)

    # Screenshot button
    screenshotBtn = API.Gumps.CreateSimpleButton("[SCREENSHOT]", 90, 26)
    screenshotBtn.SetPos(10, 75)
    screenshotBtn.SetBackgroundHue(68)
    API.Gumps.AddControlOnClick(screenshotBtn, on_screenshot_click)
    gump.Add(screenshotBtn)

    # Solve button (test Claude)
    solveBtn = API.Gumps.CreateSimpleButton("[SOLVE]", 80, 26)
    solveBtn.SetPos(110, 75)
    solveBtn.SetBackgroundHue(43)
    API.Gumps.AddControlOnClick(solveBtn, on_solve_click)
    gump.Add(solveBtn)

    # Open Captcha button
    captchaBtn = API.Gumps.CreateSimpleButton("[OPEN CAPTCHA]", 180, 22)
    captchaBtn.SetPos(10, 110)
    captchaBtn.SetBackgroundHue(90)
    API.Gumps.AddControlOnClick(captchaBtn, on_open_captcha_click)
    gump.Add(captchaBtn)

    # Auto-solve toggle
    autoText = "Auto: [ON]" if auto_solve_enabled else "Auto: [OFF]"
    autoBtn = API.Gumps.CreateSimpleButton(autoText, 85, 22)
    autoBtn.SetPos(10, 140)
    autoBtn.SetBackgroundHue(68 if auto_solve_enabled else 32)
    API.Gumps.AddControlOnClick(autoBtn, toggle_auto_solve)
    gump.Add(autoBtn)

    # Watch toggle (compact)
    watchText = "Watch: [ON]" if watching_enabled else "Watch: [OFF]"
    watchCompactBtn = API.Gumps.CreateSimpleButton(watchText, 85, 22)
    watchCompactBtn.SetPos(105, 140)
    watchCompactBtn.SetBackgroundHue(68 if watching_enabled else 32)
    API.Gumps.AddControlOnClick(watchCompactBtn, toggle_watching)
    gump.Add(watchCompactBtn)

    # Config panel (only if visible)
    if config_visible:
        # Config background
        configBg = API.Gumps.CreateGumpColorBox(0.90, "#16213e")
        configBg.SetRect(5, 170, WINDOW_WIDTH - 10, CONFIG_HEIGHT - 175)
        gump.Add(configBg)

        # Config title
        configTitle = API.Gumps.CreateGumpTTFLabel("Configuration", 11, "#ffaa00")
        configTitle.SetPos(15, 175)
        gump.Add(configTitle)

        # Region section title
        regionTitle = API.Gumps.CreateGumpTTFLabel("Capture Region (0=full)", 11, "#ffaa00")
        regionTitle.SetPos(15, 200)
        gump.Add(regionTitle)

        # X position
        xLabel = API.Gumps.CreateGumpTTFLabel("X:", 11, "#888888")
        xLabel.SetPos(15, 220)
        gump.Add(xLabel)

        inputX = API.Gumps.CreateGumpTextBox(str(capture_x), 40, 18)
        inputX.SetPos(35, 218)
        gump.Add(inputX)

        # Y position
        yLabel = API.Gumps.CreateGumpTTFLabel("Y:", 11, "#888888")
        yLabel.SetPos(100, 220)
        gump.Add(yLabel)

        inputY = API.Gumps.CreateGumpTextBox(str(capture_y), 40, 18)
        inputY.SetPos(120, 218)
        gump.Add(inputY)

        # Width
        wLabel = API.Gumps.CreateGumpTTFLabel("W:", 11, "#888888")
        wLabel.SetPos(15, 245)
        gump.Add(wLabel)

        inputWidth = API.Gumps.CreateGumpTextBox(str(capture_width), 40, 18)
        inputWidth.SetPos(35, 243)
        gump.Add(inputWidth)

        # Height
        hLabel = API.Gumps.CreateGumpTTFLabel("H:", 11, "#888888")
        hLabel.SetPos(100, 245)
        gump.Add(hLabel)

        inputHeight = API.Gumps.CreateGumpTextBox(str(capture_height), 40, 18)
        inputHeight.SetPos(120, 243)
        gump.Add(inputHeight)

        # Current region display
        if capture_width > 0 and capture_height > 0:
            currentLabel = API.Gumps.CreateGumpTTFLabel("Current: " + str(capture_width) + "x" + str(capture_height) + " at " + str(capture_x) + "," + str(capture_y), 11, "#88ff88")
        else:
            currentLabel = API.Gumps.CreateGumpTTFLabel("Current: Full Screen", 11, "#888888")
        currentLabel.SetPos(15, 270)
        gump.Add(currentLabel)

        # Apply button
        applyBtn = API.Gumps.CreateSimpleButton("[APPLY]", 80, 22)
        applyBtn.SetPos(15, 295)
        applyBtn.SetBackgroundHue(68)
        API.Gumps.AddControlOnClick(applyBtn, on_apply_region_click)
        gump.Add(applyBtn)

        # Reset button
        resetBtn = API.Gumps.CreateSimpleButton("[RESET]", 80, 22)
        resetBtn.SetPos(105, 295)
        resetBtn.SetBackgroundHue(43)
        API.Gumps.AddControlOnClick(resetBtn, on_reset_region_click)
        gump.Add(resetBtn)

        # Show overlay button
        overlayBtn = API.Gumps.CreateSimpleButton("[SHOW OVERLAY]", 80, 22)
        overlayBtn.SetPos(15, 325)
        overlayBtn.SetBackgroundHue(66)
        API.Gumps.AddControlOnClick(overlayBtn, on_show_overlay_click)
        gump.Add(overlayBtn)

        # Capture from overlay button
        captureBtn = API.Gumps.CreateSimpleButton("[CAPTURE]", 80, 22)
        captureBtn.SetPos(105, 325)
        captureBtn.SetBackgroundHue(68)
        API.Gumps.AddControlOnClick(captureBtn, on_capture_overlay_click)
        gump.Add(captureBtn)

        # Help button (old method)
        helpBtn = API.Gumps.CreateSimpleButton("[HELP: MANUAL]", 170, 22)
        helpBtn.SetPos(15, 355)
        helpBtn.SetBackgroundHue(90)
        API.Gumps.AddControlOnClick(helpBtn, on_help_set_region_click)
        gump.Add(helpBtn)

        # Debug toggle
        debugText = "Debug: [ON]" if debug_enabled else "Debug: [OFF]"
        debugBtn = API.Gumps.CreateSimpleButton(debugText, 170, 22)
        debugBtn.SetPos(15, 380)
        debugBtn.SetBackgroundHue(68 if debug_enabled else 90)
        API.Gumps.AddControlOnClick(debugBtn, toggle_debug)
        gump.Add(debugBtn)

        # Done button
        doneBtn = API.Gumps.CreateSimpleButton("[DONE]", 170, 22)
        doneBtn.SetPos(15, 410)
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
        statusLabel.SetText("Status: Watching...")
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
    
    # Update solve result
    if solveLabel and last_solve_result:
        solveLabel.SetText("Solve: " + last_solve_result)

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
debug_msg("Screenshots: " + get_screenshot_path())

# Check for samples
sample_images = get_sample_images()
if sample_images:
    API.SysMsg("Samples loaded: " + str(len(sample_images)) + " solved captchas", 68)
    # Show which digits are covered
    digits_seen = set()
    for _, _, answer in sample_images:
        for d in answer:
            digits_seen.add(d)
    missing = set("0123456789") - digits_seen
    if missing:
        API.SysMsg("Missing digits: " + ", ".join(sorted(missing)), 43)
    else:
        API.SysMsg("All digits 0-9 covered!", 68)
else:
    API.SysMsg("No samples found in: " + get_samples_path(), 43)
    API.SysMsg("Add solved captchas (e.g., 308.png) for better accuracy!", 43)

if watching_enabled:
    API.SysMsg("Journal watching: ENABLED", 68)
if auto_solve_enabled:
    API.SysMsg("Auto-solve: ENABLED (using Claude Code)", 68)
if debug_enabled:
    API.SysMsg("Debug mode: ENABLED", 68)
if capture_width > 0 and capture_height > 0:
    debug_msg("Capture region: " + str(capture_width) + "x" + str(capture_height) + " at " + str(capture_x) + "," + str(capture_y))

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
