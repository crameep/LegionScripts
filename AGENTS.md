# Repository Guidelines

## Project Structure & Module Organization
- Root script categories must remain at the repository root for TazUO compatibility: `Dexer/`, `Mage/`, `Tamer/`, `Utility/`.
- Shared libraries live at the root (`LegionUtils.py`, `GatherFramework.py`) and are imported directly from scripts.
- Support materials (docs, assets, examples, dev tests, archives) live under `_support/`.
- Reference structure: `_support/FOLDER_STRUCTURE.md`.

## Build, Test, and Development Commands
- There is no build system; scripts are loaded directly in the TazUO Legion script manager.
- Manual testing is done in-game. Helpful dev scripts are under `_support/dev/test/`.

## Coding Style & Naming Conventions
- Language: Python (Legion scripting API).
- Script naming: `Category/Script_Name.py` with descriptive names (e.g., `Tamer/Tamer_Suite.py`).
- Keep scripts non-blocking: call `API.ProcessCallbacks()` each loop and use short pauses (see `CLAUDE.md`).
- GUI standards and button creation patterns are documented in `_support/docs/guides/UI_STANDARDS.md`.
- Font size minimum: 15 for `CreateGumpTTFLabel` (see `CLAUDE.md`).

## Testing Guidelines
- No automated test runner is defined.
- Manual verification in the TazUO client is required after changes that affect state machines, hotkeys, or gumps.
- Dev-only tests live in `_support/dev/test/` and can be loaded like any other script.

## Commit & Pull Request Guidelines
- Recent commits use the prefix `auto-claude:` with short summaries (see `git log`).
- Commit messages should be concise and describe the user-visible behavior change.
- PRs should include:
  - A clear summary of the script(s) changed.
  - Manual testing notes (e.g., “Loaded `Tamer/Tamer_Suite.py` and verified hotkeys + gump layout”).
  - Screenshots for UI/gump changes when applicable.

## Agent-Specific Instructions
- `CLAUDE.md` documents critical API patterns, non-blocking state machines, and known pitfalls.
- `_support/docs/guides/UI_STANDARDS.md` is the source of truth for gump UI patterns.
