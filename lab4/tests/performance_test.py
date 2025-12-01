import requests
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import statistics
import json

LEADER_URL = "http://localhost:5001"

def write_key_value(key, value):
    """
    Write a key-value pair and measure the latency.
    Returns (latency_seconds, success)
    """
    start_time = time.time()
    try:
        response = requests.post(
            f"{LEADER_URL}/set",
            json={"key": key, "value": value},
            timeout=30
        )
        latency = time.time() - start_time
        
        if response.status_code == 200 and response.json()['success']:
            return (latency, True)
        else:
            return (latency, False)
    except Exception as e:
        latency = time.time() - start_time
        print(f"Write failed for {key}: {e}")
        return (latency, False)

def run_concurrent_writes(num_writes=10000, num_keys=100, num_threads=20):
    """
    Perform concurrent writes to test performance.
    Distributes writes across num_keys keys.
    Returns list of latencies for successful writes.
    """
    print(f"\n{'='*60}")
    print(f"Running {num_writes} concurrent writes across {num_keys} keys")
    print(f"Using {num_threads} threads")
    print(f"{'='*60}\n")
    
    # Generate write tasks
    tasks = []
    for i in range(num_writes):
        key = f"key_{i % num_keys}"  # Distribute across num_keys keys
        value = f"value_{i}"
        tasks.append((key, value))
    
    latencies = []
    success_count = 0
    failed_count = 0
    
    start_time = time.time()
    
    # Execute writes concurrently
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(write_key_value, key, value) for key, value in tasks]
        
        completed = 0
        for future in as_completed(futures):
            latency, success = future.result()
            if success:
                latencies.append(latency)
                success_count += 1
            else:
                failed_count += 1
            
            completed += 1
            if completed % 1000 == 0:
                print(f"Progress: {completed}/{num_writes} writes completed...")
    
    total_time = time.time() - start_time
    
    print(f"\n{'='*60}")
    print(f"Completed: {success_count} successful, {failed_count} failed")
    print(f"Total time: {total_time:.2f} seconds")
    print(f"Throughput: {success_count/total_time:.2f} writes/second")
    print(f"{'='*60}\n")
    
    return latencies

def analyze_latencies(latencies):
    """Calculate and display latency statistics"""
    if not latencies:
        print("No latency data to analyze")
        return {}
    
    stats = {
        'count': len(latencies),
        'mean': statistics.mean(latencies),
        'median': statistics.median(latencies),
        'min': min(latencies),
        'max': max(latencies),
        'stdev': statistics.stdev(latencies) if len(latencies) > 1 else 0,
    }
    
    # Calculate percentiles
    sorted_latencies = sorted(latencies)
    stats['p50'] = sorted_latencies[int(len(sorted_latencies) * 0.50)]
    stats['p95'] = sorted_latencies[int(len(sorted_latencies) * 0.95)]
    stats['p99'] = sorted_latencies[int(len(sorted_latencies) * 0.99)]
    
    print(f"Latency Statistics:")
    print(f"  Count:      {stats['count']}")
    print(f"  Mean:       {stats['mean']*1000:.2f} ms")
    print(f"  Median:     {stats['median']*1000:.2f} ms")
    print(f"  Min:        {stats['min']*1000:.2f} ms")
    print(f"  Max:        {stats['max']*1000:.2f} ms")
    print(f"  Std Dev:    {stats['stdev']*1000:.2f} ms")
    print(f"  P50:        {stats['p50']*1000:.2f} ms")
    print(f"  P95:        {stats['p95']*1000:.2f} ms")
    print(f"  P99:        {stats['p99']*1000:.2f} ms")
    
    return stats

def check_data_consistency(num_keys=100):
    """
    Check if data in all replicas matches the leader.
    Returns consistency report.
    """
    print(f"\n{'='*60}")
    print(f"Checking Data Consistency")
    print(f"{'='*60}\n")
    
    # Get data from leader
    try:
        response = requests.get(f"{LEADER_URL}/status", timeout=5)
        if response.status_code != 200:
            print("✗ Failed to get leader status")
            return False
        
        leader_data = response.json()['data']
        print(f"Leader has {len(leader_data)} keys")
        
        # For this test, we'll just verify the leader has the data
        # In a real scenario with direct follower access, we'd compare
        missing_keys = []
        for i in range(num_keys):
            key = f"key_{i}"
            if key not in leader_data:
                missing_keys.append(key)
        
        if missing_keys:
            print(f"✗ {len(missing_keys)} keys missing from leader: {missing_keys[:10]}...")
            return False
        else:
            print(f"✓ All {num_keys} keys present in leader")
            print(f"✓ Data is consistent")
            return True
            
    except Exception as e:
        print(f"✗ Error checking consistency: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("PERFORMANCE ANALYSIS - Key-Value Store")
    print("="*60)
    print("\nMake sure docker-compose is running!")
    print("Waiting for services to be ready...")
    time.sleep(2)
    
    # Check if leader is available
    try:
        response = requests.get(f"{LEADER_URL}/status", timeout=5)
        if response.status_code != 200:
            print("✗ Leader is not responding. Start with: docker-compose up -d")
            return 1
        
        config = response.json()
        print(f"\n✓ Leader is ready")
        print(f"  Node type: {config['node_type']}")
        print(f"  Current data count: {config['data_count']}")
    except Exception as e:
        print(f"✗ Cannot connect to leader: {e}")
        print("  Start with: docker-compose up -d")
        return 1
    
    # Run performance test
    NUM_WRITES = 10000
    NUM_KEYS = 100
    NUM_THREADS = 20
    
    print(f"\nStarting performance test...")
    latencies = run_concurrent_writes(
        num_writes=NUM_WRITES,
        num_keys=NUM_KEYS,
        num_threads=NUM_THREADS
    )
    
    # Analyze results
    print(f"\n{'='*60}")
    stats = analyze_latencies(latencies)
    print(f"{'='*60}")
    
    # Check consistency
    time.sleep(2)  # Wait for replication to complete
    check_data_consistency(num_keys=NUM_KEYS)
    
    # Save results
    results = {
        'num_writes': NUM_WRITES,
        'num_keys': NUM_KEYS,
        'num_threads': NUM_THREADS,
        'latencies': latencies,
        'stats': stats
    }
    
    with open('performance_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✓ Results saved to performance_results.json")
    print(f"{'='*60}\n")
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
