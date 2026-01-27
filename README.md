# TazUO Legion Scripts Collection

A collection of Python scripts for [TazUO](https://tazuo.org) client using the Legion scripting engine. Built and tested for **Ultima Online: Unchained**.

## Disclaimer

These scripts are created for personal use and shared with the community as-is. I'm not responsible if they don't work as expected for your setup, character build, or playstyle. This is a hobby project done for fun, not a professional service.

**Having issues?** Feel free to open an issue on the repository and I'll try to help when I have time. No guarantees, but I do enjoy fixing bugs and improving functionality.

---

## Script Management

### Script_Updater.py
**Automatic script updater for keeping your Legion scripts up-to-date.** Downloads latest versions directly from GitHub with version tracking and backup functionality.

**Features:**
- **Version Checking**: Compares your local scripts against the GitHub repository
- **Selective Updates**: Choose which scripts to update with checkboxes
- **Automatic Backups**: Creates timestamped backups before every update in `_backups/` folder
- **Restore Capability**: Recover previous versions if needed
- **Status Indicators**: Visual feedback (OK/UPDATE/NEW/ERROR) for each script
- **Non-Blocking**: GUI stays responsive during downloads
- **Error Handling**: Graceful network and file error recovery

**Usage:**
1. Launch the script to see your current script versions
2. Click **[Check Updates]** to compare with GitHub
3. Select scripts to update (or use **[Update All]**)
4. Click **[Update Selected]** to download and install
5. Scripts are automatically backed up before updating

**First Time Setup:** Just run the script - it will automatically check for updates and show you what's available.

---

## 🔧 LegionUtils v3.0 - Shared Utility Library

**A comprehensive library of reusable utilities for eliminating code duplication across scripts.**

**What is it?**
- 1,920 lines of battle-tested utility code
- 19 major classes/functions covering common patterns
- Eliminates ~1,755-1,810 lines of duplicated code across scripts
- Reduces token usage by ~40% per script

**Documentation:**
- 📑 [Complete Documentation](docs/INDEX.md) - Start here for everything
- 🤖 [Refactor Agent](docs/agent/REFACTOR_AGENT_READY.md) - Analyze scripts for refactoring opportunities
- 📖 [Implementation Guides](docs/phases/) - Phase 1, 2, 3 step-by-step guides
- 📊 [Deep Dive Report](docs/reference/DEEP_DIVE_REPORT.md) - 40+ page analysis

**Location:** The v3.0 library is in `refactors/LegionUtils.py` (the root `LegionUtils.py` is an older version).

**Status:** ✅ All 3 phases complete (2026-01-27)

---

## Tamer Scripts

### Tamer_Suite.py
**The all-in-one tamer automation suite.** Combines pet healing, commands, and combat support into a single non-blocking script.

**Features:**
- **Smart Pet Healing**: Multi-level priority system (resurrection → self-healing → tank pet → poisoned pets → lowest HP)
- **Dual Healing Systems**: Bandages + Greater Heal (magery) with automatic switching
- **Pet Commands**: All Kill, Guard, Follow with individual pet targeting (ORDER mode)
- **Potion Support**: Auto-consume Greater Heal, Cure, and Refresh potions for self
- **Trapped Pouch**: Auto-trigger to break paralyze (safety check: HP >= 30)
- **Auto-Targeting**: Continuous combat - automatically chains to next enemy within 3 tiles when current target dies
- **Veterinary Kit**: Intelligent multi-pet triage when several pets are injured
- **Friend Resurrection**: Configurable res support for party members
- **Persistent Settings**: All preferences saved per-character
- **Sound Alerts**: Audio notifications for critical events
- **Banking**: Quick gold deposit and balance check buttons

**Hotkeys:**
- `PAUSE`: Toggle auto-healing
- `TAB`: All Kill command
- `1`: Guard Me command
- `2`: Follow Me command

**GUI Controls:** Tank selection, target filters (grays/reds), healing thresholds, ORDER mode, potion toggles, trapped pouch, auto-targeting

---

### Tamer_Healer.py
**Standalone pet healing script.** Simpler architecture than the Suite (uses blocking waits). Great for understanding the priority system or if you just want healing without commands.

**Features:**
- Multi-level heal priority system
- Bandage + Greater Heal support
- Tank pet designation
- Friend resurrection
- Pet-by-pet healing thresholds
- Sound alerts

**Hotkeys:** `PAUSE` to toggle

---

### Tamer_Commands.py
**Pet command hotkey system.** Lightweight script for issuing pet commands with ORDER mode support.

**Features:**
- All Kill, Guard, Follow hotkeys
- ORDER mode: Commands pets individually by name
- Target filters (grays/reds)
- Shared pet list system (syncs with other tamer scripts)

**Hotkeys:**
- `TAB`: All Kill
- `1`: Guard Me
- `2`: Follow Me

---

### Test_Tamer_Healer.py / Test_Tamer_Commands.py
**Experimental versions** with additional features and testing. Use at your own risk - may be unstable.

---

## Dexer Scripts

### Dexer_Suite.py
**Complete melee automation suite.** Handles healing, curing, buffs, and targeting for warriors/dexers.

**Features:**
- **Auto-Bandaging**: Self-heal with configurable HP threshold
- **Potion System**: Greater Heal, Cure, Refresh, Strength, Agility
- **Buff Maintenance**: Automatic STR and AGI buff upkeep with alternating system (handles shared potion cooldown)
- **Trapped Pouch**: Auto-trigger to break paralyze (HP safety check)
- **Auto-Targeting**: Continuous combat - chains to next enemy within 3 tiles when target dies
- **Target Filters**: Configurable targeting of grays, reds, and enemy-flagged mobiles
- **Potion Counting**: Real-time display of potion quantities (searches nested containers)
- **Smart Cooldowns**: Grace periods for server lag, universal potion cooldown tracking

**Hotkeys:**
- `F1`: Target nearest enemy
- `F2`: Target nearest gray/criminal
- `F3`: Target nearest red/murderer
- `F4`: Toggle trapped pouch

**GUI Controls:** Auto-bandage toggle, buff toggles (STR/AGI/AUTO), potion toggles, HP/cure thresholds, trapped pouch, auto-targeting, target filters

---

## Mage Scripts

### Mage_SpellMenu.py
**Spell combo system** for quick-casting common PvP and PvE spell sequences.

**Features:**
- Pre-configured spell combos (explosion→ebolt, flamestrike→ebolt, etc.)
- Last-target support
- Interrupt casting hotkey
- Add your own custom combos easily

**Hotkeys:**
- `CTRL+M`: Open spell menu / cast selected combo
- `CTRL+SHIFT+M`: Cast last combo on last target
- `CTRL+I`: Interrupt current spell

---

## Utility Scripts

### Util_GoldSatchel.py
**Auto-loot gold from corpses.** Automatically picks up gold from nearby corpses and displays total looted.

**Features:**
- Configurable loot range (default: 2 tiles)
- Real-time gold counter
- Toggle on/off
- Smart corpse detection (avoids player corpses)

**Hotkey:** `PAUSE` to toggle

---

### Util_Runebook.py
**Quick travel system.** Hotkeys for instant runebook recalls to 4 preset locations.

**Features:**
- Save 4 favorite runebook locations
- Visual indicators for configured slots
- One-button recall

**Hotkeys:** `F1`-`F4` for recall to slots 1-4

---

### Util_GumpInspector.py
**Developer tool** for discovering gump IDs, button IDs, and text field IDs in the Legion API.

**Features:**
- Click any gump to inspect its ID and button info
- Essential for creating custom gump interactions
- Real-time gump event logging

**Hotkey:** `PAUSE` to toggle inspector mode

---

## Installation

1. Place desired `.py` files in your TazUO `LegionScripts` folder
2. Launch TazUO and open the Legion script manager
3. Load the script(s) you want to use
4. Configure settings via the in-game GUI
5. Use hotkeys or GUI buttons to control the scripts

## Requirements

- **TazUO Client**: [Download here](https://tazuo.org)
- **Legion Scripting Enabled**: See [setup guide](https://tazuo.org/wiki/legion-scripting-setup/)
- **Server**: Built for Ultima Online: Unchained (may work on other servers but untested)

## Documentation

- [Legion Python API Reference](https://tazuo.org/legion/api/)
- [Legion Scripting Guide](https://tazuo.org/wiki/legion-scripting/)
- [Public Script Library](https://github.com/PlayTazUO/PublicLegionScripts)

## Support

Found a bug? Have a feature request? Open an issue on the repository.

Remember: This is a hobby project. I'll do my best to help, but can't guarantee quick fixes or support for every edge case.

## License

Free to use, modify, and share. Attribution appreciated but not required.

---

*Happy scripting!*
