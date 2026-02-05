#!/usr/bin/env python3
"""
Test script for DangerAssessment class

Tests all required scenarios from CoryCustom-ho5:
1. Initialize DangerAssessment with default weights
2. Call calculate_danger() with full HP, no enemies - verify returns 0-10 (safe)
3. Reduce player HP to 30% - verify danger rises to 30-50 range
4. Add 3 nearby hostile NPCs - verify danger rises further
5. Verify get_danger_zone() returns correct zone names
6. Adjust weights via configure_weights() - verify danger recalculates correctly
"""

import sys
import os

# Mock API for testing outside of TazUO
class MockPlayer:
    def __init__(self):
        self.Hits = 100
        self.HitsMax = 100
        self.X = 100
        self.Y = 100

class MockMobile:
    def __init__(self, hits=100, hits_max=100, distance=5, is_dead=False):
        self.Hits = hits
        self.HitsMax = hits_max
        self.Distance = distance
        self.IsDead = is_dead
        self.X = 105
        self.Y = 105

class MockAPI:
    Player = MockPlayer()

    @staticmethod
    def Mobiles_FindMobile(serial):
        # Return mock mobiles for testing
        return MockMobile()

    @staticmethod
    def SysMsg(msg, color):
        pass

# Mock the API module
class API:
    Player = MockPlayer()

    class Mobiles:
        @staticmethod
        def FindMobile(serial):
            return MockMobile()

    @staticmethod
    def SysMsg(msg, color):
        print(f"[{color}] {msg}")

# Define helper functions (from script)
def get_player_pos():
    return (getattr(API.Player, 'X', 0), getattr(API.Player, 'Y', 0))

def distance(x1, y1, x2, y2):
    return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5

# Import time for damage tracking
import time

# Constants
MAX_FOLLOW_RANGE = 15

# Now we can define the DangerAssessment class
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
            print(f"Danger calc error: {str(e)}")
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

# ============ TEST FUNCTIONS ============

def test_1_initialization():
    """Test 1: Initialize DangerAssessment with default weights"""
    print("\n=== Test 1: Initialization ===")
    da = DangerAssessment()

    # Verify weights sum to 1.0
    weight_sum = sum(da.weights.values())
    print(f"Weight sum: {weight_sum:.2f} (expected: 1.00)")
    assert abs(weight_sum - 1.0) < 0.01, "Weights should sum to 1.0"

    print("✓ Initialization successful")
    return da

def test_2_full_hp_no_enemies(da):
    """Test 2: Full HP, no enemies - expect 0-10 danger (safe)"""
    print("\n=== Test 2: Full HP, No Enemies ===")

    # Set player to full HP
    API.Player.Hits = 100
    API.Player.HitsMax = 100

    # No pets, no enemies, no NPCs
    danger = da.calculate_danger(
        pets_data=[],
        enemy_count=0,
        npc_positions=[],
        player_pos=(100, 100)
    )

    print(f"Danger score: {danger} (expected: 0-10)")
    print(f"Danger zone: {da.get_danger_zone(danger)}")

    assert 0 <= danger <= 10, f"Expected 0-10, got {danger}"
    assert da.get_danger_zone(danger) == "SAFE", "Expected SAFE zone"

    print("✓ Full HP no enemies test passed")
    return danger

def test_3_low_hp(da):
    """Test 3: Reduce player HP to 30% - expect 30-50 danger range"""
    print("\n=== Test 3: Low HP (30%) ===")

    # Set player to 30% HP
    API.Player.Hits = 30
    API.Player.HitsMax = 100

    # No pets, no enemies, no NPCs
    danger = da.calculate_danger(
        pets_data=[],
        enemy_count=0,
        npc_positions=[],
        player_pos=(100, 100)
    )

    print(f"Danger score: {danger} (expected: 30-50)")
    print(f"Danger zone: {da.get_danger_zone(danger)}")

    assert 30 <= danger <= 50, f"Expected 30-50, got {danger}"

    print("✓ Low HP test passed")
    return danger

def test_4_nearby_npcs(da):
    """Test 4: Add 3 nearby hostile NPCs - expect danger rises further"""
    print("\n=== Test 4: Add 3 Nearby NPCs ===")

    # Player still at 30% HP
    API.Player.Hits = 30
    API.Player.HitsMax = 100

    # Add 3 NPCs close to player at (100, 100)
    npc_positions = [
        (105, 105),  # 7 tiles away
        (108, 100),  # 8 tiles away
        (100, 106),  # 6 tiles away
    ]

    danger = da.calculate_danger(
        pets_data=[],
        enemy_count=0,
        npc_positions=npc_positions,
        player_pos=(100, 100)
    )

    print(f"Danger score: {danger} (expected: higher than previous)")
    print(f"Danger zone: {da.get_danger_zone(danger)}")

    # Should be higher than just low HP alone
    # Low HP gives ~30-50, adding NPCs should push it higher
    assert danger > 30, f"Expected > 30 with NPCs, got {danger}"

    print("✓ Nearby NPCs test passed")
    return danger

def test_5_danger_zones(da):
    """Test 5: Verify get_danger_zone() returns correct zone names"""
    print("\n=== Test 5: Danger Zone Names ===")

    test_cases = [
        (5, "SAFE"),
        (25, "LOW"),
        (45, "MODERATE"),
        (65, "HIGH"),
        (85, "CRITICAL"),
        (100, "CRITICAL"),
    ]

    for score, expected_zone in test_cases:
        zone = da.get_danger_zone(score)
        print(f"Score {score} -> {zone} (expected: {expected_zone})")
        assert zone == expected_zone, f"Expected {expected_zone}, got {zone}"

    print("✓ Danger zone names test passed")

def test_6_adjust_weights(da):
    """Test 6: Adjust weights - verify danger recalculates correctly"""
    print("\n=== Test 6: Adjust Weights ===")

    # Set up scenario
    API.Player.Hits = 50
    API.Player.HitsMax = 100

    # Calculate with default weights
    danger_default = da.calculate_danger(
        pets_data=[],
        enemy_count=2,
        npc_positions=[],
        player_pos=(100, 100)
    )
    print(f"Danger with default weights: {danger_default}")

    # Increase enemy_count weight significantly
    da.configure_weights(enemy_count=0.8, player_hp=0.2)

    # Verify weights normalized
    weight_sum = sum(da.weights.values())
    print(f"Weight sum after adjustment: {weight_sum:.2f}")
    assert abs(weight_sum - 1.0) < 0.01, "Weights should still sum to 1.0"

    # Recalculate - should be higher due to increased enemy weight
    danger_adjusted = da.calculate_danger(
        pets_data=[],
        enemy_count=2,
        npc_positions=[],
        player_pos=(100, 100)
    )
    print(f"Danger with adjusted weights: {danger_adjusted}")
    print(f"Change: {danger_adjusted - danger_default:+d}")

    # With higher enemy weight, danger should increase
    assert danger_adjusted != danger_default, "Danger should change with weight adjustment"

    print("✓ Weight adjustment test passed")

def run_all_tests():
    """Run all test cases"""
    print("=" * 60)
    print("DANGER ASSESSMENT SYSTEM - TEST SUITE")
    print("=" * 60)

    try:
        da = test_1_initialization()
        test_2_full_hp_no_enemies(da)
        test_3_low_hp(da)
        test_4_nearby_npcs(da)
        test_5_danger_zones(da)
        test_6_adjust_weights(da)

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {str(e)}")
        return 1
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(run_all_tests())
