# GatherFramework.py
# Reusable framework for resource gathering bots
# Version 1.0
#
# USAGE:
#   import API
#   import time
#   from GatherFramework import TravelSystem, StorageSystem, StateMachine, etc.
#
# NOTE: Scripts must import API and time BEFORE importing GatherFramework
#
# FEATURES:
# - Runebook navigation with position verification
# - Resource storage with gump interaction
# - Weight management and auto-dump
# - Combat/flee mechanics
# - Pet system integration (optional)
# - State machine infrastructure
# - Cooldown management

import time
import random

# ============ CONSTANTS ============

# Timings
RECALL_DELAY = 2.0
GUMP_WAIT_TIME = 3.0
USE_OBJECT_DELAY = 0.5
GUMP_READY_DELAY = 0.3  # Time for gump to fully load

# Runebook
RUNEBOOK_GUMP_ID = 89
EMERGENCY_RECALL_BUTTON = 10  # Button for runebook emergency charges

# UI Colors
HUE_GREEN = 68
HUE_RED = 32
HUE_YELLOW = 43
HUE_PURPLE = 53
HUE_GRAY = 90

# Default weights
DEFAULT_MAX_WEIGHT = 450

# ============ TRAVEL SYSTEM ============

class TravelSystem:
    """Handles runebook travel, spot rotation, emergency recalls.

    Features:
    - Position verification (not journal-based)
    - Emergency runebook charges when out of reagents
    - Mana regeneration waiting
    - Multi-spot rotation (slot 1 = home, 2+ = gathering spots)
    """

    def __init__(self, runebook_serial, num_spots=1, home_slot=1):
        """Initialize travel system.

        Args:
            runebook_serial: Serial number of runebook
            num_spots: Number of gathering spots (slots 2, 3, 4, etc.)
            home_slot: Slot number for home (default 1)
        """
        self.runebook_serial = runebook_serial
        self.num_spots = num_spots
        self.current_spot = 0  # Current spot index (0 = slot 2, 1 = slot 3, etc.)
        self.home_slot = home_slot
        self.at_home = True

    def get_position(self):
        """Get current player position as tuple."""
        return (getattr(API.Player, 'X', 0), getattr(API.Player, 'Y', 0))

    def check_out_of_reagents(self):
        """Check journal for out of reagents messages."""
        out_of_regs = [
            "reagents to cast",
            "insufficient reagents",
            "more reagents are needed",
            "you do not have enough reagents"
        ]
        for msg in out_of_regs:
            if API.InJournal(msg, False):
                return True
        return False

    def wait_for_mana(self, required_mana=11, timeout=60.0):
        """Wait for mana to regenerate.

        Args:
            required_mana: Mana needed to recall (default 11)
            timeout: Max seconds to wait (default 60)

        Returns:
            True if mana reached, False if timeout
        """
        start_time = time.time()

        while True:
            player_mana = getattr(API.Player, 'Mana', 0)

            if player_mana >= required_mana:
                return True

            if time.time() > start_time + timeout:
                API.SysMsg("Timeout waiting for mana - Cannot recall", HUE_RED)
                return False

            API.SysMsg(f"Waiting for mana to regen: {player_mana}/{required_mana}", HUE_YELLOW)
            API.Pause(2.0)
            API.ProcessCallbacks()

        return False

    def slot_to_button_id(self, slot):
        """Convert slot number to runebook button ID.

        Formula: button_id = 49 + slot
        Slot 1 = Button 50, Slot 2 = Button 51, etc.
        """
        return 49 + slot

    def emergency_recall(self, slot):
        """Use emergency runebook charges when out of reagents.

        Args:
            slot: Slot number to recall to

        Returns:
            True if successful, False otherwise
        """
        try:
            # Open runebook
            API.UseObject(self.runebook_serial)

            wait_start = time.time()
            while not API.HasGump(RUNEBOOK_GUMP_ID):
                if time.time() > wait_start + GUMP_WAIT_TIME:
                    return False
                API.Pause(0.1)

            API.Pause(GUMP_READY_DELAY)

            # Click emergency recall button
            API.ReplyGump(EMERGENCY_RECALL_BUTTON, RUNEBOOK_GUMP_ID)
            API.Pause(0.5)

            # Target the spot button
            if API.HasGump(RUNEBOOK_GUMP_ID):
                button_id = 100 + slot  # Emergency charges use 100+ slot number
                API.ReplyGump(button_id, RUNEBOOK_GUMP_ID)

            API.Pause(RECALL_DELAY + 2.5)
            return True

        except Exception as e:
            API.SysMsg(f"Emergency recall error: {e}", HUE_RED)
            return False

    def recall_to_slot(self, slot):
        """Recall to specified runebook slot with position verification.

        Args:
            slot: Slot number (1-16)

        Returns:
            True if successful, False otherwise
        """
        if not self.runebook_serial or self.runebook_serial == 0:
            API.SysMsg("No runebook configured!", HUE_RED)
            return False

        runebook = API.FindItem(self.runebook_serial)
        if not runebook:
            API.SysMsg("Runebook not found!", HUE_RED)
            return False

        # Check mana and wait if needed
        if not self.wait_for_mana():
            return False

        # Clear journal and save position
        API.ClearJournal()
        pos_before = self.get_position()

        API.SysMsg(f"Recalling to slot {slot}...", HUE_YELLOW)

        # Open runebook
        API.UseObject(self.runebook_serial)
        API.Pause(USE_OBJECT_DELAY)

        wait_start = time.time()
        while not API.HasGump(RUNEBOOK_GUMP_ID):
            if time.time() > wait_start + GUMP_WAIT_TIME:
                API.SysMsg("Runebook gump didn't open!", HUE_RED)
                return False
            API.Pause(0.1)

        API.Pause(GUMP_READY_DELAY)

        # Click recall button for slot
        button_id = self.slot_to_button_id(slot)
        result = API.ReplyGump(button_id)  # Don't pass gump_id for regular recalls

        # Wait for recall to complete
        API.Pause(RECALL_DELAY + 2.5)

        # Check if position changed
        pos_after = self.get_position()

        if pos_before != pos_after:
            API.SysMsg("Recall successful!", HUE_GREEN)
            return True

        # Position didn't change - check if out of reagents
        if self.check_out_of_reagents():
            API.SysMsg("OUT OF REAGENTS - Trying emergency charges...", HUE_YELLOW)
            return self.emergency_recall(slot)

        # Failed for unknown reason
        API.SysMsg("Recall failed!", HUE_RED)
        return False

    def recall_home(self):
        """Recall to home location (slot 1).

        Returns:
            True if successful, False otherwise
        """
        if self.recall_to_slot(self.home_slot):
            self.at_home = True
            return True
        return False

    def recall_to_current_spot(self):
        """Recall to current gathering spot.

        Returns:
            True if successful, False otherwise
        """
        spot_slot = 2 + self.current_spot
        if self.recall_to_slot(spot_slot):
            self.at_home = False
            return True
        return False

    def rotate_to_next_spot(self):
        """Rotate to next gathering spot and recall there.

        Returns:
            True if successful, False otherwise
        """
        self.current_spot = (self.current_spot + 1) % self.num_spots
        return self.recall_to_current_spot()

# ============ STORAGE SYSTEM ============

class StorageSystem:
    """Handles resource storage with gump interaction.

    Features:
    - Pathfinding to storage container
    - Gump interaction (fill from backpack button)
    - Distance checking
    """

    def __init__(self, container_serial, gump_id=111922706, fill_button=121):
        """Initialize storage system.

        Args:
            container_serial: Serial of storage container
            gump_id: Gump ID for storage container (default: resource bin)
            fill_button: Button ID for "fill from backpack" (default: 121)
        """
        self.container_serial = container_serial
        self.gump_id = gump_id
        self.fill_button = fill_button
        self.container_x = 0
        self.container_y = 0

    def set_container_position(self, x, y):
        """Set container position for pathfinding.

        Args:
            x: X coordinate
            y: Y coordinate
        """
        self.container_x = x
        self.container_y = y

    def is_in_range(self, max_distance=3):
        """Check if player is within range of container.

        Args:
            max_distance: Maximum distance (default 3)

        Returns:
            True if in range, False otherwise
        """
        container = API.FindItem(self.container_serial)
        if not container:
            return False

        distance = getattr(container, 'Distance', 999)
        return distance <= max_distance

    def pathfind_to_container(self, max_distance=2):
        """Pathfind to storage container.

        Args:
            max_distance: Distance to pathfind to (default 2)

        Returns:
            True if successful or already in range, False if failed
        """
        if self.is_in_range(max_distance):
            return True

        # Try entity-based pathfinding first
        if API.PathfindEntity(self.container_serial, max_distance):
            # Wait for pathfinding to complete (with timeout)
            timeout = time.time() + 30.0
            while API.Pathfinding():
                if time.time() > timeout:
                    API.CancelPathfinding()
                    return False
                API.Pause(0.1)

            return self.is_in_range(max_distance)

        # Try coordinate-based pathfinding if we have position
        if self.container_x > 0 and self.container_y > 0:
            API.Pathfind(self.container_x, self.container_y)

            timeout = time.time() + 30.0
            while API.Pathfinding():
                if time.time() > timeout:
                    API.CancelPathfinding()
                    return False
                API.Pause(0.1)

            return self.is_in_range(max_distance)

        return False

    def dump_resources(self):
        """Open storage container and use fill button.

        Returns:
            True if successful, False otherwise
        """
        if not self.is_in_range():
            API.SysMsg("Not in range of storage container!", HUE_RED)
            return False

        try:
            # Use container
            API.UseObject(self.container_serial)
            API.Pause(USE_OBJECT_DELAY)

            # Wait for gump
            wait_start = time.time()
            while not API.HasGump(self.gump_id):
                if time.time() > wait_start + GUMP_WAIT_TIME:
                    API.SysMsg("Storage gump didn't open!", HUE_RED)
                    return False
                API.Pause(0.1)

            API.Pause(GUMP_READY_DELAY)

            # Click fill button
            result = API.ReplyGump(self.fill_button, self.gump_id)

            if not result:
                API.SysMsg("Failed to click fill button!", HUE_RED)
                return False

            API.Pause(2.0)  # Wait for items to transfer

            # Close gump if still open
            if API.HasGump(self.gump_id):
                API.CloseGump(self.gump_id)
                API.Pause(0.3)

            return True

        except Exception as e:
            API.SysMsg(f"Error dumping resources: {e}", HUE_RED)
            return False

# ============ WEIGHT MANAGER ============

class WeightManager:
    """Tracks player weight and triggers auto-dump.

    Features:
    - Configurable weight threshold
    - Percentage-based checking
    """

    def __init__(self, threshold_pct=80):
        """Initialize weight manager.

        Args:
            threshold_pct: Weight threshold percentage (default 80)
        """
        self.threshold_pct = threshold_pct

    def get_current_weight(self):
        """Get current player weight."""
        return getattr(API.Player, 'Weight', 0)

    def get_max_weight(self):
        """Get max player weight."""
        return getattr(API.Player, 'MaxWeight', DEFAULT_MAX_WEIGHT)

    def get_weight_pct(self):
        """Get current weight as percentage of max.

        Returns:
            Weight percentage (0-100)
        """
        current = self.get_current_weight()
        max_weight = self.get_max_weight()

        if max_weight > 0:
            return (current / max_weight * 100)
        return 0

    def should_dump(self):
        """Check if weight exceeds threshold.

        Returns:
            True if should dump, False otherwise
        """
        return self.get_weight_pct() >= self.threshold_pct

    def set_threshold(self, threshold_pct):
        """Set weight threshold percentage.

        Args:
            threshold_pct: New threshold (0-100)
        """
        self.threshold_pct = max(0, min(100, threshold_pct))

# ============ DAMAGE TRACKER ============

class DamageTracker:
    """Tracks player HP changes to detect incoming damage.

    Features:
    - Detects HP loss between checks
    - Resets on HP gain
    - Used for immediate combat response
    """

    def __init__(self):
        """Initialize damage tracker."""
        self.last_hp = 0

    def is_taking_damage(self):
        """Check if player is taking damage.

        Returns:
            True if HP decreased since last check, False otherwise
        """
        current_hp = getattr(API.Player, 'Hits', 0)

        # Initialize on first check
        if self.last_hp == 0:
            self.last_hp = current_hp
            return False

        # Check if HP decreased
        if current_hp < self.last_hp:
            self.last_hp = current_hp
            return True

        # Update tracked HP
        self.last_hp = current_hp
        return False

    def reset(self):
        """Reset HP tracking."""
        self.last_hp = 0

# ============ STATE MACHINE ============

class StateMachine:
    """Generic state machine with timing support.

    Features:
    - State handlers
    - State timing/duration
    - State context data
    """

    def __init__(self):
        """Initialize state machine."""
        self.state = "idle"
        self.state_start_time = time.time()
        self.state_data = {}
        self.handlers = {}

    def set_state(self, new_state, **kwargs):
        """Change to new state with optional context data.

        Args:
            new_state: Name of new state
            **kwargs: Context data for state
        """
        self.state = new_state
        self.state_start_time = time.time()
        self.state_data = kwargs

    def get_state(self):
        """Get current state name."""
        return self.state

    def get_elapsed(self):
        """Get seconds elapsed in current state."""
        return time.time() - self.state_start_time

    def is_timeout(self, timeout):
        """Check if state has exceeded timeout.

        Args:
            timeout: Timeout in seconds

        Returns:
            True if timeout exceeded, False otherwise
        """
        return self.get_elapsed() > timeout

    def register_handler(self, state_name, handler_func):
        """Register handler function for state.

        Args:
            state_name: Name of state
            handler_func: Function to call (receives self as argument)
        """
        self.handlers[state_name] = handler_func

    def tick(self):
        """Execute current state handler."""
        handler = self.handlers.get(self.state)
        if handler:
            handler(self)

# ============ COMBAT SYSTEM ============

class CombatSystem:
    """Handles threat detection and combat response.

    Features:
    - Hostile detection
    - HP-based flee threshold
    - Pet combat commands
    - Flee mechanics with stuck detection
    """

    def __init__(self, mode="flee", flee_hp_threshold=50):
        """Initialize combat system.

        Args:
            mode: Combat mode ("flee" or "pet_combat")
            flee_hp_threshold: HP percentage to trigger flee (default 50)
        """
        self.mode = mode
        self.flee_hp_threshold = flee_hp_threshold
        self.current_enemy = None
        self.last_guard_time = 0
        self.last_kill_time = 0

    def find_closest_hostile(self, max_distance=10):
        """Find nearest hostile mobile.

        Args:
            max_distance: Maximum search distance (default 10)

        Returns:
            Hostile mobile or None
        """
        notorieties = [API.Notoriety.Enemy, API.Notoriety.Murderer, API.Notoriety.Criminal]
        enemy = API.NearestMobile(notorieties, max_distance)

        if enemy and not enemy.IsDead:
            return enemy
        return None

    def find_all_hostiles(self, max_distance=10):
        """Find all hostile mobiles nearby.

        Args:
            max_distance: Maximum search distance (default 10)

        Returns:
            List of mobile objects, or empty list
        """
        enemy = self.find_closest_hostile(max_distance)
        if enemy:
            return [enemy]
        return []

    def should_flee(self):
        """Check if player HP is below flee threshold.

        Returns:
            True if should flee, False otherwise
        """
        hp_pct = (API.Player.Hits / API.Player.HitsMax * 100) if API.Player.HitsMax > 0 else 100
        return hp_pct < self.flee_hp_threshold

    def all_guard_me(self):
        """Send all guard me command.

        Returns:
            True if successful
        """
        try:
            API.Say("all guard me")
            API.Pause(0.5)
            self.last_guard_time = time.time()
            return True
        except:
            return False

    def all_follow_me(self):
        """Send all follow me command.

        Returns:
            True if successful
        """
        try:
            API.Say("all follow me")
            API.Pause(0.5)
            return True
        except:
            return False

    def all_kill(self, enemy):
        """Send all kill command targeting enemy.

        Args:
            enemy: Mobile to target

        Returns:
            True if successful, False otherwise
        """
        try:
            if not enemy:
                return False

            enemy_serial = getattr(enemy, 'Serial', None)
            if not enemy_serial:
                return False

            API.Msg("all kill")
            API.Pause(0.3)

            # Use WaitForTarget and Target (like working CottonSuite)
            if API.WaitForTarget(timeout=2.0):
                API.Target(enemy_serial)
                API.Attack(enemy_serial)
                API.HeadMsg("KILL!", enemy_serial, HUE_RED)
                self.last_kill_time = time.time()
                return True

            return False
        except:
            return False

    def flee_from_enemy(self, enemy, distance=15, timeout=15.0):
        """Flee from enemy with stuck detection.

        Args:
            enemy: Mobile to flee from
            distance: Distance to flee (default 15)
            timeout: Max flee time (default 15 seconds)

        Returns:
            True if successfully fled, False otherwise
        """
        flee_start = time.time()
        last_pos_x = getattr(API.Player, 'X', 0)
        last_pos_y = getattr(API.Player, 'Y', 0)
        last_pos_check = time.time()
        stuck_count = 0

        while time.time() < flee_start + timeout:
            API.ProcessCallbacks()

            # Check if stuck
            current_x = getattr(API.Player, 'X', 0)
            current_y = getattr(API.Player, 'Y', 0)

            if time.time() > last_pos_check + 1.5:
                if current_x == last_pos_x and current_y == last_pos_y:
                    stuck_count += 1

                    # Cancel and try new direction
                    if API.Pathfinding():
                        API.CancelPathfinding()

                    # Random direction
                    dx = random.randint(-10, 10)
                    dy = random.randint(-10, 10)
                    API.Pathfind(current_x + dx, current_y + dy)

                last_pos_x = current_x
                last_pos_y = current_y
                last_pos_check = time.time()

            # Check distance to enemy
            if enemy and not enemy.IsDead:
                enemy_dist = getattr(enemy, 'Distance', 0)

                # Safe if 8+ tiles away and not losing HP
                if enemy_dist >= 8 and time.time() > flee_start + 2.0:
                    hp_before = API.Player.Hits
                    API.Pause(0.5)
                    hp_after = API.Player.Hits

                    if hp_after >= hp_before:
                        return True

            # Pathfind away from enemy
            if not API.Pathfinding() and enemy:
                player_x = getattr(API.Player, 'X', 0)
                player_y = getattr(API.Player, 'Y', 0)
                enemy_x = getattr(enemy, 'X', player_x)
                enemy_y = getattr(enemy, 'Y', player_y)

                # Run opposite direction
                flee_x = player_x + (player_x - enemy_x) * 2
                flee_y = player_y + (player_y - enemy_y) * 2
                API.Pathfind(flee_x, flee_y)

            API.Pause(0.1)

        return True  # Timeout - assume safe enough

# ============ PET SYSTEM ============

class PetSystem:
    """Pet management with Tamer Suite integration.

    Features:
    - SharedPets_List integration
    - Pet health checking
    - Preflight validation
    """

    def __init__(self, use_shared_list=True):
        """Initialize pet system.

        Args:
            use_shared_list: Use SharedPets_List from Tamer Suite (default True)
        """
        self.use_shared_list = use_shared_list

    def get_pets(self):
        """Get pets from SharedPets_List.

        Returns:
            List of pet mobiles
        """
        if not self.use_shared_list:
            return []

        try:
            pets_str = API.GetPersistentVar("SharedPets_List", "", API.PersistentVar.Char)
            if not pets_str:
                return []

            pets = []
            for entry in pets_str.split('|'):
                if not entry or ':' not in entry:
                    continue

                parts = entry.split(':')
                if len(parts) >= 2:
                    try:
                        serial = int(parts[1])
                        mob = API.FindMobile(serial)
                        if mob and not mob.IsDead:
                            pets.append(mob)
                    except:
                        continue

            return pets
        except:
            return []

    def get_dead_pets(self):
        """Get list of dead pets.

        Returns:
            List of dead pet mobiles
        """
        if not self.use_shared_list:
            return []

        try:
            pets_str = API.GetPersistentVar("SharedPets_List", "", API.PersistentVar.Char)
            if not pets_str:
                return []

            dead_pets = []
            for entry in pets_str.split('|'):
                if not entry or ':' not in entry:
                    continue

                parts = entry.split(':')
                if len(parts) >= 2:
                    try:
                        serial = int(parts[1])
                        mob = API.FindMobile(serial)
                        if mob and mob.IsDead:
                            dead_pets.append(mob)
                    except:
                        continue

            return dead_pets
        except:
            return []

    def preflight_check(self, min_hp_pct=80):
        """Check if pets are alive and healthy.

        Args:
            min_hp_pct: Minimum HP percentage (default 80)

        Returns:
            "ok", "no_pets", "dead_pets", or "needs_healing"
        """
        pets = self.get_pets()

        if not pets or len(pets) == 0:
            return "no_pets"

        dead_pets = self.get_dead_pets()
        if dead_pets and len(dead_pets) > 0:
            return "dead_pets"

        for pet in pets:
            hp_pct = (pet.Hits / pet.HitsMax * 100) if pet.HitsMax > 0 else 100
            if hp_pct < min_hp_pct:
                return "needs_healing"

        return "ok"

# ============ RESOURCE FINDER ============

class ResourceFinder:
    """Find harvestable resources with cooldown management.

    Features:
    - Multi-graphic support
    - Cooldown tracking
    - Distance sorting
    """

    def __init__(self, graphics, scan_range=24):
        """Initialize resource finder.

        Args:
            graphics: Single graphic ID or list of IDs
            scan_range: Scan radius (default 24)
        """
        self.graphics = graphics if isinstance(graphics, list) else [graphics]
        self.scan_range = scan_range
        self.cooldown_dict = {}
        self.cooldown_duration = 10.0  # Default 10 second cooldown

    def find_resources(self):
        """Find all resources of configured graphics.

        Returns:
            List of resource items
        """
        all_resources = []

        for graphic in self.graphics:
            try:
                items = API.GetItemsOnGround(self.scan_range, graphic)
                if items:
                    all_resources.extend(items)
            except:
                continue

        return all_resources

    def is_on_cooldown(self, serial):
        """Check if resource is on cooldown.

        Args:
            serial: Resource serial

        Returns:
            True if on cooldown, False otherwise
        """
        return time.time() < self.cooldown_dict.get(serial, 0) + self.cooldown_duration

    def mark_on_cooldown(self, serial):
        """Mark resource as on cooldown.

        Args:
            serial: Resource serial
        """
        self.cooldown_dict[serial] = time.time()

    def find_nearest(self, exclude_cooldown=True):
        """Find nearest resource not on cooldown.

        Args:
            exclude_cooldown: Exclude resources on cooldown (default True)

        Returns:
            Nearest resource item or None
        """
        resources = self.find_resources()

        if not resources:
            return None

        # Filter cooldown
        if exclude_cooldown:
            resources = [r for r in resources if not self.is_on_cooldown(getattr(r, 'Serial', 0))]

        if not resources:
            return None

        # Sort by distance
        return min(resources, key=lambda r: getattr(r, 'Distance', 999))

    def prune_cooldowns(self, max_entries=100):
        """Prune old cooldown entries to prevent memory leak.

        Args:
            max_entries: Max cooldown entries to keep (default 100)
        """
        if len(self.cooldown_dict) > max_entries:
            # Remove oldest entries
            sorted_items = sorted(self.cooldown_dict.items(), key=lambda x: x[1])
            self.cooldown_dict = dict(sorted_items[-max_entries:])

# ============ HARVESTER ============

class Harvester:
    """Perform harvesting actions with tool.

    Features:
    - Tool-based harvesting
    - AOE self-targeting mode
    - Target-specific mode
    - Journal checking
    """

    def __init__(self, tool_serial, harvest_delay=2.5):
        """Initialize harvester.

        Args:
            tool_serial: Serial of harvesting tool
            harvest_delay: Time to complete harvest (default 2.5s)
        """
        self.tool_serial = tool_serial
        self.harvest_delay = harvest_delay
        self.use_aoe = False  # AOE self-targeting mode

    def get_tool(self):
        """Get tool item.

        Returns:
            Tool item or None
        """
        if self.tool_serial == 0:
            return None
        return API.FindItem(self.tool_serial)

    def harvest(self, target_serial=None):
        """Perform harvest action.

        Args:
            target_serial: Target resource serial (None for AOE mode)

        Returns:
            True if action performed, False otherwise
        """
        tool = self.get_tool()
        if not tool:
            return False

        API.ClearJournal()

        if self.use_aoe:
            # AOE self-targeting
            API.PreTarget(API.Player.Serial, "neutral")
            API.Pause(0.1)
            API.UseObject(self.tool_serial, False)
            API.Pause(0.2)
            API.CancelPreTarget()
        else:
            # Target specific resource
            API.UseObject(self.tool_serial, False)
            API.Pause(0.3)

            if target_serial:
                if API.WaitForTarget(timeout=2.0):
                    API.Target(target_serial)
            else:
                # Wait for player to target
                API.WaitForTarget(timeout=5.0)

        return True

    def check_journal(self, success_messages, failure_messages):
        """Check journal for success/failure messages.

        Args:
            success_messages: List of success message strings
            failure_messages: List of failure message strings

        Returns:
            "success", "depleted", or "unknown"
        """
        for msg in success_messages:
            if API.InJournal(msg):
                return "success"

        for msg in failure_messages:
            if API.InJournal(msg):
                return "depleted"

        return "unknown"

# ============ SESSION STATS ============

class SessionStats:
    """Track session statistics.

    Features:
    - Resource counting
    - Rate calculations
    - Session timing
    """

    def __init__(self):
        """Initialize session stats."""
        self.start_time = time.time()
        self.stats = {}

    def reset(self):
        """Reset all stats."""
        self.start_time = time.time()
        self.stats = {}

    def increment(self, key, amount=1):
        """Increment stat counter.

        Args:
            key: Stat name
            amount: Amount to increment (default 1)
        """
        self.stats[key] = self.stats.get(key, 0) + amount

    def get(self, key, default=0):
        """Get stat value.

        Args:
            key: Stat name
            default: Default value if not found (default 0)

        Returns:
            Stat value
        """
        return self.stats.get(key, default)

    def get_runtime(self):
        """Get session runtime in seconds.

        Returns:
            Runtime in seconds
        """
        return time.time() - self.start_time

    def get_rate(self, key):
        """Get stat rate per hour.

        Args:
            key: Stat name

        Returns:
            Rate per hour
        """
        runtime = self.get_runtime()
        if runtime <= 0:
            return 0

        value = self.get(key, 0)
        return (value / runtime) * 3600
