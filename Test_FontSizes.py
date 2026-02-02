# Test_FontSizes.py
# Find minimum safe font size for work machine
import API

gump = API.Gumps.CreateGump()
gump.SetRect(100, 100, 400, 500)

bg = API.Gumps.CreateGumpColorBox(0.85, "#1a1a2e")
bg.SetRect(0, 0, 400, 500)
gump.Add(bg)

y = 10
for size in range(16, 6, -1):  # Test 16 down to 7
    try:
        API.SysMsg(f"Testing font size {size}...", 88)
        label = API.Gumps.CreateGumpTTFLabel(f"Font Size {size}", size, "#00ff00")
        label.SetPos(10, y)
        gump.Add(label)
        API.SysMsg(f"Font size {size} - SUCCESS", 68)
        y += 25
    except Exception as e:
        API.SysMsg(f"Font size {size} - FAILED: {str(e)}", 32)
        API.SysMsg(f"MINIMUM SAFE FONT SIZE IS: {size + 1}", 53)
        break

API.Gumps.AddGump(gump)
API.SysMsg("Test complete. Press STOP to close.", 43)

while not API.StopRequested:
    API.Pause(0.5)

gump.Dispose()
