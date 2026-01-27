# ============================================================
# LegionUtils - Common Utilities for TazUO Legion Scripts
# by Coryigon for UO Unchained
# Version: 3.0 (Phase 1 + 2 + 3 COMPLETE!)
# ============================================================
#
# Shared library of common patterns used across scripts.
# Import this to reduce code duplication and token usage.
#
# Usage:
#   import API
#   import time
#   import sys
#   sys.path.append(r"path\to\refactors")
#   from LegionUtils import *
#
# NOTE: Scripts must import API and time BEFORE importing LegionUtils
#
# ============================================================
# CHANGELOG:
# v3.0 Phase 3 (2026-01-27) - Polish & Specialized
#   - Additional formatters: distance, weight, percentage, countdown
#   - LayoutHelper class (GUI positioning with spacing)
#   - ConditionChecker class (batch condition checking)
#   - ResourceTracker class (multi-resource tracking with warnings)
#   - Journal helpers: journal_contains(), journal_contains_any()
#   - Safe math helpers: safe_divide(), clamp(), lerp()
#   - Color helpers: hue_for_percentage(), hue_for_value()
#
# v3.0 Phase 2 (2026-01-27) - Advanced Patterns
#   - HotkeyBinding class (per-binding management)
#   - HotkeyManager class (eliminates ~200 lines per script)
#   - StateMachine class (transition callbacks)
#   - DisplayGroup class (batch label updates, ~50-100 lines saved)
#   - WarningManager class (extends ErrorManager for warnings)
#   - StatusDisplay class (transient status messages)
#   - Common formatters: format_stat_bar(), format_hp_bar()
#
# v3.0 Phase 1 (2026-01-27) - Foundation Enhancements
#   - Enhanced item counting: get_item_count(), has_item(), count_items_by_type()
#   - WindowPositionTracker class (eliminates ~40 lines per script)
#   - ToggleSetting class (eliminates ~20 lines per toggle)
#   - ActionTimer class (simpler than CooldownTracker for one-time actions)
#   - ExpandableWindow class (eliminates ~80 lines per script)
#
# v2.0 (2026-01-25) - Tamer Suite Additions
#   - CooldownTracker class for reusable cooldown management
#   - Player state functions (poisoned, dead, paralyzed)
#   - Enhanced potion management
#   - Sound alerts
#   - Pet list save/load helpers
#
# v1.0 (2026-01-24) - Initial Release
#   - Combat state management
#   - Mobile/item utilities
#   - Persistence helpers
#   - ErrorManager class
#   - Basic GUI utilities
# ============================================================
# LegionUtils needs its own imports
import time

# Note: API is expected to be in global scope (imported by calling script before LegionUtils)
# But time needs to be imported here for internal use

# ============ CONSTANTS ============
BANDAGE_GRAPHIC = 0x0E21
GOLD_GRAPHIC = 0x0EED
CHECK_GRAPHIC = 0x14F0
HEAL_POTION_GRAPHIC = 0x0F0C
CURE_POTION_GRAPHIC = 0x0F07

# Shared persistence keys
SHARED_COMBAT_KEY = "SharedCombat_Active"
SHARED_PETS_KEY = "SharedPets_List"

# All possible hotkey bindings
ALL_HOTKEYS = [
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
    "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "NUMPAD0", "NUMPAD1", "NUMPAD2", "NUMPAD3", "NUMPAD4",
    "NUMPAD5", "NUMPAD6", "NUMPAD7", "NUMPAD8", "NUMPAD9",
    "ESC",
]

# ============ COMBAT STATE ============
def is_in_combat():
    """Check if any script reports being in combat"""
    return API.GetPersistentVar(SHARED_COMBAT_KEY, "False", API.PersistentVar.Char) == "True"

def set_combat_state(in_combat):
    """Set shared combat state for all scripts"""
    API.SavePersistentVar(SHARED_COMBAT_KEY, str(in_combat), API.PersistentVar.Char)

# ============ MOBILE UTILITIES ============
def get_mobile_safe(serial):
    """Safely get mobile by serial, returns None if not found or dead"""
    if serial == 0:
        return None
    mob = API.Mobiles.FindMobile(serial)
    if not mob:
        return None
    if mob.IsDead:
        return None
    return mob

def get_hp_percent(mob):
    """Get mobile HP percentage, safe against division by zero"""
    if not mob:
        return 100
    max_hp = mob.HitsMax if hasattr(mob, 'HitsMax') else 1
    if max_hp <= 0:
        return 100
    return (mob.Hits / mob.HitsMax * 100) if hasattr(mob, 'Hits') else 100

def is_poisoned(mob):
    """Check if mobile is poisoned (handles both attribute names)"""
    if not mob:
        return False
    return getattr(mob, 'IsPoisoned', False) or getattr(mob, 'Poisoned', False)

def get_distance(mob):
    """Get distance to mobile, safe default if unavailable"""
    try:
        return mob.Distance if hasattr(mob, 'Distance') else 999
    except:
        return 999

def get_mob_name(mob, default="Unknown"):
    """Get mobile name or default"""
    if not mob:
        return default
    return getattr(mob, 'Name', default)

def is_player_poisoned():
    """Check if player is poisoned"""
    return is_poisoned(API.Player)

def is_player_dead():
    """Check if player is dead"""
    try:
        return API.Player.IsDead
    except:
        return False

def is_player_paralyzed():
    """Check if player is paralyzed by checking if NotorietyFlag == 1"""
    try:
        return API.Player.NotorietyFlag == 1
    except:
        return False

# ============ ITEM UTILITIES ============
def get_item_safe(serial):
    """Safely get item by serial, returns None if not found"""
    if serial == 0:
        return None
    return API.FindItem(serial)

def has_bandages():
    """Check if player has bandages"""
    return API.FindType(BANDAGE_GRAPHIC)

def get_bandage_count():
    """Get number of bandages in backpack"""
    try:
        if API.FindType(BANDAGE_GRAPHIC):
            if hasattr(API.Found, 'Amount'):
                return API.Found.Amount
            return -1
        return 0
    except:
        return -1

def get_potion_count(graphic):
    """Get number of potions of specific type in backpack"""
    try:
        if API.FindType(graphic):
            if hasattr(API.Found, 'Amount'):
                return API.Found.Amount
            return -1
        return 0
    except:
        return -1

# ============ TARGETING UTILITIES ============
def cancel_all_targets():
    """Cancel all active targeting states"""
    if API.HasTarget():
        API.CancelTarget()
    API.CancelPreTarget()

def target_with_pretarget(serial, target_type="beneficial"):
    """Standard pre-target pattern"""
    cancel_all_targets()
    API.PreTarget(serial, target_type)
    API.Pause(0.1)

def request_target(timeout=10):
    """Request a target from the user (blocking)

    Returns:
        serial: The targeted serial, or None if cancelled/timeout
    """
    cancel_all_targets()
    try:
        return API.RequestTarget(timeout=timeout)
    except:
        return None

# ============ PERSISTENCE UTILITIES ============
def save_bool(key, value, scope=None):
    """Save boolean to persistent storage"""
    if scope is None:
        scope = API.PersistentVar.Char
    API.SavePersistentVar(key, str(value), scope)

def load_bool(key, default=True, scope=None):
    """Load boolean from persistent storage"""
    if scope is None:
        scope = API.PersistentVar.Char
    return API.GetPersistentVar(key, str(default), scope) == "True"

def save_int(key, value, scope=None):
    """Save integer to persistent storage"""
    if scope is None:
        scope = API.PersistentVar.Char
    API.SavePersistentVar(key, str(value), scope)

def load_int(key, default=0, scope=None):
    """Load integer from persistent storage"""
    if scope is None:
        scope = API.PersistentVar.Char
    try:
        return int(API.GetPersistentVar(key, str(default), scope))
    except:
        return default

def save_float(key, value, scope=None):
    """Save float to persistent storage"""
    if scope is None:
        scope = API.PersistentVar.Char
    API.SavePersistentVar(key, str(value), scope)

def load_float(key, default=0.0, scope=None):
    """Load float from persistent storage"""
    if scope is None:
        scope = API.PersistentVar.Char
    try:
        return float(API.GetPersistentVar(key, str(default), scope))
    except:
        return default

def save_list(key, items, separator="|", scope=None):
    """Save list to persistent storage"""
    if scope is None:
        scope = API.PersistentVar.Char
    API.SavePersistentVar(key, separator.join(str(x) for x in items), scope)

def load_list(key, separator="|", scope=None):
    """Load list from persistent storage"""
    if scope is None:
        scope = API.PersistentVar.Char
    stored = API.GetPersistentVar(key, "", scope)
    if not stored:
        return []
    return [x for x in stored.split(separator) if x]

def save_window_position(key, gump, scope=None):
    """Save window position from gump"""
    if scope is None:
        scope = API.PersistentVar.Char
    if gump:
        try:
            x = gump.GetX()
            y = gump.GetY()
            API.SavePersistentVar(key, str(x) + "," + str(y), scope)
        except:
            pass

def load_window_position(key, default_x=100, default_y=100, scope=None):
    """Load window position

    Returns:
        tuple: (x, y) coordinates
    """
    if scope is None:
        scope = API.PersistentVar.Char
    saved_pos = API.GetPersistentVar(key, str(default_x) + "," + str(default_y), scope)
    try:
        pos_parts = saved_pos.split(',')
        return (int(pos_parts[0]), int(pos_parts[1]))
    except:
        return (default_x, default_y)

# ============ PET MANAGEMENT ============
def get_shared_pets():
    """Load shared pet list from storage

    Returns:
        dict: {serial: {"name": str, "active": bool}}
    """
    stored = API.GetPersistentVar(SHARED_PETS_KEY, "", API.PersistentVar.Char)
    if not stored:
        return {}

    pets = {}
    for entry in stored.split("|"):
        if not entry:
            continue
        parts = entry.split(":")
        if len(parts) >= 3:
            name = parts[0]
            serial = int(parts[1]) if parts[1].isdigit() else 0
            active = parts[2] == "1"
            if serial > 0:
                pets[serial] = {"name": name, "active": active}
    return pets

def save_shared_pets(pet_dict):
    """Save shared pet list to storage

    Args:
        pet_dict: {serial: {"name": str, "active": bool}}
    """
    if not pet_dict:
        API.SavePersistentVar(SHARED_PETS_KEY, "", API.PersistentVar.Char)
        return

    pairs = []
    for serial, info in pet_dict.items():
        name = info.get("name", "Pet")
        active = info.get("active", True)
        active_str = "1" if active else "0"
        pairs.append(name + ":" + str(serial) + ":" + active_str)

    API.SavePersistentVar(SHARED_PETS_KEY, "|".join(pairs), API.PersistentVar.Char)

# ============ GUI UTILITIES ============
def create_toggle_button(text, width, height, is_on):
    """Create a toggle button with standard colors"""
    btn = API.Gumps.CreateSimpleButton(text, width, height)
    btn.SetBackgroundHue(68 if is_on else 32)  # Green/Red
    return btn

def update_toggle_button(btn, is_on):
    """Update toggle button appearance"""
    if btn:
        btn.SetBackgroundHue(68 if is_on else 32)

# ============ ERROR MESSAGE MANAGEMENT ============
class ErrorManager:
    """Manages error messages with cooldowns to prevent spam"""
    def __init__(self, cooldown=5.0):
        self.last_error_time = 0
        self.last_error_msg = ""
        self.cooldown = cooldown

    def set_error(self, msg):
        """Show error message if cooldown has passed"""
        if msg != self.last_error_msg or (time.time() - self.last_error_time) > self.cooldown:
            self.last_error_msg = msg
            self.last_error_time = time.time()
            if msg:
                API.SysMsg(msg, 32)

    def clear_error(self):
        """Clear error state"""
        self.last_error_msg = ""

    def has_error(self):
        """Check if there's an active error"""
        return bool(self.last_error_msg)

# ============ COOLDOWN MANAGEMENT ============
class CooldownTracker:
    """Tracks cooldowns for actions (potions, vet kit, etc)"""
    def __init__(self, cooldown_seconds=10.0):
        self.last_use_time = 0
        self.cooldown = cooldown_seconds

    def is_ready(self):
        """Check if action is off cooldown"""
        return (time.time() - self.last_use_time) >= self.cooldown

    def use(self):
        """Mark action as used, starting cooldown"""
        self.last_use_time = time.time()

    def time_remaining(self):
        """Get seconds remaining on cooldown"""
        elapsed = time.time() - self.last_use_time
        remaining = self.cooldown - elapsed
        return max(0, remaining)

# ============ DEBUG UTILITIES ============
DEBUG_MODE = False

def set_debug(enabled):
    """Enable/disable debug messages"""
    global DEBUG_MODE
    DEBUG_MODE = enabled

def debug_msg(text):
    """Print debug message if debug mode enabled"""
    if DEBUG_MODE:
        API.SysMsg("DEBUG: " + text, 88)

# ============ SOUND UTILITIES ============
def play_sound_alert(sound_id):
    """Play sound alert if supported by API"""
    try:
        if hasattr(API, 'PlaySound'):
            API.PlaySound(sound_id)
    except:
        pass

# ============ FORMATTING UTILITIES ============
def format_gold_compact(amount):
    """Format gold in compact form: 1234 -> 1.2k, 123456 -> 123k"""
    if amount < 1000:
        return str(int(amount))
    elif amount < 10000:
        val = round(amount / 1000.0, 1)
        if val == int(val):
            return str(int(val)) + "k"
        else:
            return "{:.1f}".format(val) + "k"
    elif amount < 1000000:
        return str(int(amount / 1000)) + "k"
    else:
        val = round(amount / 1000000.0, 1)
        if val == int(val):
            return str(int(val)) + "m"
        else:
            return "{:.1f}".format(val) + "m"

def format_time_elapsed(seconds):
    """Format elapsed time: 125 -> '2m 5s', 3665 -> '1h 1m'"""
    if seconds < 60:
        return str(int(seconds)) + "s"
    elif seconds < 3600:
        mins = int(seconds / 60)
        secs = int(seconds % 60)
        return str(mins) + "m " + str(secs) + "s"
    else:
        hours = int(seconds / 3600)
        mins = int((seconds % 3600) / 60)
        return str(hours) + "h " + str(mins) + "m"

# ============================================================
# PHASE 1 UTILITIES - Enhanced Patterns
# Added: 2026-01-27 - Deep Dive Analysis Results
# ============================================================

# ============ ENHANCED ITEM COUNTING ============
def get_item_count(graphic, container_serial=None, recursive=True):
    """Enhanced item counter - works with ANY item type in any container

    Generalizes get_potion_count(), get_bandage_count(), count_gold(), etc.
    into one flexible function. This eliminates ~250 lines of duplication.

    Args:
        graphic: Item graphic ID to count
        container_serial: Container to search (None = player backpack)
        recursive: Search nested containers (default True)

    Returns:
        int: Total count (stacks are summed)

    Examples:
        heal_potions = get_item_count(HEAL_POTION_GRAPHIC)
        gold = get_item_count(GOLD_GRAPHIC, container_serial=satchel)
        bandages = get_item_count(BANDAGE_GRAPHIC)
    """
    try:
        # Determine container
        if container_serial is None:
            backpack = API.Player.Backpack
            if not backpack:
                return 0
            container_serial = backpack.Serial if hasattr(backpack, 'Serial') else 0

        if container_serial == 0:
            return 0

        # Get items in container
        items = API.ItemsInContainer(container_serial, recursive)
        if not items:
            return 0

        # Count matching items
        total = 0
        for item in items:
            if hasattr(item, 'Graphic') and item.Graphic == graphic:
                if hasattr(item, 'Amount'):
                    total += item.Amount
                else:
                    total += 1

        return total
    except:
        return 0

def has_item(graphic, min_count=1, container_serial=None):
    """Quick predicate: do I have enough of this item?

    Args:
        graphic: Item graphic ID
        min_count: Minimum count required (default 1)
        container_serial: Container to search (None = backpack)

    Returns:
        bool: True if count >= min_count

    Examples:
        if has_item(HEAL_POTION_GRAPHIC, min_count=5):
            # Have at least 5 heal potions
            pass
    """
    return get_item_count(graphic, container_serial) >= min_count

def count_items_by_type(*graphics, **kwargs):
    """Count multiple item types at once

    Args:
        *graphics: Variable number of graphic IDs to count
        container_serial: Optional container (keyword arg)
        recursive: Optional recursive flag (keyword arg)

    Returns:
        dict: {graphic: count} mapping

    Example:
        counts = count_items_by_type(
            HEAL_POTION_GRAPHIC,
            CURE_POTION_GRAPHIC,
            REFRESH_POTION_GRAPHIC
        )
        # Returns: {0x0F0C: 15, 0x0F07: 8, 0x0F0B: 3}
    """
    container = kwargs.get('container_serial', None)
    recursive = kwargs.get('recursive', True)

    counts = {}
    for graphic in graphics:
        counts[graphic] = get_item_count(graphic, container, recursive)

    return counts

# ============ WINDOW POSITION TRACKING ============
class WindowPositionTracker:
    """Manages window position with periodic updates and persistence

    Eliminates ~40-50 lines per script of manual position tracking code.
    Handles the common pattern:
    - Load position on startup
    - Track position every N seconds
    - Save on window close

    Example:
        # Setup
        pos_tracker = WindowPositionTracker(gump, SETTINGS_KEY, 100, 100)
        gump.SetRect(pos_tracker.last_x, pos_tracker.last_y, WIDTH, HEIGHT)

        # In main loop
        pos_tracker.update()

        # On window close
        pos_tracker.save()
    """

    def __init__(self, gump, persist_key, default_x=100, default_y=100, update_interval=2.0):
        """Initialize position tracker

        Args:
            gump: The gump to track
            persist_key: Persistence key for saving position
            default_x, default_y: Default position if not saved
            update_interval: Seconds between position checks (default 2.0)
        """
        self.gump = gump
        self.key = persist_key
        self.last_x = default_x
        self.last_y = default_y
        self.last_update = 0
        self.update_interval = update_interval

        # Load saved position
        saved_x, saved_y = load_window_position(persist_key, default_x, default_y)
        self.last_x = saved_x
        self.last_y = saved_y

    def update(self):
        """Update position if interval elapsed (call in main loop)"""
        if time.time() - self.last_update > self.update_interval:
            try:
                self.last_x = self.gump.GetX()
                self.last_y = self.gump.GetY()
                self.last_update = time.time()
            except:
                pass

    def get_position(self):
        """Get current tracked position

        Returns:
            tuple: (x, y) coordinates
        """
        return (self.last_x, self.last_y)

    def save(self):
        """Save position to persistence (call on window close)"""
        if self.last_x >= 0 and self.last_y >= 0:
            save_window_position(self.key, self.gump)

# ============ TOGGLE SETTING MANAGEMENT ============
class ToggleSetting:
    """Manages a boolean setting with persistence and button updates

    Eliminates ~20-25 lines per toggle of repetitive code.
    Handles the complete pattern:
    - Load/save persistence
    - Update button appearance
    - System messages
    - Change callbacks

    Example:
        # Create toggle
        auto_heal = ToggleSetting(
            AUTO_HEAL_KEY, True, "Auto Heal",
            {"off": auto_heal_off_btn, "on": auto_heal_on_btn},
            update_display
        )

        # Wire callbacks
        API.Gumps.AddControlOnClick(auto_heal_on_btn, lambda: auto_heal.set(True))
        API.Gumps.AddControlOnClick(auto_heal_off_btn, lambda: auto_heal.set(False))

        # Use in code
        if auto_heal.value:
            do_healing()
    """

    def __init__(self, persist_key, default=True, label="Setting", buttons=None, on_change=None):
        """Initialize toggle setting

        Args:
            persist_key: Persistence key for saving
            default: Default value if not saved
            label: Display name for system messages
            buttons: Dict {"off": btn, "on": btn} or {"toggle": btn} or None
            on_change: Callback function(new_value) called on toggle
        """
        self.key = persist_key
        self.label = label
        self.value = load_bool(persist_key, default)
        self.on_change = on_change

        # Normalize buttons dict
        if buttons is None:
            self.buttons = {}
        elif isinstance(buttons, dict):
            self.buttons = buttons
        else:
            # Single button passed
            self.buttons = {"toggle": buttons}

        # Initial button state
        self.update_ui()

    def toggle(self):
        """Toggle the setting value"""
        self.value = not self.value
        save_bool(self.key, self.value)
        self.update_ui()

        # System message
        API.SysMsg(self.label + ": " + ("ON" if self.value else "OFF"),
                   68 if self.value else 32)

        # Callback
        if self.on_change:
            self.on_change(self.value)

    def set(self, value):
        """Set to specific value (True/False)"""
        if self.value != value:
            self.value = value
            save_bool(self.key, self.value)
            self.update_ui()

            # Callback
            if self.on_change:
                self.on_change(self.value)

    def update_ui(self):
        """Update button appearances"""
        if not self.buttons:
            return

        # Handle on/off button pair
        if "off" in self.buttons and "on" in self.buttons:
            self.buttons["off"].SetBackgroundHue(32 if not self.value else 90)
            self.buttons["on"].SetBackgroundHue(68 if self.value else 90)

        # Handle single toggle button
        elif "toggle" in self.buttons:
            btn = self.buttons["toggle"]
            btn.SetBackgroundHue(68 if self.value else 32)
            btn.SetText("[" + ("ON" if self.value else "OFF") + "]")

# ============ ACTION TIMING ============
class ActionTimer:
    """Tracks timing for single actions with duration

    Simpler than CooldownTracker - for one-time actions that complete.
    Eliminates manual start_time + duration tracking.

    Example:
        bandage_timer = ActionTimer(BANDAGE_DELAY)

        def start_bandage():
            bandage_timer.start()
            statusLabel.SetText("Healing...")

        # In main loop
        if bandage_timer.is_complete():
            # Ready for next action
            pass
        else:
            # Show remaining time
            remaining = int(bandage_timer.time_remaining())
            statusLabel.SetText("Healing (" + str(remaining) + "s)")
    """

    def __init__(self, duration):
        """Initialize action timer

        Args:
            duration: Duration in seconds
        """
        self.duration = duration
        self.start_time = 0
        self.active = False

    def start(self):
        """Start action timer"""
        self.start_time = time.time()
        self.active = True

    def is_complete(self):
        """Check if action duration elapsed

        Returns:
            bool: True if timer not active or duration passed
        """
        if not self.active:
            return True

        if time.time() >= self.start_time + self.duration:
            self.active = False
            return True

        return False

    def time_remaining(self):
        """Get seconds remaining

        Returns:
            float: Seconds remaining (0 if not active)
        """
        if not self.active:
            return 0
        remaining = self.duration - (time.time() - self.start_time)
        return max(0, remaining)

    def cancel(self):
        """Cancel active timer"""
        self.active = False

# ============ EXPANDABLE WINDOW MANAGEMENT ============
class ExpandableWindow:
    """Manages window expand/collapse with control visibility

    Eliminates ~80-120 lines per script of repetitive expand/collapse code.
    Handles the complete pattern:
    - Load/save expanded state
    - Toggle button updates
    - Show/hide controls
    - Resize window

    Example:
        expander = ExpandableWindow(
            gump, expandBtn, EXPANDED_KEY,
            width=280, expanded_height=600, collapsed_height=24
        )

        # Register collapsible controls
        expander.add_controls(
            hpLabel, stamLabel, manaLabel,
            healBtn, cureBtn, buffBtn
        )

        # Wire button
        API.Gumps.AddControlOnClick(expandBtn, expander.toggle)
    """

    def __init__(self, gump, expand_btn, persist_key,
                 width=280, expanded_height=600, collapsed_height=24):
        """Initialize expandable window

        Args:
            gump: The gump window
            expand_btn: The expand/collapse button
            persist_key: Persistence key for saving state
            width: Window width
            expanded_height: Height when expanded
            collapsed_height: Height when collapsed
        """
        self.gump = gump
        self.expand_btn = expand_btn
        self.key = persist_key
        self.width = width
        self.expanded_height = expanded_height
        self.collapsed_height = collapsed_height

        self.controls_to_toggle = []
        self.is_expanded = load_bool(persist_key, True)

        # Initial state
        self.update_state(animate=False)

    def add_control(self, control):
        """Register control for visibility toggle

        Args:
            control: Control to show/hide on expand/collapse
        """
        self.controls_to_toggle.append(control)
        control.IsVisible = self.is_expanded

    def add_controls(self, *controls):
        """Register multiple controls

        Args:
            *controls: Variable number of controls to register
        """
        for ctrl in controls:
            self.add_control(ctrl)

    def toggle(self):
        """Toggle expanded state"""
        self.is_expanded = not self.is_expanded
        save_bool(self.key, self.is_expanded)
        self.update_state()

    def update_state(self, animate=True):
        """Update window and controls to current state

        Args:
            animate: Reserved for future animation support
        """
        # Update button
        self.expand_btn.SetText("[-]" if self.is_expanded else "[+]")

        # Update control visibility
        for ctrl in self.controls_to_toggle:
            ctrl.IsVisible = self.is_expanded

        # Resize window
        try:
            x = self.gump.GetX()
            y = self.gump.GetY()
            height = self.expanded_height if self.is_expanded else self.collapsed_height
            self.gump.SetRect(x, y, self.width, height)
        except:
            pass

# ============================================================
# PHASE 2 UTILITIES - Advanced Patterns
# Added: 2026-01-27 - Deep Dive Analysis Phase 2
# ============================================================

# ============ HOTKEY MANAGEMENT SYSTEM ============
class HotkeyBinding:
    """Manages a single hotkey binding with capture and execution

    Handles the complete hotkey pattern:
    - Load/save binding
    - Capture mode (listen for key press)
    - Button updates
    - Execute callback when key pressed

    Example:
        pause_hk = HotkeyBinding(
            PAUSE_KEY, "Pause", toggle_pause,
            pause_btn, "PAUSE"
        )

        # Create handlers for all keys
        for key in ALL_HOTKEYS:
            API.OnHotKey(key, pause_hk.make_handler(key))

        # Start capture on button click
        API.Gumps.AddControlOnClick(pause_btn, pause_hk.start_capture)
    """

    def __init__(self, persist_key, label, execute_cb, button=None, default_key=""):
        """Initialize hotkey binding

        Args:
            persist_key: Persistence key for saving binding
            label: Display name for system messages
            execute_cb: Function to call when hotkey pressed
            button: Button control to update with current key
            default_key: Default hotkey if not saved
        """
        self.key = persist_key
        self.label = label
        self.execute = execute_cb
        self.button = button
        self.current_hotkey = API.GetPersistentVar(persist_key, default_key, API.PersistentVar.Char)
        self.capturing = False

        self.update_button()

    def make_handler(self, key_name):
        """Create handler for specific key

        Args:
            key_name: The key this handler responds to

        Returns:
            function: Handler function for this key
        """
        def handler():
            if self.capturing:
                if key_name == "ESC":
                    # Cancel capture
                    self.capturing = False
                    self.update_button()
                    API.SysMsg("Hotkey capture cancelled", 90)
                    return

                # Bind to this key
                self.bind(key_name)
                return

            # Execute if matches current binding
            if key_name == self.current_hotkey:
                self.execute()

        return handler

    def start_capture(self):
        """Start listening for key press"""
        self.capturing = True
        self.update_button()
        API.SysMsg("Press key for " + self.label + " (ESC to cancel)", 68)

    def bind(self, key_name):
        """Bind to new key

        Args:
            key_name: Key to bind to
        """
        old_key = self.current_hotkey
        self.current_hotkey = key_name
        API.SavePersistentVar(self.key, key_name, API.PersistentVar.Char)
        self.capturing = False
        self.update_button()

        msg = self.label + " bound to [" + key_name + "]"
        if old_key:
            msg += " (was [" + old_key + "])"
        API.SysMsg(msg, 68)

    def clear(self):
        """Clear hotkey binding"""
        self.current_hotkey = ""
        API.SavePersistentVar(self.key, "", API.PersistentVar.Char)
        self.update_button()
        API.SysMsg(self.label + " binding cleared", 90)

    def update_button(self):
        """Update button appearance"""
        if not self.button:
            return

        if self.capturing:
            self.button.SetBackgroundHue(38)  # Purple for listening
            self.button.SetText("[Listening...]")
        else:
            if self.current_hotkey:
                self.button.SetBackgroundHue(68)  # Green for bound
                self.button.SetText("[" + self.current_hotkey + "]")
            else:
                self.button.SetBackgroundHue(90)  # Gray for unbound
                self.button.SetText("[---]")

class HotkeyManager:
    """Manages multiple hotkey bindings

    Eliminates ~200 lines per script of hotkey management code.
    Centralizes the complete hotkey system:
    - Register multiple bindings
    - Automatic handler creation
    - Bulk registration with API

    Example:
        hotkeys = HotkeyManager()

        # Add bindings
        pause_hk = hotkeys.add("pause", PAUSE_KEY, "Pause",
                               toggle_pause, pause_btn, "PAUSE")
        kill_hk = hotkeys.add("kill", KILL_KEY, "All Kill",
                              cmd_all_kill, kill_btn, "TAB")

        # Register all with API
        hotkeys.register_all()

        # Start capture on button click
        API.Gumps.AddControlOnClick(pause_btn, pause_hk.start_capture)
    """

    def __init__(self, all_keys=None):
        """Initialize hotkey manager

        Args:
            all_keys: List of all valid keys for capture (defaults to ALL_HOTKEYS)
        """
        self.bindings = {}
        self.all_keys = all_keys if all_keys else ALL_HOTKEYS

    def add(self, name, persist_key, label, execute_cb, button=None, default_key=""):
        """Add hotkey binding

        Args:
            name: Internal name for this binding
            persist_key: Persistence key
            label: Display name
            execute_cb: Callback function
            button: Button control
            default_key: Default key

        Returns:
            HotkeyBinding: The created binding
        """
        binding = HotkeyBinding(persist_key, label, execute_cb, button, default_key)
        self.bindings[name] = binding
        return binding

    def get(self, name):
        """Get binding by name

        Args:
            name: Binding name

        Returns:
            HotkeyBinding: The binding, or None if not found
        """
        return self.bindings.get(name)

    def register_all(self):
        """Register all hotkey handlers with API

        Call this once after adding all bindings.
        Creates handlers for every key × every binding.
        """
        for key in self.all_keys:
            for binding in self.bindings.values():
                try:
                    API.OnHotKey(key, binding.make_handler(key))
                except:
                    pass

# ============ STATE MACHINE MANAGEMENT ============
class StateMachine:
    """Simple state machine with transition callbacks

    Useful for complex workflows with multiple states.
    Simpler than manual state tracking with if/elif chains.

    Example:
        heal_state = StateMachine("idle")
        heal_state.on_enter["healing"] = lambda: statusLabel.SetText("Healing...")
        heal_state.on_exit["healing"] = lambda: statusLabel.SetText("Running")

        # Transitions
        heal_state.transition("healing")  # Triggers on_enter callback
        heal_state.transition("idle")     # Triggers on_exit callback

        # Check state
        if heal_state.is_state("idle"):
            # Can start new action
            pass

        # Time in state
        if heal_state.time_in_state() > 5.0:
            # Been healing for 5+ seconds
            pass
    """

    def __init__(self, initial_state):
        """Initialize state machine

        Args:
            initial_state: Starting state name
        """
        self.state = initial_state
        self.prev_state = None
        self.state_start_time = time.time()
        self.on_enter = {}  # state -> callback
        self.on_exit = {}   # state -> callback

    def transition(self, new_state):
        """Transition to new state

        Args:
            new_state: State to transition to
        """
        if new_state == self.state:
            return  # Already in this state

        # Exit callback for current state
        if self.state in self.on_exit:
            try:
                self.on_exit[self.state]()
            except:
                pass

        # Transition
        self.prev_state = self.state
        self.state = new_state
        self.state_start_time = time.time()

        # Enter callback for new state
        if new_state in self.on_enter:
            try:
                self.on_enter[new_state]()
            except:
                pass

    def is_state(self, state):
        """Check if in specific state

        Args:
            state: State to check

        Returns:
            bool: True if in this state
        """
        return self.state == state

    def time_in_state(self):
        """Get time spent in current state

        Returns:
            float: Seconds in current state
        """
        return time.time() - self.state_start_time

# ============ GUI DISPLAY MANAGEMENT ============
class DisplayGroup:
    """Manages batch updates to display labels

    Eliminates ~50-100 lines per script of repetitive label updates.
    Centralizes label management with formatters.

    Example:
        display = DisplayGroup()

        # Add labels with formatters
        display.add("hp", hpLabel,
                    lambda v: "HP: " + str(v[0]) + "/" + str(v[1]))
        display.add("stam", stamLabel,
                    lambda v: "Stam: " + str(v[0]) + "/" + str(v[1]))
        display.add("poison", poisonLabel)

        # Update all at once
        player = API.Player
        display.update_all({
            "hp": (player.Hits, player.HitsMax),
            "stam": (player.Stam, player.StamMax),
            "poison": "POISONED!" if is_player_poisoned() else "Clear"
        })
    """

    def __init__(self):
        """Initialize display group"""
        self.labels = {}      # name -> control
        self.formatters = {}  # name -> format function

    def add(self, name, control, formatter=None):
        """Register label for updates

        Args:
            name: Identifier for this label
            control: Label control
            formatter: Optional function(value) -> str for formatting
        """
        self.labels[name] = control
        if formatter:
            self.formatters[name] = formatter

    def update(self, name, value):
        """Update single label

        Args:
            name: Label identifier
            value: New value
        """
        if name not in self.labels:
            return

        # Format if formatter exists
        if name in self.formatters:
            try:
                value = self.formatters[name](value)
            except:
                pass

        try:
            self.labels[name].SetText(str(value))
        except:
            pass

    def update_all(self, values):
        """Update multiple labels at once

        Args:
            values: Dict of {name: value}
        """
        for name, value in values.items():
            self.update(name, value)

    def set_visibility(self, visible):
        """Show/hide all labels in group

        Args:
            visible: True to show, False to hide
        """
        for label in self.labels.values():
            try:
                label.IsVisible = visible
            except:
                pass

    def clear(self):
        """Clear all labels"""
        for label in self.labels.values():
            try:
                label.SetText("")
            except:
                pass

# ============ ENHANCED ERROR/WARNING MANAGEMENT ============
class WarningManager(ErrorManager):
    """Extends ErrorManager for warnings (yellow text, less aggressive)

    Use for non-critical warnings that should be less prominent.

    Example:
        warnings = WarningManager(cooldown=10.0)
        warnings.set_warning("Low on bandages!")  # Yellow text
    """

    def set_warning(self, msg):
        """Show warning message if cooldown passed

        Args:
            msg: Warning message to display
        """
        if msg != self.last_error_msg or (time.time() - self.last_error_time) > self.cooldown:
            self.last_error_msg = msg
            self.last_error_time = time.time()
            if msg:
                API.SysMsg(msg, 43)  # Yellow for warnings

class StatusDisplay:
    """Manages transient status messages with auto-clear

    Useful for temporary status updates that should disappear.

    Example:
        status = StatusDisplay(statusLabel, duration=3.0)

        # Show transient message
        status.show("Healed!", duration=2.0)

        # In main loop
        status.update()  # Auto-clears after duration
    """

    def __init__(self, status_label, duration=3.0):
        """Initialize status display

        Args:
            status_label: Label control for status messages
            duration: Seconds before auto-clearing message
        """
        self.label = status_label
        self.duration = duration
        self.message_time = 0
        self.current_message = ""

    def show(self, msg, duration=None):
        """Show transient status message

        Args:
            msg: Message to display
            duration: Optional custom duration for this message
        """
        try:
            self.label.SetText(msg)
            self.message_time = time.time()
            self.current_message = msg
            if duration:
                self.duration = duration
        except:
            pass

    def update(self):
        """Call in main loop to auto-clear expired messages"""
        if self.current_message and time.time() > self.message_time + self.duration:
            try:
                self.label.SetText("")
                self.current_message = ""
            except:
                pass

    def clear(self):
        """Clear status immediately"""
        try:
            self.label.SetText("")
            self.current_message = ""
        except:
            pass

# ============ COMMON FORMATTERS ============
def format_stat_bar(current, maximum, label):
    """Format stat as current/max (pct%)

    Args:
        current: Current value
        maximum: Maximum value
        label: Label text (e.g., "HP", "Stam")

    Returns:
        str: Formatted string like "HP: 100/120 (83%)"
    """
    pct = (current / maximum * 100) if maximum > 0 else 100
    return label + ": " + str(current) + "/" + str(maximum) + " (" + str(int(pct)) + "%)"

def format_hp_bar(current, maximum):
    """Format HP with visual bar

    Args:
        current: Current HP
        maximum: Maximum HP

    Returns:
        str: Formatted string like "HP: 83% ████████████████"
    """
    pct = (current / maximum * 100) if maximum > 0 else 100
    bar_length = int(pct / 5)
    bar = "█" * bar_length
    return "HP: " + str(int(pct)) + "% " + bar

# ============================================================
# PHASE 3 UTILITIES - Polish & Specialized Patterns
# Added: 2026-01-27 - Additional convenience utilities
# ============================================================

# ============ ADDITIONAL FORMATTERS ============
def format_distance(distance):
    """Format distance for display

    Args:
        distance: Distance in tiles

    Returns:
        str: Formatted distance like "5 tiles" or "Out of range"
    """
    if distance <= 0:
        return "---"
    elif distance == 1:
        return "1 tile"
    elif distance > 20:
        return "Out of range"
    else:
        return str(distance) + " tiles"

def format_weight(weight, max_weight=None):
    """Format weight for display

    Args:
        weight: Current weight
        max_weight: Optional maximum weight

    Returns:
        str: Formatted weight like "120/150 stones" or "120 stones"
    """
    if max_weight:
        return str(int(weight)) + "/" + str(int(max_weight)) + " stones"
    else:
        return str(int(weight)) + " stones"

def format_percentage(value, total):
    """Format as percentage

    Args:
        value: Current value
        total: Total value

    Returns:
        str: Formatted percentage like "75%"
    """
    if total <= 0:
        return "0%"
    pct = (value / total * 100)
    return str(int(pct)) + "%"

def format_countdown(seconds):
    """Format countdown timer

    Args:
        seconds: Seconds remaining

    Returns:
        str: Formatted countdown like "5s" or "1m 30s"
    """
    if seconds <= 0:
        return "Ready"
    elif seconds < 60:
        return str(int(seconds)) + "s"
    else:
        mins = int(seconds / 60)
        secs = int(seconds % 60)
        return str(mins) + "m " + str(secs) + "s"

# ============ GUI LAYOUT HELPERS ============
class LayoutHelper:
    """Helper for positioning GUI controls

    Simplifies positioning controls in columns/rows with consistent spacing.

    Example:
        layout = LayoutHelper(start_x=10, start_y=30, spacing=5)

        # Add controls in column
        layout.add_vertical(label1)
        layout.add_vertical(label2)
        layout.add_vertical(label3)

        # Start new column
        layout.new_column(x_offset=100)
        layout.add_vertical(button1)
        layout.add_vertical(button2)
    """

    def __init__(self, start_x=10, start_y=30, spacing=5):
        """Initialize layout helper

        Args:
            start_x: Starting X position
            start_y: Starting Y position
            spacing: Spacing between controls
        """
        self.start_x = start_x
        self.start_y = start_y
        self.spacing = spacing
        self.current_x = start_x
        self.current_y = start_y

    def add_vertical(self, control, height=None):
        """Add control vertically (stacked)

        Args:
            control: Control to position
            height: Optional custom height (auto-detected if None)

        Returns:
            tuple: (x, y) position used
        """
        try:
            control.SetPos(self.current_x, self.current_y)

            # Move down for next control
            if height:
                self.current_y += height + self.spacing
            else:
                # Try to get height from control
                try:
                    h = control.GetHeight() if hasattr(control, 'GetHeight') else 20
                    self.current_y += h + self.spacing
                except:
                    self.current_y += 20 + self.spacing

            return (self.current_x, self.current_y - height - self.spacing if height else self.current_y - 20 - self.spacing)
        except:
            return (self.current_x, self.current_y)

    def add_horizontal(self, control, width=None):
        """Add control horizontally (side-by-side)

        Args:
            control: Control to position
            width: Optional custom width (auto-detected if None)

        Returns:
            tuple: (x, y) position used
        """
        try:
            control.SetPos(self.current_x, self.current_y)

            # Move right for next control
            if width:
                self.current_x += width + self.spacing
            else:
                # Try to get width from control
                try:
                    w = control.GetWidth() if hasattr(control, 'GetWidth') else 100
                    self.current_x += w + self.spacing
                except:
                    self.current_x += 100 + self.spacing

            return (self.current_x - width - self.spacing if width else self.current_x - 100 - self.spacing, self.current_y)
        except:
            return (self.current_x, self.current_y)

    def new_row(self, y_offset=None):
        """Start new row (reset X, move Y down)

        Args:
            y_offset: Optional custom Y offset
        """
        self.current_x = self.start_x
        if y_offset:
            self.current_y += y_offset
        else:
            self.current_y += self.spacing

    def new_column(self, x_offset=None):
        """Start new column (move X right, reset Y)

        Args:
            x_offset: Optional custom X offset
        """
        if x_offset:
            self.current_x += x_offset
        else:
            self.current_x += 100  # Default column width
        self.current_y = self.start_y

    def reset(self):
        """Reset to starting position"""
        self.current_x = self.start_x
        self.current_y = self.start_y

# ============ BATCH OPERATIONS ============
class ConditionChecker:
    """Check multiple conditions at once

    Useful for complex checks with multiple requirements.

    Example:
        checker = ConditionChecker()
        checker.add("HP Low", lambda: player.Hits < 50)
        checker.add("Poisoned", lambda: is_player_poisoned())
        checker.add("Out of Range", lambda: target.Distance > 10)

        # Check all
        if checker.check_all():
            # All conditions true
            pass

        # Check any
        if checker.check_any():
            # At least one condition true
            pass

        # Get failed conditions
        failed = checker.get_failed()
        # Returns: ["HP Low", "Out of Range"]
    """

    def __init__(self):
        """Initialize condition checker"""
        self.conditions = {}  # name -> function

    def add(self, name, condition_func):
        """Add condition to check

        Args:
            name: Condition name
            condition_func: Function that returns True/False
        """
        self.conditions[name] = condition_func

    def check_all(self):
        """Check if all conditions are true

        Returns:
            bool: True if all conditions pass
        """
        for func in self.conditions.values():
            try:
                if not func():
                    return False
            except:
                return False
        return True

    def check_any(self):
        """Check if any condition is true

        Returns:
            bool: True if at least one condition passes
        """
        for func in self.conditions.values():
            try:
                if func():
                    return True
            except:
                pass
        return False

    def get_failed(self):
        """Get list of failed condition names

        Returns:
            list: Names of conditions that failed
        """
        failed = []
        for name, func in self.conditions.items():
            try:
                if not func():
                    failed.append(name)
            except:
                failed.append(name)
        return failed

    def get_passed(self):
        """Get list of passed condition names

        Returns:
            list: Names of conditions that passed
        """
        passed = []
        for name, func in self.conditions.items():
            try:
                if func():
                    passed.append(name)
            except:
                pass
        return passed

# ============ RESOURCE TRACKING ============
class ResourceTracker:
    """Track multiple resources with thresholds

    Useful for tracking bandages, potions, reagents, etc. with warnings.

    Example:
        tracker = ResourceTracker()
        tracker.add("Bandages", BANDAGE_GRAPHIC, low_threshold=10)
        tracker.add("Heal Potions", HEAL_POTION_GRAPHIC, low_threshold=5)
        tracker.add("Gold", GOLD_GRAPHIC, low_threshold=1000)

        # Update counts
        tracker.update_all()

        # Check status
        if tracker.is_low("Bandages"):
            API.SysMsg("Low on bandages!", 43)

        # Get all low resources
        low_resources = tracker.get_low_resources()
        # Returns: ["Bandages", "Heal Potions"]
    """

    def __init__(self):
        """Initialize resource tracker"""
        self.resources = {}  # name -> {graphic, count, threshold, warned}

    def add(self, name, graphic, low_threshold=10):
        """Add resource to track

        Args:
            name: Resource name
            graphic: Item graphic ID
            low_threshold: Threshold for low warning
        """
        self.resources[name] = {
            "graphic": graphic,
            "count": 0,
            "threshold": low_threshold,
            "warned": False
        }

    def update(self, name):
        """Update count for specific resource

        Args:
            name: Resource name
        """
        if name not in self.resources:
            return

        res = self.resources[name]
        res["count"] = get_item_count(res["graphic"])

    def update_all(self):
        """Update counts for all tracked resources"""
        for name in self.resources:
            self.update(name)

    def get_count(self, name):
        """Get current count for resource

        Args:
            name: Resource name

        Returns:
            int: Current count
        """
        if name in self.resources:
            return self.resources[name]["count"]
        return 0

    def is_low(self, name):
        """Check if resource is below threshold

        Args:
            name: Resource name

        Returns:
            bool: True if count < threshold
        """
        if name not in self.resources:
            return False

        res = self.resources[name]
        return res["count"] < res["threshold"]

    def get_low_resources(self):
        """Get list of resources below threshold

        Returns:
            list: Names of resources that are low
        """
        low = []
        for name, res in self.resources.items():
            if res["count"] < res["threshold"]:
                low.append(name)
        return low

    def warn_if_low(self, name, cooldown=10.0):
        """Warn if resource is low (with cooldown)

        Args:
            name: Resource name
            cooldown: Seconds between warnings

        Returns:
            bool: True if warning was shown
        """
        if name not in self.resources:
            return False

        res = self.resources[name]

        if res["count"] < res["threshold"]:
            if not res["warned"]:
                API.SysMsg("Low on " + name + "! (" + str(res["count"]) + " remaining)", 43)
                res["warned"] = True
                return True
        else:
            # Reset warning flag when not low
            res["warned"] = False

        return False

# ============ JOURNAL HELPERS ============
def journal_contains(pattern, recent_lines=10):
    """Check if journal contains pattern in recent lines

    Args:
        pattern: Text pattern to search for (case-insensitive)
        recent_lines: Number of recent lines to check

    Returns:
        bool: True if pattern found
    """
    try:
        journal_text = API.InGameJournal.GetText()
        recent = journal_text.split('\n')[-recent_lines:]

        pattern_lower = pattern.lower()
        for line in recent:
            if pattern_lower in line.lower():
                return True

        return False
    except:
        return False

def journal_contains_any(patterns, recent_lines=10):
    """Check if journal contains any of multiple patterns

    Args:
        patterns: List of patterns to search for
        recent_lines: Number of recent lines to check

    Returns:
        str: First pattern found, or None if none found
    """
    try:
        journal_text = API.InGameJournal.GetText()
        recent = journal_text.split('\n')[-recent_lines:]

        for pattern in patterns:
            pattern_lower = pattern.lower()
            for line in recent:
                if pattern_lower in line.lower():
                    return pattern

        return None
    except:
        return None

def clear_journal_check():
    """Mark journal as checked (for detecting new messages)

    Returns current journal length to compare later.

    Returns:
        int: Journal length
    """
    try:
        journal_text = API.InGameJournal.GetText()
        return len(journal_text.split('\n'))
    except:
        return 0

# ============ SAFE MATH HELPERS ============
def safe_divide(numerator, denominator, default=0):
    """Safe division with default for divide-by-zero

    Args:
        numerator: Value to divide
        denominator: Divide by this
        default: Return this if denominator is 0

    Returns:
        float: Result or default
    """
    if denominator == 0:
        return default
    return numerator / denominator

def clamp(value, min_value, max_value):
    """Clamp value between min and max

    Args:
        value: Value to clamp
        min_value: Minimum value
        max_value: Maximum value

    Returns:
        Value clamped to range
    """
    if value < min_value:
        return min_value
    elif value > max_value:
        return max_value
    else:
        return value

def lerp(start, end, t):
    """Linear interpolation between two values

    Args:
        start: Start value
        end: End value
        t: Interpolation factor (0.0 to 1.0)

    Returns:
        float: Interpolated value
    """
    t = clamp(t, 0.0, 1.0)
    return start + (end - start) * t

# ============ COLOR HELPERS ============
def hue_for_percentage(percentage):
    """Get color hue for percentage (red=low, yellow=mid, green=high)

    Args:
        percentage: Value from 0-100

    Returns:
        int: Color hue for API
    """
    if percentage >= 75:
        return 68  # Green
    elif percentage >= 50:
        return 43  # Yellow
    elif percentage >= 25:
        return 53  # Orange
    else:
        return 32  # Red

def hue_for_value(value, low, high):
    """Get color hue based on value in range

    Args:
        value: Current value
        low: Low threshold (red)
        high: High threshold (green)

    Returns:
        int: Color hue for API
    """
    if value >= high:
        return 68  # Green
    elif value >= (low + high) / 2:
        return 43  # Yellow
    else:
        return 32  # Red
