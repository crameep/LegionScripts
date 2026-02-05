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


# ========== NPC THREAT MAP CLASS ==========
class NPCThreatMap:
    """Handles NPC detection and threat zone mapping for avoidance"""

    def __init__(self, avoid_radius=6, scan_radius=12, refresh_interval=2.0):
        """
        Initialize NPC threat map.

        Args:
            avoid_radius: Radius around NPCs to mark as avoid zone (tiles)
            scan_radius: Radius to scan for NPCs (tiles)
            refresh_interval: Minimum time between scans to reduce overhead (seconds)
        """
        self.avoid_radius = avoid_radius
        self.scan_radius = scan_radius
        self.refresh_interval = refresh_interval
        self.last_scan_time = 0
        self.npc_positions = []  # List of (x, y) NPC positions

    def scan_npcs(self, force_scan=False):
        """
        Scan for nearby NPCs and update threat map.

        Args:
            force_scan: If True, ignore refresh_interval and scan immediately

        Returns:
            List of (x, y) NPC positions
        """
        try:
            # Check refresh interval
            if not force_scan:
                elapsed = time.time() - self.last_scan_time
                if elapsed < self.refresh_interval:
                    return self.npc_positions  # Return cached positions

            # Clear previous threat map
            self.npc_positions = []

            # Get all mobiles within scan radius
            all_mobiles = API.Mobiles.GetMobiles()

            player_x = getattr(API.Player, 'X', 0)
            player_y = getattr(API.Player, 'Y', 0)

            for mob in all_mobiles:
                if mob is None or mob.IsDead:
                    continue

                # Filter out pets (Notoriety == 1)
                if mob.Notoriety == 1:
                    continue

                # Filter out player
                if mob.Serial == API.Player.Serial:
                    continue

                # Check if within scan radius
                if mob.Distance > self.scan_radius:
                    continue

                # Store NPC position
                mob_x = getattr(mob, 'X', player_x)
                mob_y = getattr(mob, 'Y', player_y)
                self.npc_positions.append((mob_x, mob_y))

            # Update last scan time
            self.last_scan_time = time.time()

            return self.npc_positions

        except Exception as e:
            API.SysMsg("NPCThreatMap.scan_npcs error: " + str(e), 32)
            return []

    def is_position_safe(self, x, y):
        """
        Check if position is safe from NPCs (not in any avoid zone).

        Args:
            x, y: Position to check

        Returns:
            True if safe, False if in avoid zone
        """
        try:
            import math

            for npc_x, npc_y in self.npc_positions:
                # Calculate distance to NPC
                distance = math.sqrt((x - npc_x) ** 2 + (y - npc_y) ** 2)

                # Check if within avoid radius
                if distance <= self.avoid_radius:
                    return False

            return True

        except Exception as e:
            API.SysMsg("NPCThreatMap.is_position_safe error: " + str(e), 32)
            return True  # Assume safe on error

    def get_nearest_threat(self, x, y):
        """
        Find closest NPC to given position.

        Args:
            x, y: Position to check from

        Returns:
            (npc_x, npc_y, distance) or None if no NPCs
        """
        try:
            import math

            if not self.npc_positions:
                return None

            nearest_npc = None
            min_distance = float('inf')

            for npc_x, npc_y in self.npc_positions:
                distance = math.sqrt((x - npc_x) ** 2 + (y - npc_y) ** 2)

                if distance < min_distance:
                    min_distance = distance
                    nearest_npc = (npc_x, npc_y, distance)

            return nearest_npc

        except Exception as e:
            API.SysMsg("NPCThreatMap.get_nearest_threat error: " + str(e), 32)
            return None

    def calculate_safe_direction(self, from_x, from_y):
        """
        Calculate safest direction to move from given position.
        Samples 8 cardinal/diagonal directions and returns the safest one.

        Args:
            from_x, from_y: Starting position

        Returns:
            (dx, dy) direction vector for safest path, or None if all blocked
        """
        try:
            import math

            # Define 8 directions (N, NE, E, SE, S, SW, W, NW)
            directions = [
                (0, -10),   # North
                (7, -7),    # NE
                (10, 0),    # East
                (7, 7),     # SE
                (0, 10),    # South
                (-7, 7),    # SW
                (-10, 0),   # West
                (-7, -7)    # NW
            ]

            best_direction = None
            max_distance_to_threat = 0

            for dx, dy in directions:
                # Calculate destination
                dest_x = from_x + dx
                dest_y = from_y + dy

                # Check if destination is safe
                if not self.is_position_safe(dest_x, dest_y):
                    continue

                # Find distance to nearest threat from this destination
                nearest = self.get_nearest_threat(dest_x, dest_y)
                if nearest is None:
                    # No threats at all, this direction is perfect
                    return (dx, dy)

                threat_distance = nearest[2]

                # Track direction that gets us furthest from threats
                if threat_distance > max_distance_to_threat:
                    max_distance_to_threat = threat_distance
                    best_direction = (dx, dy)

            return best_direction

        except Exception as e:
            API.SysMsg("NPCThreatMap.calculate_safe_direction error: " + str(e), 32)
            return None

    def get_threat_count(self):
        """Get number of NPCs in current threat map"""
        return len(self.npc_positions)

    def clear_threats(self):
        """Clear all tracked threats"""
        self.npc_positions = []


# ========== DANGER ASSESSMENT CLASS ==========
class DangerAssessment:
    """Evaluates threat level based on multiple factors"""

    def __init__(self, pet_manager):
        """
        Initialize danger assessment system.

        Args:
            pet_manager: PetManager instance for pet HP tracking
        """
        self.pet_manager = pet_manager

        # Configurable weights for danger factors (default values)
        self.weights = {
            "player_hp": 40,        # Weight for player HP (0-50)
            "tank_pet_hp": 25,      # Weight for tank pet HP (0-50)
            "enemy_count": 15,      # Weight per enemy (5-30)
            "nearby_npcs": 5,       # Weight per nearby NPC (0-20)
            "damage_rate": 20       # Weight for damage rate (0-30)
        }

        # Danger zone thresholds
        self.thresholds = {
            "safe": 30,         # 0-30 = safe
            "elevated": 50,     # 31-50 = elevated
            "high": 70          # 51-70 = high, 71+ = critical
        }

        # Danger history tracking (last 10 readings)
        self.danger_history = []
        self.max_history_size = 10

        # Damage rate tracking
        self.last_player_hp = 0
        self.last_hp_check_time = 0
        self.recent_damage = []  # List of (damage, time) tuples

    def configure_weights(self, player_hp=None, tank_pet_hp=None, enemy_count=None, nearby_npcs=None, damage_rate=None):
        """Update danger calculation weights"""
        if player_hp is not None:
            self.weights["player_hp"] = player_hp
        if tank_pet_hp is not None:
            self.weights["tank_pet_hp"] = tank_pet_hp
        if enemy_count is not None:
            self.weights["enemy_count"] = enemy_count
        if nearby_npcs is not None:
            self.weights["nearby_npcs"] = nearby_npcs
        if damage_rate is not None:
            self.weights["damage_rate"] = damage_rate

    def configure_thresholds(self, safe=None, elevated=None, high=None):
        """Update danger zone thresholds"""
        if safe is not None:
            self.thresholds["safe"] = safe
        if elevated is not None:
            self.thresholds["elevated"] = elevated
        if high is not None:
            self.thresholds["high"] = high

    def _get_player_danger(self):
        """Calculate danger from player HP"""
        try:
            player_hp_pct = (API.Player.Hits / API.Player.HitsMax) if API.Player.HitsMax > 0 else 1.0
            danger = self.weights["player_hp"] * (1.0 - player_hp_pct)
            return danger
        except:
            return 0

    def _get_tank_pet_danger(self):
        """Calculate danger from tank pet HP"""
        try:
            tank_pet = self.pet_manager.get_tank_pet()
            if tank_pet is None:
                return 0

            tank_mob = API.Mobiles.FindMobile(tank_pet["serial"])
            if tank_mob is None:
                return 0

            if tank_mob.IsDead:
                return self.weights["tank_pet_hp"] + 50  # Extra danger if tank dead

            tank_hp_pct = (tank_mob.Hits / tank_mob.HitsMax) if tank_mob.HitsMax > 0 else 1.0
            danger = self.weights["tank_pet_hp"] * (1.0 - tank_hp_pct)
            return danger
        except:
            return 0

    def _get_enemy_danger(self, enemy_count):
        """Calculate danger from nearby enemy count"""
        return enemy_count * self.weights["enemy_count"]

    def _get_npc_danger(self, npc_count):
        """Calculate danger from nearby NPC count"""
        return npc_count * self.weights["nearby_npcs"]

    def _get_damage_danger(self):
        """Calculate danger from recent damage rate"""
        try:
            current_time = time.time()

            # Track player HP changes
            current_hp = API.Player.Hits
            if self.last_player_hp > 0 and current_hp < self.last_player_hp:
                damage = self.last_player_hp - current_hp
                self.recent_damage.append((damage, current_time))

            self.last_player_hp = current_hp
            self.last_hp_check_time = current_time

            # Remove damage events older than 3 seconds
            self.recent_damage = [(dmg, t) for dmg, t in self.recent_damage if current_time - t <= 3.0]

            # Calculate damage rate (total damage in last 3 seconds)
            total_damage = sum(dmg for dmg, _ in self.recent_damage)

            # Normalize damage rate (assume 100 HP = full danger weight)
            max_hp = API.Player.HitsMax if API.Player.HitsMax > 0 else 100
            damage_ratio = min(1.0, total_damage / max_hp)

            return self.weights["damage_rate"] * damage_ratio

        except:
            return 0

    def _get_positioning_danger(self):
        """Calculate danger from pet positioning (too far from player)"""
        try:
            tank_pet = self.pet_manager.get_tank_pet()
            if tank_pet is None:
                return 0

            tank_mob = API.Mobiles.FindMobile(tank_pet["serial"])
            if tank_mob is None or tank_mob.IsDead:
                return 0

            # Add danger if tank pet is more than 5 tiles away
            distance = tank_mob.Distance
            if distance > 5:
                return min(15, (distance - 5) * 3)  # Up to 15 extra danger

            return 0
        except:
            return 0

    def calculate_danger(self, enemy_count=0, npc_count=0):
        """
        Calculate overall danger score from all factors.

        Args:
            enemy_count: Number of hostile enemies nearby
            npc_count: Number of non-hostile NPCs nearby

        Returns:
            Danger score (0-100)
        """
        try:
            # Calculate individual danger factors
            player_danger = self._get_player_danger()
            tank_danger = self._get_tank_pet_danger()
            enemy_danger = self._get_enemy_danger(enemy_count)
            npc_danger = self._get_npc_danger(npc_count)
            damage_danger = self._get_damage_danger()
            positioning_danger = self._get_positioning_danger()

            # Sum all factors
            total_danger = (
                player_danger +
                tank_danger +
                enemy_danger +
                npc_danger +
                damage_danger +
                positioning_danger
            )

            # Clamp to 0-100
            total_danger = max(0, min(100, total_danger))

            # Track in history
            self.danger_history.append(total_danger)
            if len(self.danger_history) > self.max_history_size:
                self.danger_history.pop(0)

            return total_danger

        except Exception as e:
            API.SysMsg("DangerAssessment.calculate_danger error: " + str(e), 32)
            return 0

    def get_danger_zone(self, danger_score=None):
        """
        Get danger zone name for a danger score.

        Args:
            danger_score: Optional danger score (uses last calculated if None)

        Returns:
            "safe", "elevated", "high", or "critical"
        """
        if danger_score is None:
            if not self.danger_history:
                return "safe"
            danger_score = self.danger_history[-1]

        if danger_score <= self.thresholds["safe"]:
            return "safe"
        elif danger_score <= self.thresholds["elevated"]:
            return "elevated"
        elif danger_score <= self.thresholds["high"]:
            return "high"
        else:
            return "critical"

    def get_danger_trend(self):
        """
        Analyze danger trend from recent history.

        Returns:
            "rising", "falling", or "stable"
        """
        if len(self.danger_history) < 3:
            return "stable"

        # Compare last 3 readings to previous 3
        recent_avg = sum(self.danger_history[-3:]) / 3
        previous_avg = sum(self.danger_history[-6:-3]) / 3 if len(self.danger_history) >= 6 else recent_avg

        diff = recent_avg - previous_avg

        if diff > 5:
            return "rising"
        elif diff < -5:
            return "falling"
        else:
            return "stable"

    def get_current_danger(self):
        """Get most recent danger score"""
        return self.danger_history[-1] if self.danger_history else 0

    def reset_damage_tracking(self):
        """Reset damage rate tracking"""
        self.recent_damage = []
        self.last_player_hp = API.Player.Hits
        self.last_hp_check_time = time.time()


# ========== COMBAT MANAGER CLASS ==========
class CombatManager:
    """Handles enemy detection, engagement decisions, and combat monitoring"""

    def __init__(self, danger_assessment, npc_threat_map, pet_manager, healing_system=None):
        """
        Initialize combat manager.

        Args:
            danger_assessment: DangerAssessment instance
            npc_threat_map: NPCThreatMap instance
            pet_manager: PetManager instance
            healing_system: Optional HealingSystem instance for mid-combat heals
        """
        self.danger_assessment = danger_assessment
        self.npc_threat_map = npc_threat_map
        self.pet_manager = pet_manager
        self.healing_system = healing_system

        # Configurable engagement settings
        self.enemy_scan_range = 10
        self.max_danger_to_engage = 50
        self.max_nearby_hostiles = 1
        self.npc_proximity_radius = 6
        self.max_npcs_near_target = 2
        self.min_tank_hp_to_engage = 60  # Percentage

        # Danger thresholds for combat monitoring
        self.flee_threshold = 71         # Initiate emergency flee
        self.high_threshold = 51         # Issue "all guard me", stop engaging new targets

        # Engagement state
        self.engaged_enemy_serial = 0
        self.combat_start_time = 0
        self.corpse_serial = 0           # Corpse of defeated enemy for looting

        # Settings for enemy types to engage
        self.attack_reds = True      # Notoriety 5
        self.attack_grays = False    # Notoriety 6

        # Combat statistics tracking
        self.kills = 0
        self.damage_dealt = 0
        self.damage_taken = 0
        self.total_combat_duration = 0

    def configure_engagement(self, scan_range=None, max_danger=None, max_hostiles=None,
                           proximity_radius=None, max_npcs=None, min_tank_hp=None):
        """Update engagement configuration"""
        if scan_range is not None:
            self.enemy_scan_range = scan_range
        if max_danger is not None:
            self.max_danger_to_engage = max_danger
        if max_hostiles is not None:
            self.max_nearby_hostiles = max_hostiles
        if proximity_radius is not None:
            self.npc_proximity_radius = proximity_radius
        if max_npcs is not None:
            self.max_npcs_near_target = max_npcs
        if min_tank_hp is not None:
            self.min_tank_hp_to_engage = min_tank_hp

    def configure_enemy_types(self, attack_reds=None, attack_grays=None):
        """Configure which enemy types to attack"""
        if attack_reds is not None:
            self.attack_reds = attack_reds
        if attack_grays is not None:
            self.attack_grays = attack_grays

    def scan_for_enemies(self, scan_range=None):
        """
        Scan for hostile enemies within range.

        Args:
            scan_range: Optional override for scan range (uses default if None)

        Returns:
            List of enemy serials sorted by distance (closest first)
        """
        try:
            if scan_range is None:
                scan_range = self.enemy_scan_range

            all_mobiles = API.Mobiles.GetMobiles()
            enemies = []

            for mob in all_mobiles:
                if mob is None or mob.IsDead:
                    continue

                # Skip player
                if mob.Serial == API.Player.Serial:
                    continue

                # Skip pets (Notoriety 1)
                if mob.Notoriety == 1:
                    continue

                # Check if this enemy type is enabled
                if mob.Notoriety == 5 and not self.attack_reds:
                    continue
                if mob.Notoriety == 6 and not self.attack_grays:
                    continue

                # Filter by notoriety (5=red, 6=gray)
                if mob.Notoriety not in [5, 6]:
                    continue

                # Check range
                if mob.Distance > scan_range:
                    continue

                # Add to enemy list with distance for sorting
                enemies.append((mob.Serial, mob.Distance))

            # Sort by distance (closest first)
            enemies.sort(key=lambda x: x[1])

            # Return just serials
            return [serial for serial, _ in enemies]

        except Exception as e:
            API.SysMsg("CombatManager.scan_for_enemies error: " + str(e), 32)
            return []

    def should_engage_enemy(self, enemy_serial):
        """
        Evaluate if it's safe to engage an enemy.

        Args:
            enemy_serial: Enemy serial to evaluate

        Returns:
            True if safe to engage, False otherwise
        """
        try:
            # Get enemy mobile
            enemy = API.Mobiles.FindMobile(enemy_serial)
            if enemy is None or enemy.IsDead:
                return False

            # Check 1: Current danger level
            current_danger = self.danger_assessment.get_current_danger()
            if current_danger > self.max_danger_to_engage:
                return False

            # Check 2: Count nearby hostiles
            nearby_hostiles = self.scan_for_enemies()
            if len(nearby_hostiles) > self.max_nearby_hostiles:
                return False

            # Check 3: Scan for NPCs near target enemy (pull risk assessment)
            import math
            enemy_x = getattr(enemy, 'X', 0)
            enemy_y = getattr(enemy, 'Y', 0)

            npcs_near_target = 0
            all_mobiles = API.Mobiles.GetMobiles()

            for mob in all_mobiles:
                if mob is None or mob.IsDead:
                    continue

                # Skip player and pets
                if mob.Serial == API.Player.Serial or mob.Notoriety == 1:
                    continue

                # Skip the target enemy itself
                if mob.Serial == enemy_serial:
                    continue

                # Calculate distance to target enemy
                mob_x = getattr(mob, 'X', enemy_x)
                mob_y = getattr(mob, 'Y', enemy_y)
                distance = math.sqrt((mob_x - enemy_x) ** 2 + (mob_y - enemy_y) ** 2)

                if distance <= self.npc_proximity_radius:
                    npcs_near_target += 1

            if npcs_near_target > self.max_npcs_near_target:
                return False

            # Check 4: Tank pet HP
            tank_pet = self.pet_manager.get_tank_pet()
            if tank_pet is not None:
                tank_mob = API.Mobiles.FindMobile(tank_pet["serial"])
                if tank_mob is not None and not tank_mob.IsDead:
                    tank_hp_pct = (tank_mob.Hits / tank_mob.HitsMax * 100) if tank_mob.HitsMax > 0 else 100
                    if tank_hp_pct < self.min_tank_hp_to_engage:
                        return False

            # All checks passed
            return True

        except Exception as e:
            API.SysMsg("CombatManager.should_engage_enemy error: " + str(e), 32)
            return False

    def engage_enemy(self, enemy_serial):
        """
        Engage an enemy in combat.

        Args:
            enemy_serial: Enemy serial to engage

        Returns:
            True if engagement started successfully, False otherwise
        """
        try:
            # Verify enemy is valid
            enemy = API.Mobiles.FindMobile(enemy_serial)
            if enemy is None or enemy.IsDead:
                return False

            # Cancel any existing targets
            if API.HasTarget():
                API.CancelTarget()
            API.CancelPreTarget()

            # Issue "all kill" command
            API.Msg("all kill")
            API.Pause(0.3)

            # Target enemy
            API.PreTarget(enemy_serial, "harmful")
            API.Pause(0.1)
            API.CancelPreTarget()

            # Update engagement state
            self.engaged_enemy_serial = enemy_serial
            self.combat_start_time = time.time()

            API.HeadMsg("Engaging!", API.Player.Serial, 68)

            return True

        except Exception as e:
            API.SysMsg("CombatManager.engage_enemy error: " + str(e), 32)
            return False

    def get_engaged_enemy(self):
        """
        Get currently engaged enemy mobile.

        Returns:
            Enemy mobile or None
        """
        if self.engaged_enemy_serial == 0:
            return None

        enemy = API.Mobiles.FindMobile(self.engaged_enemy_serial)
        if enemy and not enemy.IsDead:
            return enemy

        return None

    def clear_engagement(self):
        """Clear engagement state"""
        self.engaged_enemy_serial = 0
        self.combat_start_time = 0

    def get_combat_duration(self):
        """Get duration of current combat in seconds"""
        if self.combat_start_time == 0:
            return 0
        return time.time() - self.combat_start_time

    def monitor_combat(self):
        """
        Monitor ongoing combat and handle dynamic responses.
        Should be called every 0.3s in main loop when STATE == "engaging".

        Returns:
            Dict with keys:
            - "status": "continuing", "enemy_dead", "enemy_lost", "flee_now", or "high_danger"
            - "enemy_serial": Engaged enemy serial (0 if none)
            - "corpse_serial": Corpse serial if enemy died (0 otherwise)
        """
        try:
            result = {
                "status": "continuing",
                "enemy_serial": self.engaged_enemy_serial,
                "corpse_serial": 0
            }

            # No active engagement
            if self.engaged_enemy_serial == 0:
                result["status"] = "no_engagement"
                return result

            # Check 1: Enemy status (dead or lost)
            enemy = API.Mobiles.FindMobile(self.engaged_enemy_serial)

            if enemy is None or enemy.IsDead:
                # Enemy defeated
                if enemy and enemy.IsDead:
                    result["status"] = "enemy_dead"
                    result["corpse_serial"] = self.on_enemy_death(enemy)
                else:
                    # Enemy lost (no longer in range or despawned)
                    result["status"] = "enemy_lost"
                    self.clear_engagement()
                return result

            if enemy.Distance > 15:
                # Lost enemy (too far)
                result["status"] = "enemy_lost"
                self.clear_engagement()
                return result

            # Check 2: Danger level assessment
            current_danger = self.danger_assessment.calculate_danger()

            if current_danger >= self.flee_threshold:
                # CRITICAL: Initiate emergency flee
                result["status"] = "flee_now"
                API.HeadMsg("FLEE!", API.Player.Serial, 32)
                return result

            if current_danger >= self.high_threshold:
                # HIGH DANGER: Issue "all guard me", stop engaging new targets
                result["status"] = "high_danger"
                API.Msg("all guard me")
                API.Pause(0.3)
                return result

            # Check 3: Healing needs (if healing_system available and not in healing state)
            if self.healing_system and self.healing_system.STATE == "idle":
                heal_action = self.healing_system.get_next_heal_action()

                if heal_action:
                    target_serial, action_type, is_self = heal_action
                    target_mob = API.Mobiles.FindMobile(target_serial) if not is_self else API.Player

                    if target_mob:
                        hp_pct = (target_mob.Hits / target_mob.HitsMax * 100) if target_mob.HitsMax > 0 else 100

                        # Critical heal needed (player < 50% or tank < 40%)
                        is_critical = False
                        if is_self and hp_pct < 50:
                            is_critical = True
                        elif not is_self:
                            tank_pet = self.pet_manager.get_tank_pet()
                            if tank_pet and target_serial == tank_pet["serial"] and hp_pct < 40:
                                is_critical = True

                        if is_critical:
                            result["status"] = "critical_heal_needed"
                            # Note: Caller should execute heal and pause combat briefly

            # Check 4: Tank pet positioning
            tank_pet = self.pet_manager.get_tank_pet()
            if tank_pet:
                tank_mob = API.Mobiles.FindMobile(tank_pet["serial"])
                if tank_mob and not tank_mob.IsDead:
                    if tank_mob.Distance > 10:
                        # Tank too far - call back
                        API.Msg("all come")
                        API.Pause(0.3)
                        result["status"] = "recalling_tank"

            return result

        except Exception as e:
            API.SysMsg("CombatManager.monitor_combat error: " + str(e), 32)
            return {
                "status": "error",
                "enemy_serial": self.engaged_enemy_serial,
                "corpse_serial": 0
            }

    def on_enemy_death(self, enemy_mob):
        """
        Handle enemy death: track corpse, update stats, clear engagement.

        Args:
            enemy_mob: The dead enemy mobile

        Returns:
            Corpse serial for looting (0 if not found)
        """
        try:
            # Get corpse serial (the mobile serial becomes the corpse serial)
            corpse_serial = enemy_mob.Serial if enemy_mob else 0

            # Store for looting
            self.corpse_serial = corpse_serial

            # Update statistics
            self.kills += 1
            if self.combat_start_time > 0:
                combat_duration = time.time() - self.combat_start_time
                self.total_combat_duration += combat_duration

            # Clear engagement
            self.clear_engagement()

            # Success message
            API.HeadMsg("Kill!", API.Player.Serial, 68)

            return corpse_serial

        except Exception as e:
            API.SysMsg("CombatManager.on_enemy_death error: " + str(e), 32)
            return 0

    def get_corpse_serial(self):
        """Get the corpse serial of last defeated enemy"""
        return self.corpse_serial

    def clear_corpse(self):
        """Clear the stored corpse serial"""
        self.corpse_serial = 0

    def get_combat_statistics(self):
        """
        Get combat statistics.

        Returns:
            Dict with keys: kills, damage_dealt, damage_taken, total_combat_duration, avg_combat_duration
        """
        avg_duration = (self.total_combat_duration / self.kills) if self.kills > 0 else 0
        return {
            "kills": self.kills,
            "damage_dealt": self.damage_dealt,
            "damage_taken": self.damage_taken,
            "total_combat_duration": self.total_combat_duration,
            "avg_combat_duration": avg_duration
        }

    def reset_statistics(self):
        """Reset combat statistics"""
        self.kills = 0
        self.damage_dealt = 0
        self.damage_taken = 0
        self.total_combat_duration = 0

    def configure_danger_thresholds(self, flee_threshold=None, high_threshold=None):
        """Update danger thresholds for combat monitoring"""
        if flee_threshold is not None:
            self.flee_threshold = flee_threshold
        if high_threshold is not None:
            self.high_threshold = high_threshold


# ========== PATROL SYSTEM CLASS ==========
class PatrolSystem:
    """Handles patrol movement for circle and waypoint-based areas"""

    def __init__(self, npc_threat_map=None):
        """
        Initialize the patrol system.

        Args:
            npc_threat_map: Optional NPCThreatMap instance for avoidance
        """
        self.npc_threat_map = npc_threat_map
        self.patrol_active = False
        self.STATE = "idle"  # idle, patrolling
        self.patrol_start_time = 0
        self.destination_x = 0
        self.destination_y = 0
        self.stuck_check_time = 0
        self.last_position_x = 0
        self.last_position_y = 0
        self.stuck_threshold = 3.0  # Seconds

        # Waypoint patrol state
        self.current_waypoint_index = 0
        self.patrol_direction = "forward"

    def get_current_position(self):
        """Get player's current position"""
        return (getattr(API.Player, 'X', 0), getattr(API.Player, 'Y', 0))

    def calculate_distance(self, x1, y1, x2, y2):
        """Calculate Euclidean distance between two points"""
        import math
        return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)

    def _is_position_safe(self, x, y):
        """
        Check if position is safe from NPCs (uses NPCThreatMap if available).

        Args:
            x, y: Position to check

        Returns:
            True if safe, False if in avoid zone
        """
        if self.npc_threat_map is None:
            return True  # No threat map available, assume safe

        # Use NPCThreatMap to check if position is safe
        return self.npc_threat_map.is_position_safe(x, y)

    def _pick_circle_destination(self, area, max_attempts=3):
        """
        Pick a random destination within circle area, avoiding NPCs.

        Args:
            area: FarmingArea with circle configuration
            max_attempts: Max tries to find safe destination

        Returns:
            (dest_x, dest_y) or None if no safe destination found
        """
        import random
        import math

        for attempt in range(max_attempts):
            # Pick random angle and distance
            angle = random.random() * 2 * math.pi
            distance = random.random() * area.radius

            # Calculate destination
            dest_x = area.center_x + int(math.cos(angle) * distance)
            dest_y = area.center_y + int(math.sin(angle) * distance)

            # Add random offset for variation (±0-3 tiles)
            dest_x += random.randint(-3, 3)
            dest_y += random.randint(-3, 3)

            # Check if safe
            if self._is_position_safe(dest_x, dest_y):
                return (dest_x, dest_y)

        # No safe destination found after max attempts
        return None

    def patrol_circle(self, area):
        """
        Execute circle patrol movement.

        Args:
            area: FarmingArea with circle configuration

        Returns:
            True if patrol started successfully, False otherwise
        """
        try:
            # Validate area
            if area is None or area.area_type != "circle":
                return False

            if area.center_x == 0 and area.center_y == 0:
                API.SysMsg("Error: Circle area has no center coordinates", 32)
                return False

            # Pick destination
            destination = self._pick_circle_destination(area)
            if destination is None:
                API.SysMsg("No safe destination found in patrol area", 32)
                return False

            self.destination_x, self.destination_y = destination

            # Start pathfinding
            if not API.Pathfind(self.destination_x, self.destination_y):
                API.SysMsg("Pathfinding failed to destination", 32)
                return False

            # Update state
            self.STATE = "patrolling"
            self.patrol_start_time = time.time()
            self.patrol_active = True

            # Initialize stuck detection
            current_x, current_y = self.get_current_position()
            self.last_position_x = current_x
            self.last_position_y = current_y
            self.stuck_check_time = time.time()

            return True

        except Exception as e:
            API.SysMsg("patrol_circle error: " + str(e), 32)
            return False

    def check_patrol_progress(self, area=None, scan_for_enemies_callback=None):
        """
        Check patrol progress and handle arrival/stuck detection.

        Args:
            area: Optional FarmingArea - if provided and type is "waypoints", will advance waypoint index on arrival
            scan_for_enemies_callback: Optional function to call during patrol for enemy scanning

        Returns:
            "arrived" if reached destination
            "stuck" if detected stuck
            "patrolling" if still moving
            "idle" if not patrolling
        """
        if self.STATE != "patrolling":
            return "idle"

        try:
            # Get current position
            current_x, current_y = self.get_current_position()

            # Check if arrived
            distance = self.calculate_distance(current_x, current_y, self.destination_x, self.destination_y)
            if distance <= 1:
                # Arrived at destination
                self.STATE = "idle"
                self.patrol_active = False

                # If waypoint patrol, advance to next waypoint
                if area is not None and area.area_type == "waypoints":
                    self.current_waypoint_index = (self.current_waypoint_index + 1) % len(area.waypoints)

                # Random pause (1-3 seconds)
                import random
                pause_duration = random.uniform(1.0, 3.0)
                API.Pause(pause_duration)

                return "arrived"

            # Check if still pathfinding
            if not API.Pathfinding():
                # Lost pathfinding (player moved manually or interrupted)
                self.STATE = "idle"
                self.patrol_active = False
                return "interrupted"

            # Check for stuck (same position for 3+ seconds)
            if time.time() - self.stuck_check_time >= self.stuck_threshold:
                if current_x == self.last_position_x and current_y == self.last_position_y:
                    # Stuck detected
                    API.SysMsg("Patrol stuck detected, canceling", 43)
                    API.CancelPathfinding()
                    self.STATE = "idle"
                    self.patrol_active = False
                    return "stuck"

                # Update stuck detection
                self.last_position_x = current_x
                self.last_position_y = current_y
                self.stuck_check_time = time.time()

            # Call enemy scan callback if provided
            if scan_for_enemies_callback is not None:
                scan_for_enemies_callback()

            return "patrolling"

        except Exception as e:
            API.SysMsg("check_patrol_progress error: " + str(e), 32)
            self.STATE = "idle"
            self.patrol_active = False
            return "error"

    def patrol_waypoints(self, area):
        """
        Execute waypoint patrol movement.

        Args:
            area: FarmingArea with waypoints configuration

        Returns:
            True if patrol started successfully, False otherwise
        """
        try:
            # Validate area
            if area is None or area.area_type != "waypoints":
                return False

            if not area.waypoints or len(area.waypoints) == 0:
                API.SysMsg("Error: Waypoint area has no waypoints", 32)
                return False

            # Reset index if at end
            if self.current_waypoint_index >= len(area.waypoints):
                self.current_waypoint_index = 0

            # Get target waypoint
            target_x, target_y = area.waypoints[self.current_waypoint_index]

            # 20% chance: skip to next waypoint OR backtrack to previous
            import random
            if random.random() < 0.20:
                if random.random() < 0.5 and self.current_waypoint_index < len(area.waypoints) - 1:
                    # Skip forward
                    self.current_waypoint_index += 1
                    target_x, target_y = area.waypoints[self.current_waypoint_index]
                elif self.current_waypoint_index > 0:
                    # Backtrack
                    self.current_waypoint_index -= 1
                    target_x, target_y = area.waypoints[self.current_waypoint_index]

            # Add random offset for variation (±1-3 tiles)
            offset_x = random.randint(-3, 3)
            offset_y = random.randint(-3, 3)
            dest_x = target_x + offset_x
            dest_y = target_y + offset_y

            # Check if position is safe from NPCs
            if not self._is_position_safe(dest_x, dest_y):
                API.SysMsg("Waypoint destination not safe from NPCs", 43)
                # Try next waypoint instead
                self.current_waypoint_index = (self.current_waypoint_index + 1) % len(area.waypoints)
                return False

            self.destination_x = dest_x
            self.destination_y = dest_y

            # Start pathfinding
            if not API.Pathfind(self.destination_x, self.destination_y):
                API.SysMsg("Pathfinding failed to waypoint", 32)
                return False

            # Update state
            self.STATE = "patrolling"
            self.patrol_start_time = time.time()
            self.patrol_active = True

            # Initialize stuck detection
            current_x, current_y = self.get_current_position()
            self.last_position_x = current_x
            self.last_position_y = current_y
            self.stuck_check_time = time.time()

            return True

        except Exception as e:
            API.SysMsg("patrol_waypoints error: " + str(e), 32)
            return False

    def reset_waypoint_patrol(self):
        """Reset waypoint patrol to beginning"""
        self.current_waypoint_index = 0
        self.patrol_direction = "forward"

    def cancel_patrol(self):
        """Cancel current patrol"""
        if API.Pathfinding():
            API.CancelPathfinding()
        self.STATE = "idle"
        self.patrol_active = False


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

def test_patrol_system():
    """Test function to verify PatrolSystem works correctly"""
    API.SysMsg("Testing PatrolSystem...", 68)

    try:
        # Initialize PatrolSystem
        patrol_system = PatrolSystem()

        # Create a test circle area
        test_area = FarmingArea("Test Circle", "circle")
        current_x, current_y = patrol_system.get_current_position()
        test_area.center_x = current_x
        test_area.center_y = current_y
        test_area.radius = 10

        API.SysMsg("Test area center: (" + str(test_area.center_x) + ", " + str(test_area.center_y) + ")", 43)
        API.SysMsg("Radius: " + str(test_area.radius) + " tiles", 43)

        # Test patrol_circle
        API.SysMsg("Starting circle patrol...", 68)
        if patrol_system.patrol_circle(test_area):
            API.SysMsg("Patrol started! Destination: (" + str(patrol_system.destination_x) + ", " + str(patrol_system.destination_y) + ")", 68)

            # Monitor patrol progress
            max_iterations = 200  # 20 seconds max
            iteration = 0
            while iteration < max_iterations:
                API.ProcessCallbacks()

                result = patrol_system.check_patrol_progress()

                if result == "arrived":
                    API.SysMsg("Arrived at destination!", 68)
                    break
                elif result == "stuck":
                    API.SysMsg("Patrol stuck detected", 32)
                    break
                elif result == "interrupted":
                    API.SysMsg("Patrol interrupted", 43)
                    break
                elif result == "error":
                    API.SysMsg("Patrol error", 32)
                    break

                iteration += 1
                API.Pause(0.1)

            if iteration >= max_iterations:
                API.SysMsg("Patrol test timeout (still moving)", 43)

        else:
            API.SysMsg("Failed to start patrol", 32)

        API.SysMsg("PatrolSystem test complete", 68)

    except Exception as e:
        API.SysMsg("Test error: " + str(e), 32)

def test_waypoint_patrol():
    """Test function to verify waypoint patrol works correctly"""
    API.SysMsg("Testing Waypoint Patrol...", 68)

    try:
        # Initialize PatrolSystem
        patrol_system = PatrolSystem()

        # Create a test waypoint area with 5 waypoints forming a path
        test_area = FarmingArea("Test Waypoints", "waypoints")
        current_x, current_y = patrol_system.get_current_position()

        # Create a square path around current position
        test_area.waypoints = [
            (current_x + 5, current_y),
            (current_x + 5, current_y + 5),
            (current_x, current_y + 5),
            (current_x - 5, current_y + 5),
            (current_x - 5, current_y)
        ]

        API.SysMsg("Test waypoint path with " + str(len(test_area.waypoints)) + " waypoints", 43)

        # Test multiple waypoint movements
        for i in range(3):
            API.SysMsg("Waypoint iteration " + str(i + 1) + ", index: " + str(patrol_system.current_waypoint_index), 68)

            if patrol_system.patrol_waypoints(test_area):
                API.SysMsg("Patrol started! Destination: (" + str(patrol_system.destination_x) + ", " + str(patrol_system.destination_y) + ")", 68)

                # Monitor patrol progress
                max_iterations = 200  # 20 seconds max
                iteration = 0
                while iteration < max_iterations:
                    API.ProcessCallbacks()

                    result = patrol_system.check_patrol_progress(area=test_area)

                    if result == "arrived":
                        API.SysMsg("Arrived at waypoint " + str(patrol_system.current_waypoint_index), 68)
                        break
                    elif result == "stuck":
                        API.SysMsg("Patrol stuck detected", 32)
                        break
                    elif result == "interrupted":
                        API.SysMsg("Patrol interrupted", 43)
                        break
                    elif result == "error":
                        API.SysMsg("Patrol error", 32)
                        break

                    iteration += 1
                    API.Pause(0.1)

                if iteration >= max_iterations:
                    API.SysMsg("Waypoint patrol timeout (still moving)", 43)
                    break

            else:
                API.SysMsg("Failed to start waypoint patrol", 32)
                break

        # Test reset
        patrol_system.reset_waypoint_patrol()
        API.SysMsg("Reset waypoint patrol - index now: " + str(patrol_system.current_waypoint_index), 68)

        API.SysMsg("Waypoint patrol test complete", 68)

    except Exception as e:
        API.SysMsg("Test error: " + str(e), 32)

def test_npc_threat_map():
    """Test function to verify NPCThreatMap works correctly"""
    API.SysMsg("Testing NPCThreatMap...", 68)

    try:
        # Initialize NPCThreatMap
        threat_map = NPCThreatMap(avoid_radius=6, scan_radius=12, refresh_interval=2.0)
        API.SysMsg("NPCThreatMap initialized", 68)
        API.SysMsg("Avoid radius: 6 tiles, Scan radius: 12 tiles", 43)

        # Test 1: Scan for NPCs
        API.SysMsg("Scanning for NPCs...", 68)
        npc_positions = threat_map.scan_npcs(force_scan=True)
        API.SysMsg("Found " + str(len(npc_positions)) + " NPCs", 68)

        for i, (npc_x, npc_y) in enumerate(npc_positions[:5]):  # Show first 5
            API.SysMsg("  NPC " + str(i + 1) + ": (" + str(npc_x) + ", " + str(npc_y) + ")", 43)

        if len(npc_positions) > 5:
            API.SysMsg("  ... and " + str(len(npc_positions) - 5) + " more", 43)

        # Test 2: Check current position safety
        player_x = getattr(API.Player, 'X', 0)
        player_y = getattr(API.Player, 'Y', 0)
        API.SysMsg("Checking current position safety: (" + str(player_x) + ", " + str(player_y) + ")", 68)

        if threat_map.is_position_safe(player_x, player_y):
            API.SysMsg("Current position is SAFE", 68)
        else:
            API.SysMsg("Current position is in AVOID ZONE", 32)

        # Test 3: Check position next to nearest NPC (if any)
        if npc_positions:
            nearest = threat_map.get_nearest_threat(player_x, player_y)
            if nearest:
                npc_x, npc_y, distance = nearest
                API.SysMsg("Nearest threat: (" + str(npc_x) + ", " + str(npc_y) + ") at " + str(int(distance)) + " tiles", 43)

                # Check position right next to NPC (should be unsafe)
                test_x = npc_x + 3
                test_y = npc_y + 3
                API.SysMsg("Checking position near NPC: (" + str(test_x) + ", " + str(test_y) + ")", 68)

                if threat_map.is_position_safe(test_x, test_y):
                    API.SysMsg("Position is SAFE (unexpected)", 43)
                else:
                    API.SysMsg("Position is in AVOID ZONE (correct)", 68)

                # Check position far from NPCs (should be safe)
                test_x = npc_x + 15
                test_y = npc_y + 15
                API.SysMsg("Checking position far from NPC: (" + str(test_x) + ", " + str(test_y) + ")", 68)

                if threat_map.is_position_safe(test_x, test_y):
                    API.SysMsg("Position is SAFE (correct)", 68)
                else:
                    API.SysMsg("Position is in AVOID ZONE (unexpected)", 43)

        # Test 4: Calculate safe direction
        if npc_positions:
            API.SysMsg("Calculating safe direction from current position...", 68)
            safe_dir = threat_map.calculate_safe_direction(player_x, player_y)

            if safe_dir:
                dx, dy = safe_dir
                API.SysMsg("Safe direction: (" + str(dx) + ", " + str(dy) + ")", 68)
                API.SysMsg("Safe destination: (" + str(player_x + dx) + ", " + str(player_y + dy) + ")", 43)
            else:
                API.SysMsg("No safe direction found (surrounded!)", 32)

        # Test 5: Test refresh interval
        API.SysMsg("Testing refresh interval (2 seconds)...", 68)
        threat_map.scan_npcs()  # Should use cached results
        API.SysMsg("Scan 1 (should use cache): " + str(threat_map.get_threat_count()) + " NPCs", 43)

        API.Pause(2.5)
        threat_map.scan_npcs()  # Should scan again after interval
        API.SysMsg("Scan 2 (after 2.5s delay): " + str(threat_map.get_threat_count()) + " NPCs", 43)

        # Test 6: Force scan
        API.SysMsg("Testing force scan (ignoring interval)...", 68)
        npc_positions = threat_map.scan_npcs(force_scan=True)
        API.SysMsg("Force scan: " + str(len(npc_positions)) + " NPCs", 43)

        # Test 7: Clear threats
        threat_map.clear_threats()
        API.SysMsg("Cleared threats. Count: " + str(threat_map.get_threat_count()), 68)

        API.SysMsg("NPCThreatMap test complete!", 68)

    except Exception as e:
        API.SysMsg("Test error: " + str(e), 32)
        import traceback
        API.SysMsg(str(traceback.format_exc()), 32)

def test_danger_assessment():
    """Test function to verify DangerAssessment works correctly"""
    API.SysMsg("Testing DangerAssessment...", 68)

    try:
        # Initialize systems
        pet_manager = PetManager()
        pet_manager.scan_pets()
        danger_assessment = DangerAssessment(pet_manager)

        API.SysMsg("DangerAssessment initialized", 68)
        API.SysMsg("Default weights: Player=" + str(danger_assessment.weights["player_hp"]) +
                   ", Tank=" + str(danger_assessment.weights["tank_pet_hp"]) +
                   ", Enemy=" + str(danger_assessment.weights["enemy_count"]), 43)

        # Test 1: Calculate danger with no enemies
        danger = danger_assessment.calculate_danger(enemy_count=0, npc_count=0)
        zone = danger_assessment.get_danger_zone()
        API.SysMsg("Danger (no enemies): " + str(int(danger)) + " - Zone: " + zone, 68)

        # Test 2: Calculate danger with 3 enemies
        danger = danger_assessment.calculate_danger(enemy_count=3, npc_count=0)
        zone = danger_assessment.get_danger_zone()
        API.SysMsg("Danger (3 enemies): " + str(int(danger)) + " - Zone: " + zone, 68)

        # Test 3: Calculate danger with 5 nearby NPCs
        danger = danger_assessment.calculate_danger(enemy_count=1, npc_count=5)
        zone = danger_assessment.get_danger_zone()
        API.SysMsg("Danger (1 enemy + 5 NPCs): " + str(int(danger)) + " - Zone: " + zone, 68)

        # Test 4: Test weight adjustment
        API.SysMsg("Adjusting enemy_count weight to 30...", 43)
        danger_assessment.configure_weights(enemy_count=30)
        danger = danger_assessment.calculate_danger(enemy_count=3, npc_count=0)
        zone = danger_assessment.get_danger_zone()
        API.SysMsg("Danger (3 enemies, higher weight): " + str(int(danger)) + " - Zone: " + zone, 68)

        # Test 5: Test trend analysis
        for i in range(10):
            danger_assessment.calculate_danger(enemy_count=i, npc_count=0)
            API.Pause(0.1)

        trend = danger_assessment.get_danger_trend()
        API.SysMsg("Danger trend (increasing enemies): " + trend, 68)

        # Test 6: Test threshold configuration
        API.SysMsg("Adjusting thresholds (safe=20, elevated=40, high=60)...", 43)
        danger_assessment.configure_thresholds(safe=20, elevated=40, high=60)
        danger = 35
        zone = danger_assessment.get_danger_zone(danger)
        API.SysMsg("Danger " + str(danger) + " with new thresholds: " + zone, 68)

        API.SysMsg("DangerAssessment test complete!", 68)

    except Exception as e:
        API.SysMsg("Test error: " + str(e), 32)

def test_combat_manager():
    """Test function to verify CombatManager works correctly"""
    API.SysMsg("Testing CombatManager...", 68)

    try:
        # Initialize systems
        pet_manager = PetManager()
        pet_manager.scan_pets()
        healing_system = HealingSystem(pet_manager)
        danger_assessment = DangerAssessment(pet_manager)
        npc_threat_map = NPCThreatMap()
        npc_threat_map.scan_npcs(force_scan=True)
        combat_manager = CombatManager(danger_assessment, npc_threat_map, pet_manager, healing_system)

        API.SysMsg("CombatManager initialized", 68)
        API.SysMsg("Settings: Scan range=" + str(combat_manager.enemy_scan_range) +
                   ", Max danger=" + str(combat_manager.max_danger_to_engage) +
                   ", Max hostiles=" + str(combat_manager.max_nearby_hostiles), 43)

        # Test 1: Scan for enemies
        API.SysMsg("Scanning for enemies...", 68)
        enemies = combat_manager.scan_for_enemies()
        API.SysMsg("Found " + str(len(enemies)) + " enemies", 68)

        for i, enemy_serial in enumerate(enemies[:3]):  # Show first 3
            enemy = API.Mobiles.FindMobile(enemy_serial)
            if enemy:
                API.SysMsg("  Enemy " + str(i + 1) + ": " + enemy.Name +
                          " (Serial: " + str(enemy_serial) + ", Distance: " + str(enemy.Distance) + ")", 43)

        # Test 2: Evaluate engagement for first enemy
        if enemies:
            first_enemy = enemies[0]
            API.SysMsg("Evaluating engagement for first enemy...", 68)

            # Calculate current danger
            current_danger = danger_assessment.calculate_danger(enemy_count=len(enemies), npc_count=npc_threat_map.get_threat_count())
            API.SysMsg("Current danger: " + str(int(current_danger)), 43)

            should_engage = combat_manager.should_engage_enemy(first_enemy)
            API.SysMsg("Should engage: " + str(should_engage), 68 if should_engage else 32)

            # Test 3: Test with high danger (should refuse to engage)
            API.SysMsg("Testing with danger > max_danger_to_engage...", 43)
            danger_assessment.configure_weights(player_hp=50)  # Increase player HP weight
            danger_assessment.calculate_danger(enemy_count=len(enemies) + 5, npc_count=10)
            should_engage = combat_manager.should_engage_enemy(first_enemy)
            API.SysMsg("Should engage (high danger): " + str(should_engage) + " (expected False)", 43)

            # Test 4: Test engagement (only if should_engage is True)
            danger_assessment.configure_weights(player_hp=40)  # Reset
            current_danger = danger_assessment.calculate_danger(enemy_count=len(enemies), npc_count=npc_threat_map.get_threat_count())

            if should_engage and current_danger <= combat_manager.max_danger_to_engage:
                API.SysMsg("Attempting to engage enemy (will issue 'all kill')...", 68)
                if combat_manager.engage_enemy(first_enemy):
                    API.SysMsg("Engagement started! Engaged enemy serial: " + str(combat_manager.engaged_enemy_serial), 68)
                    API.SysMsg("Combat duration: " + str(combat_manager.get_combat_duration()) + "s", 43)

                    # Clear engagement
                    API.Pause(1.0)
                    combat_manager.clear_engagement()
                    API.SysMsg("Engagement cleared", 43)
                else:
                    API.SysMsg("Failed to engage enemy", 32)
        else:
            API.SysMsg("No enemies found to test engagement", 43)

        # Test 5: Test configuration
        API.SysMsg("Testing configuration update...", 68)
        combat_manager.configure_engagement(scan_range=15, max_danger=60, max_hostiles=2)
        API.SysMsg("New settings: Scan range=" + str(combat_manager.enemy_scan_range) +
                   ", Max danger=" + str(combat_manager.max_danger_to_engage) +
                   ", Max hostiles=" + str(combat_manager.max_nearby_hostiles), 43)

        # Test 6: Test enemy type configuration
        API.SysMsg("Testing enemy type configuration...", 68)
        combat_manager.configure_enemy_types(attack_reds=True, attack_grays=True)
        enemies_with_grays = combat_manager.scan_for_enemies()
        API.SysMsg("Enemies (reds + grays): " + str(len(enemies_with_grays)), 43)

        combat_manager.configure_enemy_types(attack_reds=True, attack_grays=False)
        enemies_reds_only = combat_manager.scan_for_enemies()
        API.SysMsg("Enemies (reds only): " + str(len(enemies_reds_only)), 43)

        API.SysMsg("CombatManager test complete!", 68)

    except Exception as e:
        API.SysMsg("Test error: " + str(e), 32)
        import traceback
        API.SysMsg(str(traceback.format_exc()), 32)

def test_monitor_combat():
    """Test function to verify monitor_combat() works correctly"""
    API.SysMsg("Testing CombatManager.monitor_combat()...", 68)

    try:
        # Initialize systems
        pet_manager = PetManager()
        pet_manager.scan_pets()
        healing_system = HealingSystem(pet_manager)
        danger_assessment = DangerAssessment(pet_manager)
        npc_threat_map = NPCThreatMap()
        npc_threat_map.scan_npcs(force_scan=True)
        combat_manager = CombatManager(danger_assessment, npc_threat_map, pet_manager, healing_system)

        API.SysMsg("CombatManager initialized with HealingSystem", 68)

        # Test 1: Monitor combat with no engagement
        API.SysMsg("Test 1: Monitor with no engagement...", 68)
        result = combat_manager.monitor_combat()
        API.SysMsg("  Status: " + result["status"] + " (expected: no_engagement)", 43)

        # Test 2: Engage an enemy and monitor
        enemies = combat_manager.scan_for_enemies()
        if enemies:
            first_enemy = enemies[0]
            API.SysMsg("Test 2: Engaging enemy and monitoring...", 68)

            # Engage enemy
            if combat_manager.engage_enemy(first_enemy):
                API.SysMsg("  Engaged enemy serial: " + str(combat_manager.engaged_enemy_serial), 68)

                # Monitor combat for a few cycles
                for i in range(5):
                    API.Pause(0.3)
                    result = combat_manager.monitor_combat()
                    API.SysMsg("  Cycle " + str(i + 1) + " - Status: " + result["status"], 43)

                    if result["status"] == "enemy_dead":
                        API.SysMsg("    Enemy defeated! Corpse serial: " + str(result["corpse_serial"]), 68)
                        break
                    elif result["status"] == "enemy_lost":
                        API.SysMsg("    Enemy lost", 43)
                        break
                    elif result["status"] == "flee_now":
                        API.SysMsg("    FLEE TRIGGERED!", 32)
                        break
                    elif result["status"] == "high_danger":
                        API.SysMsg("    High danger - all guard me issued", 43)
                    elif result["status"] == "critical_heal_needed":
                        API.SysMsg("    Critical heal needed", 43)
                    elif result["status"] == "recalling_tank":
                        API.SysMsg("    Recalling tank pet", 43)

                # Clear engagement
                combat_manager.clear_engagement()
                API.SysMsg("  Engagement cleared", 43)
        else:
            API.SysMsg("Test 2: No enemies found to test monitoring", 43)

        # Test 3: Test statistics
        API.SysMsg("Test 3: Combat statistics...", 68)
        stats = combat_manager.get_combat_statistics()
        API.SysMsg("  Kills: " + str(stats["kills"]), 43)
        API.SysMsg("  Total combat duration: " + str(int(stats["total_combat_duration"])) + "s", 43)
        API.SysMsg("  Avg combat duration: " + str(int(stats["avg_combat_duration"])) + "s", 43)

        # Test 4: Test danger threshold configuration
        API.SysMsg("Test 4: Configure danger thresholds...", 68)
        combat_manager.configure_danger_thresholds(flee_threshold=80, high_threshold=60)
        API.SysMsg("  New flee threshold: " + str(combat_manager.flee_threshold), 43)
        API.SysMsg("  New high threshold: " + str(combat_manager.high_threshold), 43)

        # Test 5: Test corpse tracking
        API.SysMsg("Test 5: Corpse tracking...", 68)
        API.SysMsg("  Current corpse serial: " + str(combat_manager.get_corpse_serial()), 43)
        combat_manager.clear_corpse()
        API.SysMsg("  After clear: " + str(combat_manager.get_corpse_serial()) + " (expected: 0)", 43)

        API.SysMsg("CombatManager.monitor_combat() test complete!", 68)

    except Exception as e:
        API.SysMsg("Test error: " + str(e), 32)
        import traceback
        API.SysMsg(str(traceback.format_exc()), 32)

# Run tests if script is loaded
# Uncomment to test:
# test_farming_areas()
# test_healing_system()
# test_area_recording_gump()
# test_patrol_system()
# test_waypoint_patrol()
# test_npc_threat_map()
# test_danger_assessment()
# test_combat_manager()
# test_monitor_combat()

API.SysMsg("Dungeon Farmer loaded (FarmingArea + HealingSystem + PatrolSystem + NPCThreatMap + DangerAssessment + CombatManager v1.6)", 68)
