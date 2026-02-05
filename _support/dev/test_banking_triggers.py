"""
Test suite for BankingTriggers class.
Tests all trigger conditions and configuration methods.
"""

import time

# Mock API for testing
class MockAPI:
    class Player:
        Weight = 0
        MaxWeight = 100
        Backpack = None

    class PersistentVar:
        Char = "char"
        Global = "global"

    _persistence = {}

    @staticmethod
    def GetPersistentVar(key, default, scope):
        return MockAPI._persistence.get(key, default)

    @staticmethod
    def SavePersistentVar(key, value, scope):
        MockAPI._persistence[key] = value

    @staticmethod
    def SysMsg(msg, hue=None):
        print(f"[SysMsg] {msg}")

    @staticmethod
    def FindType(graphic, container=None):
        return []

# Replace global API with mock
API = MockAPI()

# Import the BankingTriggers class
# In real test, would import from Tamer_PetFarmer.py
# For now, copy the class implementation here for standalone testing

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


def test_banking_triggers():
    """Run all banking trigger tests"""
    print("=" * 60)
    print("BANKING TRIGGERS TEST SUITE")
    print("=" * 60)

    # Test 1: Initialize with default settings
    print("\n[TEST 1] Initialize BankingTriggers with default settings")
    triggers = BankingTriggers("TestScript_")
    assert triggers.weight_trigger['enabled'] == True
    assert triggers.weight_trigger['threshold_pct'] == 80.0
    assert triggers.time_trigger['enabled'] == True
    assert triggers.time_trigger['interval_minutes'] == 60
    assert triggers.gold_trigger['enabled'] == True
    assert triggers.gold_trigger['gold_amount'] == 10000
    assert triggers.supply_trigger['enabled'] == True
    assert triggers.supply_trigger['bandage_threshold'] == 50
    print("✓ Default settings initialized correctly")

    # Test 2: Weight trigger
    print("\n[TEST 2] Set player weight to 85% - should trigger")
    API.Player.Weight = 85
    API.Player.MaxWeight = 100
    triggers.last_check_time = 0  # Force immediate check
    should_bank, reason = triggers.should_bank()
    assert should_bank == True
    assert reason == "weight"
    print(f"✓ Weight trigger activated: {reason}")

    # Test 3: Time trigger
    print("\n[TEST 3] Wait 60+ minutes - should trigger")
    API.Player.Weight = 50  # Reset weight
    triggers.last_bank_time = time.time() - (61 * 60)  # 61 minutes ago
    triggers.last_check_time = 0  # Force immediate check
    should_bank, reason = triggers.should_bank()
    assert should_bank == True
    assert reason == "time"
    print(f"✓ Time trigger activated: {reason}")

    # Test 4: Gold trigger (simulate by mocking)
    print("\n[TEST 4] Add 12000 gold to backpack - should trigger")
    triggers.last_bank_time = time.time()  # Reset time trigger
    triggers.last_check_time = 0  # Force immediate check

    # Mock the gold counting method
    original_count_gold = triggers._count_gold_in_backpack
    triggers._count_gold_in_backpack = lambda: 12000

    should_bank, reason = triggers.should_bank()
    assert should_bank == True
    assert reason == "gold"
    print(f"✓ Gold trigger activated: {reason}")

    # Restore original method
    triggers._count_gold_in_backpack = original_count_gold

    # Test 5: Supply trigger (simulate by mocking)
    print("\n[TEST 5] Remove bandages to 30 count - should trigger")
    triggers.last_check_time = 0  # Force immediate check

    # Mock the bandage counting method
    original_count_bandages = triggers._count_bandages
    triggers._count_bandages = lambda: 30

    should_bank, reason = triggers.should_bank()
    assert should_bank == True
    assert reason == "supplies"
    print(f"✓ Supply trigger activated: {reason}")

    # Restore original method
    triggers._count_bandages = original_count_bandages

    # Test 6: Disable all triggers
    print("\n[TEST 6] Disable all triggers - should not trigger")
    triggers.weight_trigger['enabled'] = False
    triggers.time_trigger['enabled'] = False
    triggers.gold_trigger['enabled'] = False
    triggers.supply_trigger['enabled'] = False
    triggers.last_check_time = 0  # Force immediate check
    should_bank, reason = triggers.should_bank()
    assert should_bank == False
    assert reason is None
    print("✓ No triggers activated when all disabled")

    # Test 7: Configure triggers via dictionary
    print("\n[TEST 7] Configure triggers via configure_triggers()")
    config = {
        'weight_enabled': True,
        'weight_threshold_pct': 90.0,
        'time_enabled': False,
        'time_interval_minutes': 120,
        'gold_enabled': True,
        'gold_amount': 15000,
        'supply_enabled': True,
        'supply_bandage_threshold': 100
    }
    triggers.configure_triggers(config)
    assert triggers.weight_trigger['threshold_pct'] == 90.0
    assert triggers.time_trigger['interval_minutes'] == 120
    assert triggers.gold_trigger['gold_amount'] == 15000
    assert triggers.supply_trigger['bandage_threshold'] == 100
    print("✓ Triggers configured successfully")

    # Test 8: Track last bank time
    print("\n[TEST 8] Track last bank time")
    current_time = time.time()
    triggers.track_last_bank()
    assert triggers.last_bank_time > 0
    assert abs(triggers.last_bank_time - current_time) < 1.0
    print(f"✓ Last bank time tracked: {triggers.last_bank_time}")

    # Test 9: Get time until next bank
    print("\n[TEST 9] Get time until next bank")
    triggers.time_trigger['enabled'] = True
    triggers.time_trigger['interval_minutes'] = 60
    triggers.last_bank_time = time.time() - (30 * 60)  # 30 minutes ago
    time_remaining = triggers.get_time_until_next_bank()
    assert 29.0 < time_remaining < 31.0  # Should be around 30 minutes
    print(f"✓ Time until next bank: {time_remaining:.1f} minutes")

    # Test 10: Persistence
    print("\n[TEST 10] Test persistence save/load")
    triggers2 = BankingTriggers("TestScript_")
    triggers2.configure_triggers({
        'weight_threshold_pct': 75.0,
        'time_interval_minutes': 45,
        'gold_amount': 8000,
        'supply_bandage_threshold': 75
    })

    # Create new instance and verify it loads saved config
    triggers3 = BankingTriggers("TestScript_")
    assert triggers3.weight_trigger['threshold_pct'] == 75.0
    assert triggers3.time_trigger['interval_minutes'] == 45
    assert triggers3.gold_trigger['gold_amount'] == 8000
    assert triggers3.supply_trigger['bandage_threshold'] == 75
    print("✓ Persistence working correctly")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    test_banking_triggers()
