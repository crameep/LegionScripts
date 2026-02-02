# ============================================================
# Mage Spell Menu v1.3
# by Coryigon for UO Unchained
# ============================================================
#
# A spell combo system for mages. Select your combo from the
# menu, then use hotkeys to unleash it on enemies.
#
# Features:
#   - Pre-defined spell combos for PvP and PvE
#   - One-key combo execution on nearest hostile
#   - Last target support for chasing
#   - Quick interrupt spell (Harm)
#   - Expand/collapse to save screen space
#
# Hotkeys: CTRL+M (cast combo), CTRL+SHIFT+M (last target),
#          CTRL+I (interrupt)
#
# ============================================================
import API
import time

__version__ = "1.3"

# ============ USER SETTINGS ============
MAX_DISTANCE = 12
CAST_HOTKEY = "CTRL+M"           # Execute selected combo on nearest hostile
TARGET_HOTKEY = "CTRL+SHIFT+M"   # Execute selected combo on last target
INTERRUPT_HOTKEY = "CTRL+I"      # Quick interrupt (Harm)
# =======================================

# ============ CONSTANTS ============
SETTINGS_KEY = "mage_combat_xy"
COMBO_SETTING = "mage_combat_combo"

# GUI dimensions
COLLAPSED_HEIGHT = 24
EXPANDED_HEIGHT = 400
WINDOW_WIDTH = 280
# ===================================

# ============ RUNTIME STATE ============
current_combo = "explo_ebolt"
lastTarget = 0
is_expanded = True

# GUI position tracking (for improved position saving)
last_known_x = 100
last_known_y = 100
last_position_check = 0
# =======================================

# ============ SPELL DEFINITIONS ============
# Format: (spell_name, delay_after_cast, needs_target)
SPELLS = {
    "magic_arrow": ("Magic Arrow", 0.5, True),
    "harm": ("Harm", 0.5, True),
    "fireball": ("Fireball", 1.0, True),
    "lightning": ("Lightning", 1.25, True),
    "mind_blast": ("Mind Blast", 1.5, True),
    "energy_bolt": ("Energy Bolt", 1.75, True),
    "explosion": ("Explosion", 2.0, True),      # 2s fuse delay
    "flamestrike": ("Flamestrike", 2.25, True),
    "chain_lightning": ("Chain Lightning", 2.5, True),
    "meteor_swarm": ("Meteor Swarm", 2.5, True),
    # Debuffs
    "curse": ("Curse", 1.5, True),
    "weaken": ("Weaken", 0.5, True),
    "clumsy": ("Clumsy", 0.5, True),
    "feeblemind": ("Feeblemind", 0.5, True),
    "paralyze": ("Paralyze", 1.75, True),
    "mana_drain": ("Mana Drain", 1.5, True),
    # Utility
    "greater_heal": ("Greater Heal", 1.75, True),
    "cure": ("Cure", 1.0, True),
    "magic_reflect": ("Magic Reflection", 1.5, False),
    "protection": ("Protection", 1.25, False),
}

# ============ COMBO DEFINITIONS ============
COMBOS = {
    # === PVP COMBOS ===
    "explo_ebolt": {
        "name": "Explo → E-Bolt",
        "desc": "Classic PvP dump combo",
        "type": "pvp",
        "spells": ["explosion", "energy_bolt"],
        "hue": 32
    },
    "para_dump": {
        "name": "Para → Dump",
        "desc": "Paralyze then burst",
        "type": "pvp",
        "spells": ["paralyze", "explosion", "energy_bolt"],
        "hue": 53
    },
    "curse_dump": {
        "name": "Curse → Dump", 
        "desc": "Debuff then burst damage",
        "type": "pvp",
        "spells": ["curse", "explosion", "energy_bolt"],
        "hue": 18
    },
    "full_debuff": {
        "name": "Full Debuff",
        "desc": "Weaken + Curse + Para",
        "type": "pvp",
        "spells": ["weaken", "curse", "paralyze"],
        "hue": 63
    },
    "mana_dump": {
        "name": "Mana Dump",
        "desc": "Drain mana then burst",
        "type": "pvp",
        "spells": ["mana_drain", "explosion", "energy_bolt"],
        "hue": 88
    },
    
    # === PVE COMBOS ===
    "fs_spam": {
        "name": "Flamestrike x2",
        "desc": "Double flamestrike burst",
        "type": "pve",
        "spells": ["flamestrike", "flamestrike"],
        "hue": 38
    },
    "ebolt_spam": {
        "name": "E-Bolt x3",
        "desc": "Triple energy bolt (mana efficient)",
        "type": "pve", 
        "spells": ["energy_bolt", "energy_bolt", "energy_bolt"],
        "hue": 88
    },
    "fs_ebolt": {
        "name": "FS → E-Bolt",
        "desc": "Flamestrike + Energy Bolt",
        "type": "pve",
        "spells": ["flamestrike", "energy_bolt"],
        "hue": 48
    },
    "chain_meteor": {
        "name": "Chain + Meteor",
        "desc": "AoE combo for groups",
        "type": "pve",
        "spells": ["chain_lightning", "meteor_swarm"],
        "hue": 68
    },
    "lightning_spam": {
        "name": "Lightning x3",
        "desc": "Fast lightning spam",
        "type": "pve",
        "spells": ["lightning", "lightning", "lightning"],
        "hue": 1152
    },
    
    # === SINGLE SPELLS (for quick casting) ===
    "single_fs": {
        "name": "Flamestrike",
        "desc": "Single flamestrike",
        "type": "single",
        "spells": ["flamestrike"],
        "hue": 38
    },
    "single_ebolt": {
        "name": "Energy Bolt",
        "desc": "Single energy bolt",
        "type": "single",
        "spells": ["energy_bolt"],
        "hue": 88
    },
    "single_explo": {
        "name": "Explosion",
        "desc": "Single explosion",
        "type": "single",
        "spells": ["explosion"],
        "hue": 32
    },
}

# ============ SPELL CASTING FUNCTIONS ============
def cast_spell(spell_key, target=None):
    """Cast a single spell, optionally on a target"""
    if spell_key not in SPELLS:
        API.SysMsg(f"Unknown spell: {spell_key}", 32)
        return False
    
    spell_name, delay, needs_target = SPELLS[spell_key]
    
    API.CastSpell(spell_name)
    
    if needs_target and target:
        if API.WaitForTarget(timeout=3):
            API.Target(target)
        else:
            API.SysMsg("Target cursor timeout", 32)
            return False
    
    API.Pause(delay)
    return True

def execute_combo(combo_key, target):
    """Execute a full spell combo on target"""
    global lastTarget
    
    if combo_key not in COMBOS:
        API.SysMsg(f"Unknown combo: {combo_key}", 32)
        return
    
    combo = COMBOS[combo_key]
    spells = combo["spells"]
    
    API.SysMsg(f"Casting: {combo['name']}", combo["hue"])
    
    # Highlight target
    mob = API.FindMobile(target)
    if mob:
        mob.Hue = combo["hue"]
        lastTarget = target
    
    # Cast each spell in sequence
    for i, spell_key in enumerate(spells):
        # Check if target is still valid/alive
        mob = API.FindMobile(target)
        if not mob or mob.IsDead:
            API.SysMsg("Target dead or gone", 32)
            break
        
        # Check distance
        if mob.Distance > MAX_DISTANCE:
            API.SysMsg("Target out of range", 32)
            break
            
        cast_spell(spell_key, target)
    
    API.SysMsg("Combo complete", 68)

def find_and_attack():
    """Find nearest hostile and execute current combo"""
    enemy = API.NearestMobile(
        [API.Notoriety.Gray, API.Notoriety.Criminal, API.Notoriety.Murderer, API.Notoriety.Enemy],
        MAX_DISTANCE
    )
    
    if enemy:
        execute_combo(current_combo, enemy.Serial)
    else:
        API.SysMsg(f"No hostile targets within {MAX_DISTANCE} tiles", 32)

def attack_last_target():
    """Execute current combo on last target"""
    global lastTarget
    
    if lastTarget == 0:
        API.SysMsg("No last target set", 32)
        return
    
    mob = API.FindMobile(lastTarget)
    if mob and not mob.IsDead and mob.Distance <= MAX_DISTANCE:
        execute_combo(current_combo, lastTarget)
    else:
        API.SysMsg("Last target invalid/dead/out of range", 32)

def quick_interrupt():
    """Cast harm for quick interrupt"""
    enemy = API.NearestMobile(
        [API.Notoriety.Gray, API.Notoriety.Criminal, API.Notoriety.Murderer, API.Notoriety.Enemy],
        MAX_DISTANCE
    )
    if enemy:
        API.SysMsg("Interrupt!", 32)
        cast_spell("harm", enemy.Serial)
    else:
        API.SysMsg("No target for interrupt", 32)

def self_heal():
    """Cast greater heal on self"""
    API.CastSpell("Greater Heal")
    if API.WaitForTarget(timeout=3):
        API.TargetSelf()
    API.SysMsg("Healing self", 68)

def self_cure():
    """Cast cure on self"""
    API.CastSpell("Cure")
    if API.WaitForTarget(timeout=3):
        API.TargetSelf()
    API.SysMsg("Curing self", 68)

def cast_reflect():
    """Cast magic reflection on self"""
    API.CastSpell("Magic Reflection")
    API.Pause(1.5)
    API.SysMsg("Magic Reflect active", 88)

def cast_protection():
    """Cast protection on self"""
    API.CastSpell("Protection")
    API.Pause(1.25)
    API.SysMsg("Protection active", 63)

# ============ COMBO SELECTION ============
def select_combo(combo_key):
    """Select a combo as current"""
    global current_combo
    current_combo = combo_key
    combo = COMBOS[combo_key]
    API.SavePersistentVar(COMBO_SETTING, combo_key, API.PersistentVar.Char)
    update_combo_display()
    API.SysMsg(f"Selected: {combo['name']}", combo["hue"])

def update_combo_display():
    """Update the combo display label"""
    combo = COMBOS[current_combo]
    comboLabel.SetText(f"Active: {combo['name']}")

# ============ GUI CALLBACKS ============
def toggle_expand():
    """Toggle between collapsed and expanded states"""
    global is_expanded

    is_expanded = not is_expanded
    save_expanded_state()

    if is_expanded:
        expand_window()
    else:
        collapse_window()

def expand_window():
    """Show all controls and resize window"""
    expandBtn.SetText("[-]")

    # Show all controls except title and expand button
    hotkeyInfo.IsVisible = True
    comboLabel.IsVisible = True
    pvpLabel.IsVisible = True
    pveLabel.IsVisible = True
    singleLabel.IsVisible = True
    utilLabel.IsVisible = True

    for btn in pvp_buttons:
        btn.IsVisible = True
    for btn in pve_buttons:
        btn.IsVisible = True
    for btn in single_buttons:
        btn.IsVisible = True
    for btn in util_buttons:
        btn.IsVisible = True
    for btn in action_buttons:
        btn.IsVisible = True

    # Resize gump
    x = gump.GetX()
    y = gump.GetY()
    gump.SetRect(x, y, WINDOW_WIDTH, EXPANDED_HEIGHT)
    bg.SetRect(0, 0, WINDOW_WIDTH, EXPANDED_HEIGHT)

def collapse_window():
    """Hide all controls and shrink window"""
    expandBtn.SetText("[+]")

    # Hide all controls except title and expand button
    hotkeyInfo.IsVisible = False
    comboLabel.IsVisible = False
    pvpLabel.IsVisible = False
    pveLabel.IsVisible = False
    singleLabel.IsVisible = False
    utilLabel.IsVisible = False

    for btn in pvp_buttons:
        btn.IsVisible = False
    for btn in pve_buttons:
        btn.IsVisible = False
    for btn in single_buttons:
        btn.IsVisible = False
    for btn in util_buttons:
        btn.IsVisible = False
    for btn in action_buttons:
        btn.IsVisible = False

    # Resize gump
    x = gump.GetX()
    y = gump.GetY()
    gump.SetRect(x, y, WINDOW_WIDTH, COLLAPSED_HEIGHT)
    bg.SetRect(0, 0, WINDOW_WIDTH, COLLAPSED_HEIGHT)

# ============ BUTTON FACTORIES ============
def make_combo_selector(combo_key):
    """Factory function to create combo selector callbacks"""
    def selector():
        select_combo(combo_key)
    return selector

# ============ PERSISTENCE ============
def save_window_position():
    """Save window position to persistence using last known position"""
    global last_known_x, last_known_y
    if last_known_x >= 0 and last_known_y >= 0:
        API.SavePersistentVar(SETTINGS_KEY, f"{last_known_x},{last_known_y}", API.PersistentVar.Char)

def save_expanded_state():
    """Save expanded state to persistence"""
    API.SavePersistentVar(SETTINGS_KEY + "_Expanded", str(is_expanded), API.PersistentVar.Char)

def load_expanded_state():
    """Load expanded state from persistence"""
    global is_expanded
    saved = API.GetPersistentVar(SETTINGS_KEY + "_Expanded", "True", API.PersistentVar.Char)
    is_expanded = (saved == "True")

# ============ CLEANUP ============
def cleanup():
    """Unregister hotkeys"""
    API.OnHotKey(CAST_HOTKEY)       # Unregister
    API.OnHotKey(TARGET_HOTKEY)     # Unregister
    API.OnHotKey(INTERRUPT_HOTKEY)  # Unregister

def on_closed():
    """Handle window close event"""
    save_window_position()
    cleanup()
    API.Stop()

def stop_script():
    """Manual stop via button"""
    save_window_position()
    cleanup()
    gump.Dispose()
    API.Stop()

# ============ INITIALIZATION ============
# Load saved combo
saved_combo = API.GetPersistentVar(COMBO_SETTING, "explo_ebolt", API.PersistentVar.Char)
if saved_combo in COMBOS:
    current_combo = saved_combo

# Load expanded state BEFORE building GUI
load_expanded_state()

# ============ REGISTER HOTKEYS ============
API.OnHotKey(CAST_HOTKEY, find_and_attack)
API.OnHotKey(TARGET_HOTKEY, attack_last_target)
API.OnHotKey(INTERRUPT_HOTKEY, quick_interrupt)

# ============ BUILD GUI ============
gump = API.Gumps.CreateGump()
API.Gumps.AddControlOnDisposed(gump, on_closed)

# Load saved position
savedPos = API.GetPersistentVar(SETTINGS_KEY, "100,100", API.PersistentVar.Char)
posXY = savedPos.split(',')
last_known_x = int(posXY[0])
last_known_y = int(posXY[1])

# Set initial size based on expanded state
initial_height = EXPANDED_HEIGHT if is_expanded else COLLAPSED_HEIGHT
gump.SetRect(last_known_x, last_known_y, WINDOW_WIDTH, initial_height)

# Background
bg = API.Gumps.CreateGumpColorBox(0.9, "#1a1a2e")
bg.SetRect(0, 0, WINDOW_WIDTH, initial_height)
gump.Add(bg)

# Title (always visible)
title = API.Gumps.CreateGumpTTFLabel("⚡ Mage Combat", 16, "#ff4444", aligned="center", maxWidth=WINDOW_WIDTH)
title.SetPos(0, 5)
gump.Add(title)

# Expand/collapse button
expandBtn = API.Gumps.CreateSimpleButton("[-]" if is_expanded else "[+]", 20, 18)
expandBtn.SetPos(255, 3)
expandBtn.SetBackgroundHue(90)
API.Gumps.AddControlOnClick(expandBtn, toggle_expand)
gump.Add(expandBtn)

# Hotkey info (hidden when collapsed)
hotkeyInfo = API.Gumps.CreateGumpTTFLabel(f"Cast: {CAST_HOTKEY} | Last: {TARGET_HOTKEY} | Int: {INTERRUPT_HOTKEY}", 15, "#666666", aligned="center", maxWidth=WINDOW_WIDTH)
hotkeyInfo.SetPos(0, 28)
hotkeyInfo.IsVisible = is_expanded
gump.Add(hotkeyInfo)

# Current combo display (hidden when collapsed)
comboLabel = API.Gumps.CreateGumpTTFLabel(f"Active: {COMBOS[current_combo]['name']}", 15, "#00ff00", aligned="center", maxWidth=WINDOW_WIDTH)
comboLabel.SetPos(0, 45)
comboLabel.IsVisible = is_expanded
gump.Add(comboLabel)

# Layout constants
btnWidth = 88
btnHeight = 22
col1X = 5
col2X = 96
col3X = 187
startY = 70

# === PVP SECTION ===
pvpLabel = API.Gumps.CreateGumpTTFLabel("═══ PVP COMBOS ═══", 15, "#ff6666", aligned="center", maxWidth=WINDOW_WIDTH)
pvpLabel.SetPos(0, startY)
pvpLabel.IsVisible = is_expanded
gump.Add(pvpLabel)

# Track buttons for visibility control
pvp_buttons = []
y = startY + 18
pvp_combos = [(k, v) for k, v in COMBOS.items() if v["type"] == "pvp"]
for i, (key, combo) in enumerate(pvp_combos):
    col = i % 3
    row = i // 3
    x = col1X + (col * 91)
    btn = API.Gumps.CreateSimpleButton(f"[{combo['name'][:10]}]", btnWidth, btnHeight)
    btn.SetPos(x, y + (row * 25))
    btn.SetBackgroundHue(combo["hue"])
    btn.IsVisible = is_expanded
    API.Gumps.AddControlOnClick(btn, make_combo_selector(key))
    gump.Add(btn)
    pvp_buttons.append(btn)

# === PVE SECTION ===
pveY = startY + 75
pveLabel = API.Gumps.CreateGumpTTFLabel("═══ PVE COMBOS ═══", 15, "#66ff66", aligned="center", maxWidth=WINDOW_WIDTH)
pveLabel.SetPos(0, pveY)
pveLabel.IsVisible = is_expanded
gump.Add(pveLabel)

pve_buttons = []
y = pveY + 18
pve_combos = [(k, v) for k, v in COMBOS.items() if v["type"] == "pve"]
for i, (key, combo) in enumerate(pve_combos):
    col = i % 3
    row = i // 3
    x = col1X + (col * 91)
    btn = API.Gumps.CreateSimpleButton(f"[{combo['name'][:10]}]", btnWidth, btnHeight)
    btn.SetPos(x, y + (row * 25))
    btn.SetBackgroundHue(combo["hue"])
    btn.IsVisible = is_expanded
    API.Gumps.AddControlOnClick(btn, make_combo_selector(key))
    gump.Add(btn)
    pve_buttons.append(btn)

# === SINGLE SPELLS SECTION ===
singleY = pveY + 80
singleLabel = API.Gumps.CreateGumpTTFLabel("═══ SINGLE SPELLS ═══", 15, "#6666ff", aligned="center", maxWidth=WINDOW_WIDTH)
singleLabel.SetPos(0, singleY)
singleLabel.IsVisible = is_expanded
gump.Add(singleLabel)

single_buttons = []
y = singleY + 18
single_combos = [(k, v) for k, v in COMBOS.items() if v["type"] == "single"]
for i, (key, combo) in enumerate(single_combos):
    col = i % 3
    x = col1X + (col * 91)
    btn = API.Gumps.CreateSimpleButton(f"[{combo['name'][:10]}]", btnWidth, btnHeight)
    btn.SetPos(x, y)
    btn.SetBackgroundHue(combo["hue"])
    btn.IsVisible = is_expanded
    API.Gumps.AddControlOnClick(btn, make_combo_selector(key))
    gump.Add(btn)
    single_buttons.append(btn)

# === UTILITY SECTION ===
utilY = singleY + 50
utilLabel = API.Gumps.CreateGumpTTFLabel("═══ UTILITY ═══", 15, "#ffff66", aligned="center", maxWidth=WINDOW_WIDTH)
utilLabel.SetPos(0, utilY)
utilLabel.IsVisible = is_expanded
gump.Add(utilLabel)

util_buttons = []
y = utilY + 18

healBtn = API.Gumps.CreateSimpleButton("[HEAL SELF]", btnWidth, btnHeight)
healBtn.SetPos(col1X, y)
healBtn.SetBackgroundHue(68)
healBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(healBtn, self_heal)
gump.Add(healBtn)
util_buttons.append(healBtn)

cureBtn = API.Gumps.CreateSimpleButton("[CURE SELF]", btnWidth, btnHeight)
cureBtn.SetPos(col2X, y)
cureBtn.SetBackgroundHue(63)
cureBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(cureBtn, self_cure)
gump.Add(cureBtn)
util_buttons.append(cureBtn)

reflectBtn = API.Gumps.CreateSimpleButton("[REFLECT]", btnWidth, btnHeight)
reflectBtn.SetPos(col3X, y)
reflectBtn.SetBackgroundHue(88)
reflectBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(reflectBtn, cast_reflect)
gump.Add(reflectBtn)
util_buttons.append(reflectBtn)

y += 25

protectBtn = API.Gumps.CreateSimpleButton("[PROTECT]", btnWidth, btnHeight)
protectBtn.SetPos(col1X, y)
protectBtn.SetBackgroundHue(53)
protectBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(protectBtn, cast_protection)
gump.Add(protectBtn)
util_buttons.append(protectBtn)

interruptBtn = API.Gumps.CreateSimpleButton("[INTERRUPT]", btnWidth, btnHeight)
interruptBtn.SetPos(col2X, y)
interruptBtn.SetBackgroundHue(32)
interruptBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(interruptBtn, quick_interrupt)
gump.Add(interruptBtn)
util_buttons.append(interruptBtn)

# === ACTION BUTTONS ===
action_buttons = []
actionY = y + 35

castBtn = API.Gumps.CreateSimpleButton("[CAST NEAREST]", 133, 25)
castBtn.SetPos(col1X, actionY)
castBtn.SetBackgroundHue(32)
castBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(castBtn, find_and_attack)
gump.Add(castBtn)
action_buttons.append(castBtn)

lastBtn = API.Gumps.CreateSimpleButton("[CAST LAST]", 133, 25)
lastBtn.SetPos(142, actionY)
lastBtn.SetBackgroundHue(53)
lastBtn.IsVisible = is_expanded
API.Gumps.AddControlOnClick(lastBtn, attack_last_target)
gump.Add(lastBtn)
action_buttons.append(lastBtn)

API.Gumps.AddGump(gump)

# Apply initial expanded/collapsed state
if not is_expanded:
    collapse_window()

API.SysMsg(f"Mage Combat loaded! Combo: {COMBOS[current_combo]['name']}", 68)
API.SysMsg(f"Hotkeys: {CAST_HOTKEY} = Cast | {TARGET_HOTKEY} = Last Target | {INTERRUPT_HOTKEY} = Interrupt", 88)

# Main loop
while True:
    try:
        API.ProcessCallbacks()

        # Periodically capture window position (every 2 seconds)
        current_time = time.time()
        if current_time - last_position_check > 2.0:
            if not API.StopRequested:
                try:
                    x = gump.GetX()
                    y = gump.GetY()
                    if x >= 0 and y >= 0:
                        last_known_x = x
                        last_known_y = y
                except:
                    pass
            last_position_check = current_time

        API.Pause(0.1)
    except Exception as e:
        # Suppress "operation canceled" during shutdown
        if "canceled" not in str(e).lower():
            API.SysMsg(f"Error: {e}", 32)
        API.Pause(0.1)