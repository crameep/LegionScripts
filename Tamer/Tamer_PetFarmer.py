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

    # Initialize danger assessment system
    danger_assessment = DangerAssessment()

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

        API.Pause(0.1)  # Short pause only

except Exception as e:
    API.SysMsg(f"Main loop error: {str(e)}", 32)
    import traceback
    API.SysMsg(traceback.format_exc(), 32)
finally:
    cleanup()
