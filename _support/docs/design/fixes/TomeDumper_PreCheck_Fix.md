# Util_TomeDumper_v1.py - Pre-Check Container Bug Fix

**Date**: 2026-01-31
**Issue**: Script says "No items to dump" when only loot bag has maps, but works when both backpack and loot bag have maps
**Root Cause**: Pre-check function hardcoded to only check backpack, ignoring configured target containers

---

## Bug Description

**User Report**:
- Works fine when both backpack AND loot bag have maps
- Says "No items to dump for TreasureMaps" when ONLY loot bag has maps
- Configured containers: backpack + loot bag
- Item graphics filter: treasure maps

**Symptoms**:
- Message: "No items to dump for TreasureMaps"
- Script stops before even starting container loop
- Doesn't check the loot bag at all

---

## Root Cause Analysis

**Location**: Lines 110-136 - `get_items_to_dump()` function

**Problem**: Function hardcoded to check **backpack only**

```python
def get_items_to_dump(tome_config):
    """Get backpack items matching tome's filter"""
    try:
        backpack = API.Player.Backpack  # ← HARDCODED to backpack!
        if not backpack:
            return []

        items = API.ItemsInContainer(backpack.Serial, recursive=False)
        # ... filter logic ...
```

**Why This Breaks**:

1. **Pre-check happens at line 200**: `item_count = count_items_for_tome(tome_config)`
2. **count_items_for_tome()** calls **get_items_to_dump()**
3. **get_items_to_dump()** only checks backpack (ignores configured containers!)
4. **If backpack has no maps**: Returns 0
5. **Line 201-203**: `if item_count == 0:` → "No items to dump" → **stops completely**

**Flow Breakdown**:

**Scenario 1: Both containers have maps** ✓
```
Pre-check → Backpack has 5 maps → count = 5 → Passes
Container loop → Processes backpack (5 maps) → Processes loot bag (3 maps) → Success!
```

**Scenario 2: Only loot bag has maps** ✗
```
Pre-check → Backpack has 0 maps → count = 0 → STOPS
Message: "No items to dump for TreasureMaps"
Container loop → NEVER REACHED!
```

---

## Fix Applied

**Changed**: Lines 110-146 - `get_items_to_dump()` function

**Before** (Broken):
```python
def get_items_to_dump(tome_config):
    """Get backpack items matching tome's filter"""
    try:
        backpack = API.Player.Backpack  # ← ONLY checks backpack
        if not backpack:
            return []

        items = API.ItemsInContainer(backpack.Serial, recursive=False)
        # ... filter by graphics ...
        return matching
```

**After** (Fixed):
```python
def get_items_to_dump(tome_config):
    """Get items matching tome's filter from configured containers (or backpack if none)"""
    try:
        all_matching = []

        # Determine which containers to check
        containers_to_check = []
        targeting_mode = tome_config.get("targeting_mode", "container")

        # For multi_item and container modes, check configured containers
        if targeting_mode in ["container", "multi_item"]:
            target_containers = tome_config.get("target_containers", [])
            if target_containers:
                containers_to_check = target_containers

        # Fallback to backpack if no containers configured
        if not containers_to_check:
            backpack = API.Player.Backpack
            if backpack:
                containers_to_check = [backpack.Serial]

        # Check each container for matching items
        for container_serial in containers_to_check:
            items = API.ItemsInContainer(container_serial, recursive=False)
            if not items:
                continue

            # Filter by graphics
            if not tome_config.get("item_graphics", []):
                all_matching.extend(items)  # No filter = all items
            else:
                for item in items:
                    if hasattr(item, 'Graphic') and item.Graphic in tome_config["item_graphics"]:
                        all_matching.append(item)

        return all_matching
```

**Key Changes**:
1. ✅ **Checks configured target containers** instead of hardcoded backpack
2. ✅ **Loops through all containers** to count total matching items
3. ✅ **Fallback to backpack** if no containers configured (backward compatible)
4. ✅ **Respects targeting mode** - only checks containers for container/multi_item modes

---

## Why This Fix Works

### Correct Flow Now:

**Scenario 1: Both containers have maps** ✓
```
Pre-check → Checks backpack (5 maps) + loot bag (3 maps) → count = 8 → Passes
Container loop → Processes both → Success!
```

**Scenario 2: Only loot bag has maps** ✓ FIXED!
```
Pre-check → Checks backpack (0 maps) + loot bag (3 maps) → count = 3 → Passes
Container loop → Skips backpack (empty) → Processes loot bag (3 maps) → Success!
```

**Scenario 3: No containers configured** ✓ Backward compatible
```
Pre-check → No containers → Falls back to backpack → Works as before
```

---

## Additional Debug Messages Added

Also added debug output to help diagnose future issues:

```python
# Line 430 - Shows which containers are being processed
API.SysMsg("Container serials: " + ", ".join("0x{:X}".format(c) for c in target_containers), 88)

# Line 433 - Shows progress through container list
API.SysMsg("Processing container " + str(container_idx + 1) + "/" + str(len(target_containers)) + ": 0x{:X}".format(container_serial), 88)

# Line 463 - Clarifies that script is continuing to next container
API.SysMsg("No matching items in container 0x{:X}, continuing to next...".format(container_serial), 43)

# Line 536 - Confirms container finished processing
API.SysMsg("Finished processing container 0x{:X}".format(container_serial), 88)
```

These messages make it clear what's happening during multi-container operations.

---

## Testing Instructions

### Test Case 1: Only Loot Bag Has Maps
**Setup**:
1. Tome configured with:
   - Target containers: [backpack, loot bag]
   - Item graphics: [treasure map graphics]
2. Backpack: **empty** (or no maps)
3. Loot bag: **3+ treasure maps**

**Test Steps**:
1. Run dump operation
2. **Expected**:
   ```
   Searching 2 containers for items...
   Container serials: 0x40XXXXXX, 0x41YYYYYY
   Processing container 1/2: 0x40XXXXXX
   Container 0x40XXXXXX has 15 items total
   No matching items in container 0x40XXXXXX, continuing to next...
   Processing container 2/2: 0x41YYYYYY
   Container 0x41YYYYYY has 10 items total
   Filtering for graphics: 0x14EB
     Found matching item: graphic 0x14EB, serial 0x50ZZZZZZ
   Found 3 items to dump from 0x41YYYYYY
   Targeting item 1/3...
     Clicking button 1
     Targeting item serial 0x50ZZZZZZ
   ...
   Targeted 3 items from 2 containers
   ```

**Success Criteria**:
- ✅ No "No items to dump" message
- ✅ Processes loot bag
- ✅ Targets all 3 maps
- ✅ Maps end up in tome

### Test Case 2: Both Containers Have Maps
**Setup**:
1. Backpack: 2 maps
2. Loot bag: 3 maps

**Expected**: Targets 5 maps total (should work as before)

### Test Case 3: No Containers Configured
**Setup**:
1. Remove all target containers from config
2. Maps in backpack

**Expected**: Falls back to backpack, works as before (backward compatible)

---

## Performance Impact

**Before**: Pre-check only looked at backpack (fast, but wrong!)
**After**: Pre-check looks at all configured containers (slightly slower, but correct!)

**Impact**: Negligible - pre-check happens once per dump operation, not per item.

---

## Related Fixes in This Session

1. **Multi-target redundant wait fix** - Removed double WaitForTarget() call
2. **Pre-check container fix** - This fix (checks configured containers)
3. **Debug output added** - Better visibility into container processing

---

## Files Modified

- `Utility/Util_TomeDumper_v1.py` - Fixed `get_items_to_dump()` function (lines 110-146)

## Validation

- ✅ Python syntax validated
- ✅ Logic flow preserved
- ✅ Backward compatible (fallback to backpack)
- ✅ Debug messages added
- ✅ Ready for testing

---

**End of Report**
