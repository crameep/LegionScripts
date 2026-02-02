# ============================================================
# Script Updater v1.8.1
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
#   - Auto-cleanup old backups (keeps last 5 per script)
#   - Restore previous versions from backup
#   - Scrollable list with checkboxes for selective updates
#   - Category indicators: [Tamer], [Mage], [Dexer], [Utility]
#   - Status indicators: NEW, OK, UPDATE, N-A, ERROR
#   - Network error handling with timeouts
#   - Warning if script might be running
#
# ============================================================
import API
import time
import re
import os
from datetime import datetime
try:
    import urllib.request
except ImportError:
    import urllib2 as urllib_request  # Fallback for older Python

__version__ = "1.9.0"

# ============ USER SETTINGS ============
GITHUB_BASE_URL = "https://raw.githubusercontent.com/crameep/LegionScripts/main/"
GITHUB_API_URL = "https://api.github.com/repos/crameep/LegionScripts/contents/"
BACKUP_DATE = datetime.now().strftime("%Y-%m-%d")
BACKUP_DIR = os.path.join("_support", "archive", "backups_" + BACKUP_DATE)
DOWNLOAD_TIMEOUT = 5  # seconds
MAX_BACKUPS_PER_SCRIPT = 5  # Keep only this many backups per script (auto-cleanup old ones)

# Directories to exclude from recursion (Test excluded conditionally via show_test_scripts toggle)
EXCLUDED_DIRS_BASE = ["__pycache__", ".git", ".github", "_support", ".claude"]

# Scripts to manage - dynamically loaded from GitHub
MANAGED_SCRIPTS = []  # List of (category, relative_path) tuples

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
SHOW_TEST_KEY = "Updater_ShowTest"

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
script_data = {}  # Dict: {relative_path: {local_version, remote_version, status, selected, error, category}}
checking_all = False
backup_path = ""
updater_was_updated = False  # Track if Script_Updater.py was updated (needs restart)
last_known_x = 100
last_known_y = 100
last_position_check = 0
show_test_scripts = False  # Toggle to show/hide Test folder scripts

# ============ UTILITY FUNCTIONS ============
def debug_msg(text):
    """Debug logging"""
    if False:  # Set to True for debugging

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
        # Explicitly use UTF-8 encoding to handle any encoding issues
        with open(script_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Regex: __version__ = "1.0" or __version__ = '1.0'
            match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                version = match.group(1)
                return version
            else:
                # Show first 500 chars to diagnose
                preview = content[:500].replace('\n', '\\n').replace('\r', '\\r')
    except Exception as e:
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
            file_size = os.path.getsize(path)
            version = parse_version(path)
            return version
    except Exception as e:
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

        if len(content) < 100:
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

        # Clean up old backups
        cleanup_old_backups(filename)

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

        # Write with explicit UTF-8 encoding and Unix line endings (newline='\n')
        # This prevents Windows from converting LF to CRLF which can cause parsing issues
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(content)

        # Verify file was written
        if os.path.exists(path):
            file_size = os.path.getsize(path)

            # Verify it can be parsed
            try:
                test_version = parse_version(path)
                if test_version:
                else:
            except:
                pass
        else:

        debug_msg("Wrote " + str(len(content)) + " bytes to " + relative_path)
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

def cleanup_old_backups(filename):
    """Delete old backups, keeping only the most recent MAX_BACKUPS_PER_SCRIPT"""
    try:
        backups = list_backups(filename)

        if len(backups) <= MAX_BACKUPS_PER_SCRIPT:
            return  # Nothing to clean up

        # Delete backups beyond the limit
        backups_to_delete = backups[MAX_BACKUPS_PER_SCRIPT:]
        deleted_count = 0

        for backup_path, timestamp in backups_to_delete:
            try:
                os.remove(backup_path)
                deleted_count += 1
                debug_msg("Deleted old backup: " + os.path.basename(backup_path))
            except Exception as e:
                debug_msg("Failed to delete backup: " + str(e))

        if deleted_count > 0:
            debug_msg("Cleaned up " + str(deleted_count) + " old backups for " + filename)
    except Exception as e:
        debug_msg("Error during backup cleanup: " + str(e))

def cleanup_all_backups():
    """Clean up all existing backups on startup, keeping only MAX_BACKUPS_PER_SCRIPT per script"""
    try:
        script_dir = get_script_dir()
        backup_dir = os.path.join(script_dir, BACKUP_DIR)

        if not os.path.exists(backup_dir):
            return  # No backups to clean

        # Group backups by script name
        script_backups = {}  # {script_name: [(path, timestamp), ...]}

        for backup_file in os.listdir(backup_dir):
            if not backup_file.endswith('.py'):
                continue

            # Extract base script name from filename like "Script_20260122_143055.py"
            # Split by underscore and find where the date pattern starts
            parts = backup_file.replace('.py', '').split('_')

            # Find the script name (everything before the date pattern YYYYMMDD)
            script_name = None
            for i in range(len(parts)):
                # Check if this part looks like a date (8 digits)
                if len(parts[i]) == 8 and parts[i].isdigit():
                    # Script name is everything before this index
                    script_name = '_'.join(parts[:i]) + '.py'
                    break

            if not script_name:
                continue

            # Get timestamp from filename
            try:
                if len(parts) >= 2:
                    date_str = parts[-2]  # YYYYMMDD
                    time_str = parts[-1]  # HHMMSS
                    timestamp = date_str + "_" + time_str
                else:
                    timestamp = "unknown"
            except:
                timestamp = "unknown"

            backup_path = os.path.join(backup_dir, backup_file)

            if script_name not in script_backups:
                script_backups[script_name] = []
            script_backups[script_name].append((backup_path, timestamp))

        # Clean up each script's backups
        total_deleted = 0
        for script_name, backups in script_backups.items():
            if len(backups) <= MAX_BACKUPS_PER_SCRIPT:
                continue

            # Sort by timestamp (newest first)
            backups.sort(key=lambda x: x[1], reverse=True)

            # Delete old backups
            backups_to_delete = backups[MAX_BACKUPS_PER_SCRIPT:]
            for backup_path, timestamp in backups_to_delete:
                try:
                    os.remove(backup_path)
                    total_deleted += 1
                    debug_msg("Deleted old backup: " + os.path.basename(backup_path))
                except Exception as e:
                    debug_msg("Failed to delete backup: " + str(e))

        if total_deleted > 0:
            API.SysMsg("Cleaned up " + str(total_deleted) + " old backups (keeping " + str(MAX_BACKUPS_PER_SCRIPT) + " per script)", HUE_GREEN)
            debug_msg("Backup cleanup complete: " + str(total_deleted) + " files deleted")

    except Exception as e:
        debug_msg("Error during all-backups cleanup: " + str(e))

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
    """Recursively fetch .py files from GitHub repository. Returns list of (category, relative_path) tuples."""
    try:
        debug_msg("Fetching script list from GitHub API...")

        script_list = []

        # Build exclusion list based on show_test_scripts toggle
        excluded_dirs = list(EXCLUDED_DIRS_BASE)
        if not show_test_scripts:
            excluded_dirs.append("Test")

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
                        category = path_prefix.rstrip('/') if path_prefix else ""
                        script_list.append((category, relative_path))

                elif item_type == 'dir' and item_name not in excluded_dirs:
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
    """Discover .py files in local directory as fallback. Returns list of (category, relative_path) tuples."""
    try:
        script_dir = get_script_dir()
        script_list = []

        # Build exclusion list based on show_test_scripts toggle
        excluded_dirs = list(EXCLUDED_DIRS_BASE)
        if not show_test_scripts:
            excluded_dirs.append("Test")

        def scan_directory(dir_path, path_prefix=""):
            """Recursively scan directory"""
            try:
                for item_name in os.listdir(dir_path):
                    item_path = os.path.join(dir_path, item_name)

                    if os.path.isfile(item_path) and item_name.endswith('.py') and item_name != '__init__.py':
                        relative_path = path_prefix + item_name if path_prefix else item_name
                        category = path_prefix.rstrip('/') if path_prefix else ""
                        script_list.append((category, relative_path))

                    elif os.path.isdir(item_path) and item_name not in excluded_dirs:
                        sub_path_prefix = path_prefix + item_name + "/"
                        scan_directory(item_path, sub_path_prefix)
            except:
                pass

        scan_directory(script_dir)
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

    for category, relative_path in MANAGED_SCRIPTS:
        script_data[relative_path] = {
            'local_version': None,
            'remote_version': None,
            'status': STATUS_NA,
            'selected': False,
            'error': None,
            'category': category
        }
        # Get local version
        local_ver = get_local_version(relative_path)
        script_data[relative_path]['local_version'] = local_ver
        if local_ver:
            script_data[relative_path]['status'] = STATUS_OK
            # Don't auto-select on initialization - user will check for updates first
            script_data[relative_path]['selected'] = False

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
        for category, relative_path in MANAGED_SCRIPTS:
            if script_data[relative_path]['selected']:
                scripts_to_update.append(relative_path)
        if not scripts_to_update:
            API.SysMsg("No scripts selected!", HUE_YELLOW)
            return
        checking_all = False
    else:
        scripts_to_update = [relative_path for category, relative_path in MANAGED_SCRIPTS]
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
            # Auto-select new scripts
            script_data[relative_path]['selected'] = True
        elif not remote_ver:
            # Can't find remote version
            script_data[relative_path]['status'] = STATUS_NA
            script_data[relative_path]['error'] = "No version in remote file"
        else:
            # Compare versions
            cmp = compare_versions(local_ver, remote_ver)
            if cmp == -1:
                script_data[relative_path]['status'] = STATUS_UPDATE
                # Auto-select scripts that have updates available
                script_data[relative_path]['selected'] = True
            elif cmp == 0:
                script_data[relative_path]['status'] = STATUS_OK
                # Don't auto-select scripts that are already up-to-date
                script_data[relative_path]['selected'] = False
            else:
                script_data[relative_path]['status'] = STATUS_OK  # Local is newer
                # Don't auto-select scripts that are already up-to-date
                script_data[relative_path]['selected'] = False

        script_data[relative_path]['error'] = None
    else:
        # Download failed
        script_data[relative_path]['status'] = STATUS_ERROR
        script_data[relative_path]['error'] = content  # Error message

    current_script_index += 1
    # Don't update GUI every script - wait until all checking is done
    # update_script_list()

def start_update_selected():
    """Start updating selected scripts"""
    global STATE, scripts_to_update, current_script_index, status_message

    if STATE != "IDLE":
        API.SysMsg("Already busy!", HUE_RED)
        return

    # Build list of selected scripts
    scripts_to_update = []
    for category, relative_path in MANAGED_SCRIPTS:
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
    for category, relative_path in MANAGED_SCRIPTS:
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

def toggle_show_test():
    """Toggle showing Test folder scripts"""
    global show_test_scripts

    if STATE != "IDLE":
        API.SysMsg("Please wait until current operation finishes", HUE_YELLOW)
        return

    show_test_scripts = not show_test_scripts
    API.SavePersistentVar(SHOW_TEST_KEY, str(show_test_scripts), API.PersistentVar.Char)

    # Update button
    color = HUE_BLUE if show_test_scripts else HUE_GRAY
    text = "[SHOW TEST:" + ("ON" if show_test_scripts else "OFF") + "]"
    showTestBtn.SetBackgroundHue(color)
    showTestBtn.SetText(text)

    API.SysMsg("Test scripts: " + ("SHOWN" if show_test_scripts else "HIDDEN"), color)
    API.SysMsg("Please RESTART Script_Updater to reload the script list", HUE_YELLOW)

def toggle_script_selection(index):
    """Toggle selection checkbox for a script"""
    if index < 0 or index >= len(MANAGED_SCRIPTS):
        return

    category, relative_path = MANAGED_SCRIPTS[index]
    script_data[relative_path]['selected'] = not script_data[relative_path]['selected']
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
    for i, (category, relative_path) in enumerate(MANAGED_SCRIPTS):
        if i >= len(script_rows):
            continue

        data = script_data[relative_path]
        filename = os.path.basename(relative_path)
        local_ver = data['local_version'] or "---"
        remote_ver = data['remote_version'] or "---"
        status = data['status']
        selected = data['selected']

        # Determine color first
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

        # Build display text with category: [X] [Tamer] Script.py | v1.0 | v1.1 | UPDATE
        checkbox = "[X]" if selected else "[ ]"

        # Format category indicator
        if category:
            cat_display = "[" + category + "]"
        else:
            cat_display = ""

        # Combine: checkbox + category + filename with appropriate spacing
        name_part = (cat_display + " " + filename)[:30].ljust(30) if cat_display else filename[:30].ljust(30)
        text = checkbox + " " + name_part + " | " + local_ver[:6].ljust(6) + " | " + remote_ver[:6].ljust(6) + " | " + status

        # Update button - set color first, then text to force redraw
        btn = script_rows[i]['label']
        btn.SetBackgroundHue(color)
        btn.SetText(text)

# ============ CLEANUP ============
def cleanup():
    """Cleanup on exit"""
    pass

def onClosed():
    """GUI closed callback"""
    cleanup()
    # Save window position using last known position
    try:
        # Validate coordinates
        if last_known_x >= 0 and last_known_y >= 0:
            pos = str(last_known_x) + "," + str(last_known_y)
            API.SavePersistentVar(SETTINGS_KEY, pos, API.PersistentVar.Char)
    except:
        pass
    API.Stop()

# ============ INITIALIZATION ============
# Load show_test_scripts setting before initializing script data
show_test_scripts = API.GetPersistentVar(SHOW_TEST_KEY, "False", API.PersistentVar.Char) == "True"

init_script_data()

# Clean up old backups on startup
cleanup_all_backups()

# ============ BUILD GUI ============
try:
    gump = API.Gumps.CreateGump()
    API.Gumps.AddControlOnDisposed(gump, onClosed)

    # Load window position
    savedPos = API.GetPersistentVar(SETTINGS_KEY, "100,100", API.PersistentVar.Char)
    posXY = savedPos.split(',')
    lastX = int(posXY[0])
    lastY = int(posXY[1])

    # Initialize last known position with loaded values
    last_known_x = lastX
    last_known_y = lastY

    # Window size - dynamic height based on script count
    win_width = 580
    # Calculate height: header(68) + rows(22 each) + buttons(28+28) + status(25) + padding(20)
    min_height = 450
    script_count = len(MANAGED_SCRIPTS) if MANAGED_SCRIPTS else 0
    calculated_height = 68 + (script_count * 22) + 28 + 28 + 25 + 20
    max_height = 700  # Don't make window too tall
    win_height = max(min_height, min(calculated_height, max_height))

    gump.SetRect(lastX, lastY, win_width, win_height)
except Exception as e:
    API.SysMsg("ERROR creating GUI: " + str(e), 32)
    raise

try:
    # Background
    bg = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
    bg.SetRect(0, 0, win_width, win_height)
    gump.Add(bg)
except Exception as e:
    API.SysMsg("ERROR creating background: " + str(e), 32)
    raise

try:
    # Title
    test_indicator = " [TEST: ON]" if show_test_scripts else ""
    title_text = "Script Updater v" + __version__ + test_indicator
    title = API.Gumps.CreateGumpTTFLabel(title_text, 16, "#00d4ff", aligned="center", maxWidth=win_width)
    title.SetPos(0, 5)
    gump.Add(title)
except Exception as e:
    API.SysMsg("ERROR creating title: " + str(e), 32)
    raise

try:
    # Instructions with script count
    script_count_text = str(script_count) + " scripts" if MANAGED_SCRIPTS else "Click 'Check Updates'"
    instructions = API.Gumps.CreateGumpTTFLabel(script_count_text, 16, "#00d4ff", aligned="center", maxWidth=win_width)
    instructions.SetPos(0, 28)
    gump.Add(instructions)
except Exception as e:
    API.SysMsg("ERROR creating instructions: " + str(e), 32)
    raise

# Column headers
y = 48
header = API.Gumps.CreateGumpTTFLabel("[ ] [Category] Script Name         | Local  | Remote | Status", 16, "#ffaa00")
header.SetPos(10, y)
gump.Add(header)

# Script list (scrollable area)
y = 68
script_rows = []
row_height = 22

for i, (category, relative_path) in enumerate(MANAGED_SCRIPTS):
    # Clickable row
    filename = os.path.basename(relative_path)
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
y = 68 + (script_count * row_height) + 10

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

# Show Test toggle button (second row)
y += 28
showTestBtn = API.Gumps.CreateSimpleButton("[SHOW TEST:" + ("ON" if show_test_scripts else "OFF") + "]", 140, 22)
showTestBtn.SetPos(10, y)
showTestBtn.SetBackgroundHue(HUE_BLUE if show_test_scripts else HUE_GRAY)
API.Gumps.AddControlOnClick(showTestBtn, toggle_show_test)
gump.Add(showTestBtn)

# Status bar
y += 25
statusBg = API.Gumps.CreateGumpColorBox(0.9, "#000000")
statusBg.SetRect(5, y, win_width - 10, 25)
gump.Add(statusBg)

statusLabel = API.Gumps.CreateGumpTTFLabel("Ready", 16, "#00ff00")
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

        # Periodically update last known position (every 2 seconds)
        # Skip if stop is requested to avoid "operation canceled" errors
        if not API.StopRequested:
            current_time = time.time()
            if current_time - last_position_check > 2.0:
                last_position_check = current_time
                try:
                    last_known_x = gump.GetX()
                    last_known_y = gump.GetY()
                except:
                    pass  # Silently ignore if gump is disposed

        # Short pause - loop runs ~10x/second
        API.Pause(0.1)

    except Exception as e:
        # Don't show "operation canceled" errors during shutdown
        if "operation canceled" not in str(e).lower() and not API.StopRequested:
            API.SysMsg("Error: " + str(e), HUE_RED)
            STATE = "IDLE"
            status_message = "Error: " + str(e)
            update_status_display()
        API.Pause(1)

cleanup()
