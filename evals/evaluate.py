import json, os, sys
import httpx

BASE = os.getenv("AGENT_API", "http://localhost:8000")
data = json.load(open("dataset.json"))

passed = 0
for case in data:
    response = httpx.post(
        f"{BASE}/v1/chat",
        headers={"X-Tenant-Id": case["tenant_id"]},
        json={"message": case["question"], "session_id": "eval-" + case["id"]},
        timeout=120,
    )
    response.raise_for_status()
    answer = response.json()["answer"].lower()
    ok = all(x.lower() in answer for x in case["expected_contains"])
    passed += int(ok)
    print(("PASS" if ok else "FAIL"), case["id"], "=>", answer[:180])

print(f"{passed}/{len(data)} passed")
sys.exit(0 if passed == len(data) else 1)
