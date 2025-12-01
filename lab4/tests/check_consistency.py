import requests
import subprocess
import json

def get_leader_data():
    """Get all data from the leader"""
    try:
        response = requests.get("http://localhost:5001/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data['data'], data['data_count']
        return None, 0
    except Exception as e:
        print(f"Error connecting to leader: {e}")
        return None, 0

def get_follower_data(follower_container):
    """Get data from a follower by executing Python inside the container"""
    try:
        cmd = f"docker exec {follower_container} python -c \"import requests; import json; print(json.dumps(requests.get('http://localhost:5000/status').json()))\""
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data['data'], data['data_count']
        return None, 0
    except Exception as e:
        print(f"Error getting data from {follower_container}: {e}")
        return None, 0

def compare_data(leader_data, follower_data, follower_name):
    """Compare leader and follower data"""
    if leader_data is None or follower_data is None:
        return False, "Unable to fetch data"
    
    # Check if all leader keys exist in follower
    missing_in_follower = []
    value_mismatches = []
    
    for key, value in leader_data.items():
        if key not in follower_data:
            missing_in_follower.append(key)
        elif follower_data[key] != value:
            value_mismatches.append((key, value, follower_data[key]))
    
    # Check if follower has extra keys
    extra_in_follower = []
    for key in follower_data.keys():
        if key not in leader_data:
            extra_in_follower.append(key)
    
    # Report results
    consistent = (len(missing_in_follower) == 0 and 
                 len(value_mismatches) == 0 and 
                 len(extra_in_follower) == 0)
    
    issues = []
    if missing_in_follower:
        issues.append(f"Missing {len(missing_in_follower)} keys: {missing_in_follower[:5]}")
    if value_mismatches:
        issues.append(f"Value mismatches: {len(value_mismatches)}")
    if extra_in_follower:
        issues.append(f"Extra keys in follower: {extra_in_follower[:5]}")
    
    return consistent, issues

def main():
    print("="*70)
    print("DATA CONSISTENCY CHECK - Leader vs Followers")
    print("="*70)
    
    # Get leader data
    print("\n[1] Fetching data from leader...")
    leader_data, leader_count = get_leader_data()
    
    if leader_data is None:
        print("✗ Failed to get leader data. Make sure containers are running.")
        return 1
    
    print(f"✓ Leader has {leader_count} keys")
    
    # Check each follower
    print("\n[2] Checking followers...\n")
    followers = ['follower1', 'follower2', 'follower3', 'follower4', 'follower5']
    results = {}
    
    for follower in followers:
        print(f"Checking {follower}...")
        follower_data, follower_count = get_follower_data(follower)
        
        if follower_data is None:
            print(f"  ✗ Failed to connect")
            results[follower] = {'consistent': False, 'count': 0}
            continue
        
        print(f"  Data count: {follower_count}")
        
        consistent, issues = compare_data(leader_data, follower_data, follower)
        results[follower] = {
            'consistent': consistent,
            'count': follower_count,
            'issues': issues
        }
        
        if consistent:
            print(f"  ✓ CONSISTENT with leader")
        else:
            print(f"  ✗ INCONSISTENT:")
            for issue in issues:
                print(f"    - {issue}")
        print()
    
    # Summary
    print("="*70)
    print("SUMMARY")
    print("="*70)
    print(f"\nLeader has {leader_count} keys\n")
    
    consistent_count = sum(1 for r in results.values() if r['consistent'])
    
    for follower, result in results.items():
        status = "✓ CONSISTENT" if result['consistent'] else "✗ INCONSISTENT"
        print(f"{follower:12} {status:15} ({result['count']} keys)")
    
    print(f"\nResult: {consistent_count}/5 followers are consistent with leader")
    
    # Explanation
    print("\n" + "="*70)
    print("EXPLANATION")
    print("="*70)
    
    if consistent_count == 5:
        print("\n✓ All replicas are CONSISTENT with the leader!")
        print("\nWhy this happened:")
        print("1. Semi-synchronous replication ensures data propagates to all followers")
        print("2. The leader sends replication requests to ALL 5 followers (not just quorum)")
        print("3. Even if quorum < 5, remaining followers still receive the data")
        print("4. Eventually, all followers have the same data as the leader")
        print("\nThis demonstrates EVENTUAL CONSISTENCY in distributed systems:")
        print("- Writes may complete before all replicas confirm (quorum-based)")
        print("- But given enough time, all replicas converge to the same state")
        print("- This is how systems like Cassandra, MongoDB, and MySQL work")
    else:
        print(f"\n✗ Only {consistent_count}/5 replicas are consistent!")
        print("\nPossible reasons:")
        print("1. Some replication requests may have failed during heavy load")
        print("2. Network delays or container issues")
        print("3. Leader sends to all but doesn't wait for all confirmations")
        print("\nNote: Semi-synchronous replication guarantees quorum confirmations,")
        print("but doesn't guarantee all replicas receive data immediately.")
        print("Eventually consistent systems trade immediate consistency for performance.")
    
    print("\n" + "="*70)
    
    return 0 if consistent_count == 5 else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
