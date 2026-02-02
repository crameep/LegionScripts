# Script_Updater.py - Required Changes for New Structure

## Current Status
Script_Updater.py is now at root level and ready to be updated for the new folder structure.

## Required Changes

### 1. Update Backup Directory (Line 36)

**CURRENT:**
```python
BACKUP_DIR = "_backups"
```

**NEW:**
```python
from datetime import datetime
BACKUP_DATE = datetime.now().strftime("%Y-%m-%d")
BACKUP_DIR = os.path.join("_support", "archive", f"backups_{BACKUP_DATE}")
```

**Why:** Backups now go to dated folders in `_support/archive/` instead of `_backups/` at root.

---

### 2. Update Excluded Directories (Line 41)

**CURRENT:**
```python
EXCLUDED_DIRS_BASE = ["__pycache__", ".git", ".github", "_backups"]
```

**NEW:**
```python
EXCLUDED_DIRS_BASE = ["__pycache__", ".git", ".github", "_support", ".claude"]
```

**Why:**
- `_support/` contains all non-script files and should be excluded
- `.claude/` contains agents and should be excluded
- `_backups` no longer exists (now in `_support/archive/`)

---

### 3. Add Import for datetime (After line 24)

**CURRENT:**
```python
import re
import os
try:
    import urllib.request
```

**NEW:**
```python
import re
import os
from datetime import datetime
try:
    import urllib.request
```

**Why:** Needed for dated backup folders.

---

### 4. Update Version Number (Line 31)

**CURRENT:**
```python
__version__ = "1.8.1"
```

**NEW:**
```python
__version__ = "1.9.0"
```

**Why:** Signify folder structure update.

---

### 5. Ensure Backup Directory Exists

Add this function after `get_script_dir()` (around line 100):

```python
def ensure_backup_dir():
    """Create backup directory if it doesn't exist"""
    if not os.path.exists(BACKUP_DIR):
        try:
            os.makedirs(BACKUP_DIR)
            debug_msg(f"Created backup directory: {BACKUP_DIR}")
        except Exception as e:
            debug_msg(f"Failed to create backup dir: {str(e)}")
```

Then call it in the backup function before creating backups.

---

### 6. Include Shared Libraries in Scan

The script should also check LegionUtils.py and GatherFramework.py at root level.

**Find the section that scans for scripts** (likely in a function that builds MANAGED_SCRIPTS) and ensure it includes:
- Root level `.py` files (LegionUtils.py, GatherFramework.py, Script_Updater.py)
- Category folders (Dexer/, Mage/, Tamer/, Utility/)

---

## Implementation Steps

1. **Backup current Script_Updater.py:**
   ```bash
   cp Script_Updater.py Script_Updater.py.backup
   ```

2. **Make changes 1-4** (imports, constants, version)

3. **Add function from change 5** (ensure_backup_dir)

4. **Test the script:**
   - Run it and verify it creates `_support/archive/backups_2026-02-01/`
   - Verify it scans Dexer/, Mage/, Tamer/, Utility/ folders
   - Verify it skips `_support/` and `.claude/`

5. **Verify backup functionality:**
   - Try backing up a script
   - Confirm backup goes to new location
   - Verify old backups in `_support/archive/backups_2026-01-22/` are preserved

---

## Summary of Changes

| Item | Old Value | New Value |
|------|-----------|-----------|
| BACKUP_DIR | `"_backups"` | `os.path.join("_support", "archive", f"backups_{BACKUP_DATE}")` |
| EXCLUDED_DIRS | `["__pycache__", ".git", ".github", "_backups"]` | `["__pycache__", ".git", ".github", "_support", ".claude"]` |
| Version | `"1.8.1"` | `"1.9.0"` |
| Imports | No datetime | `from datetime import datetime` |

---

## Testing Checklist

After making changes:

- [ ] Script runs without errors
- [ ] Creates backup directory at `_support/archive/backups_YYYY-MM-DD/`
- [ ] Scans all category folders (Dexer, Mage, Tamer, Utility)
- [ ] Skips `_support/` folder
- [ ] Skips `.claude/` folder
- [ ] Can backup scripts successfully
- [ ] Backups go to new location
- [ ] Can restore from backups
- [ ] Old backups in `_support/archive/backups_2026-01-22/` preserved

---

## Note on GitHub Repository

If your GitHub repository also needs to be updated with the new structure, make sure:
- Script category folders remain at root (Dexer/, Mage/, Tamer/, Utility/)
- Shared libraries at root (LegionUtils.py, GatherFramework.py)
- _support/ folder structure is consistent

Otherwise, Script_Updater won't be able to download files from the correct paths.

---

**Ready to implement these changes?** Let me know when you want me to update the file!
