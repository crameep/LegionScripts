# Cotton Suite v1.1 - AutoPick Redesign

## Changes Summary

### AutoPick Mode - Complete Redesign

**Previous Approach:**
- Complex stuck detection with retry logic
- Searched all 4 cotton plant graphics automatically
- Used `API.MoveItem()` for ground cotton pickup
- Multiple stuck detection timers and counters
- Random offset pathfinding on stuck

**New Approach:**
- User targets a cotton plant on activation to identify graphic
- Searches only for that specific graphic
- Uses `API.UseObject()` (double-click) for picking up ground cotton
- Simpler state machine: setup → scanning → moving → picking → waiting_for_loot → looting
- Removed complex stuck detection (user can pause/reposition if needed)
- 10 second timeout for pathfinding to each plant

### State Machine Flow

```
setup (NEW):
  - Prompts: "Target a cotton plant to identify..."
  - Uses API.RequestTarget(15) to get user selection
  - Extracts graphic ID from targeted item
  - Transitions to: scanning

scanning:
  - Searches for plants with target graphic using API.FindType()
  - Checks cooldown on found plants
  - If in reach (1 tile): transitions to picking
  - If out of reach: starts pathfinding, transitions to moving

moving:
  - Monitors distance to target plant
  - Cancels pathfinding when in reach
  - 10 second timeout → marks plant on cooldown, returns to scanning
  - Transitions to: picking (when in reach)

picking:
  - Double-clicks plant with API.UseObject()
  - Marks plant on cooldown
  - Transitions to: waiting_for_loot

waiting_for_loot (NEW):
  - Waits 1.5 seconds for cotton bales to drop to ground
  - Transitions to: looting

looting:
  - Tries 3 times to find and pick up ground cotton
  - Uses API.UseObject() to double-click ground bales
  - Updates stats if any cotton collected
  - Transitions to: scanning (for next plant)
```

### Picker Mode Changes

**Updated `loot_ground_cotton()` function:**
- Changed from `API.MoveItem()` to `API.UseObject()` (double-click)
- Simplified logic - tries 3 times to find and pick up ground cotton
- More reliable pickup that matches game client behavior

### UI/UX Improvements

**Status Text Updates:**
- "Waiting for target..." during setup phase
- "Scanning for 0x[GRAPHIC]..." shows targeted graphic ID
- "Waiting for loot..." during cotton drop delay
- "Collecting cotton..." during pickup phase

**Help Text:**
- Updated: "AutoPick: Target plant type, auto-pathfind and pick"

**Mode Activation:**
- System message: "AutoPick mode activated - target a plant"
- Immediately prompts for target

### Code Cleanup

**Removed Constants:**
- `STUCK_CHECK_INTERVAL` (2.0 seconds)
- `STUCK_MAX_COUNT` (3 attempts)
- `PATHFIND_TIMEOUT` (15.0 seconds)

**Removed State Variables:**
- `stuck_check_time`
- `last_position`
- `stuck_count`

**Added State Variables:**
- `autopick_target_graphic` - stores user-targeted graphic ID
- `autopick_move_timeout = 10.0` - simpler timeout constant

### Benefits

1. **User Control**: User chooses which plant type to harvest
2. **Simplicity**: Removed ~100 lines of complex stuck detection code
3. **Reliability**: Double-click pickup matches game client behavior better
4. **Flexibility**: Can target any harvestable plant graphic, not just pre-defined list
5. **Clarity**: Simpler state machine is easier to understand and maintain
6. **Performance**: Less complex logic = fewer edge cases

### Usage

1. Click **[AutoPick]** button
2. Target any cotton plant when prompted
3. Script will automatically:
   - Find nearest plant of that type
   - Pathfind to it if needed
   - Pick the plant
   - Collect ground cotton
   - Move to next plant

4. If stuck, press **PAUSE** hotkey, reposition manually, then resume

### Version

- Updated from v1.0 to v1.1
