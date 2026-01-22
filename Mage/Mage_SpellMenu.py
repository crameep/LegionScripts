# ============================================================
# Mage Spell Menu v1.2
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
#
# Hotkeys: CTRL+M (cast combo), CTRL+SHIFT+M (last target),
#          CTRL+I (interrupt)
#
# ============================================================
import API
import time

__version__ = "1.2"

# ============ USER SETTINGS ============
MAX_DISTANCE = 12
CAST_HOTKEY = "CTRL+M"           # Execute selected combo on nearest hostile
TARGET_HOTKEY = "CTRL+SHIFT+M"   # Execute selected combo on last target
INTERRUPT_HOTKEY = "CTRL+I"      # Quick interrupt (Harm)
# =======================================

SETTINGS_KEY = "mage_combat_xy"
COMBO_SETTING = "mage_combat_combo"

# Current combo selection
current_combo = "explo_ebolt"
lastTarget = 0

# GUI position tracking (for improved position saving)
last_known_x = 100
last_known_y = 100
last_position_check = 0

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

# ============ GUI BUTTON FACTORIES ============
def make_combo_selector(combo_key):
    """Factory function to create combo selector callbacks"""
    def selector():
        select_combo(combo_key)
    return selector

# ============ SCRIPT CONTROL ============
def stop_script():
    """Clean up and stop"""
    global last_known_x, last_known_y
    # Save last known good position (validated as non-negative)
    if last_known_x >= 0 and last_known_y >= 0:
        API.SavePersistentVar(SETTINGS_KEY, f"{last_known_x},{last_known_y}", API.PersistentVar.Char)
    API.OnHotKey(CAST_HOTKEY)       # Unregister
    API.OnHotKey(TARGET_HOTKEY)     # Unregister
    API.OnHotKey(INTERRUPT_HOTKEY)  # Unregister
    gump.Dispose()
    API.Stop()

# ============ LOAD SETTINGS ============
saved_combo = API.GetPersistentVar(COMBO_SETTING, "explo_ebolt", API.PersistentVar.Char)
if saved_combo in COMBOS:
    current_combo = saved_combo

# ============ REGISTER HOTKEYS ============
API.OnHotKey(CAST_HOTKEY, find_and_attack)
API.OnHotKey(TARGET_HOTKEY, attack_last_target)
API.OnHotKey(INTERRUPT_HOTKEY, quick_interrupt)

# ============ BUILD GUI ============
gump = API.Gumps.CreateGump()

savedPos = API.GetPersistentVar(SETTINGS_KEY, "100,100", API.PersistentVar.Char)
posXY = savedPos.split(',')
last_known_x = int(posXY[0])
last_known_y = int(posXY[1])
gump.SetRect(last_known_x, last_known_y, 280, 400)

# Background
bg = API.Gumps.CreateGumpColorBox(0.9, "#1a1a2e").SetRect(0, 0, 280, 400)
gump.Add(bg)

# Title
title = API.Gumps.CreateGumpTTFLabel("⚡ Mage Combat", 16, "#ff4444", aligned="center", maxWidth=280)
title.SetPos(0, 5)
gump.Add(title)

# Hotkey info
hotkeyInfo = API.Gumps.CreateGumpTTFLabel(f"Cast: {CAST_HOTKEY} | Last: {TARGET_HOTKEY} | Int: {INTERRUPT_HOTKEY}", 9, "#666666", aligned="center", maxWidth=280)
hotkeyInfo.SetPos(0, 28)
gump.Add(hotkeyInfo)

# Current combo display
comboLabel = API.Gumps.CreateGumpTTFLabel(f"Active: {COMBOS[current_combo]['name']}", 13, "#00ff00", aligned="center", maxWidth=280)
comboLabel.SetPos(0, 45)
gump.Add(comboLabel)

# Layout constants
btnWidth = 88
btnHeight = 22
col1X = 5
col2X = 96
col3X = 187
startY = 70

# === PVP SECTION ===
pvpLabel = API.Gumps.CreateGumpTTFLabel("═══ PVP COMBOS ═══", 11, "#ff6666", aligned="center", maxWidth=280)
pvpLabel.SetPos(0, startY)
gump.Add(pvpLabel)

y = startY + 18
pvp_combos = [(k, v) for k, v in COMBOS.items() if v["type"] == "pvp"]
for i, (key, combo) in enumerate(pvp_combos):
    col = i % 3
    row = i // 3
    x = col1X + (col * 91)
    btn = API.Gumps.CreateSimpleButton(f"[{combo['name'][:10]}]", btnWidth, btnHeight)
    btn.SetPos(x, y + (row * 25))
    btn.SetBackgroundHue(combo["hue"])
    API.Gumps.AddControlOnClick(btn, make_combo_selector(key))
    gump.Add(btn)

# === PVE SECTION ===
pveY = startY + 75
pveLabel = API.Gumps.CreateGumpTTFLabel("═══ PVE COMBOS ═══", 11, "#66ff66", aligned="center", maxWidth=280)
pveLabel.SetPos(0, pveY)
gump.Add(pveLabel)

y = pveY + 18
pve_combos = [(k, v) for k, v in COMBOS.items() if v["type"] == "pve"]
for i, (key, combo) in enumerate(pve_combos):
    col = i % 3
    row = i // 3
    x = col1X + (col * 91)
    btn = API.Gumps.CreateSimpleButton(f"[{combo['name'][:10]}]", btnWidth, btnHeight)
    btn.SetPos(x, y + (row * 25))
    btn.SetBackgroundHue(combo["hue"])
    API.Gumps.AddControlOnClick(btn, make_combo_selector(key))
    gump.Add(btn)

# === SINGLE SPELLS SECTION ===
singleY = pveY + 80
singleLabel = API.Gumps.CreateGumpTTFLabel("═══ SINGLE SPELLS ═══", 11, "#6666ff", aligned="center", maxWidth=280)
singleLabel.SetPos(0, singleY)
gump.Add(singleLabel)

y = singleY + 18
single_combos = [(k, v) for k, v in COMBOS.items() if v["type"] == "single"]
for i, (key, combo) in enumerate(single_combos):
    col = i % 3
    x = col1X + (col * 91)
    btn = API.Gumps.CreateSimpleButton(f"[{combo['name'][:10]}]", btnWidth, btnHeight)
    btn.SetPos(x, y)
    btn.SetBackgroundHue(combo["hue"])
    API.Gumps.AddControlOnClick(btn, make_combo_selector(key))
    gump.Add(btn)

# === UTILITY SECTION ===
utilY = singleY + 50
utilLabel = API.Gumps.CreateGumpTTFLabel("═══ UTILITY ═══", 11, "#ffff66", aligned="center", maxWidth=280)
utilLabel.SetPos(0, utilY)
gump.Add(utilLabel)

y = utilY + 18

healBtn = API.Gumps.CreateSimpleButton("[HEAL SELF]", btnWidth, btnHeight)
healBtn.SetPos(col1X, y)
healBtn.SetBackgroundHue(68)
API.Gumps.AddControlOnClick(healBtn, self_heal)
gump.Add(healBtn)

cureBtn = API.Gumps.CreateSimpleButton("[CURE SELF]", btnWidth, btnHeight)
cureBtn.SetPos(col2X, y)
cureBtn.SetBackgroundHue(63)
API.Gumps.AddControlOnClick(cureBtn, self_cure)
gump.Add(cureBtn)

reflectBtn = API.Gumps.CreateSimpleButton("[REFLECT]", btnWidth, btnHeight)
reflectBtn.SetPos(col3X, y)
reflectBtn.SetBackgroundHue(88)
API.Gumps.AddControlOnClick(reflectBtn, cast_reflect)
gump.Add(reflectBtn)

y += 25

protectBtn = API.Gumps.CreateSimpleButton("[PROTECT]", btnWidth, btnHeight)
protectBtn.SetPos(col1X, y)
protectBtn.SetBackgroundHue(53)
API.Gumps.AddControlOnClick(protectBtn, cast_protection)
gump.Add(protectBtn)

interruptBtn = API.Gumps.CreateSimpleButton("[INTERRUPT]", btnWidth, btnHeight)
interruptBtn.SetPos(col2X, y)
interruptBtn.SetBackgroundHue(32)
API.Gumps.AddControlOnClick(interruptBtn, quick_interrupt)
gump.Add(interruptBtn)

# === ACTION BUTTONS ===
actionY = y + 35

castBtn = API.Gumps.CreateSimpleButton("[CAST NEAREST]", 133, 25)
castBtn.SetPos(col1X, actionY)
castBtn.SetBackgroundHue(32)
API.Gumps.AddControlOnClick(castBtn, find_and_attack)
gump.Add(castBtn)

lastBtn = API.Gumps.CreateSimpleButton("[CAST LAST]", 133, 25)
lastBtn.SetPos(142, actionY)
lastBtn.SetBackgroundHue(53)
API.Gumps.AddControlOnClick(lastBtn, attack_last_target)
gump.Add(lastBtn)

API.Gumps.AddGump(gump)

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