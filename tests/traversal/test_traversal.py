import sys
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)
os.chdir(REPO_ROOT)

from service.static_service import static_service

passed = 0
failed = 0

def check(name, condition):
    global passed, failed
    if condition:
        print("PASS", name)
        passed += 1
    else:
        print("FAIL", name)
        failed += 1

leak = static_service("/public/../../../../etc/passwd")
check("traversal to /etc/passwd is blocked", b"root:" not in leak)
check("traversal returns the generic not-found", leak == b"file not found")
check("single ../ escape blocked", static_service("/public/../server.py") == b"file not found")
check("deep escape blocked", static_service("/public/../../../../etc/shadow") == b"file not found")
index = static_service("/public/index.html")
check("public/index.html still served", index != b"file not found" and len(index) > 0)

print()
print(str(passed) + " passed, " + str(failed) + " failed")
sys.exit(1 if failed else 0)
