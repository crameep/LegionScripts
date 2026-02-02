# CoryCustom Folder Structure

## Root Level (Visible to TazUO)

```
CoryCustom/
├── 📄 README.md                    # Main documentation
├── 📄 CLAUDE.md                    # AI assistant context
├── 📄 FOLDER_CLEANUP_PLAN.md       # Cleanup details
├── 📄 CLEANUP_COMPLETE.md          # Cleanup summary
│
├── 🎮 Dexer/                       # TazUO script category
│   └── Dexer_Suite.py
│
├── 🎮 Mage/                        # TazUO script category
│   └── Mage_SpellMenu.py
│
├── 🎮 Tamer/                       # TazUO script category
│   ├── Tamer_Suite.py
│   ├── Tamer_Healer.py
│   └── Tamer_Commands.py
│
├── 🎮 Utility/                     # TazUO script category
│   ├── Util_CottonSuite.py
│   ├── Util_DebugConsole.py
│   ├── Util_Gatherer.py
│   ├── Util_GoldSatchel.py
│   ├── Util_GumpInspector.py
│   ├── Util_HotkeyBar.py
│   ├── Util_Runebook.py
│   └── Util_TomeDumper_v1.py
│
├── 📁 .claude/                     # Claude Code agents (hidden)
│   └── agents/
│
└── 📦 _support/                    # Everything else (hidden from git/TazUO clutter)
    ├── lib/
    ├── tools/
    ├── examples/
    ├── dev/
    ├── docs/
    ├── assets/
    ├── archive/
    └── refactors/
```

---

## _support/ Contents

All non-script files organized here to keep root clean for TazUO:

### 📚 lib/ - Shared Libraries
```
lib/
├── LegionUtils.py          # Shared utilities
└── GatherFramework.py      # Gathering framework
```

**Usage in scripts:**
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '_support', 'lib'))
from LegionUtils import *
```

### 🛠️ tools/ - Utility Tools
```
tools/
├── Script_Updater.py               # Version control for scripts
└── SCRIPT_UPDATER_NOTES.md         # Update guide for new structure
```

### 📘 examples/ - Example Scripts
```
examples/
└── Example_MiningBot.py            # Template for gathering scripts
```

### 🔧 dev/ - Development Workspace
```
dev/
├── test/                           # Test scripts
│   ├── Test_ModuleAvailability.py
│   ├── Test_Screenshot_Methods.py
│   ├── Test_Tamer_Commands.py
│   ├── Test_DebugConsole.py
│   └── Util_HotkeyTester.py
├── wip/                            # Work in progress
│   ├── CottonPicker2.py
│   ├── GatherFramework.py
│   ├── Tamer_Suite_v2.2.py
│   ├── Util_CaptchaSolver.py
│   ├── Util_HotkeyCapture.py
│   └── Util_Scavenger.py
└── archived/                       # Old experiments
    └── refactors_2026-01/
```

### 📖 docs/ - Documentation
```
docs/
├── guides/
│   ├── UI_STANDARDS.md
│   └── GEMINI.md
├── design/
│   ├── tamer/                      # Tamer design docs
│   ├── utility/                    # Utility design docs
│   └── fixes/                      # Fix documentation
├── reference/
│   ├── BEFORE_AFTER_EXAMPLES.md
│   ├── DEEP_DIVE_REPORT.md
│   ├── MORNING_BRIEFING.md
│   └── START_HERE.md
└── archive/                        # Historical docs
    ├── agent/
    ├── phases/
    └── summaries/
```

### 🎨 assets/ - Images & Data
```
assets/
├── debug/
│   └── Debug.png
├── screenshots/
│   └── TomeDumper.png
└── captcha/
    ├── samples/                    # Training data (8 images)
    ├── captcha_current.png
    └── captcha_current3.png
```

### 📦 archive/ - Old Versions
```
archive/
├── backups_2026-01-22/            # 50 timestamped backups
├── old_utility/                    # Old script versions
└── razorenhanced/                  # Archived RazorEnhanced scripts
```

### 📂 refactors/ - Old Refactor Work
```
refactors/
└── .claude/                        # Preserved agent config
    └── agents/
```

---

## Design Philosophy

### Why This Structure?

**Root Level:**
- Script folders (Dexer, Mage, Tamer, Utility) stay at root for TazUO compatibility
- Only essential docs at root (README, CLAUDE)
- Everything else hidden in `_support/`

**_support/ Folder:**
- Keeps root clean for TazUO script menu
- Organizes all non-script files by purpose
- Underscore prefix suggests "support files"
- Single location for development resources

**Benefits:**
- ✅ TazUO sees only script folders (clean menu)
- ✅ All support files organized logically
- ✅ Easy navigation for developers
- ✅ Clear separation of production vs development
- ✅ Git-friendly structure

---

## Quick Reference

| I need... | Location |
|-----------|----------|
| Production script | Root: Dexer/, Mage/, Tamer/, Utility/ |
| Shared library | `_support/lib/` |
| Example/template | `_support/examples/` |
| Test script | `_support/dev/test/` |
| WIP script | `_support/dev/wip/` |
| Documentation | `_support/docs/` |
| Old backup | `_support/archive/backups_YYYY-MM-DD/` |
| Script_Updater | `_support/tools/` |
| Images/assets | `_support/assets/` |

---

## Path Updates for Script_Updater

Since Script_Updater is now in `_support/tools/`, update paths:

```python
import os
from datetime import datetime

# Get repo root (two levels up from _support/tools/)
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Update backup location
BACKUP_DATE = datetime.now().strftime("%Y-%m-%d")
BACKUP_DIR = os.path.join(REPO_ROOT, "_support", "archive", f"backups_{BACKUP_DATE}")

# Update script folders
SCRIPT_FOLDERS = [
    os.path.join(REPO_ROOT, "Dexer"),
    os.path.join(REPO_ROOT, "Mage"),
    os.path.join(REPO_ROOT, "Tamer"),
    os.path.join(REPO_ROOT, "Utility"),
    os.path.join(REPO_ROOT, "_support", "lib")  # Include shared libraries
]
```

---

## Import Paths for Scripts

If scripts need to import from `_support/lib/`:

```python
import sys
import os

# Add _support/lib to path (from script at Tamer/Script.py)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '_support', 'lib'))
from LegionUtils import *
```

**Check which scripts need updates:**
```bash
cd /path/to/CoryCustom
grep -r "from LegionUtils" Dexer/ Mage/ Tamer/ Utility/
grep -r "from GatherFramework" Dexer/ Mage/ Tamer/ Utility/
```

---

## .gitignore Updates

Already configured to ignore:
```
# Development
_support/dev/wip/
_support/assets/debug/
_support/assets/captcha/captcha_current*.png

# Archives
_support/archive/backups_*/

# Executables
*.exe

# Python
__pycache__/
*.pyc
*.pyo
```

---

## Notes

- Underscore prefix (`_support/`) conventionally indicates "internal/support files"
- TazUO may still show `_support/` in menu, but it's clearly not a script category
- All `.claude/` directories preserved (root and in `_support/refactors/`)
- Script folders remain at root for game compatibility
- Clean separation: production scripts vs everything else

---

**Last Updated:** 2026-02-01 - Reorganization complete
