# Folder Structure Cleanup Plan

## Current Issues

### 🔴 Critical Problems

1. **Root Directory Clutter** - 9 files at root level, should be 1-2
2. **Test Folder Misuse** - Contains production scripts, not just tests
3. **Scattered Documentation** - Fix/design docs mixed with scripts
4. **Executables in Wrong Places** - Windows installers in refactors/
5. **Duplicate Files** - LegionUtils.py exists in 2 places
6. **Massive Backup Folder** - 50+ timestamped backups from Jan 22

### ⚠️ Moderate Issues

7. **Image File Scatter** - Debug/captcha images in multiple folders
8. **RazorEnhanced Folder** - Contains Wireshark installer (doesn't belong)
9. **Orphaned Folders** - Empty docs/guides, nested .claude/agents in refactors/
10. **Unclear Folder Purposes** - Test vs Utility vs refactors overlap

---

## Proposed Clean Structure

```
CoryCustom/
├── README.md                          # Main project readme
├── CLAUDE.md                          # AI assistant context (keep)
│
├── scripts/                           # ✨ NEW: All production scripts
│   ├── Dexer/
│   │   └── Dexer_Suite.py
│   ├── Mage/
│   │   └── Mage_SpellMenu.py
│   ├── Tamer/
│   │   ├── Tamer_Suite.py            # Active version
│   │   ├── Tamer_Healer.py
│   │   └── Tamer_Commands.py
│   └── Utility/
│       ├── Util_CottonSuite.py
│       ├── Util_DebugConsole.py
│       ├── Util_GoldSatchel.py
│       ├── Util_GumpInspector.py
│       ├── Util_HotkeyBar.py
│       ├── Util_Runebook.py
│       ├── Util_TomeDumper_v1.py
│       └── Util_Gatherer.py          # Move from Test/
│
├── lib/                               # ✨ NEW: Shared libraries
│   ├── LegionUtils.py                # Consolidated version
│   └── GatherFramework.py            # Shared gathering logic
│
├── examples/                          # ✨ NEW: Example/template scripts
│   └── Example_MiningBot.py
│
├── dev/                               # ✨ NEW: Development/WIP scripts
│   ├── test/                         # Actual test scripts
│   │   ├── Test_ModuleAvailability.py
│   │   ├── Test_Screenshot_Methods.py
│   │   ├── Test_Tamer_Commands.py
│   │   ├── Test_DebugConsole.py
│   │   └── Util_HotkeyTester.py
│   │
│   ├── wip/                          # Work in progress
│   │   ├── CottonPicker2.py
│   │   ├── Util_CaptchaSolver.py
│   │   ├── Util_HotkeyCapture.py
│   │   └── Util_Scavenger.py
│   │
│   └── archived/                     # Old refactors/experiments
│       └── refactors_2026-01/        # Rename refactors/ folder
│           ├── README.md
│           ├── Tamer_Suite.py
│           ├── Util_CaptchaSolver.py
│           └── LegionUtils.py
│
├── docs/                             # Documentation only
│   ├── guides/
│   │   ├── UI_STANDARDS.md          # Move from root
│   │   └── GEMINI.md                # Move from root
│   │
│   ├── design/                       # ✨ NEW: Design docs
│   │   ├── tamer/
│   │   │   ├── Tamer_Suite_v2_DESIGN.md
│   │   │   ├── Tamer_Suite_v2.1_DESIGN.md
│   │   │   └── Tamer_Suite_v2.2_DESIGN.md
│   │   ├── utility/
│   │   │   ├── AUTOPICK_REDESIGN.md
│   │   │   └── DEBUG_INTEGRATION_GUIDE.md
│   │   └── fixes/                    # ✨ NEW: Fix documentation
│   │       ├── CONFIG_LAYOUT_FIX.md
│   │       ├── HOTKEY_FIX.md
│   │       ├── FIXES_SUMMARY.md
│   │       ├── CottonSuite_Fixes_Applied.md
│   │       ├── FIXES_APPLIED.md
│   │       ├── TomeDumper_All_Fixes_Applied.md
│   │       ├── TomeDumper_Comprehensive_Fix_Plan.md
│   │       ├── TomeDumper_Fixes_Applied.md
│   │       ├── TomeDumper_MultiTarget_Fix.md
│   │       ├── TomeDumper_PreCheck_Fix.md
│   │       └── TomeDumper_SetFill_Fix.md
│   │
│   ├── reference/
│   │   ├── BEFORE_AFTER_EXAMPLES.md
│   │   ├── DEEP_DIVE_REPORT.md
│   │   ├── MORNING_BRIEFING.md
│   │   └── START_HERE.md
│   │
│   └── archive/                      # ✨ NEW: Outdated/historical docs
│       ├── agent/
│       │   ├── AGENT_SUMMARY.md
│       │   ├── REFACTOR_AGENT_INSTRUCTIONS.md
│       │   ├── REFACTOR_AGENT_READY.md
│       │   └── REFACTOR_AGENT_USAGE.md
│       ├── phases/
│       │   ├── PHASE1_IMPLEMENTATION.md
│       │   ├── PHASE2_IMPLEMENTATION.md
│       │   └── PHASE3_IMPLEMENTATION.md
│       ├── summaries/
│       │   ├── NIGHT_SUMMARY.md
│       │   ├── NIGHT_WORK_SUMMARY.md
│       │   ├── REFACTOR_SUMMARY.md
│       │   └── SESSION_2_SUMMARY.md
│       ├── AGENT_UPDATES.md
│       ├── DOCS_ORGANIZED.md
│       ├── INDEX.md
│       ├── REVIEW_Util_Runebook_Hotkeys.md
│       └── TAMER_SUITE_PROGRESS.md
│
├── assets/                           # ✨ NEW: Images, data files
│   ├── debug/
│   │   └── Debug.png
│   ├── screenshots/
│   │   └── TomeDumper.png
│   └── captcha/                      # ✨ NEW: Captcha training data
│       ├── samples/
│       │   ├── 022.png
│       │   ├── 049.png
│       │   ├── 063.png
│       │   ├── 300.png
│       │   ├── 317.png
│       │   ├── 706.png
│       │   ├── 775.png
│       │   └── 887.png
│       ├── captcha_current.png
│       └── captcha_current3.png
│
├── tools/                            # ✨ NEW: Utility tools
│   └── Script_Updater.py
│
├── archive/                          # ✨ NEW: Old versions
│   ├── backups_2026-01-22/           # Rename _backups/
│   │   └── (50+ backup files)
│   ├── old_utility/                  # From Utility/_old/
│   │   ├── Util_GoldSatchel_v1.8.py
│   │   ├── Util_HotkeyBar_v1.1.py
│   │   └── Util_Runebook_v1.3.py
│   └── razorenhanced/                # Archive RazorEnhanced/
│       └── CottonPickerGUI_Public.py
│
├── .claude/
│   └── agents/                       # Keep agents at root level only
│       └── (agent files)
│
└── .git/                             # Git repo (keep)
```

---

## Cleanup Actions

### Phase 1: Create New Folders
```bash
mkdir -p scripts/{Dexer,Mage,Tamer,Utility}
mkdir -p lib
mkdir -p examples
mkdir -p dev/{test,wip,archived}
mkdir -p docs/{guides,design/{tamer,utility,fixes},archive/{agent,phases,summaries}}
mkdir -p assets/{debug,screenshots,captcha/samples}
mkdir -p tools
mkdir -p archive/{backups_2026-01-22,old_utility,razorenhanced}
```

### Phase 2: Move Production Scripts
```bash
# Move category folders
mv Dexer scripts/
mv Mage scripts/
mv Tamer scripts/

# Move Utility scripts (keep production only)
mv Utility/Util_*.py scripts/Utility/

# Move Test/Util_Gatherer.py to production
mv Test/Util_Gatherer.py scripts/Utility/
```

### Phase 3: Move Libraries & Examples
```bash
# Consolidate libraries
mv LegionUtils.py lib/
mv GatherFramework.py lib/

# Move example
mv Example_MiningBot.py examples/
```

### Phase 4: Move Development Files
```bash
# Move actual test scripts
mv Test/Test_*.py dev/test/
mv Utility/Test_DebugConsole.py dev/test/
mv Test/Util_HotkeyTester.py dev/test/

# Move WIP scripts
mv Test/CottonPicker2.py dev/wip/
mv Test/Util_CaptchaSolver.py dev/wip/
mv Test/Util_HotkeyCapture.py dev/wip/
mv Test/Util_Scavenger.py dev/wip/
mv Test/GatherFramework.py dev/wip/

# Archive refactors
mv refactors dev/archived/refactors_2026-01/
```

### Phase 5: Move Documentation
```bash
# Move guides
mv UI_STANDARDS.md docs/guides/
mv GEMINI.md docs/guides/

# Move design docs
mv Test/Tamer_Suite_v2*_DESIGN.md docs/design/tamer/
mv Utility/AUTOPICK_REDESIGN.md docs/design/utility/
mv Utility/DEBUG_INTEGRATION_GUIDE.md docs/design/utility/

# Move fix docs
mv Test/CONFIG_LAYOUT_FIX.md docs/design/fixes/
mv Test/HOTKEY_FIX.md docs/design/fixes/
mv Test/FIXES_SUMMARY.md docs/design/fixes/
mv Utility/*Fixes*.md docs/design/fixes/
mv Utility/TomeDumper_*.md docs/design/fixes/

# Archive old docs
mv docs/agent docs/archive/
mv docs/phases docs/archive/
mv docs/summaries docs/archive/
mv docs/AGENT_UPDATES.md docs/archive/
mv docs/DOCS_ORGANIZED.md docs/archive/
mv docs/INDEX.md docs/archive/
mv Test/REVIEW_Util_Runebook_Hotkeys.md docs/archive/
mv refactors/TAMER_SUITE_PROGRESS.md docs/archive/ 2>/dev/null || true
```

### Phase 6: Move Assets
```bash
# Move images
mv Debug.png assets/debug/
mv Utility/TomeDumper.png assets/screenshots/

# Move captcha data
mv refactors/samples/*.png assets/captcha/samples/
mv refactors/captcha_*.png assets/captcha/
mv Test/captcha_current.png assets/captcha/
```

### Phase 7: Move Tools & Archives
```bash
# Move tools
mv Script_Updater.py tools/

# Archive old versions
mv _backups/* archive/backups_2026-01-22/
mv Utility/_old/* archive/old_utility/
mv RazorEnhanced archive/razorenhanced/
```

### Phase 8: Delete Obsolete Files
```bash
# Delete executables that don't belong
rm refactors/MediaCreationTool.exe 2>/dev/null || true
rm refactors/NTLite_setup_x64.exe 2>/dev/null || true
rm RazorEnhanced/Wireshark-4.6.3-x64.exe 2>/dev/null || true

# Delete duplicate LegionUtils (keep lib/ version)
rm refactors/LegionUtils.py 2>/dev/null || true

# Delete error screenshot
rm refactors/error.png 2>/dev/null || true
```

### Phase 9: Cleanup Empty Folders
```bash
# Remove now-empty folders
rmdir Test Utility Dexer Mage Tamer _backups refactors 2>/dev/null || true
rmdir Utility/_old 2>/dev/null || true
rmdir docs/guides 2>/dev/null || true  # Was empty
```

### Phase 10: Update .gitignore
```bash
# Add to .gitignore
echo "# Development" >> .gitignore
echo "dev/wip/" >> .gitignore
echo "assets/debug/" >> .gitignore
echo "assets/captcha/captcha_current*.png" >> .gitignore
echo "" >> .gitignore
echo "# Archives" >> .gitignore
echo "archive/backups_*/" >> .gitignore
echo "" >> .gitignore
echo "# Executables" >> .gitignore
echo "*.exe" >> .gitignore
```

---

## Benefits

### ✅ Clarity
- **scripts/** - Clear separation: production code only
- **dev/** - Everything development-related in one place
- **docs/** - All documentation organized by purpose
- **lib/** - Shared libraries easy to find
- **assets/** - All non-code files separated

### ✅ Navigation
- Root directory: 6 items instead of 15
- Logical grouping: similar files together
- Clear naming: purpose obvious from folder name

### ✅ Maintenance
- Easy to find production scripts
- Clear separation of WIP vs production
- Archives organized by date
- Design docs separated from fixes

### ✅ Git Workflow
- Cleaner diffs (files in consistent locations)
- Easier PR reviews (related files grouped)
- Better .gitignore rules

---

## Migration Path

**Option A: Full Cleanup (Recommended)**
- Execute all phases in order
- Clean break, fresh structure
- Takes ~15 minutes
- Requires updating import paths in scripts

**Option B: Gradual Migration**
- Phase 1-2: Move production scripts first
- Phase 3-4: Move dev files second
- Phase 5-7: Move docs/assets when convenient
- Phase 8-10: Final cleanup
- Takes several sessions

**Option C: Hybrid Approach**
- Create new structure alongside old
- Copy (don't move) production scripts
- Test new structure
- Delete old structure when confident

---

## Import Path Updates Needed

After moving files, update imports:

```python
# OLD: from LegionUtils import *
# NEW: from lib.LegionUtils import *

# OLD: from GatherFramework import *
# NEW: from lib.GatherFramework import *
```

Scripts in subdirectories may need sys.path adjustments:
```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))
```

---

## Files to Review Before Deleting

**Executables in refactors/:**
- MediaCreationTool.exe (Windows tool - doesn't belong)
- NTLite_setup_x64.exe (Windows tool - doesn't belong)

**Wireshark in RazorEnhanced/:**
- Wireshark-4.6.3-x64.exe (Network analyzer - doesn't belong)

**Recommendation:** Delete all - they're unrelated to UO scripting

---

## Post-Cleanup Verification

1. **Run all production scripts** - Ensure imports still work
2. **Check git status** - Verify moves tracked correctly
3. **Update CLAUDE.md** - Update "Key Files" section with new paths
4. **Update README.md** - Add folder structure documentation
5. **Test Script_Updater.py** - May need path updates

---

## Estimated Impact

- **Root files**: 15 → 6 (60% reduction)
- **Folder depth**: More organized (3 levels max)
- **Duplicate files**: Eliminated
- **Misplaced files**: 0 (all in logical locations)
- **Archive size**: ~100 files archived (out of active workspace)

---

## Questions to Answer

1. **Are refactors/ scripts still needed?**
   - If yes: keep in dev/archived/
   - If no: delete entirely

2. **Should _backups/ be kept?**
   - Git history exists
   - Recommend: archive or delete

3. **Is RazorEnhanced/ folder still relevant?**
   - Only 1 script
   - Recommend: archive

4. **Should Test/ test scripts be kept?**
   - If actively used: move to dev/test/
   - If obsolete: delete

5. **Are docs/phases/ and docs/summaries/ still useful?**
   - If historical reference: archive
   - If obsolete: delete
