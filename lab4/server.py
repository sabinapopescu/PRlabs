"""
Key-Value Store Server with Single-Leader Replication
Can run as either Leader or Follower based on NODE_TYPE environment variable.
"""

from flask import Flask, request, jsonify
import os
import threading
import time
import random
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# In-memory key-value store
data_store = {}
data_lock = threading.Lock()

# Configuration from environment variables
NODE_TYPE = os.getenv('NODE_TYPE', 'leader')  # 'leader' or 'follower'
WRITE_QUORUM = int(os.getenv('WRITE_QUORUM', '3'))  # Number of confirmations needed
MIN_DELAY = float(os.getenv('MIN_DELAY', '0.0'))  # 0ms
MAX_DELAY = float(os.getenv('MAX_DELAY', '1.0'))    # 1000ms (1 second)
PORT = int(os.getenv('PORT', '5000'))

# Follower addresses
FOLLOWERS = [f"http://follower{i}:5000" for i in range(1, 6)]

logger.info(f"Starting {NODE_TYPE} node on port {PORT}")
logger.info(f"Write quorum: {WRITE_QUORUM}")
logger.info(f"Delay range: {MIN_DELAY*1000:.0f}ms - {MAX_DELAY*1000:.0f}ms")


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'node_type': NODE_TYPE,
        'port': PORT
    }), 200


@app.route('/status', methods=['GET'])
def status():
    """Return node status and current data"""
    with data_lock:
        return jsonify({
            'node_type': NODE_TYPE,
            'data_count': len(data_store),
            'data': dict(data_store),
            'write_quorum': WRITE_QUORUM if NODE_TYPE == 'leader' else None
        }), 200


@app.route('/get/<key>', methods=['GET'])
def get_value(key):
    """Get value for a key (works on both leader and followers)"""
    with data_lock:
        if key in data_store:
            logger.debug(f"GET {key} = {data_store[key]}")
            return jsonify({
                'success': True,
                'key': key,
                'value': data_store[key],
                'node_type': NODE_TYPE
            }), 200
        else:
            logger.debug(f"GET {key} - not found")
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
    
    start_time = time.time()
    
    # Write to leader's own storage
    with data_lock:
        data_store[key] = value
    
    logger.info(f"SET {key} = {value}")
    
    # Replicate to followers (semi-synchronous)
    success_count, replication_latencies = replicate_to_followers(key, value)
    
    total_latency = (time.time() - start_time) * 1000  # Convert to ms
    
    # Calculate average replication latency (only for successful replications)
    avg_replication_latency = sum(replication_latencies) / len(replication_latencies) if replication_latencies else 0
    
    if success_count >= WRITE_QUORUM:
        logger.info(f"Write successful: {success_count}/{len(FOLLOWERS)} replicas confirmed, total latency: {total_latency:.2f}ms, avg replication: {avg_replication_latency:.2f}ms")
        return jsonify({
            'success': True,
            'key': key,
            'value': value,
            'replicas': success_count,
            'required': WRITE_QUORUM,
            'latency_ms': total_latency,
            'avg_replication_latency_ms': avg_replication_latency,
            'replication_latencies': replication_latencies
        }), 200
    else:
        logger.warning(f"Write quorum not met: {success_count}/{WRITE_QUORUM}")
        return jsonify({
            'success': False,
            'error': f'Not enough replicas confirmed. Got {success_count}, need {WRITE_QUORUM}',
            'replicas': success_count,
            'required': WRITE_QUORUM
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
    
    logger.debug(f"REPLICATE {key} = {value}")
    
    return jsonify({
        'success': True,
        'key': key
    }), 200


def replicate_to_followers(key, value):
    """
    Replicate data to followers with simulated network delay.
    Returns as soon as WRITE_QUORUM confirmations are received.
    This is TRUE semi-synchronous replication.
    """
    def replicate_to_one_follower(follower_url):
        start = time.time()
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
            
            latency = (time.time() - start) * 1000  # ms
            
            if response.status_code == 200:
                logger.debug(f"Replicated to {follower_url} in {latency:.2f}ms")
                return (True, latency)
            else:
                logger.warning(f"Replication to {follower_url} failed with status {response.status_code}")
                return (False, latency)
        except Exception as e:
            latency = (time.time() - start) * 1000
            logger.error(f"Replication to {follower_url} failed: {e}")
            return (False, latency)
    
    # Send replication requests concurrently
    success_count = 0
    all_latencies = []
    
    with ThreadPoolExecutor(max_workers=len(FOLLOWERS)) as executor:
        futures = {
            executor.submit(replicate_to_one_follower, follower): follower
            for follower in FOLLOWERS
        }
        
        # Return AS SOON AS we have enough successful replications
        for future in as_completed(futures):
            success, latency = future.result()
            if success:
                success_count += 1
                all_latencies.append(latency)
                
                # CRITICAL: Return immediately when quorum is reached!
                if success_count >= WRITE_QUORUM:
                    logger.debug(f"Quorum {WRITE_QUORUM} reached, returning early")
                    return success_count, all_latencies
        
        # If we get here, quorum was not reached
        return success_count, all_latencies


@app.route('/get_all', methods=['GET'])
def get_all():
    """Get all key-value pairs from the store"""
    with data_lock:
        return jsonify({
            'success': True,
            'data': dict(data_store),
            'count': len(data_store),
            'node_type': NODE_TYPE
        }), 200


if __name__ == '__main__':
    logger.info(f"Server ready: {NODE_TYPE.upper()} node")
    # Run Flask with threading enabled for concurrent request handling
    app.run(host='0.0.0.0', port=PORT, threaded=True, debug=False)