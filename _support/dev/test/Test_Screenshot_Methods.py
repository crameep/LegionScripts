import API
import time

__version__ = "1.0"

# Test which screenshot-related modules and methods are available

def test_modules():
    """Test which modules are available"""
    API.SysMsg("=== Testing Screenshot Modules ===", 43)
    time.sleep(0.3)

    modules = ["subprocess", "ctypes", "PIL", "mss"]
    available = []

    for name in modules:
        try:
            __import__(name)
            available.append(name)
            API.SysMsg(f"✓ {name} - AVAILABLE", 68)
        except ImportError:
            API.SysMsg(f"✗ {name} - NOT AVAILABLE", 32)
        time.sleep(0.3)

    return available

def test_api_methods():
    """Test if Legion API has screenshot methods"""
    API.SysMsg("", 43)
    API.SysMsg("=== Testing Legion API ===", 43)
    time.sleep(0.3)

    methods = ["TakeScreenshot", "Screenshot", "CaptureScreen"]

    for method in methods:
        if hasattr(API, method):
            API.SysMsg(f"✓ API.{method} - EXISTS", 68)
        else:
            API.SysMsg(f"✗ API.{method} - NOT FOUND", 32)
        time.sleep(0.3)

def test_subprocess():
    """Test if subprocess + PowerShell works"""
    API.SysMsg("", 43)
    API.SysMsg("=== Testing PowerShell ===", 43)
    time.sleep(0.3)

    try:
        import subprocess
        ps_cmd = 'Write-Host "PowerShell test successful"'
        result = subprocess.run(["powershell", "-Command", ps_cmd],
                               capture_output=True, timeout=5, text=True)
        if result.returncode == 0:
            API.SysMsg("✓ PowerShell works!", 68)
            API.SysMsg(f"Output: {result.stdout.strip()}", 88)
        else:
            API.SysMsg("✗ PowerShell failed", 32)
    except Exception as e:
        API.SysMsg(f"✗ PowerShell error: {type(e).__name__}", 32)
        API.SysMsg(f"  {str(e)}", 32)

def test_ctypes():
    """Test if ctypes works"""
    API.SysMsg("", 43)
    API.SysMsg("=== Testing ctypes ===", 43)
    time.sleep(0.3)

    try:
        import ctypes
        from ctypes import windll

        # Try to get screen metrics
        user32 = windll.user32
        width = user32.GetSystemMetrics(0)
        height = user32.GetSystemMetrics(1)

        API.SysMsg(f"✓ ctypes works!", 68)
        API.SysMsg(f"  Screen: {width}x{height}", 88)
    except Exception as e:
        API.SysMsg(f"✗ ctypes error: {type(e).__name__}", 32)
        API.SysMsg(f"  {str(e)}", 32)

# Run all tests
available = test_modules()
test_api_methods()

if "subprocess" in available:
    test_subprocess()

if "ctypes" in available:
    test_ctypes()

API.SysMsg("", 43)
API.SysMsg("=== Test Complete ===", 43)
API.SysMsg("Check messages above for results", 88)
