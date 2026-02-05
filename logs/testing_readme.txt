================================================================================
TAMER PET FARMER - TESTING DOCUMENTATION
================================================================================
Created: 2026-02-05
Script: Tamer_PetFarmer.py

OVERVIEW
========
This directory contains comprehensive testing documentation for the Tamer Pet
Farmer script. Testing is organized into 9 phases, progressing from static
validation through live dungeon testing.

FILES
=====
1. testing_checklist.txt - Comprehensive testing checklist with 9 phases
2. testing_issues.txt - Issue tracking log (severity, status, resolution)
3. testing_readme.txt - This file (overview and getting started)

QUICK START
===========
1. Review testing_checklist.txt to understand the scope
2. Start with Phase 1 (Static Testing)
3. Work through phases sequentially
4. Log any issues in testing_issues.txt
5. Fix critical issues before proceeding to next phase

TESTING PHASES
==============
Phase 1: Static Testing (no combat)
- Script initialization, GUI, persistence, configuration
- Estimated time: 30-60 minutes

Phase 2: Pet System Testing
- Pet detection, healing priority, vet kit usage
- Estimated time: 30 minutes

Phase 3: Patrol Testing
- Movement, NPC avoidance, stuck detection
- Estimated time: 30 minutes

Phase 4: Combat Testing (safe enemy)
- Enemy detection, engagement, combat flow, looting
- Estimated time: 30 minutes

Phase 5: Danger System Testing
- Danger assessment, flee triggers, recovery
- Estimated time: 1 hour

Phase 6: Banking Testing
- Bank triggers, travel, deposit, restocking
- Estimated time: 30 minutes

Phase 7: Error Recovery Testing
- Handling stuck states, resource depletion
- Estimated time: 45 minutes

Phase 8: Long-Run Stability
- Multi-hour stability, memory, responsiveness
- Estimated time: 2-4 hours

Phase 9: Live Dungeon Testing
- Real-world performance, danger tuning
- Estimated time: 2-3 hours (includes tuning)

TOTAL ESTIMATED TIME: 8-12 hours (spread over multiple sessions)

PREREQUISITES
=============
Before starting testing:
1. Character with taming skill and 2+ pets
2. Adequate supplies (bandages, reagents, vet kits)
3. Runebook with safe dungeon and bank locations
4. Safe low-tier dungeon access (Covetous L1, Shame L1)
5. Mid-tier dungeon for Phase 9 (Shame L2, Destard)

RECOMMENDED APPROACH
====================
- Don't rush. Testing is critical for safety and performance.
- Test in multiple sessions. Don't try to complete all phases in one sitting.
- Document thoroughly. Future debugging depends on good notes.
- Start conservative. Use safe dungeons and low-risk settings.
- Tune iteratively. Adjust settings based on observed performance.

SAFETY NOTES
============
- NEVER AFK test in dangerous dungeons
- Stay nearby during Phase 9 (live dungeon testing)
- Use safe dungeons for initial testing (Phases 1-8)
- Keep emergency escape methods ready
- Monitor closely when testing flee mechanics

ISSUE REPORTING
===============
When logging issues in testing_issues.txt:
1. Assign severity (CRITICAL/HIGH/MEDIUM/LOW)
2. Document reproduction steps clearly
3. Note which phase the issue was discovered
4. Track resolution status
5. Update statistics at bottom of file

COMPLETION CRITERIA
===================
Testing is complete when:
1. All 9 phases executed and documented
2. All critical issues resolved
3. Recommended default settings documented
4. Final 2-hour validation run successful (>90% flee success, stable)
5. CLAUDE.md updated with patterns learned
6. Script header updated with setup instructions

NEXT STEPS AFTER TESTING
=========================
1. Update CLAUDE.md with dungeon farming patterns
2. Update script header with recommended settings
3. Create user guide (if specified in project plan)
4. Consider creating video tutorial or quick-start guide
5. Deploy to production use

TROUBLESHOOTING
===============
If testing gets stuck:
- Review testing_issues.txt for patterns
- Check script logs for errors
- Verify all systems initialized correctly
- Restart script with clean settings
- Consult CLAUDE.md for known issues

CONTACT / FEEDBACK
==================
Document feedback and suggestions in testing_issues.txt under severity "LOW"
with prefix "SUGGESTION:" for non-critical improvements.

================================================================================
