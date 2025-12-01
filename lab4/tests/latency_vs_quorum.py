"""
Latency vs Quorum Analysis
Generates a plot showing how latency changes with different quorum values.
Uses smaller delays (0-100ms) for more granular analysis.
"""

import subprocess
import time
import sys
import os
import json
import matplotlib.pyplot as plt
import requests
import statistics

LEADER_URL = "http://localhost:5050"
NUM_WRITES = 200   # Number of writes per quorum value
NUM_KEYS = 50
NUM_THREADS = 10

# Test with moderate delays to see clear quorum progression
MIN_DELAY = 0.0      # 0ms
MAX_DELAY = 0.2      # 200ms - gives clear separation between quorums


def update_docker_config(quorum_value):
    """Update WRITE_QUORUM and delays in docker-compose.yml"""
    compose_file = "docker-compose.yml"
    
    with open(compose_file, 'r') as f:
        lines = f.readlines()
    
    with open(compose_file, 'w') as f:
        for i, line in enumerate(lines):
            # Check if this is the leader section
            if 'WRITE_QUORUM=' in line and any('NODE_TYPE=leader' in lines[j] for j in range(max(0, i-5), i)):
                indent = line[:line.index('WRITE_QUORUM=')]
                f.write(f"{indent}WRITE_QUORUM={quorum_value}\n")
            elif 'MIN_DELAY=' in line and any('NODE_TYPE=leader' in lines[j] for j in range(max(0, i-5), i)):
                indent = line[:line.index('MIN_DELAY=')]
                f.write(f"{indent}MIN_DELAY={MIN_DELAY}\n")
            elif 'MAX_DELAY=' in line and any('NODE_TYPE=leader' in lines[j] for j in range(max(0, i-5), i)):
                indent = line[:line.index('MAX_DELAY=')]
                f.write(f"{indent}MAX_DELAY={MAX_DELAY}\n")
            else:
                f.write(line)


def restart_docker_services():
    """Restart docker-compose services with thorough cleanup"""
    print("  Stopping services...")
    subprocess.run(["docker-compose", "down"], capture_output=True)
    time.sleep(2)  # Wait for cleanup
    
    print("  Starting services...")
    subprocess.run(["docker-compose", "up", "-d", "--build"], capture_output=True)
    
    # Wait longer for services to be ready
    print("  Waiting for services to stabilize...")
    time.sleep(8)
    
    # Check if leader is ready and verify configuration
    for i in range(30):
        try:
            response = requests.get(f"{LEADER_URL}/health", timeout=1)
            if response.status_code == 200:
                # Verify the configuration is correct
                status_response = requests.get(f"{LEADER_URL}/status", timeout=1)
                if status_response.status_code == 200:
                    config = status_response.json()
                    print(f"  ✓ Services ready - Quorum: {config.get('write_quorum', 'N/A')}")
                    return True
        except:
            pass
        time.sleep(1)
    
    print("  ✗ Services failed to start")
    return False


def run_performance_test():
    """Run performance test and return latency data"""
    print("  Running performance test...")
    
    # Clear any cached data first
    try:
        # Make a dummy request to ensure connection is fresh
        requests.get(f"{LEADER_URL}/status", timeout=2)
        time.sleep(0.5)
    except:
        pass
    
    sys.path.insert(0, os.path.dirname(__file__))
    from performance_test import run_concurrent_writes
    
    total_lats, repl_lats, success_count, failed_count, total_time = run_concurrent_writes(
        num_writes=NUM_WRITES,
        num_keys=NUM_KEYS,
        num_threads=NUM_THREADS
    )
    
    # Use REPLICATION latency (like quorum_analysis.py) not total client latency
    # This measures the actual quorum wait time, not HTTP overhead
    if repl_lats:
        sorted_repl = sorted(repl_lats)
        stats = {
            'mean': statistics.mean(repl_lats) / 1000,  # Convert to seconds
            'median': statistics.median(repl_lats) / 1000,
            'p95': sorted_repl[int(len(sorted_repl) * 0.95)] / 1000,
            'p99': sorted_repl[int(len(sorted_repl) * 0.99)] / 1000,
            'throughput': success_count / total_time if total_time > 0 else 0
        }
    else:
        stats = {'mean': 0, 'median': 0, 'p95': 0, 'p99': 0, 'throughput': 0}
    
    return stats, success_count, failed_count


def plot_latency_vs_quorum(results):
    """Generate plot matching the example format"""
    os.makedirs('results', exist_ok=True)
    
    quorums = [r['quorum'] for r in results]
    means = [r['mean'] for r in results]
    medians = [r['median'] for r in results]
    p95s = [r['p95'] for r in results]
    p99s = [r['p99'] for r in results]
    
    plt.figure(figsize=(10, 7))
    
    # Plot all four metrics
    plt.plot(quorums, means, 'o-', linewidth=2, markersize=8, label='mean', color='#1f77b4')
    plt.plot(quorums, medians, 's-', linewidth=2, markersize=8, label='median', color='#ff7f0e')
    plt.plot(quorums, p95s, '^-', linewidth=2, markersize=8, label='p95', color='#2ca02c')
    plt.plot(quorums, p99s, 'd-', linewidth=2, markersize=8, label='p99', color='#d62728')
    
    plt.xlabel('Quorum value', fontsize=12)
    plt.ylabel('Latency (s)', fontsize=12)
    plt.title(f'Quorum vs. Latency, random delay in range [0, {int(MAX_DELAY*1000)}ms]', fontsize=13)
    plt.legend(fontsize=11)
    plt.grid(True, alpha=0.3)
    plt.xticks(quorums)
    
    # Set y-axis to start from 0
    plt.ylim(bottom=0)
    
    plt.tight_layout()
    plt.savefig('results/latency_vs_quorum.png', dpi=300, bbox_inches='tight')
    print(f"\n✓ Plot saved: results/latency_vs_quorum.png")
    plt.close()


def save_results(results):
    """Save results to JSON"""
    with open('results/latency_vs_quorum.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("✓ Data saved: results/latency_vs_quorum.json")


def print_summary_table(results):
    """Print formatted results table"""
    print("\n" + "="*80)
    print("LATENCY VS QUORUM SUMMARY")
    print("="*80)
    print(f"{'Quorum':<10} {'Mean (s)':<12} {'Median (s)':<12} {'P95 (s)':<12} {'P99 (s)':<12} {'Throughput':<12}")
    print("-"*80)
    for r in results:
        print(f"{r['quorum']:<10} {r['mean']:<12.3f} {r['median']:<12.3f} {r['p95']:<12.3f} {r['p99']:<12.3f} {r['throughput']:<12.2f}")
    print("="*80)


def main():
    print("\n" + "="*80)
    print("LATENCY VS QUORUM ANALYSIS")
    print("="*80)
    print(f"Delay range: [{int(MIN_DELAY*1000)}ms, {int(MAX_DELAY*1000)}ms]")
    print(f"Writes per quorum: {NUM_WRITES}")
    print(f"Total writes: {NUM_WRITES * 5} (across 5 quorum values)")
    print("="*80 + "\n")
    
    all_results = []
    
    for quorum in range(1, 6):
        print(f"\n{'='*80}")
        print(f"Testing WRITE_QUORUM={quorum}")
        print(f"{'='*80}")
        
        # Update configuration
        update_docker_config(quorum)
        
        # Restart services
        if not restart_docker_services():
            print(f"✗ Failed to restart services for quorum={quorum}")
            continue
        
        # Run test
        try:
            stats, success_count, failed_count = run_performance_test()
            
            result = {
                'quorum': quorum,
                'mean': stats['mean'],
                'median': stats['median'],
                'p95': stats['p95'],
                'p99': stats['p99'],
                'throughput': stats['throughput'],
                'success_count': success_count,
                'failed_count': failed_count,
                'success_rate': (success_count / NUM_WRITES * 100) if NUM_WRITES > 0 else 0
            }
            
            all_results.append(result)
            
            print(f"\n✓ Quorum {quorum} completed")
            print(f"  Mean latency: {stats['mean']:.3f}s ({stats['mean']*1000:.1f}ms)")
            print(f"  Median latency: {stats['median']:.3f}s ({stats['median']*1000:.1f}ms)")
            print(f"  Throughput: {stats['throughput']:.2f} writes/sec")
            print(f"  Success rate: {result['success_rate']:.1f}%")
            
        except Exception as e:
            print(f"✗ Error testing quorum {quorum}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    if all_results:
        # Print summary table
        print_summary_table(all_results)
        
        # Generate plot
        print("\n" + "="*80)
        print("Generating visualization...")
        print("="*80)
        plot_latency_vs_quorum(all_results)
        
        # Save results
        save_results(all_results)
        
        print("\n" + "="*80)
        print("✓ ANALYSIS COMPLETE!")
        print("="*80)
        print("\nResults saved in 'results/' folder:")
        print("  - latency_vs_quorum.png (visualization)")
        print("  - latency_vs_quorum.json (raw data)")
        
        # Analysis insights
        print("\n" + "="*80)
        print("KEY INSIGHTS:")
        print("="*80)
        
        # Calculate latency increase from Q1 to Q5
        if len(all_results) == 5:
            q1_mean = all_results[0]['mean']
            q5_mean = all_results[4]['mean']
            increase = ((q5_mean - q1_mean) / q1_mean * 100) if q1_mean > 0 else 0
            
            print(f"Latency increase from Q=1 to Q=5: {increase:.1f}%")
            print(f"  Q=1 mean: {q1_mean*1000:.1f}ms")
            print(f"  Q=5 mean: {q5_mean*1000:.1f}ms")
            print(f"\nWith {int(MAX_DELAY*1000)}ms max delay, waiting for more replicas")
            print(f"increases latency as expected in semi-synchronous replication.")
        
    else:
        print("\n✗ No results collected")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
