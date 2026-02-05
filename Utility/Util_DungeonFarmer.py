# Util_DungeonFarmer_v1.py
#
# A comprehensive dungeon farming script for tamer characters.
# Handles navigation, combat, pet healing, looting, banking, and supply management.
#
# Features:
# - Hybrid patrol system with randomized movement
# - Multi-factor danger assessment
# - Built-in pet healing with vet kit AOE support
# - Selective instant looting
# - Realistic banking behavior
# - Comprehensive GUI with real-time configuration
#
# Setup:
# 1. Load script via TazUO Script Manager
# 2. Configure farming areas and runebook
# 3. Set vet kit graphic if available
# 4. Press START to begin farming

import API
import time

# ========== CONSTANTS ==========
KEY_PREFIX = "DungeonFarmer_"
BANDAGE_GRAPHIC = 0x0E21
BANDAGE_COOLDOWN = 10.0  # Seconds between bandages per target
HEAL_RANGE = 2  # Tiles

# Timing constants for healing actions
BANDAGE_DELAY = 4.5  # Seconds for bandage to complete
VETKIT_DELAY = 5.0   # Seconds for vet kit to complete
CURE_DELAY = 2.5     # Seconds for cure spell to complete

# ========== PET MANAGER CLASS ==========
class PetManager:
    """Handles pet detection, tracking, and tank designation"""

    def __init__(self):
        self.pets = []  # List of {"serial": int, "name": str, "is_tank": bool}
        self.tank_pet_serial = self._load_tank_serial()

    def _load_tank_serial(self):
        """Load saved tank pet serial from persistence"""
        saved = API.GetPersistentVar(KEY_PREFIX + "TankSerial", "0", API.PersistentVar.Char)
        return int(saved) if saved.isdigit() else 0

    def _save_tank_serial(self):
        """Save tank pet serial to persistence"""
        API.SavePersistentVar(KEY_PREFIX + "TankSerial", str(self.tank_pet_serial), API.PersistentVar.Char)

    def scan_pets(self):
        """Scan for owned pets (Notoriety == 1) and update pet list"""
        try:
            all_mobiles = API.Mobiles.GetMobiles()
            pet_data = []

            for mob in all_mobiles:
                if mob and not mob.IsDead and mob.Notoriety == 1:  # Owned pet
                    pet_data.append({
                        "serial": mob.Serial,
                        "name": mob.Name,
                        "max_hp": mob.HitsMax,
                        "is_tank": mob.Serial == self.tank_pet_serial
                    })

            # Sort by max HP (highest first)
            pet_data.sort(key=lambda p: p["max_hp"], reverse=True)

            # Auto-designate tank if not set or invalid
            if self.tank_pet_serial == 0 or not any(p["serial"] == self.tank_pet_serial for p in pet_data):
                if pet_data:
                    self.tank_pet_serial = pet_data[0]["serial"]
                    pet_data[0]["is_tank"] = True
                    self._save_tank_serial()

            self.pets = pet_data
            return len(self.pets)

        except Exception as e:
            API.SysMsg("PetManager.scan_pets error: " + str(e), 32)
            return 0

    def get_pet_info(self, serial):
        """Get pet info dict by serial, returns None if not found"""
        for pet in self.pets:
            if pet["serial"] == serial:
                return pet
        return None

    def get_tank_pet(self):
        """Returns tank pet dict or None"""
        return self.get_pet_info(self.tank_pet_serial)

    def set_tank_pet(self, serial):
        """Change tank designation"""
        # Remove tank flag from all pets
        for pet in self.pets:
            pet["is_tank"] = False

        # Set new tank
        self.tank_pet_serial = serial
        pet_info = self.get_pet_info(serial)
        if pet_info:
            pet_info["is_tank"] = True

        self._save_tank_serial()

    def validate_pets(self):
        """Remove dead/invalid pets from list"""
        valid_pets = []
        for pet in self.pets:
            mob = API.Mobiles.FindMobile(pet["serial"])
            if mob and not mob.IsDead:
                valid_pets.append(pet)
        self.pets = valid_pets

    @property
    def pet_count(self):
        """Number of tracked pets"""
        return len(self.pets)

    @property
    def all_pets_alive(self):
        """Check if all tracked pets are alive"""
        for pet in self.pets:
            mob = API.Mobiles.FindMobile(pet["serial"])
            if not mob or mob.IsDead:
                return False
        return True

    def get_pet_by_name(self, name):
        """Find pet by name (for resurrection targeting)"""
        for pet in self.pets:
            if pet["name"].lower() == name.lower():
                return pet
        return None


# ========== HEALING SYSTEM CLASS ==========
class HealingSystem:
    """Handles healing priority and decision-making"""

    def __init__(self, pet_manager):
        self.pet_manager = pet_manager

        # Configurable thresholds (percentages)
        self.player_critical_threshold = 50
        self.player_bandage_threshold = 85
        self.tank_critical_threshold = 40
        self.tank_heal_threshold = 70
        self.pet_heal_threshold = 50
        self.pet_topoff_threshold = 90

        # Bandage cooldown tracking: {serial: last_bandage_time}
        self.bandage_cooldowns = {}

        # Vet kit settings (will be extended in vet kit task)
        self.vet_kit_graphic = 0
        self.vet_kit_hp_threshold = 90
        self.vet_kit_min_pets_hurt = 2
        self.vet_kit_cooldown = 5.0
        self.vet_kit_critical_hp = 50
        self.last_vetkit_use = 0
        self.out_of_vetkit_warned = False

        # Healing state tracking
        self.STATE = "idle"  # idle, healing
        self.heal_start_time = 0
        self.current_heal_target = 0
        self.current_heal_type = ""
        self.out_of_bandages_warned = False

        # Statistics tracking
        self.bandages_used = 0
        self.vetkits_used = 0
        self.cures_cast = 0

    def can_bandage(self, target_serial):
        """Check if target's bandage cooldown has expired"""
        if target_serial not in self.bandage_cooldowns:
            return True

        elapsed = time.time() - self.bandage_cooldowns[target_serial]
        return elapsed >= BANDAGE_COOLDOWN

    def track_bandage_cooldown(self, target_serial):
        """Record bandage use on target"""
        self.bandage_cooldowns[target_serial] = time.time()

    def _get_hp_percent(self, mob):
        """Safely get HP percentage for a mobile"""
        if mob is None or mob.IsDead:
            return 100
        if mob.HitsMax == 0:
            return 100
        return (mob.Hits / mob.HitsMax) * 100

    def _is_in_range(self, mob):
        """Check if mobile is within heal range"""
        if mob is None or mob.IsDead:
            return False
        return mob.Distance <= HEAL_RANGE

    def _is_poisoned(self, mob):
        """Check if mobile is poisoned"""
        if mob is None or mob.IsDead:
            return False
        return getattr(mob, 'IsPoisoned', False) or getattr(mob, 'Poisoned', False)

    def check_vetkit_conditions(self):
        """Check if vet kit should be used (called from get_next_heal_action)"""
        # Not configured or not available
        if self.vet_kit_graphic == 0:
            return False

        vet_kit = API.FindType(self.vet_kit_graphic)
        if not vet_kit:
            if not self.out_of_vetkit_warned:
                API.SysMsg("Out of vet kits!", 32)
                self.out_of_vetkit_warned = True
            return False
        else:
            self.out_of_vetkit_warned = False

        # Don't use vet kit if pets need rezzing
        if not self.pet_manager.all_pets_alive:
            return False

        # Count pets hurt and critically hurt
        hurt_count = 0
        critical_count = 0

        for pet_info in self.pet_manager.pets:
            mob = API.Mobiles.FindMobile(pet_info["serial"])
            if mob and not mob.IsDead and self._is_in_range(mob):
                hp_pct = self._get_hp_percent(mob)
                if hp_pct < self.vet_kit_hp_threshold:
                    hurt_count += 1
                if hp_pct < self.vet_kit_critical_hp:
                    critical_count += 1

        # Check cooldown (bypass if critical situation)
        cooldown_expired = (time.time() - self.last_vetkit_use) >= self.vet_kit_cooldown
        emergency_bypass = critical_count >= 2

        # Use vet kit if enough pets hurt and (cooldown ok OR emergency)
        return hurt_count >= self.vet_kit_min_pets_hurt and (cooldown_expired or emergency_bypass)

    def use_vetkit(self):
        """Execute vet kit usage"""
        vet_kit = API.FindType(self.vet_kit_graphic)
        if vet_kit:
            API.UseObject(vet_kit.Serial, False)
            self.last_vetkit_use = time.time()
            API.HeadMsg("Vet Kit!", API.Player.Serial, 68)
            return True
        return False

    def get_next_heal_action(self):
        """
        Determine next heal action based on priority system.
        Returns tuple: (target_serial, action_type, is_self)
        action_type: "bandage_self", "bandage_pet", "vetkit", "cure"
        Returns None if nothing needs healing
        """
        player_hp_pct = self._get_hp_percent(API.Player)

        # PRIORITY 1: Player critical (< 50%)
        if player_hp_pct < self.player_critical_threshold:
            if self.can_bandage(API.Player.Serial):
                return (API.Player.Serial, "bandage_self", True)

        # Get tank pet
        tank_pet_info = self.pet_manager.get_tank_pet()
        tank_mob = None
        tank_hp_pct = 100

        if tank_pet_info:
            tank_mob = API.Mobiles.FindMobile(tank_pet_info["serial"])
            if tank_mob and not tank_mob.IsDead and self._is_in_range(tank_mob):
                tank_hp_pct = self._get_hp_percent(tank_mob)

        # PRIORITY 2: Tank pet critical (< 40%)
        if tank_mob and tank_hp_pct < self.tank_critical_threshold:
            if self.can_bandage(tank_mob.Serial):
                return (tank_mob.Serial, "bandage_pet", False)

        # PRIORITY 3: Player normal (< 85%)
        if player_hp_pct < self.player_bandage_threshold:
            if self.can_bandage(API.Player.Serial):
                return (API.Player.Serial, "bandage_self", True)

        # PRIORITY 4: Vet kit AOE (2+ pets hurt)
        if self.check_vetkit_conditions():
            return (0, "vetkit", False)

        # PRIORITY 5: Tank pet normal (< 70%)
        if tank_mob and tank_hp_pct < self.tank_heal_threshold:
            if self.can_bandage(tank_mob.Serial):
                return (tank_mob.Serial, "bandage_pet", False)

        # PRIORITY 6: Other pets poisoned
        for pet_info in self.pet_manager.pets:
            if pet_info["is_tank"]:
                continue  # Already handled tank

            mob = API.Mobiles.FindMobile(pet_info["serial"])
            if mob and not mob.IsDead and self._is_in_range(mob):
                if self._is_poisoned(mob):
                    # For now, bandage poisoned pets (cure spell will be added later)
                    if self.can_bandage(mob.Serial):
                        return (mob.Serial, "cure", False)

        # PRIORITY 7: Other pets injured (< 50%)
        for pet_info in self.pet_manager.pets:
            if pet_info["is_tank"]:
                continue

            mob = API.Mobiles.FindMobile(pet_info["serial"])
            if mob and not mob.IsDead and self._is_in_range(mob):
                hp_pct = self._get_hp_percent(mob)
                if hp_pct < self.pet_heal_threshold:
                    if self.can_bandage(mob.Serial):
                        return (mob.Serial, "bandage_pet", False)

        # PRIORITY 8: Top-off heals (< 90%)
        # Check tank first for top-off
        if tank_mob and tank_hp_pct < self.pet_topoff_threshold:
            if self.can_bandage(tank_mob.Serial):
                return (tank_mob.Serial, "bandage_pet", False)

        # Then check other pets
        for pet_info in self.pet_manager.pets:
            if pet_info["is_tank"]:
                continue

            mob = API.Mobiles.FindMobile(pet_info["serial"])
            if mob and not mob.IsDead and self._is_in_range(mob):
                hp_pct = self._get_hp_percent(mob)
                if hp_pct < self.pet_topoff_threshold:
                    if self.can_bandage(mob.Serial):
                        return (mob.Serial, "bandage_pet", False)

        # Nothing needs healing
        return None

    def execute_heal(self, target_serial, action_type, is_self):
        """
        Execute a healing action.

        Args:
            target_serial: Serial of target (0 for vetkit AOE)
            action_type: "bandage_self", "bandage_pet", "vetkit", or "cure"
            is_self: True if healing self, False otherwise

        Returns:
            True if action started successfully, False otherwise
        """
        try:
            # Handle bandage_self
            if action_type == "bandage_self":
                bandage = API.FindType(BANDAGE_GRAPHIC)
                if not bandage:
                    if not self.out_of_bandages_warned:
                        API.SysMsg("Out of bandages!", 32)
                        self.out_of_bandages_warned = True
                    return False
                else:
                    self.out_of_bandages_warned = False

                # Use bandage on self
                API.UseObject(bandage.Serial, False)
                self.STATE = "healing"
                self.heal_start_time = time.time()
                self.current_heal_target = target_serial
                self.current_heal_type = action_type
                self.track_bandage_cooldown(target_serial)
                self.bandages_used += 1
                return True

            # Handle bandage_pet
            elif action_type == "bandage_pet":
                bandage = API.FindType(BANDAGE_GRAPHIC)
                if not bandage:
                    if not self.out_of_bandages_warned:
                        API.SysMsg("Out of bandages!", 32)
                        self.out_of_bandages_warned = True
                    return False
                else:
                    self.out_of_bandages_warned = False

                # Check if target is in range
                target_mob = API.Mobiles.FindMobile(target_serial)
                if not target_mob or target_mob.IsDead or not self._is_in_range(target_mob):
                    return False

                # Cancel any existing targets
                if API.HasTarget():
                    API.CancelTarget()
                API.CancelPreTarget()

                # Setup and execute targeting
                API.PreTarget(target_serial, "beneficial")
                API.Pause(0.1)
                API.UseObject(bandage.Serial, False)
                API.Pause(0.1)
                API.CancelPreTarget()

                self.STATE = "healing"
                self.heal_start_time = time.time()
                self.current_heal_target = target_serial
                self.current_heal_type = action_type
                self.track_bandage_cooldown(target_serial)
                self.bandages_used += 1
                return True

            # Handle vetkit
            elif action_type == "vetkit":
                if self.use_vetkit():
                    self.STATE = "healing"
                    self.heal_start_time = time.time()
                    self.current_heal_target = 0
                    self.current_heal_type = action_type
                    self.vetkits_used += 1
                    return True
                return False

            # Handle cure (poison cure for pets)
            elif action_type == "cure":
                # For now, use bandages on poisoned pets
                # Full magery cure spell will be added later
                bandage = API.FindType(BANDAGE_GRAPHIC)
                if not bandage:
                    if not self.out_of_bandages_warned:
                        API.SysMsg("Out of bandages!", 32)
                        self.out_of_bandages_warned = True
                    return False
                else:
                    self.out_of_bandages_warned = False

                # Check if target is in range
                target_mob = API.Mobiles.FindMobile(target_serial)
                if not target_mob or target_mob.IsDead or not self._is_in_range(target_mob):
                    return False

                # Cancel any existing targets
                if API.HasTarget():
                    API.CancelTarget()
                API.CancelPreTarget()

                # Setup and execute targeting
                API.PreTarget(target_serial, "beneficial")
                API.Pause(0.1)
                API.UseObject(bandage.Serial, False)
                API.Pause(0.1)
                API.CancelPreTarget()

                self.STATE = "healing"
                self.heal_start_time = time.time()
                self.current_heal_target = target_serial
                self.current_heal_type = action_type
                self.track_bandage_cooldown(target_serial)
                self.cures_cast += 1
                self.bandages_used += 1
                return True

            return False

        except Exception as e:
            API.SysMsg("execute_heal error: " + str(e), 32)
            self.STATE = "idle"
            return False

    def check_heal_complete(self):
        """
        Check if current healing action has completed.

        Returns:
            True if healing is complete or no healing in progress
        """
        if self.STATE != "healing":
            return True

        # Determine delay based on heal type
        delay = BANDAGE_DELAY
        if self.current_heal_type == "vetkit":
            delay = VETKIT_DELAY
        elif self.current_heal_type == "cure":
            delay = CURE_DELAY

        # Check if enough time has passed
        if time.time() > self.heal_start_time + delay:
            self.STATE = "idle"
            self.current_heal_target = 0
            self.current_heal_type = ""
            return True

        return False

    def set_vetkit_graphic(self, graphic):
        """Set vet kit graphic and save to persistence"""
        self.vet_kit_graphic = graphic
        API.SavePersistentVar(KEY_PREFIX + "VetKitGraphic", str(graphic), API.PersistentVar.Char)

    def load_vetkit_graphic(self):
        """Load vet kit graphic from persistence"""
        saved = API.GetPersistentVar(KEY_PREFIX + "VetKitGraphic", "0", API.PersistentVar.Char)
        self.vet_kit_graphic = int(saved) if saved.isdigit() else 0

    def configure_thresholds(self, player_crit=None, player_norm=None, tank_crit=None, tank_norm=None, pet_heal=None, pet_topoff=None):
        """Update healing thresholds"""
        if player_crit is not None:
            self.player_critical_threshold = player_crit
        if player_norm is not None:
            self.player_bandage_threshold = player_norm
        if tank_crit is not None:
            self.tank_critical_threshold = tank_crit
        if tank_norm is not None:
            self.tank_heal_threshold = tank_norm
        if pet_heal is not None:
            self.pet_heal_threshold = pet_heal
        if pet_topoff is not None:
            self.pet_topoff_threshold = pet_topoff

    def configure_vetkit(self, hp_threshold=None, min_pets_hurt=None, cooldown=None, critical_hp=None):
        """Update vet kit configuration"""
        if hp_threshold is not None:
            self.vet_kit_hp_threshold = hp_threshold
        if min_pets_hurt is not None:
            self.vet_kit_min_pets_hurt = min_pets_hurt
        if cooldown is not None:
            self.vet_kit_cooldown = cooldown
        if critical_hp is not None:
            self.vet_kit_critical_hp = critical_hp

    def get_vetkit_status(self):
        """Get vet kit readiness status"""
        if self.vet_kit_graphic == 0:
            return "not_configured"

        vet_kit = API.FindType(self.vet_kit_graphic)
        if not vet_kit:
            return "not_found"

        cooldown_remaining = self.vet_kit_cooldown - (time.time() - self.last_vetkit_use)
        if cooldown_remaining > 0:
            return "cooldown"

        return "ready"


# ========== SAFE SPOT CLASS ==========
class SafeSpot:
    """Represents a safe spot location with escape method"""

    def __init__(self, x, y, escape_method="direct_recall", gump_id=0, button_id=0, is_primary=True):
        """
        Initialize a safe spot.

        Args:
            x, y: Coordinates of the safe spot
            escape_method: "direct_recall", "gump_gate", "timer_gate", or "run_outside"
            gump_id: Gump ID if using gump_gate method
            button_id: Button ID if using gump_gate method
            is_primary: True for primary safe spot, False for backup
        """
        self.x = x
        self.y = y
        self.escape_method = escape_method
        self.gump_id = gump_id
        self.button_id = button_id
        self.is_primary = is_primary

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "x": self.x,
            "y": self.y,
            "escape_method": self.escape_method,
            "gump_id": self.gump_id,
            "button_id": self.button_id,
            "is_primary": self.is_primary
        }

    @staticmethod
    def from_dict(data):
        """Create SafeSpot from dictionary"""
        return SafeSpot(
            x=data.get("x", 0),
            y=data.get("y", 0),
            escape_method=data.get("escape_method", "direct_recall"),
            gump_id=data.get("gump_id", 0),
            button_id=data.get("button_id", 0),
            is_primary=data.get("is_primary", True)
        )

    def get_distance_to(self, x, y):
        """Calculate distance from this safe spot to given coordinates"""
        import math
        return math.sqrt((self.x - x) ** 2 + (self.y - y) ** 2)


# ========== FARMING AREA CLASS ==========
class FarmingArea:
    """Represents a farming area with configuration"""

    def __init__(self, name, area_type="circle"):
        """
        Initialize a farming area.

        Args:
            name: Unique name for this area
            area_type: "circle" or "waypoints"
        """
        self.name = name
        self.area_type = area_type

        # Circle area properties
        self.center_x = 0
        self.center_y = 0
        self.radius = 0

        # Waypoint area properties
        self.waypoints = []  # List of (x, y) tuples

        # Area configuration
        self.difficulty = "medium"  # "low", "medium", "high"
        self.safe_spots = []  # List of SafeSpot objects
        self.loot_filter = []  # List of graphic IDs to collect
        self.notes = ""

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "name": self.name,
            "area_type": self.area_type,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "radius": self.radius,
            "waypoints": self.waypoints,
            "difficulty": self.difficulty,
            "safe_spots": [spot.to_dict() for spot in self.safe_spots],
            "loot_filter": self.loot_filter,
            "notes": self.notes
        }

    @staticmethod
    def from_dict(data):
        """Create FarmingArea from dictionary"""
        area = FarmingArea(
            name=data.get("name", "Unnamed"),
            area_type=data.get("area_type", "circle")
        )

        area.center_x = data.get("center_x", 0)
        area.center_y = data.get("center_y", 0)
        area.radius = data.get("radius", 0)
        area.waypoints = [tuple(wp) for wp in data.get("waypoints", [])]
        area.difficulty = data.get("difficulty", "medium")
        area.safe_spots = [SafeSpot.from_dict(spot) for spot in data.get("safe_spots", [])]
        area.loot_filter = data.get("loot_filter", [])
        area.notes = data.get("notes", "")

        return area

    def is_in_area(self, x, y):
        """Check if coordinates are within this farming area"""
        import math

        if self.area_type == "circle":
            # Calculate distance from center
            distance = math.sqrt((x - self.center_x) ** 2 + (y - self.center_y) ** 2)
            return distance <= self.radius

        elif self.area_type == "waypoints":
            # For waypoint-based areas, check if within reasonable distance of any waypoint
            # Use radius of 15 tiles from any waypoint
            for wp_x, wp_y in self.waypoints:
                distance = math.sqrt((x - wp_x) ** 2 + (y - wp_y) ** 2)
                if distance <= 15:
                    return True
            return False

        return False

    def get_nearest_safe_spot(self, x, y):
        """Get the nearest safe spot to given coordinates"""
        if not self.safe_spots:
            return None

        nearest = None
        min_distance = float('inf')

        for spot in self.safe_spots:
            distance = spot.get_distance_to(x, y)
            if distance < min_distance:
                min_distance = distance
                nearest = spot

        return nearest

    def get_primary_safe_spot(self):
        """Get the primary safe spot, or first safe spot if no primary marked"""
        for spot in self.safe_spots:
            if spot.is_primary:
                return spot

        # Return first spot if no primary
        return self.safe_spots[0] if self.safe_spots else None


# ========== AREA MANAGER CLASS ==========
class AreaManager:
    """Manages farming areas with persistence"""

    def __init__(self):
        self.areas = {}  # Cache: {name: FarmingArea}
        self._load_area_list()

    def _load_area_list(self):
        """Load list of area names from persistence"""
        area_list_str = API.GetPersistentVar(KEY_PREFIX + "AreaList", "", API.PersistentVar.Char)
        if area_list_str:
            area_names = [name.strip() for name in area_list_str.split("|") if name.strip()]
            for name in area_names:
                # Load each area into cache
                self._load_area_from_persistence(name)

    def _save_area_list(self):
        """Save list of area names to persistence"""
        area_names = list(self.areas.keys())
        area_list_str = "|".join(area_names)
        API.SavePersistentVar(KEY_PREFIX + "AreaList", area_list_str, API.PersistentVar.Char)

    def _load_area_from_persistence(self, name):
        """Load a specific area from persistence into cache"""
        import json

        key = KEY_PREFIX + "Area_" + name
        json_str = API.GetPersistentVar(key, "", API.PersistentVar.Char)

        if json_str:
            try:
                data = json.loads(json_str)
                area = FarmingArea.from_dict(data)
                self.areas[name] = area
                return area
            except Exception as e:
                API.SysMsg("Error loading area " + name + ": " + str(e), 32)
                return None

        return None

    def add_area(self, area):
        """
        Add or update a farming area.

        Args:
            area: FarmingArea object to save

        Returns:
            True if saved successfully, False otherwise
        """
        import json

        try:
            # Add to cache
            self.areas[area.name] = area

            # Serialize to JSON
            json_str = json.dumps(area.to_dict())

            # Save to persistence
            key = KEY_PREFIX + "Area_" + area.name
            API.SavePersistentVar(key, json_str, API.PersistentVar.Char)

            # Update area list
            self._save_area_list()

            return True

        except Exception as e:
            API.SysMsg("Error saving area: " + str(e), 32)
            return False

    def get_area(self, name):
        """
        Retrieve a farming area by name.

        Args:
            name: Area name

        Returns:
            FarmingArea object or None if not found
        """
        # Check cache first
        if name in self.areas:
            return self.areas[name]

        # Try loading from persistence
        return self._load_area_from_persistence(name)

    def list_areas(self):
        """
        Get list of all area names.

        Returns:
            List of area name strings
        """
        return list(self.areas.keys())

    def delete_area(self, name):
        """
        Delete a farming area.

        Args:
            name: Area name to delete

        Returns:
            True if deleted, False if not found
        """
        if name not in self.areas:
            return False

        try:
            # Remove from cache
            del self.areas[name]

            # Remove from persistence
            key = KEY_PREFIX + "Area_" + name
            API.SavePersistentVar(key, "", API.PersistentVar.Char)

            # Update area list
            self._save_area_list()

            return True

        except Exception as e:
            API.SysMsg("Error deleting area: " + str(e), 32)
            return False

    def get_current_area(self):
        """
        Get the farming area player is currently in (by proximity).

        Returns:
            FarmingArea object or None if not in any area
        """
        player_x = getattr(API.Player, 'X', 0)
        player_y = getattr(API.Player, 'Y', 0)

        for area in self.areas.values():
            if area.is_in_area(player_x, player_y):
                return area

        return None

    def get_area_count(self):
        """Get total number of configured areas"""
        return len(self.areas)


# ========== AREA RECORDING GUMP ==========
class AreaRecordingGump:
    """GUI for recording farming areas in-game"""

    def __init__(self, area_manager):
        """
        Initialize the area recording gump.

        Args:
            area_manager: AreaManager instance to save areas to
        """
        self.area_manager = area_manager
        self.gump = None
        self.controls = {}

        # Recording state
        self.area_name = ""
        self.area_type = "circle"  # "circle" or "waypoints"
        self.center_x = 0
        self.center_y = 0
        self.radius = 10
        self.waypoints = []
        self.recording_waypoints = False
        self.difficulty = "medium"
        self.safe_spot_panel_open = False

        # Safe spot recording state
        self.safe_spot_x = 0
        self.safe_spot_y = 0
        self.safe_spot_escape_method = "direct_recall"
        self.safe_spot_gump_id = 0
        self.safe_spot_button_id = 0

        self._build_gump()

    def _build_gump(self):
        """Build the area recording gump UI"""
        try:
            self.gump = API.Gumps.CreateGump()
            self.gump.SetRect(100, 100, 400, 450)

            y_offset = 10

            # Title
            title = API.Gumps.CreateGumpTTFLabel("Record Farming Area", 16, "#ffaa00")
            title.SetPos(10, y_offset)
            self.gump.AddControl(title)
            y_offset += 30

            # Area name input
            name_label = API.Gumps.CreateGumpTTFLabel("Area Name:", 15, "#ffffff")
            name_label.SetPos(10, y_offset)
            self.gump.AddControl(name_label)

            name_input = API.Gumps.CreateGumpTextBox("", 250, 22)
            name_input.SetPos(120, y_offset)
            self.controls["name_input"] = name_input
            self.gump.AddControl(name_input)
            y_offset += 35

            # Area type radio buttons
            type_label = API.Gumps.CreateGumpTTFLabel("Area Type:", 15, "#ffffff")
            type_label.SetPos(10, y_offset)
            self.gump.AddControl(type_label)

            circle_btn = API.Gumps.CreateSimpleButton("[Circle]", 80, 22)
            circle_btn.SetPos(120, y_offset)
            circle_btn.SetBackgroundHue(68 if self.area_type == "circle" else 90)
            self.controls["circle_btn"] = circle_btn
            self.gump.AddControl(circle_btn)
            API.Gumps.AddControlOnClick(circle_btn, self._on_circle_mode)

            waypoints_btn = API.Gumps.CreateSimpleButton("[Waypoints]", 95, 22)
            waypoints_btn.SetPos(210, y_offset)
            waypoints_btn.SetBackgroundHue(68 if self.area_type == "waypoints" else 90)
            self.controls["waypoints_btn"] = waypoints_btn
            self.gump.AddControl(waypoints_btn)
            API.Gumps.AddControlOnClick(waypoints_btn, self._on_waypoints_mode)
            y_offset += 35

            # Mode-specific controls container
            self.controls["mode_container_y"] = y_offset
            self._rebuild_mode_controls()

            API.Gumps.AddGump(self.gump)

        except Exception as e:
            API.SysMsg("Error building AreaRecordingGump: " + str(e), 32)

    def _rebuild_mode_controls(self):
        """Rebuild mode-specific controls based on current area_type"""
        # Remove old mode controls
        for key in list(self.controls.keys()):
            if key.startswith("mode_"):
                del self.controls[key]

        y_offset = self.controls["mode_container_y"]

        if self.area_type == "circle":
            y_offset = self._build_circle_controls(y_offset)
        else:
            y_offset = self._build_waypoints_controls(y_offset)

        # Difficulty dropdown (common to both modes)
        y_offset += 10
        diff_label = API.Gumps.CreateGumpTTFLabel("Difficulty:", 15, "#ffffff")
        diff_label.SetPos(10, y_offset)
        self.controls["mode_diff_label"] = diff_label
        self.gump.AddControl(diff_label)

        low_btn = API.Gumps.CreateSimpleButton("[Low]", 60, 22)
        low_btn.SetPos(120, y_offset)
        low_btn.SetBackgroundHue(68 if self.difficulty == "low" else 90)
        self.controls["mode_diff_low"] = low_btn
        self.gump.AddControl(low_btn)
        API.Gumps.AddControlOnClick(low_btn, lambda: self._on_difficulty_change("low"))

        med_btn = API.Gumps.CreateSimpleButton("[Medium]", 75, 22)
        med_btn.SetPos(190, y_offset)
        med_btn.SetBackgroundHue(68 if self.difficulty == "medium" else 90)
        self.controls["mode_diff_med"] = med_btn
        self.gump.AddControl(med_btn)
        API.Gumps.AddControlOnClick(med_btn, lambda: self._on_difficulty_change("medium"))

        high_btn = API.Gumps.CreateSimpleButton("[High]", 65, 22)
        high_btn.SetPos(275, y_offset)
        high_btn.SetBackgroundHue(68 if self.difficulty == "high" else 90)
        self.controls["mode_diff_high"] = high_btn
        self.gump.AddControl(high_btn)
        API.Gumps.AddControlOnClick(high_btn, lambda: self._on_difficulty_change("high"))
        y_offset += 35

        # Record Safe Spot button
        safe_spot_btn = API.Gumps.CreateSimpleButton("[Record Safe Spot]", 150, 22)
        safe_spot_btn.SetPos(10, y_offset)
        self.controls["mode_safe_spot_btn"] = safe_spot_btn
        self.gump.AddControl(safe_spot_btn)
        API.Gumps.AddControlOnClick(safe_spot_btn, self._on_record_safe_spot)
        y_offset += 35

        # Save and Cancel buttons
        save_btn = API.Gumps.CreateSimpleButton("[Save Area]", 150, 22)
        save_btn.SetPos(10, y_offset)
        save_btn.SetBackgroundHue(68)
        self.controls["mode_save_btn"] = save_btn
        self.gump.AddControl(save_btn)
        API.Gumps.AddControlOnClick(save_btn, self._on_save_area)

        cancel_btn = API.Gumps.CreateSimpleButton("[Cancel]", 100, 22)
        cancel_btn.SetPos(170, y_offset)
        cancel_btn.SetBackgroundHue(32)
        self.controls["mode_cancel_btn"] = cancel_btn
        self.gump.AddControl(cancel_btn)
        API.Gumps.AddControlOnClick(cancel_btn, self._on_cancel)

    def _build_circle_controls(self, y_offset):
        """Build controls for circle mode"""
        # Set Center button
        center_btn = API.Gumps.CreateSimpleButton("[Set Center]", 120, 22)
        center_btn.SetPos(10, y_offset)
        self.controls["mode_center_btn"] = center_btn
        self.gump.AddControl(center_btn)
        API.Gumps.AddControlOnClick(center_btn, self._on_set_center)
        y_offset += 30

        # Center coordinates display
        center_text = "Center: (" + str(self.center_x) + ", " + str(self.center_y) + ")"
        if self.center_x == 0 and self.center_y == 0:
            center_text = "Center: (not set)"
        center_label = API.Gumps.CreateGumpTTFLabel(center_text, 15, "#ffcc00")
        center_label.SetPos(10, y_offset)
        self.controls["mode_center_label"] = center_label
        self.gump.AddControl(center_label)
        y_offset += 30

        # Radius label
        radius_label = API.Gumps.CreateGumpTTFLabel("Radius: " + str(self.radius) + " tiles", 15, "#ffffff")
        radius_label.SetPos(10, y_offset)
        self.controls["mode_radius_label"] = radius_label
        self.gump.AddControl(radius_label)
        y_offset += 25

        # Radius adjustment buttons
        minus_btn = API.Gumps.CreateSimpleButton("[-]", 30, 22)
        minus_btn.SetPos(10, y_offset)
        self.controls["mode_radius_minus"] = minus_btn
        self.gump.AddControl(minus_btn)
        API.Gumps.AddControlOnClick(minus_btn, self._on_radius_decrease)

        plus_btn = API.Gumps.CreateSimpleButton("[+]", 30, 22)
        plus_btn.SetPos(50, y_offset)
        self.controls["mode_radius_plus"] = plus_btn
        self.gump.AddControl(plus_btn)
        API.Gumps.AddControlOnClick(plus_btn, self._on_radius_increase)
        y_offset += 30

        return y_offset

    def _build_waypoints_controls(self, y_offset):
        """Build controls for waypoints mode"""
        # Recording buttons
        if not self.recording_waypoints:
            start_btn = API.Gumps.CreateSimpleButton("[Start Recording]", 150, 22)
            start_btn.SetPos(10, y_offset)
            start_btn.SetBackgroundHue(68)
            self.controls["mode_start_recording"] = start_btn
            self.gump.AddControl(start_btn)
            API.Gumps.AddControlOnClick(start_btn, self._on_start_recording)
        else:
            add_btn = API.Gumps.CreateSimpleButton("[Add Waypoint] (F5)", 150, 22)
            add_btn.SetPos(10, y_offset)
            add_btn.SetBackgroundHue(43)
            self.controls["mode_add_waypoint"] = add_btn
            self.gump.AddControl(add_btn)
            API.Gumps.AddControlOnClick(add_btn, self._on_add_waypoint)

            stop_btn = API.Gumps.CreateSimpleButton("[Stop Recording]", 120, 22)
            stop_btn.SetPos(170, y_offset)
            stop_btn.SetBackgroundHue(32)
            self.controls["mode_stop_recording"] = stop_btn
            self.gump.AddControl(stop_btn)
            API.Gumps.AddControlOnClick(stop_btn, self._on_stop_recording)

        y_offset += 30

        # Waypoint count
        wp_count_text = "Waypoints: " + str(len(self.waypoints))
        wp_count_label = API.Gumps.CreateGumpTTFLabel(wp_count_text, 15, "#ffcc00")
        wp_count_label.SetPos(10, y_offset)
        self.controls["mode_wp_count"] = wp_count_label
        self.gump.AddControl(wp_count_label)
        y_offset += 25

        # Waypoint list (show last 5)
        display_waypoints = self.waypoints[-5:] if len(self.waypoints) > 5 else self.waypoints
        for i, (wx, wy) in enumerate(display_waypoints):
            wp_text = "  WP" + str(len(self.waypoints) - len(display_waypoints) + i + 1) + ": (" + str(wx) + ", " + str(wy) + ")"
            wp_label = API.Gumps.CreateGumpTTFLabel(wp_text, 15, "#aaaaaa")
            wp_label.SetPos(10, y_offset)
            self.controls["mode_wp_" + str(i)] = wp_label
            self.gump.AddControl(wp_label)
            y_offset += 20

        # Clear waypoints button
        if len(self.waypoints) > 0:
            clear_btn = API.Gumps.CreateSimpleButton("[Clear Waypoints]", 140, 22)
            clear_btn.SetPos(10, y_offset)
            clear_btn.SetBackgroundHue(32)
            self.controls["mode_clear_wp"] = clear_btn
            self.gump.AddControl(clear_btn)
            API.Gumps.AddControlOnClick(clear_btn, self._on_clear_waypoints)
            y_offset += 30

        return y_offset

    # ========== EVENT HANDLERS ==========
    def _on_circle_mode(self):
        """Switch to circle mode"""
        if self.area_type != "circle":
            self.area_type = "circle"
            self.controls["circle_btn"].SetBackgroundHue(68)
            self.controls["waypoints_btn"].SetBackgroundHue(90)
            self._rebuild_mode_controls()

    def _on_waypoints_mode(self):
        """Switch to waypoints mode"""
        if self.area_type != "waypoints":
            self.area_type = "waypoints"
            self.controls["circle_btn"].SetBackgroundHue(90)
            self.controls["waypoints_btn"].SetBackgroundHue(68)
            self._rebuild_mode_controls()

    def _on_set_center(self):
        """Record current position as circle center"""
        self.center_x = getattr(API.Player, 'X', 0)
        self.center_y = getattr(API.Player, 'Y', 0)
        API.SysMsg("Center set to (" + str(self.center_x) + ", " + str(self.center_y) + ")", 68)
        self._rebuild_mode_controls()

    def _on_radius_increase(self):
        """Increase radius"""
        if self.radius < 20:
            self.radius += 1
            self._rebuild_mode_controls()

    def _on_radius_decrease(self):
        """Decrease radius"""
        if self.radius > 5:
            self.radius -= 1
            self._rebuild_mode_controls()

    def _on_start_recording(self):
        """Start waypoint recording"""
        self.recording_waypoints = True
        self.waypoints = []
        API.SysMsg("Waypoint recording started! Press F5 to add waypoints", 68)
        API.OnHotKey("F5", self._on_add_waypoint_hotkey)
        self._rebuild_mode_controls()

    def _on_stop_recording(self):
        """Stop waypoint recording"""
        self.recording_waypoints = False
        try:
            API.UnregisterHotkey("F5")
        except:
            pass
        API.SysMsg("Waypoint recording stopped. " + str(len(self.waypoints)) + " waypoints recorded", 68)
        self._rebuild_mode_controls()

    def _on_add_waypoint(self):
        """Add current position as waypoint (button click)"""
        wx = getattr(API.Player, 'X', 0)
        wy = getattr(API.Player, 'Y', 0)
        self.waypoints.append((wx, wy))
        API.SysMsg("Waypoint " + str(len(self.waypoints)) + " added: (" + str(wx) + ", " + str(wy) + ")", 68)
        self._rebuild_mode_controls()

    def _on_add_waypoint_hotkey(self):
        """Add waypoint via F5 hotkey"""
        if self.recording_waypoints:
            self._on_add_waypoint()

    def _on_clear_waypoints(self):
        """Clear all waypoints"""
        self.waypoints = []
        API.SysMsg("Waypoints cleared", 43)
        self._rebuild_mode_controls()

    def _on_difficulty_change(self, difficulty):
        """Change difficulty setting"""
        self.difficulty = difficulty
        API.SysMsg("Difficulty set to: " + difficulty, 68)
        self._rebuild_mode_controls()

    def _on_record_safe_spot(self):
        """Open safe spot recording sub-panel"""
        # For now, record current position as safe spot with direct recall
        # Full sub-panel will be implemented in next iteration
        self.safe_spot_x = getattr(API.Player, 'X', 0)
        self.safe_spot_y = getattr(API.Player, 'Y', 0)
        self.safe_spot_escape_method = "direct_recall"
        API.SysMsg("Safe spot recorded: (" + str(self.safe_spot_x) + ", " + str(self.safe_spot_y) + ")", 68)

    def _on_save_area(self):
        """Save the configured area"""
        try:
            # Get area name from text input
            self.area_name = self.controls["name_input"].GetText().strip()

            # Validation
            if not self.area_name:
                API.SysMsg("Error: Area name is required", 32)
                return

            if self.area_type == "circle":
                if self.center_x == 0 and self.center_y == 0:
                    API.SysMsg("Error: Please set center coordinates", 32)
                    return
            elif self.area_type == "waypoints":
                if len(self.waypoints) < 2:
                    API.SysMsg("Error: At least 2 waypoints required", 32)
                    return

            # Create FarmingArea object
            area = FarmingArea(self.area_name, self.area_type)

            if self.area_type == "circle":
                area.center_x = self.center_x
                area.center_y = self.center_y
                area.radius = self.radius
            else:
                area.waypoints = self.waypoints[:]

            area.difficulty = self.difficulty

            # Add safe spot if recorded
            if self.safe_spot_x != 0 or self.safe_spot_y != 0:
                safe_spot = SafeSpot(
                    x=self.safe_spot_x,
                    y=self.safe_spot_y,
                    escape_method=self.safe_spot_escape_method,
                    gump_id=self.safe_spot_gump_id,
                    button_id=self.safe_spot_button_id,
                    is_primary=True
                )
                area.safe_spots.append(safe_spot)

            # Save to AreaManager
            if self.area_manager.add_area(area):
                API.SysMsg("Area '" + self.area_name + "' saved successfully!", 68)
                self.close()
            else:
                API.SysMsg("Error: Failed to save area", 32)

        except Exception as e:
            API.SysMsg("Error saving area: " + str(e), 32)

    def _on_cancel(self):
        """Cancel and close gump"""
        API.SysMsg("Area recording cancelled", 43)
        self.close()

    def close(self):
        """Close the gump"""
        try:
            if self.recording_waypoints:
                API.UnregisterHotkey("F5")
        except:
            pass

        if self.gump:
            self.gump.Dispose()
            self.gump = None


# ========== MAIN SCRIPT ==========
# NOTE: This is a foundational implementation for the core classes.
# The full dungeon farming script will be built up in subsequent tasks.

def test_farming_areas():
    """Test function to verify FarmingArea and AreaManager work correctly"""
    API.SysMsg("Testing FarmingArea System...", 68)

    try:
        # Test 1: Create AreaManager
        area_manager = AreaManager()
        API.SysMsg("AreaManager initialized", 68)

        # Test 2: Create a circle-based farming area
        orc_fort = FarmingArea("Orc Fort", "circle")
        orc_fort.center_x = 1000
        orc_fort.center_y = 1000
        orc_fort.radius = 15
        orc_fort.difficulty = "low"
        orc_fort.loot_filter = [0x0EED]  # Gold
        orc_fort.notes = "Low risk orc farming spot"

        # Add safe spot with direct recall
        safe_spot = SafeSpot(x=995, y=995, escape_method="direct_recall", is_primary=True)
        orc_fort.safe_spots.append(safe_spot)

        # Test 3: Save area to persistence
        if area_manager.add_area(orc_fort):
            API.SysMsg("Saved 'Orc Fort' area", 68)
        else:
            API.SysMsg("Failed to save area", 32)
            return

        # Test 4: Create a waypoint-based farming area
        dungeon_path = FarmingArea("Dungeon Path", "waypoints")
        dungeon_path.waypoints = [(1100, 1100), (1110, 1105), (1120, 1110)]
        dungeon_path.difficulty = "medium"
        dungeon_path.loot_filter = [0x0EED, 0x0F0E]  # Gold + gems
        dungeon_path.notes = "Medium risk dungeon route"

        # Add safe spot with gump gate
        safe_gate = SafeSpot(x=1095, y=1095, escape_method="gump_gate", gump_id=89, button_id=10, is_primary=True)
        dungeon_path.safe_spots.append(safe_gate)

        # Add backup safe spot
        backup_spot = SafeSpot(x=1090, y=1090, escape_method="run_outside", is_primary=False)
        dungeon_path.safe_spots.append(backup_spot)

        # Test 5: Save second area
        if area_manager.add_area(dungeon_path):
            API.SysMsg("Saved 'Dungeon Path' area", 68)
        else:
            API.SysMsg("Failed to save second area", 32)
            return

        # Test 6: List all areas
        area_list = area_manager.list_areas()
        API.SysMsg("Total areas: " + str(len(area_list)), 43)
        for area_name in area_list:
            API.SysMsg("  - " + area_name, 43)

        # Test 7: Retrieve and verify an area
        retrieved_area = area_manager.get_area("Orc Fort")
        if retrieved_area:
            API.SysMsg("Retrieved 'Orc Fort':", 68)
            API.SysMsg("  Type: " + retrieved_area.area_type, 43)
            API.SysMsg("  Center: (" + str(retrieved_area.center_x) + ", " + str(retrieved_area.center_y) + ")", 43)
            API.SysMsg("  Radius: " + str(retrieved_area.radius), 43)
            API.SysMsg("  Difficulty: " + retrieved_area.difficulty, 43)
            API.SysMsg("  Safe spots: " + str(len(retrieved_area.safe_spots)), 43)
            API.SysMsg("  Notes: " + retrieved_area.notes, 43)
        else:
            API.SysMsg("Failed to retrieve area", 32)
            return

        # Test 8: Test is_in_area
        if retrieved_area.is_in_area(1005, 1005):
            API.SysMsg("Position (1005, 1005) is IN area (correct)", 68)
        else:
            API.SysMsg("Position (1005, 1005) NOT in area (error)", 32)

        if not retrieved_area.is_in_area(2000, 2000):
            API.SysMsg("Position (2000, 2000) is NOT in area (correct)", 68)
        else:
            API.SysMsg("Position (2000, 2000) in area (error)", 32)

        # Test 9: Test safe spot retrieval
        primary_spot = retrieved_area.get_primary_safe_spot()
        if primary_spot:
            API.SysMsg("Primary safe spot: (" + str(primary_spot.x) + ", " + str(primary_spot.y) + ")", 68)
            API.SysMsg("  Escape method: " + primary_spot.escape_method, 43)

        nearest_spot = retrieved_area.get_nearest_safe_spot(1000, 1000)
        if nearest_spot:
            API.SysMsg("Nearest safe spot: (" + str(nearest_spot.x) + ", " + str(nearest_spot.y) + ")", 68)

        # Test 10: Test waypoint area
        waypoint_area = area_manager.get_area("Dungeon Path")
        if waypoint_area:
            API.SysMsg("Retrieved 'Dungeon Path':", 68)
            API.SysMsg("  Type: " + waypoint_area.area_type, 43)
            API.SysMsg("  Waypoints: " + str(len(waypoint_area.waypoints)), 43)
            for i, wp in enumerate(waypoint_area.waypoints):
                API.SysMsg("    WP" + str(i + 1) + ": " + str(wp), 43)

        # Test 11: Delete an area
        if area_manager.delete_area("Orc Fort"):
            API.SysMsg("Deleted 'Orc Fort'", 68)
            remaining = area_manager.list_areas()
            API.SysMsg("Remaining areas: " + str(len(remaining)), 43)
        else:
            API.SysMsg("Failed to delete area", 32)

        API.SysMsg("FarmingArea System test complete!", 68)

    except Exception as e:
        API.SysMsg("Test error: " + str(e), 32)

def test_healing_system():
    """Simple test function to verify HealingSystem works"""
    API.SysMsg("Testing HealingSystem...", 68)

    # Initialize systems
    pet_manager = PetManager()
    healing_system = HealingSystem(pet_manager)

    # Scan for pets
    pet_count = pet_manager.scan_pets()
    API.SysMsg("Found " + str(pet_count) + " pets", 68)

    # Test 1: Check for heal action
    heal_action = healing_system.get_next_heal_action()
    if heal_action:
        target_serial, action_type, is_self = heal_action
        target_str = "self" if is_self else "pet #" + str(target_serial)
        API.SysMsg("Next heal: " + action_type + " on " + target_str, 43)

        # Test 2: Execute the heal action
        if healing_system.execute_heal(target_serial, action_type, is_self):
            API.SysMsg("Heal action started successfully", 68)
            API.SysMsg("STATE: " + healing_system.STATE, 43)

            # Test 3: Wait and check completion
            API.Pause(1.0)
            if healing_system.check_heal_complete():
                API.SysMsg("Heal completed (or still in progress)", 68)
            else:
                API.SysMsg("Heal still in progress", 43)
        else:
            API.SysMsg("Failed to start heal action", 32)
    else:
        API.SysMsg("No healing needed", 68)

    # Test 4: Display statistics
    API.SysMsg("Stats - Bandages: " + str(healing_system.bandages_used) +
               " VetKits: " + str(healing_system.vetkits_used) +
               " Cures: " + str(healing_system.cures_cast), 43)

    API.SysMsg("HealingSystem test complete", 68)

def test_area_recording_gump():
    """Test function to open the area recording UI"""
    API.SysMsg("Opening Area Recording UI...", 68)

    try:
        # Initialize AreaManager
        area_manager = AreaManager()

        # Create and open the recording gump
        recording_gump = AreaRecordingGump(area_manager)

        API.SysMsg("Area Recording UI opened!", 68)
        API.SysMsg("Instructions:", 43)
        API.SysMsg("1. Enter area name", 43)
        API.SysMsg("2. Select Circle or Waypoints mode", 43)
        API.SysMsg("3. Configure area (set center/record waypoints)", 43)
        API.SysMsg("4. Set difficulty level", 43)
        API.SysMsg("5. Record safe spot (optional)", 43)
        API.SysMsg("6. Click Save Area to persist", 43)

    except Exception as e:
        API.SysMsg("Test error: " + str(e), 32)

# Run tests if script is loaded
# Uncomment to test:
# test_farming_areas()
# test_healing_system()
# test_area_recording_gump()

API.SysMsg("Dungeon Farmer loaded (FarmingArea + HealingSystem + AreaRecordingGump v1.2)", 68)
