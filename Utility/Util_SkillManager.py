# Util_SkillManager.py
# Razor-style skill management - raise/lower/lock skills
# Version 1.0
#
# Shows only non-zero skills with controls to manage them

import API
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from LegionUtils import WindowPositionTracker

# ============ CONSTANTS ============
HUE_GREEN = 68
HUE_RED = 32
HUE_YELLOW = 43
HUE_ORANGE = 53
HUE_GRAY = 90

# Skill names mapping (ID to name)
SKILL_NAMES = {
    0: "Alchemy", 1: "Anatomy", 2: "Animal Lore", 3: "Item ID", 4: "Arms Lore",
    5: "Parrying", 6: "Begging", 7: "Blacksmith", 8: "Bowcraft", 9: "Peacemaking",
    10: "Camping", 11: "Carpentry", 12: "Cartography", 13: "Cooking", 14: "Detect Hidden",
    15: "Discordance", 16: "EvalInt", 17: "Healing", 18: "Fishing", 19: "Forensics",
    20: "Herding", 21: "Hiding", 22: "Provocation", 23: "Inscription", 24: "Lockpicking",
    25: "Magery", 26: "Magic Resist", 27: "Tactics", 28: "Snooping", 29: "Musicianship",
    30: "Poisoning", 31: "Archery", 32: "Spirit Speak", 33: "Stealing", 34: "Tailoring",
    35: "Taming", 36: "Taste ID", 37: "Tinkering", 38: "Tracking", 39: "Veterinary",
    40: "Swordsmanship", 41: "Macing", 42: "Fencing", 43: "Wrestling", 44: "Lumberjacking",
    45: "Mining", 46: "Meditation", 47: "Stealth", 48: "Remove Trap", 49: "Necromancy",
    50: "Focus", 51: "Chivalry", 52: "Bushido", 53: "Ninjitsu", 54: "Spellweaving",
    55: "Mysticism", 56: "Imbuing", 57: "Throwing"
}

# Skill lock states
LOCK_UP = 0      # Raise (up arrow)
LOCK_DOWN = 1    # Lower (down arrow)
LOCK_LOCKED = 2  # Locked

# ============ STATE ============
gump = None
controls = {}
pos_tracker = None
skill_data = []  # List of (skill_id, name, value, cap, lock_state)

# ============ PERSISTENCE ============
KEY_WINDOW_POS = "SkillManager_WindowXY"

# ============ SKILL FUNCTIONS ============

def get_all_skills():
    """Get all skills with non-zero values"""
    skills = []

    try:
        # Try to get skills from API
        if hasattr(API, 'GetSkills'):
            all_skills = API.GetSkills()
            for skill_id, skill_info in enumerate(all_skills):
                if skill_info and skill_info.Value > 0:
                    skills.append({
                        'id': skill_id,
                        'name': SKILL_NAMES.get(skill_id, f"Skill {skill_id}"),
                        'value': skill_info.Value,
                        'cap': skill_info.Cap,
                        'lock': skill_info.Lock
                    })
        elif hasattr(API.Player, 'Skills'):
            # Alternative API format
            for skill_id in range(58):  # 0-57 skills
                try:
                    skill = API.Player.Skills[skill_id]
                    if skill and skill.Value > 0:
                        skills.append({
                            'id': skill_id,
                            'name': SKILL_NAMES.get(skill_id, f"Skill {skill_id}"),
                            'value': skill.Value / 10.0,  # Convert from tenths
                            'cap': skill.Cap / 10.0 if hasattr(skill, 'Cap') else 100.0,
                            'lock': skill.Lock if hasattr(skill, 'Lock') else LOCK_UP
                        })
                except:
                    continue
        else:
            API.SysMsg("Skills API not found - using placeholder data", HUE_RED)
            # Return empty list if API not available
            return []

    except Exception as e:
        API.SysMsg("Error getting skills: " + str(e), HUE_RED)
        return []

    # Sort by name
    skills.sort(key=lambda x: x['name'])
    return skills

def set_skill_lock(skill_id, lock_state):
    """Set skill lock state (up/down/locked)"""
    try:
        if hasattr(API, 'SetSkillLock'):
            API.SetSkillLock(skill_id, lock_state)
        elif hasattr(API.Player, 'SetSkillLock'):
            API.Player.SetSkillLock(skill_id, lock_state)
        else:
            API.SysMsg("SetSkillLock API not found", HUE_RED)
            return False

        API.SysMsg("Set " + SKILL_NAMES.get(skill_id, str(skill_id)) + " to " + get_lock_name(lock_state), HUE_GREEN)
        return True
    except Exception as e:
        API.SysMsg("Error setting skill lock: " + str(e), HUE_RED)
        return False

def get_lock_name(lock_state):
    """Get friendly name for lock state"""
    if lock_state == LOCK_UP:
        return "UP"
    elif lock_state == LOCK_DOWN:
        return "DOWN"
    elif lock_state == LOCK_LOCKED:
        return "LOCKED"
    return "UNKNOWN"

def get_lock_color(lock_state):
    """Get color for lock state"""
    if lock_state == LOCK_UP:
        return HUE_GREEN
    elif lock_state == LOCK_DOWN:
        return HUE_RED
    elif lock_state == LOCK_LOCKED:
        return HUE_GRAY
    return HUE_YELLOW

# ============ GUI CALLBACKS ============

def on_skill_up(skill_id):
    """Set skill to raise"""
    if set_skill_lock(skill_id, LOCK_UP):
        refresh_skills()

def on_skill_down(skill_id):
    """Set skill to lower"""
    if set_skill_lock(skill_id, LOCK_DOWN):
        refresh_skills()

def on_skill_lock(skill_id):
    """Set skill to locked"""
    if set_skill_lock(skill_id, LOCK_LOCKED):
        refresh_skills()

def on_refresh():
    """Refresh skill list"""
    refresh_skills()

def refresh_skills():
    """Reload skills and rebuild gump"""
    global skill_data
    skill_data = get_all_skills()
    rebuild_gump()

def rebuild_gump():
    """Rebuild the entire gump"""
    global gump, controls

    if gump:
        gump.Dispose()

    build_gump()

# ============ BUILD GUI ============

def build_gump():
    """Build the skill manager gump"""
    global gump, controls, pos_tracker, skill_data

    # Load window position
    x, y = load_window_position(KEY_WINDOW_POS, 100, 100)

    # Calculate height based on number of skills
    num_skills = len(skill_data)
    height = 100 + (num_skills * 22)  # Header + (skills * row height)
    height = min(height, 800)  # Cap at 800px

    # Create gump
    gump = API.Gumps.CreateGump()
    gump.SetRect(x, y, 400, height)

    # Create position tracker
    pos_tracker = WindowPositionTracker(gump, KEY_WINDOW_POS, x, y)

    # Add background
    bg = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
    bg.SetRect(0, 0, 400, height)
    gump.Add(bg)

    controls = {}
    y_offset = 10

    # Title
    title = API.Gumps.CreateGumpTTFLabel("SKILL MANAGER", 16, "#ffaa00")
    title.SetPos(10, y_offset)
    gump.Add(title)

    # Refresh button
    refresh_btn = API.Gumps.CreateSimpleButton("REFRESH", 80, 22)
    refresh_btn.SetPos(300, y_offset - 2)
    gump.Add(refresh_btn)
    API.Gumps.AddControlOnClick(refresh_btn, on_refresh)

    y_offset += 30

    # Column headers
    name_header = API.Gumps.CreateGumpTTFLabel("Skill", 15, "#cccccc")
    name_header.SetPos(10, y_offset)
    gump.Add(name_header)

    value_header = API.Gumps.CreateGumpTTFLabel("Value", 15, "#cccccc")
    value_header.SetPos(180, y_offset)
    gump.Add(value_header)

    cap_header = API.Gumps.CreateGumpTTFLabel("Cap", 15, "#cccccc")
    cap_header.SetPos(240, y_offset)
    gump.Add(cap_header)

    lock_header = API.Gumps.CreateGumpTTFLabel("Lock", 15, "#cccccc")
    lock_header.SetPos(300, y_offset)
    gump.Add(lock_header)

    y_offset += 25

    # Skill rows
    for skill in skill_data:
        skill_id = skill['id']

        # Skill name
        name_label = API.Gumps.CreateGumpTTFLabel(skill['name'], 15, "#ffffff")
        name_label.SetPos(10, y_offset)
        gump.Add(name_label)

        # Skill value
        value_str = str(round(skill['value'], 1))
        value_label = API.Gumps.CreateGumpTTFLabel(value_str, 15, "#00ff00")
        value_label.SetPos(180, y_offset)
        gump.Add(value_label)

        # Skill cap
        cap_str = str(round(skill['cap'], 1))
        cap_label = API.Gumps.CreateGumpTTFLabel(cap_str, 15, "#ffaa00")
        cap_label.SetPos(240, y_offset)
        gump.Add(cap_label)

        # Lock buttons
        lock_state = skill['lock']

        # Up button
        up_btn = API.Gumps.CreateSimpleButton("^", 25, 18)
        up_btn.SetPos(295, y_offset - 2)
        up_btn.SetBackgroundHue(HUE_GREEN if lock_state == LOCK_UP else HUE_GRAY)
        gump.Add(up_btn)
        API.Gumps.AddControlOnClick(up_btn, lambda sid=skill_id: on_skill_up(sid))

        # Lock button
        lock_btn = API.Gumps.CreateSimpleButton("=", 25, 18)
        lock_btn.SetPos(325, y_offset - 2)
        lock_btn.SetBackgroundHue(HUE_GRAY if lock_state == LOCK_LOCKED else HUE_GRAY)
        gump.Add(lock_btn)
        API.Gumps.AddControlOnClick(lock_btn, lambda sid=skill_id: on_skill_lock(sid))

        # Down button
        down_btn = API.Gumps.CreateSimpleButton("v", 25, 18)
        down_btn.SetPos(355, y_offset - 2)
        down_btn.SetBackgroundHue(HUE_RED if lock_state == LOCK_DOWN else HUE_GRAY)
        gump.Add(down_btn)
        API.Gumps.AddControlOnClick(down_btn, lambda sid=skill_id: on_skill_down(sid))

        y_offset += 22

    # No skills message
    if len(skill_data) == 0:
        no_skills = API.Gumps.CreateGumpTTFLabel("No skills to display (all at 0.0)", 15, "#888888")
        no_skills.SetPos(10, y_offset)
        gump.Add(no_skills)

    # Close callback
    API.Gumps.AddControlOnDisposed(gump, on_gump_closed)

    # Display
    API.Gumps.AddGump(gump)

def load_window_position(key, default_x, default_y):
    """Load window position from persistence"""
    try:
        pos_str = API.GetPersistentVar(key, "", API.PersistentVar.Char)
        if pos_str and "," in pos_str:
            x, y = pos_str.split(",")
            return int(x), int(y)
    except:
        pass
    return default_x, default_y

def on_gump_closed():
    """Handle gump close"""
    global gump, controls
    if pos_tracker:
        pos_tracker.save()
    gump = None
    controls = {}

# ============ CLEANUP ============

def cleanup():
    """Cleanup on script stop"""
    global gump, controls

    if pos_tracker:
        pos_tracker.save()

    if gump:
        try:
            gump.Dispose()
        except:
            pass

    controls = {}
    gump = None

# ============ MAIN ============

try:
    # Load skills
    skill_data = get_all_skills()

    if len(skill_data) == 0:
        API.SysMsg("No skills found - make sure Skills API is available", HUE_YELLOW)

    # Build GUI
    build_gump()

    API.SysMsg("Skill Manager started! (" + str(len(skill_data)) + " skills)", HUE_GREEN)

    # Main loop for position tracking
    while not API.StopRequested:
        API.ProcessCallbacks()

        if pos_tracker:
            pos_tracker.update()

        API.Pause(0.5)

except Exception as e:
    API.SysMsg("Skill Manager error: " + str(e), HUE_RED)

finally:
    cleanup()
