from flask import Flask, request, jsonify
import os
import threading
import time
import random
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)

# In-memory key-value store
data_store = {}
data_lock = threading.Lock()

# Configuration from environment variables
NODE_TYPE = os.getenv('NODE_TYPE', 'leader')  # 'leader' or 'follower'
WRITE_QUORUM = int(os.getenv('WRITE_QUORUM', '3'))  # Number of confirmations needed
MIN_DELAY = float(os.getenv('MIN_DELAY', '0.0001'))  # 0.1ms
MAX_DELAY = float(os.getenv('MAX_DELAY', '0.01'))    # 10ms
PORT = int(os.getenv('PORT', '5000'))

# Follower addresses (will be set in docker-compose)
FOLLOWERS = [
    f"http://follower{i}:5000" for i in range(1, 6)
]

@app.route('/status', methods=['GET'])
def status():
    """Return node status and current data"""
    with data_lock:
        return jsonify({
            'node_type': NODE_TYPE,
            'data_count': len(data_store),
            'data': dict(data_store)
        })

@app.route('/get/<key>', methods=['GET'])
def get_value(key):
    """Get value for a key (works on both leader and followers)"""
    with data_lock:
        if key in data_store:
            return jsonify({
                'success': True,
                'key': key,
                'value': data_store[key]
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Key not found'
            }), 404

@app.route('/set', methods=['POST'])
def set_value():
    """Set a key-value pair (leader only for client requests)"""
    if NODE_TYPE != 'leader':
        return jsonify({
            'success': False,
            'error': 'Only leader accepts write requests'
        }), 403
    
    data = request.get_json()
    if not data or 'key' not in data or 'value' not in data:
        return jsonify({
            'success': False,
            'error': 'Invalid request. Need key and value'
        }), 400
    
    key = data['key']
    value = data['value']
    
    # Write to leader's own storage
    with data_lock:
        data_store[key] = value
    
    # Replicate to followers (semi-synchronous)
    success_count = replicate_to_followers(key, value)
    
    if success_count >= WRITE_QUORUM:
        return jsonify({
            'success': True,
            'key': key,
            'value': value,
            'replicas': success_count
        })
    else:
        return jsonify({
            'success': False,
            'error': f'Not enough replicas confirmed. Got {success_count}, need {WRITE_QUORUM}'
        }), 500

@app.route('/replicate', methods=['POST'])
def replicate():
    """Receive replication request from leader (followers only)"""
    if NODE_TYPE != 'follower':
        return jsonify({
            'success': False,
            'error': 'Only followers accept replication requests'
        }), 403
    
    data = request.get_json()
    if not data or 'key' not in data or 'value' not in data:
        return jsonify({
            'success': False,
            'error': 'Invalid replication request'
        }), 400
    
    key = data['key']
    value = data['value']
    
    # Write to follower's storage
    with data_lock:
        data_store[key] = value
    
    return jsonify({
        'success': True,
        'key': key
    })

def replicate_to_followers(key, value):
    """
    Replicate data to followers with simulated network delay.
    Returns the number of successful confirmations.
    Uses concurrent requests with individual delays.
    """
    def replicate_to_one_follower(follower_url):
        try:
            # Simulate network lag
            delay = random.uniform(MIN_DELAY, MAX_DELAY)
            time.sleep(delay)
            
            # Send replication request
            response = requests.post(
                f"{follower_url}/replicate",
                json={'key': key, 'value': value},
                timeout=5
            )
            
            if response.status_code == 200:
                return True
            return False
        except Exception as e:
            print(f"Replication to {follower_url} failed: {e}")
            return False
    
    # Send replication requests concurrently
    success_count = 0
    with ThreadPoolExecutor(max_workers=len(FOLLOWERS)) as executor:
        futures = [
            executor.submit(replicate_to_one_follower, follower)
            for follower in FOLLOWERS
        ]
        
        for future in as_completed(futures):
            if future.result():
                success_count += 1
                # Early return if we have enough confirmations
                if success_count >= WRITE_QUORUM:
                    break
    
    return success_count

if __name__ == '__main__':
    print(f"Starting {NODE_TYPE} node on port {PORT}")
    print(f"Write quorum: {WRITE_QUORUM}")
    print(f"Delay range: {MIN_DELAY*1000:.2f}ms - {MAX_DELAY*1000:.2f}ms")
    
    # Run Flask with threading enabled for concurrent request handling
    app.run(host='0.0.0.0', port=PORT, threaded=True)
