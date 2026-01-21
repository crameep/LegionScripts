import API
import time

# Test script to check which Python modules are available in Legion
# Run this script and check the system messages to see what's available

def test_modules():
    """Test which standard library modules are available"""

    modules_to_test = [
        "urllib",
        "urllib.request",
        "urllib.parse",
        "json",
        "os",
        "sys",
        "io",
        "pathlib",
        "re",
        "hashlib",
        "base64",
        "datetime",
        "collections",
        "http",
        "http.client",
    ]

    API.SysMsg("=== Testing Module Availability ===", 0x35)
    time.sleep(0.5)

    available = []
    unavailable = []

    for module_name in modules_to_test:
        try:
            __import__(module_name)
            available.append(module_name)
            API.SysMsg(f"✓ {module_name} - AVAILABLE", 0x35)
        except ImportError:
            unavailable.append(module_name)
            API.SysMsg(f"✗ {module_name} - NOT AVAILABLE", 0x32)
        time.sleep(0.3)

    API.SysMsg("=== Summary ===", 0x43)
    API.SysMsg(f"Available: {len(available)}/{len(modules_to_test)}", 0x35)
    API.SysMsg(f"Unavailable: {len(unavailable)}/{len(modules_to_test)}", 0x32)

    # If urllib.request is available, test a simple network request
    if "urllib.request" in available:
        API.SysMsg("", 0x35)
        API.SysMsg("=== Testing urllib.request ===", 0x43)
        try:
            import urllib.request
            # Try to fetch a simple text file from GitHub
            test_url = "https://raw.githubusercontent.com/crameep/LegionScripts/main/.gitignore"
            API.SysMsg(f"Attempting to fetch: {test_url}", 0x35)
            time.sleep(0.5)

            with urllib.request.urlopen(test_url, timeout=5) as response:
                data = response.read()
                API.SysMsg(f"✓ SUCCESS! Fetched {len(data)} bytes", 0x35)
                API.SysMsg("Network requests ARE possible!", 0x35)
        except Exception as e:
            API.SysMsg(f"✗ Network request failed: {type(e).__name__}", 0x32)
            API.SysMsg(f"Error: {str(e)}", 0x32)

# Run the test
test_modules()
API.SysMsg("Test complete! Check messages above.", 0x43)
