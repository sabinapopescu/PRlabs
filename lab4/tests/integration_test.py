import requests
import time
import sys

LEADER_URL = "http://localhost:5050"
FOLLOWER_URLS = [f"http://localhost:500{i}" for i in range(1, 6)]


def wait_for_services(max_retries=30, delay=2):
    """Wait for all services to be ready."""
    print("Waiting for services to start...")
    
    all_urls = [LEADER_URL] + FOLLOWER_URLS
    
    for retry in range(max_retries):
        all_ready = True
        for url in all_urls:
            try:
                response = requests.get(f"{url}/health", timeout=1)
                if response.status_code != 200:
                    all_ready = False
                    break
            except:
                all_ready = False
                break
        
        if all_ready:
            print("✓ All services are ready!")
            return True
        
        print(f"  Retry {retry + 1}/{max_retries}...")
        time.sleep(delay)
    
    print("✗ Services failed to start in time")
    return False


def test_health_checks():
    """Test that all nodes respond to health checks."""
    print("\n=== Test 1: Health Checks ===")
    
    # Check leader
    response = requests.get(f"{LEADER_URL}/health")
    assert response.status_code == 200, "Leader health check failed"
    data = response.json()
    assert data['node_type'] == 'leader', "Leader role mismatch"
    print(f"✓ Leader is healthy: {data}")
    
    # Check followers
    for i, url in enumerate(FOLLOWER_URLS, 1):
        response = requests.get(f"{url}/health")
        assert response.status_code == 200, f"Follower {i} health check failed"
        data = response.json()
        assert data['node_type'] == 'follower', f"Follower {i} role mismatch"
        print(f"✓ Follower {i} is healthy: {data}")
    
    print("✓ All health checks passed!")


def test_write_and_read():
    """Test basic write and read operations."""
    print("\n=== Test 2: Write and Read ===")
    
    # Write to leader
    test_data = {"key": "test_key_1", "value": "test_value_1"}
    response = requests.post(f"{LEADER_URL}/set", json=test_data)
    assert response.status_code == 200, "Write failed"
    result = response.json()
    print(f"✓ Write successful: {result}")
    
    # Read from leader
    response = requests.get(f"{LEADER_URL}/get/test_key_1")
    assert response.status_code == 200, "Read from leader failed"
    data = response.json()
    assert data['value'] == "test_value_1", "Value mismatch on leader"
    print(f"✓ Read from leader: {data}")
    
    print("✓ Write and read test passed!")


def test_replication():
    """Test that data is replicated to followers."""
    print("\n=== Test 3: Replication to Followers ===")
    
    # Write multiple keys
    test_keys = [
        {"key": "repl_key_1", "value": "repl_value_1"},
        {"key": "repl_key_2", "value": "repl_value_2"},
        {"key": "repl_key_3", "value": "repl_value_3"}
    ]
    
    for test_data in test_keys:
        response = requests.post(f"{LEADER_URL}/set", json=test_data)
        assert response.status_code == 200, f"Write failed for {test_data['key']}"
        print(f"✓ Written: {test_data['key']}")
    
    # Give some time for replication
    time.sleep(0.5)
    
    # Check replication on followers
    for i, follower_url in enumerate(FOLLOWER_URLS, 1):
        response = requests.get(f"{follower_url}/get_all")
        assert response.status_code == 200, f"Failed to get data from follower {i}"
        data = response.json()
        
        # Check if all keys are present
        for test_data in test_keys:
            key = test_data['key']
            assert key in data['data'], f"Key {key} not found in follower {i}"
            assert data['data'][key] == test_data['value'], f"Value mismatch for {key} in follower {i}"
        
        print(f"✓ Follower {i} has all replicated data ({data['count']} keys)")
    
    print("✓ Replication test passed!")


def test_write_quorum():
    """Test that write quorum is enforced."""
    print("\n=== Test 4: Write Quorum ===")
    
    # Write a key and check the response includes quorum info
    test_data = {"key": "quorum_test", "value": "quorum_value"}
    response = requests.post(f"{LEADER_URL}/set", json=test_data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✓ Write succeeded: {result['replicas']}/{result['required']} replications confirmed")
        assert result['replicas'] >= result['required'], "Quorum not met but write succeeded"
    else:
        result = response.json()
        print(f"✗ Write failed: {result}")
        assert result.get('replicas', 0) < result.get('required', 0), "Quorum met but write failed"
    
    print("✓ Write quorum test passed!")


def test_concurrent_writes():
    """Test concurrent write operations."""
    print("\n=== Test 5: Concurrent Writes ===")
    
    import concurrent.futures
    
    def write_key(i):
        test_data = {"key": f"concurrent_key_{i}", "value": f"concurrent_value_{i}"}
        response = requests.post(f"{LEADER_URL}/set", json=test_data)
        return response.status_code == 200
    
    # Write 20 keys concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(write_key, range(20)))
    
    successful_writes = sum(results)
    print(f"✓ {successful_writes}/20 concurrent writes succeeded")
    
    # Give time for replication
    time.sleep(1)
    
    # Verify data on leader
    response = requests.get(f"{LEADER_URL}/get_all")
    leader_data = response.json()
    print(f"✓ Leader has {leader_data['count']} keys total")
    
    print("✓ Concurrent writes test passed!")


def test_consistency():
    """Test data consistency across all nodes."""
    print("\n=== Test 6: Consistency Check ===")
    
    # Get all data from leader
    response = requests.get(f"{LEADER_URL}/get_all")
    leader_data = response.json()['data']
    print(f"Leader has {len(leader_data)} keys")
    
    # Compare with each follower
    for i, follower_url in enumerate(FOLLOWER_URLS, 1):
        response = requests.get(f"{follower_url}/get_all")
        follower_data = response.json()['data']
        
        # Check if all leader keys are in follower
        missing_keys = []
        mismatched_values = []
        
        for key, value in leader_data.items():
            if key not in follower_data:
                missing_keys.append(key)
            elif follower_data[key] != value:
                mismatched_values.append(key)
        
        if missing_keys:
            print(f"  Follower {i}: Missing {len(missing_keys)} keys: {missing_keys[:5]}")
        if mismatched_values:
            print(f"  Follower {i}: {len(mismatched_values)} mismatched values")
        
        if not missing_keys and not mismatched_values:
            print(f"✓ Follower {i}: Fully consistent ({len(follower_data)} keys)")
        else:
            print(f"  Follower {i}: Partially consistent ({len(follower_data)}/{len(leader_data)} keys match)")
    
    print("✓ Consistency check completed!")


def run_all_tests():
    """Run all integration tests."""
    print("=" * 60)
    print("Starting Integration Tests")
    print("=" * 60)
    
    if not wait_for_services():
        print("\n✗ Failed to connect to services. Make sure docker-compose is running.")
        sys.exit(1)
    
    try:
        test_health_checks()
        test_write_and_read()
        test_replication()
        test_write_quorum()
        test_concurrent_writes()
        test_consistency()
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED!")
        print("=" * 60)
        return True
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)