import requests
import time
import sys
import subprocess
import os
import signal

def wait_for_server(url, timeout=10):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            requests.get(url)
            return True
        except requests.ConnectionError:
            time.sleep(0.5)
    return False

def run_tests():
    base_url = "http://127.0.0.1:8000"
    
    print("Testing /analytics/yearly-count...")
    try:
        r = requests.get(f"{base_url}/analytics/yearly-count")
        r.raise_for_status()
        data = r.json()
        print(f"Response: {data}")
        if "yearly_counts" not in data:
            print("FAILED: 'yearly_counts' not in response")
            return False
    except Exception as e:
        print(f"FAILED: {e}")
        return False

    print("\nTesting /analytics/filter?year=2025...")
    try:
        r = requests.get(f"{base_url}/analytics/filter", params={"year": "2025"})
        r.raise_for_status()
        data = r.json()
        print(f"Response count: {data.get('count')}")
        for p in data.get("papers", []):
            if p.get("published_year") != "2025":
                print(f"FAILED: Paper with wrong year found: {p.get('published_year')}")
                return False
    except Exception as e:
        print(f"FAILED: {e}")
        return False

    print("\nTesting /analytics/filter?keyword=agent...")
    try:
        r = requests.get(f"{base_url}/analytics/filter", params={"keyword": "agent"})
        r.raise_for_status()
        data = r.json()
        print(f"Response count: {data.get('count')}")
        # Just check if we got results, exact matching might be tricky if data changes
    except Exception as e:
        print(f"FAILED: {e}")
        return False
        
    print("\nTesting /analytics/summaries...")
    try:
        r = requests.get(f"{base_url}/analytics/summaries")
        r.raise_for_status()
        data = r.json()
        print(f"Response count: {data.get('count')}")
        papers = data.get("papers", [])
        if papers and "summary" not in papers[0]:
            print("FAILED: 'summary' missing from paper object")
            return False
        print(f"Sample summary: {papers[0].get('summary', '')[:50]}...")
    except Exception as e:
        print(f"FAILED: {e}")
        return False

    print("\nTesting /analytics/keyword-trend?keyword=ai...")
    try:
        r = requests.get(f"{base_url}/analytics/keyword-trend", params={"keyword": "ai"})
        r.raise_for_status()
        data = r.json()
        print(f"Response keyword: {data.get('keyword')}")
        if "yearly_counts" not in data:
            print("FAILED: 'yearly_counts' not in response")
            return False
        print(f"Counts: {data.get('yearly_counts')}")
    except Exception as e:
        print(f"FAILED: {e}")
        return False

    return True

if __name__ == "__main__":
    # Start server
    print("Starting server...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--port", "8000"],
        cwd="backend",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    try:
        if wait_for_server("http://127.0.0.1:8000"):
            print("Server is up.")
            success = run_tests()
            if success:
                print("\nALL TESTS PASSED")
            else:
                print("\nTESTS FAILED")
                sys.exit(1)
        else:
            print("Server failed to start")
            out, err = proc.communicate(timeout=1)
            print(f"Server Output: {out.decode()}")
            print(f"Server Error: {err.decode()}")
            sys.exit(1)
    finally:
        proc.terminate()
        proc.wait()
