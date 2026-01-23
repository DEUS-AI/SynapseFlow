import os
import subprocess
import sys

def test_generate_data_map():
    # Ensure FalkorDB is reachable (use env vars)
    host = os.getenv("FALKORDB_HOST", "localhost")
    port = os.getenv("FALKORDB_PORT", "6379")
    # Run the script
    result = subprocess.run([sys.executable, "scripts/generate_data_map.py"], capture_output=True, text=True)
    assert result.returncode == 0, f"Script failed: {result.stderr}"
    # Check that CSV file exists and is non‑empty
    assert os.path.isfile("data_map.csv"), "data_map.csv not created"
    assert os.path.getsize("data_map.csv") > 0, "data_map.csv is empty"
    # Clean up generated files
    for f in ["data_map.csv", "data_map.xlsx", "data_map.html"]:
        if os.path.isfile(f):
            os.remove(f)

if __name__ == "__main__":
    test_generate_data_map()
    print("✅ test_generate_data_map passed")
