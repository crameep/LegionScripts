# Tamer Suite v2.1 - Config Panel Layout Correction

## Problem Summary

Based on external-reviewer and script-reviewer analysis:

1. **Config background**: 240px specified, needs 661px (actual content ends at ~661px)
2. **CONFIG_HEIGHT**: 600px specified, needs 1021px (total window height to bottom of config)
3. **SET/CLR buttons**: X=345 too close to right edge (400px width)
4. **8 static labels**: Missing from visibility toggle system

---

## Current Layout Analysis

### Starting Point
- `configY = 360` (EXPANDED_HEIGHT)

### Section Breakdown

| Section | Start Y | Content | Rows | Height | End Y |
|---------|---------|---------|------|--------|-------|
| **Header** | 360 | Title + Help | 2 | 35px | 395 |
| **Healer Settings** | 395 | Section title | 1 | 20px | 415 |
| | 415 | Self Heal (toggle) | 1 | 25px | 440 |
| | 440 | Pet Rez (toggle) | 1 | 25px | 465 |
| | 465 | Skip OOR (toggle) | 1 | 25px | 490 |
| | 490 | Tank Pet (SET/CLR) | 1 | 25px | 515 |
| | 515 | Vet Kit (SET/CLR) | 1 | 25px (+30 gap) | 570 |
| **Command Settings** | 570 | Section title | 1 | 20px | 590 |
| | 590 | Target Reds | 1 | 25px | 615 |
| | 615 | Target Grays | 1 | 25px | 640 |
| | 640 | Use Potions | 1 | 25px | 665 |
| | 665 | Auto-Target | 1 | 25px | 690 |
| | 690 | Trapped Pouch (SET) | 1 | 25px | 715 |
| | 715 | Use Pouch (toggle) | 1 | 25px | 740 |
| | 740 | Potion Counts | 1 | 25px (+30 gap) | 795 |
| **Command Hotkeys** | 795 | Section title | 1 | 20px | 815 |
| | 815 | Pause + Kill | 1 | 23px | 838 |
| | 838 | Guard + Follow | 1 | 23px | 861 |
| | 861 | Stay | 1 | 23px (+30 gap) | 914 |
| **Pet Order Mode** | 914 | Title + Help | 2 | 35px | 949 |
| | 949 | Pet 1 | 1 | 23px | 972 |
| | 972 | Pet 2 | 1 | 23px | 995 |
| | 995 | Pet 3 | 1 | 23px | 1018 |
| | 1018 | Pet 4 | 1 | 23px | 1041 |
| | 1041 | Pet 5 | 1 | 23px (+10 gap) | 1074 |
| **Footer** | 1074 | Done button | 1 | 20px | 1094 |

**Total content height**: 1094 - 360 = **734px**
**Last element bottom**: 1094px from top of window

---

## Corrected Constants

### Height Values
```python
CONFIG_HEIGHT = 1100           # Total window height when config visible
                               # (was 600px - off by 500px!)
```

### Config Background
```python
# Line 2012 - Config background
configBg.SetRect(0, configY, WINDOW_WIDTH_CONFIG, 740)
# Was: 240px (off by 500px)
# Now: 740px (covers all content + 6px padding at bottom)
```

---

## Button Position Fixes

### Current Problem
- Window width: 400px
- SET/CLR buttons at X=345 leaves only 10px margin (button width=45px ends at 390px)
- Very tight - difficult to click near window edge

### Recommended Button Positions

**Option 1: Compact (recommended)**
```python
# Tank Pet (line 2125-2133)
tankSetBtn.SetPos(270, configY - 2)    # Was 295
tankClrBtn.SetPos(320, configY - 2)    # Was 345

# Vet Kit (line 2147-2155)
vetkitSetBtn.SetPos(270, configY - 2)  # Was 295
vetkitClrBtn.SetPos(320, configY - 2)  # Was 345

# Trapped Pouch (line 2285-2286)
pouchSetBtn.SetPos(320, configY - 2)   # Was 345
```

**Spacing breakdown:**
- Label at X=15
- SET at X=270 (button 45px wide = ends at 315px)
- 5px gap
- CLR at X=320 (button 45px wide = ends at 365px)
- 35px right margin to edge (400px)

**Option 2: Right-aligned (alternative)**
```python
# If you want more space between label and buttons
tankSetBtn.SetPos(300, configY - 2)
tankClrBtn.SetPos(350, configY - 2)    # Only 5px from edge - risky!
```

---

## Missing Visibility Toggles (8 Static Labels)

These labels are NOT in config visibility arrays but should be:

### From Healer Settings Section
1. `selfHealLabel` (line 2039) - "Self Heal:"
2. `petRezLabel` (line 2066) - "Pet Rez:"
3. `skipOorLabel` (line 2093) - "Skip OOR:"

### From Command Settings Section
4. `redsLabel` (line 2172) - "Target Reds:"
5. `graysLabel` (line 2199) - "Target Grays:"
6. `potionsLabel` (line 2226) - "Use Potions:"
7. `autoTargetLabel` (line 2253) - "Auto-Target:"
8. `usePouchLabel` (line 2295) - "Use Pouch:"

### Fix Required
Add to `config_controls` array (around line 650-700):
```python
config_controls = [
    configBg, configTitle, configHelp,
    configHealerTitle,
    selfHealLabel, selfHealOnBtn, selfHealOffBtn, selfHealStatus,  # Added selfHealLabel
    petRezLabel, petRezOnBtn, petRezOffBtn, petRezStatus,          # Added petRezLabel
    skipOorLabel, skipOorOnBtn, skipOorOffBtn, skipOorStatus,      # Added skipOorLabel
    tankDisplayLabel, tankSetBtn, tankClrBtn,
    vetkitDisplayLabel, vetkitSetBtn, vetkitClrBtn,
    configCmdTitle,
    redsLabel, redsOnBtn, redsOffBtn, redsStatus,                  # Added redsLabel
    graysLabel, graysOnBtn, graysOffBtn, graysStatus,              # Added graysLabel
    potionsLabel, potionsOnBtn, potionsOffBtn, potionsStatus,      # Added potionsLabel
    autoTargetLabel, autoTargetOnBtn, autoTargetOffBtn, autoTargetStatus,  # Added autoTargetLabel
    pouchDisplayLabel, pouchSetBtn,
    usePouchLabel, usePouchOnBtn, usePouchOffBtn, usePouchStatus,  # Added usePouchLabel
    potionCountsLabel,
    configHkTitle,
    pauseHkLabel, pauseHkBtn,
    killHkLabel, killHkBtn,
    guardHkLabel, guardHkBtn,
    followHkLabel, followHkBtn,
    stayHkLabel, stayHkBtn,
    configOrderTitle, configOrderHelp,
    configDoneBtn
]
```

---

## Verified Y Positions (All Sections)

### Header Section (Y=360)
```
360: Config background starts
363: "=== CONFIGURATION ===" title
378: "Settings organized by category" help
```

### Healer Settings (Y=395-545)
```
395: "--- HEALER SETTINGS ---" section title
415: Self Heal toggle row
440: Pet Rez toggle row
465: Skip OOR toggle row
490: Tank Pet SET/CLR row
515: Vet Kit SET/CLR row
545: Section end (+30px gap)
```

### Command Settings (Y=570-765)
```
570: "--- COMMAND SETTINGS ---" section title
590: Target Reds toggle
615: Target Grays toggle
640: Use Potions toggle
665: Auto-Target toggle
690: Trapped Pouch SET button
715: Use Pouch toggle
740: Potion Counts label
765: Section end (+30px gap)
```

### Command Hotkeys (Y=795-884)
```
795: "--- COMMAND HOTKEYS ---" section title
815: Pause + Kill hotkey buttons
838: Guard + Follow hotkey buttons
861: Stay hotkey button
884: Section end (+30px gap)
```

### Pet Order Mode (Y=914-1064)
```
914: "--- PET ORDER MODE ---" title
929: Help text "(Controls which pets...)"
949: Pet 1 ACTIVE/SKIP
972: Pet 2 ACTIVE/SKIP
995: Pet 3 ACTIVE/SKIP
1018: Pet 4 ACTIVE/SKIP
1041: Pet 5 ACTIVE/SKIP
1064: Section end (+10px gap)
```

### Footer (Y=1074)
```
1074: [DONE - Close Config] button
1094: Button bottom (20px tall)
```

---

## Complete Fix Summary

### 1. Change Line 98 (Constants)
```python
CONFIG_HEIGHT = 1100           # Was 600px, needs 1100px
```

### 2. Change Line 2012 (Background Height)
```python
configBg.SetRect(0, configY, WINDOW_WIDTH_CONFIG, 740)  # Was 240px
```

### 3. Change Lines 2125-2133 (Tank Pet Buttons)
```python
tankSetBtn.SetPos(270, configY - 2)    # Was 295
tankClrBtn.SetPos(320, configY - 2)    # Was 345
```

### 4. Change Lines 2147-2155 (Vet Kit Buttons)
```python
vetkitSetBtn.SetPos(270, configY - 2)  # Was 295
vetkitClrBtn.SetPos(320, configY - 2)  # Was 345
```

### 5. Change Line 2286 (Trapped Pouch Button)
```python
pouchSetBtn.SetPos(320, configY - 2)   # Was 345
```

### 6. Add 8 Missing Labels to config_controls Array
See "Missing Visibility Toggles" section above for complete list.

---

## Space Optimization Opportunities (Future)

If 1100px total height is too tall, consider:

1. **Reduce section gaps**: 30px → 20px (saves 60px across 3 sections)
2. **Reduce row spacing**: 25px → 22px (saves ~30px across 12 rows)
3. **Reduce Pet Order rows**: 23px → 20px (saves 15px)
4. **Smaller font for help text**: Already at 8pt (minimal)

**Potential savings**: ~105px → Could reduce to CONFIG_HEIGHT = 995px

---

## Layout Verification Checklist

- [ ] CONFIG_HEIGHT matches actual content (1100px)
- [ ] configBg height covers all content (740px)
- [ ] SET/CLR buttons have adequate right margin (≥30px)
- [ ] All 8 static labels in visibility array
- [ ] All Y positions verified against calculations
- [ ] No overlapping controls
- [ ] Buttons clickable without hitting window edge
- [ ] Config panel toggles visibility correctly

---

**Generated**: 2026-01-25
**Script**: Test/Tamer_Suite_v2.1.py
**Fix Priority**: CRITICAL (prevents config panel from displaying properly)
