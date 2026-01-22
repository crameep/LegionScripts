# ============================================================
# Script Updater v3.1
# by Coryigon for TazUO Legion Scripts
# ============================================================
#
# Automatic script updater that downloads latest versions from GitHub.
# Non-blocking state machine keeps GUI responsive during downloads.
#
# Features:
#   - Collapsible folder hierarchy for organized script display
#   - Check for script updates from GitHub repository
#   - Compare local vs remote versions (semantic versioning)
#   - Backup scripts before updating (_backups directory)
#   - Restore previous versions from backup
#   - Pagination for large script lists (14 rows per page)
#   - Single-button-per-row design (click to select/expand)
#   - Status indicators: NEW, OK, UPDATE, N-A, ERROR
#   - Network error handling with timeouts
#   - Auto-select scripts with updates after version check
#   - Persistent folder expand/collapse state
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

__version__ = "3.1"

# ============ USER SETTINGS ============
GITHUB_BASE_URL = "https://raw.githubusercontent.com/crameep/LegionScripts/main/CoryCustom/"
GITHUB_API_URL = "https://api.github.com/repos/crameep/LegionScripts/contents/CoryCustom/"
BACKUP_DIR = "_backups"
DOWNLOAD_TIMEOUT = 5  # seconds

# Directories to exclude from recursion
EXCLUDED_DIRS = ["__pycache__", ".git", ".github", "_backups", "Test"]

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

# Pagination
MAX_VISIBLE_ROWS = 14

# ============ PERSISTENCE KEYS ============
SETTINGS_KEY = "Updater_WindowXY"
FOLDER_STATE_KEY = "Updater_FolderExpanded"

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
script_data = {}  # Dict: {relative_path: {local_version, remote_version, status, selected, error}}
folder_data = {}  # Dict: {folder_name: {scripts: [], expanded: bool, update_count: int, total_count: int}}
FOLDER_ORDER = []  # Sorted list of folder names
visible_items = []  # Dynamic list of what's currently visible: ("folder", name) or ("script", path)
current_page = 0
total_pages = 1
checking_all = False
backup_path = ""
updater_was_updated = False  # Track if Script_Updater.py was updated (needs restart)

# GUI References
row_pool = []  # List of {"button": btn, "index": i}
pageLabel = None
prevPageBtn = None
nextPageBtn = None

# ============ UTILITY FUNCTIONS ============
def debug_msg(text):
    """Debug logging"""
    if True:  # Set to True for debugging
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
    """Get version of local script file using relative path"""
    try:
        script_dir = get_script_dir()
        path = os.path.join(script_dir, relative_path)
        if os.path.exists(path):
            return parse_version(path)
    except:
        pass
    return None

def download_script(relative_path):
    """Download script content from GitHub using relative path. Returns (success, content_or_error)"""
    # Convert Windows path separators to forward slashes for URL
    url_path = relative_path.replace("\\", "/")
    url = GITHUB_BASE_URL + url_path
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

        # Generate backup filename: Tamer/Tamer_Suite.py -> Tamer_Suite_20260121_143055.py
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        # Get just the filename without extension
        base_name = os.path.basename(relative_path).replace(".py", "")
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
    """Write new content to script file using relative path. Creates directories as needed. Returns (success, error_or_none)"""
    try:
        script_dir = get_script_dir()
        path = os.path.join(script_dir, relative_path)

        # Create parent directories if they don't exist
        parent_dir = os.path.dirname(path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir)
            debug_msg("Created directory: " + parent_dir)

        with open(path, 'w') as f:
            f.write(content)

        debug_msg("Wrote " + str(len(content)) + " bytes to " + relative_path)
        return (True, None)
    except Exception as e:
        return (False, str(e))

def list_backups(relative_path):
    """List all backup files for a given script. Returns list of (path, timestamp)"""
    try:
        script_dir = get_script_dir()
        backup_dir = os.path.join(script_dir, BACKUP_DIR)

        if not os.path.exists(backup_dir):
            return []

        # Get just the filename without extension
        base_name = os.path.basename(relative_path).replace(".py", "")
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

def restore_backup(backup_path, relative_path):
    """Restore a backup file. Returns (success, error_or_none)"""
    try:
        script_dir = get_script_dir()
        target_path = os.path.join(script_dir, relative_path)

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

def fetch_github_directory_recursive(api_url, base_path=""):
    """
    Recursively fetch .py files from GitHub directory.
    Returns list of relative paths (e.g., "Tamer/Tamer_Suite.py")
    """
    script_list = []

    try:
        debug_msg("Fetching: " + api_url)

        try:
            # Python 3 style
            import json
            req = urllib.request.Request(api_url)
            response = urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT)
            data = response.read().decode('utf-8')
            files = json.loads(data)
        except:
            # Python 2 style fallback
            import urllib2
            import json
            req = urllib2.Request(api_url)
            response = urllib2.urlopen(req, timeout=DOWNLOAD_TIMEOUT)
            data = response.read()
            files = json.loads(data)

        for item in files:
            item_name = item.get('name', '')
            item_type = item.get('type', '')

            # Skip excluded directories
            if item_type == 'dir' and item_name in EXCLUDED_DIRS:
                debug_msg("Skipping excluded directory: " + item_name)
                continue

            # Recursively fetch subdirectories
            if item_type == 'dir':
                subdir_url = item.get('url', '')
                if subdir_url:
                    subdir_path = os.path.join(base_path, item_name) if base_path else item_name
                    debug_msg("Recursing into: " + subdir_path)
                    subdir_scripts = fetch_github_directory_recursive(subdir_url, subdir_path)
                    script_list.extend(subdir_scripts)

            # Add .py files
            elif item_type == 'file' and item_name.endswith('.py'):
                # Exclude __init__.py files
                if item_name != '__init__.py':
                    relative_path = os.path.join(base_path, item_name) if base_path else item_name
                    script_list.append(relative_path)
                    debug_msg("Found script: " + relative_path)

    except Exception as e:
        debug_msg("Error fetching directory: " + str(e))

    return script_list

def fetch_github_script_list():
    """Fetch list of .py files from GitHub repository recursively. Returns list of relative paths."""
    try:
        debug_msg("Fetching script list from GitHub API...")
        script_list = fetch_github_directory_recursive(GITHUB_API_URL)
        debug_msg("Found " + str(len(script_list)) + " scripts on GitHub")
        return script_list
    except Exception as e:
        debug_msg("Error fetching GitHub list: " + str(e))
        # Fallback to local discovery
        return discover_local_scripts()

def discover_local_scripts():
    """Discover .py files in local directory recursively as fallback. Returns list of relative paths."""
    try:
        script_dir = get_script_dir()
        script_list = []

        # Walk directory tree
        for root, dirs, files in os.walk(script_dir):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]

            for filename in files:
                if filename.endswith('.py') and filename != '__init__.py':
                    # Get relative path
                    full_path = os.path.join(root, filename)
                    relative_path = os.path.relpath(full_path, script_dir)

                    # Skip if in backup directory
                    if not relative_path.startswith(BACKUP_DIR):
                        script_list.append(relative_path)

        debug_msg("Discovered " + str(len(script_list)) + " local scripts")
        return script_list
    except Exception as e:
        debug_msg("Local discovery error: " + str(e))
        API.SysMsg("Error discovering local scripts: " + str(e), HUE_RED)
        return []

# ============ FOLDER MANAGEMENT ============
def group_scripts_by_folder():
    """Organize MANAGED_SCRIPTS into folder_data structure"""
    global folder_data, FOLDER_ORDER

    folder_data = {}

    for relative_path in MANAGED_SCRIPTS:
        # Determine folder name
        if os.sep in relative_path or "/" in relative_path:
            # Has folder: "Tamer/Script.py" or "Tamer\Script.py"
            folder_name = relative_path.split(os.sep)[0].split("/")[0]
        else:
            # Root level: "Script.py"
            folder_name = "_root"

        # Initialize folder if needed
        if folder_name not in folder_data:
            folder_data[folder_name] = {
                'scripts': [],
                'expanded': True,  # Default to expanded
                'update_count': 0,
                'total_count': 0
            }

        # Add script to folder
        folder_data[folder_name]['scripts'].append(relative_path)
        folder_data[folder_name]['total_count'] += 1

    # Sort folders: Alphabetically, with _root at end
    FOLDER_ORDER = sorted([f for f in folder_data.keys() if f != "_root"])
    if "_root" in folder_data:
        FOLDER_ORDER.append("_root")

    debug_msg("Grouped into " + str(len(folder_data)) + " folders: " + str(FOLDER_ORDER))

    # Load saved expand state
    load_folder_state()

def update_folder_counts():
    """Calculate update counts per folder after version check"""
    for folder_name, folder in folder_data.items():
        update_count = 0
        for script_path in folder['scripts']:
            if script_data[script_path]['status'] == STATUS_UPDATE:
                update_count += 1
        folder['update_count'] = update_count
        debug_msg("Folder " + folder_name + ": " + str(update_count) + " updates")

def toggle_folder_expand(folder_name):
    """Toggle expand/collapse state for a folder"""
    if folder_name in folder_data:
        folder_data[folder_name]['expanded'] = not folder_data[folder_name]['expanded']
        save_folder_state()
        rebuild_visible_items()
        render_visible_rows()
        debug_msg("Toggled folder: " + folder_name + " -> " + str(folder_data[folder_name]['expanded']))


def save_folder_state():
    """Save folder expand/collapse state to persistence"""
    try:
        # Format: "Tamer:1|Mage:0|Utility:1" (1=expanded, 0=collapsed)
        state_list = []
        for folder_name in FOLDER_ORDER:
            expanded = folder_data[folder_name]['expanded']
            state_list.append(folder_name + ":" + ("1" if expanded else "0"))

        state_str = "|".join(state_list)
        API.SavePersistentVar(FOLDER_STATE_KEY, state_str, API.PersistentVar.Char)
        debug_msg("Saved folder state: " + state_str)
    except Exception as e:
        debug_msg("Error saving folder state: " + str(e))

def load_folder_state():
    """Load folder expand/collapse state from persistence"""
    try:
        state_str = API.GetPersistentVar(FOLDER_STATE_KEY, "", API.PersistentVar.Char)
        if not state_str:
            return

        # Parse: "Tamer:1|Mage:0|Utility:1"
        for entry in state_str.split("|"):
            if ":" not in entry:
                continue
            folder_name, expanded_str = entry.split(":", 1)
            if folder_name in folder_data:
                folder_data[folder_name]['expanded'] = (expanded_str == "1")

        debug_msg("Loaded folder state: " + state_str)
    except Exception as e:
        debug_msg("Error loading folder state: " + str(e))

# ============ VISIBLE ITEMS & PAGINATION ============
def rebuild_visible_items():
    """Build list of visible items based on expand state"""
    global visible_items, total_pages, current_page

    visible_items = []

    for folder_name in FOLDER_ORDER:
        folder = folder_data[folder_name]

        # Add folder header
        visible_items.append(("folder", folder_name))

        # Add scripts if expanded
        if folder['expanded']:
            for script_path in folder['scripts']:
                visible_items.append(("script", script_path))

    # Calculate pagination
    total_pages = max(1, (len(visible_items) + MAX_VISIBLE_ROWS - 1) // MAX_VISIBLE_ROWS)

    # Clamp current page
    if current_page >= total_pages:
        current_page = total_pages - 1
    if current_page < 0:
        current_page = 0

    debug_msg("Visible items: " + str(len(visible_items)) + ", Pages: " + str(total_pages))

def get_visible_page_items():
    """Get items for current page"""
    start_idx = current_page * MAX_VISIBLE_ROWS
    end_idx = start_idx + MAX_VISIBLE_ROWS
    return visible_items[start_idx:end_idx]

def next_page():
    """Go to next page"""
    global current_page
    if current_page < total_pages - 1:
        current_page += 1
        render_visible_rows()
        debug_msg("Page: " + str(current_page + 1) + "/" + str(total_pages))

def prev_page():
    """Go to previous page"""
    global current_page
    if current_page > 0:
        current_page -= 1
        render_visible_rows()
        debug_msg("Page: " + str(current_page + 1) + "/" + str(total_pages))

# ============ ROW RENDERING ============
def render_folder_row(row, item):
    """Render a folder row"""
    folder_name = item[1]
    folder = folder_data[folder_name]

    # Expand icon
    expand_icon = u"\u25BC" if folder['expanded'] else u"\u25B6"  # ▼ or ▶

    # Display name
    display_name = "Other" if folder_name == "_root" else folder_name

    # Update info
    update_text = ""
    if folder['update_count'] > 0:
        update_text = " - " + str(folder['update_count']) + " update"
        if folder['update_count'] > 1:
            update_text += "s"

    # Build text
    text = expand_icon + " " + display_name + " (" + str(folder['total_count']) + " scripts)" + update_text

    # Set button
    row["button"].SetText(text)

    # Color: Yellow if has updates, Blue otherwise
    if folder['update_count'] > 0:
        row["button"].SetBackgroundHue(HUE_YELLOW)
    else:
        row["button"].SetBackgroundHue(HUE_BLUE)

def render_script_row(row, item):
    """Render a script row"""
    path = item[1]
    data = script_data[path]
    filename = os.path.basename(path)

    local_ver = data['local_version'] or "---"
    remote_ver = data['remote_version'] or "---"
    status = data['status']

    # Build text with indent - simplified format
    text = "    " + filename + "  v" + local_ver + " -> v" + remote_ver + "  [" + status + "]"

    row["button"].SetText(text)

    # Color based on SELECTION, then STATUS
    if data['selected']:
        row["button"].SetBackgroundHue(HUE_GREEN)  # Selected = green
    else:
        # Not selected - show status color
        if status == STATUS_UPDATE:
            row["button"].SetBackgroundHue(HUE_YELLOW)
        elif status == STATUS_NEW:
            row["button"].SetBackgroundHue(HUE_BLUE)
        elif status == STATUS_ERROR:
            row["button"].SetBackgroundHue(HUE_RED)
        else:  # OK or N-A
            row["button"].SetBackgroundHue(HUE_GRAY)

def render_visible_rows():
    """Update GUI rows with current visible items"""
    page_items = get_visible_page_items()

    for i in range(MAX_VISIBLE_ROWS):
        row = row_pool[i]

        if i < len(page_items):
            # Show this row
            item = page_items[i]
            item_type = item[0]

            if item_type == "folder":
                render_folder_row(row, item)
            else:  # "script"
                render_script_row(row, item)

            # Bind callback for this row
            bind_row_callbacks(i)
        else:
            # Hide this row (no item)
            row["button"].SetText("")
            row["button"].SetBackgroundHue(HUE_GRAY)
            API.Gumps.AddControlOnClick(row["button"], lambda: None)

    # Update page label
    if pageLabel:
        pageLabel.SetText("Page " + str(current_page + 1) + " / " + str(total_pages))

# ============ CALLBACK FACTORIES ============
def make_folder_expand_callback(folder_name):
    """Create callback to expand/collapse folder"""
    def callback():
        toggle_folder_expand(folder_name)
    return callback

def make_script_toggle_callback(script_path):
    """Create callback to toggle script selection"""
    def callback():
        script_data[script_path]['selected'] = not script_data[script_path]['selected']
        render_visible_rows()
    return callback

def bind_row_callbacks(row_idx):
    """Bind callbacks for a specific row based on current page items"""
    row = row_pool[row_idx]
    page_items = get_visible_page_items()

    if row_idx >= len(page_items):
        # Empty row - no callback needed
        API.Gumps.AddControlOnClick(row["button"], lambda: None)
        return

    item = page_items[row_idx]
    item_type = item[0]
    item_data = item[1]

    if item_type == 'folder':
        # Folder - click to expand/collapse
        API.Gumps.AddControlOnClick(row["button"], make_folder_expand_callback(item_data))
    else:
        # Script - click to toggle selection
        API.Gumps.AddControlOnClick(row["button"], make_script_toggle_callback(item_data))

# ============ INITIALIZATION ============
def init_script_data():
    """Initialize script data structure"""
    global script_data, MANAGED_SCRIPTS

    # Fetch script list from GitHub
    API.SysMsg("Fetching script list from GitHub...", HUE_BLUE)
    MANAGED_SCRIPTS = fetch_github_script_list()

    debug_msg("MANAGED_SCRIPTS after fetch: " + str(len(MANAGED_SCRIPTS)) + " items")
    if MANAGED_SCRIPTS:
        debug_msg("First few scripts: " + str(MANAGED_SCRIPTS[:3]))

    if not MANAGED_SCRIPTS:
        API.SysMsg("GitHub fetch returned no scripts! Trying local discovery...", HUE_YELLOW)
        MANAGED_SCRIPTS = discover_local_scripts()
        if not MANAGED_SCRIPTS:
            API.SysMsg("ERROR: No scripts found anywhere! Cannot continue.", HUE_RED)
            return
        else:
            API.SysMsg("Found " + str(len(MANAGED_SCRIPTS)) + " scripts locally", HUE_GREEN)
    else:
        API.SysMsg("Found " + str(len(MANAGED_SCRIPTS)) + " scripts in repository", HUE_GREEN)

    for relative_path in MANAGED_SCRIPTS:
        script_data[relative_path] = {
            'local_version': None,
            'remote_version': None,
            'status': STATUS_NA,
            'selected': False,
            'error': None
        }
        # Get local version
        local_ver = get_local_version(relative_path)
        script_data[relative_path]['local_version'] = local_ver
        if local_ver:
            script_data[relative_path]['status'] = STATUS_OK

    # Group scripts into folders
    group_scripts_by_folder()

    # Build initial visible items
    rebuild_visible_items()

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
        for relative_path in MANAGED_SCRIPTS:
            if script_data[relative_path]['selected']:
                scripts_to_update.append(relative_path)
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

        # Auto-select ONLY scripts with updates available
        for path, data in script_data.items():
            if data['status'] == STATUS_UPDATE:
                data['selected'] = True
            else:
                data['selected'] = False  # Ensure others are deselected

        # Update folder counts
        update_folder_counts()

        # Rebuild visible items and render
        rebuild_visible_items()
        render_visible_rows()

        # Count updates available
        update_count = sum(1 for data in script_data.values() if data['status'] == STATUS_UPDATE)
        if update_count > 0:
            API.SysMsg("Found " + str(update_count) + " updates!", HUE_YELLOW)
        else:
            API.SysMsg("All scripts up to date", HUE_GREEN)
        return

    # Check next script
    relative_path = scripts_to_update[current_script_index]
    status_message = "Checking " + os.path.basename(relative_path) + "..."
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
            elif cmp == 0:
                script_data[relative_path]['status'] = STATUS_OK
            else:
                script_data[relative_path]['status'] = STATUS_OK  # Local is newer

        script_data[relative_path]['error'] = None
    else:
        # Download failed
        script_data[relative_path]['status'] = STATUS_ERROR
        script_data[relative_path]['error'] = content  # Error message

    current_script_index += 1

def start_update_selected():
    """Start updating selected scripts"""
    global STATE, scripts_to_update, current_script_index, status_message

    if STATE != "IDLE":
        API.SysMsg("Already busy!", HUE_RED)
        return

    # Build list of selected scripts
    scripts_to_update = []
    for relative_path in MANAGED_SCRIPTS:
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

def process_backing_up():
    """Process BACKING_UP state - backup one script"""
    global STATE, current_script, backup_path, status_message, updater_was_updated

    if current_script_index >= len(scripts_to_update):
        # Done with all updates
        STATE = "IDLE"
        status_message = "Update complete!"
        update_status_display()
        API.SysMsg("Update complete! " + str(len(scripts_to_update)) + " scripts updated", HUE_GREEN)

        # Update folder counts
        update_folder_counts()
        rebuild_visible_items()
        render_visible_rows()

        # Remind user if updater was updated
        if updater_was_updated:
            API.SysMsg("", HUE_GREEN)
            API.SysMsg("REMINDER: Restart Script_Updater.py to use new version!", HUE_YELLOW)

        return

    # Backup next script
    relative_path = scripts_to_update[current_script_index]
    current_script = relative_path
    status_message = "Backing up " + os.path.basename(relative_path) + "..."
    update_status_display()

    # Only backup if file exists locally
    if script_data[relative_path]['local_version']:
        success, result = backup_script(relative_path)
        if not success:
            # Backup failed - warn but continue
            API.SysMsg("Backup failed for " + relative_path + ": " + result, HUE_RED)

    # Move to downloading
    STATE = "DOWNLOADING"

def process_downloading():
    """Process DOWNLOADING state - download one script"""
    global STATE, download_data, status_message

    relative_path = current_script
    status_message = "Downloading " + os.path.basename(relative_path) + "..."
    update_status_display()

    success, content = download_script(relative_path)

    if success:
        download_data = content
        STATE = "WRITING"
    else:
        # Download failed
        script_data[relative_path]['status'] = STATUS_ERROR
        script_data[relative_path]['error'] = content
        API.SysMsg("Download failed: " + relative_path, HUE_RED)

        # Move to next script
        global current_script_index
        current_script_index += 1
        STATE = "BACKING_UP"
        render_visible_rows()

def process_writing():
    """Process WRITING state - write downloaded content to file"""
    global STATE, current_script_index, status_message, updater_was_updated

    relative_path = current_script
    status_message = "Writing " + os.path.basename(relative_path) + "..."
    update_status_display()

    success, error = write_script(relative_path, download_data)

    if success:
        # Update local version
        new_version = get_remote_version(download_data)
        script_data[relative_path]['local_version'] = new_version
        script_data[relative_path]['status'] = STATUS_OK
        script_data[relative_path]['error'] = None
        script_data[relative_path]['selected'] = False  # Deselect after update

        API.SysMsg("Updated: " + os.path.basename(relative_path) + " -> v" + (new_version or "?"), HUE_GREEN)

        # Special handling for self-update
        if relative_path == "Script_Updater.py":
            updater_was_updated = True
            API.SysMsg("", HUE_GREEN)
            API.SysMsg("=== UPDATER SELF-UPDATE COMPLETE ===", HUE_YELLOW)
            API.SysMsg("Please RESTART this script for changes to take effect!", HUE_YELLOW)
            API.SysMsg("Close and reopen Script_Updater.py", HUE_YELLOW)
    else:
        # Write failed
        script_data[relative_path]['status'] = STATUS_ERROR
        script_data[relative_path]['error'] = error
        API.SysMsg("Write failed: " + relative_path, HUE_RED)

    # Move to next script
    current_script_index += 1
    STATE = "BACKING_UP"
    render_visible_rows()

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

def on_restore_backup():
    """Restore a script from backup"""
    global STATE

    if STATE != "IDLE":
        API.SysMsg("Please wait until current operation finishes", HUE_YELLOW)
        return

    API.SysMsg("Restore feature: Use file manager to copy from _backups/", HUE_YELLOW)

# ============ DISPLAY UPDATES ============
def update_status_display():
    """Update status bar"""
    statusLabel.SetText(status_message)

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
win_height = 480
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
instructions = API.Gumps.CreateGumpTTFLabel("Collapsible folders | Select and update | Backups in _backups/", 8, "#aaaaaa", aligned="center", maxWidth=win_width)
instructions.SetPos(0, 28)
gump.Add(instructions)

# Column headers
y = 48
header = API.Gumps.CreateGumpTTFLabel("Script Name -> Version -> Status  (click to select/expand)", 9, "#ffaa00")
header.SetPos(10, y)
gump.Add(header)

# Script list area - Fixed pool of MAX_VISIBLE_ROWS
y_start = 68
row_height = 22
row_width = win_width - 25

if not MANAGED_SCRIPTS:
    # Show error message if no scripts loaded
    errorLabel = API.Gumps.CreateGumpTTFLabel("ERROR: No scripts loaded! Check network.", 11, "#ff0000", aligned="center", maxWidth=win_width)
    errorLabel.SetPos(0, y_start + 100)
    gump.Add(errorLabel)
else:
    for i in range(MAX_VISIBLE_ROWS):
        y = y_start + (i * row_height)
        btn = API.Gumps.CreateSimpleButton("", row_width, row_height - 2)
        btn.SetPos(10, y)
        btn.SetBackgroundHue(HUE_GRAY)
        gump.Add(btn)

        row_pool.append({
            "button": btn,
            "index": i
        })

# Pagination controls
y = y_start + (MAX_VISIBLE_ROWS * row_height) + 5

prevPageBtn = API.Gumps.CreateSimpleButton("[<]", 40, 22)
prevPageBtn.SetPos(10, y)
prevPageBtn.SetBackgroundHue(HUE_BLUE)
API.Gumps.AddControlOnClick(prevPageBtn, prev_page)
gump.Add(prevPageBtn)

pageLabel = API.Gumps.CreateGumpTTFLabel("Page 1 / 1", 9, "#ffffff")
pageLabel.SetPos(60, y + 3)
gump.Add(pageLabel)

nextPageBtn = API.Gumps.CreateSimpleButton("[>]", 40, 22)
nextPageBtn.SetPos(180, y)
nextPageBtn.SetBackgroundHue(HUE_BLUE)
API.Gumps.AddControlOnClick(nextPageBtn, next_page)
gump.Add(nextPageBtn)

# Bottom buttons
y += 32

checkBtn = API.Gumps.CreateSimpleButton("[Check Updates]", 180, 25)
checkBtn.SetPos(10, y)
checkBtn.SetBackgroundHue(HUE_BLUE)
API.Gumps.AddControlOnClick(checkBtn, on_check_updates)
gump.Add(checkBtn)

updateSelectedBtn = API.Gumps.CreateSimpleButton("[Update Selected]", 180, 25)
updateSelectedBtn.SetPos(200, y)
updateSelectedBtn.SetBackgroundHue(HUE_YELLOW)
API.Gumps.AddControlOnClick(updateSelectedBtn, on_update_selected)
gump.Add(updateSelectedBtn)

restoreBtn = API.Gumps.CreateSimpleButton("[Restore Backup]", 170, 25)
restoreBtn.SetPos(390, y)
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
render_visible_rows()
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
