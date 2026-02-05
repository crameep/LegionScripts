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
from LegionUtils import WindowPositionTracker, ResourceRateTracker

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

# Healing tracking
last_heal_time = 0
last_vet_kit_time = 0
priority_heal_pet = None  # Serial of pet flagged for priority heal

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

# Error tracking
last_error_time = 0
error_count = 0

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

    except Exception as e:
        API.SysMsg(f"Save error: {str(e)}", 32)

def load_settings():
    """Load all persistent settings"""
    global script_enabled, pets, area_type, area_center_x, area_center_y, area_radius
    global area_waypoints, banking_enabled, bank_runebook_serial, bank_spot_index
    global return_runebook_serial, return_spot_index, loot_corpses, loot_gold_only
    global loot_threshold_value

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

# ============ GUI FUNCTIONS ============

def build_main_gump():
    """Build main control panel"""
    global main_gump, main_controls, main_pos_tracker

    # TODO: Implement main GUI in later tasks
    API.SysMsg("Main GUI not yet implemented", 43)

def build_config_gump():
    """Build configuration window"""
    global config_gump, config_controls, config_pos_tracker

    # TODO: Implement config GUI in later tasks
    API.SysMsg("Config GUI not yet implemented", 43)

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

    # TODO: Implement state logic in later tasks
    pass

def handle_healing_state():
    """Handle healing state"""
    global STATE

    # Check if heal action is complete
    if time.time() > action_start_time + BANDAGE_DELAY:
        STATE = "idle"

def handle_combat_state():
    """Handle combat state"""
    global STATE

    # TODO: Implement combat logic in later tasks
    pass

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
    """Clean up on script exit"""
    try:
        if main_gump:
            main_gump.Dispose()
        if config_gump:
            config_gump.Dispose()
        API.SysMsg("Pet Farmer stopped", 43)
    except Exception as e:
        API.SysMsg(f"Cleanup error: {str(e)}", 32)

# ============ INITIALIZATION ============

try:
    load_settings()

    # Initialize systems
    danger_assessment = DangerAssessment()
    pet_manager = PetManager(KEY_PREFIX)
    area_manager = AreaManager(KEY_PREFIX)
    npc_threat_map = NPCThreatMap()
    flee_system = FleeSystem(area_manager, npc_threat_map, KEY_PREFIX)
    recovery_system = RecoverySystem(pet_manager, area_manager, KEY_PREFIX)

    API.SysMsg(f"Pet Farmer v{__version__} loaded", 68)
    API.SysMsg("Press PAUSE to pause/unpause", 90)

    # Register hotkeys
    API.OnHotKey("PAUSE", toggle_pause)

    # TODO: Build GUI in later tasks
    # build_main_gump()

except Exception as e:
    API.SysMsg(f"Init error: {str(e)}", 32)
    cleanup()
    raise

# ============ MAIN LOOP ============

try:
    while not API.StopRequested:
        API.ProcessCallbacks()  # MUST be first

        if script_paused:
            API.Pause(0.2)
            continue

        # State machine dispatcher
        if STATE == "idle":
            handle_idle_state()
        elif STATE == "healing":
            handle_healing_state()
        elif STATE == "combat":
            handle_combat_state()
        elif STATE == "fleeing":
            handle_fleeing_state()
        elif STATE == "recovering":
            handle_recovering_state()

        API.Pause(0.1)  # Short pause only

except Exception as e:
    API.SysMsg(f"Main loop error: {str(e)}", 32)
    import traceback
    API.SysMsg(traceback.format_exc(), 32)
finally:
    cleanup()
