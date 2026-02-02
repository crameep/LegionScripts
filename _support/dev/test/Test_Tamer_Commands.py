# ============================================================
# Pet Commands v3.0 (Experimental)
# by Coryigon for UO Unchained
# ============================================================
#
# EXPERIMENTAL VERSION - Testing new features before merging
# into the stable commands script. May have bugs or incomplete features.
#
# Based on Pet Commands v3 with additional experimental features:
#   - Enhanced pet sync system
#   - Extended ORDER mode options
#
# See Tamer_Commands_v3.py for the stable version.
#
# ============================================================
import API
import time

__version__ = "3.0"

# ============ USER SETTINGS ============
MAX_DISTANCE = 10             # Max distance to search for hostiles
SHOW_RADIUS_INDICATOR = True  # Show range circle around player
TARGET_TIMEOUT = 3.0          # Seconds to wait for target cursor
COMMAND_DELAY = 0.8           # Delay between pet commands in ORDER mode (increased)
MAX_ATTACK_PETS = 5           # Maximum pets in attack order list

# Hotkeys (set to "" to disable)
ALL_KILL_HOTKEY = "TAB"       # All Kill - finds nearest hostile or gives target cursor
GUARD_HOTKEY = "1"            # Guard Me
FOLLOW_HOTKEY = "2"           # Follow Me
STAY_HOTKEY = ""              # All Stay (disabled by default)
# =======================================

# Persistent storage keys
SETTINGS_KEY = "TamerCmd_XY"
REDS_KEY = "TamerCmd_Reds"
GRAYS_KEY = "TamerCmd_Grays"
MODE_KEY = "TamerCmd_Mode"
PETS_KEY = "SharedPets_List"      # SHARED with Pet Healer! Format: "name:serial:active|..."

# Auto-sync with Pet Healer
PET_SYNC_INTERVAL = 2.0           # How often to check for pet list changes (seconds)
last_known_pets_str = ""          # Track last known pet string for sync detection

# Runtime state - target toggles
TARGET_REDS = False           # Target murderers (red)
TARGET_GRAYS = False          # Target gray/criminal/enemy

# Attack mode: "ALL" = all kill, "ORDER" = individual pet commands
ATTACK_MODE = "ALL"

# Ordered pet list: [{name, serial, active}, ...]
ATTACK_PETS = []

# GUI elements for pet list (will be populated later)
pet_rows = []  # List of {label, toggleBtn, index}
selected_pet_index = -1

# ============ UTILITY FUNCTIONS ============
def safe_get_name(mobile):
    """Safely get mobile name"""
    if not mobile:
        return "Unknown"
    try:
        return mobile.Name if mobile.Name else "Unknown"
    except:
        return "Unknown"

def get_pet_display_name(pet_data):
    """Get display name for pet (truncated if needed)"""
    name = pet_data.get("name", "Unknown")
    if len(name) > 12:
        return name[:11] + "."
    return name

# ============ PERSISTENCE ============
def save_pets():
    """Save pet list to persistent storage"""
    global last_known_pets_str
    # Format: name:serial:active|name:serial:active|...
    parts = []
    for pet in ATTACK_PETS:
        active_str = "1" if pet.get("active", True) else "0"
        # Escape special chars in name
        safe_name = pet["name"].replace("|", "_").replace(":", "_")
        parts.append(safe_name + ":" + str(pet["serial"]) + ":" + active_str)
    
    pets_str = "|".join(parts)
    last_known_pets_str = pets_str  # Track what we saved
    API.SavePersistentVar(PETS_KEY, pets_str, API.PersistentVar.Char)

def load_pets():
    """Load pet list from persistent storage"""
    global ATTACK_PETS, last_known_pets_str
    ATTACK_PETS = []
    
    pets_str = API.GetPersistentVar(PETS_KEY, "", API.PersistentVar.Char)
    last_known_pets_str = pets_str  # Track for auto-sync
    if not pets_str:
        return
    
    for part in pets_str.split("|"):
        if not part:
            continue
        try:
            pieces = part.split(":")
            if len(pieces) >= 2:
                # Handle both formats: name:serial:active and name:serial
                active = True
                if len(pieces) >= 3:
                    active = pieces[2] == "1"
                ATTACK_PETS.append({
                    "name": pieces[0],
                    "serial": int(pieces[1]),
                    "active": active
                })
        except:
            pass

def sync_pets_from_storage():
    """Check if pet list changed externally and reload if needed"""
    global ATTACK_PETS, last_known_pets_str
    
    current_str = API.GetPersistentVar(PETS_KEY, "", API.PersistentVar.Char)
    
    # If unchanged, nothing to do
    if current_str == last_known_pets_str:
        return False
    
    # Pet list changed externally! Reload it
    old_count = len(ATTACK_PETS)
    ATTACK_PETS = []
    
    if current_str:
        for part in current_str.split("|"):
            if not part:
                continue
            try:
                pieces = part.split(":")
                if len(pieces) >= 2:
                    active = True
                    if len(pieces) >= 3:
                        active = pieces[2] == "1"
                    ATTACK_PETS.append({
                        "name": pieces[0],
                        "serial": int(pieces[1]),
                        "active": active
                    })
            except:
                pass
    
    last_known_pets_str = current_str
    
    # Notify user if list changed
    new_count = len(ATTACK_PETS)
    if old_count != new_count:
        API.SysMsg("Pet list synced: " + str(new_count) + " pets", 66)
        update_pet_display()
    
    return True

def save_mode():
    """Save attack mode"""
    API.SavePersistentVar(MODE_KEY, ATTACK_MODE, API.PersistentVar.Char)

def load_mode():
    """Load attack mode"""
    global ATTACK_MODE
    ATTACK_MODE = API.GetPersistentVar(MODE_KEY, "ALL", API.PersistentVar.Char)
    if ATTACK_MODE not in ["ALL", "ORDER"]:
        ATTACK_MODE = "ALL"

# ============ PET LIST MANAGEMENT ============
def add_attack_pet():
    """Target a pet to add to the attack order list"""
    if len(ATTACK_PETS) >= MAX_ATTACK_PETS:
        API.SysMsg("Maximum " + str(MAX_ATTACK_PETS) + " pets in attack list!", 32)
        return
    
    API.SysMsg("Target a pet to add to attack order...", 68)
    
    target = API.RequestTarget(timeout=10)
    if not target:
        API.SysMsg("Targeting cancelled", 32)
        return
    
    mob = API.FindMobile(target)
    if not mob:
        API.SysMsg("Not a valid mobile!", 32)
        return
    
    # Check if already in list
    for pet in ATTACK_PETS:
        if pet["serial"] == target:
            API.SysMsg(safe_get_name(mob) + " is already in the list!", 32)
            return
    
    # Add to list
    pet_name = safe_get_name(mob)
    ATTACK_PETS.append({
        "name": pet_name,
        "serial": target,
        "active": True
    })
    
    save_pets()
    update_pet_display()
    API.SysMsg("Added: " + pet_name + " (#" + str(len(ATTACK_PETS)) + ")", 68)

def remove_attack_pet():
    """Remove selected pet from attack order list"""
    global selected_pet_index
    
    if not ATTACK_PETS:
        API.SysMsg("No pets to remove!", 32)
        return
    
    if selected_pet_index < 0 or selected_pet_index >= len(ATTACK_PETS):
        API.SysMsg("Select a pet first (click the name)", 32)
        return
    
    removed = ATTACK_PETS.pop(selected_pet_index)
    selected_pet_index = -1
    
    save_pets()
    update_pet_display()
    API.SysMsg("Removed: " + removed["name"], 68)

def move_pet_up():
    """Move selected pet up in the order"""
    global selected_pet_index
    
    if selected_pet_index <= 0:
        return
    
    # Swap with previous
    ATTACK_PETS[selected_pet_index], ATTACK_PETS[selected_pet_index - 1] = \
        ATTACK_PETS[selected_pet_index - 1], ATTACK_PETS[selected_pet_index]
    
    selected_pet_index -= 1
    save_pets()
    update_pet_display()

def move_pet_down():
    """Move selected pet down in the order"""
    global selected_pet_index
    
    if selected_pet_index < 0 or selected_pet_index >= len(ATTACK_PETS) - 1:
        return
    
    # Swap with next
    ATTACK_PETS[selected_pet_index], ATTACK_PETS[selected_pet_index + 1] = \
        ATTACK_PETS[selected_pet_index + 1], ATTACK_PETS[selected_pet_index]
    
    selected_pet_index += 1
    save_pets()
    update_pet_display()

def toggle_pet_active(index):
    """Toggle a pet's active status"""
    if index < 0 or index >= len(ATTACK_PETS):
        return
    
    ATTACK_PETS[index]["active"] = not ATTACK_PETS[index]["active"]
    save_pets()
    update_pet_display()
    
    status = "ON" if ATTACK_PETS[index]["active"] else "OFF"
    API.SysMsg(ATTACK_PETS[index]["name"] + " attack: " + status, 68)

def select_pet(index):
    """Select a pet for reordering"""
    global selected_pet_index
    selected_pet_index = index
    update_pet_display()

def pet_follow_by_click(index):
    """Send follow command to a specific pet by clicking its button"""
    global selected_pet_index
    
    if index >= len(ATTACK_PETS):
        return
    
    pet = ATTACK_PETS[index]
    name = pet["name"]
    serial = pet["serial"]
    
    # Also select this pet for UP/DOWN reordering
    selected_pet_index = index
    update_pet_display()
    
    # Verify pet exists
    mob = API.FindMobile(serial)
    if not mob:
        API.SysMsg(name + " not found!", 32)
        return
    
    # Send follow command by name
    API.Msg(name + " follow me")
    API.SysMsg(name + " follow!", 68)
    API.HeadMsg("Follow!", serial, 68)

# Create toggle/select callback closures
def make_toggle_callback(idx):
    def callback():
        toggle_pet_active(idx)
    return callback

def make_select_callback(idx):
    def callback():
        pet_follow_by_click(idx)  # Click = follow + select
    return callback

# ============ PET COMMANDS ============
def find_attack_target():
    """Find nearest hostile based on current settings, returns serial or None"""
    # Show range indicator
    if SHOW_RADIUS_INDICATOR:
        API.DisplayRange(MAX_DISTANCE)
    
    # Build notoriety list - always include monsters (Enemy)
    notorieties = [API.Notoriety.Enemy]
    
    if TARGET_GRAYS:
        notorieties.append(API.Notoriety.Gray)
        notorieties.append(API.Notoriety.Criminal)
    
    if TARGET_REDS:
        notorieties.append(API.Notoriety.Murderer)
    
    enemy = API.NearestMobile(notorieties, MAX_DISTANCE)
    
    # Make sure we never target self
    if enemy:
        try:
            if enemy.Serial == API.Player.Serial:
                enemy = None
        except:
            pass
    
    API.DisplayRange(0)
    return enemy

def all_kill():
    """Main attack command - uses ALL or ORDER mode based on setting"""
    if ATTACK_MODE == "ORDER" and ATTACK_PETS:
        ordered_kill()
    else:
        all_kill_classic()

def all_kill_classic():
    """Classic 'all kill' command"""
    try:
        if SHOW_RADIUS_INDICATOR:
            API.DisplayRange(MAX_DISTANCE)
        
        enemy = find_attack_target()
        
        if enemy:
            API.Msg("all kill")
            if API.WaitForTarget(timeout=TARGET_TIMEOUT):
                API.Target(enemy)
                API.HeadMsg("KILL!", enemy, 32)
                API.SysMsg("All pets attacking: " + safe_get_name(enemy), 68)
            else:
                API.SysMsg("No target cursor received", 32)
        else:
            API.SysMsg("No hostile nearby - select target manually", 53)
            API.Msg("all kill")
        
        API.DisplayRange(0)
        
    except Exception as e:
        API.DisplayRange(0)
        API.SysMsg("Error: " + str(e), 32)

def ordered_kill():
    """Send each active pet to attack in order by name"""
    try:
        # Count active pets
        active_pets = [p for p in ATTACK_PETS if p.get("active", True)]
        
        if not active_pets:
            API.SysMsg("No active pets in attack order! Using 'all kill'", 43)
            all_kill_classic()
            return
        
        # Find target first
        enemy = find_attack_target()
        target_serial = None
        
        if enemy:
            target_serial = enemy.Serial
            API.HeadMsg("KILL!", enemy, 32)
            API.SysMsg("Ordered attack: " + safe_get_name(enemy), 68)
        else:
            # No auto-target found, get manual target
            API.SysMsg("No hostile nearby - select target for ordered attack", 53)
            
            # Request manual target first
            manual_target = API.RequestTarget(timeout=TARGET_TIMEOUT)
            if manual_target:
                target_serial = manual_target
                mob = API.FindMobile(manual_target)
                if mob:
                    API.HeadMsg("KILL!", manual_target, 32)
                API.SysMsg("Ordered attack on selected target", 68)
            else:
                API.SysMsg("No target selected", 32)
                return
        
        # Send each active pet to attack
        for i, pet in enumerate(active_pets):
            pet_name = pet["name"]
            
            # Delay BEFORE command (except first one)
            if i > 0:
                API.Pause(COMMAND_DELAY)
            
            # Say the command
            API.Msg(pet_name + " kill")
            API.SysMsg("  " + str(i + 1) + ". " + pet_name + " -> attack", 88)
            
            # Wait for target cursor to appear
            if API.WaitForTarget(timeout=2.0):
                API.Target(target_serial)
            else:
                API.SysMsg("  " + pet_name + " - no target cursor", 43)
            
            # Small pause after targeting to let it register
            API.Pause(0.2)
        
        API.SysMsg("Ordered attack complete (" + str(len(active_pets)) + " pets)", 68)
        
    except Exception as e:
        API.DisplayRange(0)
        API.SysMsg("Error in ordered attack: " + str(e), 32)

def all_follow():
    if ATTACK_MODE == "ORDER" and ATTACK_PETS:
        ordered_command("follow me", "Follow")
    else:
        API.Msg("all follow me")
        API.SysMsg("Pets: Follow Me", 88)

def all_guard():
    if ATTACK_MODE == "ORDER" and ATTACK_PETS:
        ordered_command("guard me", "Guard")
    else:
        API.Msg("all guard me")
        API.SysMsg("Pets: Guard Me", 88)

def all_stay():
    if ATTACK_MODE == "ORDER" and ATTACK_PETS:
        ordered_command("stay", "Stay")
    else:
        API.Msg("all stay")
        API.SysMsg("Pets: Stay", 88)

def ordered_command(command, display_name):
    """Send a command to each active pet by name"""
    active_pets = [p for p in ATTACK_PETS if p.get("active", True)]
    
    if not active_pets:
        API.Msg("all " + command)
        API.SysMsg("Pets: " + display_name, 88)
        return
    
    for i, pet in enumerate(active_pets):
        pet_name = pet["name"]
        
        # Delay before command (except first)
        if i > 0:
            API.Pause(COMMAND_DELAY)
        
        API.Msg(pet_name + " " + command)
    
    API.SysMsg("Ordered " + display_name + " (" + str(len(active_pets)) + " pets)", 88)

def stable_pets():
    API.Msg("stable")
    API.SysMsg("Requesting stable...", 88)

def claim_pets():
    API.Msg("claim list")
    API.SysMsg("Requesting claim list...", 88)

# ============ TOGGLE FUNCTIONS ============
def toggle_reds():
    global TARGET_REDS
    TARGET_REDS = not TARGET_REDS
    API.SavePersistentVar(REDS_KEY, "True" if TARGET_REDS else "False", API.PersistentVar.Char)
    redsBtn.SetText("[REDS:" + ("ON" if TARGET_REDS else "OFF") + "]")
    redsBtn.SetBackgroundHue(32 if TARGET_REDS else 90)
    status = "ON" if TARGET_REDS else "OFF"
    API.SysMsg("Target Murderers: " + status, 32 if TARGET_REDS else 90)

def toggle_grays():
    global TARGET_GRAYS
    TARGET_GRAYS = not TARGET_GRAYS
    API.SavePersistentVar(GRAYS_KEY, "True" if TARGET_GRAYS else "False", API.PersistentVar.Char)
    graysBtn.SetText("[GRAYS:" + ("ON" if TARGET_GRAYS else "OFF") + "]")
    graysBtn.SetBackgroundHue(53 if TARGET_GRAYS else 90)
    status = "ON" if TARGET_GRAYS else "OFF"
    API.SysMsg("Target Grays/Criminals: " + status, 53 if TARGET_GRAYS else 90)

def toggle_attack_mode():
    global ATTACK_MODE
    ATTACK_MODE = "ORDER" if ATTACK_MODE == "ALL" else "ALL"
    save_mode()
    update_mode_display()
    API.SysMsg("Attack Mode: " + ATTACK_MODE, 68)

def update_mode_display():
    if ATTACK_MODE == "ALL":
        modeBtn.SetText("[MODE: ALL]")
        modeBtn.SetBackgroundHue(68)
    else:
        modeBtn.SetText("[MODE: ORDER]")
        modeBtn.SetBackgroundHue(38)

# ============ DISPLAY UPDATES ============
def update_pet_display():
    """Update the pet list display"""
    for i, row in enumerate(pet_rows):
        if i < len(ATTACK_PETS):
            pet = ATTACK_PETS[i]
            name = get_pet_display_name(pet)
            
            # Check if pet still exists
            mob = API.FindMobile(pet["serial"])
            exists_marker = "" if mob else "?"
            
            # Selection indicator
            sel_marker = ">" if i == selected_pet_index else " "
            
            # Update label
            row["label"].SetText(sel_marker + str(i + 1) + "." + name + exists_marker)
            
            # Update toggle button
            if pet.get("active", True):
                row["toggleBtn"].SetText("[ON]")
                row["toggleBtn"].SetBackgroundHue(68)
            else:
                row["toggleBtn"].SetText("[--]")
                row["toggleBtn"].SetBackgroundHue(32)
        else:
            row["label"].SetText("  " + str(i + 1) + ". ---")
            row["toggleBtn"].SetText("[--]")
            row["toggleBtn"].SetBackgroundHue(90)

# ============ CLEANUP ============
def cleanup():
    if ALL_KILL_HOTKEY:
        API.OnHotKey(ALL_KILL_HOTKEY)
    if GUARD_HOTKEY:
        API.OnHotKey(GUARD_HOTKEY)
    if FOLLOW_HOTKEY:
        API.OnHotKey(FOLLOW_HOTKEY)
    if STAY_HOTKEY:
        API.OnHotKey(STAY_HOTKEY)
    API.DisplayRange(0)

def onClosed():
    cleanup()
    API.SavePersistentVar(SETTINGS_KEY, str(gump.GetX()) + "," + str(gump.GetY()), API.PersistentVar.Char)
    API.Stop()

def stop_script():
    cleanup()
    API.SavePersistentVar(SETTINGS_KEY, str(gump.GetX()) + "," + str(gump.GetY()), API.PersistentVar.Char)
    gump.Dispose()
    API.Stop()

# ============ LOAD SETTINGS ============
def load_settings():
    global TARGET_REDS, TARGET_GRAYS
    
    reds = API.GetPersistentVar(REDS_KEY, "False", API.PersistentVar.Char)
    TARGET_REDS = (reds == "True")
    
    grays = API.GetPersistentVar(GRAYS_KEY, "False", API.PersistentVar.Char)
    TARGET_GRAYS = (grays == "True")

load_settings()
load_mode()
load_pets()

# ============ REGISTER HOTKEYS ============
if ALL_KILL_HOTKEY:
    API.OnHotKey(ALL_KILL_HOTKEY, all_kill)
if GUARD_HOTKEY:
    API.OnHotKey(GUARD_HOTKEY, all_guard)
if FOLLOW_HOTKEY:
    API.OnHotKey(FOLLOW_HOTKEY, all_follow)
if STAY_HOTKEY:
    API.OnHotKey(STAY_HOTKEY, all_stay)

# ============ BUILD GUI ============
gump = API.Gumps.CreateGump()
API.Gumps.AddControlOnDisposed(gump, onClosed)

savedPos = API.GetPersistentVar(SETTINGS_KEY, "100,100", API.PersistentVar.Char)
posXY = savedPos.split(',')
gump.SetRect(int(posXY[0]), int(posXY[1]), 200, 380)

bg = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
bg.SetRect(0, 0, 200, 380)
gump.Add(bg)

title = API.Gumps.CreateGumpTTFLabel("Pet Commands v3", 16, "#00d4ff", aligned="center", maxWidth=200)
title.SetPos(0, 5)
gump.Add(title)

hotkeyText = "Kill:" + (ALL_KILL_HOTKEY if ALL_KILL_HOTKEY else "-")
hotkeyText += " | Guard:" + (GUARD_HOTKEY if GUARD_HOTKEY else "-")
hotkeyText += " | Follow:" + (FOLLOW_HOTKEY if FOLLOW_HOTKEY else "-")
hotkeyLabel = API.Gumps.CreateGumpTTFLabel(hotkeyText, 9, "#888888", aligned="center", maxWidth=200)
hotkeyLabel.SetPos(0, 24)
gump.Add(hotkeyLabel)

# Target type section
targetLabel = API.Gumps.CreateGumpTTFLabel("=== TARGET TYPES ===", 9, "#ff8800", aligned="center", maxWidth=200)
targetLabel.SetPos(0, 42)
gump.Add(targetLabel)

buttonWidth = 90
buttonHeight = 22
col1X = 5
col2X = 105
startY = 58

redsBtn = API.Gumps.CreateSimpleButton("[REDS:" + ("ON" if TARGET_REDS else "OFF") + "]", buttonWidth, buttonHeight)
redsBtn.SetPos(col1X, startY)
redsBtn.SetBackgroundHue(32 if TARGET_REDS else 90)
API.Gumps.AddControlOnClick(redsBtn, toggle_reds)
gump.Add(redsBtn)

graysBtn = API.Gumps.CreateSimpleButton("[GRAYS:" + ("ON" if TARGET_GRAYS else "OFF") + "]", buttonWidth, buttonHeight)
graysBtn.SetPos(col2X, startY)
graysBtn.SetBackgroundHue(53 if TARGET_GRAYS else 90)
API.Gumps.AddControlOnClick(graysBtn, toggle_grays)
gump.Add(graysBtn)

# === ATTACK ORDER SECTION ===
orderLabel = API.Gumps.CreateGumpTTFLabel("=== ATTACK ORDER ===", 9, "#ff6666", aligned="center", maxWidth=200)
orderLabel.SetPos(0, startY + 27)
gump.Add(orderLabel)

# Mode toggle button
modeBtn = API.Gumps.CreateSimpleButton("[MODE: " + ATTACK_MODE + "]", 190, buttonHeight)
modeBtn.SetPos(col1X, startY + 43)
modeBtn.SetBackgroundHue(68 if ATTACK_MODE == "ALL" else 38)
API.Gumps.AddControlOnClick(modeBtn, toggle_attack_mode)
gump.Add(modeBtn)

# Pet list (5 rows)
petListY = startY + 68
for i in range(MAX_ATTACK_PETS):
    # Pet name label (clickable for selection)
    lbl = API.Gumps.CreateSimpleButton("  " + str(i + 1) + ". ---", 145, 18)
    lbl.SetPos(col1X, petListY + (i * 20))
    lbl.SetBackgroundHue(90)
    API.Gumps.AddControlOnClick(lbl, make_select_callback(i))
    gump.Add(lbl)
    
    # Toggle button
    toggleBtn = API.Gumps.CreateSimpleButton("[--]", 40, 18)
    toggleBtn.SetPos(155, petListY + (i * 20))
    toggleBtn.SetBackgroundHue(90)
    API.Gumps.AddControlOnClick(toggleBtn, make_toggle_callback(i))
    gump.Add(toggleBtn)
    
    pet_rows.append({"label": lbl, "toggleBtn": toggleBtn})

# Pet management buttons
petBtnY = petListY + (MAX_ATTACK_PETS * 20) + 3

addPetBtn = API.Gumps.CreateSimpleButton("[ADD]", 45, 20)
addPetBtn.SetPos(col1X, petBtnY)
addPetBtn.SetBackgroundHue(68)
API.Gumps.AddControlOnClick(addPetBtn, add_attack_pet)
gump.Add(addPetBtn)

removePetBtn = API.Gumps.CreateSimpleButton("[DEL]", 45, 20)
removePetBtn.SetPos(55, petBtnY)
removePetBtn.SetBackgroundHue(32)
API.Gumps.AddControlOnClick(removePetBtn, remove_attack_pet)
gump.Add(removePetBtn)

upBtn = API.Gumps.CreateSimpleButton("[UP]", 40, 20)
upBtn.SetPos(105, petBtnY)
upBtn.SetBackgroundHue(53)
API.Gumps.AddControlOnClick(upBtn, move_pet_up)
gump.Add(upBtn)

downBtn = API.Gumps.CreateSimpleButton("[DN]", 40, 20)
downBtn.SetPos(150, petBtnY)
downBtn.SetBackgroundHue(53)
API.Gumps.AddControlOnClick(downBtn, move_pet_down)
gump.Add(downBtn)

# Commands section
cmdLabel = API.Gumps.CreateGumpTTFLabel("=== COMMANDS ===", 9, "#00ff00", aligned="center", maxWidth=200)
cmdLabel.SetPos(0, petBtnY + 27)
gump.Add(cmdLabel)

cmdStartY = petBtnY + 43

killBtn = API.Gumps.CreateSimpleButton("[ALL KILL]", buttonWidth, buttonHeight)
killBtn.SetPos(col1X, cmdStartY)
killBtn.SetBackgroundHue(32)
API.Gumps.AddControlOnClick(killBtn, all_kill)
gump.Add(killBtn)

guardBtn = API.Gumps.CreateSimpleButton("[GUARD]", buttonWidth, buttonHeight)
guardBtn.SetPos(col2X, cmdStartY)
guardBtn.SetBackgroundHue(63)
API.Gumps.AddControlOnClick(guardBtn, all_guard)
gump.Add(guardBtn)

followBtn = API.Gumps.CreateSimpleButton("[FOLLOW]", buttonWidth, buttonHeight)
followBtn.SetPos(col1X, cmdStartY + 25)
followBtn.SetBackgroundHue(88)
API.Gumps.AddControlOnClick(followBtn, all_follow)
gump.Add(followBtn)

stayBtn = API.Gumps.CreateSimpleButton("[STAY]", buttonWidth, buttonHeight)
stayBtn.SetPos(col2X, cmdStartY + 25)
stayBtn.SetBackgroundHue(43)
API.Gumps.AddControlOnClick(stayBtn, all_stay)
gump.Add(stayBtn)

stableBtn = API.Gumps.CreateSimpleButton("[STABLE]", buttonWidth, buttonHeight)
stableBtn.SetPos(col1X, cmdStartY + 50)
stableBtn.SetBackgroundHue(66)
API.Gumps.AddControlOnClick(stableBtn, stable_pets)
gump.Add(stableBtn)

claimBtn = API.Gumps.CreateSimpleButton("[CLAIM]", buttonWidth, buttonHeight)
claimBtn.SetPos(col2X, cmdStartY + 50)
claimBtn.SetBackgroundHue(66)
API.Gumps.AddControlOnClick(claimBtn, claim_pets)
gump.Add(claimBtn)

closeBtn = API.Gumps.CreateSimpleButton("[CLOSE SCRIPT]", 190, buttonHeight)
closeBtn.SetPos(col1X, cmdStartY + 80)
closeBtn.SetBackgroundHue(32)
API.Gumps.AddControlOnClick(closeBtn, stop_script)
gump.Add(closeBtn)

API.Gumps.AddGump(gump)

# Initial display update
update_pet_display()
update_mode_display()

API.SysMsg("Tamer Commands v3 loaded!", 68)
API.SysMsg("Mode: " + ATTACK_MODE + " | Pets in order: " + str(len(ATTACK_PETS)), 53)
if ALL_KILL_HOTKEY:
    API.SysMsg("Kill hotkey: " + ALL_KILL_HOTKEY, 53)

# ============ MAIN LOOP ============
next_save = time.time() + 10
next_display = time.time() + 1.0
next_pet_sync = time.time() + PET_SYNC_INTERVAL

while not API.StopRequested:
    try:
        API.ProcessCallbacks()
        
        if time.time() > next_save:
            API.SavePersistentVar(SETTINGS_KEY, str(gump.GetX()) + "," + str(gump.GetY()), API.PersistentVar.Char)
            next_save = time.time() + 10
        
        # Auto-sync pet list from storage (check if changed by Pet Healer)
        if time.time() > next_pet_sync:
            sync_pets_from_storage()
            next_pet_sync = time.time() + PET_SYNC_INTERVAL
        
        # Refresh pet display periodically (check if pets still exist)
        if time.time() > next_display:
            update_pet_display()
            next_display = time.time() + 2.0
        
        API.Pause(0.1)
    except Exception as e:
        API.SysMsg("Error: " + str(e), 32)
        API.Pause(1)

cleanup()