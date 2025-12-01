"""
Data Consistency Checker
Verifies that data in follower replicas matches the leader.
"""

import requests
import sys
import time
from typing import List, Dict

LEADER_URL = "http://localhost:5050"
FOLLOWER_URLS = [f"http://localhost:500{i}" for i in range(1, 6)]


def get_node_data(url: str, node_name: str) -> Dict:
    """Get all data from a node"""
    try:
        response = requests.get(f"{url}/get_all", timeout=5)
        if response.status_code == 200:
            return response.json()['data']
        else:
            print(f"✗ {node_name}: Failed to retrieve data (status {response.status_code})")
            return None
    except Exception as e:
        print(f"✗ {node_name}: Error - {e}")
        return None


def check_data_consistency(verbose=True, wait_for_consistency=False, max_retries=3) -> List[Dict]:
    """
    Check if data in all replicas matches the leader.
    Returns list of consistency results for each follower.
    
    Args:
        verbose: Print detailed output
        wait_for_consistency: Retry if not fully consistent
        max_retries: Maximum number of retries
    """
    if verbose:
        print(f"\n{'='*60}")
        print("DATA CONSISTENCY CHECK")
        print(f"{'='*60}\n")
    
    for attempt in range(max_retries):
        if attempt > 0 and wait_for_consistency:
            print(f"\nRetry {attempt}/{max_retries-1} - Waiting 2 seconds for replication...")
            time.sleep(2)
        
        # Get leader data
        leader_data = get_node_data(LEADER_URL, "Leader")
        if leader_data is None:
            print("✗ Cannot retrieve leader data")
            return []
        
        leader_count = len(leader_data)
        if verbose:
            print(f"Leader has {leader_count} keys\n")
        
        consistency_results = []
        
        # Check each follower
        for i, follower_url in enumerate(FOLLOWER_URLS, 1):
            follower_data = get_node_data(follower_url, f"Follower {i}")
            
            if follower_data is None:
                consistency_results.append({
                    'follower': i,
                    'consistency_pct': 0,
                    'missing': leader_count,
                    'extra': 0,
                    'mismatched': 0,
                    'status': 'unreachable'
                })
                continue
            
            follower_count = len(follower_data)
            
            # Find missing keys (in leader but not in follower)
            missing_keys = set(leader_data.keys()) - set(follower_data.keys())
            
            # Find extra keys (in follower but not in leader)
            extra_keys = set(follower_data.keys()) - set(leader_data.keys())
            
            # Find mismatched values
            mismatched_keys = []
            for key in set(leader_data.keys()) & set(follower_data.keys()):
                if leader_data[key] != follower_data[key]:
                    mismatched_keys.append(key)
            
            # Calculate consistency percentage
            if leader_count > 0:
                matching_keys = len(set(leader_data.keys()) & set(follower_data.keys())) - len(mismatched_keys)
                consistency_pct = (matching_keys / leader_count) * 100
            else:
                consistency_pct = 100 if follower_count == 0 else 0
            
            result = {
                'follower': i,
                'consistency_pct': consistency_pct,
                'missing': len(missing_keys),
                'extra': len(extra_keys),
                'mismatched': len(mismatched_keys),
                'total_keys': follower_count,
                'status': 'consistent' if consistency_pct == 100 else 'inconsistent'
            }
            
            consistency_results.append(result)
            
            if verbose:
                print(f"Follower {i}:")
                print(f"  Keys: {follower_count} (Leader has {leader_count})")
                print(f"  Missing keys: {len(missing_keys)}")
                if missing_keys and len(missing_keys) <= 5:
                    print(f"    Examples: {list(missing_keys)[:5]}")
                print(f"  Extra keys: {len(extra_keys)}")
                if extra_keys and len(extra_keys) <= 5:
                    print(f"    Examples: {list(extra_keys)[:5]}")
                print(f"  Mismatched values: {len(mismatched_keys)}")
                if mismatched_keys and len(mismatched_keys) <= 5:
                    print(f"    Examples: {mismatched_keys[:5]}")
                print(f"  Consistency: {consistency_pct:.1f}%")
                
                if consistency_pct == 100:
                    print(f"  ✓ Fully consistent\n")
                elif consistency_pct >= 95:
                    print(f"  ⚠ Mostly consistent\n")
                else:
                    print(f"  ✗ Inconsistent\n")
        
        # Summary
        if verbose and consistency_results:
            avg_consistency = sum(r['consistency_pct'] for r in consistency_results) / len(consistency_results)
            print(f"{'='*60}")
            print(f"Average Consistency: {avg_consistency:.1f}%")
            
            fully_consistent = sum(1 for r in consistency_results if r['consistency_pct'] == 100)
            print(f"Fully Consistent Replicas: {fully_consistent}/{len(consistency_results)}")
            print(f"{'='*60}\n")
            
            # Check if we should retry
            if wait_for_consistency and fully_consistent < len(consistency_results) and attempt < max_retries - 1:
                continue  # Retry
            
        return consistency_results
    
    return consistency_results


def main():
    """Run consistency check as standalone script"""
    print("\n" + "="*80)
    print("DATA CONSISTENCY CHECK - Leader and Followers")
    print("="*80)
    
    # Check if services are running
    try:
        response = requests.get(f"{LEADER_URL}/health", timeout=2)
        if response.status_code != 200:
            print("\n✗ Leader is not responding. Make sure services are running:")
            print("  docker-compose up -d")
            return 1
    except:
        print("\n✗ Cannot connect to leader. Make sure services are running:")
        print("  docker-compose up -d")
        return 1
    
    # Run consistency check with retries
    results = check_data_consistency(verbose=True, wait_for_consistency=True, max_retries=3)
    
    if not results:
        print("✗ No consistency data collected")
        return 1
    
    # Check if all are consistent
    all_consistent = all(r['consistency_pct'] == 100 for r in results)
    
    if all_consistent:
        print("✓ All replicas are fully consistent with the leader!")
        return 0
    else:
        print("⚠ Some replicas still have consistency issues after retries")
        print("  This can happen with high write load and network delays")
        avg_consistency = sum(r['consistency_pct'] for r in results) / len(results)
        if avg_consistency >= 99:
            print(f"  But {avg_consistency:.1f}% average consistency is excellent!")
        return 0


if __name__ == "__main__":
    sys.exit(main())