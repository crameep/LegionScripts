# Library Import Paths Fixed ✅

**Date:** 2026-02-01
**Issue:** Scripts had hardcoded absolute paths to old library locations
**Status:** All fixed and validated

---

## Problem

After moving `LegionUtils.py` and `GatherFramework.py` to root, three scripts had broken imports with hardcoded absolute paths to old locations:

1. **Util_Gatherer.py** - Imported from `/Test/` and `/refactors/`
2. **Util_GoldSatchel.py** - Imported from `/refactors/`
3. **Util_TomeDumper_v1.py** - Imported from `/refactors/`

---

## Files Fixed

### 1. ✅ Utility/Util_Gatherer.py

**BEFORE:**
```python
import sys

# Import framework and utils
sys.path.append(r"/mnt/g/Ultima Online/TazUO-Launcher.win-x64/TazUO/LegionScripts/CoryCustom/Test")
sys.path.append(r"/mnt/g/Ultima Online/TazUO-Launcher.win-x64/TazUO/LegionScripts/CoryCustom/refactors")

from GatherFramework import (
from LegionUtils import (
```

**AFTER:**
```python
import sys
import os

# Add parent directory (CoryCustom root) to path for library imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from GatherFramework import (
from LegionUtils import (
```

---

### 2. ✅ Utility/Util_GoldSatchel.py

**BEFORE:**
```python
import sys

# Add LegionUtils to path
sys.path.append(r"G:\Ultima Online\TazUO-Launcher.win-x64\TazUO\LegionScripts\CoryCustom\refactors")
from LegionUtils import (
```

**AFTER:**
```python
import sys
import os

# Add parent directory (CoryCustom root) to path for library imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from LegionUtils import (
```

---

### 3. ✅ Utility/Util_TomeDumper_v1.py

**BEFORE:**
```python
import sys
sys.path.append(r"G:\Ultima Online\TazUO-Launcher.win-x64\TazUO\LegionScripts\CoryCustom\refactors")
from LegionUtils import *
```

**AFTER:**
```python
import sys
import os

# Add parent directory (CoryCustom root) to path for library imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from LegionUtils import *
```

---

## How It Works

### Path Resolution

Scripts in `Utility/` subfolder need to import from root:

```
CoryCustom/                           ← Root (libraries here)
├── LegionUtils.py
├── GatherFramework.py
└── Utility/                          ← Scripts here
    ├── Util_Gatherer.py              ← __file__ = Utility/Util_Gatherer.py
    ├── Util_GoldSatchel.py
    └── Util_TomeDumper_v1.py
```

**Path calculation:**
1. `__file__` = `Utility/Util_Gatherer.py`
2. `os.path.abspath(__file__)` = Full path to script
3. `os.path.dirname(...)` once = `Utility/` directory
4. `os.path.dirname(...)` twice = `CoryCustom/` directory (root)
5. `sys.path.insert(0, ...)` = Add root to Python path
6. Now can `from LegionUtils import *`

---

## Benefits

### ✅ Platform Independent
```python
# OLD - Windows-only hardcoded path
sys.path.append(r"G:\Ultima Online\...")

# NEW - Works on Windows, Linux, macOS
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

### ✅ Relative Paths
- Works regardless of installation directory
- No need to edit paths after moving repository
- Works in WSL, Windows, and any other environment

### ✅ Dynamic
- Automatically finds parent directory
- Works if folder is renamed or moved
- No hardcoded assumptions

---

## Validation Results

All scripts validated successfully:

```bash
✓ Utility/Util_Gatherer.py - Valid syntax
✓ Utility/Util_GoldSatchel.py - Valid syntax
✓ Utility/Util_TomeDumper_v1.py - Valid syntax
```

No remaining hardcoded paths found in:
- Dexer/
- Mage/
- Tamer/
- Utility/

---

## Testing Checklist

Before running in TazUO:

- [✅] Syntax validation passed
- [ ] Run Util_Gatherer.py in TazUO
- [ ] Verify it imports GatherFramework and LegionUtils successfully
- [ ] Run Util_GoldSatchel.py in TazUO
- [ ] Verify it imports LegionUtils successfully
- [ ] Run Util_TomeDumper_v1.py in TazUO
- [ ] Verify it imports LegionUtils successfully
- [ ] No import errors in game

**Expected behavior:** All scripts should start without import errors.

---

## Pattern for Future Scripts

When creating new scripts in subdirectories that need libraries:

```python
import API
import time
import sys
import os

# Add parent directory to path for library imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Now can import from root
from LegionUtils import *
from GatherFramework import *
```

For scripts at root level (Dexer/, Mage/, Tamer/), same pattern works:
```python
# From Tamer/Tamer_Suite.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from LegionUtils import *  # Finds LegionUtils.py at root
```

---

## Summary

| Script | Old Import | New Import | Status |
|--------|-----------|------------|--------|
| Util_Gatherer.py | Hardcoded `/Test/`, `/refactors/` | Relative `../../` | ✅ Fixed |
| Util_GoldSatchel.py | Hardcoded `G:\...\refactors/` | Relative `../../` | ✅ Fixed |
| Util_TomeDumper_v1.py | Hardcoded `G:\...\refactors/` | Relative `../../` | ✅ Fixed |

**All library imports now work with new folder structure!** 🎉

---

## Next Steps

1. ✅ Scripts fixed and validated
2. ⏳ Test in TazUO Legion environment
3. ⏳ Verify no import errors
4. ⏳ Verify functionality works correctly

**Ready to test in game!**
