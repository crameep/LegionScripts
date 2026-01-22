# ============================================================
# Script Updater v2.1.1
# by Coryigon for TazUO Legion Scripts
# ============================================================
#
# Automatic script updater that downloads latest versions from GitHub.
# Non-blocking state machine keeps GUI responsive during downloads.
#
# Features:
#   - Collapsible folder hierarchy (Tamer/, Mage/, Dexer/, Utility/)
#   - Check for script updates from GitHub repository
#   - Compare local vs remote versions (semantic versioning)
#   - Backup scripts before updating (_backups directory)
#   - Restore previous versions from backup
#   - Scrollable list with checkboxes for selective updates
#   - Status indicators: NEW, OK, UPDATE, N-A, ERROR
#   - Network error handling with timeouts
#   - Auto-select installed scripts after version check
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

__version__ = "2.1.1"

# ============ USER SETTINGS ============
GITHUB_BASE_URL = "https://raw.githubusercontent.com/crameep/LegionScripts/main/CoryCustom/"
GITHUB_API_URL = "https://api.github.com/repos/crameep/LegionScripts/contents/CoryCustom/"
BACKUP_DIR = "_backups"
DOWNLOAD_TIMEOUT = 5  # seconds

# Directories to exclude from recursion
EXCLUDED_DIRS = ["__pycache__", ".git", ".github", "_backups", "Test"]

# Scripts to manage - dynamically loaded from GitHub
MANAGED_SCRIPTS = []  # List of (folder_name, relative_path) tuples

# ============ CONSTANTS ============
# GUI colors
HUE_GREEN = 68      # OK/active
HUE_RED = 32        # Error/danger
HUE_YELLOW = 43     # Warning/update available
HUE_GRAY = 90       # Neutral/disabled
HUE_BLUE = 66       # Special/folder

# Status indicators
STATUS_OK = "OK"
STATUS_UPDATE = "UPDATE"
STATUS_NEW = "NEW"
STATUS_NA = "N-A"
STATUS_ERROR = "ERROR"

# ============ PERSISTENCE KEYS ============
SETTINGS_KEY = "Updater_WindowXY"
FOLDER_STATE_KEY = "Updater_FolderState"

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
script_data = {}  # Dict: {relative_path: {local_version, remote_version, status, selected, error, folder}}
folder_data = {}  # Dict: {folder_name: {expanded: bool, script_count: int, update_count: int}}
checking_all = False
backup_path = ""
updater_was_updated = False  # Track if Script_Updater.py was updated (needs restart)

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

def get_local_version(relative_path):
    """Get version of local script file"""
    try:
        script_dir = get_script_dir()
        path = os.path.join(script_dir, relative_path)
        if os.path.exists(path):
            return parse_version(path)
    except:
        pass
    return None

def download_script(relative_path):
    """Download script content from GitHub. Returns (success, content_or_error)"""
    url = GITHUB_BASE_URL + relative_path
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

def backup_script(relative_path):
    """Create timestamped backup of script. Returns (success, backup_path_or_error)"""
    try:
        script_dir = get_script_dir()
        source_path = os.path.join(script_dir, relative_path)

        if not os.path.exists(source_path):
            return (False, "File not found: " + relative_path)

        backup_dir = ensure_backup_dir()
        if not backup_dir:
            return (False, "Could not create backup directory")

        # Generate backup filename: Tamer/Script.py -> Script_20260122_143055.py
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = os.path.basename(relative_path)
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

def write_script(relative_path, content):
    """Write new content to script file. Returns (success, error_or_none)"""
    try:
        script_dir = get_script_dir()
        path = os.path.join(script_dir, relative_path)

        # Ensure directory exists
        dir_path = os.path.dirname(path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path)

        with open(path, 'w') as f:
            f.write(content)

        debug_msg("Wrote " + str(len(content)) + " bytes to " + relative_path)
        return (True, None)
    except Exception as e:
        return (False, str(e))

def fetch_github_script_list():
    """Recursively fetch .py files from GitHub repository. Returns list of (folder_name, relative_path) tuples."""
    try:
        debug_msg("Fetching script list from GitHub API...")

        script_list = []

        def fetch_directory(api_url, path_prefix=""):
            """Recursively fetch contents from a directory"""
            try:
                # Python 3 style
                import json
                req = urllib.request.Request(api_url)
                response = urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT)
                data = response.read().decode('utf-8')
                items = json.loads(data)
            except:
                # Python 2 style fallback
                import urllib2
                import json
                req = urllib2.Request(api_url)
                response = urllib2.urlopen(req, timeout=DOWNLOAD_TIMEOUT)
                data = response.read()
                items = json.loads(data)

            for item in items:
                item_name = item.get('name', '')
                item_type = item.get('type', '')

                if item_type == 'file' and item_name.endswith('.py'):
                    # Skip __init__.py files
                    if item_name != '__init__.py':
                        relative_path = path_prefix + item_name if path_prefix else item_name
                        folder_name = path_prefix.rstrip('/') if path_prefix else "_root"
                        script_list.append((folder_name, relative_path))

                elif item_type == 'dir' and item_name not in EXCLUDED_DIRS:
                    # Recursively fetch from subdirectory
                    sub_url = item.get('url', '')
                    if sub_url:
                        sub_path_prefix = path_prefix + item_name + "/"
                        fetch_directory(sub_url, sub_path_prefix)

        # Start fetching from root
        fetch_directory(GITHUB_API_URL)

        debug_msg("Found " + str(len(script_list)) + " scripts on GitHub")
        return script_list
    except Exception as e:
        debug_msg("Error fetching GitHub list: " + str(e))
        # Fallback to local discovery
        return discover_local_scripts()

def discover_local_scripts():
    """Discover .py files in local directory as fallback. Returns list of (folder_name, relative_path) tuples."""
    try:
        script_dir = get_script_dir()
        script_list = []

        def scan_directory(dir_path, path_prefix=""):
            """Recursively scan directory"""
            try:
                for item_name in os.listdir(dir_path):
                    item_path = os.path.join(dir_path, item_name)

                    if os.path.isfile(item_path) and item_name.endswith('.py') and item_name != '__init__.py':
                        relative_path = path_prefix + item_name if path_prefix else item_name
                        folder_name = path_prefix.rstrip('/') if path_prefix else "_root"
                        script_list.append((folder_name, relative_path))

                    elif os.path.isdir(item_path) and item_name not in EXCLUDED_DIRS:
                        sub_path_prefix = path_prefix + item_name + "/"
                        scan_directory(item_path, sub_path_prefix)
            except:
                pass

        scan_directory(script_dir)
        debug_msg("Discovered " + str(len(script_list)) + " local scripts")
        return script_list
    except:
        return []

# ============ FOLDER MANAGEMENT ============
def load_folder_state():
    """Load folder expanded/collapsed state from persistent storage"""
    global folder_data
    try:
        saved_state = API.GetPersistentVar(FOLDER_STATE_KEY, "", API.PersistentVar.Char)
        if saved_state:
            # Format: "Tamer:1|Mage:0|Dexer:1"
            for pair in saved_state.split('|'):
                if ':' in pair:
                    folder_name, expanded = pair.split(':')
                    if folder_name in folder_data:
                        folder_data[folder_name]['expanded'] = (expanded == '1')
    except:
        pass

def save_folder_state():
    """Save folder expanded/collapsed state to persistent storage"""
    try:
        state_parts = []
        for folder_name, data in folder_data.items():
            expanded = '1' if data['expanded'] else '0'
            state_parts.append(folder_name + ':' + expanded)
        state_str = '|'.join(state_parts)
        API.SavePersistentVar(FOLDER_STATE_KEY, state_str, API.PersistentVar.Char)
    except:
        pass

def toggle_folder(folder_name):
    """Toggle folder expanded/collapsed state"""
    if folder_name in folder_data:
        folder_data[folder_name]['expanded'] = not folder_data[folder_name]['expanded']
        save_folder_state()
        update_script_list()

def make_folder_toggle_callback(folder_name):
    """Create callback for toggling folder"""
    def callback():
        toggle_folder(folder_name)
    return callback

# ============ INITIALIZATION ============
def init_script_data():
    """Initialize script data structure"""
    global script_data, MANAGED_SCRIPTS, folder_data

    # Fetch script list from GitHub
    API.SysMsg("Fetching script list from GitHub...", HUE_BLUE)
    MANAGED_SCRIPTS = fetch_github_script_list()

    if not MANAGED_SCRIPTS:
        API.SysMsg("No scripts found! Check network connection.", HUE_RED)
        return

    API.SysMsg("Found " + str(len(MANAGED_SCRIPTS)) + " scripts in repository", HUE_GREEN)

    # Initialize script data and folder data
    for folder_name, relative_path in MANAGED_SCRIPTS:
        script_data[relative_path] = {
            'local_version': None,
            'remote_version': None,
            'status': STATUS_NA,
            'selected': False,
            'error': None,
            'folder': folder_name
        }

        # Get local version
        local_ver = get_local_version(relative_path)
        script_data[relative_path]['local_version'] = local_ver
        if local_ver:
            script_data[relative_path]['status'] = STATUS_OK

        # Initialize folder data
        if folder_name not in folder_data:
            folder_data[folder_name] = {
                'expanded': True,  # Default to expanded
                'script_count': 0,
                'update_count': 0
            }
        folder_data[folder_name]['script_count'] += 1

    # Load saved folder state
    load_folder_state()

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
        for folder_name, relative_path in MANAGED_SCRIPTS:
            if script_data[relative_path]['selected']:
                scripts_to_update.append(relative_path)
        if not scripts_to_update:
            API.SysMsg("No scripts selected!", HUE_YELLOW)
            return
        checking_all = False
    else:
        scripts_to_update = [relative_path for folder_name, relative_path in MANAGED_SCRIPTS]
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

        # Update folder counts
        update_folder_counts()
        update_script_list()

        # Count updates available
        update_count = sum(1 for data in script_data.values() if data['status'] == STATUS_UPDATE)
        if update_count > 0:
            API.SysMsg("Found " + str(update_count) + " updates!", HUE_YELLOW)
        else:
            API.SysMsg("All scripts up to date", HUE_GREEN)
        return

    # Check next script
    relative_path = scripts_to_update[current_script_index]
    filename = os.path.basename(relative_path)
    status_message = "Checking " + filename + "..."
    update_status_display()

    # Download and check version
    success, content = download_script(relative_path)

    if success:
        remote_ver = get_remote_version(content)
        script_data[relative_path]['remote_version'] = remote_ver

        local_ver = script_data[relative_path]['local_version']

        if not local_ver:
            # Script doesn't exist locally
            script_data[relative_path]['status'] = STATUS_NEW
        elif not remote_ver:
            # Can't find remote version
            script_data[relative_path]['status'] = STATUS_NA
            script_data[relative_path]['error'] = "No version in remote file"
        else:
            # Compare versions
            cmp = compare_versions(local_ver, remote_ver)
            if cmp == -1:
                script_data[relative_path]['status'] = STATUS_UPDATE
                # Auto-select scripts that are installed and have updates
                script_data[relative_path]['selected'] = True
            elif cmp == 0:
                script_data[relative_path]['status'] = STATUS_OK
                # Auto-select scripts that are already installed
                script_data[relative_path]['selected'] = True
            else:
                script_data[relative_path]['status'] = STATUS_OK  # Local is newer
                # Auto-select scripts that are already installed
                script_data[relative_path]['selected'] = True

        script_data[relative_path]['error'] = None
    else:
        # Download failed
        script_data[relative_path]['status'] = STATUS_ERROR
        script_data[relative_path]['error'] = content  # Error message

    current_script_index += 1

def update_folder_counts():
    """Update folder update counts"""
    for folder_name in folder_data:
        folder_data[folder_name]['update_count'] = 0

    for relative_path, data in script_data.items():
        folder_name = data['folder']
        if data['status'] == STATUS_UPDATE:
            folder_data[folder_name]['update_count'] += 1

def start_update_selected():
    """Start updating selected scripts"""
    global STATE, scripts_to_update, current_script_index, status_message

    if STATE != "IDLE":
        API.SysMsg("Already busy!", HUE_RED)
        return

    # Build list of selected scripts
    scripts_to_update = []
    for folder_name, relative_path in MANAGED_SCRIPTS:
        if script_data[relative_path]['selected']:
            scripts_to_update.append(relative_path)

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
    for folder_name, relative_path in MANAGED_SCRIPTS:
        if script_data[relative_path]['status'] in [STATUS_UPDATE, STATUS_NEW]:
            scripts_to_update.append(relative_path)

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
    global STATE, current_script, backup_path, status_message, updater_was_updated

    if current_script_index >= len(scripts_to_update):
        # Done with all updates
        STATE = "IDLE"
        status_message = "Update complete!"
        update_status_display()
        update_folder_counts()
        update_script_list()
        API.SysMsg("Update complete! " + str(len(scripts_to_update)) + " scripts updated", HUE_GREEN)

        # Remind user if updater was updated
        if updater_was_updated:
            API.SysMsg("", HUE_GREEN)
            API.SysMsg("REMINDER: Restart Script_Updater.py to use new version!", HUE_YELLOW)

        return

    # Backup next script
    relative_path = scripts_to_update[current_script_index]
    current_script = relative_path
    filename = os.path.basename(relative_path)
    status_message = "Backing up " + filename + "..."
    update_status_display()

    # Only backup if file exists locally
    if script_data[relative_path]['local_version']:
        success, result = backup_script(relative_path)
        if not success:
            # Backup failed - warn but continue
            API.SysMsg("Backup failed for " + filename + ": " + result, HUE_RED)

    # Move to downloading
    STATE = "DOWNLOADING"

def process_downloading():
    """Process DOWNLOADING state - download one script"""
    global STATE, download_data, status_message

    relative_path = current_script
    filename = os.path.basename(relative_path)
    status_message = "Downloading " + filename + "..."
    update_status_display()

    success, content = download_script(relative_path)

    if success:
        download_data = content
        STATE = "WRITING"
    else:
        # Download failed
        script_data[relative_path]['status'] = STATUS_ERROR
        script_data[relative_path]['error'] = content
        API.SysMsg("Download failed: " + filename, HUE_RED)

        # Move to next script
        global current_script_index
        current_script_index += 1
        STATE = "BACKING_UP"
        update_script_list()

def process_writing():
    """Process WRITING state - write downloaded content to file"""
    global STATE, current_script_index, status_message, updater_was_updated

    relative_path = current_script
    filename = os.path.basename(relative_path)
    status_message = "Writing " + filename + "..."
    update_status_display()

    success, error = write_script(relative_path, download_data)

    if success:
        # Update local version
        new_version = get_remote_version(download_data)
        script_data[relative_path]['local_version'] = new_version
        script_data[relative_path]['status'] = STATUS_OK
        script_data[relative_path]['error'] = None
        script_data[relative_path]['selected'] = False  # Deselect after update

        API.SysMsg("Updated: " + filename + " -> v" + (new_version or "?"), HUE_GREEN)

        # Special handling for self-update
        if filename == "Script_Updater.py":
            updater_was_updated = True
            API.SysMsg("", HUE_GREEN)
            API.SysMsg("=== UPDATER SELF-UPDATE COMPLETE ===", HUE_YELLOW)
            API.SysMsg("Please RESTART this script for changes to take effect!", HUE_YELLOW)
            API.SysMsg("Close and reopen Script_Updater.py", HUE_YELLOW)
    else:
        # Write failed
        script_data[relative_path]['status'] = STATUS_ERROR
        script_data[relative_path]['error'] = error
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

def toggle_script_selection(relative_path):
    """Toggle selection checkbox for a script"""
    if relative_path in script_data:
        script_data[relative_path]['selected'] = not script_data[relative_path]['selected']
        update_script_list()

def make_toggle_callback(relative_path):
    """Create callback for toggling script selection"""
    def callback():
        toggle_script_selection(relative_path)
    return callback

# ============ DISPLAY UPDATES ============
def update_status_display():
    """Update status bar"""
    statusLabel.SetText(status_message)

def build_display_list():
    """Build list of items to display (folders + scripts)"""
    display_list = []

    # Sort folders alphabetically (_root at the end)
    sorted_folders = sorted(folder_data.keys(), key=lambda x: ('~' if x == '_root' else x))

    for folder_name in sorted_folders:
        folder_info = folder_data[folder_name]

        # Add folder row
        display_list.append(('folder', folder_name))

        # Add scripts if folder is expanded
        if folder_info['expanded']:
            folder_scripts = []
            for folder, relative_path in MANAGED_SCRIPTS:
                if folder == folder_name:
                    folder_scripts.append(relative_path)

            # Sort scripts alphabetically
            folder_scripts.sort()

            for relative_path in folder_scripts:
                display_list.append(('script', relative_path))

    return display_list

def update_script_list():
    """Update the script list display"""
    display_list = build_display_list()

    for i in range(len(script_rows)):
        btn = script_rows[i]['btn']

        if i < len(display_list):
            item_type, item_value = display_list[i]

            if item_type == 'folder':
                # Render folder row
                folder_name = item_value
                folder_info = folder_data[folder_name]
                expand_icon = "v" if folder_info['expanded'] else ">"
                display_name = "Other" if folder_name == "_root" else folder_name

                update_text = ""
                if folder_info['update_count'] > 0:
                    update_text = " - " + str(folder_info['update_count']) + " update"
                    if folder_info['update_count'] > 1:
                        update_text += "s"

                text = expand_icon + " " + display_name + " (" + str(folder_info['script_count']) + " scripts)" + update_text

                # Color
                if folder_info['update_count'] > 0:
                    color = HUE_YELLOW
                else:
                    color = HUE_BLUE

                btn.SetBackgroundHue(color)
                btn.SetText(text)

                # Update callback
                script_rows[i]['callback'] = make_folder_toggle_callback(folder_name)

            else:  # script
                # Render script row
                relative_path = item_value
                data = script_data[relative_path]
                filename = os.path.basename(relative_path)

                local_ver = data['local_version'] or "---"
                remote_ver = data['remote_version'] or "---"
                status = data['status']
                selected = data['selected']

                # Determine color
                if status == STATUS_OK:
                    color = HUE_GREEN
                elif status == STATUS_UPDATE:
                    color = HUE_YELLOW
                elif status == STATUS_NEW:
                    color = HUE_BLUE
                elif status == STATUS_ERROR:
                    color = HUE_RED
                else:  # N-A
                    color = HUE_GRAY

                # Build display text: [X]  Script.py | v1.0 | v1.1 | UPDATE
                checkbox = "[X]" if selected else "[ ]"
                text = checkbox + "  " + filename[:20].ljust(20) + " | " + local_ver[:6].ljust(6) + " | " + remote_ver[:6].ljust(6) + " | " + status

                # Update button - set color first, then text
                btn.SetBackgroundHue(color)
                btn.SetText(text)

                # Update callback
                script_rows[i]['callback'] = make_toggle_callback(relative_path)
        else:
            # Clear unused rows - set to empty text with neutral gray background
            btn.SetBackgroundHue(HUE_GRAY)
            btn.SetText("")
            script_rows[i]['callback'] = None

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
win_width = 600
win_height = 500
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
max_rows = 15

# Create row pool
for i in range(max_rows):
    btn = API.Gumps.CreateSimpleButton("", 580, row_height - 2)
    btn.SetPos(10, y + (i * row_height))
    btn.SetBackgroundHue(HUE_GRAY)
    gump.Add(btn)

    script_rows.append({
        'btn': btn,
        'callback': None
    })

# Setup click callbacks
def make_row_click_handler(row_index):
    """Create click handler that calls the current callback for this row"""
    def handler():
        if script_rows[row_index]['callback']:
            script_rows[row_index]['callback']()
    return handler

for i in range(len(script_rows)):
    API.Gumps.AddControlOnClick(script_rows[i]['btn'], make_row_click_handler(i))

# Bottom buttons
y = 68 + (max_rows * row_height) + 10

checkBtn = API.Gumps.CreateSimpleButton("[Check Updates]", 140, 25)
checkBtn.SetPos(10, y)
checkBtn.SetBackgroundHue(HUE_BLUE)
API.Gumps.AddControlOnClick(checkBtn, on_check_updates)
gump.Add(checkBtn)

updateSelectedBtn = API.Gumps.CreateSimpleButton("[Update Selected]", 140, 25)
updateSelectedBtn.SetPos(155, y)
updateSelectedBtn.SetBackgroundHue(HUE_YELLOW)
API.Gumps.AddControlOnClick(updateSelectedBtn, on_update_selected)
gump.Add(updateSelectedBtn)

updateAllBtn = API.Gumps.CreateSimpleButton("[Update All]", 140, 25)
updateAllBtn.SetPos(300, y)
updateAllBtn.SetBackgroundHue(HUE_GREEN)
API.Gumps.AddControlOnClick(updateAllBtn, on_update_all)
gump.Add(updateAllBtn)

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
