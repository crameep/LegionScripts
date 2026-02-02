# Script_Updater.py - Updated for New Folder Structure ✅

**Date:** 2026-02-01
**Version:** 1.8.1 → 1.9.0
**Status:** Successfully updated and tested (syntax valid)

---

## Changes Made

### 1. ✅ Added datetime Import (Line 25)
```python
from datetime import datetime
```

### 2. ✅ Updated Version Number (Line 32)
```python
__version__ = "1.9.0"  # Was: "1.8.1"
```

### 3. ✅ Updated Backup Directory (Lines 36-37)
**Before:**
```python
BACKUP_DIR = "_backups"
```

**After:**
```python
BACKUP_DATE = datetime.now().strftime("%Y-%m-%d")
BACKUP_DIR = os.path.join("_support", "archive", "backups_" + BACKUP_DATE)
```

**Result:** Backups now go to `_support/archive/backups_2026-02-01/` (dated folders)

### 4. ✅ Updated Excluded Directories (Line 43)
**Before:**
```python
EXCLUDED_DIRS_BASE = ["__pycache__", ".git", ".github", "_backups"]
```

**After:**
```python
EXCLUDED_DIRS_BASE = ["__pycache__", ".git", ".github", "_support", ".claude"]
```

**Result:** Script_Updater now skips `_support/` and `.claude/` when scanning for scripts

### 5. ✅ Verified ensure_backup_dir() Function
The function already existed (lines 103-114) and properly:
- Creates backup directory if it doesn't exist
- Uses `os.makedirs()` for nested paths
- Handles errors gracefully
- Returns full backup path

**No changes needed** - function already compatible with new structure!

---

## How It Works Now

### Backup Flow
1. User clicks "Backup & Update" on a script
2. `backup_script()` calls `ensure_backup_dir()`
3. `ensure_backup_dir()` creates `_support/archive/backups_2026-02-01/` if needed
4. Script is backed up to dated folder with timestamp
5. Old backups are cleaned up (keeps last 5 per script)

### Scanning Flow
1. Script_Updater scans root directory for script folders
2. Finds: Dexer/, Mage/, Tamer/, Utility/
3. Skips: _support/, .claude/, __pycache__/
4. Lists all `.py` files in category folders
5. Also checks root level `.py` files (LegionUtils.py, GatherFramework.py, Script_Updater.py)

---

## Testing Checklist

### Before Running in TazUO:

- [✅] Syntax validation passed (`python3 -m py_compile`)
- [ ] Run Script_Updater.py in TazUO
- [ ] Verify it opens without errors
- [ ] Click "Check All" button
- [ ] Verify it scans Dexer/, Mage/, Tamer/, Utility/ folders
- [ ] Verify it finds LegionUtils.py and GatherFramework.py at root
- [ ] Verify it does NOT show scripts from `_support/dev/` or `_support/examples/`
- [ ] Try backing up a script
- [ ] Verify backup goes to `_support/archive/backups_2026-02-01/`
- [ ] Check that old backups in `_support/archive/backups_2026-01-22/` are preserved

### Expected Behavior:

**Script List Should Show:**
- Scripts from Dexer/
- Scripts from Mage/
- Scripts from Tamer/
- Scripts from Utility/
- LegionUtils.py (at root)
- GatherFramework.py (at root)
- Script_Updater.py (at root)

**Script List Should NOT Show:**
- Anything from `_support/dev/test/`
- Anything from `_support/dev/wip/`
- Anything from `_support/examples/`
- Anything from `_support/tools/`
- Agent files from `.claude/agents/`

---

## Backup Directory Structure

**Old Structure (before update):**
```
CoryCustom/
└── _backups/
    ├── Tamer_Suite_20260122_143055.py
    ├── Tamer_Suite_20260122_150330.py
    └── ...
```

**New Structure (after update):**
```
CoryCustom/
└── _support/
    └── archive/
        ├── backups_2026-01-22/         ← Old backups (preserved)
        │   ├── Tamer_Suite_20260122_143055.py
        │   └── ...
        └── backups_2026-02-01/         ← New backups (today)
            ├── Tamer_Suite_20260201_100000.py
            └── ...
```

**Benefits:**
- Backups organized by date
- Easy to find backups from specific day
- Old backups preserved and archived
- Clean separation from active scripts

---

## What Happens on First Run

1. Script_Updater.py starts
2. User clicks backup or update
3. `ensure_backup_dir()` is called
4. Creates folder chain: `_support/` → `archive/` → `backups_2026-02-01/`
5. Backup is written to new folder
6. Success message shown

**Note:** The `_support/archive/` directory already exists from folder reorganization, so only `backups_YYYY-MM-DD/` needs to be created.

---

## Compatibility Notes

### GitHub Repository
If your GitHub repository uses the same folder structure:
- ✅ Scripts in category folders at root (Dexer/, Mage/, Tamer/, Utility/)
- ✅ Shared libraries at root (LegionUtils.py, GatherFramework.py)
- ✅ _support/ folder structure

Script_Updater will download from correct paths.

**If GitHub structure is different:**
You may need to update `GITHUB_BASE_URL` or add path translation logic.

### Old Backups
Old backups in `_support/archive/backups_2026-01-22/` are **preserved** and can still be restored manually if needed. Script_Updater auto-cleanup only affects current day's backup folder.

---

## Rollback Instructions

If you need to revert to old version:

1. **Restore backup directory:**
   ```python
   BACKUP_DIR = "_backups"
   ```

2. **Restore excluded dirs:**
   ```python
   EXCLUDED_DIRS_BASE = ["__pycache__", ".git", ".github", "_backups"]
   ```

3. **Remove datetime import:**
   ```python
   # Remove: from datetime import datetime
   # Remove: BACKUP_DATE = datetime.now().strftime("%Y-%m-%d")
   ```

4. **Revert version:**
   ```python
   __version__ = "1.8.1"
   ```

Or just restore from `_support/archive/backups_2026-01-22/Script_Updater_*.py`

---

## Summary

| Item | Before | After |
|------|--------|-------|
| Version | 1.8.1 | 1.9.0 |
| Backup Location | `_backups/` | `_support/archive/backups_YYYY-MM-DD/` |
| Excludes | _backups | _support, .claude |
| Date Folders | No | Yes |
| Syntax Valid | ✅ | ✅ |

**Status:** ✅ Ready to test in TazUO!

---

## Next Steps

1. ✅ Script updated and validated
2. ⏳ Test in TazUO Legion environment
3. ⏳ Verify backup functionality
4. ⏳ Verify script scanning
5. ⏳ Update CLAUDE.md with any findings

**Ready to test!**
