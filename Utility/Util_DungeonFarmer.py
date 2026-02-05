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


# ========== MAIN SCRIPT ==========
# NOTE: This is a foundational implementation for the HealingSystem class.
# The full dungeon farming script will be built up in subsequent tasks.

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

# Run test if script is loaded
# Uncomment to test:
# test_healing_system()

API.SysMsg("Dungeon Farmer loaded (HealingSystem v1.0)", 68)
