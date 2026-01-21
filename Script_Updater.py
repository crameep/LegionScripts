# ============================================================
# Script Updater v1.2
# by Coryigon for TazUO Legion Scripts
# ============================================================
#
# Automatic script updater that downloads latest versions from GitHub.
# Non-blocking state machine keeps GUI responsive during downloads.
#
# Features:
#   - Check for script updates from GitHub repository
#   - Compare local vs remote versions (semantic versioning)
#   - Backup scripts before updating (_backups directory)
#   - Restore previous versions from backup
#   - Scrollable list with checkboxes for selective updates
#   - Status indicators: NEW, OK, UPDATE, N-A, ERROR
#   - Network error handling with timeouts
#   - Warning if script might be running
#
# ============================================================
import API
import time
import re
import os
try:
    import urllib.request
except ImportError:
    import urllib2 as urllib_request  # Fallback for older Python

__version__ = "1.2"

# ============ USER SETTINGS ============
GITHUB_BASE_URL = "https://raw.githubusercontent.com/crameep/LegionScripts/main/"
GITHUB_API_URL = "https://api.github.com/repos/crameep/LegionScripts/contents/"
BACKUP_DIR = "_backups"
DOWNLOAD_TIMEOUT = 5  # seconds

# Scripts to manage - dynamically loaded from GitHub
MANAGED_SCRIPTS = []

# ============ CONSTANTS ============
# GUI colors
HUE_GREEN = 68      # OK/active
HUE_RED = 32        # Error/danger
HUE_YELLOW = 43     # Warning/update available
HUE_GRAY = 90       # Neutral/disabled
HUE_BLUE = 66       # Special

# Status indicators
STATUS_OK = "OK"
STATUS_UPDATE = "UPDATE"
STATUS_NEW = "NEW"
STATUS_NA = "N-A"
STATUS_ERROR = "ERROR"

# ============ PERSISTENCE KEYS ============
SETTINGS_KEY = "Updater_WindowXY"

# ============ STATE MACHINE ============
# States: IDLE, CHECKING, BACKING_UP, DOWNLOADING, WRITING, ERROR
STATE = "IDLE"
state_start_time = 0
current_script = ""
current_script_index = 0
scripts_to_update = []
download_data = ""
error_message = ""
status_message = "Ready"

# ============ RUNTIME STATE ============
script_data = {}  # Dict: {filename: {local_version, remote_version, status, selected, error}}
checking_all = False
backup_path = ""

# ============ UTILITY FUNCTIONS ============
def debug_msg(text):
    """Debug logging"""
    if False:  # Set to True for debugging
        API.SysMsg("DEBUG: " + text, 88)

def get_script_dir():
    """Get the directory where scripts are located"""
    try:
        # Try to get from current working directory or Legion script path
        return os.path.dirname(os.path.abspath(__file__))
    except:
        # Fallback - try relative path
        return "."

def ensure_backup_dir():
    """Create backup directory if it doesn't exist"""
    try:
        script_dir = get_script_dir()
        backup_full_path = os.path.join(script_dir, BACKUP_DIR)
        if not os.path.exists(backup_full_path):
            os.makedirs(backup_full_path)
            debug_msg("Created backup directory: " + backup_full_path)
        return backup_full_path
    except Exception as e:
        API.SysMsg("Error creating backup dir: " + str(e), HUE_RED)
        return None

def parse_version(script_path):
    """Parse __version__ from a script file. Returns version string or None."""
    try:
        with open(script_path, 'r') as f:
            content = f.read()
            # Regex: __version__ = "1.0" or __version__ = '1.0'
            match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)
    except:
        pass
    return None

def compare_versions(v1, v2):
    """
    Compare semantic versions. Returns:
    -1 if v1 < v2 (update available)
     0 if v1 == v2 (same)
     1 if v1 > v2 (local is newer)
    None if can't compare
    """
    if not v1 or not v2:
        return None

    try:
        # Parse "1.2.3" -> (1, 2, 3)
        def parse_tuple(v):
            parts = v.split('.')
            # Pad with zeros: "1.2" -> (1, 2, 0)
            while len(parts) < 3:
                parts.append('0')
            return tuple(int(p) for p in parts[:3])

        t1 = parse_tuple(v1)
        t2 = parse_tuple(v2)

        if t1 < t2:
            return -1
        elif t1 > t2:
            return 1
        else:
            return 0
    except:
        # Fallback to string comparison
        if v1 == v2:
            return 0
        return None

def get_local_version(filename):
    """Get version of local script file"""
    try:
        script_dir = get_script_dir()
        path = os.path.join(script_dir, filename)
        if os.path.exists(path):
            return parse_version(path)
    except:
        pass
    return None

def download_script(filename):
    """Download script content from GitHub. Returns (success, content_or_error)"""
    url = GITHUB_BASE_URL + filename
    try:
        debug_msg("Downloading: " + url)
        try:
            # Python 3 style
            req = urllib.request.Request(url)
            response = urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT)
            content = response.read().decode('utf-8')
        except:
            # Python 2 style fallback
            import urllib2
            req = urllib2.Request(url)
            response = urllib2.urlopen(req, timeout=DOWNLOAD_TIMEOUT)
            content = response.read()

        debug_msg("Downloaded " + str(len(content)) + " bytes")
        return (True, content)
    except Exception as e:
        error = str(e)
        debug_msg("Download error: " + error)
        return (False, error)

def get_remote_version(content):
    """Parse version from downloaded content"""
    try:
        match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            return match.group(1)
    except:
        pass
    return None

def backup_script(filename):
    """Create timestamped backup of script. Returns (success, backup_path_or_error)"""
    try:
        script_dir = get_script_dir()
        source_path = os.path.join(script_dir, filename)

        if not os.path.exists(source_path):
            return (False, "File not found: " + filename)

        backup_dir = ensure_backup_dir()
        if not backup_dir:
            return (False, "Could not create backup directory")

        # Generate backup filename: Script_v1.py -> Script_v1_20260121_143055.py
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        base_name = filename.replace(".py", "")
        backup_filename = base_name + "_" + timestamp + ".py"
        backup_path = os.path.join(backup_dir, backup_filename)

        # Copy file
        with open(source_path, 'r') as src:
            content = src.read()
        with open(backup_path, 'w') as dst:
            dst.write(content)

        debug_msg("Backed up to: " + backup_path)
        return (True, backup_path)
    except Exception as e:
        return (False, str(e))

def write_script(filename, content):
    """Write new content to script file. Returns (success, error_or_none)"""
    try:
        script_dir = get_script_dir()
        path = os.path.join(script_dir, filename)

        with open(path, 'w') as f:
            f.write(content)

        debug_msg("Wrote " + str(len(content)) + " bytes to " + filename)
        return (True, None)
    except Exception as e:
        return (False, str(e))

def list_backups(filename):
    """List all backup files for a given script. Returns list of (path, timestamp)"""
    try:
        script_dir = get_script_dir()
        backup_dir = os.path.join(script_dir, BACKUP_DIR)

        if not os.path.exists(backup_dir):
            return []

        base_name = filename.replace(".py", "")
        backups = []

        for f in os.listdir(backup_dir):
            if f.startswith(base_name + "_") and f.endswith(".py"):
                path = os.path.join(backup_dir, f)
                # Extract timestamp from filename
                try:
                    parts = f.replace(".py", "").split("_")
                    if len(parts) >= 3:
                        date_str = parts[-2]  # YYYYMMDD
                        time_str = parts[-1]  # HHMMSS
                        timestamp = date_str + "_" + time_str
                        backups.append((path, timestamp))
                except:
                    backups.append((path, "unknown"))

        # Sort by timestamp (newest first)
        backups.sort(key=lambda x: x[1], reverse=True)
        return backups
    except:
        return []

def restore_backup(backup_path, filename):
    """Restore a backup file. Returns (success, error_or_none)"""
    try:
        script_dir = get_script_dir()
        target_path = os.path.join(script_dir, filename)

        # Read backup
        with open(backup_path, 'r') as src:
            content = src.read()

        # Write to script
        with open(target_path, 'w') as dst:
            dst.write(content)

        debug_msg("Restored from: " + backup_path)
        return (True, None)
    except Exception as e:
        return (False, str(e))

def fetch_github_script_list():
    """Fetch list of .py files from GitHub repository. Returns list of filenames."""
    try:
        debug_msg("Fetching script list from GitHub API...")

        try:
            # Python 3 style
            import json
            req = urllib.request.Request(GITHUB_API_URL)
            response = urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT)
            data = response.read().decode('utf-8')
            files = json.loads(data)
        except:
            # Python 2 style fallback
            import urllib2
            import json
            req = urllib2.Request(GITHUB_API_URL)
            response = urllib2.urlopen(req, timeout=DOWNLOAD_TIMEOUT)
            data = response.read()
            files = json.loads(data)

        # Filter for .py files, exclude Script_Updater.py
        script_list = []
        for item in files:
            if item.get('type') == 'file' and item.get('name', '').endswith('.py'):
                filename = item['name']
                # Exclude the updater itself and any __init__.py files
                if filename != 'Script_Updater.py' and filename != '__init__.py':
                    script_list.append(filename)

        debug_msg("Found " + str(len(script_list)) + " scripts on GitHub")
        return script_list
    except Exception as e:
        debug_msg("Error fetching GitHub list: " + str(e))
        # Fallback to local discovery
        return discover_local_scripts()

def discover_local_scripts():
    """Discover .py files in local directory as fallback. Returns list of filenames."""
    try:
        script_dir = get_script_dir()
        script_list = []

        for filename in os.listdir(script_dir):
            if filename.endswith('.py') and filename != 'Script_Updater.py' and filename != '__init__.py':
                # Skip backup directory
                full_path = os.path.join(script_dir, filename)
                if os.path.isfile(full_path):
                    script_list.append(filename)

        debug_msg("Discovered " + str(len(script_list)) + " local scripts")
        return script_list
    except:
        return []

# ============ INITIALIZATION ============
def init_script_data():
    """Initialize script data structure"""
    global script_data, MANAGED_SCRIPTS

    # Fetch script list from GitHub
    API.SysMsg("Fetching script list from GitHub...", HUE_BLUE)
    MANAGED_SCRIPTS = fetch_github_script_list()

    if not MANAGED_SCRIPTS:
        API.SysMsg("No scripts found! Check network connection.", HUE_RED)
        return

    API.SysMsg("Found " + str(len(MANAGED_SCRIPTS)) + " scripts in repository", HUE_GREEN)

    for filename in MANAGED_SCRIPTS:
        script_data[filename] = {
            'local_version': None,
            'remote_version': None,
            'status': STATUS_NA,
            'selected': False,
            'error': None
        }
        # Get local version
        local_ver = get_local_version(filename)
        script_data[filename]['local_version'] = local_ver
        if local_ver:
            script_data[filename]['status'] = STATUS_OK

# ============ STATE MACHINE ACTIONS ============
def start_check_updates(selected_only=False):
    """Start checking for updates. Non-blocking."""
    global STATE, scripts_to_update, current_script_index, checking_all, status_message

    if STATE != "IDLE":
        API.SysMsg("Already busy!", HUE_RED)
        return

    # Build list of scripts to check
    scripts_to_update = []
    if selected_only:
        for filename in MANAGED_SCRIPTS:
            if script_data[filename]['selected']:
                scripts_to_update.append(filename)
        if not scripts_to_update:
            API.SysMsg("No scripts selected!", HUE_YELLOW)
            return
        checking_all = False
    else:
        scripts_to_update = list(MANAGED_SCRIPTS)
        checking_all = True

    current_script_index = 0
    STATE = "CHECKING"
    status_message = "Checking updates..."
    update_status_display()
    API.SysMsg("Checking " + str(len(scripts_to_update)) + " scripts...", HUE_BLUE)

def process_checking():
    """Process CHECKING state - check one script per cycle"""
    global STATE, current_script_index, status_message

    if current_script_index >= len(scripts_to_update):
        # Done checking all scripts
        STATE = "IDLE"
        status_message = "Check complete"
        update_status_display()
        update_script_list()

        # Count updates available
        update_count = sum(1 for data in script_data.values() if data['status'] == STATUS_UPDATE)
        if update_count > 0:
            API.SysMsg("Found " + str(update_count) + " updates!", HUE_YELLOW)
        else:
            API.SysMsg("All scripts up to date", HUE_GREEN)
        return

    # Check next script
    filename = scripts_to_update[current_script_index]
    status_message = "Checking " + filename + "..."
    update_status_display()

    # Download and check version
    success, content = download_script(filename)

    if success:
        remote_ver = get_remote_version(content)
        script_data[filename]['remote_version'] = remote_ver

        local_ver = script_data[filename]['local_version']

        if not local_ver:
            # Script doesn't exist locally
            script_data[filename]['status'] = STATUS_NEW
        elif not remote_ver:
            # Can't find remote version
            script_data[filename]['status'] = STATUS_NA
            script_data[filename]['error'] = "No version in remote file"
        else:
            # Compare versions
            cmp = compare_versions(local_ver, remote_ver)
            if cmp == -1:
                script_data[filename]['status'] = STATUS_UPDATE
                # Auto-select scripts that are installed and have updates
                script_data[filename]['selected'] = True
            elif cmp == 0:
                script_data[filename]['status'] = STATUS_OK
                # Auto-select scripts that are already installed
                script_data[filename]['selected'] = True
            else:
                script_data[filename]['status'] = STATUS_OK  # Local is newer
                # Auto-select scripts that are already installed
                script_data[filename]['selected'] = True

        script_data[filename]['error'] = None
    else:
        # Download failed
        script_data[filename]['status'] = STATUS_ERROR
        script_data[filename]['error'] = content  # Error message

    current_script_index += 1
    update_script_list()

def start_update_selected():
    """Start updating selected scripts"""
    global STATE, scripts_to_update, current_script_index, status_message

    if STATE != "IDLE":
        API.SysMsg("Already busy!", HUE_RED)
        return

    # Build list of selected scripts
    scripts_to_update = []
    for filename in MANAGED_SCRIPTS:
        if script_data[filename]['selected']:
            scripts_to_update.append(filename)

    if not scripts_to_update:
        API.SysMsg("No scripts selected!", HUE_YELLOW)
        return

    current_script_index = 0
    STATE = "BACKING_UP"
    status_message = "Starting update..."
    update_status_display()
    API.SysMsg("Updating " + str(len(scripts_to_update)) + " scripts...", HUE_BLUE)

def start_update_all():
    """Start updating all scripts that have updates available"""
    global STATE, scripts_to_update, current_script_index, status_message

    if STATE != "IDLE":
        API.SysMsg("Already busy!", HUE_RED)
        return

    # Build list of scripts with updates
    scripts_to_update = []
    for filename in MANAGED_SCRIPTS:
        if script_data[filename]['status'] in [STATUS_UPDATE, STATUS_NEW]:
            scripts_to_update.append(filename)

    if not scripts_to_update:
        API.SysMsg("No updates available!", HUE_YELLOW)
        return

    current_script_index = 0
    STATE = "BACKING_UP"
    status_message = "Starting update..."
    update_status_display()
    API.SysMsg("Updating " + str(len(scripts_to_update)) + " scripts...", HUE_BLUE)

def process_backing_up():
    """Process BACKING_UP state - backup one script"""
    global STATE, current_script, backup_path, status_message

    if current_script_index >= len(scripts_to_update):
        # Done with all updates
        STATE = "IDLE"
        status_message = "Update complete!"
        update_status_display()
        API.SysMsg("Update complete! " + str(len(scripts_to_update)) + " scripts updated", HUE_GREEN)
        return

    # Backup next script
    filename = scripts_to_update[current_script_index]
    current_script = filename
    status_message = "Backing up " + filename + "..."
    update_status_display()

    # Only backup if file exists locally
    if script_data[filename]['local_version']:
        success, result = backup_script(filename)
        if not success:
            # Backup failed - warn but continue
            API.SysMsg("Backup failed for " + filename + ": " + result, HUE_RED)

    # Move to downloading
    STATE = "DOWNLOADING"

def process_downloading():
    """Process DOWNLOADING state - download one script"""
    global STATE, download_data, status_message

    filename = current_script
    status_message = "Downloading " + filename + "..."
    update_status_display()

    success, content = download_script(filename)

    if success:
        download_data = content
        STATE = "WRITING"
    else:
        # Download failed
        script_data[filename]['status'] = STATUS_ERROR
        script_data[filename]['error'] = content
        API.SysMsg("Download failed: " + filename, HUE_RED)

        # Move to next script
        global current_script_index
        current_script_index += 1
        STATE = "BACKING_UP"
        update_script_list()

def process_writing():
    """Process WRITING state - write downloaded content to file"""
    global STATE, current_script_index, status_message

    filename = current_script
    status_message = "Writing " + filename + "..."
    update_status_display()

    success, error = write_script(filename, download_data)

    if success:
        # Update local version
        new_version = get_remote_version(download_data)
        script_data[filename]['local_version'] = new_version
        script_data[filename]['status'] = STATUS_OK
        script_data[filename]['error'] = None
        script_data[filename]['selected'] = False  # Deselect after update

        API.SysMsg("Updated: " + filename + " -> v" + (new_version or "?"), HUE_GREEN)
    else:
        # Write failed
        script_data[filename]['status'] = STATUS_ERROR
        script_data[filename]['error'] = error
        API.SysMsg("Write failed: " + filename, HUE_RED)

    # Move to next script
    current_script_index += 1
    STATE = "BACKING_UP"
    update_script_list()

def process_state_machine():
    """Main state machine processor - call frequently"""
    global STATE

    if STATE == "CHECKING":
        process_checking()
    elif STATE == "BACKING_UP":
        process_backing_up()
    elif STATE == "DOWNLOADING":
        process_downloading()
    elif STATE == "WRITING":
        process_writing()

# ============ GUI CALLBACKS ============
def on_check_updates():
    """Check all scripts for updates"""
    start_check_updates(selected_only=False)

def on_update_selected():
    """Update selected scripts"""
    start_update_selected()

def on_update_all():
    """Update all scripts with updates available"""
    start_update_all()

def on_restore_backup():
    """Restore a script from backup"""
    global STATE

    if STATE != "IDLE":
        API.SysMsg("Please wait until current operation finishes", HUE_YELLOW)
        return

    API.SysMsg("Select a script to restore (target it)...", HUE_BLUE)
    # Note: Restore functionality would require a file picker dialog
    # For now, just show message
    API.SysMsg("Restore feature: Use file manager to copy from _backups/", HUE_YELLOW)

def toggle_script_selection(index):
    """Toggle selection checkbox for a script"""
    if index < 0 or index >= len(MANAGED_SCRIPTS):
        return

    filename = MANAGED_SCRIPTS[index]
    script_data[filename]['selected'] = not script_data[filename]['selected']
    update_script_list()

def make_toggle_callback(index):
    """Create callback for toggling script selection"""
    def callback():
        toggle_script_selection(index)
    return callback

# ============ DISPLAY UPDATES ============
def update_status_display():
    """Update status bar"""
    statusLabel.SetText(status_message)

def update_script_list():
    """Update the script list display"""
    for i, filename in enumerate(MANAGED_SCRIPTS):
        if i >= len(script_rows):
            continue

        data = script_data[filename]
        local_ver = data['local_version'] or "---"
        remote_ver = data['remote_version'] or "---"
        status = data['status']
        selected = data['selected']

        # Build display text: [X] Script.py | v1.0 | v1.1 | UPDATE
        checkbox = "[X]" if selected else "[ ]"
        text = checkbox + " " + filename[:22].ljust(22) + " | " + local_ver[:6].ljust(6) + " | " + remote_ver[:6].ljust(6) + " | " + status

        # Update label
        script_rows[i]['label'].SetText(text)

        # Update color based on status
        if status == STATUS_OK:
            script_rows[i]['label'].SetBackgroundHue(HUE_GREEN)
        elif status == STATUS_UPDATE:
            script_rows[i]['label'].SetBackgroundHue(HUE_YELLOW)
        elif status == STATUS_NEW:
            script_rows[i]['label'].SetBackgroundHue(HUE_BLUE)
        elif status == STATUS_ERROR:
            script_rows[i]['label'].SetBackgroundHue(HUE_RED)
        else:  # N-A
            script_rows[i]['label'].SetBackgroundHue(HUE_GRAY)

# ============ CLEANUP ============
def cleanup():
    """Cleanup on exit"""
    pass

def onClosed():
    """GUI closed callback"""
    cleanup()
    # Save window position
    try:
        API.SavePersistentVar(SETTINGS_KEY, str(gump.GetX()) + "," + str(gump.GetY()), API.PersistentVar.Char)
    except:
        pass
    API.Stop()

# ============ INITIALIZATION ============
init_script_data()

# ============ BUILD GUI ============
gump = API.Gumps.CreateGump()
API.Gumps.AddControlOnDisposed(gump, onClosed)

# Load window position
savedPos = API.GetPersistentVar(SETTINGS_KEY, "100,100", API.PersistentVar.Char)
posXY = savedPos.split(',')
lastX = int(posXY[0])
lastY = int(posXY[1])

# Window size
win_width = 580
win_height = 450
gump.SetRect(lastX, lastY, win_width, win_height)

# Background
bg = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
bg.SetRect(0, 0, win_width, win_height)
gump.Add(bg)

# Title
title = API.Gumps.CreateGumpTTFLabel("Script Updater v" + __version__, 16, "#00d4ff", aligned="center", maxWidth=win_width)
title.SetPos(0, 5)
gump.Add(title)

# Instructions
instructions = API.Gumps.CreateGumpTTFLabel("Check scripts for updates from GitHub | Select and update | Backups in _backups/", 8, "#aaaaaa", aligned="center", maxWidth=win_width)
instructions.SetPos(0, 28)
gump.Add(instructions)

# Column headers
y = 48
header = API.Gumps.CreateGumpTTFLabel("[ ] Script Name          | Local  | Remote | Status", 9, "#ffaa00")
header.SetPos(10, y)
gump.Add(header)

# Script list (scrollable area)
y = 68
script_rows = []
row_height = 22

for i, filename in enumerate(MANAGED_SCRIPTS):
    # Clickable row
    btn = API.Gumps.CreateSimpleButton("[ ] " + filename, 560, row_height - 2)
    btn.SetPos(10, y + (i * row_height))
    btn.SetBackgroundHue(HUE_GRAY)
    API.Gumps.AddControlOnClick(btn, make_toggle_callback(i))
    gump.Add(btn)

    script_rows.append({
        'label': btn,
        'filename': filename
    })

# Bottom buttons
y = 68 + (len(MANAGED_SCRIPTS) * row_height) + 10

checkBtn = API.Gumps.CreateSimpleButton("[Check Updates]", 135, 25)
checkBtn.SetPos(10, y)
checkBtn.SetBackgroundHue(HUE_BLUE)
API.Gumps.AddControlOnClick(checkBtn, on_check_updates)
gump.Add(checkBtn)

updateSelectedBtn = API.Gumps.CreateSimpleButton("[Update Selected]", 135, 25)
updateSelectedBtn.SetPos(150, y)
updateSelectedBtn.SetBackgroundHue(HUE_YELLOW)
API.Gumps.AddControlOnClick(updateSelectedBtn, on_update_selected)
gump.Add(updateSelectedBtn)

updateAllBtn = API.Gumps.CreateSimpleButton("[Update All]", 135, 25)
updateAllBtn.SetPos(290, y)
updateAllBtn.SetBackgroundHue(HUE_GREEN)
API.Gumps.AddControlOnClick(updateAllBtn, on_update_all)
gump.Add(updateAllBtn)

restoreBtn = API.Gumps.CreateSimpleButton("[Restore Backup]", 135, 25)
restoreBtn.SetPos(430, y)
restoreBtn.SetBackgroundHue(HUE_GRAY)
API.Gumps.AddControlOnClick(restoreBtn, on_restore_backup)
gump.Add(restoreBtn)

# Status bar
y += 30
statusBg = API.Gumps.CreateGumpColorBox(0.9, "#000000")
statusBg.SetRect(5, y, win_width - 10, 25)
gump.Add(statusBg)

statusLabel = API.Gumps.CreateGumpTTFLabel("Ready", 10, "#00ff00")
statusLabel.SetPos(10, y + 4)
gump.Add(statusLabel)

API.Gumps.AddGump(gump)

# Initial display update
update_script_list()
API.SysMsg("Script Updater v" + __version__ + " loaded! Click [Check Updates] to start", HUE_GREEN)

# ============ MAIN LOOP (NON-BLOCKING) ============
DISPLAY_INTERVAL = 0.5
next_display = time.time() + DISPLAY_INTERVAL

while not API.StopRequested:
    try:
        # Process GUI clicks - always instant!
        API.ProcessCallbacks()

        # Process state machine
        process_state_machine()

        # Update display periodically
        if time.time() > next_display:
            update_status_display()
            next_display = time.time() + DISPLAY_INTERVAL

        # Short pause - loop runs ~10x/second
        API.Pause(0.1)

    except Exception as e:
        API.SysMsg("Error: " + str(e), HUE_RED)
        STATE = "IDLE"
        status_message = "Error: " + str(e)
        update_status_display()
        API.Pause(1)

cleanup()
