# CLAUDE.md

Python scripts for TazUO (Ultima Online) using the Legion scripting engine. Scripts run in-game with injected `API` object. No build system - load directly via game UI.

## Documentation
- **API Reference**: https://tazuo.org/legion/api/
- **Scripting Guide**: https://tazuo.org/wiki/legion-scripting/
- **Public Scripts**: https://github.com/PlayTazUO/PublicLegionScripts
- **UO Unchained Wiki**: https://uounchained.wiki.gg/wiki/

---

## Core Patterns

### Non-Blocking State Machine (REQUIRED)
Never use long `API.Pause()` - blocks hotkeys. Use state machine:
```python
STATE = "idle"
action_start_time = 0

while not API.StopRequested:
    API.ProcessCallbacks()  # MUST be first

    if STATE == "idle":
        if action := get_next_action():
            start_action(action)
            STATE = "acting"
            action_start_time = time.time()
    elif STATE == "acting":
        if time.time() > action_start_time + action.duration:
            STATE = "idle"

    API.Pause(0.1)  # Short pause only
```

### Healing Priority
1. Friend resurrection → 2. Self (poison/HP) → 3. Tank pet → 4. Poisoned pets → 5. Lowest HP → 6. Top-off → 7. Vet kit

### Shared Pet List
- Key: `SharedPets_List`, Format: `name:serial:active|...`, Scope: `API.PersistentVar.Char`

---

## Timing Constants

| Action | Duration | Notes |
|--------|----------|-------|
| Bandage | ~4.5s | 8 - (DEX/20) |
| Greater Heal | ~2.5s | 4th circle |
| Pet Rez | ~10s | 80+ Vet |
| Vet kit / Potion | 10s | Cooldown |
| Pet command | ~0.5s | Between commands |
| Recall | ~2s | |

---

## API Quick Reference

### Core
```python
API.Msg("text")                      # Say in game
API.SysMsg("text", hue)              # System message
API.Pause(seconds)                   # Pause execution
API.StopRequested                    # Check if stopping
API.ProcessCallbacks()               # Process hotkeys/GUI
```

### Mobiles
```python
mob = API.Mobiles.FindMobile(serial) # Can return None!
API.Player                           # Current player
mob.Hits / mob.HitsMax               # HP
mob.IsDead                           # Death check
mob.Distance                         # Distance (property, not method!)
mob.IsPoisoned or mob.Poisoned       # Poison check
```

### Items
```python
item = API.FindItem(serial)          # Can return None!
API.FindType(graphic)                # Find by graphic
API.UseObject(item, False)           # Use item
item.Distance                        # Property, not method!
```

### Targeting
```python
API.HasTarget() / API.CancelTarget() / API.CancelPreTarget()
API.PreTarget(serial, "beneficial")  # or "harmful"
```

### Persistence
```python
API.SavePersistentVar(key, value, scope)
API.GetPersistentVar(key, default, scope)
# Scopes: API.PersistentVar.Char, API.PersistentVar.Global
```

### GUI
```python
gump = API.Gumps.CreateGump()
gump.SetRect(x, y, width, height)    # Position & size
gump.Dispose()                       # Close (NOT RemoveGump!)
API.Gumps.AddGump(gump)
API.Gumps.AddControlOnClick(ctrl, cb)

label = API.Gumps.CreateGumpTTFLabel("text", size, "#color")
button = API.Gumps.CreateSimpleButton("text", width, height)
textBox = API.Gumps.CreateGumpTextBox(default, width, height)
```

### Undocumented (Verified Working)
```python
# Blocking - use in callbacks, NOT main loop
target = API.RequestTarget(timeout=15)
hotkey = API.WaitForHotkey(timeout=10)
API.UnregisterHotkey(hotkey_str)
API.WaitForGump(delay=3.0)
API.ReplyGump(button_id, gump_id)
API.HasGump(gump_id) / API.CloseGump(gump_id)

# Pathfinding
API.Pathfinding()                    # Check if active
API.CancelPathfinding()
API.Pathfind(x, y)                   # Returns bool
API.PathfindEntity(serial, distance)
```

---

## STOP! Common API Errors

### ❌ Methods That DON'T Exist
```python
API.Gumps.RemoveGump(gump)           # NO! Use gump.Dispose()
gump.SetTitle() / gump.SetSize()     # NO! Use SetRect(x,y,w,h)
gump.X / gump.Y                      # NO! Use gump.GetX() / gump.GetY()
label.SetColor()                     # NO! Set at creation only
textBox.Text = "x"                   # NO! Use textBox.SetText("x")
btn.SetSize(w, h)                    # NO! Use SetRect or SetPos
API.Player.DistanceTo(mob)           # NO! Use mob.Distance
API.Target(serial)                   # NO! Use PreTarget + UseObject
```

### ✅ Correct Usage
```python
gump.Dispose()                       # Close gump
gump.SetRect(x, y, w, h)             # Position & size
x, y = gump.GetX(), gump.GetY()      # Get position
textBox.SetText("value")             # Update text
mobile.Distance / item.Distance      # Properties, not methods
API.PreTarget(serial, "beneficial")  # Setup target
API.UseObject(item_serial, False)    # Trigger action
```

---

## Critical Gotchas

### Null Safety (ALWAYS CHECK!)
```python
mob = API.Mobiles.FindMobile(serial)
if mob is None or mob.IsDead:
    return
hp_pct = (mob.Hits / mob.HitsMax * 100) if mob.HitsMax > 0 else 100
```

### Button Creation Patterns
```python
# Pattern 1: WITH dimensions → use SetPos()
btn = API.Gumps.CreateSimpleButton("Text", 100, 22)
btn.SetPos(x, y)  # ONLY x, y

# Pattern 2: NO dimensions → use SetRect()
btn = API.Gumps.CreateSimpleButton("Text")
btn.SetRect(x, y, 100, 22)  # Includes size

# NEVER MIX: Don't use SetRect() after creating with dimensions!
```

### Multi-Window Button References
```python
# Store button refs in global dict for updates after creation
config_controls = {}

def build_config():
    global config_controls
    config_controls = {}
    config_controls["btn"] = API.Gumps.CreateSimpleButton("[ON]", 47, 18)
    # ... add to gump ...

def toggle():
    if "btn" in config_controls:
        config_controls["btn"].SetBackgroundHue(68)
        config_controls["btn"].SetText("[OFF]")
```

### String Concatenation Safety
```python
# WRONG: Crashes if value is bool/int/None
msg = "Value: " + config["key"]

# CORRECT: Always use str() with .get() and defaults
msg = "Value: " + str(config.get("key", "Unknown"))
```

### Poison Detection
```python
is_poisoned = getattr(mob, 'IsPoisoned', False) or getattr(mob, 'Poisoned', False)
```

---

## GUI Standards

### Color Hues
| Hue | Color | Usage |
|-----|-------|-------|
| 68 | Green | Active/enabled |
| 32 | Red | Danger/disabled |
| 38 | Red-purple | Rez/tank |
| 43 | Yellow | Warning |
| 90 | Gray | Neutral |

### Font Sizes

**CRITICAL:** Minimum font size is **15** for work machine compatibility. Font sizes 14 and below cause `Arg_IndexOutOfRangeException` on some systems (DPI/font rendering related).

```python
titleLabel = API.Gumps.CreateGumpTTFLabel("Title", 16, "#ffaa00")       # Title/headers
dataLabel = API.Gumps.CreateGumpTTFLabel("12,345", 15, "#ffcc00")       # All other text (minimum safe)
statusLabel = API.Gumps.CreateGumpTTFLabel("ACTIVE", 15, "#00ff00")     # Status
helpLabel = API.Gumps.CreateGumpTTFLabel("Help text", 15, "#888888")    # Help/secondary
```

**Testing revealed (2026-02-02):**
- Font 16: ✅ Works everywhere
- Font 15: ✅ Works everywhere
- Font 14: ❌ Fails on work machine (IndexOutOfRangeException)
- Font 7-13: ❌ Fails on work machine

---

## Common Patterns

### Safe Mobile Operation
```python
def heal_target(serial):
    mob = API.Mobiles.FindMobile(serial)
    if mob is None or mob.IsDead or mob.Distance > HEAL_RANGE:
        return False
    hp_pct = (mob.Hits / mob.HitsMax * 100) if mob.HitsMax > 0 else 100
    return hp_pct < 100
```

### Targeting Sequence
```python
def target_and_use(item_serial, target_serial, target_type="beneficial"):
    if API.HasTarget():
        API.CancelTarget()
    API.CancelPreTarget()
    API.PreTarget(target_serial, target_type)
    API.Pause(0.1)
    API.UseObject(item_serial, False)
    API.Pause(0.1)
    API.CancelPreTarget()
```

### Persistence
```python
# Boolean
API.SavePersistentVar(KEY + "Enabled", str(enabled), API.PersistentVar.Char)
enabled = API.GetPersistentVar(KEY + "Enabled", "True", API.PersistentVar.Char) == "True"

# List
API.SavePersistentVar(KEY + "List", "|".join(items), API.PersistentVar.Char)
items = [x for x in API.GetPersistentVar(KEY + "List", "", API.PersistentVar.Char).split("|") if x]

# Window Position (use WindowPositionTracker class)
from LegionUtils import WindowPositionTracker

# After creating gump
pos_tracker = WindowPositionTracker(gump, SETTINGS_KEY, default_x=100, default_y=100)
gump.SetRect(pos_tracker.last_x, pos_tracker.last_y, width, height)

# In main loop
pos_tracker.update()  # Tracks position every 2 seconds

# In on_closed callback
pos_tracker.save()  # Saves tracked position (works even when gump disposed)
```

### Income/Rate Tracking
```python
# For gathering scripts - tracks resource gains and calculates rates
from LegionUtils import ResourceRateTracker

# Setup (notify on gains of 100+)
gold_tracker = ResourceRateTracker("gold", check_interval=2.0, notify_threshold=100)

# In main loop
current_gold = count_all_gold()
gold_tracker.update(current_gold)  # Auto-detects increases

# Get rates for display
per_min, per_10min, per_hour = gold_tracker.get_rates()
API.SysMsg(f"Total: {gold_tracker.total_gained} ({format_gold_compact(per_min)}/m)")

# Reset button
gold_tracker.reset()  # Clears total, restarts timer
```

### Resource Depletion (Anti-Spam)
```python
out_of_resource_warned = False
out_of_resource_cooldown = 0

def check_resource(graphic):
    global out_of_resource_warned, out_of_resource_cooldown
    if not API.FindType(graphic):
        if not out_of_resource_warned:
            API.SysMsg("OUT OF RESOURCE!", 32)
            out_of_resource_warned = True
            out_of_resource_cooldown = time.time()
        return False
    else:
        out_of_resource_warned = False
        out_of_resource_cooldown = 0
    return True

# In main loop
if STATE == "idle":
    if out_of_resource_cooldown > 0:
        if API.FindType(RESOURCE):
            out_of_resource_warned = False
            out_of_resource_cooldown = 0
            perform_action()
        elif time.time() - out_of_resource_cooldown > 5.0:
            out_of_resource_cooldown = time.time()  # Extend cooldown
    else:
        perform_action()
```

### Emergency Runebook Recall
```python
def emergency_recall(runebook_serial, spot_index):
    """Use runebook charges when out of reagents (button 10, gump 89)"""
    API.UseObject(runebook_serial)
    while not API.HasGump(89):
        API.Pause(0.1)
    API.Pause(2.70)
    API.ReplyGump(10, 89)  # Emergency recall button
    API.Pause(0.5)
    if API.HasGump(89):
        API.ReplyGump(100 + spot_index, 89)
    API.Pause(4.5)
```

### Position-Based Recall Verification
```python
def verify_recall():
    pos_x = getattr(API.Player, 'X', 0)
    pos_y = getattr(API.Player, 'Y', 0)
    # ... perform recall ...
    API.Pause(4.5)
    if pos_x != getattr(API.Player, 'X', 0) or pos_y != getattr(API.Player, 'Y', 0):
        return True
    API.Pause(2.0)  # Retry
    return pos_x != getattr(API.Player, 'X', 0) or pos_y != getattr(API.Player, 'Y', 0)
```

### Flee with Stuck Detection
```python
def flee_from_enemy(enemy_serial):
    flee_start = time.time()
    last_check = time.time()
    last_x = getattr(API.Player, 'X', 0)
    last_y = getattr(API.Player, 'Y', 0)

    while time.time() < flee_start + 15:
        API.ProcessCallbacks()
        cur_x = getattr(API.Player, 'X', 0)
        cur_y = getattr(API.Player, 'Y', 0)

        # Stuck detection
        if time.time() > last_check + 1.5:
            if cur_x == last_x and cur_y == last_y:
                if API.Pathfinding():
                    API.CancelPathfinding()
                import random
                API.Pathfind(cur_x + random.randint(-10, 10), cur_y + random.randint(-10, 10))
            last_x, last_y = cur_x, cur_y
            last_check = time.time()

        # Check if safe to recall
        enemy = API.Mobiles.FindMobile(enemy_serial)
        if enemy and not enemy.IsDead and enemy.Distance >= 8 and time.time() - flee_start >= 2.0:
            hp = API.Player.Hits
            API.Pause(0.5)
            if API.Player.Hits >= hp:
                return True

        # Flee in opposite direction
        if not API.Pathfinding() and enemy:
            px, py = getattr(API.Player, 'X', 0), getattr(API.Player, 'Y', 0)
            ex, ey = getattr(enemy, 'X', px), getattr(enemy, 'Y', py)
            API.Pathfind(px + (px - ex) * 2, py + (py - ey) * 2)

        API.Pause(0.1)
    return True
```

### Dungeon-Aware Flee System
```python
# FleeSystem with multiple escape methods (direct_recall, gump_gate, timer_gate, run_outside)
# Used in Tamer_PetFarmer.py - see full implementation

# Initialize systems
area_manager = AreaManager(KEY_PREFIX)
npc_threat_map = NPCThreatMap()
flee_system = FleeSystem(area_manager, npc_threat_map, KEY_PREFIX)

# Define farming area with safe spots
safe_spot = SafeSpot(x=1500, y=1500, escape_method="direct_recall", is_primary=True)
area = FarmingArea(name="Orc Fort", area_type="circle", center_x=1500, center_y=1500, radius=15)
area.safe_spots = [safe_spot]
area_manager.add_area(area)

# In danger assessment logic
if danger_score >= 70:
    flee_system.initiate_flee("danger_critical")
    STATE = "fleeing"

# In fleeing state handler (main loop)
def handle_fleeing_state():
    if not flee_system.is_fleeing:
        STATE = "idle"
        return
    still_fleeing = flee_system.flee_to_safe_spot(flee_system.current_safe_spot)
    if not still_fleeing:
        STATE = "recovering"

# Key features:
# - Automatic pathfinding to safe spot with stuck detection
# - NPC threat map integration for safe path selection
# - Multiple escape methods (recall, gates, run outside)
# - Statistics tracking (flee_count, flee_success, flee_failures)
# - Timeout protection and emergency recall
```

### Journal Detection
```python
def check_out_of_reagents():
    return "reagents to cast" in API.InGameJournal.GetText().lower()

def check_resource_depleted():
    journal = API.InGameJournal.GetText().lower()
    return any(msg in journal for msg in ["no ore here", "can't mine", "try mining elsewhere"])
```

---

## Script Structure Template

```python
# Script_Name_v1.py
import API
import time

# ========== CONSTANTS ==========
BANDAGE_DELAY = 4.5

# ========== PERSISTENCE ==========
KEY_PREFIX = "ScriptName_"

# ========== STATE ==========
STATE = "idle"
action_start_time = 0
config_controls = {}

# ========== FUNCTIONS ==========
def get_next_action():
    pass

def save_settings():
    pass

def load_settings():
    pass

def cleanup():
    if config_gump:
        config_gump.Dispose()

# ========== INIT ==========
load_settings()
# ... build GUI ...
API.OnHotKey("PAUSE", toggle_pause)

# ========== MAIN LOOP ==========
while not API.StopRequested:
    try:
        API.ProcessCallbacks()
        # ... main logic ...
        API.Pause(0.1)
    except Exception as e:
        API.SysMsg("Error: " + str(e), 32)
        API.Pause(1)

cleanup()
```

---

## Code Review Integration

Use `codex-code-reviewer` agent after significant changes:

**ALWAYS invoke for:**
- New scripts, refactoring 3+ functions, state machine changes, multi-file changes

**NEVER invoke for:**
- Typo fixes, single-line fixes, variable renames, formatting

**How to invoke:**
```
Task tool:
- subagent_type: "codex-code-reviewer"
- description: "Review [filename] changes"
- prompt: "Review [filename] for [concerns]. Focus on [state machine/GUI/persistence]."
```

**Two-tier validation:**
1. **Pre-validation**: Scans 30+ documented anti-patterns, checks ProcessCallbacks, null safety
2. **Codex Review**: Deep architectural analysis, race conditions (if pre-validation passes)

---

## Folder Structure

```
CoryCustom/
├── Dexer/              # Melee combat scripts
├── Mage/               # Spellcasting scripts
├── Tamer/              # Pet management scripts
├── Utility/            # Utility scripts
├── LegionUtils.py      # Shared library (import with: from LegionUtils import *)
├── GatherFramework.py  # Gathering framework (import with: from GatherFramework import *)
├── Script_Updater.py   # Version control utility
└── _support/           # Hidden from TazUO (dev, docs, assets, archive, examples, tools)
```

**Note:** Script category folders (Dexer, Mage, Tamer, Utility) must stay at root for TazUO script loader compatibility.

## Key Files

| File | Description |
|------|-------------|
| Tamer/Tamer_Suite.py | Combined healer + commands, non-blocking |
| Utility/Util_Gatherer.py | Mining/lumberjacking automation |
| Utility/Util_Runebook.py | Quick travel system |
| Mage/Mage_SpellMenu.py | Spell combo system |
| LegionUtils.py | Shared utilities (at root for easy import) |
| GatherFramework.py | Shared gathering logic (at root for easy import) |

---

## Known Issues

| Issue | Workaround |
|-------|------------|
| Pet serials change after rez | Re-scan by name |
| Hotkeys unresponsive | ProcessCallbacks() frequently |
| Target cursor stuck | CancelTarget() + CancelPreTarget() |
| Buttons not updating | Store refs in global dict |
| Resource spam | Use anti-spam cooldown pattern |

---

## Changelog

Major changes:
- **2026-02-05**: Added FleeSystem, AreaManager, NPCThreatMap classes to Tamer_PetFarmer.py - dungeon-aware flee mechanics with multiple escape methods (direct_recall, gump_gate, timer_gate, run_outside)
- **2026-02-02**: CRITICAL: Discovered minimum font size requirement of 15 for CreateGumpTTFLabel on some systems (work machine DPI/font rendering issue causes IndexOutOfRangeException with fonts 14 and below). Updated all scripts to use minimum font 15.
- **2026-02-01**: Added ResourceRateTracker class - tracks resource gains and calculates per-min/hour rates for gathering scripts
- **2026-02-01**: Refactored Util_GoldSatchel.py to use ResourceRateTracker (removed 45 lines of manual tracking code)
- **2026-02-01**: Fixed WindowPositionTracker.save() - now uses tracked position instead of reading from disposed gump
- **2026-02-01**: Updated window position pattern in Common Patterns - use WindowPositionTracker class for all scripts
- **2026-02-01**: Reorganized folder structure - scripts at root (TazUO compat), support files in _support/
- **2026-01-31**: Integrated codex-code-reviewer with two-tier validation
- **2026-01-30**: Added "STOP! Common No Attribute Errors" section
- **2026-01-27**: Added pathfinding APIs, resource depletion anti-spam
- **2026-01-25**: Added flee mechanics, emergency recall, journal patterns
- **2026-01-24**: Added button creation patterns, font standards, multi-window refs
- **Initial**: Base patterns from Tamer_Suite_v1
