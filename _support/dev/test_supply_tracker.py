#!/usr/bin/env python3
"""
Test script for SupplyTracker class
Tests all major functionality without requiring the game API
"""
import time

# Mock API for testing
class MockAPI:
    class Player:
        class Backpack:
            Serial = 12345

    class PersistentVar:
        Char = 1

    _storage = {}

    @staticmethod
    def SavePersistentVar(key, value, scope):
        MockAPI._storage[key] = value

    @staticmethod
    def GetPersistentVar(key, default, scope):
        return MockAPI._storage.get(key, default)

    @staticmethod
    def FindType(graphic, container_serial):
        # Simulate bandages: 150 count, vet kits: 5 count
        if graphic == 0x0E21:  # Bandages
            return [MockItem(150)]
        elif graphic == 0x0E50:  # Vet kits
            return [MockItem(5)]
        return None

    @staticmethod
    def SysMsg(msg, hue=0):
        print(f"[SysMsg] {msg}")

class MockItem:
    def __init__(self, amount):
        self.Amount = amount

# Replace global API with mock
import sys
sys.modules['API'] = MockAPI()
API = MockAPI()

# Import SupplyTracker (we'll copy the class here for testing)
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

# Test functions
def test_initialization():
    print("\n=== Test 1: Initialization ===")
    tracker = SupplyTracker("Test_")
    print("✓ SupplyTracker initialized")
    print(f"  Tracked supplies: {list(tracker.supplies.keys())}")
    return tracker

def test_track_usage(tracker):
    print("\n=== Test 2: Track Usage ===")
    # Simulate using 50 bandages over 30 minutes
    start_time = time.time() - 1800  # 30 minutes ago

    # Add historical data manually
    for i in range(50):
        tracker.supplies['bandages']['usage_history'].append({
            'timestamp': start_time + (i * 36),  # Every 36 seconds
            'count': 150 - i
        })

    tracker._save_history()
    print(f"✓ Simulated 50 bandage uses over 30 minutes")
    print(f"  History entries: {len(tracker.supplies['bandages']['usage_history'])}")

def test_predict_depletion(tracker):
    print("\n=== Test 3: Predict Depletion ===")
    hours = tracker.predict_depletion_time('bandages')
    rate = tracker._calculate_usage_rate('bandages', hours=1.0)
    print(f"✓ Prediction calculated")
    print(f"  Usage rate: {rate:.2f} bandages/hour")
    print(f"  Hours remaining: {hours:.2f}" if hours >= 0 else "  Hours remaining: insufficient data")

def test_should_prioritize_restock(tracker):
    print("\n=== Test 4: Should Prioritize Restock ===")
    # Modify history to show critical supplies
    current_time = time.time()
    tracker.supplies['bandages']['usage_history'] = [
        {'timestamp': current_time - 600, 'count': 50},  # 10 min ago: 50
        {'timestamp': current_time, 'count': 30}  # now: 30
    ]

    should_restock = tracker.should_prioritize_restock(critical_hours=1.0)
    print(f"✓ Restock priority checked")
    print(f"  Should prioritize restock: {should_restock}")
    hours = tracker.predict_depletion_time('bandages')
    print(f"  Hours remaining: {hours:.2f}" if hours >= 0 else "  Hours remaining: insufficient data")

def test_get_supply_status(tracker):
    print("\n=== Test 5: Get Supply Status ===")
    status = tracker.get_supply_status()
    print("✓ Supply status retrieved")
    for supply_name, info in status.items():
        print(f"  {supply_name}:")
        print(f"    Count: {info['count']}")
        print(f"    Rate: {info['rate']:.2f}/hr")
        print(f"    Hours remaining: {info['hours_remaining']:.2f}" if info['hours_remaining'] >= 0 else "    Hours remaining: unknown")
        print(f"    Status: {info['status']}")

def test_optimize_bank_timing(tracker):
    print("\n=== Test 6: Optimize Bank Timing ===")
    # Test with high gold and low bandages
    should_bank = tracker.optimize_bank_timing(
        gold_current=8500,
        gold_threshold=10000,
        weight_percent=75
    )
    print(f"✓ Bank timing optimized")
    print(f"  Gold: 8500 (threshold: 10000, 85%)")
    print(f"  Weight: 75%")
    print(f"  Should bank now: {should_bank}")

def test_persistence(tracker):
    print("\n=== Test 7: Persistence ===")
    # Save current state
    tracker._save_history()

    # Create new tracker and load
    tracker2 = SupplyTracker("Test_")
    bandage_history_count = len(tracker2.supplies['bandages']['usage_history'])
    print(f"✓ Persistence tested")
    print(f"  Loaded history entries: {bandage_history_count}")
    print(f"  Data persisted: {bandage_history_count > 0}")

# Run all tests
if __name__ == "__main__":
    print("=" * 50)
    print("SupplyTracker Test Suite")
    print("=" * 50)

    try:
        tracker = test_initialization()
        test_track_usage(tracker)
        test_predict_depletion(tracker)
        test_should_prioritize_restock(tracker)
        test_get_supply_status(tracker)
        test_optimize_bank_timing(tracker)
        test_persistence(tracker)

        print("\n" + "=" * 50)
        print("All tests completed!")
        print("=" * 50)
    except Exception as e:
        print(f"\n✗ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
