import os
import sys
import time
import subprocess
import json

WORKSPACE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def run_step_in_subprocess(name, code, timeout_sec=15, env=None):
    print(f"\n=======================================================")
    print(f"RUNNING STEP: {name} (Process timeout: {timeout_sec}s)")
    print(f"=======================================================")
    start_t = time.time()
    
    current_env = os.environ.copy()
    if env:
        current_env.update(env)
    
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            env=current_env
        )
        elapsed = time.time() - start_t
        print(f"[{name}] Finished in {elapsed:.2f}s | Exit Code: {proc.returncode}")
        if proc.stdout:
            print(f"[{name}] STDOUT:\n{proc.stdout.strip()}")
        if proc.stderr:
            print(f"[{name}] STDERR:\n{proc.stderr.strip()}")
        return proc.returncode == 0, elapsed
    except subprocess.TimeoutExpired as exc:
        elapsed = time.time() - start_t
        print(f"[{name}] TIMEOUT EXPIRED after {elapsed:.2f}s! Subprocess was forcefully killed.")
        if exc.stdout:
            print(f"[{name}] Partial stdout: {exc.stdout.decode('utf-8', errors='replace')}")
        if exc.stderr:
            print(f"[{name}] Partial stderr: {exc.stderr.decode('utf-8', errors='replace')}")
        return False, elapsed

def main():
    results = {}
    
    # -------------------------------------------------------------------------
    # Step 1: SerpAPIService with invalid key (bounded response/error)
    # -------------------------------------------------------------------------
    step1_code = """
import os
import time
import sys
from backend.services.serpapi_service import (
    SerpAPIService,
    SerpAPIAuthError,
    SerpAPIError,
    SerpAPITimeoutError,
    SerpAPINetworkError
)

print("[Step 1] Initializing SerpAPIService with invalid_key...", flush=True)
service = SerpAPIService(api_key="invalid_key", timeout=(3.0, 5.0))
t0 = time.time()
try:
    print(f"[Step 1] Calling search_news('test')...", flush=True)
    res = service.search_news("test", timeout=(3.0, 5.0))
    print(f"[Step 1] Success (unexpected for invalid_key): {res}", flush=True)
    sys.exit(0)
except SerpAPIAuthError as e:
    print(f"[Step 1] Successfully caught SerpAPIAuthError in {time.time()-t0:.2f}s: {e}", flush=True)
    sys.exit(0)
except (SerpAPITimeoutError, SerpAPINetworkError, SerpAPIError) as e:
    print(f"[Step 1] Bounded error caught in {time.time()-t0:.2f}s: {type(e).__name__}: {e}", flush=True)
    sys.exit(0)
except Exception as e:
    print(f"[Step 1] Unexpected exception: {type(e).__name__}: {e}", flush=True)
    sys.exit(1)
"""
    results["step1_invalid_key"] = run_step_in_subprocess(
        "Step 1: SerpAPIService with invalid_key",
        step1_code,
        timeout_sec=15,
        env={"SERPAPI_API_KEY": "invalid_key"}
    )

    # -------------------------------------------------------------------------
    # Step 2: SerpAPIService with missing key (immediate configuration error)
    # -------------------------------------------------------------------------
    step2_code = """
import os
import time
import sys
from backend.services.serpapi_service import SerpAPIService, SerpAPIConfigurationError

print("[Step 2] Initializing SerpAPIService with no key...", flush=True)
# Ensure environment variable is cleared
if "SERPAPI_API_KEY" in os.environ:
    del os.environ["SERPAPI_API_KEY"]

service = SerpAPIService(api_key=None)
t0 = time.time()
try:
    print("[Step 2] Calling search_news('test')...", flush=True)
    service.search_news("test")
    print("[Step 2] FAILED: Should have raised SerpAPIConfigurationError", flush=True)
    sys.exit(1)
except SerpAPIConfigurationError as e:
    elapsed = time.time() - t0
    print(f"[Step 2] PASSED: SerpAPIConfigurationError raised immediately ({elapsed:.4f}s): {e}", flush=True)
    assert elapsed < 1.0, f"Missing key took too long: {elapsed}s"
    sys.exit(0)
except Exception as e:
    print(f"[Step 2] FAILED with unexpected error: {type(e).__name__}: {e}", flush=True)
    sys.exit(1)
"""
    # Force empty SERPAPI_API_KEY
    results["step2_missing_key"] = run_step_in_subprocess(
        "Step 2: SerpAPIService with missing key",
        step2_code,
        timeout_sec=5,
        env={"SERPAPI_API_KEY": ""}
    )

    # -------------------------------------------------------------------------
    # Step 3: Flask /api/news/search without q -> immediate 4xx
    # -------------------------------------------------------------------------
    step3_code = """
import time
import sys
from backend.app import app

client = app.test_client()
t0 = time.time()
resp = client.get("/api/news/search")
elapsed = time.time() - t0
print(f"[Step 3] Status: {resp.status_code} in {elapsed:.4f}s", flush=True)
data = resp.get_json()
print(f"[Step 3] Response: {data}", flush=True)
assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
assert data.get("success") is False, "Expected success: False"
assert data.get("code") == "MISSING_QUERY", f"Expected MISSING_QUERY, got {data.get('code')}"
assert elapsed < 1.0, f"Request took too long: {elapsed}s"
print("[Step 3] PASSED", flush=True)
sys.exit(0)
"""
    results["step3_flask_missing_q"] = run_step_in_subprocess(
        "Step 3: Flask /api/news/search without 'q'",
        step3_code,
        timeout_sec=5
    )

    # -------------------------------------------------------------------------
    # Step 4: Flask /api/news/search with query -> bounded response
    # -------------------------------------------------------------------------
    step4_code = """
import os
import time
import sys
from backend.app import app

client = app.test_client()
t0 = time.time()
print("[Step 4] Calling GET /api/news/search?q=technology with invalid key...", flush=True)
resp = client.get("/api/news/search?q=technology")
elapsed = time.time() - t0
print(f"[Step 4] Completed in {elapsed:.2f}s | Status: {resp.status_code}", flush=True)
data = resp.get_json()
print(f"[Step 4] Response: {data}", flush=True)
assert resp.status_code in (502, 503, 504), f"Expected 502/503/504, got {resp.status_code}"
assert data.get("success") is False, "Expected success: False"
assert elapsed < 15.0, f"Response was not bounded: {elapsed}s"
print("[Step 4] PASSED: Bounded error returned cleanly", flush=True)
sys.exit(0)
"""
    results["step4_flask_with_query"] = run_step_in_subprocess(
        "Step 4: Flask /api/news/search with query (invalid key)",
        step4_code,
        timeout_sec=15,
        env={"SERPAPI_API_KEY": "invalid_key"}
    )

    # -------------------------------------------------------------------------
    # Step 5: /health works after all failures
    # -------------------------------------------------------------------------
    step5_code = """
import time
import sys
from backend.app import app

client = app.test_client()

# Trigger multiple failure modes first
client.get("/api/news/search")
client.get("/api/news/search?q=")
client.get("/api/news/search?q=   ")

# Check /health responsiveness
t0 = time.time()
resp = client.get("/health")
elapsed = time.time() - t0
print(f"[Step 5] GET /health responded in {elapsed:.4f}s with status {resp.status_code}", flush=True)
data = resp.get_json()
print(f"[Step 5] Response: {data}", flush=True)
assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
assert data.get("status") == "healthy", f"Expected healthy, got {data}"
assert elapsed < 1.0, f"/health took too long: {elapsed}s"
print("[Step 5] PASSED: /health is completely responsive", flush=True)
sys.exit(0)
"""
    results["step5_health_after_failures"] = run_step_in_subprocess(
        "Step 5: /health works after all failures",
        step5_code,
        timeout_sec=5
    )

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print("\n=======================================================")
    print("ISOLATED TEST SUITE SUMMARY:")
    print("=======================================================")
    all_passed = True
    for test_name, (passed, dur) in results.items():
        status_str = "PASSED" if passed else "FAILED"
        print(f" - {test_name}: {status_str} ({dur:.2f}s)")
        if not passed:
            all_passed = False

    print("=======================================================")
    if all_passed:
        print("ALL ISOLATED STEP CHECKS PASSED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("SOME CHECKS FAILED!")
        sys.exit(1)

if __name__ == "__main__":
    main()
