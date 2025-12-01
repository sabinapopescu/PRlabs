"""
Quorum Analysis Script
Tests performance with different write quorum values (1-5)
Generates plots and analysis report using average replication latency.
"""

import subprocess
import time
import sys
import os
import json
import matplotlib.pyplot as plt
import requests

LEADER_URL = "http://localhost:5050"
NUM_WRITES = 100   # Start with fewer writes for large delay testing (0-1000ms)
NUM_KEYS = 20      # Fewer keys for initial testing
NUM_THREADS = 5    # Fewer threads to handle large delays better


def update_quorum_in_compose(quorum_value):
    """Update WRITE_QUORUM in docker-compose.yml"""
    compose_file = "docker-compose.yml"
    
    with open(compose_file, 'r') as f:
        lines = f.readlines()
    
    with open(compose_file, 'w') as f:
        for line in lines:
            if 'WRITE_QUORUM=' in line and 'NODE_TYPE=leader' in ''.join(lines[max(0, lines.index(line)-5):lines.index(line)]):
                # Replace the value only for leader
                indent = line[:line.index('WRITE_QUORUM=')]
                f.write(f"{indent}WRITE_QUORUM={quorum_value}\n")
            else:
                f.write(line)


def restart_docker_services():
    """Restart docker-compose services"""
    print("  Restarting services...")
    subprocess.run(["docker-compose", "down"], capture_output=True)
    subprocess.run(["docker-compose", "up", "-d", "--build"], capture_output=True)
    
    # Wait for services to be ready
    print("  Waiting for services...")
    time.sleep(5)
    
    # Check if leader is ready
    for i in range(30):
        try:
            response = requests.get(f"{LEADER_URL}/health", timeout=1)
            if response.status_code == 200:
                print("  ✓ Services are ready")
                return True
        except:
            pass
        time.sleep(1)
    
    print("  ✗ Services failed to start")
    return False


def run_performance_test():
    """Run performance test and return results"""
    print("  Running performance test...")
    
    # Import after ensuring the path is correct
    sys.path.insert(0, os.path.dirname(__file__))
    from performance_test import run_concurrent_writes, analyze_latencies
    
    total_lats, repl_lats, success_count, failed_count, total_time = run_concurrent_writes(
        num_writes=NUM_WRITES,
        num_keys=NUM_KEYS,
        num_threads=NUM_THREADS
    )
    
    stats = analyze_latencies(total_lats, repl_lats)
    
    return {
        'success_count': success_count,
        'failed_count': failed_count,
        'total_time': total_time,
        'throughput': success_count / total_time if total_time > 0 else 0,
        'stats': stats
    }


def check_consistency():
    """Check data consistency across all nodes"""
    print("  Checking data consistency...")
    time.sleep(2)  # Wait for replication
    
    sys.path.insert(0, os.path.dirname(__file__))
    from check_consistency import check_data_consistency
    
    return check_data_consistency(verbose=False)


def plot_quorum_analysis(all_results):
    """Generate plot for quorum analysis - single chart showing latency vs quorum"""
    os.makedirs('results', exist_ok=True)
    
    quorums = [r['quorum'] for r in all_results]
    
    # Use replication latency instead of total latency
    avg_repl_latencies = [r.get('avg_repl_latency', r['avg_latency']) for r in all_results]
    median_repl_latencies = [r.get('median_repl_latency', r['median_latency']) for r in all_results]
    p95_repl_latencies = [r.get('p95_repl_latency', r['p95_latency']) for r in all_results]
    
    # Create a single large plot
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Plot Average Replication Latency vs Quorum with three lines
    ax.plot(quorums, avg_repl_latencies, 'o-', linewidth=3, markersize=10, label='Mean', color='blue')
    ax.plot(quorums, median_repl_latencies, 's-', linewidth=3, markersize=10, label='Median', color='green')
    ax.plot(quorums, p95_repl_latencies, '^-', linewidth=3, markersize=10, label='P95', color='red')
    
    ax.set_xlabel('Write Quorum', fontsize=14, fontweight='bold')
    ax.set_ylabel('Avg Replication Latency (ms)', fontsize=14, fontweight='bold')
    ax.set_title('Write Quorum vs Average Replication Latency', fontsize=16, fontweight='bold', pad=20)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.legend(fontsize=12, loc='upper left')
    ax.set_xticks(quorums)
    
    # Increase tick label size
    ax.tick_params(axis='both', which='major', labelsize=12)
    
    plt.tight_layout()
    plt.savefig('results/quorum_analysis.png', dpi=300, bbox_inches='tight')
    print("\n✓ Plot saved: results/quorum_analysis.png")
    plt.close()


def save_analysis_report(all_results):
    """Save detailed analysis report"""
    report_file = 'results/quorum_analysis_report.txt'
    
    with open(report_file, 'w') as f:
        f.write("="*80 + "\n")
        f.write("QUORUM ANALYSIS REPORT\n")
        f.write("Key-Value Store with Single-Leader Replication\n")
        f.write("="*80 + "\n\n")
        
        f.write(f"Test Configuration:\n")
        f.write(f"  Total Writes: {NUM_WRITES}\n")
        f.write(f"  Number of Keys: {NUM_KEYS}\n")
        f.write(f"  Concurrent Threads: {NUM_THREADS}\n")
        f.write(f"  Quorum Values Tested: 1-5\n\n")
        
        f.write("="*80 + "\n")
        f.write("DETAILED RESULTS\n")
        f.write("="*80 + "\n\n")
        
        for r in all_results:
            avg_repl = r.get('avg_repl_latency', r['avg_latency'])
            f.write(f"Write Quorum: {r['quorum']}\n")
            f.write(f"  Success Rate: {r['success_rate']:.1f}%\n")
            f.write(f"  Throughput: {r['throughput']:.2f} writes/sec\n")
            f.write(f"  Average Replication Latency: {avg_repl:.2f} ms\n")
            f.write(f"  Consistency: {r['consistency_pct']:.1f}%\n\n")
        
        f.write("="*80 + "\n")
        f.write("ANALYSIS & OBSERVATIONS\n")
        f.write("="*80 + "\n\n")
        
        f.write("1. Replication Latency vs Write Quorum:\n")
        f.write("   - Measures average time to replicate to followers\n")
        f.write("   - Should remain relatively stable across quorum values\n")
        f.write("   - Variations due to network simulation and concurrent load\n\n")
        
        f.write("2. Throughput vs Write Quorum:\n")
        f.write("   - May vary due to quorum acknowledgment requirements\n")
        f.write("   - Trade-off between consistency guarantees and performance\n\n")
        
        f.write("3. Data Consistency:\n")
        f.write("   - Semi-synchronous replication provides eventual consistency\n")
        f.write("   - Higher quorum = stronger consistency guarantees\n\n")
    
    print(f"✓ Report saved: {report_file}")


def main():
    print("\n" + "="*80)
    print("QUORUM ANALYSIS - Testing Write Quorum Values 1-5")
    print("="*80)
    print(f"\nThis will run {NUM_WRITES} writes for each quorum value (1-5)")
    
    all_results = []
    
    for quorum in range(1, 6):
        print(f"\n{'='*80}")
        print(f"Testing WRITE_QUORUM={quorum}")
        print(f"{'='*80}")
        
        # Update docker-compose.yml
        update_quorum_in_compose(quorum)
        
        # Restart services
        if not restart_docker_services():
            print(f"✗ Failed to restart services for quorum={quorum}")
            continue
        
        # Run performance test
        try:
            results = run_performance_test()
            
            # Check consistency
            consistency_results = check_consistency()
            
            # Calculate average consistency
            avg_consistency = sum(r['consistency_pct'] for r in consistency_results) / len(consistency_results) if consistency_results else 0
            
            # Store results
            result_entry = {
                'quorum': quorum,
                'avg_latency': results['stats'].get('total_mean', 0),
                'median_latency': results['stats'].get('total_median', 0),
                'p95_latency': results['stats'].get('total_p95', 0),
                'throughput': results['throughput'],
                'success_rate': (results['success_count'] / NUM_WRITES * 100),
                'consistency_pct': avg_consistency
            }
            
            # Add replication latency if available
            if 'repl_mean' in results['stats']:
                result_entry['avg_repl_latency'] = results['stats']['repl_mean']
                result_entry['median_repl_latency'] = results['stats']['repl_median']
                result_entry['p95_repl_latency'] = results['stats']['repl_p95']
            
            all_results.append(result_entry)
            
            print(f"\n✓ Quorum {quorum} completed")
            avg_lat = result_entry.get('avg_repl_latency', result_entry['avg_latency'])
            print(f"  Avg Replication Latency: {avg_lat:.2f}ms")
            print(f"  Throughput: {results['throughput']:.2f} writes/sec")
            print(f"  Consistency: {avg_consistency:.1f}%")
            
        except Exception as e:
            print(f"✗ Error testing quorum {quorum}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    if all_results:
        print(f"\n{'='*80}")
        print("Generating analysis...")
        print(f"{'='*80}")
        
        # Generate plots
        plot_quorum_analysis(all_results)
        
        # Save report
        save_analysis_report(all_results)
        
        # Save JSON
        with open('results/quorum_analysis.json', 'w') as f:
            json.dump(all_results, f, indent=2)
        print("✓ Data saved: results/quorum_analysis.json")
        
        print(f"\n{'='*80}")
        print("✓ QUORUM ANALYSIS COMPLETE!")
        print(f"{'='*80}")
        print("\nResults saved in 'results/' folder:")
        print("  - quorum_analysis.png (visualization)")
        print("  - quorum_analysis_report.txt (detailed report)")
        print("  - quorum_analysis.json (raw data)")
    else:
        print("\n✗ No results collected")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
    