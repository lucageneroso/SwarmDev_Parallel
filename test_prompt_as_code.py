"""Verification script for Prompt-as-Code refactoring."""
import sys
import os

# Ensure we can import from project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 50)
print("  Prompt-as-Code Verification Suite")
print("=" * 50)

# Test 1: load_sop import
from llm_wiki import load_sop, _list_available_sops, invalidate_cache
print("\n[TEST 1] load_sop import: PASS")

# Test 2: List available SOPs
sops = _list_available_sops()
print(f"[TEST 2] Available SOPs: {sops}")
expected = {"mind_discovery", "mind_planning", "frontend_actor", "backend_actor"}
assert expected == set(sops), f"Missing SOPs: {expected - set(sops)}"
print(f"[TEST 2] All {len(sops)} SOPs found: PASS")

# Test 3: Load each SOP
for sop_name in sops:
    if sop_name == "mind_discovery":
        content = load_sop(sop_name, brainstorming_skill="TEST_SKILL")
        assert "TEST_SKILL" in content, "Placeholder not injected!"
        print(f"[TEST 3] {sop_name} ({len(content)} chars, placeholder OK): PASS")
    else:
        content = load_sop(sop_name)
        assert len(content) > 50, f"SOP {sop_name} too short!"
        print(f"[TEST 3] {sop_name} ({len(content)} chars): PASS")

# Test 4: Cache invalidation
invalidate_cache()
print("[TEST 4] Cache invalidation: PASS")

# Test 5: FileNotFoundError for missing SOP
try:
    load_sop("nonexistent_sop")
    print("[TEST 5] Missing SOP error: FAIL (no exception raised)")
    sys.exit(1)
except FileNotFoundError as e:
    print(f"[TEST 5] Missing SOP raises FileNotFoundError: PASS")

# Test 6: Import graph_orchestrator (no runtime errors)
print("\n[TEST 6] Importing graph_orchestrator...")
try:
    import graph_orchestrator
    print("[TEST 6] graph_orchestrator import: PASS")
except Exception as e:
    print(f"[TEST 6] graph_orchestrator import FAILED: {e}")
    sys.exit(1)

# Test 7: Confirm no monolithic prompts remain in Python code
print("\n[TEST 7] Checking for leftover monolithic prompts...")
with open(os.path.join(os.path.dirname(__file__), "graph_orchestrator.py"), "r", encoding="utf-8") as f:
    code = f.read()

leftovers = [
    "DISCOVERY_SYSTEM_PROMPT",
    "FRONTEND_SYSTEM_PROMPT",
    "BACKEND_SYSTEM_PROMPT",
]
found = [l for l in leftovers if l in code]
if found:
    print(f"[TEST 7] FAIL — leftover constants found: {found}")
    sys.exit(1)
else:
    print("[TEST 7] No monolithic prompt constants remain: PASS")

# Summary
print("\n" + "=" * 50)
print("  ALL TESTS PASSED ✅")
print("=" * 50)
