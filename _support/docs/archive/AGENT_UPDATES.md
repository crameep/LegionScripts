# Agent Updates - Context Awareness

**Date:** 2026-01-27
**Action:** Updated all agent documentation to reference docs/ folder and CLAUDE.md

---

## What Changed

All refactor analysis agent documentation now explicitly references:

1. **CLAUDE.md** - Project instructions and Legion API patterns
   - Contains critical API gotchas and best practices
   - MUST be read before suggesting refactorings
   - Location: `/mnt/g/Ultima Online/TazUO-Launcher.win-x64/TazUO/LegionScripts/CoryCustom/CLAUDE.md`

2. **docs/ folder** - Complete documentation structure
   - **docs/agent/** - Agent instructions and usage
   - **docs/phases/** - Phase 1, 2, 3 implementation guides
   - **docs/reference/** - Deep dive, examples, briefings
   - **docs/summaries/** - Session history
   - Location: `/mnt/g/Ultima Online/TazUO-Launcher.win-x64/TazUO/LegionScripts/CoryCustom/docs/`

---

## Files Updated

### 1. REFACTOR_AGENT_INSTRUCTIONS.md ✅

**Added section:** "Required Context - READ FIRST"

```markdown
Before analyzing any script, you MUST read:

1. **Project Instructions** - CLAUDE.md in project root
   - Contains Legion API patterns, gotchas, and best practices
   - Critical for understanding the scripting environment

2. **Documentation** - docs/ folder in project root
   - docs/phases/ - Phase 1, 2, 3 implementation guides
   - docs/reference/ - Deep dive analysis and examples
   - LegionUtils.py - The actual library
```

**Impact:** Agent now knows to check CLAUDE.md for API patterns before suggesting refactorings.

---

### 2. REFACTOR_AGENT_USAGE.md ✅

**Updated:** Invocation template

**Before:**
```
Required reading:
1. Read REFACTOR_AGENT_INSTRUCTIONS.md
2. Read [SCRIPT_NAME]
3. Read PHASE3_IMPLEMENTATION.md
4. Read LegionUtils.py
```

**After:**
```
Required reading (READ THESE FIRST):
1. **CLAUDE.md** - Project instructions and Legion API patterns
2. **docs/agent/REFACTOR_AGENT_INSTRUCTIONS.md** - Your role
3. **[SCRIPT_NAME]** - The script to analyze
4. **docs/phases/** - Phase implementation guides
5. **refactors/LegionUtils.py** - The actual library

Your analysis should:
- Check CLAUDE.md for API patterns before suggesting refactorings
- Ensure suggestions follow CLAUDE.md best practices
```

**Impact:** Users invoking the agent will ensure it reads CLAUDE.md first.

---

### 3. REFACTOR_AGENT_READY.md ✅

**Added section:** "Required Context"

```markdown
The agent reads these files before analysis:
- **CLAUDE.md** - Legion API patterns and gotchas (CRITICAL)
- **docs/agent/REFACTOR_AGENT_INSTRUCTIONS.md** - Agent expertise
- **docs/phases/** - Implementation guides
- **refactors/LegionUtils.py** - The utility library
```

**Impact:** Quick reference shows what the agent checks before analysis.

---

### 4. AGENT_SUMMARY.md ✅

**Added section:** "Required Context Files"

```markdown
Before analyzing scripts, the agent reads:
- **CLAUDE.md** - Project instructions and Legion API patterns (critical!)
- **docs/agent/REFACTOR_AGENT_INSTRUCTIONS.md** - Agent role
- **docs/phases/** - Phase 1, 2, 3 implementation guides
- **refactors/LegionUtils.py** - The actual utility library

**Why CLAUDE.md is critical:** Contains Legion API gotchas, best practices,
and patterns that must be followed for refactorings to work correctly.
```

**Impact:** Complete documentation includes context file requirements.

---

## Why This Matters

### Problem Before

Agent could suggest refactorings that:
- Violate Legion API patterns (e.g., using methods that don't exist)
- Miss documented gotchas (e.g., button creation patterns)
- Ignore best practices (e.g., using wrong tools for file operations)

### Solution Now

Agent is explicitly told to:
1. **Read CLAUDE.md first** - Understand Legion API patterns
2. **Check docs/ folder** - Access implementation guides
3. **Follow best practices** - Ensure suggestions align with project standards

### Example Scenario

**Without CLAUDE.md awareness:**
```python
# Agent might suggest:
gump.X = 100  # WRONG - Property doesn't exist!
```

**With CLAUDE.md awareness:**
```python
# Agent knows from CLAUDE.md:
x = gump.GetX()  # CORRECT - Use method, not property
```

---

## Invocation Best Practice

When invoking the agent, use this template:

```
Analyze [SCRIPT_NAME] for LegionUtils v3.0 refactoring opportunities.

Before analysis, read:
1. CLAUDE.md for Legion API patterns
2. docs/agent/REFACTOR_AGENT_INSTRUCTIONS.md for your role
3. docs/phases/ for implementation guides

Ensure all suggestions follow CLAUDE.md best practices.
```

---

## Validation

All updated documentation has been:
- ✅ Reviewed for accuracy
- ✅ Links verified
- ✅ Paths confirmed
- ✅ Examples tested

---

## Impact Summary

| File | Lines Added | Purpose |
|------|-------------|---------|
| REFACTOR_AGENT_INSTRUCTIONS.md | ~15 | Add context requirements |
| REFACTOR_AGENT_USAGE.md | ~10 | Update invocation template |
| REFACTOR_AGENT_READY.md | ~8 | Add context section |
| AGENT_SUMMARY.md | ~12 | Document context files |
| **Total** | **~45** | **Context awareness** |

---

## Next Steps

When using the agent:
1. ✅ Agent will automatically check CLAUDE.md
2. ✅ Agent will reference docs/ folder structure
3. ✅ Suggestions will follow Legion API patterns
4. ✅ Refactorings will align with project standards

---

## Documentation Locations

**All documentation is now at project root level:**

```
CoryCustom/
├── CLAUDE.md              ← Project instructions (CRITICAL)
└── docs/                  ← All documentation
    ├── INDEX.md           ← Navigation hub
    ├── agent/             ← Agent documentation (4 files - UPDATED)
    ├── phases/            ← Phase guides
    ├── reference/         ← Deep dive & examples
    └── summaries/         ← Session history
```

---

**Status:** ✅ All agents updated with context awareness!

Agents now know to check CLAUDE.md and docs/ folder before analysis, ensuring suggestions follow Legion API patterns and project standards.
