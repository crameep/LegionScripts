# LegionUtils Refactor Analysis Agent

## Overview

This specialized agent analyzes Legion Python scripts to identify opportunities to use LegionUtils v3.0 utilities. It's an expert on all 19 utility classes/functions and can provide detailed before/after examples with line-by-line analysis.

## Agent Capabilities

### What It Does
- ✅ Identifies which LegionUtils utilities are already in use
- ✅ Finds specific refactoring opportunities with line numbers
- ✅ Estimates line savings for each opportunity
- ✅ Provides before/after code examples
- ✅ Prioritizes by impact (High/Medium/Low)
- ✅ Recommends implementation order
- ✅ Considers complexity and risk

### What It Knows
- All 19 LegionUtils v3.0 utilities (Phase 1+2+3)
- Common code patterns and anti-patterns
- Line-by-line refactoring techniques
- Risk assessment for each change

## How to Invoke the Agent

### Using Claude Code Task Tool

```
I'll use the Task tool to launch the general-purpose agent with this prompt:

"You are a specialized refactoring analysis agent for Legion Python scripts.

**Your task**: Analyze `[PATH_TO_SCRIPT]` and identify opportunities to use LegionUtils v3.0 utilities.

**Required reading (READ THESE FIRST)**:
1. **CLAUDE.md** - Project instructions and Legion API patterns
   - Path: /mnt/g/Ultima Online/TazUO-Launcher.win-x64/TazUO/LegionScripts/CoryCustom/CLAUDE.md
   - Contains critical API gotchas and best practices
2. **docs/agent/REFACTOR_AGENT_INSTRUCTIONS.md** - Your role and output format
3. **[SCRIPT_NAME]** - The script to analyze
4. **docs/phases/** - Phase 1, 2, 3 implementation guides
5. **refactors/LegionUtils.py** - The actual library (focus on relevant sections)

**Your analysis should**:
- Check CLAUDE.md for API patterns before suggesting refactorings
- Identify which LegionUtils utilities are ALREADY being used (✅)
- Find specific opportunities to apply utilities
- Reference actual line numbers from the script
- Show before/after code snippets
- Estimate line savings for each opportunity
- Prioritize by impact (High/Medium/Low)
- Recommend implementation order
- Ensure suggestions follow CLAUDE.md best practices

**Focus areas** (optional - customize based on script):
- Phase 1: Item counting, window position, toggle settings, timers, expandable windows
- Phase 2: Hotkey system, state machines, display groups, formatters
- Phase 3: Formatters, layout helper, condition checker, resource tracker, journal/math/color helpers

Provide a detailed analysis following the format in docs/agent/REFACTOR_AGENT_INSTRUCTIONS.md."
```

### Quick Invocation Template

```markdown
Analyze [SCRIPT_NAME] for LegionUtils v3.0 refactoring opportunities. Use the refactor analysis agent documented in REFACTOR_AGENT_INSTRUCTIONS.md. Focus on [Phase 1/2/3 or "all phases"].
```

## Output Format

The agent produces a structured markdown report:

```markdown
# Refactoring Analysis: [Script Name]

## Current LegionUtils Usage
- ✅ [Utilities already in use]

## Refactoring Opportunities

### High Priority (100+ lines saved)
[Detailed opportunities with code examples]

### Medium Priority (20-100 lines saved)
[...]

### Low Priority (<20 lines saved)
[...]

## Total Impact
- Lines that can be removed: ~X
- Net savings: ~Y lines
- Maintainability: [Assessment]

## Recommended Implementation Order
1. [Step-by-step refactoring plan]
```

## Example Analyses

### Completed Analyses

1. **Util_GoldSatchel.py** (v3.3-refactor) - PARTIALLY REFACTORED
   - Already using 10+ Phase 1-2 utilities
   - Found 210-220 lines that can be eliminated with Phase 3
   - Identified quick wins (53 lines in 7 minutes)
   - **Validation**: Agent correctly identified existing usage + Phase 3 opportunities
   - Analysis date: 2026-01-27

2. **Dexer_Suite.py** - UNREFACTORED
   - Found 575-605 lines that can be eliminated (18% reduction!)
   - Opportunities across ALL phases (1, 2, and 3)
   - DisplayGroup alone: 150-180 lines saved
   - ExpandableWindow: 120 lines saved
   - **Validation**: Agent correctly identified NO existing usage + comprehensive opportunities
   - Analysis date: 2026-01-27

### Agent Validation Results

✅ **Test 1 - Partially Refactored Script** (Util_GoldSatchel.py)
- Agent correctly identified 10+ utilities already in use
- Focused on Phase 3 opportunities (as expected)
- Estimated 210-220 additional lines can be saved
- Provided quick wins (53 lines in 7 minutes)

✅ **Test 2 - Unrefactored Script** (Dexer_Suite.py)
- Agent correctly identified NO utilities in use
- Found opportunities across ALL phases
- Estimated 575-605 lines can be saved (18% reduction)
- Matched deep dive analysis expectations (~500+ lines)

**Conclusion:** Agent works consistently and accurately on both refactored and unrefactored scripts!

## Best Practices

### When to Use This Agent

✅ **Good use cases:**
- Before starting a refactoring session
- When reviewing old scripts for modernization
- To estimate refactoring effort/benefit
- To learn which utilities apply to specific patterns
- To generate refactoring roadmaps

❌ **Not needed for:**
- Simple scripts (<100 lines)
- Scripts already fully refactored
- Scripts with no duplication
- Quick bug fixes

### How to Use Results

1. **Read the entire analysis** - Understand current state and opportunities
2. **Start with quick wins** - Low-risk, high-impact changes first
3. **Test incrementally** - One opportunity at a time
4. **Verify in-game** - Test each change works correctly
5. **Commit frequently** - Each successful refactor gets a commit

### Customizing the Analysis

You can customize the agent prompt to focus on:
- **Specific phases**: "Focus on Phase 3 utilities only"
- **Specific patterns**: "Focus on GUI layout and hotkey systems"
- **Risk level**: "Identify only low-risk refactoring opportunities"
- **Time constraints**: "Find quick wins (<10 minute refactors)"

## Testing the Agent

### Test Scripts

To verify the agent works consistently, test on:

1. **Partially refactored scripts** (like Util_GoldSatchel.py)
   - Should identify what's done and what remains
   - Should focus on Phase 3 opportunities

2. **Unrefactored scripts** (like Dexer_Suite.py)
   - Should identify Phase 1+2+3 opportunities
   - Should estimate total impact (500+ lines potential)

3. **Small scripts** (like Util_Runebook.py)
   - Should identify limited opportunities
   - Should assess if refactoring is worth it

### Validation Criteria

A good analysis should:
- ✅ Reference actual line numbers
- ✅ Show concrete before/after examples
- ✅ Estimate line savings accurately
- ✅ Consider complexity and risk
- ✅ Recommend incremental approach
- ✅ Total impact aligns with deep dive findings

## Files

- `REFACTOR_AGENT_INSTRUCTIONS.md` - Agent role and instructions
- `REFACTOR_AGENT_USAGE.md` - This file (how to use the agent)
- `PHASE1_IMPLEMENTATION.md` - Phase 1 utilities documentation
- `PHASE2_IMPLEMENTATION.md` - Phase 2 utilities documentation
- `PHASE3_IMPLEMENTATION.md` - Phase 3 utilities documentation
- `LegionUtils.py` - The actual utility library (1,920 lines)

## Changelog

- **2026-01-27**: Initial agent creation and documentation
- **2026-01-27**: First successful analysis (Util_GoldSatchel.py)
- **2026-01-27**: Created usage documentation

## Next Steps

1. ✅ Create agent instructions (REFACTOR_AGENT_INSTRUCTIONS.md)
2. ✅ Create usage guide (this file)
3. ⏳ Test agent on multiple scripts
4. ⏳ Validate consistency and accuracy
5. ⏳ Document best practices from real usage
6. ⏳ Create quick reference for common patterns

---

**Ready to use!** Invoke the agent anytime you need to analyze a script for refactoring opportunities.
