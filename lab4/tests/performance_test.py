"""
Performance Analysis for Key-Value Store with Leader-Follower Replication
Tests write performance with different quorum values and checks data consistency.
"""

import requests
import time
import statistics
import json
import matplotlib.pyplot as plt
from concurrent.futures import ThreadPoolExecutor, as_completed

LEADER_URL = "http://localhost:5050"
FOLLOWER_URLS = [f"http://localhost:500{i}" for i in range(1, 6)]

NUM_WRITES = 100   # Start small for testing with large delays
NUM_KEYS = 20      # Fewer keys for initial testing
NUM_THREADS = 5    # Fewer threads to avoid overwhelming with large delays


def write_key_value(key, value):
    """
    Write a key-value pair and measure the latency.
    Returns (total_latency_ms, avg_replication_latency_ms, success)
    """
    start_time = time.time()
    try:
        response = requests.post(
            f"{LEADER_URL}/set",
            json={"key": key, "value": value},
            timeout=30
        )
        total_latency = (time.time() - start_time) * 1000  # ms
        
        if response.status_code == 200:
            result = response.json()
            avg_repl_latency = result.get('avg_replication_latency_ms', 0)
            return (total_latency, avg_repl_latency, True)
        else:
            return (total_latency, 0, False)
    except Exception as e:
        total_latency = (time.time() - start_time) * 1000
        print(f"Write failed for {key}: {e}")
        return (total_latency, 0, False)


def run_concurrent_writes(num_writes=NUM_WRITES, num_keys=NUM_KEYS, num_threads=NUM_THREADS):
    """
    Perform concurrent writes to test performance.
    Returns (total_latencies, replication_latencies, success_count, failed_count, total_time)
    """
    print(f"\n{'='*60}")
    print(f"Running {num_writes} concurrent writes across {num_keys} keys")
    print(f"Using {num_threads} threads")
    print(f"{'='*60}\n")
    
    # Generate write tasks
    tasks = []
    for i in range(num_writes):
        key = f"key_{i % num_keys}"  # Cycle through NUM_KEYS keys
        value = f"value_{i}_{time.time()}"
        tasks.append((key, value))
    
    total_latencies = []
    replication_latencies = []
    success_count = 0
    failed_count = 0
    
    start_time = time.time()
    
    # Execute writes concurrently
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(write_key_value, key, value) for key, value in tasks]
        
        completed = 0
        for future in as_completed(futures):
            total_lat, repl_lat, success = future.result()
            if success:
                total_latencies.append(total_lat)
                if repl_lat > 0:
                    replication_latencies.append(repl_lat)
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
    
    return total_latencies, replication_latencies, success_count, failed_count, total_time


def analyze_latencies(total_latencies, replication_latencies):
    """Calculate and display latency statistics"""
    if not total_latencies:
        print("No latency data to analyze")
        return {}
    
    sorted_total = sorted(total_latencies)
    sorted_repl = sorted(replication_latencies) if replication_latencies else []
    
    stats = {
        'count': len(total_latencies),
        'total_mean': statistics.mean(total_latencies),
        'total_median': statistics.median(total_latencies),
        'total_min': min(total_latencies),
        'total_max': max(total_latencies),
        'total_stdev': statistics.stdev(total_latencies) if len(total_latencies) > 1 else 0,
        'total_p50': sorted_total[int(len(sorted_total) * 0.50)],
        'total_p95': sorted_total[int(len(sorted_total) * 0.95)],
        'total_p99': sorted_total[int(len(sorted_total) * 0.99)],
    }
    
    if replication_latencies:
        stats.update({
            'repl_mean': statistics.mean(replication_latencies),
            'repl_median': statistics.median(replication_latencies),
            'repl_min': min(replication_latencies),
            'repl_max': max(replication_latencies),
            'repl_stdev': statistics.stdev(replication_latencies) if len(replication_latencies) > 1 else 0,
            'repl_p50': sorted_repl[int(len(sorted_repl) * 0.50)],
            'repl_p95': sorted_repl[int(len(sorted_repl) * 0.95)],
            'repl_p99': sorted_repl[int(len(sorted_repl) * 0.99)],
        })
    
    print(f"Total Latency Statistics:")
    print(f"  Count:      {stats['count']}")
    print(f"  Mean:       {stats['total_mean']:.2f} ms")
    print(f"  Median:     {stats['total_median']:.2f} ms")
    print(f"  Min:        {stats['total_min']:.2f} ms")
    print(f"  Max:        {stats['total_max']:.2f} ms")
    print(f"  Std Dev:    {stats['total_stdev']:.2f} ms")
    print(f"  P50:        {stats['total_p50']:.2f} ms")
    print(f"  P95:        {stats['total_p95']:.2f} ms")
    print(f"  P99:        {stats['total_p99']:.2f} ms")
    
    if replication_latencies:
        print(f"\nAverage Replication Latency Statistics:")
        print(f"  Mean:       {stats['repl_mean']:.2f} ms")
        print(f"  Median:     {stats['repl_median']:.2f} ms")
        print(f"  Min:        {stats['repl_min']:.2f} ms")
        print(f"  Max:        {stats['repl_max']:.2f} ms")
        print(f"  Std Dev:    {stats['repl_stdev']:.2f} ms")
        print(f"  P95:        {stats['repl_p95']:.2f} ms")
    
    return stats


def check_data_consistency():
    """Check if data in all replicas matches the leader."""
    print(f"\n{'='*60}")
    print(f"Checking Data Consistency")
    print(f"{'='*60}\n")
    
    try:
        # Get data from leader
        response = requests.get(f"{LEADER_URL}/get_all", timeout=5)
        if response.status_code != 200:
            print("✗ Failed to get leader data")
            return False
        
        leader_data = response.json()['data']
        leader_count = len(leader_data)
        print(f"Leader has {leader_count} keys")
        
        # Check each follower
        all_consistent = True
        for i, follower_url in enumerate(FOLLOWER_URLS, 1):
            try:
                response = requests.get(f"{follower_url}/get_all", timeout=5)
                if response.status_code != 200:
                    print(f"✗ Follower {i}: Failed to retrieve data")
                    all_consistent = False
                    continue
                
                follower_data = response.json()['data']
                follower_count = len(follower_data)
                
                # Check for missing keys
                missing_keys = set(leader_data.keys()) - set(follower_data.keys())
                
                # Check for mismatched values
                mismatched = 0
                for key in set(leader_data.keys()) & set(follower_data.keys()):
                    if leader_data[key] != follower_data[key]:
                        mismatched += 1
                
                consistency_pct = ((follower_count - mismatched) / leader_count * 100) if leader_count > 0 else 0
                
                print(f"Follower {i}: {follower_count}/{leader_count} keys, {consistency_pct:.1f}% consistent")
                
                if consistency_pct != 100:
                    all_consistent = False
                
            except Exception as e:
                print(f"✗ Follower {i}: Error - {e}")
                all_consistent = False
        
        return all_consistent
            
    except Exception as e:
        print(f"✗ Error checking consistency: {e}")
        return False


def main():
    print("\n" + "="*80)
    print("PERFORMANCE ANALYSIS - Key-Value Store with Leader-Follower Replication")
    print("="*80)
    
    # Check if services are ready
    print("\nChecking if services are ready...")
    try:
        response = requests.get(f"{LEADER_URL}/health", timeout=5)
        if response.status_code != 200:
            print("✗ Leader is not responding. Start with: ./run.sh")
            return 1
        print("✓ Leader is ready")
    except Exception as e:
        print(f"✗ Cannot connect to leader: {e}")
        print("  Start with: ./run.sh")
        return 1
    
    # Get current quorum setting
    response = requests.get(f"{LEADER_URL}/status")
    current_quorum = response.json().get('write_quorum', 'unknown')
    print(f"✓ Current write quorum: {current_quorum}")
    
    # Run performance test
    print(f"\n{'='*80}")
    print(f"Running performance test with WRITE_QUORUM={current_quorum}")
    print(f"{'='*80}")
    
    total_lats, repl_lats, success_count, failed_count, total_time = run_concurrent_writes()
    
    # Analyze results
    print(f"\n{'='*80}")
    stats = analyze_latencies(total_lats, repl_lats)
    print(f"{'='*80}")
    
    # Wait for replication to complete
    print("\nWaiting for replication to complete...")
    time.sleep(3)
    
    # Check consistency
    check_data_consistency()
    
    # Save results
    import os
    os.makedirs('results', exist_ok=True)
    
    results = {
        'config': {
            'num_writes': NUM_WRITES,
            'num_keys': NUM_KEYS,
            'num_threads': NUM_THREADS,
            'write_quorum': current_quorum
        },
        'performance': {
            'success_count': success_count,
            'failed_count': failed_count,
            'total_time': total_time,
            'throughput': success_count / total_time if total_time > 0 else 0
        },
        'latency_stats': {k: float(v) if isinstance(v, (int, float)) else v 
                         for k, v in stats.items()}
    }
    
    with open('results/performance_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✓ Results saved to results/performance_results.json")
    
    print(f"\n{'='*80}")
    print("ANALYSIS COMPLETE!")
    print(f"{'='*80}\n")
    
    # Print summary
    print("SUMMARY:")
    print(f"  Write Quorum: {current_quorum}")
    print(f"  Total Avg Latency: {stats['total_mean']:.2f} ms")
    if 'repl_mean' in stats:
        print(f"  Avg Replication Latency: {stats['repl_mean']:.2f} ms")
    print(f"  Throughput: {success_count/total_time:.2f} writes/sec")
    print(f"  Success Rate: {success_count/NUM_WRITES*100:.1f}%")
    print()
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())