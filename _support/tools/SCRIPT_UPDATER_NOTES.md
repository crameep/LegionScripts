# Script_Updater.py - New Folder Structure Notes

## ⚠️ CRITICAL: Script_Updater needs updates for new folder structure

The folder structure was reorganized on 2026-02-01. Script_Updater.py needs modifications to work with the new layout.

---

## Old Structure (Pre-2026-02-01)
```
CoryCustom/
├── Dexer/
├── Mage/
├── Tamer/
├── Utility/
└── Script_Updater.py (at root)
```

## New Structure (Post-2026-02-01)
```
CoryCustom/
├── scripts/
│   ├── Dexer/
│   ├── Mage/
│   ├── Tamer/
│   └── Utility/
├── lib/
│   ├── LegionUtils.py
│   └── GatherFramework.py
├── tools/
│   └── Script_Updater.py (moved here)
└── archive/
    └── backups_YYYY-MM-DD/ (new backup location)
```

---

## Required Changes

### 1. Update Backup Path
**OLD:**
```python
BACKUP_DIR = "_backups"
```

**NEW:**
```python
# Backup to dated folder in archive/
from datetime import datetime
BACKUP_DATE = datetime.now().strftime("%Y-%m-%d")
BACKUP_DIR = os.path.join("..", "archive", f"backups_{BACKUP_DATE}")
```

### 2. Update Script Paths
**OLD:**
```python
SCRIPT_FOLDERS = [
    "Dexer",
    "Mage",
    "Tamer",
    "Utility"
]
```

**NEW:**
```python
SCRIPT_FOLDERS = [
    os.path.join("..", "scripts", "Dexer"),
    os.path.join("..", "scripts", "Mage"),
    os.path.join("..", "scripts", "Tamer"),
    os.path.join("..", "scripts", "Utility")
]
```

### 3. Update Working Directory
Script_Updater now runs from `tools/` subdirectory, so all paths need `..` prefix:

**OLD:**
```python
for folder in SCRIPT_FOLDERS:
    for file in os.listdir(folder):
        # ...
```

**NEW:**
```python
import os
# Get repo root (one level up from tools/)
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

for folder in SCRIPT_FOLDERS:
    full_path = os.path.join(REPO_ROOT, folder)
    for file in os.listdir(full_path):
        # ...
```

### 4. Add lib/ Folder Support
Shared libraries are now in `lib/` and should also be backed up:

```python
SCRIPT_FOLDERS = [
    os.path.join("scripts", "Dexer"),
    os.path.join("scripts", "Mage"),
    os.path.join("scripts", "Tamer"),
    os.path.join("scripts", "Utility"),
    "lib"  # Add shared libraries
]
```

### 5. Update Import Detection
Scripts may now import from `lib/`:

```python
# Detect imports from shared libraries
import_patterns = [
    r"from lib\.(.*) import",
    r"import lib\.(.*)",
    r"from LegionUtils import",  # Old style
    r"from lib\.LegionUtils import",  # New style
]
```

---

## Migration Strategy

### Option A: Quick Fix (5 min)
Update just the paths to work with new structure:
1. Add `..` prefix to all paths
2. Change backup dir to `../archive/backups_YYYY-MM-DD`
3. Update script folders list

### Option B: Full Refactor (30 min)
Modernize Script_Updater to be path-agnostic:
1. Auto-detect folder structure
2. Use `os.path.join()` properly
3. Support both old and new structures
4. Add config file for paths

### Option C: Keep in Root (Not Recommended)
Move Script_Updater.py back to root:
```bash
mv tools/Script_Updater.py ../
```
Then update only the script folder paths. However, this defeats the purpose of having a `tools/` directory.

---

## Testing Checklist

Before deploying updated Script_Updater:

- [ ] Test backup creation in `archive/backups_YYYY-MM-DD/`
- [ ] Test script discovery in `scripts/*/`
- [ ] Test lib/ folder backup
- [ ] Verify relative paths work from `tools/` directory
- [ ] Test on fresh checkout (no cached paths)
- [ ] Verify backup restore functionality
- [ ] Check that .claude directories are not touched

---

## Import Path Updates in Scripts

Some scripts may need import updates if they reference LegionUtils:

**OLD:**
```python
from LegionUtils import *
```

**NEW:**
```python
import sys
import os
# Add lib to path (from scripts/Category/Script.py)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))
from LegionUtils import *
```

**OR (simpler):**
```python
from lib.LegionUtils import *
```

**Check these scripts:**
- scripts/Utility/Util_Gatherer.py (uses GatherFramework)
- Any script importing LegionUtils

---

## Notes for When Pushing to Git

When committing the folder reorganization:

1. **Commit Message:**
   ```
   Refactor: Reorganize folder structure for clarity

   - Move production scripts to scripts/
   - Create lib/ for shared libraries
   - Move tools to tools/
   - Archive old backups to archive/
   - Separate dev/ for WIP and tests
   - Organize docs by purpose

   ⚠️ BREAKING: Script_Updater.py needs path updates (see tools/SCRIPT_UPDATER_NOTES.md)
   ```

2. **Update README.md** with new folder structure

3. **Update CLAUDE.md** "Key Files" section with new paths

4. **Test Script_Updater** before pushing

5. **Consider**: Create `setup.py` or `init.sh` to help new users set up paths

---

## Quick Reference: Where Things Are Now

| Item | Old Location | New Location |
|------|-------------|--------------|
| Production scripts | `Tamer/`, `Utility/`, etc. | `scripts/Tamer/`, `scripts/Utility/` |
| LegionUtils | Root | `lib/` |
| Examples | Root | `examples/` |
| Script_Updater | Root | `tools/` |
| Backups | `_backups/` | `archive/backups_YYYY-MM-DD/` |
| Test scripts | `Test/` | `dev/test/` |
| WIP scripts | `Test/` | `dev/wip/` |
| Old refactors | `refactors/` | `dev/archived/refactors_2026-01/` |
| Design docs | Scattered | `docs/design/` |
| Fix docs | Scattered | `docs/design/fixes/` |
| Old docs | `docs/` subdirs | `docs/archive/` |
| Images | Root | `assets/debug/`, `assets/screenshots/` |
| Captcha data | Scattered | `assets/captcha/` |
| Claude agents | `.claude/agents/` (root) | `.claude/agents/` (unchanged) |

---

## Last Updated
2026-02-01 - Initial notes after folder reorganization
