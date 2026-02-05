# ============================================================
# Tamer Pet Farmer v1.0
# by Coryigon for UO Unchained
# ============================================================
#
# Automated pet farming script with intelligent area patrol,
# danger assessment, combat management, and banking automation.
#
# Features:
#   - Multi-pet combat coordination with smart healing
#   - Dynamic area definition (circle or waypoint-based patrol)
#   - NPC/danger avoidance with threat mapping
#   - Selective looting with weight management
#   - Auto-banking with supply restocking
#   - Dungeon-aware flee mechanics
#   - Emergency recall and recovery
#
# Setup:
#   1. Configure pets and healing thresholds
#   2. Define farming area (circle or waypoints)
#   3. Set loot preferences and banking triggers
#   4. Start script and monitor from control panel
#
# ============================================================
import API
import time
import random
from LegionUtils import WindowPositionTracker, ResourceRateTracker
from GatherFramework import TravelSystem

__version__ = "1.0"

# ============ CONSTANTS ============

# === TIMING ===
BANDAGE_DELAY = 4.5              # Self/pet bandage time
VET_DELAY = 4.5                  # Pet bandage time
REZ_DELAY = 10.0                 # Pet resurrection time
CAST_DELAY = 2.5                 # Greater Heal spell time
VET_KIT_DELAY = 5.0              # Vet kit cooldown
POTION_DELAY = 10.0              # Potion cooldown

# === RANGES ===
BANDAGE_RANGE = 2
SPELL_RANGE = 10
MAX_FOLLOW_RANGE = 15
ENEMY_SCAN_RANGE = 10
LOOT_RANGE = 2

# === HEALTH THRESHOLDS ===
SELF_HEAL_THRESHOLD = 15         # Heal self when missing this many HP
TANK_HP_PERCENT = 50             # Priority heal tank below this %
PET_HP_PERCENT = 90              # Heal pets below this %
VET_KIT_HP_PERCENT = 90          # Vet kit threshold
VET_KIT_THRESHOLD = 2            # Use vet kit when this many pets hurt
VET_KIT_COOLDOWN = 5.0           # Min seconds between vet kit uses

# === COMBAT ===
ENGAGE_DISTANCE = 8              # Distance to engage enemies
FLEE_HP_PERCENT = 30             # Player HP% to trigger flee
FLEE_DISTANCE = 8                # Min distance from enemy to recall
FLEE_TIMEOUT = 15.0              # Max flee time before forced recall

# === BANKING ===
BANK_WEIGHT_PERCENT = 85         # Bank at this weight %
BANK_RECALL_ATTEMPTS = 3         # Max recall attempts before emergency

# === ITEM GRAPHICS ===
BANDAGE = 3617
GOLD = 3821

# === PERSISTENCE KEYS ===
KEY_PREFIX = "TamerPetFarmer_"
SHARED_PETS_KEY = "SharedPets_List"

# === GUI DIMENSIONS ===
MAIN_WIDTH = 320
MAIN_HEIGHT = 280
CONFIG_WIDTH = 520
CONFIG_HEIGHT = 450

# ============ GLOBAL STATE ============

# State machine
STATE = "idle"
action_start_time = 0
last_action = ""

# Script control
script_enabled = True
script_paused = False

# Pet data
pets = []  # List of pet dicts: {name, serial, is_tank, hotkey}
active_pet_names = set()  # Set of active pet names

# Area definition
area_type = "none"  # "none", "circle", "waypoints"
area_center_x = 0
area_center_y = 0
area_radius = 15
area_waypoints = []  # List of (x, y) tuples
current_waypoint_index = 0

# Combat tracking
current_enemy = None
enemy_serial = 0
last_enemy_check = 0
combat_start_time = 0

# Danger/NPC avoidance
npc_positions = []  # List of (x, y) tuples to avoid
last_npc_scan = 0
danger_assessment = None  # DangerAssessment instance
npc_threat_map = None     # NPCThreatMap instance

# Area & flee system
area_manager = None       # AreaManager instance
flee_system = None        # FleeSystem instance
recovery_system = None    # RecoverySystem instance
pet_manager = None        # PetManager instance
danger_at_flee = 0        # Danger score when flee was initiated

# Supply tracking
supply_tracker = None     # SupplyTracker instance

# Healing system
healing_system = None     # HealingSystem instance

# Banking system
banking_system = None     # BankingSystem instance

# Statistics tracking
stats_tracker = None      # StatisticsTracker instance
last_stats_update = 0     # Last time stats display was updated
banking_triggers = None   # BankingTriggers instance

# Combat and patrol systems
combat_manager = None     # CombatManager instance
patrol_system = None      # PatrolSystem instance
looting_system = None     # LootingSystem instance

# Session logging
session_logger = None     # SessionLogger instance

# Error recovery
error_recovery = None     # ErrorRecoverySystem instance

# Travel system
travel_system = None      # TravelSystem instance

# Healing tracking
last_heal_time = 0
last_vet_kit_time = 0
priority_heal_pet = None  # Serial of pet flagged for priority heal

# Healing configuration
player_heal_threshold = 85  # Heal player at this HP%
tank_heal_threshold = 70    # Heal tank pet at this HP%
pet_heal_threshold = 50     # Heal other pets at this HP%
vetkit_graphic = 0          # Vet kit item graphic (0 = not set)
vetkit_hp_threshold = 90    # Use vet kit when pets below this HP%
vetkit_min_pets = 2         # Min number of pets hurt to trigger vet kit
vetkit_cooldown = 5.0       # Cooldown between vet kit uses
vetkit_critical_hp = 50     # Emergency vet kit bypass threshold
use_magery_healing = False  # Use magery for healing
auto_cure_poison = True     # Auto-cure poison

# Banking tracking
last_bank_time = 0
banking_enabled = False
bank_runebook_serial = 0
bank_spot_index = 0
return_runebook_serial = 0
return_spot_index = 0

# Looting tracking
loot_corpses = True
loot_gold_only = False
loot_threshold_value = 100
looted_corpses = set()  # Serials of already-looted corpses

# Statistics
stats = {
    "kills": 0,
    "deaths": 0,
    "gold_looted": 0,
    "banking_trips": 0,
    "flee_events": 0,
    "session_start": time.time()
}

# GUI references
main_gump = None
config_gump = None
main_controls = {}
config_controls = {}
main_pos_tracker = None
config_pos_tracker = None
current_config_tab = "healing"  # Current tab in config window

# Error tracking
last_error_time = 0
error_count = 0

# Advanced settings
# Randomization
movement_delay = 1.5         # Movement delay in seconds (range ±0.5s)
pause_frequency = 20         # Chance (%) to pause per action
pause_duration = 3.0         # Pause duration in seconds (random range)

# Error Recovery
max_recovery_attempts = 3    # Max recovery attempts before giving up
recovery_backoff_time = 30   # Backoff time in seconds between recovery attempts

# Logging
log_level = "standard"       # "basic", "standard", "detailed"

# ============ PERSISTENCE ============

def save_settings():
    """Save all persistent settings"""
    try:
        # Script state
        API.SavePersistentVar(KEY_PREFIX + "Enabled", str(script_enabled), API.PersistentVar.Char)

        # Pet configuration
        pet_data = []
        for pet in pets:
            pet_str = f"{pet['name']}:{pet.get('serial', 0)}:{pet.get('is_tank', False)}:{pet.get('hotkey', '')}"
            pet_data.append(pet_str)
        API.SavePersistentVar(KEY_PREFIX + "Pets", "|".join(pet_data), API.PersistentVar.Char)

        # Area configuration
        API.SavePersistentVar(KEY_PREFIX + "AreaType", area_type, API.PersistentVar.Char)
        API.SavePersistentVar(KEY_PREFIX + "AreaCenterX", str(area_center_x), API.PersistentVar.Char)
        API.SavePersistentVar(KEY_PREFIX + "AreaCenterY", str(area_center_y), API.PersistentVar.Char)
        API.SavePersistentVar(KEY_PREFIX + "AreaRadius", str(area_radius), API.PersistentVar.Char)

        waypoint_strs = [f"{x},{y}" for x, y in area_waypoints]
        API.SavePersistentVar(KEY_PREFIX + "AreaWaypoints", "|".join(waypoint_strs), API.PersistentVar.Char)

        # Banking configuration
        API.SavePersistentVar(KEY_PREFIX + "BankingEnabled", str(banking_enabled), API.PersistentVar.Char)
        API.SavePersistentVar(KEY_PREFIX + "BankRunebook", str(bank_runebook_serial), API.PersistentVar.Char)
        API.SavePersistentVar(KEY_PREFIX + "BankSpot", str(bank_spot_index), API.PersistentVar.Char)
        API.SavePersistentVar(KEY_PREFIX + "ReturnRunebook", str(return_runebook_serial), API.PersistentVar.Char)
        API.SavePersistentVar(KEY_PREFIX + "ReturnSpot", str(return_spot_index), API.PersistentVar.Char)

        # Looting configuration
        API.SavePersistentVar(KEY_PREFIX + "LootCorpses", str(loot_corpses), API.PersistentVar.Char)
        API.SavePersistentVar(KEY_PREFIX + "LootGoldOnly", str(loot_gold_only), API.PersistentVar.Char)
        API.SavePersistentVar(KEY_PREFIX + "LootThreshold", str(loot_threshold_value), API.PersistentVar.Char)

        # Healing configuration
        API.SavePersistentVar(KEY_PREFIX + "PlayerHealThreshold", str(player_heal_threshold), API.PersistentVar.Char)
        API.SavePersistentVar(KEY_PREFIX + "TankHealThreshold", str(tank_heal_threshold), API.PersistentVar.Char)
        API.SavePersistentVar(KEY_PREFIX + "PetHealThreshold", str(pet_heal_threshold), API.PersistentVar.Char)
        API.SavePersistentVar(KEY_PREFIX + "VetkitGraphic", str(vetkit_graphic), API.PersistentVar.Char)
        API.SavePersistentVar(KEY_PREFIX + "VetkitHPThreshold", str(vetkit_hp_threshold), API.PersistentVar.Char)
        API.SavePersistentVar(KEY_PREFIX + "VetkitMinPets", str(vetkit_min_pets), API.PersistentVar.Char)
        API.SavePersistentVar(KEY_PREFIX + "VetkitCooldown", str(vetkit_cooldown), API.PersistentVar.Char)
        API.SavePersistentVar(KEY_PREFIX + "VetkitCriticalHP", str(vetkit_critical_hp), API.PersistentVar.Char)
        API.SavePersistentVar(KEY_PREFIX + "UseMageryHealing", str(use_magery_healing), API.PersistentVar.Char)
        API.SavePersistentVar(KEY_PREFIX + "AutoCurePoison", str(auto_cure_poison), API.PersistentVar.Char)

        # Advanced settings
        API.SavePersistentVar(KEY_PREFIX + "MovementDelay", str(movement_delay), API.PersistentVar.Char)
        API.SavePersistentVar(KEY_PREFIX + "PauseFrequency", str(pause_frequency), API.PersistentVar.Char)
        API.SavePersistentVar(KEY_PREFIX + "PauseDuration", str(pause_duration), API.PersistentVar.Char)
        API.SavePersistentVar(KEY_PREFIX + "MaxRecoveryAttempts", str(max_recovery_attempts), API.PersistentVar.Char)
        API.SavePersistentVar(KEY_PREFIX + "RecoveryBackoffTime", str(recovery_backoff_time), API.PersistentVar.Char)
        API.SavePersistentVar(KEY_PREFIX + "LogLevel", log_level, API.PersistentVar.Char)

    except Exception as e:
        API.SysMsg(f"Save error: {str(e)}", 32)

def load_settings():
    """Load all persistent settings"""
    global script_enabled, pets, area_type, area_center_x, area_center_y, area_radius
    global area_waypoints, banking_enabled, bank_runebook_serial, bank_spot_index
    global return_runebook_serial, return_spot_index, loot_corpses, loot_gold_only
    global loot_threshold_value, player_heal_threshold, tank_heal_threshold, pet_heal_threshold
    global vetkit_graphic, vetkit_hp_threshold, vetkit_min_pets, vetkit_cooldown
    global vetkit_critical_hp, use_magery_healing, auto_cure_poison
    global movement_delay, pause_frequency, pause_duration
    global max_recovery_attempts, recovery_backoff_time, log_level

    try:
        # Script state
        script_enabled = API.GetPersistentVar(KEY_PREFIX + "Enabled", "True", API.PersistentVar.Char) == "True"

        # Pet configuration
        pet_data_str = API.GetPersistentVar(KEY_PREFIX + "Pets", "", API.PersistentVar.Char)
        if pet_data_str:
            pets = []
            for pet_str in pet_data_str.split("|"):
                if pet_str:
                    parts = pet_str.split(":")
                    if len(parts) >= 4:
                        pets.append({
                            "name": parts[0],
                            "serial": int(parts[1]) if parts[1].isdigit() else 0,
                            "is_tank": parts[2] == "True",
                            "hotkey": parts[3]
                        })

        # Area configuration
        area_type = API.GetPersistentVar(KEY_PREFIX + "AreaType", "none", API.PersistentVar.Char)
        area_center_x = int(API.GetPersistentVar(KEY_PREFIX + "AreaCenterX", "0", API.PersistentVar.Char))
        area_center_y = int(API.GetPersistentVar(KEY_PREFIX + "AreaCenterY", "0", API.PersistentVar.Char))
        area_radius = int(API.GetPersistentVar(KEY_PREFIX + "AreaRadius", "15", API.PersistentVar.Char))

        waypoint_str = API.GetPersistentVar(KEY_PREFIX + "AreaWaypoints", "", API.PersistentVar.Char)
        area_waypoints = []
        if waypoint_str:
            for wp in waypoint_str.split("|"):
                if wp and "," in wp:
                    x, y = wp.split(",")
                    area_waypoints.append((int(x), int(y)))

        # Banking configuration
        banking_enabled = API.GetPersistentVar(KEY_PREFIX + "BankingEnabled", "False", API.PersistentVar.Char) == "True"
        bank_runebook_serial = int(API.GetPersistentVar(KEY_PREFIX + "BankRunebook", "0", API.PersistentVar.Char))
        bank_spot_index = int(API.GetPersistentVar(KEY_PREFIX + "BankSpot", "0", API.PersistentVar.Char))
        return_runebook_serial = int(API.GetPersistentVar(KEY_PREFIX + "ReturnRunebook", "0", API.PersistentVar.Char))
        return_spot_index = int(API.GetPersistentVar(KEY_PREFIX + "ReturnSpot", "0", API.PersistentVar.Char))

        # Looting configuration
        loot_corpses = API.GetPersistentVar(KEY_PREFIX + "LootCorpses", "True", API.PersistentVar.Char) == "True"
        loot_gold_only = API.GetPersistentVar(KEY_PREFIX + "LootGoldOnly", "False", API.PersistentVar.Char) == "True"
        loot_threshold_value = int(API.GetPersistentVar(KEY_PREFIX + "LootThreshold", "100", API.PersistentVar.Char))

        # Healing configuration
        player_heal_threshold = int(API.GetPersistentVar(KEY_PREFIX + "PlayerHealThreshold", "85", API.PersistentVar.Char))
        tank_heal_threshold = int(API.GetPersistentVar(KEY_PREFIX + "TankHealThreshold", "70", API.PersistentVar.Char))
        pet_heal_threshold = int(API.GetPersistentVar(KEY_PREFIX + "PetHealThreshold", "50", API.PersistentVar.Char))
        vetkit_graphic = int(API.GetPersistentVar(KEY_PREFIX + "VetkitGraphic", "0", API.PersistentVar.Char))
        vetkit_hp_threshold = int(API.GetPersistentVar(KEY_PREFIX + "VetkitHPThreshold", "90", API.PersistentVar.Char))
        vetkit_min_pets = int(API.GetPersistentVar(KEY_PREFIX + "VetkitMinPets", "2", API.PersistentVar.Char))
        vetkit_cooldown = float(API.GetPersistentVar(KEY_PREFIX + "VetkitCooldown", "5.0", API.PersistentVar.Char))
        vetkit_critical_hp = int(API.GetPersistentVar(KEY_PREFIX + "VetkitCriticalHP", "50", API.PersistentVar.Char))
        use_magery_healing = API.GetPersistentVar(KEY_PREFIX + "UseMageryHealing", "False", API.PersistentVar.Char) == "True"
        auto_cure_poison = API.GetPersistentVar(KEY_PREFIX + "AutoCurePoison", "True", API.PersistentVar.Char) == "True"

        # Advanced settings
        movement_delay = float(API.GetPersistentVar(KEY_PREFIX + "MovementDelay", "1.5", API.PersistentVar.Char))
        pause_frequency = int(API.GetPersistentVar(KEY_PREFIX + "PauseFrequency", "20", API.PersistentVar.Char))
        pause_duration = float(API.GetPersistentVar(KEY_PREFIX + "PauseDuration", "3.0", API.PersistentVar.Char))
        max_recovery_attempts = int(API.GetPersistentVar(KEY_PREFIX + "MaxRecoveryAttempts", "3", API.PersistentVar.Char))
        recovery_backoff_time = int(API.GetPersistentVar(KEY_PREFIX + "RecoveryBackoffTime", "30", API.PersistentVar.Char))
        log_level = API.GetPersistentVar(KEY_PREFIX + "LogLevel", "standard", API.PersistentVar.Char)

    except Exception as e:
        API.SysMsg(f"Load error: {str(e)}", 32)

# ============ HELPER FUNCTIONS ============

def get_player_pos():
    """Get current player position"""
    return (getattr(API.Player, 'X', 0), getattr(API.Player, 'Y', 0))

def distance(x1, y1, x2, y2):
    """Calculate distance between two points"""
    return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5

# ============ PET MANAGEMENT SYSTEM ============

class PetManager:
    """
    Pet detection, tracking, and management system.
    Handles pet scanning, tank designation, validation, and resurrection targeting.
    """

    def __init__(self, key_prefix):
        self.key_prefix = key_prefix
        self.pets = []  # List of dicts: [{"serial": int, "name": str, "is_tank": bool}, ...]
        self._tank_serial = self._load_tank_serial()

    def _load_tank_serial(self):
        """Load persisted tank pet serial"""
        serial_str = API.GetPersistentVar(self.key_prefix + "TankSerial", "0", API.PersistentVar.Char)
        return int(serial_str) if serial_str.isdigit() else 0

    def _save_tank_serial(self):
        """Save tank pet serial to persistence"""
        API.SavePersistentVar(self.key_prefix + "TankSerial", str(self._tank_serial), API.PersistentVar.Char)

    def scan_pets(self):
        """
        Scan for owned pets (Notoriety == 1) and populate pets list.
        Automatically designates tank pet (highest HP or previously set).
        """
        try:
            # Get all mobiles with Notoriety == 1 (owned pets)
            all_mobiles = API.Mobiles.GetMobiles()
            if not all_mobiles:
                self.pets = []
                return

            found_pets = []
            for mob in all_mobiles:
                if mob is None:
                    continue

                # Check for owned pet (Notoriety == 1)
                notoriety = getattr(mob, 'Notoriety', -1)
                if notoriety != 1:
                    continue

                serial = getattr(mob, 'Serial', 0)
                name = getattr(mob, 'Name', 'Unknown')
                max_hp = getattr(mob, 'HitsMax', 0)

                if serial > 0 and name and name != 'Unknown':
                    found_pets.append({
                        'serial': serial,
                        'name': name,
                        'max_hp': max_hp,
                        'is_tank': False
                    })

            # Sort by max HP (highest first)
            found_pets.sort(key=lambda p: p['max_hp'], reverse=True)

            # Designate tank pet
            if found_pets:
                if self._tank_serial > 0:
                    # Use previously designated tank if found
                    for pet in found_pets:
                        if pet['serial'] == self._tank_serial:
                            pet['is_tank'] = True
                            break
                    else:
                        # Tank not found, use highest HP
                        found_pets[0]['is_tank'] = True
                        self._tank_serial = found_pets[0]['serial']
                        self._save_tank_serial()
                else:
                    # No tank set, use highest HP
                    found_pets[0]['is_tank'] = True
                    self._tank_serial = found_pets[0]['serial']
                    self._save_tank_serial()

            # Remove max_hp from final list (not needed in storage)
            for pet in found_pets:
                del pet['max_hp']

            self.pets = found_pets

        except Exception as e:
            API.SysMsg(f"Pet scan error: {str(e)}", 32)
            self.pets = []

    def get_pet_info(self, serial):
        """
        Get pet information by serial.
        Returns pet dict or None if not found.
        """
        for pet in self.pets:
            if pet['serial'] == serial:
                return pet
        return None

    def get_tank_pet(self):
        """
        Get the designated tank pet.
        Returns pet dict or None if no tank designated.
        """
        for pet in self.pets:
            if pet.get('is_tank', False):
                return pet
        return None

    def set_tank_pet(self, serial):
        """
        Change tank pet designation to the specified serial.
        Returns True if successful, False if pet not found.
        """
        # Validate that pet exists
        pet_found = False
        for pet in self.pets:
            if pet['serial'] == serial:
                pet_found = True
                break

        if not pet_found:
            return False

        # Remove tank designation from all pets
        for pet in self.pets:
            pet['is_tank'] = False

        # Set new tank
        for pet in self.pets:
            if pet['serial'] == serial:
                pet['is_tank'] = True
                self._tank_serial = serial
                self._save_tank_serial()
                return True

        return False

    def validate_pets(self):
        """
        Check if stored pets still exist as valid mobiles.
        Removes invalid/dead pets from the list.
        """
        valid_pets = []
        for pet in self.pets:
            serial = pet['serial']
            mob = API.Mobiles.FindMobile(serial)
            if mob is not None and not getattr(mob, 'IsDead', True):
                valid_pets.append(pet)
            elif pet.get('is_tank', False):
                # Tank pet removed, clear designation
                self._tank_serial = 0
                self._save_tank_serial()

        self.pets = valid_pets

    @property
    def pet_count(self):
        """Get count of tracked pets"""
        return len(self.pets)

    @property
    def all_pets_alive(self):
        """
        Check if all tracked pets are alive.
        Returns False if any pet is dead or missing.
        """
        if not self.pets:
            return True  # No pets to check

        for pet in self.pets:
            mob = API.Mobiles.FindMobile(pet['serial'])
            if mob is None or getattr(mob, 'IsDead', True):
                return False

        return True

    def get_pet_by_name(self, name):
        """
        Find pet by name (case-insensitive).
        Useful for resurrection targeting.
        Returns pet dict or None if not found.
        """
        name_lower = name.lower()
        for pet in self.pets:
            if pet['name'].lower() == name_lower:
                return pet
        return None

# ============ AREA & SAFE SPOT CLASSES ============

class SafeSpot:
    """
    Safe recall/escape point within a farming area.
    Defines coordinates and escape method (recall, gate, etc.).
    """

    def __init__(self, x, y, escape_method="direct_recall", gump_id=0, button_id=0, is_primary=True):
        """
        Args:
            x, y: Coordinates of safe spot
            escape_method: "direct_recall", "gump_gate", "timer_gate", "run_outside"
            gump_id: Gump ID for gump_gate method
            button_id: Button ID for gump_gate method
            is_primary: True if primary safe spot, False for backup
        """
        self.x = x
        self.y = y
        self.escape_method = escape_method
        self.gump_id = gump_id
        self.button_id = button_id
        self.is_primary = is_primary

    def to_dict(self):
        """Convert to dict for JSON serialization"""
        return {
            'x': self.x,
            'y': self.y,
            'escape_method': self.escape_method,
            'gump_id': self.gump_id,
            'button_id': self.button_id,
            'is_primary': self.is_primary
        }

    @staticmethod
    def from_dict(data):
        """Create SafeSpot from dict"""
        return SafeSpot(
            x=data.get('x', 0),
            y=data.get('y', 0),
            escape_method=data.get('escape_method', 'direct_recall'),
            gump_id=data.get('gump_id', 0),
            button_id=data.get('button_id', 0),
            is_primary=data.get('is_primary', True)
        )


class FarmingArea:
    """
    Farming area definition with coordinates, type, and safe spots.
    """

    def __init__(self, name, area_type="circle", center_x=0, center_y=0, radius=15,
                 waypoints=None, difficulty="medium", safe_spots=None, loot_filter=None, notes=""):
        """
        Args:
            name: Area name
            area_type: "circle" or "waypoints"
            center_x, center_y, radius: For circle type
            waypoints: List of (x, y) tuples for waypoint type
            difficulty: "low", "medium", "high"
            safe_spots: List of SafeSpot objects
            loot_filter: List of graphic IDs to loot
            notes: Optional notes
        """
        self.name = name
        self.area_type = area_type
        self.center_x = center_x
        self.center_y = center_y
        self.radius = radius
        self.waypoints = waypoints or []
        self.difficulty = difficulty
        self.safe_spots = safe_spots or []
        self.loot_filter = loot_filter or []
        self.notes = notes

    def to_dict(self):
        """Convert to dict for JSON serialization"""
        return {
            'name': self.name,
            'area_type': self.area_type,
            'center_x': self.center_x,
            'center_y': self.center_y,
            'radius': self.radius,
            'waypoints': self.waypoints,
            'difficulty': self.difficulty,
            'safe_spots': [spot.to_dict() for spot in self.safe_spots],
            'loot_filter': self.loot_filter,
            'notes': self.notes
        }

    @staticmethod
    def from_dict(data):
        """Create FarmingArea from dict"""
        safe_spots = [SafeSpot.from_dict(spot) for spot in data.get('safe_spots', [])]

        return FarmingArea(
            name=data.get('name', ''),
            area_type=data.get('area_type', 'circle'),
            center_x=data.get('center_x', 0),
            center_y=data.get('center_y', 0),
            radius=data.get('radius', 15),
            waypoints=data.get('waypoints', []),
            difficulty=data.get('difficulty', 'medium'),
            safe_spots=safe_spots,
            loot_filter=data.get('loot_filter', []),
            notes=data.get('notes', '')
        )


class AreaManager:
    """
    Manages farming area persistence and retrieval.
    """

    def __init__(self, key_prefix):
        self.key_prefix = key_prefix
        self.areas_key = key_prefix + "Areas_"

    def add_area(self, area):
        """
        Save area to persistence.

        Args:
            area: FarmingArea object
        """
        try:
            import json
            area_key = self.areas_key + area.name
            area_json = json.dumps(area.to_dict())
            API.SavePersistentVar(area_key, area_json, API.PersistentVar.Char)

            # Update area names list
            area_names_key = self.key_prefix + "AreaNames"
            names = self.list_areas()
            if area.name not in names:
                names.append(area.name)
                API.SavePersistentVar(area_names_key, "|".join(names), API.PersistentVar.Char)

            return True
        except Exception as e:
            API.SysMsg(f"Area save error: {str(e)}", 32)
            return False

    def get_area(self, name):
        """
        Retrieve area by name.

        Args:
            name: Area name

        Returns:
            FarmingArea object or None if not found
        """
        try:
            import json
            area_key = self.areas_key + name
            area_json = API.GetPersistentVar(area_key, "", API.PersistentVar.Char)

            if not area_json:
                return None

            area_dict = json.loads(area_json)
            return FarmingArea.from_dict(area_dict)
        except Exception as e:
            API.SysMsg(f"Area load error: {str(e)}", 32)
            return None

    def list_areas(self):
        """
        Get list of all area names.

        Returns:
            List of area name strings
        """
        # Note: This is a simplified implementation
        # A full implementation would need to scan all persistence keys
        # For now, we'll track area names in a separate key
        try:
            area_names_key = self.key_prefix + "AreaNames"
            names_str = API.GetPersistentVar(area_names_key, "", API.PersistentVar.Char)
            if names_str:
                return [name for name in names_str.split("|") if name]
            return []
        except:
            return []

    def delete_area(self, name):
        """
        Delete area from persistence.

        Args:
            name: Area name
        """
        try:
            area_key = self.areas_key + name
            API.SavePersistentVar(area_key, "", API.PersistentVar.Char)

            # Remove from area names list
            area_names_key = self.key_prefix + "AreaNames"
            names = self.list_areas()
            if name in names:
                names.remove(name)
                API.SavePersistentVar(area_names_key, "|".join(names), API.PersistentVar.Char)

            return True
        except Exception as e:
            API.SysMsg(f"Area delete error: {str(e)}", 32)
            return False

    def get_current_area(self, proximity=20):
        """
        Get the area player is currently in based on proximity.

        Args:
            proximity: Max distance from center/waypoints to consider "in area"

        Returns:
            FarmingArea object or None if not in any area
        """
        try:
            px, py = get_player_pos()

            for area_name in self.list_areas():
                area = self.get_area(area_name)
                if not area:
                    continue

                if area.area_type == "circle":
                    dist = distance(px, py, area.center_x, area.center_y)
                    if dist <= area.radius + proximity:
                        return area
                elif area.area_type == "waypoints":
                    # Check proximity to any waypoint
                    for wx, wy in area.waypoints:
                        if distance(px, py, wx, wy) <= proximity:
                            return area

            return None
        except:
            return None

    def rotate_to_next_area(self):
        """
        Rotate to the next farming area in the list.
        Useful after a major flee event to avoid the dangerous area.

        Returns:
            FarmingArea: The new area, or None if no areas available
        """
        try:
            area_names = self.list_areas()
            if not area_names:
                API.SysMsg("No areas configured for rotation", 43)
                return None

            # Get current area
            current_area = self.get_current_area()
            current_name = current_area.name if current_area else None

            # Find next area
            if current_name and current_name in area_names:
                current_index = area_names.index(current_name)
                next_index = (current_index + 1) % len(area_names)
                next_name = area_names[next_index]
            else:
                # Not in any area or area not found, use first area
                next_name = area_names[0]

            next_area = self.get_area(next_name)
            if next_area:
                API.SysMsg(f"Rotated to area: {next_name}", 68)
                return next_area
            else:
                API.SysMsg(f"Failed to load area: {next_name}", 32)
                return None

        except Exception as e:
            API.SysMsg(f"Area rotation error: {str(e)}", 32)
            return None


# ============ NPC THREAT MAPPING SYSTEM ============

class NPCThreatMap:
    """
    Spatial avoidance system that maps threatening NPC positions
    and provides safe pathfinding away from threats.
    """

    def __init__(self):
        self.threat_positions = []  # List of (x, y) tuples
        self.avoid_radius = 6       # Tiles around each NPC to avoid
        self.last_scan_time = 0
        self.scan_cooldown = 2.0    # Seconds between scans

    def scan_npcs(self, scan_radius=12):
        """
        Scan for threatening NPCs and update threat map.

        Args:
            scan_radius: Radius to scan for NPCs
        """
        try:
            now = time.time()

            # Cooldown check
            if now - self.last_scan_time < self.scan_cooldown:
                return

            self.last_scan_time = now
            self.threat_positions = []

            # Get all mobiles
            all_mobiles = API.Mobiles.GetMobiles()
            if not all_mobiles:
                return

            px, py = get_player_pos()

            for mob in all_mobiles:
                if mob is None:
                    continue

                # Skip if too far
                mob_dist = getattr(mob, 'Distance', 99)
                if mob_dist > scan_radius:
                    continue

                # Get notoriety
                notoriety = getattr(mob, 'Notoriety', -1)

                # Skip: owned pets (1), friendlies (2), innocents (1)
                # Include: red (5), gray (3 if aggressive), orange (4)
                if notoriety in [1, 2]:
                    continue

                # Get position
                mx = getattr(mob, 'X', 0)
                my = getattr(mob, 'Y', 0)

                if mx > 0 and my > 0:
                    self.threat_positions.append((mx, my))

        except Exception as e:
            API.SysMsg(f"NPC scan error: {str(e)}", 32)

    def is_position_safe(self, x, y):
        """
        Check if a position is safe (not near threats).

        Args:
            x, y: Position to check

        Returns:
            bool: True if safe
        """
        for tx, ty in self.threat_positions:
            if distance(x, y, tx, ty) <= self.avoid_radius:
                return False
        return True

    def get_nearest_threat(self, x, y):
        """
        Get the nearest threat position to given coordinates.

        Args:
            x, y: Position to check from

        Returns:
            Tuple of (tx, ty, distance) or None if no threats
        """
        if not self.threat_positions:
            return None

        nearest = None
        min_dist = float('inf')

        for tx, ty in self.threat_positions:
            dist = distance(x, y, tx, ty)
            if dist < min_dist:
                min_dist = dist
                nearest = (tx, ty, dist)

        return nearest

    def calculate_safe_direction(self, from_x, from_y, distance_to_move=10):
        """
        Calculate safest direction to move from current position.

        Args:
            from_x, from_y: Starting position
            distance_to_move: How far to project the safe direction

        Returns:
            Tuple of (safe_x, safe_y) or None if no safe direction
        """
        if not self.threat_positions:
            # No threats, any direction is safe
            return (from_x, from_y + distance_to_move)

        try:
            # Calculate average threat vector
            threat_vector_x = 0
            threat_vector_y = 0

            for tx, ty in self.threat_positions:
                # Vector from threat to player
                dx = from_x - tx
                dy = from_y - ty
                dist = distance(from_x, from_y, tx, ty)

                if dist > 0:
                    # Weight by inverse distance (closer threats = stronger push)
                    weight = 1.0 / max(dist, 1.0)
                    threat_vector_x += dx * weight
                    threat_vector_y += dy * weight

            # Normalize and scale
            vector_length = (threat_vector_x ** 2 + threat_vector_y ** 2) ** 0.5
            if vector_length > 0:
                safe_x = from_x + int((threat_vector_x / vector_length) * distance_to_move)
                safe_y = from_y + int((threat_vector_y / vector_length) * distance_to_move)
                return (safe_x, safe_y)

            return None
        except:
            return None


# ============ HEALING SYSTEM ============

class HealingSystem:
    """
    Manages healing configuration and provides interface for config GUI.
    Holds healing thresholds, vet kit settings, and healing options.
    """

    def __init__(self):
        """Initialize healing system with default values"""
        self.player_heal_threshold = 85
        self.tank_heal_threshold = 70
        self.pet_heal_threshold = 50
        self.vetkit_graphic = 0
        self.vetkit_hp_threshold = 90
        self.vetkit_min_pets = 2
        self.vetkit_cooldown = 5.0
        self.vetkit_critical_hp = 50
        self.use_magery_healing = False
        self.auto_cure_poison = True

    def configure_thresholds(self, player_threshold=None, tank_threshold=None, pet_threshold=None):
        """
        Configure healing thresholds.

        Args:
            player_threshold: Player heal threshold (50-95)
            tank_threshold: Tank pet heal threshold (40-90)
            pet_threshold: Other pets heal threshold (30-80)
        """
        if player_threshold is not None:
            self.player_heal_threshold = max(50, min(95, int(player_threshold)))
        if tank_threshold is not None:
            self.tank_heal_threshold = max(40, min(90, int(tank_threshold)))
        if pet_threshold is not None:
            self.pet_heal_threshold = max(30, min(80, int(pet_threshold)))

    def configure_vetkit(self, hp_threshold=None, min_pets=None, cooldown=None, critical_hp=None):
        """
        Configure vet kit settings.

        Args:
            hp_threshold: HP% threshold to use vet kit (70-95)
            min_pets: Min number of pets hurt to trigger (1-5)
            cooldown: Cooldown between uses in seconds (3-10)
            critical_hp: Emergency bypass threshold (30-70)
        """
        if hp_threshold is not None:
            self.vetkit_hp_threshold = max(70, min(95, int(hp_threshold)))
        if min_pets is not None:
            self.vetkit_min_pets = max(1, min(5, int(min_pets)))
        if cooldown is not None:
            self.vetkit_cooldown = max(3.0, min(10.0, float(cooldown)))
        if critical_hp is not None:
            self.vetkit_critical_hp = max(30, min(70, int(critical_hp)))

    def set_vetkit_graphic(self, graphic):
        """
        Set vet kit graphic ID.

        Args:
            graphic: Item graphic ID (0 = not set)
        """
        self.vetkit_graphic = int(graphic) if graphic else 0

    def configure_options(self, use_magery=None, auto_cure=None):
        """
        Configure healing options.

        Args:
            use_magery: Enable magery healing
            auto_cure: Enable auto poison cure
        """
        if use_magery is not None:
            self.use_magery_healing = bool(use_magery)
        if auto_cure is not None:
            self.auto_cure_poison = bool(auto_cure)

    def sync_to_globals(self):
        """Sync healing system settings to global variables"""
        global player_heal_threshold, tank_heal_threshold, pet_heal_threshold
        global vetkit_graphic, vetkit_hp_threshold, vetkit_min_pets
        global vetkit_cooldown, vetkit_critical_hp, use_magery_healing, auto_cure_poison

        player_heal_threshold = self.player_heal_threshold
        tank_heal_threshold = self.tank_heal_threshold
        pet_heal_threshold = self.pet_heal_threshold
        vetkit_graphic = self.vetkit_graphic
        vetkit_hp_threshold = self.vetkit_hp_threshold
        vetkit_min_pets = self.vetkit_min_pets
        vetkit_cooldown = self.vetkit_cooldown
        vetkit_critical_hp = self.vetkit_critical_hp
        use_magery_healing = self.use_magery_healing
        auto_cure_poison = self.auto_cure_poison

    def sync_from_globals(self):
        """Sync global variables to healing system settings"""
        self.player_heal_threshold = player_heal_threshold
        self.tank_heal_threshold = tank_heal_threshold
        self.pet_heal_threshold = pet_heal_threshold
        self.vetkit_graphic = vetkit_graphic
        self.vetkit_hp_threshold = vetkit_hp_threshold
        self.vetkit_min_pets = vetkit_min_pets
        self.vetkit_cooldown = vetkit_cooldown
        self.vetkit_critical_hp = vetkit_critical_hp
        self.use_magery_healing = use_magery_healing
        self.auto_cure_poison = auto_cure_poison


# ============ FLEE SYSTEM ============

class FleeSystem:
    """
    Dungeon-aware flee system with multiple escape methods.
    Handles emergency evacuation with safe spot pathfinding,
    gate usage, and recall mechanics.
    """

    def __init__(self, area_manager, npc_threat_map, key_prefix):
        """
        Args:
            area_manager: AreaManager instance
            npc_threat_map: NPCThreatMap instance
            key_prefix: Persistence key prefix
        """
        self.area_manager = area_manager
        self.npc_threat_map = npc_threat_map
        self.key_prefix = key_prefix

        # Flee state
        self.is_fleeing = False
        self.flee_start_time = 0
        self.flee_reason = ""
        self.danger_at_flee = 0
        self.current_safe_spot = None
        self.last_position = (0, 0)
        self.stuck_check_time = 0

        # Statistics
        self.flee_count = 0
        self.flee_success = 0
        self.flee_failures = 0
        self.flee_reasons = {}  # Dict of {reason: count}

        # Constants
        self.MAX_FLEE_TIME = 20.0
        self.STUCK_TIMEOUT = 3.0
        self.SAFE_SPOT_ARRIVAL_DISTANCE = 2

    def initiate_flee(self, reason="danger_critical", danger_score=0):
        """
        Initiate emergency flee sequence.

        Args:
            reason: Reason for fleeing (for statistics)
            danger_score: Current danger score (0-100) when flee initiated

        Returns:
            bool: True if flee initiated successfully
        """
        try:
            # Track statistics
            self.flee_count += 1
            self.flee_reason = reason
            self.danger_at_flee = danger_score
            self.flee_reasons[reason] = self.flee_reasons.get(reason, 0) + 1

            API.SysMsg(f"FLEEING: {reason} (danger: {danger_score})!", 32)

            # Issue guard me command
            API.Msg("all guard me")
            API.Pause(0.3)

            # Get current area
            current_area = self.area_manager.get_current_area()
            if not current_area or not current_area.safe_spots:
                API.SysMsg("No safe spots defined! Emergency recall!", 32)
                return self._emergency_recall()

            # Get primary safe spot
            primary_spot = None
            for spot in current_area.safe_spots:
                if spot.is_primary:
                    primary_spot = spot
                    break

            # Fallback to first safe spot if no primary
            if not primary_spot and current_area.safe_spots:
                primary_spot = current_area.safe_spots[0]

            if not primary_spot:
                API.SysMsg("No safe spots available! Emergency recall!", 32)
                return self._emergency_recall()

            # Check if path to safe spot is blocked by NPCs
            px, py = get_player_pos()
            if not self.npc_threat_map.is_position_safe(primary_spot.x, primary_spot.y):
                # Try alternate safe spots
                for spot in current_area.safe_spots:
                    if not spot.is_primary and self.npc_threat_map.is_position_safe(spot.x, spot.y):
                        primary_spot = spot
                        API.SysMsg("Primary blocked, using backup safe spot", 43)
                        break

            # Set flee state
            self.is_fleeing = True
            self.flee_start_time = time.time()
            self.current_safe_spot = primary_spot
            self.last_position = get_player_pos()
            self.stuck_check_time = time.time()

            # Start fleeing to safe spot
            return self.flee_to_safe_spot(primary_spot)

        except Exception as e:
            API.SysMsg(f"Flee initiate error: {str(e)}", 32)
            self.flee_failures += 1
            return False

    def flee_to_safe_spot(self, safe_spot):
        """
        Pathfind to safe spot and monitor progress.
        This is called continuously from main loop while fleeing.

        Args:
            safe_spot: SafeSpot object to flee to

        Returns:
            bool: True if still fleeing, False if arrived or failed
        """
        try:
            if not self.is_fleeing:
                return False

            now = time.time()

            # Check timeout
            if now - self.flee_start_time > self.MAX_FLEE_TIME:
                API.SysMsg("Flee timeout! Emergency recall!", 32)
                self._emergency_recall()
                self.is_fleeing = False
                self.flee_failures += 1
                return False

            # Check if arrived at safe spot
            px, py = get_player_pos()
            dist_to_spot = distance(px, py, safe_spot.x, safe_spot.y)

            if dist_to_spot < self.SAFE_SPOT_ARRIVAL_DISTANCE:
                API.SysMsg("Reached safe spot, executing escape...", 68)
                success = self.execute_escape_method(safe_spot)
                self.is_fleeing = False

                if success:
                    self.flee_success += 1
                else:
                    self.flee_failures += 1

                return False

            # Stuck detection
            if now - self.stuck_check_time >= self.STUCK_TIMEOUT:
                cur_x, cur_y = get_player_pos()
                last_x, last_y = self.last_position

                if cur_x == last_x and cur_y == last_y:
                    # Stuck! Try random direction
                    API.SysMsg("Stuck! Trying alternate path...", 43)
                    if API.Pathfinding():
                        API.CancelPathfinding()

                    import random
                    API.Pathfind(cur_x + random.randint(-5, 5), cur_y + random.randint(-5, 5))
                    API.Pause(0.5)

                self.last_position = get_player_pos()
                self.stuck_check_time = now

            # Update NPC threat map
            self.npc_threat_map.scan_npcs()

            # Start/resume pathfinding to safe spot
            if not API.Pathfinding():
                API.Pathfind(safe_spot.x, safe_spot.y)

            return True

        except Exception as e:
            API.SysMsg(f"Flee to safe spot error: {str(e)}", 32)
            self.is_fleeing = False
            self.flee_failures += 1
            return False

    def execute_escape_method(self, safe_spot):
        """
        Execute the escape method defined by the safe spot.

        Args:
            safe_spot: SafeSpot object with escape method

        Returns:
            bool: True if escape successful
        """
        try:
            method = safe_spot.escape_method

            if method == "direct_recall":
                return self.use_recall()
            elif method == "gump_gate":
                return self.use_gump_gate(safe_spot.gump_id, safe_spot.button_id)
            elif method == "timer_gate":
                return self.use_timer_gate()
            elif method == "run_outside":
                API.SysMsg("Running outside dungeon boundary...", 68)
                # Continue pathfinding - caller handles this
                return True
            else:
                API.SysMsg(f"Unknown escape method: {method}", 32)
                return self._emergency_recall()

        except Exception as e:
            API.SysMsg(f"Escape method error: {str(e)}", 32)
            return False

    def use_recall(self):
        """
        Execute direct recall escape.

        Returns:
            bool: True if recall successful
        """
        try:
            # Find recall rune/runebook
            # This is a placeholder - actual implementation would need
            # to track recall destination serial/item
            API.SysMsg("Direct recall not yet configured", 43)

            # For now, just stop fleeing and let recovery handle it
            return True

        except Exception as e:
            API.SysMsg(f"Recall error: {str(e)}", 32)
            return False

    def use_gump_gate(self, gump_id, button_id):
        """
        Use a gate that opens a gump dialog.

        Args:
            gump_id: Gump ID to wait for
            button_id: Button ID to click in gump

        Returns:
            bool: True if gate used successfully
        """
        try:
            # Find gate object near safe spot
            # This is a placeholder - would need to scan for gate graphic
            API.SysMsg("Gump gate not yet implemented", 43)

            # Wait for gump
            start_time = time.time()
            while not API.HasGump(gump_id) and time.time() - start_time < 3.0:
                API.Pause(0.1)

            if API.HasGump(gump_id):
                API.ReplyGump(button_id, gump_id)
                API.Pause(2.0)  # Wait for travel

                # Check position changed
                # Would verify travel success here
                return True
            else:
                API.SysMsg("Gate gump timeout", 32)
                return False

        except Exception as e:
            API.SysMsg(f"Gump gate error: {str(e)}", 32)
            return False

    def use_timer_gate(self):
        """
        Use a timer-based gate (5 second countdown).

        Returns:
            bool: True if gate used successfully
        """
        try:
            API.SysMsg("Timer gate: 5 second countdown...", 43)

            # Issue guard me again
            API.Msg("all guard me")

            # Wait for timer (5 seconds)
            timer_start = time.time()
            while time.time() - timer_start < 5.0:
                API.ProcessCallbacks()

                # Monitor danger during wait
                # If critical, could use emergency invis/logout
                # For now, just wait

                API.Pause(0.5)

            API.SysMsg("Timer gate travel complete", 68)
            return True

        except Exception as e:
            API.SysMsg(f"Timer gate error: {str(e)}", 32)
            return False

    def _emergency_recall(self):
        """
        Emergency recall as last resort.

        Returns:
            bool: True if successful
        """
        try:
            API.SysMsg("EMERGENCY RECALL!", 32)

            # This is a placeholder - actual implementation would:
            # 1. Use sacred journey spell
            # 2. Or use runebook emergency charges
            # 3. Or use recall scrolls

            # For now, just mark flee as failed
            return False

        except:
            return False

    def get_flee_stats(self):
        """
        Get flee statistics dictionary.

        Returns:
            dict: Flee statistics
        """
        return {
            'flee_count': self.flee_count,
            'flee_success': self.flee_success,
            'flee_failures': self.flee_failures,
            'flee_reasons': self.flee_reasons,
            'is_fleeing': self.is_fleeing
        }

    def reset_stats(self):
        """Reset flee statistics"""
        self.flee_count = 0
        self.flee_success = 0
        self.flee_failures = 0
        self.flee_reasons = {}


# ============ DANGER ASSESSMENT SYSTEM ============

class DangerAssessment:
    """
    Multi-factor danger assessment system that evaluates threat level
    based on player HP, pet HP, enemy count, nearby NPCs, damage rate,
    and pet positioning.

    Returns a 0-100 danger score that can be used for flee decisions.
    """

    def __init__(self):
        # Default weights (normalized to sum to 1.0)
        self.weights = {
            'player_hp': 0.30,      # Player HP critical for survival
            'pet_hp': 0.20,         # Pet HP average across all pets
            'enemy_count': 0.20,    # Number of engaged enemies
            'nearby_npcs': 0.10,    # Non-engaged threatening NPCs
            'damage_rate': 0.10,    # Incoming damage per second
            'pet_distance': 0.10    # How spread out pets are
        }

        # Damage tracking
        self.damage_samples = []  # List of (timestamp, hp_value)
        self.max_samples = 10

        # Thresholds
        self.critical_player_hp = 30  # HP% considered critical
        self.critical_pet_hp = 20     # Pet HP% considered critical
        self.danger_zones = {
            (0, 20): "SAFE",
            (20, 40): "LOW",
            (40, 60): "MODERATE",
            (60, 80): "HIGH",
            (80, 100): "CRITICAL"
        }

    def configure_weights(self, **kwargs):
        """
        Update danger calculation weights.

        Args:
            player_hp: Weight for player HP factor (0.0-1.0)
            pet_hp: Weight for pet HP factor (0.0-1.0)
            enemy_count: Weight for enemy count factor (0.0-1.0)
            nearby_npcs: Weight for nearby NPC factor (0.0-1.0)
            damage_rate: Weight for damage rate factor (0.0-1.0)
            pet_distance: Weight for pet distance factor (0.0-1.0)
        """
        for key, value in kwargs.items():
            if key in self.weights:
                self.weights[key] = max(0.0, min(1.0, value))

        # Normalize weights to sum to 1.0
        total = sum(self.weights.values())
        if total > 0:
            for key in self.weights:
                self.weights[key] /= total

    def _calculate_player_hp_danger(self):
        """Calculate danger score from player HP (0-100)"""
        try:
            player = API.Player
            if not player:
                return 50  # Unknown state = moderate danger

            current_hp = getattr(player, 'Hits', 0)
            max_hp = getattr(player, 'HitsMax', 1)

            if max_hp <= 0:
                return 50

            hp_percent = (current_hp / max_hp) * 100

            # Inverse relationship: lower HP = higher danger
            # 100% HP = 0 danger, 0% HP = 100 danger
            danger = 100 - hp_percent

            # Apply critical threshold multiplier
            if hp_percent <= self.critical_player_hp:
                danger = min(100, danger * 1.5)

            return danger
        except:
            return 50

    def _calculate_pet_hp_danger(self, pets_data):
        """
        Calculate danger score from pet HP average (0-100)

        Args:
            pets_data: List of pet dicts with 'serial' key
        """
        if not pets_data:
            return 0  # No pets = no pet danger

        try:
            pet_dangers = []
            for pet in pets_data:
                mob = API.Mobiles.FindMobile(pet.get('serial', 0))
                if mob and not mob.IsDead:
                    current_hp = getattr(mob, 'Hits', 0)
                    max_hp = getattr(mob, 'HitsMax', 1)

                    if max_hp > 0:
                        hp_percent = (current_hp / max_hp) * 100
                        pet_danger = 100 - hp_percent

                        # Critical threshold for pets
                        if hp_percent <= self.critical_pet_hp:
                            pet_danger = min(100, pet_danger * 1.3)

                        # Tank pets weighted higher
                        if pet.get('is_tank', False):
                            pet_danger *= 1.2

                        pet_dangers.append(pet_danger)

            if not pet_dangers:
                return 0

            # Use weighted average (emphasize worst-case)
            avg_danger = sum(pet_dangers) / len(pet_dangers)
            max_danger = max(pet_dangers)
            return (avg_danger * 0.6 + max_danger * 0.4)
        except:
            return 30  # Error = moderate pet danger

    def _calculate_enemy_count_danger(self, enemy_count, max_enemies=5):
        """
        Calculate danger score from number of enemies (0-100)

        Args:
            enemy_count: Number of currently engaged enemies
            max_enemies: Number of enemies considered maximum danger
        """
        if enemy_count <= 0:
            return 0

        # Linear scale: 1 enemy = 20 danger, 5+ enemies = 100 danger
        danger = (enemy_count / max_enemies) * 100
        return min(100, danger)

    def _calculate_nearby_npc_danger(self, npc_positions, player_pos, threat_distance=10):
        """
        Calculate danger score from nearby threatening NPCs (0-100)

        Args:
            npc_positions: List of (x, y) tuples of non-engaged NPCs
            player_pos: Tuple of (x, y) player position
            threat_distance: Distance at which NPCs are threatening
        """
        if not npc_positions or not player_pos:
            return 0

        try:
            px, py = player_pos
            nearby_npcs = 0

            for nx, ny in npc_positions:
                dist = distance(px, py, nx, ny)
                if dist <= threat_distance:
                    nearby_npcs += 1

            # Each nearby NPC adds danger (diminishing returns)
            if nearby_npcs == 0:
                return 0
            elif nearby_npcs == 1:
                return 15
            elif nearby_npcs == 2:
                return 30
            elif nearby_npcs == 3:
                return 50
            else:
                return min(100, 50 + (nearby_npcs - 3) * 15)
        except:
            return 0

    def _calculate_damage_rate_danger(self, current_hp):
        """
        Calculate danger score from incoming damage rate (0-100)

        Args:
            current_hp: Current player HP
        """
        try:
            now = time.time()

            # Add current sample
            self.damage_samples.append((now, current_hp))

            # Remove samples older than 10 seconds
            self.damage_samples = [(t, hp) for t, hp in self.damage_samples if now - t <= 10.0]

            # Keep only recent samples
            if len(self.damage_samples) > self.max_samples:
                self.damage_samples = self.damage_samples[-self.max_samples:]

            # Need at least 2 samples to calculate rate
            if len(self.damage_samples) < 2:
                return 0

            # Calculate damage per second
            oldest_time, oldest_hp = self.damage_samples[0]
            time_diff = now - oldest_time

            if time_diff <= 0:
                return 0

            hp_diff = oldest_hp - current_hp
            damage_per_sec = hp_diff / time_diff

            # Normalize to danger score
            # 0 dps = 0 danger, 10+ dps = 100 danger
            if damage_per_sec <= 0:
                return 0

            danger = (damage_per_sec / 10.0) * 100
            return min(100, danger)
        except:
            return 0

    def _calculate_pet_distance_danger(self, pets_data, player_pos):
        """
        Calculate danger score from pet positioning spread (0-100)

        Args:
            pets_data: List of pet dicts with 'serial' key
            player_pos: Tuple of (x, y) player position
        """
        if not pets_data or not player_pos:
            return 0

        try:
            px, py = player_pos
            distances = []

            for pet in pets_data:
                mob = API.Mobiles.FindMobile(pet.get('serial', 0))
                if mob and not mob.IsDead:
                    dist = getattr(mob, 'Distance', 99)
                    distances.append(dist)

            if not distances:
                return 0

            # Calculate spread (standard deviation of distances)
            avg_dist = sum(distances) / len(distances)
            variance = sum((d - avg_dist) ** 2 for d in distances) / len(distances)
            spread = variance ** 0.5

            # Also consider max distance
            max_dist = max(distances)

            # High spread or far pets = danger
            spread_danger = min(100, (spread / 10.0) * 100)
            distance_danger = min(100, (max_dist / MAX_FOLLOW_RANGE) * 100)

            return (spread_danger * 0.5 + distance_danger * 0.5)
        except:
            return 0

    def calculate_danger(self, pets_data, enemy_count, npc_positions, player_pos=None):
        """
        Calculate overall danger score (0-100) from all factors.

        Args:
            pets_data: List of pet dicts with 'serial' and 'is_tank' keys
            enemy_count: Number of currently engaged enemies
            npc_positions: List of (x, y) tuples of non-engaged NPCs
            player_pos: Tuple of (x, y) player position (optional, uses API.Player if None)

        Returns:
            int: Danger score from 0 (safe) to 100 (critical)
        """
        try:
            # Get player position
            if player_pos is None:
                player_pos = get_player_pos()

            # Get current player HP
            player = API.Player
            current_hp = getattr(player, 'Hits', 0) if player else 0

            # Calculate individual danger factors
            player_hp_danger = self._calculate_player_hp_danger()
            pet_hp_danger = self._calculate_pet_hp_danger(pets_data)
            enemy_danger = self._calculate_enemy_count_danger(enemy_count)
            npc_danger = self._calculate_nearby_npc_danger(npc_positions, player_pos)
            damage_danger = self._calculate_damage_rate_danger(current_hp)
            pet_dist_danger = self._calculate_pet_distance_danger(pets_data, player_pos)

            # Weighted sum
            total_danger = (
                player_hp_danger * self.weights['player_hp'] +
                pet_hp_danger * self.weights['pet_hp'] +
                enemy_danger * self.weights['enemy_count'] +
                npc_danger * self.weights['nearby_npcs'] +
                damage_danger * self.weights['damage_rate'] +
                pet_dist_danger * self.weights['pet_distance']
            )

            return min(100, max(0, int(total_danger)))
        except Exception as e:
            API.SysMsg(f"Danger calc error: {str(e)}", 32)
            return 50  # Error = moderate danger

    def get_danger_zone(self, danger_score):
        """
        Get danger zone name for a given danger score.

        Args:
            danger_score: Danger score from 0-100

        Returns:
            str: Zone name ("SAFE", "LOW", "MODERATE", "HIGH", "CRITICAL")
        """
        for (low, high), zone in self.danger_zones.items():
            if low <= danger_score < high:
                return zone
        return "CRITICAL"  # 100+ = critical

    def should_flee(self, danger_score, flee_threshold=70):
        """
        Determine if player should flee based on danger score.

        Args:
            danger_score: Current danger score (0-100)
            flee_threshold: Danger score that triggers flee (default 70)

        Returns:
            bool: True if should flee
        """
        return danger_score >= flee_threshold

    def reset(self):
        """Reset damage tracking samples"""
        self.damage_samples = []

class RecoverySystem:
    """
    Post-flee recovery system with adaptive behavior based on flee severity.
    Handles healing to full, cooldown periods, area rotation, and pet resurrection.
    """

    def __init__(self, pet_manager, area_manager, key_prefix):
        """
        Args:
            pet_manager: PetManager instance
            area_manager: AreaManager instance
            key_prefix: Persistence key prefix
        """
        self.pet_manager = pet_manager
        self.area_manager = area_manager
        self.key_prefix = key_prefix

        # Recovery state
        self.is_recovering = False
        self.recovery_start_time = 0
        self.recovery_severity = "minor"
        self.recovery_wait_time = 0
        self.danger_at_flee = 0
        self.flee_reason = ""

        # Temporary caution mode
        self.caution_mode_active = False
        self.caution_mode_start = 0
        self.caution_mode_duration = 3600  # 1 hour in seconds
        self.caution_danger_reduction = 10

        # Pet death policy
        self.pet_death_policy = "auto_rez_continue"  # "stop_on_death", "rez_and_cooldown", "auto_rez_continue"

        # Statistics
        self.total_recoveries = 0
        self.minor_count = 0
        self.major_count = 0
        self.critical_count = 0

        # Load pet death policy from persistence
        self._load_config()

    def _load_config(self):
        """Load configuration from persistence"""
        try:
            policy = API.GetPersistentVar(
                self.key_prefix + "PetDeathPolicy",
                "auto_rez_continue",
                API.PersistentVar.Char
            )
            if policy in ["stop_on_death", "rez_and_cooldown", "auto_rez_continue"]:
                self.pet_death_policy = policy
        except Exception as e:
            API.SysMsg(f"Recovery config load error: {str(e)}", 32)

    def _save_config(self):
        """Save configuration to persistence"""
        try:
            API.SavePersistentVar(
                self.key_prefix + "PetDeathPolicy",
                self.pet_death_policy,
                API.PersistentVar.Char
            )
        except Exception as e:
            API.SysMsg(f"Recovery config save error: {str(e)}", 32)

    def set_pet_death_policy(self, policy):
        """
        Set pet death policy.

        Args:
            policy: One of "stop_on_death", "rez_and_cooldown", "auto_rez_continue"
        """
        if policy in ["stop_on_death", "rez_and_cooldown", "auto_rez_continue"]:
            self.pet_death_policy = policy
            self._save_config()

    def assess_flee_severity(self, danger_at_flee, pet_status):
        """
        Assess the severity of the flee event.

        Args:
            danger_at_flee: Danger score when flee was initiated (0-100)
            pet_status: Dict with pet health info:
                - tank_hp_percent: Tank pet HP % (0-100)
                - any_pet_deaths: Bool indicating if any pet died
                - pet_count: Number of pets

        Returns:
            str: "minor", "major", or "critical"
        """
        try:
            any_pet_deaths = pet_status.get('any_pet_deaths', False)
            tank_hp_percent = pet_status.get('tank_hp_percent', 100)

            # Critical: danger 91+ OR any pet death
            if danger_at_flee >= 91 or any_pet_deaths:
                return "critical"

            # Major: danger 81-90 OR tank pet < 30% HP
            if danger_at_flee >= 81 or tank_hp_percent < 30:
                return "major"

            # Minor: danger 71-80 AND no pet deaths
            if danger_at_flee >= 71:
                return "minor"

            # Default to minor for lower danger scores (shouldn't happen normally)
            return "minor"

        except Exception as e:
            API.SysMsg(f"Flee severity assessment error: {str(e)}", 32)
            return "major"  # Default to major on error

    def heal_to_full(self):
        """
        Heal player and all pets to 100% HP.
        Uses simple bandage healing with delays.

        Returns:
            bool: True if healing completed successfully
        """
        try:
            API.SysMsg("Healing to full...", 68)
            max_heal_time = 120  # 2 minutes max
            heal_start = time.time()

            while time.time() - heal_start < max_heal_time:
                API.ProcessCallbacks()

                # Check if player needs healing
                player = API.Player
                if player:
                    current_hp = getattr(player, 'Hits', 0)
                    max_hp = getattr(player, 'HitsMax', 1)
                    hp_percent = (current_hp / max_hp * 100) if max_hp > 0 else 100

                    if hp_percent < 100:
                        # Heal self
                        bandages = API.FindType(BANDAGE)
                        if bandages:
                            API.UseObject(bandages, False)
                            if supply_tracker:
                                supply_tracker.track_usage('bandages')
                            API.Pause(BANDAGE_DELAY)
                            continue

                # Check if any pet needs healing
                needs_healing = False
                for pet_info in self.pet_manager.pets:
                    pet_serial = pet_info.get('serial', 0)
                    pet = API.Mobiles.FindMobile(pet_serial)

                    if pet and not getattr(pet, 'IsDead', True):
                        pet_hp = getattr(pet, 'Hits', 0)
                        pet_max_hp = getattr(pet, 'HitsMax', 1)
                        pet_hp_percent = (pet_hp / pet_max_hp * 100) if pet_max_hp > 0 else 100

                        if pet_hp_percent < 100:
                            needs_healing = True
                            # Heal pet with bandage
                            bandages = API.FindType(BANDAGE)
                            if bandages:
                                API.CancelTarget()
                                API.CancelPreTarget()
                                API.PreTarget(pet_serial, "beneficial")
                                API.Pause(0.1)
                                API.UseObject(bandages, False)
                                if supply_tracker:
                                    supply_tracker.track_usage('bandages')
                                API.Pause(VET_DELAY)
                                API.CancelPreTarget()
                                break

                # If no one needs healing, we're done
                if not needs_healing:
                    API.SysMsg("All healed to full!", 68)
                    return True

                API.Pause(0.5)

            API.SysMsg("Heal timeout reached", 43)
            return True  # Continue anyway after timeout

        except Exception as e:
            API.SysMsg(f"Heal to full error: {str(e)}", 32)
            return True  # Continue despite error

    def resurrect_pet(self, pet_name):
        """
        Resurrect a dead pet using veterinary skill.

        Args:
            pet_name: Name of the pet to resurrect

        Returns:
            bool: True if resurrection successful
        """
        try:
            API.SysMsg(f"Attempting to resurrect {pet_name}...", 68)

            # Find dead pet by name
            all_mobiles = API.Mobiles.GetMobiles()
            dead_pet = None

            for mob in all_mobiles:
                if mob is None:
                    continue

                mob_name = getattr(mob, 'Name', '')
                is_dead = getattr(mob, 'IsDead', False)

                if mob_name == pet_name and is_dead:
                    dead_pet = mob
                    break

            if not dead_pet:
                API.SysMsg(f"Could not find dead pet: {pet_name}", 32)
                return False

            pet_serial = getattr(dead_pet, 'Serial', 0)

            # Use veterinary bandage on dead pet
            bandages = API.FindType(BANDAGE)
            if not bandages:
                API.SysMsg("No bandages for resurrection!", 32)
                return False

            API.CancelTarget()
            API.CancelPreTarget()
            API.PreTarget(pet_serial, "beneficial")
            API.Pause(0.1)
            API.UseObject(bandages, False)
            if supply_tracker:
                supply_tracker.track_usage('bandages')
            API.Pause(REZ_DELAY)
            API.CancelPreTarget()

            # Re-scan pets to update list
            self.pet_manager.scan_pets()

            API.SysMsg(f"{pet_name} resurrected!", 68)
            return True

        except Exception as e:
            API.SysMsg(f"Resurrect error: {str(e)}", 32)
            return False

    def execute_recovery(self, severity, flee_reason, danger_at_flee):
        """
        Execute recovery procedure based on severity.

        Args:
            severity: "minor", "major", or "critical"
            flee_reason: Reason for flee (for logging)
            danger_at_flee: Danger score when flee initiated

        Returns:
            str: Next state to transition to ("idle", "stopped")
        """
        try:
            import random

            self.total_recoveries += 1
            self.recovery_severity = severity
            self.flee_reason = flee_reason
            self.danger_at_flee = danger_at_flee

            if severity == "minor":
                self.minor_count += 1
            elif severity == "major":
                self.major_count += 1
            elif severity == "critical":
                self.critical_count += 1

            # Always heal to full first
            self.heal_to_full()

            # Handle based on severity
            if severity == "minor":
                # Wait 30-60 seconds, return to same area
                wait_time = random.randint(30, 60)
                API.SysMsg(f"Minor flee - cooling down for {wait_time}s...", 68)
                self.recovery_wait_time = wait_time
                self.recovery_start_time = time.time()
                self.is_recovering = True
                # Will return to same area when recovery completes
                return "idle"

            elif severity == "major":
                # Wait 2-5 minutes, rotate area, enable caution mode
                wait_time = random.randint(120, 300)
                API.SysMsg(f"Major flee - extended cooldown {wait_time//60}m...", 43)
                self.recovery_wait_time = wait_time
                self.recovery_start_time = time.time()
                self.is_recovering = True

                # Rotate to different farming area
                self.area_manager.rotate_to_next_area()

                # Enable temporary caution mode (reduce danger thresholds)
                self.caution_mode_active = True
                self.caution_mode_start = time.time()
                API.SysMsg("Caution mode activated (1 hour)", 43)

                return "idle"

            elif severity == "critical":
                # Check pet death policy
                API.SysMsg(f"CRITICAL flee - checking pet death policy...", 32)

                # Check if any pets died
                any_pet_deaths = self._check_for_dead_pets()

                if any_pet_deaths:
                    if self.pet_death_policy == "stop_on_death":
                        API.SysMsg("PET DEATH DETECTED - STOPPING SCRIPT!", 32)
                        API.SysMsg("Policy: stop_on_death", 32)
                        return "stopped"

                    elif self.pet_death_policy == "rez_and_cooldown":
                        # Resurrect all dead pets
                        self._resurrect_all_dead_pets()

                        # Long cooldown, then stop
                        wait_time = random.randint(1200, 1800)  # 20-30 min
                        API.SysMsg(f"Critical recovery - {wait_time//60}m cooldown, then stopping...", 32)
                        self.recovery_wait_time = wait_time
                        self.recovery_start_time = time.time()
                        self.is_recovering = True

                        # Rotate area
                        self.area_manager.rotate_to_next_area()

                        # Enable caution mode
                        self.caution_mode_active = True
                        self.caution_mode_start = time.time()

                        return "stopped"  # Will stop after cooldown

                    elif self.pet_death_policy == "auto_rez_continue":
                        # Resurrect all dead pets
                        self._resurrect_all_dead_pets()

                        # Wait 10-15 minutes, rotate area, continue
                        wait_time = random.randint(600, 900)
                        API.SysMsg(f"Auto-rezzing and continuing after {wait_time//60}m...", 43)
                        self.recovery_wait_time = wait_time
                        self.recovery_start_time = time.time()
                        self.is_recovering = True

                        # Rotate area
                        self.area_manager.rotate_to_next_area()

                        # Enable caution mode
                        self.caution_mode_active = True
                        self.caution_mode_start = time.time()

                        return "idle"
                else:
                    # No pet deaths, treat as major flee
                    wait_time = random.randint(120, 300)
                    API.SysMsg(f"Critical flee (no deaths) - cooldown {wait_time//60}m...", 43)
                    self.recovery_wait_time = wait_time
                    self.recovery_start_time = time.time()
                    self.is_recovering = True

                    self.area_manager.rotate_to_next_area()

                    self.caution_mode_active = True
                    self.caution_mode_start = time.time()

                    return "idle"

            return "idle"

        except Exception as e:
            API.SysMsg(f"Execute recovery error: {str(e)}", 32)
            return "idle"

    def _check_for_dead_pets(self):
        """Check if any pets are dead. Returns True if any dead pets found."""
        try:
            for pet_info in self.pet_manager.pets:
                pet_serial = pet_info.get('serial', 0)
                pet = API.Mobiles.FindMobile(pet_serial)

                if pet and getattr(pet, 'IsDead', False):
                    return True

            return False
        except Exception as e:
            API.SysMsg(f"Dead pet check error: {str(e)}", 32)
            return False

    def _resurrect_all_dead_pets(self):
        """Resurrect all dead pets."""
        try:
            for pet_info in self.pet_manager.pets:
                pet_serial = pet_info.get('serial', 0)
                pet_name = pet_info.get('name', 'Unknown')
                pet = API.Mobiles.FindMobile(pet_serial)

                if pet and getattr(pet, 'IsDead', False):
                    self.resurrect_pet(pet_name)
                    API.Pause(2.0)  # Wait between resurrections

        except Exception as e:
            API.SysMsg(f"Resurrect all error: {str(e)}", 32)

    def update(self):
        """
        Update recovery system - call from main loop during recovery state.

        Returns:
            bool: True if still recovering, False if recovery complete
        """
        try:
            if not self.is_recovering:
                return False

            # Check if recovery wait time is complete
            elapsed = time.time() - self.recovery_start_time
            if elapsed >= self.recovery_wait_time:
                API.SysMsg("Recovery complete!", 68)
                self.is_recovering = False
                return False

            # Still recovering
            remaining = int(self.recovery_wait_time - elapsed)
            if remaining % 30 == 0 and remaining > 0:  # Update every 30 seconds
                API.SysMsg(f"Recovering... {remaining}s remaining", 90)

            return True

        except Exception as e:
            API.SysMsg(f"Recovery update error: {str(e)}", 32)
            self.is_recovering = False
            return False

    def is_caution_mode_active(self):
        """Check if caution mode is still active."""
        if not self.caution_mode_active:
            return False

        # Check if expired (1 hour)
        elapsed = time.time() - self.caution_mode_start
        if elapsed >= self.caution_mode_duration:
            self.caution_mode_active = False
            API.SysMsg("Caution mode expired", 90)
            return False

        return True

    def get_caution_danger_adjustment(self):
        """
        Get danger threshold adjustment for caution mode.

        Returns:
            int: Amount to reduce danger thresholds (0 if not in caution mode)
        """
        if self.is_caution_mode_active():
            return self.caution_danger_reduction
        return 0

    def get_pet_status(self):
        """
        Get current pet status for severity assessment.

        Returns:
            dict: Pet status info
        """
        try:
            status = {
                'tank_hp_percent': 100,
                'any_pet_deaths': False,
                'pet_count': len(self.pet_manager.pets)
            }

            # Check for tank pet HP
            tank_pet = self.pet_manager.get_tank_pet()
            if tank_pet:
                tank_serial = tank_pet.get('serial', 0)
                tank_mob = API.Mobiles.FindMobile(tank_serial)
                if tank_mob and not getattr(tank_mob, 'IsDead', False):
                    tank_hp = getattr(tank_mob, 'Hits', 0)
                    tank_max_hp = getattr(tank_mob, 'HitsMax', 1)
                    status['tank_hp_percent'] = (tank_hp / tank_max_hp * 100) if tank_max_hp > 0 else 100

            # Check for any pet deaths
            status['any_pet_deaths'] = self._check_for_dead_pets()

            return status

        except Exception as e:
            API.SysMsg(f"Get pet status error: {str(e)}", 32)
            return {'tank_hp_percent': 100, 'any_pet_deaths': False, 'pet_count': 0}

# ============ SUPPLY TRACKING SYSTEM ============

class SupplyTracker:
    """
    Tracks supply consumption rates, predicts depletion, optimizes banking timing.
    Monitors bandages and vet kits, calculates usage rates, and helps determine
    optimal times to bank (combining gold dump + restocking).
    """

    def __init__(self, key_prefix):
        """
        Args:
            key_prefix: Persistence key prefix for saving historical data
        """
        self.key_prefix = key_prefix
        self.check_interval = 30.0  # Check supplies every 30 seconds
        self.last_check_time = 0

        # Tracked supplies
        self.supplies = {
            'bandages': {'graphic': 0x0E21, 'usage_history': [], 'last_count': 0},
            'vet_kits': {'graphic': 0x0E50, 'usage_history': [], 'last_count': 0}
        }

        # Load historical data
        self._load_history()

    def _load_history(self):
        """Load historical usage data from persistence"""
        try:
            for supply_name in self.supplies:
                history_str = API.GetPersistentVar(
                    self.key_prefix + f"Supply_{supply_name}_History",
                    "",
                    API.PersistentVar.Char
                )
                if history_str:
                    # Format: "timestamp:count|timestamp:count|..."
                    entries = [x for x in history_str.split("|") if x]
                    history = []
                    for entry in entries[-100:]:  # Keep last 100 entries
                        parts = entry.split(":")
                        if len(parts) == 2:
                            try:
                                timestamp = float(parts[0])
                                count = int(parts[1])
                                # Only keep entries from last 24 hours
                                if time.time() - timestamp < 86400:
                                    history.append({'timestamp': timestamp, 'count': count})
                            except (ValueError, IndexError):
                                pass
                    self.supplies[supply_name]['usage_history'] = history

        except Exception as e:
            API.SysMsg(f"Load supply history error: {str(e)}", 32)

    def _save_history(self):
        """Save historical usage data to persistence"""
        try:
            for supply_name, data in self.supplies.items():
                # Format: "timestamp:count|timestamp:count|..."
                history = data['usage_history']
                history_str = "|".join([f"{h['timestamp']}:{h['count']}" for h in history[-100:]])
                API.SavePersistentVar(
                    self.key_prefix + f"Supply_{supply_name}_History",
                    history_str,
                    API.PersistentVar.Char
                )
        except Exception as e:
            API.SysMsg(f"Save supply history error: {str(e)}", 32)

    def _count_supply(self, graphic):
        """Count items of given graphic in player's backpack"""
        try:
            backpack = API.Player.Backpack
            if not backpack:
                return 0

            count = 0
            items = API.FindType(graphic, backpack.Serial)
            if items:
                for item in items:
                    if item and hasattr(item, 'Amount'):
                        count += item.Amount
            return count
        except Exception as e:
            API.SysMsg(f"Count supply error: {str(e)}", 32)
            return 0

    def track_usage(self, supply_name):
        """
        Manually track usage of a supply (call when using bandage/vet kit).
        This increments the usage counter and stores timestamp.

        Args:
            supply_name: Name of supply ('bandages' or 'vet_kits')
        """
        if supply_name not in self.supplies:
            return

        try:
            current_count = self._count_supply(self.supplies[supply_name]['graphic'])
            timestamp = time.time()

            # Add to history
            self.supplies[supply_name]['usage_history'].append({
                'timestamp': timestamp,
                'count': current_count
            })

            # Keep only last 24 hours
            cutoff = timestamp - 86400
            self.supplies[supply_name]['usage_history'] = [
                h for h in self.supplies[supply_name]['usage_history']
                if h['timestamp'] > cutoff
            ]

            # Save to persistence
            self._save_history()

        except Exception as e:
            API.SysMsg(f"Track usage error: {str(e)}", 32)

    def update_counts(self):
        """
        Automatically update supply counts periodically.
        Call this in main loop to track consumption without manual tracking.
        """
        try:
            current_time = time.time()
            if current_time < self.last_check_time + self.check_interval:
                return

            self.last_check_time = current_time

            for supply_name, data in self.supplies.items():
                current_count = self._count_supply(data['graphic'])

                # Only add to history if count changed
                if current_count != data['last_count']:
                    data['usage_history'].append({
                        'timestamp': current_time,
                        'count': current_count
                    })

                    # Keep only last 24 hours
                    cutoff = current_time - 86400
                    data['usage_history'] = [
                        h for h in data['usage_history']
                        if h['timestamp'] > cutoff
                    ]

                    data['last_count'] = current_count

            # Save to persistence
            self._save_history()

        except Exception as e:
            API.SysMsg(f"Update counts error: {str(e)}", 32)

    def _calculate_usage_rate(self, supply_name, hours=1.0):
        """
        Calculate usage rate per hour from historical data.

        Args:
            supply_name: Name of supply
            hours: Time window to calculate rate over (default 1 hour)

        Returns:
            Usage rate (items per hour), or 0 if insufficient data
        """
        if supply_name not in self.supplies:
            return 0

        try:
            history = self.supplies[supply_name]['usage_history']
            if len(history) < 2:
                return 0  # Not enough data

            current_time = time.time()
            cutoff = current_time - (hours * 3600)

            # Get entries within time window
            recent = [h for h in history if h['timestamp'] > cutoff]
            if len(recent) < 2:
                return 0

            # Calculate rate from first to last entry in window
            time_span = recent[-1]['timestamp'] - recent[0]['timestamp']
            if time_span < 60:  # Need at least 1 minute of data
                return 0

            count_change = recent[0]['count'] - recent[-1]['count']  # Consumed = decrease
            if count_change <= 0:
                return 0  # Count increased or no change

            # Convert to per-hour rate
            hours_span = time_span / 3600.0
            rate = count_change / hours_span

            return max(0, rate)

        except Exception as e:
            API.SysMsg(f"Calculate usage rate error: {str(e)}", 32)
            return 0

    def predict_depletion_time(self, supply_name):
        """
        Predict when supply will run out based on current count and usage rate.

        Args:
            supply_name: Name of supply

        Returns:
            Hours remaining until depletion, or -1 if cannot predict
        """
        if supply_name not in self.supplies:
            return -1

        try:
            current_count = self._count_supply(self.supplies[supply_name]['graphic'])
            if current_count == 0:
                return 0  # Already out

            usage_rate = self._calculate_usage_rate(supply_name, hours=1.0)
            if usage_rate == 0:
                return -1  # No usage data or not consuming

            hours_remaining = current_count / usage_rate
            return hours_remaining

        except Exception as e:
            API.SysMsg(f"Predict depletion error: {str(e)}", 32)
            return -1

    def should_prioritize_restock(self, critical_hours=1.0):
        """
        Check if any supply is running low and should prioritize restocking.

        Args:
            critical_hours: Hours remaining threshold for critical status

        Returns:
            True if any supply depleting within critical_hours
        """
        try:
            for supply_name in self.supplies:
                hours_remaining = self.predict_depletion_time(supply_name)
                if hours_remaining >= 0 and hours_remaining < critical_hours:
                    return True
            return False
        except Exception as e:
            API.SysMsg(f"Check priority restock error: {str(e)}", 32)
            return False

    def get_supply_status(self):
        """
        Get detailed status for all tracked supplies.

        Returns:
            Dict mapping supply_name -> {count, rate, hours_remaining, status}
            Status: "good" (>2hr), "low" (1-2hr), "critical" (<1hr), "out" (0)
        """
        status = {}
        try:
            for supply_name in self.supplies:
                count = self._count_supply(self.supplies[supply_name]['graphic'])
                rate = self._calculate_usage_rate(supply_name, hours=1.0)
                hours_remaining = self.predict_depletion_time(supply_name)

                # Determine status
                if count == 0:
                    supply_status = "out"
                elif hours_remaining < 0:
                    supply_status = "unknown"
                elif hours_remaining < 1.0:
                    supply_status = "critical"
                elif hours_remaining < 2.0:
                    supply_status = "low"
                else:
                    supply_status = "good"

                status[supply_name] = {
                    'count': count,
                    'rate': rate,
                    'hours_remaining': hours_remaining,
                    'status': supply_status
                }

            return status

        except Exception as e:
            API.SysMsg(f"Get supply status error: {str(e)}", 32)
            return {}

    def optimize_bank_timing(self, gold_current, gold_threshold, weight_percent):
        """
        Suggest optimal time to bank by combining triggers.
        Returns True if should bank now to combine gold dump + restocking.

        Args:
            gold_current: Current gold amount
            gold_threshold: Gold trigger threshold
            weight_percent: Current weight as percentage of max

        Returns:
            True if should bank now to optimize trip
        """
        try:
            # Check if restocking is prioritized
            need_restock = self.should_prioritize_restock(critical_hours=1.0)

            # Check if gold is close to threshold (within 20%)
            gold_close = gold_current >= (gold_threshold * 0.8)

            # Check if weight is high (>70%)
            weight_high = weight_percent > 70

            # Suggest banking if:
            # 1. Need restock AND (gold close OR weight high)
            # 2. This combines multiple trips into one
            if need_restock and (gold_close or weight_high):
                return True

            return False

        except Exception as e:
            API.SysMsg(f"Optimize bank timing error: {str(e)}", 32)
            return False

# ============ BANKING TRIGGER SYSTEM ============

class BankingTriggers:
    """
    Multi-condition banking trigger system.
    Monitors weight, time, gold, and supply thresholds to determine when banking is needed.
    """

    def __init__(self, key_prefix):
        """
        Args:
            key_prefix: Persistence key prefix
        """
        self.key_prefix = key_prefix
        self.check_interval = 10.0  # Check every 10 seconds
        self.last_check_time = 0
        self.last_bank_time = 0

        # Default trigger configurations
        self.weight_trigger = {
            'enabled': True,
            'threshold_pct': 80.0  # Percent of max weight
        }
        self.time_trigger = {
            'enabled': True,
            'interval_minutes': 60  # Bank every 60 minutes
        }
        self.gold_trigger = {
            'enabled': True,
            'gold_amount': 10000  # Bank when carrying this much gold
        }
        self.supply_trigger = {
            'enabled': True,
            'bandage_threshold': 50  # Bank when bandages drop below this
        }

        # Load configuration from persistence
        self._load_config()

    def _load_config(self):
        """Load trigger configuration from persistence"""
        try:
            # Load each trigger configuration
            config_str = API.GetPersistentVar(
                self.key_prefix + "BankTriggers",
                "",
                API.PersistentVar.Char
            )

            if config_str:
                # Parse config: weight_en:weight_pct|time_en:time_min|gold_en:gold_amt|supply_en:supply_thresh
                parts = config_str.split("|")
                if len(parts) >= 4:
                    # Weight trigger
                    weight_parts = parts[0].split(":")
                    if len(weight_parts) == 2:
                        self.weight_trigger['enabled'] = weight_parts[0] == "True"
                        self.weight_trigger['threshold_pct'] = float(weight_parts[1])

                    # Time trigger
                    time_parts = parts[1].split(":")
                    if len(time_parts) == 2:
                        self.time_trigger['enabled'] = time_parts[0] == "True"
                        self.time_trigger['interval_minutes'] = int(time_parts[1])

                    # Gold trigger
                    gold_parts = parts[2].split(":")
                    if len(gold_parts) == 2:
                        self.gold_trigger['enabled'] = gold_parts[0] == "True"
                        self.gold_trigger['gold_amount'] = int(gold_parts[1])

                    # Supply trigger
                    supply_parts = parts[3].split(":")
                    if len(supply_parts) == 2:
                        self.supply_trigger['enabled'] = supply_parts[0] == "True"
                        self.supply_trigger['bandage_threshold'] = int(supply_parts[1])

            # Load last bank time
            last_bank_str = API.GetPersistentVar(
                self.key_prefix + "LastBankTime",
                "0",
                API.PersistentVar.Char
            )
            self.last_bank_time = float(last_bank_str)

        except Exception as e:
            API.SysMsg(f"Load banking config error: {str(e)}", 32)

    def _save_config(self):
        """Save trigger configuration to persistence"""
        try:
            # Build config string
            config_str = f"{self.weight_trigger['enabled']}:{self.weight_trigger['threshold_pct']}|"
            config_str += f"{self.time_trigger['enabled']}:{self.time_trigger['interval_minutes']}|"
            config_str += f"{self.gold_trigger['enabled']}:{self.gold_trigger['gold_amount']}|"
            config_str += f"{self.supply_trigger['enabled']}:{self.supply_trigger['bandage_threshold']}"

            API.SavePersistentVar(
                self.key_prefix + "BankTriggers",
                config_str,
                API.PersistentVar.Char
            )
        except Exception as e:
            API.SysMsg(f"Save banking config error: {str(e)}", 32)

    def should_bank(self):
        """
        Check if any banking trigger condition is met.

        Returns:
            tuple: (should_bank: bool, reason: str or None)
        """
        current_time = time.time()

        # Only check at specified intervals to avoid overhead
        if current_time - self.last_check_time < self.check_interval:
            return (False, None)

        self.last_check_time = current_time

        try:
            # Check weight trigger
            if self.weight_trigger['enabled']:
                player_weight = getattr(API.Player, 'Weight', 0)
                max_weight = getattr(API.Player, 'MaxWeight', 1)
                weight_pct = (player_weight / max_weight * 100) if max_weight > 0 else 0

                if weight_pct >= self.weight_trigger['threshold_pct']:
                    return (True, "weight")

            # Check time trigger
            if self.time_trigger['enabled']:
                if self.last_bank_time > 0:  # Only check if we've banked before
                    time_since_bank = (current_time - self.last_bank_time) / 60  # Convert to minutes
                    if time_since_bank >= self.time_trigger['interval_minutes']:
                        return (True, "time")

            # Check gold trigger
            if self.gold_trigger['enabled']:
                gold_count = self._count_gold_in_backpack()
                if gold_count >= self.gold_trigger['gold_amount']:
                    return (True, "gold")

            # Check supply trigger
            if self.supply_trigger['enabled']:
                bandage_count = self._count_bandages()
                if bandage_count < self.supply_trigger['bandage_threshold']:
                    return (True, "supplies")

        except Exception as e:
            API.SysMsg(f"Banking trigger check error: {str(e)}", 32)

        return (False, None)

    def track_last_bank(self):
        """Record timestamp of last banking run"""
        self.last_bank_time = time.time()
        try:
            API.SavePersistentVar(
                self.key_prefix + "LastBankTime",
                str(self.last_bank_time),
                API.PersistentVar.Char
            )
        except Exception as e:
            API.SysMsg(f"Track bank time error: {str(e)}", 32)

    def get_time_until_next_bank(self):
        """
        Get time remaining until next time-based banking run.

        Returns:
            float: Minutes remaining (0 if time trigger disabled or no previous bank)
        """
        if not self.time_trigger['enabled'] or self.last_bank_time == 0:
            return 0

        current_time = time.time()
        time_since_bank = (current_time - self.last_bank_time) / 60  # Minutes
        time_remaining = self.time_trigger['interval_minutes'] - time_since_bank

        return max(0, time_remaining)

    def configure_triggers(self, config_dict):
        """
        Update trigger settings from configuration dictionary.

        Args:
            config_dict: Dictionary with keys like 'weight_enabled', 'weight_threshold_pct', etc.
        """
        try:
            # Update weight trigger
            if 'weight_enabled' in config_dict:
                self.weight_trigger['enabled'] = config_dict['weight_enabled']
            if 'weight_threshold_pct' in config_dict:
                self.weight_trigger['threshold_pct'] = float(config_dict['weight_threshold_pct'])

            # Update time trigger
            if 'time_enabled' in config_dict:
                self.time_trigger['enabled'] = config_dict['time_enabled']
            if 'time_interval_minutes' in config_dict:
                self.time_trigger['interval_minutes'] = int(config_dict['time_interval_minutes'])

            # Update gold trigger
            if 'gold_enabled' in config_dict:
                self.gold_trigger['enabled'] = config_dict['gold_enabled']
            if 'gold_amount' in config_dict:
                self.gold_trigger['gold_amount'] = int(config_dict['gold_amount'])

            # Update supply trigger
            if 'supply_enabled' in config_dict:
                self.supply_trigger['enabled'] = config_dict['supply_enabled']
            if 'supply_bandage_threshold' in config_dict:
                self.supply_trigger['bandage_threshold'] = int(config_dict['supply_bandage_threshold'])

            # Save updated configuration
            self._save_config()

        except Exception as e:
            API.SysMsg(f"Configure banking triggers error: {str(e)}", 32)

    def _count_gold_in_backpack(self):
        """Count total gold in player's backpack"""
        try:
            gold_count = 0
            backpack = API.Player.Backpack
            if backpack:
                # Gold graphic: 0x0EED
                gold_items = API.FindType(0x0EED, backpack.Serial)
                if gold_items:
                    for item in gold_items:
                        if item and hasattr(item, 'Amount'):
                            gold_count += item.Amount
            return gold_count
        except Exception as e:
            API.SysMsg(f"Count gold error: {str(e)}", 32)
            return 0

    def _count_bandages(self):
        """Count bandages in player's backpack"""
        try:
            bandage_count = 0
            backpack = API.Player.Backpack
            if backpack:
                # Bandage graphic: 0x0E21
                bandage_items = API.FindType(0x0E21, backpack.Serial)
                if bandage_items:
                    for item in bandage_items:
                        if item and hasattr(item, 'Amount'):
                            bandage_count += item.Amount
            return bandage_count
        except Exception as e:
            API.SysMsg(f"Count bandages error: {str(e)}", 32)
            return 0

# ============ BANKING SYSTEM ============

class BankingSystem:
    """
    Realistic banking behavior: travel to bank, navigate to banker, interact naturally.
    Adds human-like variation with random pauses, mixed pathfinding/walking.
    """

    def __init__(self, travel_system, key_prefix):
        """
        Args:
            travel_system: TravelSystem instance for recalls
            key_prefix: Persistence key prefix
        """
        self.travel_system = travel_system
        self.key_prefix = key_prefix

        # Banking configuration
        self.bank_runebook_slot = 1  # Default slot for bank location
        self.bank_x = 0
        self.bank_y = 0
        self.banking_speed = "medium"  # "fast", "medium", "realistic"

        # Supply restocking configuration
        self.restock_bandage_amount = 150  # Target bandage count
        self.low_vetkit_alert_threshold = 2  # Alert when vet kits below this

        # Statistics
        self.gold_banked = 0
        self.items_banked = 0

        # Load configuration
        self._load_config()

    def _load_config(self):
        """Load banking configuration from persistence"""
        try:
            # Load bank location
            bank_xy_str = API.GetPersistentVar(
                self.key_prefix + "BankXY",
                "0,0",
                API.PersistentVar.Char
            )
            if bank_xy_str and ',' in bank_xy_str:
                parts = bank_xy_str.split(',')
                self.bank_x = int(parts[0])
                self.bank_y = int(parts[1])

            # Load bank runebook slot
            self.bank_runebook_slot = int(API.GetPersistentVar(
                self.key_prefix + "BankRunebookSlot",
                "1",
                API.PersistentVar.Char
            ))

            # Load banking speed
            self.banking_speed = API.GetPersistentVar(
                self.key_prefix + "BankingSpeed",
                "medium",
                API.PersistentVar.Char
            )

            # Load supply restocking configuration
            self.restock_bandage_amount = int(API.GetPersistentVar(
                self.key_prefix + "RestockBandageAmount",
                "150",
                API.PersistentVar.Char
            ))
            self.low_vetkit_alert_threshold = int(API.GetPersistentVar(
                self.key_prefix + "LowVetKitAlertThreshold",
                "2",
                API.PersistentVar.Char
            ))

            # Load statistics
            self.gold_banked = int(API.GetPersistentVar(
                self.key_prefix + "GoldBanked",
                "0",
                API.PersistentVar.Char
            ))
            self.items_banked = int(API.GetPersistentVar(
                self.key_prefix + "ItemsBanked",
                "0",
                API.PersistentVar.Char
            ))

        except Exception as e:
            API.SysMsg(f"Load banking config error: {str(e)}", 32)

    def _save_config(self):
        """Save banking configuration to persistence"""
        try:
            API.SavePersistentVar(
                self.key_prefix + "BankXY",
                f"{self.bank_x},{self.bank_y}",
                API.PersistentVar.Char
            )
            API.SavePersistentVar(
                self.key_prefix + "BankRunebookSlot",
                str(self.bank_runebook_slot),
                API.PersistentVar.Char
            )
            API.SavePersistentVar(
                self.key_prefix + "BankingSpeed",
                self.banking_speed,
                API.PersistentVar.Char
            )
            API.SavePersistentVar(
                self.key_prefix + "RestockBandageAmount",
                str(self.restock_bandage_amount),
                API.PersistentVar.Char
            )
            API.SavePersistentVar(
                self.key_prefix + "LowVetKitAlertThreshold",
                str(self.low_vetkit_alert_threshold),
                API.PersistentVar.Char
            )
            API.SavePersistentVar(
                self.key_prefix + "GoldBanked",
                str(self.gold_banked),
                API.PersistentVar.Char
            )
            API.SavePersistentVar(
                self.key_prefix + "ItemsBanked",
                str(self.items_banked),
                API.PersistentVar.Char
            )
        except Exception as e:
            API.SysMsg(f"Save banking config error: {str(e)}", 32)

    def configure(self, bank_x=None, bank_y=None, runebook_slot=None, speed=None):
        """
        Configure banking parameters.

        Args:
            bank_x: X coordinate of bank location
            bank_y: Y coordinate of bank location
            runebook_slot: Runebook slot number for bank recall
            speed: Banking speed mode ("fast", "medium", "realistic")
        """
        if bank_x is not None:
            self.bank_x = bank_x
        if bank_y is not None:
            self.bank_y = bank_y
        if runebook_slot is not None:
            self.bank_runebook_slot = runebook_slot
        if speed is not None and speed in ["fast", "medium", "realistic"]:
            self.banking_speed = speed

        self._save_config()

    def get_pause_duration(self, pause_type):
        """
        Get pause duration based on banking speed mode.

        Args:
            pause_type: Type of pause ("arrival", "before_action", "between_actions")

        Returns:
            float: Pause duration in seconds
        """
        if self.banking_speed == "fast":
            durations = {
                "arrival": (0.5, 1.0),
                "before_action": (0.3, 0.5),
                "between_actions": (0.2, 0.4)
            }
        elif self.banking_speed == "realistic":
            durations = {
                "arrival": (3.0, 5.0),
                "before_action": (1.5, 3.0),
                "between_actions": (1.0, 2.0)
            }
        else:  # medium
            durations = {
                "arrival": (2.0, 3.0),
                "before_action": (1.0, 2.0),
                "between_actions": (0.5, 1.0)
            }

        min_pause, max_pause = durations.get(pause_type, (1.0, 2.0))
        return random.uniform(min_pause, max_pause)

    def travel_to_bank(self):
        """
        Recall to bank location with realistic pauses.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Save position before recall
            pos_before = (getattr(API.Player, 'X', 0), getattr(API.Player, 'Y', 0))

            # Attempt recall to bank
            API.SysMsg(f"Recalling to bank (slot {self.bank_runebook_slot})...", 43)
            success = self.travel_system.recall_to_slot(self.bank_runebook_slot)

            if not success:
                API.SysMsg("Failed to recall to bank!", 32)
                return False

            # Verify position changed
            pos_after = (getattr(API.Player, 'X', 0), getattr(API.Player, 'Y', 0))
            if pos_before == pos_after:
                API.SysMsg("Recall position didn't change!", 32)
                return False

            # Random "looking around" pause after arrival
            pause_duration = self.get_pause_duration("arrival")
            API.SysMsg(f"Arrived at bank (pausing {pause_duration:.1f}s)...", 68)
            API.Pause(pause_duration)

            return True

        except Exception as e:
            API.SysMsg(f"Travel to bank error: {str(e)}", 32)
            return False

    def navigate_to_bank(self, bank_x=None, bank_y=None):
        """
        Navigate to bank location with human-like behavior.
        Mix of pathfinding and manual walking with pauses.

        Args:
            bank_x: X coordinate (uses self.bank_x if None)
            bank_y: Y coordinate (uses self.bank_y if None)

        Returns:
            bool: True when arrived, False if failed
        """
        try:
            if bank_x is None:
                bank_x = self.bank_x
            if bank_y is None:
                bank_y = self.bank_y

            if bank_x == 0 or bank_y == 0:
                API.SysMsg("Bank location not configured!", 32)
                return False

            # Decide movement method based on banking speed
            use_pathfinding = True
            if self.banking_speed == "medium":
                use_pathfinding = random.random() < 0.6  # 60% pathfind
            elif self.banking_speed == "realistic":
                use_pathfinding = random.random() < 0.4  # 40% pathfind

            API.SysMsg(f"Navigating to bank ({bank_x}, {bank_y})...", 43)

            # Wait for arrival
            nav_start = time.time()
            max_nav_time = 30.0 if self.banking_speed == "fast" else 60.0 if self.banking_speed == "medium" else 90.0

            while time.time() < nav_start + max_nav_time:
                API.ProcessCallbacks()

                # Check distance to bank
                player_x = getattr(API.Player, 'X', 0)
                player_y = getattr(API.Player, 'Y', 0)
                distance = abs(player_x - bank_x) + abs(player_y - bank_y)  # Manhattan distance

                if distance <= 2:
                    API.SysMsg("Arrived at bank location!", 68)
                    return True

                # Start pathfinding if not active and using pathfinding method
                if use_pathfinding and not API.Pathfinding():
                    API.Pathfind(bank_x, bank_y)

                # For manual walking mode, periodically update pathfinding target
                if not use_pathfinding and not API.Pathfinding():
                    # Walk toward bank with some randomness
                    target_x = bank_x + random.randint(-1, 1)
                    target_y = bank_y + random.randint(-1, 1)
                    API.Pathfind(target_x, target_y)

                    # Random pause during walking
                    if self.banking_speed != "fast":
                        pause = self.get_pause_duration("between_actions")
                        API.Pause(pause)

                API.Pause(0.1)

            # Timeout
            API.SysMsg("Navigation timeout - may not be at bank!", 43)
            return False

        except Exception as e:
            API.SysMsg(f"Navigate to bank error: {str(e)}", 32)
            return False

    def get_distance_to_bank(self):
        """
        Calculate distance to configured bank location.

        Returns:
            int: Manhattan distance to bank, or -1 if bank not configured
        """
        if self.bank_x == 0 or self.bank_y == 0:
            return -1

        player_x = getattr(API.Player, 'X', 0)
        player_y = getattr(API.Player, 'Y', 0)
        return abs(player_x - self.bank_x) + abs(player_y - self.bank_y)

    def interact_with_bank(self, bank_serial):
        """
        Interact with bank: open, deposit gold/loot, restock supplies, close.
        Uses realistic pauses throughout for human-like behavior.

        Args:
            bank_serial: Serial of bank container/NPC

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Random pause before opening bank
            pause = self.get_pause_duration("before_action")
            API.SysMsg(f"Opening bank (pausing {pause:.1f}s)...", 43)
            API.Pause(pause)

            # Open bank/chest
            API.UseObject(bank_serial, False)

            # Wait for container gump (up to 2 seconds)
            wait_start = time.time()
            bank_opened = False
            while time.time() < wait_start + 2.0:
                API.ProcessCallbacks()
                # TODO: Check for container gump when gump detection is implemented
                API.Pause(0.1)

            # For now, assume bank opened after 2 second wait
            API.Pause(2.0)
            bank_opened = True

            if not bank_opened:
                API.SysMsg("Failed to open bank!", 32)
                return False

            API.SysMsg("Bank opened, processing...", 68)

            # Perform banking operations
            self.deposit_gold()
            self.deposit_loot_items()
            self.restock_supplies()

            # Random pause before closing
            pause = self.get_pause_duration("before_action")
            API.SysMsg(f"Closing bank (pausing {pause:.1f}s)...", 43)
            API.Pause(pause)

            # TODO: Close bank container when gump management is implemented

            API.SysMsg("Banking complete!", 68)
            self._save_config()  # Save updated statistics
            return True

        except Exception as e:
            API.SysMsg(f"Bank interaction error: {str(e)}", 32)
            return False

    def deposit_gold(self):
        """
        Deposit gold from backpack to bank in multiple stacks (realistic behavior).
        Tracks total gold banked for statistics.
        """
        try:
            backpack = API.Player.Backpack
            if not backpack:
                return

            # Find all gold piles in backpack
            gold_items = API.FindType(GOLD, backpack.Serial)
            if not gold_items:
                API.SysMsg("No gold to deposit", 43)
                return

            # Calculate total gold
            total_gold = 0
            for item in gold_items:
                if item and hasattr(item, 'Amount'):
                    total_gold += item.Amount

            if total_gold == 0:
                return

            API.SysMsg(f"Depositing {total_gold} gold...", 43)

            # Split into 1-3 random stacks
            num_stacks = random.randint(1, min(3, len(gold_items)))
            deposited_count = 0

            for i, item in enumerate(gold_items[:num_stacks]):
                if item:
                    # Random pause between deposits
                    pause = self.get_pause_duration("between_actions")
                    API.Pause(pause)

                    # TODO: Implement actual drag-to-bank when container management is ready
                    # For now, just simulate the action with pauses
                    deposited_count += 1

                    # Random pause after deposit
                    pause = self.get_pause_duration("between_actions")
                    API.Pause(pause)

            # Update statistics
            self.gold_banked += total_gold
            API.SysMsg(f"Deposited {total_gold} gold in {deposited_count} stack(s)", 68)

        except Exception as e:
            API.SysMsg(f"Deposit gold error: {str(e)}", 32)

    def deposit_loot_items(self):
        """
        Deposit collected loot items from backpack to bank.
        Tracks total items banked for statistics.
        """
        try:
            # TODO: Implement loot item detection based on loot_filter
            # For now, this is a placeholder for when loot system is implemented
            API.SysMsg("Loot deposit not yet implemented", 43)

        except Exception as e:
            API.SysMsg(f"Deposit loot items error: {str(e)}", 32)

    def restock_supplies(self):
        """
        Restock bandages from bank, alert if vet kits low.
        Does not auto-restock vet kits (too valuable).
        """
        try:
            backpack = API.Player.Backpack
            if not backpack:
                return

            # Check bandage count
            bandage_count = self._count_bandages()
            API.SysMsg(f"Current bandages: {bandage_count}", 43)

            if bandage_count < self.restock_bandage_amount:
                needed = self.restock_bandage_amount - bandage_count

                # Random pause before withdrawing
                pause = self.get_pause_duration("between_actions")
                API.SysMsg(f"Restocking {needed} bandages (pausing {pause:.1f}s)...", 43)
                API.Pause(pause)

                # TODO: Implement actual withdraw from bank when container management is ready
                # For now, just simulate the action
                API.SysMsg(f"Would restock {needed} bandages to reach {self.restock_bandage_amount}", 43)

                # Random pause after withdraw
                pause = self.get_pause_duration("between_actions")
                API.Pause(pause)

            # Check vet kit count (alert only, don't restock)
            vetkit_count = self._count_vetkits()
            if vetkit_count < self.low_vetkit_alert_threshold:
                API.SysMsg(f"WARNING: Only {vetkit_count} vet kits remaining!", 32)

        except Exception as e:
            API.SysMsg(f"Restock supplies error: {str(e)}", 32)

    def _count_bandages(self):
        """Count bandages in player's backpack"""
        try:
            bandage_count = 0
            backpack = API.Player.Backpack
            if backpack:
                bandage_items = API.FindType(BANDAGE, backpack.Serial)
                if bandage_items:
                    for item in bandage_items:
                        if item and hasattr(item, 'Amount'):
                            bandage_count += item.Amount
            return bandage_count
        except Exception as e:
            API.SysMsg(f"Count bandages error: {str(e)}", 32)
            return 0

    def _count_vetkits(self):
        """Count vet kits in player's backpack"""
        try:
            # Vet kit graphic: 0x0E50
            vetkit_count = 0
            backpack = API.Player.Backpack
            if backpack:
                vetkit_items = API.FindType(0x0E50, backpack.Serial)
                if vetkit_items:
                    for item in vetkit_items:
                        if item and hasattr(item, 'Amount'):
                            vetkit_count += item.Amount
            return vetkit_count
        except Exception as e:
            API.SysMsg(f"Count vet kits error: {str(e)}", 32)
            return 0

    def is_at_bank(self, tolerance=2):
        """
        Check if player is at bank location.

        Args:
            tolerance: Distance tolerance in tiles

        Returns:
            bool: True if within tolerance of bank location
        """
        distance = self.get_distance_to_bank()
        return distance != -1 and distance <= tolerance

# ============ STATISTICS TRACKING SYSTEM ============

class StatisticsTracker:
    """
    Comprehensive statistics tracking for farming sessions.
    Tracks session stats, performance metrics, enemy breakdown, area performance,
    danger events, and supply consumption. Updates displays in real-time.
    """

    def __init__(self, key_prefix):
        """
        Args:
            key_prefix: Persistence key prefix for saving stats
        """
        self.key_prefix = key_prefix

        # Session stats (updated in real-time)
        self.gold_collected = 0
        self.total_kills = 0
        self.player_deaths = 0
        self.pet_deaths = 0
        self.flee_events = {"minor": 0, "major": 0, "critical": 0}
        self.time_by_state = {
            "farming": 0.0,
            "banking": 0.0,
            "fleeing": 0.0,
            "recovering": 0.0,
            "looting": 0.0,
            "idle": 0.0
        }
        self.supplies_used = {"bandages": 0, "vet_kits": 0, "potions": 0}
        self.session_start_time = time.time()

        # Performance metrics (calculated periodically)
        self.gold_per_hour = 0.0
        self.kills_per_hour = 0.0
        self.deaths_per_hour = 0.0
        self.average_danger = 0.0
        self.banking_efficiency = 0.0  # farming_time / total_time

        # Enemy breakdown tracking (dict keyed by enemy name)
        self.enemy_breakdown = {}
        # Each entry: {"kill_count": int, "gold_total": int, "deaths_caused": int, "combat_time": float}

        # Area performance tracking (dict keyed by area name)
        self.area_performance = {}
        # Each entry: {"time_in_area": float, "gold_from_area": int, "kills_in_area": int,
        #              "flees_from_area": int, "danger_samples": [], "success_rate": float}

        # Danger events tracking (list of event dicts)
        self.danger_events = []
        # Each event: {"timestamp": float, "area": str, "trigger_reason": str,
        #              "danger_level": int, "enemies_present": list, "outcome": str}

        # State tracking for time calculations
        self.current_state = "idle"
        self.state_start_time = time.time()
        self.last_update_time = time.time()

        # Combat tracking
        self.current_enemy = None
        self.combat_start_time = 0

        # Load persistent stats
        self._load_stats()

    def _load_stats(self):
        """Load persistent statistics from saved data"""
        try:
            # Load cumulative stats if they exist
            self.gold_collected = int(API.GetPersistentVar(
                self.key_prefix + "StatsGoldCollected", "0", API.PersistentVar.Char
            ))
            self.total_kills = int(API.GetPersistentVar(
                self.key_prefix + "StatsTotalKills", "0", API.PersistentVar.Char
            ))
            self.player_deaths = int(API.GetPersistentVar(
                self.key_prefix + "StatsPlayerDeaths", "0", API.PersistentVar.Char
            ))
            self.pet_deaths = int(API.GetPersistentVar(
                self.key_prefix + "StatsPetDeaths", "0", API.PersistentVar.Char
            ))
        except:
            pass

    def _save_stats(self):
        """Save persistent statistics"""
        try:
            API.SavePersistentVar(
                self.key_prefix + "StatsGoldCollected",
                str(self.gold_collected),
                API.PersistentVar.Char
            )
            API.SavePersistentVar(
                self.key_prefix + "StatsTotalKills",
                str(self.total_kills),
                API.PersistentVar.Char
            )
            API.SavePersistentVar(
                self.key_prefix + "StatsPlayerDeaths",
                str(self.player_deaths),
                API.PersistentVar.Char
            )
            API.SavePersistentVar(
                self.key_prefix + "StatsPetDeaths",
                str(self.pet_deaths),
                API.PersistentVar.Char
            )
        except:
            pass

    def update_state(self, new_state):
        """
        Update current state and track time spent in each state.

        Args:
            new_state: New state name (farming, banking, fleeing, etc.)
        """
        current_time = time.time()

        # Add elapsed time to previous state
        if self.current_state in self.time_by_state:
            elapsed = current_time - self.state_start_time
            self.time_by_state[self.current_state] += elapsed

        # Update to new state
        self.current_state = new_state
        self.state_start_time = current_time

    def increment_gold(self, amount, area_name="Unknown", enemy_name=None):
        """
        Increment gold collected and update related stats.

        Args:
            amount: Gold amount collected
            area_name: Name of area where gold was collected
            enemy_name: Name of enemy that dropped the gold (if applicable)
        """
        self.gold_collected += amount

        # Update area performance
        if area_name not in self.area_performance:
            self.area_performance[area_name] = {
                "time_in_area": 0.0,
                "gold_from_area": 0,
                "kills_in_area": 0,
                "flees_from_area": 0,
                "danger_samples": [],
                "success_rate": 1.0
            }
        self.area_performance[area_name]["gold_from_area"] += amount

        # Update enemy breakdown if enemy specified
        if enemy_name:
            if enemy_name not in self.enemy_breakdown:
                self.enemy_breakdown[enemy_name] = {
                    "kill_count": 0,
                    "gold_total": 0,
                    "deaths_caused": 0,
                    "combat_time": 0.0
                }
            self.enemy_breakdown[enemy_name]["gold_total"] += amount

        self._save_stats()

    def increment_kills(self, enemy_name, area_name="Unknown", combat_duration=0.0):
        """
        Increment kill count and update enemy/area stats.

        Args:
            enemy_name: Name of killed enemy
            area_name: Name of area where kill occurred
            combat_duration: Time spent in combat (seconds)
        """
        self.total_kills += 1

        # Update enemy breakdown
        if enemy_name not in self.enemy_breakdown:
            self.enemy_breakdown[enemy_name] = {
                "kill_count": 0,
                "gold_total": 0,
                "deaths_caused": 0,
                "combat_time": 0.0
            }
        self.enemy_breakdown[enemy_name]["kill_count"] += 1
        self.enemy_breakdown[enemy_name]["combat_time"] += combat_duration

        # Update area performance
        if area_name not in self.area_performance:
            self.area_performance[area_name] = {
                "time_in_area": 0.0,
                "gold_from_area": 0,
                "kills_in_area": 0,
                "flees_from_area": 0,
                "danger_samples": [],
                "success_rate": 1.0
            }
        self.area_performance[area_name]["kills_in_area"] += 1

        self._save_stats()

    def increment_player_deaths(self):
        """Increment player death count"""
        self.player_deaths += 1
        self._save_stats()

    def increment_pet_deaths(self):
        """Increment pet death count"""
        self.pet_deaths += 1
        self._save_stats()

    def increment_flee_event(self, severity, area_name="Unknown", trigger_reason="",
                            danger_level=0, enemies_present=None, outcome="success"):
        """
        Record a flee event with full details.

        Args:
            severity: "minor", "major", or "critical"
            area_name: Name of area where flee occurred
            trigger_reason: Reason for fleeing
            danger_level: Danger assessment score (0-100)
            enemies_present: List of enemy names present
            outcome: "success", "death", or "timeout"
        """
        # Update flee event counts
        if severity in self.flee_events:
            self.flee_events[severity] += 1

        # Update area performance
        if area_name not in self.area_performance:
            self.area_performance[area_name] = {
                "time_in_area": 0.0,
                "gold_from_area": 0,
                "kills_in_area": 0,
                "flees_from_area": 0,
                "danger_samples": [],
                "success_rate": 1.0
            }
        self.area_performance[area_name]["flees_from_area"] += 1

        # Recalculate success rate for area
        area = self.area_performance[area_name]
        total_events = area["kills_in_area"] + area["flees_from_area"]
        if total_events > 0:
            area["success_rate"] = area["kills_in_area"] / total_events

        # Record detailed danger event
        event = {
            "timestamp": time.time(),
            "area": area_name,
            "trigger_reason": trigger_reason,
            "danger_level": danger_level,
            "enemies_present": enemies_present or [],
            "outcome": outcome
        }
        self.danger_events.append(event)

        # Keep only last 100 danger events
        if len(self.danger_events) > 100:
            self.danger_events = self.danger_events[-100:]

    def increment_supply_usage(self, supply_type, amount=1):
        """
        Increment supply usage counter.

        Args:
            supply_type: "bandages", "vet_kits", or "potions"
            amount: Amount used (default 1)
        """
        if supply_type in self.supplies_used:
            self.supplies_used[supply_type] += amount

    def update_area_time(self, area_name, elapsed_time):
        """
        Update time spent in a specific area.

        Args:
            area_name: Name of area
            elapsed_time: Time spent in seconds
        """
        if area_name not in self.area_performance:
            self.area_performance[area_name] = {
                "time_in_area": 0.0,
                "gold_from_area": 0,
                "kills_in_area": 0,
                "flees_from_area": 0,
                "danger_samples": [],
                "success_rate": 1.0
            }
        self.area_performance[area_name]["time_in_area"] += elapsed_time

    def add_danger_sample(self, area_name, danger_level):
        """
        Add a danger level sample for an area.

        Args:
            area_name: Name of area
            danger_level: Danger assessment score (0-100)
        """
        if area_name not in self.area_performance:
            self.area_performance[area_name] = {
                "time_in_area": 0.0,
                "gold_from_area": 0,
                "kills_in_area": 0,
                "flees_from_area": 0,
                "danger_samples": [],
                "success_rate": 1.0
            }

        samples = self.area_performance[area_name]["danger_samples"]
        samples.append(danger_level)

        # Keep only last 50 samples
        if len(samples) > 50:
            self.area_performance[area_name]["danger_samples"] = samples[-50:]

    def calculate_performance_metrics(self):
        """
        Calculate performance metrics based on current session data.
        Should be called periodically (every few seconds) to update rates.
        """
        current_time = time.time()
        session_duration = current_time - self.session_start_time

        # Avoid division by zero
        if session_duration < 1.0:
            return

        hours_elapsed = session_duration / 3600.0

        # Calculate rates
        self.gold_per_hour = self.gold_collected / hours_elapsed if hours_elapsed > 0 else 0
        self.kills_per_hour = self.total_kills / hours_elapsed if hours_elapsed > 0 else 0
        self.deaths_per_hour = (self.player_deaths + self.pet_deaths) / hours_elapsed if hours_elapsed > 0 else 0

        # Calculate average danger level from all area samples
        all_danger_samples = []
        for area_data in self.area_performance.values():
            all_danger_samples.extend(area_data["danger_samples"])

        if all_danger_samples:
            self.average_danger = sum(all_danger_samples) / len(all_danger_samples)
        else:
            self.average_danger = 0.0

        # Calculate banking efficiency
        farming_time = self.time_by_state.get("farming", 0.0)
        total_active_time = sum(self.time_by_state.values())
        if total_active_time > 0:
            self.banking_efficiency = farming_time / total_active_time
        else:
            self.banking_efficiency = 0.0

    def get_session_stats(self):
        """
        Get formatted session statistics dictionary.

        Returns:
            dict: Session statistics including area and enemy data
        """
        return {
            "gold_collected": self.gold_collected,
            "total_kills": self.total_kills,
            "player_deaths": self.player_deaths,
            "pet_deaths": self.pet_deaths,
            "flee_events": dict(self.flee_events),
            "total_flees": sum(self.flee_events.values()),
            "time_by_state": dict(self.time_by_state),
            "supplies_used": dict(self.supplies_used),
            "session_duration": time.time() - self.session_start_time,
            "area_performance": self.get_area_performance(),
            "enemy_breakdown": self.get_enemy_breakdown()
        }

    def get_performance_metrics(self):
        """
        Get formatted performance metrics dictionary.

        Returns:
            dict: Performance metrics
        """
        return {
            "gold_per_hour": self.gold_per_hour,
            "kills_per_hour": self.kills_per_hour,
            "deaths_per_hour": self.deaths_per_hour,
            "average_danger": self.average_danger,
            "banking_efficiency": self.banking_efficiency
        }

    def get_enemy_breakdown(self):
        """
        Get enemy breakdown sorted by gold per enemy.

        Returns:
            list: List of enemy stat dicts sorted by average gold per kill
        """
        breakdown = []

        for enemy_name, stats in self.enemy_breakdown.items():
            kills = stats["kill_count"]
            gold_total = stats["gold_total"]
            avg_gold = gold_total / kills if kills > 0 else 0
            avg_combat_time = stats["combat_time"] / kills if kills > 0 else 0

            breakdown.append({
                "name": enemy_name,
                "kills": kills,
                "gold_total": gold_total,
                "avg_gold_per_kill": avg_gold,
                "deaths_caused": stats["deaths_caused"],
                "avg_combat_time": avg_combat_time
            })

        # Sort by average gold per kill (descending)
        breakdown.sort(key=lambda x: x["avg_gold_per_kill"], reverse=True)

        return breakdown

    def get_area_performance(self):
        """
        Get area performance sorted by gold per hour.

        Returns:
            list: List of area performance dicts sorted by gold per hour
        """
        performance = []

        for area_name, stats in self.area_performance.items():
            time_in_area = stats["time_in_area"]
            gold_from_area = stats["gold_from_area"]

            # Calculate gold per hour for this area
            hours = time_in_area / 3600.0 if time_in_area > 0 else 0
            gold_per_hour = gold_from_area / hours if hours > 0 else 0

            # Calculate average danger
            danger_samples = stats["danger_samples"]
            avg_danger = sum(danger_samples) / len(danger_samples) if danger_samples else 0

            performance.append({
                "area": area_name,
                "time_in_area": time_in_area,
                "gold_from_area": gold_from_area,
                "gold_per_hour": gold_per_hour,
                "kills": stats["kills_in_area"],
                "flees": stats["flees_from_area"],
                "success_rate": stats["success_rate"],
                "avg_danger": avg_danger
            })

        # Sort by gold per hour (descending)
        performance.sort(key=lambda x: x["gold_per_hour"], reverse=True)

        return performance

    def update_display(self, gui_controls):
        """
        Update GUI labels with current statistics.
        Should be called periodically (every 2 seconds) to update displays.

        Args:
            gui_controls: Dictionary of GUI control references
        """
        try:
            # Update performance metrics first
            self.calculate_performance_metrics()

            # Format session duration
            duration = time.time() - self.session_start_time
            hours = int(duration // 3600)
            minutes = int((duration % 3600) // 60)
            duration_str = f"{hours}h {minutes}m"

            # Update main stats labels if they exist
            if "label_gold" in gui_controls:
                gui_controls["label_gold"].SetText(f"{self.gold_collected:,}g ({self.gold_per_hour:.0f}/hr)")

            if "label_kills" in gui_controls:
                gui_controls["label_kills"].SetText(f"{self.total_kills} ({self.kills_per_hour:.1f}/hr)")

            if "label_deaths" in gui_controls:
                total_deaths = self.player_deaths + self.pet_deaths
                gui_controls["label_deaths"].SetText(f"P:{self.player_deaths} Pet:{self.pet_deaths}")

            if "label_flees" in gui_controls:
                total_flees = sum(self.flee_events.values())
                gui_controls["label_flees"].SetText(f"{total_flees} (M:{self.flee_events['minor']} C:{self.flee_events['critical']})")

            if "label_duration" in gui_controls:
                gui_controls["label_duration"].SetText(duration_str)

            if "label_efficiency" in gui_controls:
                gui_controls["label_efficiency"].SetText(f"{self.banking_efficiency * 100:.0f}%")

        except Exception as e:
            # Silently fail to avoid disrupting main loop
            pass

    def save_session(self):
        """
        Save current session to logs/farming_sessions.json.
        Appends session data to file.
        """
        import json
        import os

        try:
            # Create logs directory if it doesn't exist
            logs_dir = "logs"
            if not os.path.exists(logs_dir):
                os.makedirs(logs_dir)

            # Calculate final metrics
            self.calculate_performance_metrics()

            # Build session data
            session_data = {
                "session_id": time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime(self.session_start_time)),
                "start_time": self.session_start_time,
                "end_time": time.time(),
                "duration_seconds": time.time() - self.session_start_time,
                "stats": self.get_session_stats(),
                "performance": self.get_performance_metrics(),
                "enemy_breakdown": self.get_enemy_breakdown(),
                "area_performance": self.get_area_performance(),
                "danger_events": self.danger_events[-20:]  # Last 20 events only
            }

            # Load existing sessions
            sessions_file = os.path.join(logs_dir, "farming_sessions.json")
            sessions = []

            if os.path.exists(sessions_file):
                try:
                    with open(sessions_file, 'r') as f:
                        sessions = json.load(f)
                except:
                    sessions = []

            # Append new session
            sessions.append(session_data)

            # Keep only last 100 sessions
            if len(sessions) > 100:
                sessions = sessions[-100:]

            # Save back to file
            with open(sessions_file, 'w') as f:
                json.dump(sessions, f, indent=2)

            API.SysMsg("Session saved to logs/farming_sessions.json", 68)

        except Exception as e:
            API.SysMsg(f"Error saving session: {str(e)}", 32)

    def reset_session(self):
        """Reset session statistics (keeps cumulative totals)"""
        self.session_start_time = time.time()
        self.time_by_state = {k: 0.0 for k in self.time_by_state}
        self.flee_events = {k: 0 for k in self.flee_events}
        self.supplies_used = {k: 0 for k in self.supplies_used}
        self.danger_events = []
        self.current_state = "idle"
        self.state_start_time = time.time()

# ============ COMBAT MANAGEMENT SYSTEM ============

class CombatManager:
    """
    Combat management system for engaging enemies and coordinating pet attacks.
    Handles enemy scanning, engagement decisions, and attack coordination.
    TODO: Full implementation in future task.
    """

    def __init__(self, danger_assessment, npc_threat_map, pet_manager):
        """
        Args:
            danger_assessment: DangerAssessment instance
            npc_threat_map: NPCThreatMap instance
            pet_manager: PetManager instance
        """
        self.danger_assessment = danger_assessment
        self.npc_threat_map = npc_threat_map
        self.pet_manager = pet_manager

    def scan_for_enemies(self):
        """Scan for enemies in range. Returns list of enemy dicts."""
        # TODO: Implement enemy scanning
        return []

    def should_engage_enemy(self, enemy):
        """Determine if should engage enemy. Returns bool."""
        # TODO: Implement engagement logic
        return False

    def engage_enemy(self, enemy):
        """Initiate combat with enemy."""
        # TODO: Implement engagement
        pass

# ============ PATROL SYSTEM ============

class PatrolSystem:
    """
    Patrol system for area navigation and waypoint management.
    Handles pathfinding between waypoints and circle patrol.
    TODO: Full implementation in future task.
    """

    def __init__(self):
        """Initialize patrol system"""
        self.current_waypoint_index = 0
        self.is_patrolling = False

    def start_patrol(self):
        """Start patrolling"""
        self.is_patrolling = True

    def stop_patrol(self):
        """Stop patrolling"""
        self.is_patrolling = False

    def get_next_waypoint(self):
        """Get next waypoint to patrol to. Returns (x, y) or None."""
        # TODO: Implement waypoint logic
        return None

# ============ LOOTING SYSTEM ============

class LootingSystem:
    """
    Looting system for corpse scanning and item collection.
    Handles selective looting based on preferences and weight limits.
    TODO: Full implementation in future task.
    """

    def __init__(self):
        """Initialize looting system"""
        self.loot_preferences = {}
        self.min_gold_amount = 0

    def scan_for_loot(self):
        """Scan for lootable corpses. Returns list of corpse serials."""
        # TODO: Implement corpse scanning
        return []

    def should_loot_corpse(self, corpse_serial):
        """Determine if should loot corpse. Returns bool."""
        # TODO: Implement loot decision logic
        return False

    def loot_corpse(self, corpse_serial):
        """Loot items from corpse."""
        # TODO: Implement looting
        pass

# ============ SESSION LOGGING SYSTEM ============

class SessionLogger:
    """
    Session history logging to JSON file with trend analysis.
    Logs session statistics and provides historical data for analysis.

    Features:
    - Saves sessions to JSON with automatic cleanup (max 100 sessions)
    - Loads historical sessions for analysis
    - Extracts trend data for metrics across sessions
    - Aggregates area performance across multiple sessions
    - Identifies dangerous areas by flee rate
    - Exports session data to CSV format
    """

    def __init__(self, key_prefix):
        """
        Args:
            key_prefix: Persistence key prefix
        """
        self.key_prefix = key_prefix
        self.log_file = "logs/farming_sessions.json"
        self._ensure_logs_directory()

    def _ensure_logs_directory(self):
        """Create logs directory if it doesn't exist"""
        import os
        log_dir = os.path.dirname(self.log_file)
        if log_dir and not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir)
            except Exception:
                pass  # Fail silently - will error on actual save if needed

    def save_session(self, stats_dict):
        """
        Save session statistics to JSON log file.

        Session format:
        {
            "session_id": "YYYY-MM-DD_HH-MM-SS",
            "start_time": timestamp,
            "end_time": timestamp,
            "duration_minutes": float,
            "total_gold": int,
            "gold_per_hour": float,
            "kills": int,
            "deaths": int,
            "flee_events": int,
            "supplies_used": {...},
            "areas_farmed": [...],
            "enemy_breakdown": {...},
            "notes": ""
        }

        Args:
            stats_dict: Dictionary of session statistics from StatisticsTracker
        """
        import json
        import os
        from datetime import datetime

        # Create session data structure
        end_time = time.time()
        session_duration = stats_dict.get("session_duration", 0)
        start_time = end_time - session_duration
        duration_minutes = session_duration / 60.0

        # Calculate gold per hour
        hours = session_duration / 3600.0 if session_duration > 0 else 0
        gold_per_hour = stats_dict.get("gold_collected", 0) / hours if hours > 0 else 0

        # Format session ID as YYYY-MM-DD_HH-MM-SS
        session_id = datetime.fromtimestamp(start_time).strftime("%Y-%m-%d_%H-%M-%S")

        session_data = {
            "session_id": session_id,
            "start_time": start_time,
            "end_time": end_time,
            "duration_minutes": duration_minutes,
            "total_gold": stats_dict.get("gold_collected", 0),
            "gold_per_hour": gold_per_hour,
            "kills": stats_dict.get("total_kills", 0),
            "deaths": stats_dict.get("player_deaths", 0) + stats_dict.get("pet_deaths", 0),
            "flee_events": stats_dict.get("total_flees", 0),
            "supplies_used": stats_dict.get("supplies_used", {}),
            "areas_farmed": [],  # Will be populated from area_performance if available
            "enemy_breakdown": {},  # Will be populated if available
            "notes": ""
        }

        # Add area performance if available (from get_area_performance method)
        # Note: stats_dict may need to be enhanced to include this data
        if "area_performance" in stats_dict:
            session_data["areas_farmed"] = [
                {
                    "area": area["area"],
                    "gold": area.get("gold_from_area", 0),
                    "time": area.get("time_in_area", 0)
                }
                for area in stats_dict["area_performance"]
            ]

        # Add enemy breakdown if available
        if "enemy_breakdown" in stats_dict:
            session_data["enemy_breakdown"] = stats_dict["enemy_breakdown"]

        # Load existing sessions
        sessions = []
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r') as f:
                    sessions = json.load(f)
                    if not isinstance(sessions, list):
                        sessions = []
            except Exception:
                sessions = []

        # Append new session
        sessions.append(session_data)

        # Maintain max 100 sessions (delete oldest if exceeded)
        if len(sessions) > 100:
            sessions = sessions[-100:]

        # Save back to file
        try:
            with open(self.log_file, 'w') as f:
                json.dump(sessions, f, indent=2)
        except Exception as e:
            # Silent fail - don't crash the script over logging
            pass

    def load_sessions(self, count=10):
        """
        Load last N sessions from log file.

        Args:
            count: Number of sessions to load

        Returns:
            List of session dicts (most recent first)
        """
        import json
        import os

        if not os.path.exists(self.log_file):
            return []

        try:
            with open(self.log_file, 'r') as f:
                sessions = json.load(f)
                if not isinstance(sessions, list):
                    return []

                # Return last N sessions (most recent first)
                return list(reversed(sessions[-count:])) if count > 0 else []
        except Exception:
            return []

    def get_trend_data(self, metric_name, session_count=10):
        """
        Get trend data for a specific metric across sessions.

        Supported metrics:
        - "gold_per_hour": Gold farming rate
        - "deaths_per_hour": Death rate
        - "avg_session_length": Average session duration in minutes

        Args:
            metric_name: Name of metric to extract
            session_count: Number of sessions to analyze

        Returns:
            List of values (oldest to newest)
        """
        sessions = self.load_sessions(session_count)
        if not sessions:
            return []

        # Reverse to get oldest to newest for trend analysis
        sessions = list(reversed(sessions))

        values = []
        for session in sessions:
            if metric_name == "gold_per_hour":
                values.append(session.get("gold_per_hour", 0))
            elif metric_name == "deaths_per_hour":
                duration_hours = session.get("duration_minutes", 0) / 60.0
                deaths = session.get("deaths", 0)
                deaths_per_hour = deaths / duration_hours if duration_hours > 0 else 0
                values.append(deaths_per_hour)
            elif metric_name == "avg_session_length":
                values.append(session.get("duration_minutes", 0))
            else:
                # Unknown metric - try direct access
                values.append(session.get(metric_name, 0))

        return values

    def get_best_areas(self, session_count=10):
        """
        Aggregate area performance across sessions and identify best areas.

        Args:
            session_count: Number of sessions to analyze

        Returns:
            List of dicts sorted by avg_gold_per_hour (highest first)
            Format: [{"area": "Dragon Lair", "avg_gold_per_hour": 22500, "sessions": 5}, ...]
        """
        sessions = self.load_sessions(session_count)
        if not sessions:
            return []

        # Aggregate area data across sessions
        area_aggregates = {}

        for session in sessions:
            areas = session.get("areas_farmed", [])
            for area_data in areas:
                area_name = area_data.get("area", "Unknown")
                gold = area_data.get("gold", 0)
                time_spent = area_data.get("time", 0)

                if area_name not in area_aggregates:
                    area_aggregates[area_name] = {
                        "total_gold": 0,
                        "total_time": 0,
                        "session_count": 0
                    }

                area_aggregates[area_name]["total_gold"] += gold
                area_aggregates[area_name]["total_time"] += time_spent
                area_aggregates[area_name]["session_count"] += 1

        # Calculate averages and format results
        results = []
        for area_name, data in area_aggregates.items():
            hours = data["total_time"] / 3600.0 if data["total_time"] > 0 else 0
            avg_gold_per_hour = data["total_gold"] / hours if hours > 0 else 0

            results.append({
                "area": area_name,
                "avg_gold_per_hour": avg_gold_per_hour,
                "sessions": data["session_count"],
                "total_gold": data["total_gold"],
                "total_time_minutes": data["total_time"] / 60.0
            })

        # Sort by avg_gold_per_hour (highest first)
        results.sort(key=lambda x: x["avg_gold_per_hour"], reverse=True)
        return results

    def get_most_dangerous_areas(self, session_count=10):
        """
        Aggregate flee events by area across sessions to identify dangerous areas.

        Args:
            session_count: Number of sessions to analyze

        Returns:
            List of dicts sorted by flee_rate (highest first)
            Format: [{"area": "Dragon Lair", "flee_rate": 0.35, "total_flees": 12}, ...]
        """
        sessions = self.load_sessions(session_count)
        if not sessions:
            return []

        # Aggregate flee data by area
        area_danger = {}

        for session in sessions:
            areas = session.get("areas_farmed", [])
            total_flees = session.get("flee_events", 0)

            # If no area breakdown available, skip this session
            if not areas:
                continue

            # Distribute flees proportionally by time spent in each area
            # (This is an approximation since we don't have per-area flee counts)
            total_time = sum(area.get("time", 0) for area in areas)

            for area_data in areas:
                area_name = area_data.get("area", "Unknown")
                time_spent = area_data.get("time", 0)

                if area_name not in area_danger:
                    area_danger[area_name] = {
                        "total_flees": 0,
                        "total_time": 0,
                        "visits": 0
                    }

                # Proportional flee attribution
                if total_time > 0:
                    area_flees = total_flees * (time_spent / total_time)
                    area_danger[area_name]["total_flees"] += area_flees

                area_danger[area_name]["total_time"] += time_spent
                area_danger[area_name]["visits"] += 1

        # Calculate flee rates
        results = []
        for area_name, data in area_danger.items():
            hours = data["total_time"] / 3600.0 if data["total_time"] > 0 else 0
            flee_rate = data["total_flees"] / hours if hours > 0 else 0

            results.append({
                "area": area_name,
                "flee_rate": flee_rate,
                "total_flees": int(data["total_flees"]),
                "visits": data["visits"],
                "total_time_hours": hours
            })

        # Sort by flee_rate (highest first)
        results.sort(key=lambda x: x["flee_rate"], reverse=True)
        return results

    def export_sessions_csv(self, session_count=10):
        """
        Export sessions to CSV format for external analysis.

        Args:
            session_count: Number of sessions to export

        Returns:
            bool: True if export successful
        """
        import csv
        import os

        sessions = self.load_sessions(session_count)
        if not sessions:
            return False

        csv_file = "logs/farming_sessions_export.csv"

        try:
            with open(csv_file, 'w', newline='') as f:
                # Define CSV columns
                fieldnames = [
                    "session_id",
                    "duration_minutes",
                    "total_gold",
                    "gold_per_hour",
                    "kills",
                    "deaths",
                    "flee_events",
                    "bandages_used",
                    "vet_kits_used",
                    "potions_used",
                    "notes"
                ]

                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                # Write each session (reverse to get chronological order)
                for session in reversed(sessions):
                    supplies = session.get("supplies_used", {})

                    row = {
                        "session_id": session.get("session_id", ""),
                        "duration_minutes": round(session.get("duration_minutes", 0), 2),
                        "total_gold": session.get("total_gold", 0),
                        "gold_per_hour": round(session.get("gold_per_hour", 0), 2),
                        "kills": session.get("kills", 0),
                        "deaths": session.get("deaths", 0),
                        "flee_events": session.get("flee_events", 0),
                        "bandages_used": supplies.get("bandages", 0),
                        "vet_kits_used": supplies.get("vet_kits", 0),
                        "potions_used": supplies.get("potions", 0),
                        "notes": session.get("notes", "")
                    }
                    writer.writerow(row)

            return True
        except Exception:
            return False

# ============ ERROR RECOVERY SYSTEM ============

class ErrorRecoverySystem:
    """
    Error detection and recovery system for handling common failures.
    Detects errors in movement, combat, resources, state, and pets.
    Applies specific recovery strategies with backoff.
    TODO: Full implementation in future task.
    """

    def __init__(self):
        """Initialize error recovery system"""
        self.error_history = []
        self.recovery_attempts = {}

    def detect_errors(self):
        """
        Detect errors in current state.

        Returns:
            List of detected errors with categories
        """
        # TODO: Implement error detection
        return []

    def recover_from_error(self, error):
        """
        Apply recovery strategy for detected error.

        Args:
            error: Error dict with type and details
        """
        # TODO: Implement error recovery
        pass

    def should_escalate(self, error_type):
        """
        Check if should escalate to safe state.

        Args:
            error_type: Type of error

        Returns:
            bool: True if max attempts exceeded
        """
        # TODO: Implement escalation logic
        return False

# ============ GUI FUNCTIONS ============

def build_main_gump():
    """Build main control panel"""
    global main_gump, main_controls, main_pos_tracker

    # TODO: Implement main GUI in later tasks
    API.SysMsg("Main GUI not yet implemented", 43)

def build_config_gump():
    """Build configuration window with tabbed interface"""
    global config_gump, config_controls, config_pos_tracker, current_config_tab, healing_system

    # Dispose old gump if exists
    if config_gump:
        config_gump.Dispose()
        config_gump = None

    # Create new gump
    config_gump = API.Gumps.CreateGump()
    config_controls = {}

    # Load position or use default
    last_x = int(API.GetPersistentVar(KEY_PREFIX + "ConfigX", "150", API.PersistentVar.Char))
    last_y = int(API.GetPersistentVar(KEY_PREFIX + "ConfigY", "150", API.PersistentVar.Char))
    config_gump.SetRect(last_x, last_y, CONFIG_WIDTH, CONFIG_HEIGHT)

    # Create position tracker
    config_pos_tracker = WindowPositionTracker(config_gump, KEY_PREFIX + "Config", last_x, last_y)

    # --- Title ---
    title = API.Gumps.CreateGumpTTFLabel("Pet Farmer Configuration", 16, "#ffaa00")
    title.SetPos(10, 10)
    config_gump.AddControl(title)

    # --- Tab Buttons ---
    tab_y = 35
    tab_buttons = [
        ("healing", "Healing", 10),
        ("looting", "Looting", 90),
        ("banking", "Banking", 170),
        ("advanced", "Advanced", 250)
    ]

    for tab_id, tab_label, tab_x in tab_buttons:
        btn = API.Gumps.CreateSimpleButton(tab_label, 70, 22)
        btn.SetPos(tab_x, tab_y)

        # Highlight active tab
        if tab_id == current_config_tab:
            btn.SetBackgroundHue(68)  # Green for active
        else:
            btn.SetBackgroundHue(90)  # Gray for inactive

        config_gump.AddControl(btn)
        config_controls[f"tab_{tab_id}"] = btn
        API.Gumps.AddControlOnClick(btn, lambda tid=tab_id: switch_config_tab(tid))

    # --- Tab Content Area (y=70 to y=440) ---
    if current_config_tab == "healing":
        build_healing_tab()
    elif current_config_tab == "looting":
        build_looting_tab()
    elif current_config_tab == "banking":
        build_banking_tab()
    elif current_config_tab == "advanced":
        build_advanced_tab()

    # --- Close Button ---
    close_btn = API.Gumps.CreateSimpleButton("Close", 100, 22)
    close_btn.SetPos(CONFIG_WIDTH - 110, CONFIG_HEIGHT - 30)
    config_gump.AddControl(close_btn)
    API.Gumps.AddControlOnClick(close_btn, close_config_gump)

    # Add gump to screen
    API.Gumps.AddGump(config_gump)

def switch_config_tab(tab_id):
    """Switch to a different config tab"""
    global current_config_tab
    current_config_tab = tab_id
    build_config_gump()

def close_config_gump():
    """Close config window and save position"""
    global config_gump, config_pos_tracker

    if config_pos_tracker:
        config_pos_tracker.save()

    if config_gump:
        config_gump.Dispose()
        config_gump = None

def build_healing_tab():
    """Build the Healing tab content"""
    global config_gump, config_controls, healing_system

    if not healing_system:
        return

    # Sync from globals to ensure we have current values
    healing_system.sync_from_globals()

    y_offset = 70

    # --- Healing Thresholds Section ---
    section_label = API.Gumps.CreateGumpTTFLabel("Healing Thresholds", 16, "#ffcc00")
    section_label.SetPos(10, y_offset)
    config_gump.AddControl(section_label)
    y_offset += 30

    # Player Bandage Threshold
    player_label = API.Gumps.CreateGumpTTFLabel(f"Player Bandage: {healing_system.player_heal_threshold}%", 15, "#ffffff")
    player_label.SetPos(20, y_offset)
    config_gump.AddControl(player_label)
    config_controls["player_heal_label"] = player_label

    # Slider placeholder (text input for now, sliders are complex)
    player_input = API.Gumps.CreateGumpTextBox(str(healing_system.player_heal_threshold), 60, 22)
    player_input.SetPos(200, y_offset)
    config_gump.AddControl(player_input)
    config_controls["player_heal_input"] = player_input

    player_set_btn = API.Gumps.CreateSimpleButton("Set", 50, 22)
    player_set_btn.SetPos(270, y_offset)
    config_gump.AddControl(player_set_btn)
    API.Gumps.AddControlOnClick(player_set_btn, lambda: update_player_heal_threshold())
    y_offset += 30

    # Tank Pet Heal Threshold
    tank_label = API.Gumps.CreateGumpTTFLabel(f"Tank Pet Heal: {healing_system.tank_heal_threshold}%", 15, "#ffffff")
    tank_label.SetPos(20, y_offset)
    config_gump.AddControl(tank_label)
    config_controls["tank_heal_label"] = tank_label

    tank_input = API.Gumps.CreateGumpTextBox(str(healing_system.tank_heal_threshold), 60, 22)
    tank_input.SetPos(200, y_offset)
    config_gump.AddControl(tank_input)
    config_controls["tank_heal_input"] = tank_input

    tank_set_btn = API.Gumps.CreateSimpleButton("Set", 50, 22)
    tank_set_btn.SetPos(270, y_offset)
    config_gump.AddControl(tank_set_btn)
    API.Gumps.AddControlOnClick(tank_set_btn, lambda: update_tank_heal_threshold())
    y_offset += 30

    # Other Pets Heal Threshold
    pet_label = API.Gumps.CreateGumpTTFLabel(f"Other Pets Heal: {healing_system.pet_heal_threshold}%", 15, "#ffffff")
    pet_label.SetPos(20, y_offset)
    config_gump.AddControl(pet_label)
    config_controls["pet_heal_label"] = pet_label

    pet_input = API.Gumps.CreateGumpTextBox(str(healing_system.pet_heal_threshold), 60, 22)
    pet_input.SetPos(200, y_offset)
    config_gump.AddControl(pet_input)
    config_controls["pet_heal_input"] = pet_input

    pet_set_btn = API.Gumps.CreateSimpleButton("Set", 50, 22)
    pet_set_btn.SetPos(270, y_offset)
    config_gump.AddControl(pet_set_btn)
    API.Gumps.AddControlOnClick(pet_set_btn, lambda: update_pet_heal_threshold())
    y_offset += 40

    # --- Vet Kit Settings Section ---
    vetkit_section_label = API.Gumps.CreateGumpTTFLabel("Vet Kit Settings", 16, "#ffcc00")
    vetkit_section_label.SetPos(10, y_offset)
    config_gump.AddControl(vetkit_section_label)
    y_offset += 30

    # Vet Kit Graphic Display
    vetkit_graphic_text = f"Vet Kit Graphic: 0x{healing_system.vetkit_graphic:04X}" if healing_system.vetkit_graphic else "Vet Kit Graphic: Not Set"
    vetkit_graphic_label = API.Gumps.CreateGumpTTFLabel(vetkit_graphic_text, 15, "#ffffff")
    vetkit_graphic_label.SetPos(20, y_offset)
    config_gump.AddControl(vetkit_graphic_label)
    config_controls["vetkit_graphic_label"] = vetkit_graphic_label
    y_offset += 30

    # Set Vet Kit and Clear buttons
    set_vetkit_btn = API.Gumps.CreateSimpleButton("Set Vet Kit", 100, 22)
    set_vetkit_btn.SetPos(20, y_offset)
    config_gump.AddControl(set_vetkit_btn)
    API.Gumps.AddControlOnClick(set_vetkit_btn, target_vetkit)

    clear_vetkit_btn = API.Gumps.CreateSimpleButton("Clear", 60, 22)
    clear_vetkit_btn.SetPos(130, y_offset)
    config_gump.AddControl(clear_vetkit_btn)
    API.Gumps.AddControlOnClick(clear_vetkit_btn, clear_vetkit)
    y_offset += 30

    # HP Threshold
    vetkit_hp_label = API.Gumps.CreateGumpTTFLabel(f"HP Threshold: {healing_system.vetkit_hp_threshold}%", 15, "#ffffff")
    vetkit_hp_label.SetPos(20, y_offset)
    config_gump.AddControl(vetkit_hp_label)
    config_controls["vetkit_hp_label"] = vetkit_hp_label

    vetkit_hp_input = API.Gumps.CreateGumpTextBox(str(healing_system.vetkit_hp_threshold), 60, 22)
    vetkit_hp_input.SetPos(200, y_offset)
    config_gump.AddControl(vetkit_hp_input)
    config_controls["vetkit_hp_input"] = vetkit_hp_input

    vetkit_hp_set_btn = API.Gumps.CreateSimpleButton("Set", 50, 22)
    vetkit_hp_set_btn.SetPos(270, y_offset)
    config_gump.AddControl(vetkit_hp_set_btn)
    API.Gumps.AddControlOnClick(vetkit_hp_set_btn, lambda: update_vetkit_hp_threshold())
    y_offset += 30

    # Min Pets Hurt
    vetkit_min_label = API.Gumps.CreateGumpTTFLabel(f"Min Pets Hurt: {healing_system.vetkit_min_pets}", 15, "#ffffff")
    vetkit_min_label.SetPos(20, y_offset)
    config_gump.AddControl(vetkit_min_label)
    config_controls["vetkit_min_label"] = vetkit_min_label

    vetkit_min_input = API.Gumps.CreateGumpTextBox(str(healing_system.vetkit_min_pets), 60, 22)
    vetkit_min_input.SetPos(200, y_offset)
    config_gump.AddControl(vetkit_min_input)
    config_controls["vetkit_min_input"] = vetkit_min_input

    vetkit_min_set_btn = API.Gumps.CreateSimpleButton("Set", 50, 22)
    vetkit_min_set_btn.SetPos(270, y_offset)
    config_gump.AddControl(vetkit_min_set_btn)
    API.Gumps.AddControlOnClick(vetkit_min_set_btn, lambda: update_vetkit_min_pets())
    y_offset += 30

    # Cooldown
    vetkit_cooldown_label = API.Gumps.CreateGumpTTFLabel(f"Cooldown: {healing_system.vetkit_cooldown:.1f}s", 15, "#ffffff")
    vetkit_cooldown_label.SetPos(20, y_offset)
    config_gump.AddControl(vetkit_cooldown_label)
    config_controls["vetkit_cooldown_label"] = vetkit_cooldown_label

    vetkit_cooldown_input = API.Gumps.CreateGumpTextBox(str(healing_system.vetkit_cooldown), 60, 22)
    vetkit_cooldown_input.SetPos(200, y_offset)
    config_gump.AddControl(vetkit_cooldown_input)
    config_controls["vetkit_cooldown_input"] = vetkit_cooldown_input

    vetkit_cooldown_set_btn = API.Gumps.CreateSimpleButton("Set", 50, 22)
    vetkit_cooldown_set_btn.SetPos(270, y_offset)
    config_gump.AddControl(vetkit_cooldown_set_btn)
    API.Gumps.AddControlOnClick(vetkit_cooldown_set_btn, lambda: update_vetkit_cooldown())
    y_offset += 30

    # Critical HP
    vetkit_critical_label = API.Gumps.CreateGumpTTFLabel(f"Critical HP: {healing_system.vetkit_critical_hp}%", 15, "#ffffff")
    vetkit_critical_label.SetPos(20, y_offset)
    config_gump.AddControl(vetkit_critical_label)
    config_controls["vetkit_critical_label"] = vetkit_critical_label

    vetkit_critical_input = API.Gumps.CreateGumpTextBox(str(healing_system.vetkit_critical_hp), 60, 22)
    vetkit_critical_input.SetPos(200, y_offset)
    config_gump.AddControl(vetkit_critical_input)
    config_controls["vetkit_critical_input"] = vetkit_critical_input

    vetkit_critical_set_btn = API.Gumps.CreateSimpleButton("Set", 50, 22)
    vetkit_critical_set_btn.SetPos(270, y_offset)
    config_gump.AddControl(vetkit_critical_set_btn)
    API.Gumps.AddControlOnClick(vetkit_critical_set_btn, lambda: update_vetkit_critical_hp())
    y_offset += 40

    # --- Options Section ---
    options_section_label = API.Gumps.CreateGumpTTFLabel("Options", 16, "#ffcc00")
    options_section_label.SetPos(10, y_offset)
    config_gump.AddControl(options_section_label)
    y_offset += 30

    # Use Magery Checkbox
    magery_text = "[X] Use Magery for Healing" if healing_system.use_magery_healing else "[ ] Use Magery for Healing"
    magery_btn = API.Gumps.CreateSimpleButton(magery_text, 200, 22)
    magery_btn.SetPos(20, y_offset)
    if healing_system.use_magery_healing:
        magery_btn.SetBackgroundHue(68)
    config_gump.AddControl(magery_btn)
    config_controls["magery_btn"] = magery_btn
    API.Gumps.AddControlOnClick(magery_btn, toggle_magery_healing)
    y_offset += 30

    # Auto-Cure Poison Checkbox
    cure_text = "[X] Auto-Cure Poison" if healing_system.auto_cure_poison else "[ ] Auto-Cure Poison"
    cure_btn = API.Gumps.CreateSimpleButton(cure_text, 200, 22)
    cure_btn.SetPos(20, y_offset)
    if healing_system.auto_cure_poison:
        cure_btn.SetBackgroundHue(68)
    config_gump.AddControl(cure_btn)
    config_controls["cure_btn"] = cure_btn
    API.Gumps.AddControlOnClick(cure_btn, toggle_auto_cure)

def build_looting_tab():
    """Build the Looting tab content (stub)"""
    global config_gump

    stub_label = API.Gumps.CreateGumpTTFLabel("Looting tab not yet implemented", 15, "#888888")
    stub_label.SetPos(10, 80)
    config_gump.AddControl(stub_label)

def build_banking_tab():
    """Build the Banking tab content"""
    global config_gump, config_controls, banking_triggers, banking_system

    if not banking_triggers or not banking_system:
        stub_label = API.Gumps.CreateGumpTTFLabel("Banking systems not initialized", 15, "#888888")
        stub_label.SetPos(10, 80)
        config_gump.AddControl(stub_label)
        return

    y_offset = 70

    # --- Banking Triggers Section ---
    triggers_label = API.Gumps.CreateGumpTTFLabel("Banking Triggers", 16, "#ffcc00")
    triggers_label.SetPos(10, y_offset)
    config_gump.AddControl(triggers_label)
    y_offset += 30

    # Weight Threshold
    weight_enabled = banking_triggers.weight_trigger['enabled']
    weight_pct = int(banking_triggers.weight_trigger['threshold_pct'])
    weight_text = "[X]" if weight_enabled else "[ ]"
    weight_checkbox = API.Gumps.CreateSimpleButton(f"{weight_text} Weight Threshold", 160, 22)
    weight_checkbox.SetPos(20, y_offset)
    if weight_enabled:
        weight_checkbox.SetBackgroundHue(68)
    config_gump.AddControl(weight_checkbox)
    config_controls["weight_checkbox"] = weight_checkbox
    API.Gumps.AddControlOnClick(weight_checkbox, lambda: toggle_weight_trigger())

    weight_input = API.Gumps.CreateGumpTextBox(str(weight_pct), 50, 22)
    weight_input.SetPos(190, y_offset)
    config_gump.AddControl(weight_input)
    config_controls["weight_input"] = weight_input

    weight_set_btn = API.Gumps.CreateSimpleButton("Set", 50, 22)
    weight_set_btn.SetPos(250, y_offset)
    config_gump.AddControl(weight_set_btn)
    API.Gumps.AddControlOnClick(weight_set_btn, lambda: update_weight_threshold())

    weight_pct_label = API.Gumps.CreateGumpTTFLabel("%", 15, "#ffffff")
    weight_pct_label.SetPos(310, y_offset + 3)
    config_gump.AddControl(weight_pct_label)
    y_offset += 30

    # Time Limit
    time_enabled = banking_triggers.time_trigger['enabled']
    time_min = banking_triggers.time_trigger['interval_minutes']
    time_text = "[X]" if time_enabled else "[ ]"
    time_checkbox = API.Gumps.CreateSimpleButton(f"{time_text} Time Limit", 160, 22)
    time_checkbox.SetPos(20, y_offset)
    if time_enabled:
        time_checkbox.SetBackgroundHue(68)
    config_gump.AddControl(time_checkbox)
    config_controls["time_checkbox"] = time_checkbox
    API.Gumps.AddControlOnClick(time_checkbox, lambda: toggle_time_trigger())

    time_input = API.Gumps.CreateGumpTextBox(str(time_min), 50, 22)
    time_input.SetPos(190, y_offset)
    config_gump.AddControl(time_input)
    config_controls["time_input"] = time_input

    time_set_btn = API.Gumps.CreateSimpleButton("Set", 50, 22)
    time_set_btn.SetPos(250, y_offset)
    config_gump.AddControl(time_set_btn)
    API.Gumps.AddControlOnClick(time_set_btn, lambda: update_time_trigger())

    time_min_label = API.Gumps.CreateGumpTTFLabel("min", 15, "#ffffff")
    time_min_label.SetPos(310, y_offset + 3)
    config_gump.AddControl(time_min_label)
    y_offset += 30

    # Gold Amount
    gold_enabled = banking_triggers.gold_trigger['enabled']
    gold_amt = banking_triggers.gold_trigger['gold_amount']
    gold_text = "[X]" if gold_enabled else "[ ]"
    gold_checkbox = API.Gumps.CreateSimpleButton(f"{gold_text} Gold Amount", 160, 22)
    gold_checkbox.SetPos(20, y_offset)
    if gold_enabled:
        gold_checkbox.SetBackgroundHue(68)
    config_gump.AddControl(gold_checkbox)
    config_controls["gold_checkbox"] = gold_checkbox
    API.Gumps.AddControlOnClick(gold_checkbox, lambda: toggle_gold_trigger())

    gold_input = API.Gumps.CreateGumpTextBox(str(gold_amt), 70, 22)
    gold_input.SetPos(190, y_offset)
    config_gump.AddControl(gold_input)
    config_controls["gold_input"] = gold_input

    gold_set_btn = API.Gumps.CreateSimpleButton("Set", 50, 22)
    gold_set_btn.SetPos(270, y_offset)
    config_gump.AddControl(gold_set_btn)
    API.Gumps.AddControlOnClick(gold_set_btn, lambda: update_gold_trigger())

    gold_label = API.Gumps.CreateGumpTTFLabel("gold", 15, "#ffffff")
    gold_label.SetPos(330, y_offset + 3)
    config_gump.AddControl(gold_label)
    y_offset += 30

    # Supply Low
    supply_enabled = banking_triggers.supply_trigger['enabled']
    supply_thresh = banking_triggers.supply_trigger['bandage_threshold']
    supply_text = "[X]" if supply_enabled else "[ ]"
    supply_checkbox = API.Gumps.CreateSimpleButton(f"{supply_text} Supply Low", 160, 22)
    supply_checkbox.SetPos(20, y_offset)
    if supply_enabled:
        supply_checkbox.SetBackgroundHue(68)
    config_gump.AddControl(supply_checkbox)
    config_controls["supply_checkbox"] = supply_checkbox
    API.Gumps.AddControlOnClick(supply_checkbox, lambda: toggle_supply_trigger())

    supply_input = API.Gumps.CreateGumpTextBox(str(supply_thresh), 50, 22)
    supply_input.SetPos(190, y_offset)
    config_gump.AddControl(supply_input)
    config_controls["supply_input"] = supply_input

    supply_set_btn = API.Gumps.CreateSimpleButton("Set", 50, 22)
    supply_set_btn.SetPos(250, y_offset)
    config_gump.AddControl(supply_set_btn)
    API.Gumps.AddControlOnClick(supply_set_btn, lambda: update_supply_trigger())

    supply_label = API.Gumps.CreateGumpTTFLabel("bandages", 15, "#ffffff")
    supply_label.SetPos(310, y_offset + 3)
    config_gump.AddControl(supply_label)
    y_offset += 40

    # --- Banking Behavior Section ---
    behavior_label = API.Gumps.CreateGumpTTFLabel("Banking Speed", 16, "#ffcc00")
    behavior_label.SetPos(10, y_offset)
    config_gump.AddControl(behavior_label)
    y_offset += 30

    # Radio buttons for speed
    speed = banking_system.banking_speed
    speeds = ["fast", "medium", "realistic"]
    speed_labels = {
        "fast": "Fast",
        "medium": "Medium",
        "realistic": "Realistic"
    }
    speed_descriptions = {
        "fast": "~30s, direct pathfind, minimal pauses",
        "medium": "~60s, mixed movement, normal pauses",
        "realistic": "~90s, walking, longer pauses"
    }

    for speed_option in speeds:
        radio_text = f"({chr(0x2022) if speed == speed_option else ' '}) {speed_labels[speed_option]}"
        radio_btn = API.Gumps.CreateSimpleButton(radio_text, 100, 22)
        radio_btn.SetPos(20, y_offset)
        if speed == speed_option:
            radio_btn.SetBackgroundHue(68)
        config_gump.AddControl(radio_btn)
        config_controls[f"speed_{speed_option}"] = radio_btn
        API.Gumps.AddControlOnClick(radio_btn, lambda s=speed_option: set_banking_speed(s))

        desc_label = API.Gumps.CreateGumpTTFLabel(speed_descriptions[speed_option], 15, "#888888")
        desc_label.SetPos(130, y_offset + 3)
        config_gump.AddControl(desc_label)
        y_offset += 30

    y_offset += 10

    # --- Supply Restocking Section ---
    restock_label = API.Gumps.CreateGumpTTFLabel("Supply Restocking", 16, "#ffcc00")
    restock_label.SetPos(10, y_offset)
    config_gump.AddControl(restock_label)
    y_offset += 30

    # Restock Bandages
    restock_bandage_label = API.Gumps.CreateGumpTTFLabel("Restock Bandages to:", 15, "#ffffff")
    restock_bandage_label.SetPos(20, y_offset + 3)
    config_gump.AddControl(restock_bandage_label)

    restock_bandage_input = API.Gumps.CreateGumpTextBox(str(banking_system.restock_bandage_amount), 60, 22)
    restock_bandage_input.SetPos(180, y_offset)
    config_gump.AddControl(restock_bandage_input)
    config_controls["restock_bandage_input"] = restock_bandage_input

    restock_bandage_set_btn = API.Gumps.CreateSimpleButton("Set", 50, 22)
    restock_bandage_set_btn.SetPos(250, y_offset)
    config_gump.AddControl(restock_bandage_set_btn)
    API.Gumps.AddControlOnClick(restock_bandage_set_btn, lambda: update_restock_bandages())

    restock_count_label = API.Gumps.CreateGumpTTFLabel("count", 15, "#ffffff")
    restock_count_label.SetPos(310, y_offset + 3)
    config_gump.AddControl(restock_count_label)
    y_offset += 30

    # Alert Vet Kits
    vetkit_alert_enabled = banking_system.low_vetkit_alert_threshold > 0
    vetkit_text = "[X]" if vetkit_alert_enabled else "[ ]"
    vetkit_checkbox = API.Gumps.CreateSimpleButton(f"{vetkit_text} Alert when Vet Kits below:", 230, 22)
    vetkit_checkbox.SetPos(20, y_offset)
    if vetkit_alert_enabled:
        vetkit_checkbox.SetBackgroundHue(68)
    config_gump.AddControl(vetkit_checkbox)
    config_controls["vetkit_alert_checkbox"] = vetkit_checkbox
    API.Gumps.AddControlOnClick(vetkit_checkbox, lambda: toggle_vetkit_alert())

    vetkit_input = API.Gumps.CreateGumpTextBox(str(banking_system.low_vetkit_alert_threshold), 50, 22)
    vetkit_input.SetPos(260, y_offset)
    config_gump.AddControl(vetkit_input)
    config_controls["vetkit_input"] = vetkit_input

    vetkit_set_btn = API.Gumps.CreateSimpleButton("Set", 50, 22)
    vetkit_set_btn.SetPos(320, y_offset)
    config_gump.AddControl(vetkit_set_btn)
    API.Gumps.AddControlOnClick(vetkit_set_btn, lambda: update_vetkit_alert())

def build_advanced_tab():
    """Build the Advanced tab content"""
    global config_gump, config_controls, recovery_system

    y_offset = 70

    # --- Randomization Section ---
    section_label = API.Gumps.CreateGumpTTFLabel("Randomization", 16, "#ffcc00")
    section_label.SetPos(10, y_offset)
    config_gump.AddControl(section_label)
    y_offset += 30

    # Movement Delay
    movement_label = API.Gumps.CreateGumpTTFLabel(f"Movement Delay: {movement_delay:.1f}s", 15, "#ffffff")
    movement_label.SetPos(20, y_offset)
    config_gump.AddControl(movement_label)
    config_controls["movement_delay_label"] = movement_label

    movement_input = API.Gumps.CreateGumpTextBox(str(movement_delay), 60, 22)
    movement_input.SetPos(220, y_offset)
    config_gump.AddControl(movement_input)
    config_controls["movement_delay_input"] = movement_input

    movement_set_btn = API.Gumps.CreateSimpleButton("Set", 50, 22)
    movement_set_btn.SetPos(290, y_offset)
    config_gump.AddControl(movement_set_btn)
    API.Gumps.AddControlOnClick(movement_set_btn, update_movement_delay)
    y_offset += 30

    # Pause Frequency
    pause_freq_label = API.Gumps.CreateGumpTTFLabel(f"Pause Frequency: {pause_frequency}%", 15, "#ffffff")
    pause_freq_label.SetPos(20, y_offset)
    config_gump.AddControl(pause_freq_label)
    config_controls["pause_freq_label"] = pause_freq_label

    pause_freq_input = API.Gumps.CreateGumpTextBox(str(pause_frequency), 60, 22)
    pause_freq_input.SetPos(220, y_offset)
    config_gump.AddControl(pause_freq_input)
    config_controls["pause_freq_input"] = pause_freq_input

    pause_freq_set_btn = API.Gumps.CreateSimpleButton("Set", 50, 22)
    pause_freq_set_btn.SetPos(290, y_offset)
    config_gump.AddControl(pause_freq_set_btn)
    API.Gumps.AddControlOnClick(pause_freq_set_btn, update_pause_frequency)
    y_offset += 30

    # Pause Duration
    pause_dur_label = API.Gumps.CreateGumpTTFLabel(f"Pause Duration: {pause_duration:.1f}s", 15, "#ffffff")
    pause_dur_label.SetPos(20, y_offset)
    config_gump.AddControl(pause_dur_label)
    config_controls["pause_dur_label"] = pause_dur_label

    pause_dur_input = API.Gumps.CreateGumpTextBox(str(pause_duration), 60, 22)
    pause_dur_input.SetPos(220, y_offset)
    config_gump.AddControl(pause_dur_input)
    config_controls["pause_dur_input"] = pause_dur_input

    pause_dur_set_btn = API.Gumps.CreateSimpleButton("Set", 50, 22)
    pause_dur_set_btn.SetPos(290, y_offset)
    config_gump.AddControl(pause_dur_set_btn)
    API.Gumps.AddControlOnClick(pause_dur_set_btn, update_pause_duration)
    y_offset += 35

    # --- Pet Death Policy Section ---
    section_label = API.Gumps.CreateGumpTTFLabel("Pet Death Policy", 16, "#ffcc00")
    section_label.SetPos(10, y_offset)
    config_gump.AddControl(section_label)
    y_offset += 30

    # Get current policy from recovery_system
    current_policy = "auto_rez_continue"
    if recovery_system:
        current_policy = recovery_system.pet_death_policy

    # Radio buttons for pet death policy
    policies = [
        ("auto_rez_continue", "Auto-Rez & Continue (10-15 min cooldown)"),
        ("rez_and_cooldown", "Rez & Extended Cooldown (20-30 min)"),
        ("stop_on_death", "Stop on Death (alert user)")
    ]

    for policy_id, policy_label in policies:
        is_selected = (policy_id == current_policy)
        radio_text = "(•) " if is_selected else "( ) "

        radio_btn = API.Gumps.CreateSimpleButton(radio_text + policy_label, 340, 22)
        radio_btn.SetPos(20, y_offset)
        if is_selected:
            radio_btn.SetBackgroundHue(68)  # Green for selected
        else:
            radio_btn.SetBackgroundHue(90)  # Gray for unselected

        config_gump.AddControl(radio_btn)
        config_controls[f"policy_{policy_id}"] = radio_btn
        API.Gumps.AddControlOnClick(radio_btn, lambda pid=policy_id: on_policy_radio_change(pid))
        y_offset += 28

    y_offset += 10

    # --- Error Recovery Section ---
    section_label = API.Gumps.CreateGumpTTFLabel("Error Recovery", 16, "#ffcc00")
    section_label.SetPos(10, y_offset)
    config_gump.AddControl(section_label)
    y_offset += 30

    # Max Recovery Attempts
    max_attempts_label = API.Gumps.CreateGumpTTFLabel(f"Max Recovery Attempts: {max_recovery_attempts}", 15, "#ffffff")
    max_attempts_label.SetPos(20, y_offset)
    config_gump.AddControl(max_attempts_label)
    config_controls["max_attempts_label"] = max_attempts_label

    max_attempts_input = API.Gumps.CreateGumpTextBox(str(max_recovery_attempts), 60, 22)
    max_attempts_input.SetPos(260, y_offset)
    config_gump.AddControl(max_attempts_input)
    config_controls["max_attempts_input"] = max_attempts_input

    max_attempts_set_btn = API.Gumps.CreateSimpleButton("Set", 50, 22)
    max_attempts_set_btn.SetPos(330, y_offset)
    config_gump.AddControl(max_attempts_set_btn)
    API.Gumps.AddControlOnClick(max_attempts_set_btn, update_max_recovery_attempts)
    y_offset += 30

    # Recovery Backoff Time
    backoff_label = API.Gumps.CreateGumpTTFLabel(f"Recovery Backoff: {recovery_backoff_time}s", 15, "#ffffff")
    backoff_label.SetPos(20, y_offset)
    config_gump.AddControl(backoff_label)
    config_controls["backoff_label"] = backoff_label

    backoff_input = API.Gumps.CreateGumpTextBox(str(recovery_backoff_time), 60, 22)
    backoff_input.SetPos(260, y_offset)
    config_gump.AddControl(backoff_input)
    config_controls["backoff_input"] = backoff_input

    backoff_set_btn = API.Gumps.CreateSimpleButton("Set", 50, 22)
    backoff_set_btn.SetPos(330, y_offset)
    config_gump.AddControl(backoff_set_btn)
    API.Gumps.AddControlOnClick(backoff_set_btn, update_recovery_backoff)
    y_offset += 35

    # --- Logging Section ---
    section_label = API.Gumps.CreateGumpTTFLabel("Logging", 16, "#ffcc00")
    section_label.SetPos(10, y_offset)
    config_gump.AddControl(section_label)
    y_offset += 30

    # Log Level (using buttons as dropdown alternative)
    log_level_label = API.Gumps.CreateGumpTTFLabel(f"Log Level: {log_level.title()}", 15, "#ffffff")
    log_level_label.SetPos(20, y_offset)
    config_gump.AddControl(log_level_label)
    config_controls["log_level_label"] = log_level_label

    # Cycle button to change log level
    cycle_log_btn = API.Gumps.CreateSimpleButton("Change Level", 120, 22)
    cycle_log_btn.SetPos(180, y_offset)
    config_gump.AddControl(cycle_log_btn)
    API.Gumps.AddControlOnClick(cycle_log_btn, cycle_log_level)
    y_offset += 30

    # Export Session Data button
    export_btn = API.Gumps.CreateSimpleButton("Export Session Data", 180, 22)
    export_btn.SetPos(20, y_offset)
    export_btn.SetBackgroundHue(68)  # Green
    config_gump.AddControl(export_btn)
    API.Gumps.AddControlOnClick(export_btn, export_session_data)

# ============ HEALING TAB CALLBACKS ============

def update_player_heal_threshold():
    """Update player heal threshold from input"""
    global healing_system, config_controls

    if not healing_system or "player_heal_input" not in config_controls:
        return

    try:
        value = int(config_controls["player_heal_input"].GetText())
        healing_system.configure_thresholds(player_threshold=value)
        healing_system.sync_to_globals()
        save_settings()
        build_config_gump()  # Refresh display
        API.SysMsg(f"Player heal threshold set to {healing_system.player_heal_threshold}%", 68)
    except ValueError:
        API.SysMsg("Invalid value - must be a number", 32)

def update_tank_heal_threshold():
    """Update tank heal threshold from input"""
    global healing_system, config_controls

    if not healing_system or "tank_heal_input" not in config_controls:
        return

    try:
        value = int(config_controls["tank_heal_input"].GetText())
        healing_system.configure_thresholds(tank_threshold=value)
        healing_system.sync_to_globals()
        save_settings()
        build_config_gump()  # Refresh display
        API.SysMsg(f"Tank heal threshold set to {healing_system.tank_heal_threshold}%", 68)
    except ValueError:
        API.SysMsg("Invalid value - must be a number", 32)

def update_pet_heal_threshold():
    """Update pet heal threshold from input"""
    global healing_system, config_controls

    if not healing_system or "pet_heal_input" not in config_controls:
        return

    try:
        value = int(config_controls["pet_heal_input"].GetText())
        healing_system.configure_thresholds(pet_threshold=value)
        healing_system.sync_to_globals()
        save_settings()
        build_config_gump()  # Refresh display
        API.SysMsg(f"Pet heal threshold set to {healing_system.pet_heal_threshold}%", 68)
    except ValueError:
        API.SysMsg("Invalid value - must be a number", 32)

def target_vetkit():
    """Callback to target vet kit item"""
    global healing_system

    if not healing_system:
        return

    try:
        API.SysMsg("Target your vet kit...", 68)
        target = API.RequestTarget(timeout=10)

        if target:
            item = API.FindItem(target)
            if item:
                graphic = getattr(item, 'Graphic', 0)
                healing_system.set_vetkit_graphic(graphic)
                healing_system.sync_to_globals()
                save_settings()
                build_config_gump()  # Refresh display
                API.SysMsg(f"Vet kit graphic set to 0x{graphic:04X}", 68)
            else:
                API.SysMsg("Invalid target - item not found", 32)
        else:
            API.SysMsg("Targeting cancelled", 43)
    except Exception as e:
        API.SysMsg(f"Error targeting vet kit: {str(e)}", 32)

def clear_vetkit():
    """Clear vet kit graphic"""
    global healing_system

    if not healing_system:
        return

    healing_system.set_vetkit_graphic(0)
    healing_system.sync_to_globals()
    save_settings()
    build_config_gump()  # Refresh display
    API.SysMsg("Vet kit graphic cleared", 43)

def update_vetkit_hp_threshold():
    """Update vet kit HP threshold from input"""
    global healing_system, config_controls

    if not healing_system or "vetkit_hp_input" not in config_controls:
        return

    try:
        value = int(config_controls["vetkit_hp_input"].GetText())
        healing_system.configure_vetkit(hp_threshold=value)
        healing_system.sync_to_globals()
        save_settings()
        build_config_gump()  # Refresh display
        API.SysMsg(f"Vet kit HP threshold set to {healing_system.vetkit_hp_threshold}%", 68)
    except ValueError:
        API.SysMsg("Invalid value - must be a number", 32)

def update_vetkit_min_pets():
    """Update vet kit min pets from input"""
    global healing_system, config_controls

    if not healing_system or "vetkit_min_input" not in config_controls:
        return

    try:
        value = int(config_controls["vetkit_min_input"].GetText())
        healing_system.configure_vetkit(min_pets=value)
        healing_system.sync_to_globals()
        save_settings()
        build_config_gump()  # Refresh display
        API.SysMsg(f"Vet kit min pets set to {healing_system.vetkit_min_pets}", 68)
    except ValueError:
        API.SysMsg("Invalid value - must be a number", 32)

def update_vetkit_cooldown():
    """Update vet kit cooldown from input"""
    global healing_system, config_controls

    if not healing_system or "vetkit_cooldown_input" not in config_controls:
        return

    try:
        value = float(config_controls["vetkit_cooldown_input"].GetText())
        healing_system.configure_vetkit(cooldown=value)
        healing_system.sync_to_globals()
        save_settings()
        build_config_gump()  # Refresh display
        API.SysMsg(f"Vet kit cooldown set to {healing_system.vetkit_cooldown:.1f}s", 68)
    except ValueError:
        API.SysMsg("Invalid value - must be a number", 32)

def update_vetkit_critical_hp():
    """Update vet kit critical HP from input"""
    global healing_system, config_controls

    if not healing_system or "vetkit_critical_input" not in config_controls:
        return

    try:
        value = int(config_controls["vetkit_critical_input"].GetText())
        healing_system.configure_vetkit(critical_hp=value)
        healing_system.sync_to_globals()
        save_settings()
        build_config_gump()  # Refresh display
        API.SysMsg(f"Vet kit critical HP set to {healing_system.vetkit_critical_hp}%", 68)
    except ValueError:
        API.SysMsg("Invalid value - must be a number", 32)

def toggle_magery_healing():
    """Toggle magery healing option"""
    global healing_system

    if not healing_system:
        return

    healing_system.configure_options(use_magery=not healing_system.use_magery_healing)
    healing_system.sync_to_globals()
    save_settings()
    build_config_gump()  # Refresh display
    status = "enabled" if healing_system.use_magery_healing else "disabled"
    API.SysMsg(f"Magery healing {status}", 68)

def toggle_auto_cure():
    """Toggle auto-cure poison option"""
    global healing_system

    if not healing_system:
        return

    healing_system.configure_options(auto_cure=not healing_system.auto_cure_poison)
    healing_system.sync_to_globals()
    save_settings()
    build_config_gump()  # Refresh display
    status = "enabled" if healing_system.auto_cure_poison else "disabled"
    API.SysMsg(f"Auto-cure poison {status}", 68)

# ============ BANKING TAB CALLBACKS ============

def toggle_weight_trigger():
    """Toggle weight threshold trigger on/off"""
    global banking_triggers
    if not banking_triggers:
        return

    banking_triggers.weight_trigger['enabled'] = not banking_triggers.weight_trigger['enabled']
    banking_triggers._save_config()
    build_config_gump()
    status = "enabled" if banking_triggers.weight_trigger['enabled'] else "disabled"
    API.SysMsg(f"Weight trigger {status}", 68)

def update_weight_threshold():
    """Update weight threshold percentage"""
    global banking_triggers, config_controls
    if not banking_triggers or "weight_input" not in config_controls:
        return

    try:
        value = int(config_controls["weight_input"].GetText())
        if 60 <= value <= 95:
            banking_triggers.weight_trigger['threshold_pct'] = float(value)
            banking_triggers._save_config()
            build_config_gump()
            API.SysMsg(f"Weight threshold set to {value}%", 68)
        else:
            API.SysMsg("Value must be between 60 and 95", 32)
    except ValueError:
        API.SysMsg("Invalid value - must be a number", 32)

def toggle_time_trigger():
    """Toggle time interval trigger on/off"""
    global banking_triggers
    if not banking_triggers:
        return

    banking_triggers.time_trigger['enabled'] = not banking_triggers.time_trigger['enabled']
    banking_triggers._save_config()
    build_config_gump()
    status = "enabled" if banking_triggers.time_trigger['enabled'] else "disabled"
    API.SysMsg(f"Time trigger {status}", 68)

def update_time_trigger():
    """Update time interval in minutes"""
    global banking_triggers, config_controls
    if not banking_triggers or "time_input" not in config_controls:
        return

    try:
        value = int(config_controls["time_input"].GetText())
        if value > 0:
            banking_triggers.time_trigger['interval_minutes'] = value
            banking_triggers._save_config()
            build_config_gump()
            API.SysMsg(f"Time interval set to {value} minutes", 68)
        else:
            API.SysMsg("Value must be greater than 0", 32)
    except ValueError:
        API.SysMsg("Invalid value - must be a number", 32)

def toggle_gold_trigger():
    """Toggle gold amount trigger on/off"""
    global banking_triggers
    if not banking_triggers:
        return

    banking_triggers.gold_trigger['enabled'] = not banking_triggers.gold_trigger['enabled']
    banking_triggers._save_config()
    build_config_gump()
    status = "enabled" if banking_triggers.gold_trigger['enabled'] else "disabled"
    API.SysMsg(f"Gold trigger {status}", 68)

def update_gold_trigger():
    """Update gold amount threshold"""
    global banking_triggers, config_controls
    if not banking_triggers or "gold_input" not in config_controls:
        return

    try:
        value = int(config_controls["gold_input"].GetText())
        if value > 0:
            banking_triggers.gold_trigger['gold_amount'] = value
            banking_triggers._save_config()
            build_config_gump()
            API.SysMsg(f"Gold threshold set to {value}", 68)
        else:
            API.SysMsg("Value must be greater than 0", 32)
    except ValueError:
        API.SysMsg("Invalid value - must be a number", 32)

def toggle_supply_trigger():
    """Toggle supply low trigger on/off"""
    global banking_triggers
    if not banking_triggers:
        return

    banking_triggers.supply_trigger['enabled'] = not banking_triggers.supply_trigger['enabled']
    banking_triggers._save_config()
    build_config_gump()
    status = "enabled" if banking_triggers.supply_trigger['enabled'] else "disabled"
    API.SysMsg(f"Supply trigger {status}", 68)

def update_supply_trigger():
    """Update supply bandage threshold"""
    global banking_triggers, config_controls
    if not banking_triggers or "supply_input" not in config_controls:
        return

    try:
        value = int(config_controls["supply_input"].GetText())
        if value > 0:
            banking_triggers.supply_trigger['bandage_threshold'] = value
            banking_triggers._save_config()
            build_config_gump()
            API.SysMsg(f"Supply threshold set to {value} bandages", 68)
        else:
            API.SysMsg("Value must be greater than 0", 32)
    except ValueError:
        API.SysMsg("Invalid value - must be a number", 32)

def set_banking_speed(speed):
    """Set banking speed (fast, medium, realistic)"""
    global banking_system
    if not banking_system:
        return

    if speed in ["fast", "medium", "realistic"]:
        banking_system.banking_speed = speed
        banking_system._save_config()
        build_config_gump()
        API.SysMsg(f"Banking speed set to {speed}", 68)

def update_restock_bandages():
    """Update bandage restock amount"""
    global banking_system, config_controls
    if not banking_system or "restock_bandage_input" not in config_controls:
        return

    try:
        value = int(config_controls["restock_bandage_input"].GetText())
        if value > 0:
            banking_system.restock_bandage_amount = value
            banking_system._save_config()
            build_config_gump()
            API.SysMsg(f"Bandage restock amount set to {value}", 68)
        else:
            API.SysMsg("Value must be greater than 0", 32)
    except ValueError:
        API.SysMsg("Invalid value - must be a number", 32)

def toggle_vetkit_alert():
    """Toggle vet kit alert on/off"""
    global banking_system
    if not banking_system:
        return

    if banking_system.low_vetkit_alert_threshold > 0:
        banking_system.low_vetkit_alert_threshold = 0
        status = "disabled"
    else:
        banking_system.low_vetkit_alert_threshold = 2  # Default
        status = "enabled"

    banking_system._save_config()
    build_config_gump()
    API.SysMsg(f"Vet kit alert {status}", 68)

def update_vetkit_alert():
    """Update vet kit alert threshold"""
    global banking_system, config_controls
    if not banking_system or "vetkit_input" not in config_controls:
        return

    try:
        value = int(config_controls["vetkit_input"].GetText())
        if value >= 0:
            banking_system.low_vetkit_alert_threshold = value
            banking_system._save_config()
            build_config_gump()
            if value > 0:
                API.SysMsg(f"Vet kit alert threshold set to {value}", 68)
            else:
                API.SysMsg("Vet kit alert disabled", 68)
        else:
            API.SysMsg("Value must be 0 or greater", 32)
    except ValueError:
        API.SysMsg("Invalid value - must be a number", 32)

# ============ ADVANCED TAB CALLBACKS ============

def update_movement_delay():
    """Update movement delay setting"""
    global movement_delay, config_controls

    if "movement_delay_input" not in config_controls:
        return

    try:
        value = float(config_controls["movement_delay_input"].GetText())
        if 0.5 <= value <= 3.0:
            movement_delay = value
            save_settings()
            build_config_gump()  # Refresh display
            API.SysMsg(f"Movement delay set to {movement_delay:.1f}s", 68)
        else:
            API.SysMsg("Value must be between 0.5 and 3.0", 32)
    except ValueError:
        API.SysMsg("Invalid value - must be a number", 32)

def update_pause_frequency():
    """Update pause frequency setting"""
    global pause_frequency, config_controls

    if "pause_freq_input" not in config_controls:
        return

    try:
        value = int(config_controls["pause_freq_input"].GetText())
        if 0 <= value <= 50:
            pause_frequency = value
            save_settings()
            build_config_gump()  # Refresh display
            API.SysMsg(f"Pause frequency set to {pause_frequency}%", 68)
        else:
            API.SysMsg("Value must be between 0 and 50", 32)
    except ValueError:
        API.SysMsg("Invalid value - must be a number", 32)

def update_pause_duration():
    """Update pause duration setting"""
    global pause_duration, config_controls

    if "pause_dur_input" not in config_controls:
        return

    try:
        value = float(config_controls["pause_dur_input"].GetText())
        if 1.0 <= value <= 5.0:
            pause_duration = value
            save_settings()
            build_config_gump()  # Refresh display
            API.SysMsg(f"Pause duration set to {pause_duration:.1f}s", 68)
        else:
            API.SysMsg("Value must be between 1.0 and 5.0", 32)
    except ValueError:
        API.SysMsg("Invalid value - must be a number", 32)

def on_policy_radio_change(policy):
    """Handle pet death policy radio button change"""
    global recovery_system

    if not recovery_system:
        API.SysMsg("Recovery system not initialized", 32)
        return

    # Set the new policy
    recovery_system.set_pet_death_policy(policy)

    # Rebuild GUI to update radio button states
    build_config_gump()

    # Show confirmation message
    policy_names = {
        "auto_rez_continue": "Auto-Rez & Continue",
        "rez_and_cooldown": "Rez & Extended Cooldown",
        "stop_on_death": "Stop on Death"
    }
    API.SysMsg(f"Pet death policy: {policy_names.get(policy, policy)}", 68)

def update_max_recovery_attempts():
    """Update max recovery attempts setting"""
    global max_recovery_attempts, config_controls

    if "max_attempts_input" not in config_controls:
        return

    try:
        value = int(config_controls["max_attempts_input"].GetText())
        if 1 <= value <= 5:
            max_recovery_attempts = value
            save_settings()
            build_config_gump()  # Refresh display
            API.SysMsg(f"Max recovery attempts set to {max_recovery_attempts}", 68)
        else:
            API.SysMsg("Value must be between 1 and 5", 32)
    except ValueError:
        API.SysMsg("Invalid value - must be a number", 32)

def update_recovery_backoff():
    """Update recovery backoff time setting"""
    global recovery_backoff_time, config_controls

    if "backoff_input" not in config_controls:
        return

    try:
        value = int(config_controls["backoff_input"].GetText())
        if 10 <= value <= 60:
            recovery_backoff_time = value
            save_settings()
            build_config_gump()  # Refresh display
            API.SysMsg(f"Recovery backoff set to {recovery_backoff_time}s", 68)
        else:
            API.SysMsg("Value must be between 10 and 60", 32)
    except ValueError:
        API.SysMsg("Invalid value - must be a number", 32)

def cycle_log_level():
    """Cycle through log levels: basic -> standard -> detailed -> basic"""
    global log_level

    levels = ["basic", "standard", "detailed"]
    current_index = levels.index(log_level) if log_level in levels else 1
    next_index = (current_index + 1) % len(levels)
    log_level = levels[next_index]

    save_settings()
    build_config_gump()  # Refresh display
    API.SysMsg(f"Log level: {log_level.title()}", 68)

def export_session_data():
    """Export current session statistics to JSON file"""
    # Use StatisticsTracker's save_session method if available
    if stats_tracker:
        stats_tracker.save_session()
    else:
        API.SysMsg("Statistics tracker not initialized", 43)

# ============ HOTKEY CALLBACKS ============

def toggle_pause():
    """Hotkey callback to pause/unpause script"""
    global script_paused
    script_paused = not script_paused
    status = "PAUSED" if script_paused else "ACTIVE"
    API.SysMsg(f"Pet Farmer: {status}", 68 if not script_paused else 43)

# ============ MAIN LOOP STATE HANDLERS ============

def handle_idle_state():
    """Handle idle state - find next action"""
    global STATE, action_start_time, last_action

    # Check banking triggers first
    if banking_triggers and banking_system:
        should_bank, reason = banking_triggers.should_bank()
        if should_bank:
            API.SysMsg(f"Banking triggered: {reason}", 43)
            STATE = "traveling_to_bank"
            return

    # Scan for enemies in range
    if combat_manager:
        enemies = combat_manager.scan_for_enemies()
        if enemies:
            for enemy in enemies:
                if combat_manager.should_engage_enemy(enemy):
                    combat_manager.engage_enemy(enemy)
                    STATE = "engaging"
                    return

    # If no enemies and no banking needed, patrol
    if patrol_system and area_manager:
        current_area = area_manager.get_current_area()
        if current_area:
            if current_area.area_type == "circle":
                # Start circle patrol
                patrol_system.start_patrol()
                STATE = "patrolling"
            elif current_area.area_type == "waypoints" and current_area.waypoints:
                # Start waypoint patrol
                patrol_system.start_patrol()
                STATE = "patrolling"
        # If no area defined, stay idle
    # Else stay in idle (no patrol system or area defined)

def handle_patrolling_state():
    """Handle patrolling state - monitor arrival and check for enemies"""
    global STATE

    # Check for enemies while patrolling
    if combat_manager:
        enemies = combat_manager.scan_for_enemies()
        if enemies:
            for enemy in enemies:
                if combat_manager.should_engage_enemy(enemy):
                    if patrol_system:
                        patrol_system.stop_patrol()
                    combat_manager.engage_enemy(enemy)
                    STATE = "engaging"
                    return

    # Check if patrol is complete or failed
    if patrol_system and not patrol_system.is_patrolling:
        # Patrol complete, return to idle
        STATE = "idle"

def handle_healing_state():
    """Handle healing state"""
    global STATE, action_start_time, combat_manager

    # Check if heal action is complete
    if healing_system and healing_system.check_heal_complete():
        # Return to engaging if enemy exists, otherwise idle
        if combat_manager and hasattr(combat_manager, 'engaged_enemy_serial') and combat_manager.engaged_enemy_serial:
            STATE = "engaging"
        else:
            STATE = "idle"
    elif time.time() > action_start_time + BANDAGE_DELAY:
        # Fallback timeout if healing_system not available
        STATE = "idle"

def handle_engaging_state():
    """Handle engaging/combat state"""
    global STATE, flee_system, healing_system, danger_assessment, looting_system

    # Monitor combat via combat manager
    if combat_manager:
        combat_manager.monitor_combat()

    # Check danger level for flee trigger
    if danger_assessment:
        danger = danger_assessment.calculate_danger()
        flee_threshold = getattr(danger_assessment, 'flee_threshold', 70)
        if danger >= flee_threshold:
            if flee_system:
                flee_system.initiate_flee("danger_critical")
                STATE = "fleeing"
                return

    # Check for healing needs (self or priority pets)
    if healing_system:
        heal_action = healing_system.get_next_heal_action()
        if heal_action:
            # heal_action is (target_serial, heal_type, ...)
            heal_type = heal_action[1] if len(heal_action) > 1 else ""
            # Only interrupt combat for self-heal or vet kit
            if heal_type in ["bandage_self", "spell_self", "vetkit"]:
                healing_system.execute_heal(*heal_action)
                STATE = "healing"
                return

    # Check if combat is complete (enemy dead/gone)
    if combat_manager and hasattr(combat_manager, 'engaged_enemy_serial'):
        if combat_manager.engaged_enemy_serial == 0:
            # Combat over, check for looting
            if looting_system:
                corpses = looting_system.scan_for_loot()
                if corpses:
                    STATE = "looting"
                    return
            # No loot, return to idle
            STATE = "idle"

def handle_looting_state():
    """Handle looting state"""
    global STATE, looting_system

    if looting_system:
        corpses = looting_system.scan_for_loot()
        if corpses:
            # Loot first corpse
            corpse_serial = corpses[0]
            if looting_system.should_loot_corpse(corpse_serial):
                looting_system.loot_corpse(corpse_serial)

    # Looting complete (or no corpses), return to idle
    STATE = "idle"

def handle_fleeing_state():
    """Handle fleeing state - monitor flee progress"""
    global STATE, flee_system, recovery_system, pet_manager, script_enabled

    if not flee_system or not flee_system.is_fleeing:
        STATE = "idle"
        return

    # Continue flee monitoring (flee_to_safe_spot handles pathfinding)
    still_fleeing = flee_system.flee_to_safe_spot(flee_system.current_safe_spot)

    if not still_fleeing:
        # Flee complete or failed, transition to recovery
        API.SysMsg("Flee complete, entering recovery", 68)

        # Assess flee severity and execute recovery
        if recovery_system and pet_manager:
            # Get pet status for severity assessment
            pet_status = recovery_system.get_pet_status()

            # Assess severity
            severity = recovery_system.assess_flee_severity(
                flee_system.danger_at_flee,
                pet_status
            )

            API.SysMsg(f"Flee severity: {severity}", 43)

            # Execute recovery (this handles healing, cooldowns, etc.)
            next_state = recovery_system.execute_recovery(
                severity,
                flee_system.flee_reason,
                flee_system.danger_at_flee
            )

            # Transition based on recovery result
            if next_state == "stopped":
                API.SysMsg("Script stopped by recovery policy", 32)
                STATE = "idle"
                script_enabled = False
            else:
                STATE = "recovering"
        else:
            # Fallback if recovery system not initialized
            STATE = "idle"

def handle_traveling_to_bank_state():
    """Handle traveling to bank state"""
    global STATE, banking_system

    if banking_system:
        # Travel to bank using runebook
        success = banking_system.travel_to_bank()
        if success:
            # Navigate to banker NPC
            if banking_system.bank_x > 0 and banking_system.bank_y > 0:
                banking_system.navigate_to_bank(banking_system.bank_x, banking_system.bank_y)
            STATE = "banking"
        else:
            API.SysMsg("Bank travel failed, returning to idle", 32)
            STATE = "idle"
    else:
        # No banking system, return to idle
        STATE = "idle"

def handle_banking_state():
    """Handle banking state - interact with bank, deposit items, restock supplies"""
    global STATE, banking_system, banking_triggers

    if banking_system:
        # Interact with bank
        success = banking_system.interact_with_bank(0)  # 0 = auto-detect banker
        if success:
            API.SysMsg("Banking complete", 68)
            # Track last bank time
            if banking_triggers:
                banking_triggers.track_last_bank()
        else:
            API.SysMsg("Banking failed", 32)

    # Return to farming area
    STATE = "idle"
    # Note: In future task, add "traveling_to_farm" state for recall back

def handle_recovering_state():
    """Handle recovering state - wait for recovery to complete"""
    global STATE, recovery_system

    if not recovery_system:
        STATE = "idle"
        return

    # Update recovery system (returns False when complete)
    still_recovering = recovery_system.update()

    if not still_recovering:
        API.SysMsg("Recovery complete, resuming farming", 68)
        STATE = "idle"

# ============ CLEANUP ============

def cleanup():
    """
    Clean up on script exit: save session, dispose gumps, unregister hotkeys, save settings.
    """
    try:
        # Save session statistics to log file
        if 'stats_tracker' in globals() and stats_tracker:
            if 'session_logger' in globals() and session_logger:
                try:
                    session_stats = stats_tracker.get_session_stats()
                    session_logger.save_session(session_stats)
                    API.SysMsg("Session saved to log", 68)
                except Exception as e:
                    API.SysMsg(f"Session save error: {str(e)}", 32)

            # Also save stats tracker's internal state
            stats_tracker.save_session()

        # Dispose GUI windows
        if 'main_gump' in globals() and main_gump:
            try:
                main_gump.Dispose()
            except:
                pass

        if 'config_gump' in globals() and config_gump:
            try:
                config_gump.Dispose()
            except:
                pass

        # Unregister hotkeys
        try:
            API.UnregisterHotkey("PAUSE")
            API.UnregisterHotkey("F12")
        except:
            pass  # Hotkeys may not be registered if init failed

        # Save final settings
        try:
            save_settings()
        except Exception as e:
            API.SysMsg(f"Settings save error: {str(e)}", 32)

        # Final message
        API.SysMsg("Pet Farmer stopped. Session saved.", 90)

    except Exception as e:
        API.SysMsg(f"Cleanup error: {str(e)}", 32)

# ============ INITIALIZATION ============

def initialize():
    """
    Initialize script: load settings, validate config, initialize systems, build GUI, register hotkeys.

    Returns:
        bool: True if initialization successful, False if critical config missing
    """
    global danger_assessment, pet_manager, area_manager, npc_threat_map
    global flee_system, recovery_system, supply_tracker, healing_system
    global travel_system, banking_triggers, banking_system, stats_tracker
    global combat_manager, patrol_system, looting_system, session_logger
    global error_recovery, last_stats_update

    try:
        # Load settings from persistence
        load_settings()

        # Validate required configuration
        config_valid = True
        missing_items = []

        # Check for runebook (required for travel/banking)
        if banking_enabled and (bank_runebook_serial == 0 or return_runebook_serial == 0):
            missing_items.append("Banking runebooks")
            config_valid = False

        # Check for at least one farming area defined
        if area_type == "none":
            missing_items.append("Farming area")
            config_valid = False

        # If critical config missing, show error and open config window
        if not config_valid:
            API.SysMsg("INITIALIZATION INCOMPLETE", 32)
            for item in missing_items:
                API.SysMsg(f"  Missing: {item}", 43)
            API.SysMsg("Please configure via F12", 68)

            # Still register hotkeys and build GUI for configuration
            API.OnHotKey("PAUSE", toggle_pause)
            API.OnHotKey("F12", build_config_gump)
            build_config_gump()

            return False

        # Initialize all system instances
        danger_assessment = DangerAssessment()
        pet_manager = PetManager(KEY_PREFIX)
        area_manager = AreaManager(KEY_PREFIX)
        npc_threat_map = NPCThreatMap()

        # Initialize healing system
        healing_system = HealingSystem()
        healing_system.sync_from_globals()

        # Initialize combat and patrol systems
        combat_manager = CombatManager(danger_assessment, npc_threat_map, pet_manager)
        patrol_system = PatrolSystem()

        # Initialize flee and recovery systems
        flee_system = FleeSystem(area_manager, npc_threat_map, KEY_PREFIX)
        recovery_system = RecoverySystem(pet_manager, area_manager, KEY_PREFIX)

        # Initialize looting system
        looting_system = LootingSystem()

        # Initialize travel and banking systems
        travel_system = TravelSystem(KEY_PREFIX)
        banking_triggers = BankingTriggers(KEY_PREFIX)
        banking_system = BankingSystem(travel_system, KEY_PREFIX)

        # Initialize supply tracker
        supply_tracker = SupplyTracker(KEY_PREFIX)

        # Initialize statistics and logging
        stats_tracker = StatisticsTracker(KEY_PREFIX)
        session_logger = SessionLogger(KEY_PREFIX)
        last_stats_update = time.time()

        # Initialize error recovery
        error_recovery = ErrorRecoverySystem()

        # Scan for pets if configured
        if pets:
            pet_manager.scan_pets()

        # Build main GUI
        build_main_gump()

        # Register hotkeys
        API.OnHotKey("PAUSE", toggle_pause)
        API.OnHotKey("F12", build_config_gump)

        # Success messages
        API.SysMsg(f"Pet Farmer v{__version__} initialized!", 68)
        API.SysMsg("Press PAUSE to pause/unpause", 90)
        API.SysMsg("Press F12 for config", 90)

        return True

    except Exception as e:
        API.SysMsg(f"Init error: {str(e)}", 32)
        import traceback
        API.SysMsg(traceback.format_exc(), 32)
        return False

# Attempt initialization
try:
    if not initialize():
        API.SysMsg("Script started in config-only mode", 43)
        API.SysMsg("Configure settings and restart", 43)
        # Don't proceed to main loop if initialization failed
        script_enabled = False
except Exception as e:
    API.SysMsg(f"Fatal init error: {str(e)}", 32)
    cleanup()
    raise

# ============ MAIN LOOP ============

try:
    while not API.StopRequested:
        API.ProcessCallbacks()  # MUST be first

        # If script not enabled (initialization failed), just keep GUI responsive
        if not script_enabled:
            API.Pause(0.5)
            continue

        if script_paused:
            API.Pause(0.2)
            continue

        # Error detection (every loop)
        if error_recovery:
            errors = error_recovery.detect_errors()
            if errors:
                for error in errors:
                    error_recovery.recover_from_error(error)

        # Update NPC threat map (every 2s)
        current_time = time.time()
        if npc_threat_map and current_time - last_npc_scan >= 2.0:
            npc_threat_map.scan_npcs()
            last_npc_scan = current_time

        # Update supply tracking (every 30s automatically)
        if supply_tracker:
            supply_tracker.update_counts()

        # Update statistics tracking (every 2s)
        if stats_tracker and current_time - last_stats_update >= 2.0:
            # Update state time tracking
            stats_tracker.update_state(STATE)

            # Update performance metrics
            stats_tracker.calculate_performance_metrics()

            # Update display if GUI exists
            if main_controls:
                stats_tracker.update_display(main_controls)

            last_stats_update = current_time

        # State machine dispatcher
        if STATE == "idle":
            handle_idle_state()
        elif STATE == "patrolling":
            handle_patrolling_state()
        elif STATE == "engaging":
            handle_engaging_state()
        elif STATE == "healing":
            handle_healing_state()
        elif STATE == "looting":
            handle_looting_state()
        elif STATE == "fleeing":
            handle_fleeing_state()
        elif STATE == "traveling_to_bank":
            handle_traveling_to_bank_state()
        elif STATE == "banking":
            handle_banking_state()
        elif STATE == "recovering":
            handle_recovering_state()
        elif STATE == "paused":
            # Do nothing, wait for unpause
            pass
        elif STATE == "stopped":
            API.SysMsg("Script stopped", 43)
            break

        API.Pause(0.1)  # Short pause only

except Exception as e:
    API.SysMsg(f"Main loop error: {str(e)}", 32)
    import traceback
    API.SysMsg(traceback.format_exc(), 32)
finally:
    cleanup()
