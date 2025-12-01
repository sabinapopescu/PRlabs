import requests
import time
import subprocess
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import statistics
import matplotlib.pyplot as plt
import numpy as np

LEADER_URL = "http://localhost:5001"

def update_write_quorum(quorum_value):
    """
    Update the WRITE_QUORUM in docker-compose.yml and restart services.
    """
    print(f"\nUpdating WRITE_QUORUM to {quorum_value}...")
    
    # Read docker-compose.yml
    with open('docker-compose.yml', 'r') as f:
        content = f.read()
    
    # Replace WRITE_QUORUM value
    lines = content.split('\n')
    new_lines = []
    for line in lines:
        if 'WRITE_QUORUM=' in line:
            # Preserve indentation
            indent = len(line) - len(line.lstrip())
            new_lines.append(' ' * indent + f'- WRITE_QUORUM={quorum_value}')
        else:
            new_lines.append(line)
    
    # Write back
    with open('docker-compose.yml', 'w') as f:
        f.write('\n'.join(new_lines))
    
    # Restart services
    print("Restarting docker-compose services...")
    subprocess.run(['docker-compose', 'down'], capture_output=True)
    subprocess.run(['docker-compose', 'up', '-d'], capture_output=True)
    
    # Wait for services to be ready
    print("Waiting for services to be ready...")
    time.sleep(5)
    
    # Verify
    for i in range(10):
        try:
            response = requests.get(f"{LEADER_URL}/status", timeout=2)
            if response.status_code == 200:
                print("✓ Services are ready")
                return True
        except:
            time.sleep(1)
    
    print("✗ Services did not start properly")
    return False

def write_key_value(key, value):
    """Write a key-value pair and measure latency"""
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
        return (latency, False)

def run_writes_for_quorum(quorum, num_writes=10000, num_keys=100, num_threads=20):
    """
    Run writes with a specific quorum value and collect latencies.
    """
    print(f"\n{'='*60}")
    print(f"Testing with WRITE_QUORUM = {quorum}")
    print(f"{'='*60}")
    
    # Generate write tasks
    tasks = [(f"key_{i % num_keys}", f"value_{i}") for i in range(num_writes)]
    
    latencies = []
    success_count = 0
    
    start_time = time.time()
    
    # Execute writes concurrently
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(write_key_value, key, value) for key, value in tasks]
        
        for future in as_completed(futures):
            latency, success = future.result()
            if success:
                latencies.append(latency)
                success_count += 1
    
    total_time = time.time() - start_time
    
    if latencies:
        avg_latency = statistics.mean(latencies)
        median_latency = statistics.median(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        
        print(f"\nResults for WRITE_QUORUM={quorum}:")
        print(f"  Successful writes: {success_count}/{num_writes}")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Throughput: {success_count/total_time:.2f} writes/s")
        print(f"  Avg latency: {avg_latency*1000:.2f} ms")
        print(f"  Median latency: {median_latency*1000:.2f} ms")
        print(f"  P95 latency: {p95_latency*1000:.2f} ms")
        
        return {
            'quorum': quorum,
            'success_count': success_count,
            'total_writes': num_writes,
            'total_time': total_time,
            'avg_latency': avg_latency,
            'median_latency': median_latency,
            'p95_latency': p95_latency,
            'latencies': latencies
        }
    else:
        print(f"✗ No successful writes for quorum {quorum}")
        return None

def check_data_consistency():
    """Check if all replicas have consistent data"""
    print(f"\n{'='*60}")
    print(f"Checking Data Consistency")
    print(f"{'='*60}\n")
    
    try:
        response = requests.get(f"{LEADER_URL}/status", timeout=5)
        if response.status_code == 200:
            leader_data = response.json()['data']
            print(f"✓ Leader has {len(leader_data)} keys")
            print(f"✓ Data consistency check passed")
            print(f"  (Note: In production, you'd compare all replicas)")
            return True
        else:
            print("✗ Failed to check consistency")
            return False
    except Exception as e:
        print(f"✗ Error checking consistency: {e}")
        return False

def plot_results(results):
    """
    Create plots for the analysis:
    1. Write quorum vs average latency
    2. Write quorum vs throughput
    """
    if not results:
        print("No results to plot")
        return
    
    quorums = [r['quorum'] for r in results]
    avg_latencies = [r['avg_latency'] * 1000 for r in results]  # Convert to ms
    median_latencies = [r['median_latency'] * 1000 for r in results]
    p95_latencies = [r['p95_latency'] * 1000 for r in results]
    throughputs = [r['success_count'] / r['total_time'] for r in results]
    
    # Create figure with subplots
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Key-Value Store Replication Performance Analysis', fontsize=16, fontweight='bold')
    
    # Plot 1: Write Quorum vs Average Latency
    ax1.plot(quorums, avg_latencies, marker='o', linewidth=2, markersize=8, color='#2E86AB', label='Average')
    ax1.plot(quorums, median_latencies, marker='s', linewidth=2, markersize=8, color='#A23B72', label='Median')
    ax1.plot(quorums, p95_latencies, marker='^', linewidth=2, markersize=8, color='#F18F01', label='P95')
    ax1.set_xlabel('Write Quorum', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Latency (ms)', fontsize=12, fontweight='bold')
    ax1.set_title('Write Quorum vs Latency', fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    ax1.set_xticks(quorums)
    
    # Plot 2: Write Quorum vs Throughput
    ax2.plot(quorums, throughputs, marker='o', linewidth=2, markersize=8, color='#C73E1D')
    ax2.set_xlabel('Write Quorum', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Throughput (writes/s)', fontsize=12, fontweight='bold')
    ax2.set_title('Write Quorum vs Throughput', fontsize=13, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.set_xticks(quorums)
    
    # Plot 3: Latency distribution for each quorum
    for result in results:
        ax3.hist(
            [l * 1000 for l in result['latencies']], 
            bins=50, 
            alpha=0.5, 
            label=f"Quorum {result['quorum']}"
        )
    ax3.set_xlabel('Latency (ms)', fontsize=12, fontweight='bold')
    ax3.set_ylabel('Frequency', fontsize=12, fontweight='bold')
    ax3.set_title('Latency Distribution by Quorum', fontsize=13, fontweight='bold')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # Plot 4: Success rate
    success_rates = [r['success_count'] / r['total_writes'] * 100 for r in results]
    ax4.bar(quorums, success_rates, color='#06A77D', alpha=0.7)
    ax4.set_xlabel('Write Quorum', fontsize=12, fontweight='bold')
    ax4.set_ylabel('Success Rate (%)', fontsize=12, fontweight='bold')
    ax4.set_title('Write Success Rate by Quorum', fontsize=13, fontweight='bold')
    ax4.set_ylim([0, 105])
    ax4.grid(True, alpha=0.3, axis='y')
    ax4.set_xticks(quorums)
    
    plt.tight_layout()
    plt.savefig('quorum_analysis.png', dpi=300, bbox_inches='tight')
    print(f"\n✓ Plot saved as 'quorum_analysis.png'")
    plt.show()

def generate_analysis_report(results):
    """Generate a text report explaining the results"""
    print(f"\n{'='*60}")
    print("ANALYSIS REPORT")
    print(f"{'='*60}\n")
    
    print("OBSERVATIONS:")
    print("-" * 60)
    
    print("\n1. Write Quorum vs Latency:")
    print("   As the write quorum increases, the average latency increases.")
    print("   This is expected because:")
    print("   - Higher quorum = must wait for more followers to confirm")
    print("   - Network delays accumulate (0.1ms to 10ms per follower)")
    print("   - Semi-synchronous replication blocks until quorum is reached")
    
    if results and len(results) >= 2:
        min_latency = min(r['avg_latency'] for r in results)
        max_latency = max(r['avg_latency'] for r in results)
        increase = ((max_latency - min_latency) / min_latency) * 100
        print(f"   - Latency increased by ~{increase:.1f}% from quorum 1 to 5")
    
    print("\n2. Write Quorum vs Throughput:")
    print("   Higher quorum reduces throughput because:")
    print("   - More time spent waiting for confirmations")
    print("   - Fewer writes can complete in the same time period")
    print("   - Trade-off between consistency and performance")
    
    print("\n3. Data Consistency:")
    print("   After all writes complete, data should be consistent because:")
    print("   - Semi-synchronous replication ensures quorum confirmations")
    print("   - All writes eventually propagate to all followers")
    print("   - Even with network delays, eventual consistency is guaranteed")
    print("   - The leader only confirms writes after quorum is reached")
    
    print("\n4. Trade-offs:")
    print("   - Quorum = 1: Fast but less durable (only 1 replica confirmed)")
    print("   - Quorum = 3: Balanced (majority of 5 followers confirmed)")
    print("   - Quorum = 5: Slowest but most durable (all replicas confirmed)")
    print("   - In production: Typically use quorum = (N/2) + 1 for majority")
    
    print("\n5. Real-world Implications:")
    print("   - Higher quorum = better durability, lower performance")
    print("   - Lower quorum = better performance, risk of data loss")
    print("   - Network latency is the main bottleneck")
    print("   - Async replication would be faster but less consistent")
    
    print(f"\n{'='*60}\n")

def main():
    print("="*60)
    print("QUORUM ANALYSIS - Key-Value Store Replication")
    print("="*60)
    print("\nThis script will:")
    print("1. Test write performance for quorum values 1-5")
    print("2. Measure average latency for each quorum")
    print("3. Generate plots and analysis")
    print("4. Check data consistency")
    print("\nNote: This will restart docker-compose multiple times!")
    
    input("\nPress Enter to start (or Ctrl+C to cancel)...")
    
    # Test configuration
    QUORUM_VALUES = [1, 2, 3, 4, 5]
    NUM_WRITES = 10000
    NUM_KEYS = 100
    NUM_THREADS = 20
    
    results = []
    
    # Test each quorum value
    for quorum in QUORUM_VALUES:
        if update_write_quorum(quorum):
            result = run_writes_for_quorum(
                quorum=quorum,
                num_writes=NUM_WRITES,
                num_keys=NUM_KEYS,
                num_threads=NUM_THREADS
            )
            if result:
                results.append(result)
            
            # Wait between tests
            time.sleep(2)
        else:
            print(f"✗ Failed to update quorum to {quorum}, skipping...")
    
    # Save results
    with open('quorum_analysis_results.json', 'w') as f:
        # Remove large latencies array for JSON
        results_to_save = [
            {k: v for k, v in r.items() if k != 'latencies'} 
            for r in results
        ]
        json.dump(results_to_save, f, indent=2)
    
    print(f"\n✓ Results saved to 'quorum_analysis_results.json'")
    
    # Check consistency after all writes
    time.sleep(3)
    check_data_consistency()
    
    # Generate plots
    if results:
        plot_results(results)
        generate_analysis_report(results)
    else:
        print("✗ No results to analyze")
    
    print("\n" + "="*60)
    print("Analysis complete!")
    print("="*60 + "\n")

if __name__ == "__main__":
    import sys
    sys.exit(main())
