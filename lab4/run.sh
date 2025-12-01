#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Lab 4 - Key-Value Store Setup${NC}"
echo -e "${BLUE}========================================${NC}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}✗ Docker is not running. Please start Docker first.${NC}"
    exit 1
fi

echo -e "\n${GREEN}✓ Docker is running${NC}"

# Build and start containers
echo -e "\n${BLUE}Building and starting containers...${NC}"
docker-compose down
docker-compose up --build -d

# Wait for services to be ready
echo -e "\n${BLUE}Waiting for services to be ready...${NC}"
sleep 5

# Check if leader is responding
echo -e "${BLUE}Checking leader...${NC}"
for i in {1..10}; do
    if curl -s http://localhost:5050/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Leader is ready!${NC}"
        break
    fi
    echo "  Waiting... ($i/10)"
    sleep 1
    
    if [ $i -eq 10 ]; then
        echo -e "${RED}✗ Leader failed to start${NC}"
        exit 1
    fi
done

# Check followers
echo -e "\n${BLUE}Checking followers...${NC}"
for port in 5001 5002 5003 5004 5005; do
    if curl -s http://localhost:$port/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Follower on port $port is ready${NC}"
    else
        echo -e "${YELLOW}⚠ Follower on port $port not responding${NC}"
    fi
done

# Show status
echo -e "\n${BLUE}Container Status:${NC}"
docker-compose ps

# Show leader info
echo -e "\n${BLUE}Leader Status:${NC}"
curl -s http://localhost:5050/status | python3 -m json.tool 2>/dev/null || echo "Leader not responding"

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}System is ready!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "\nYou can now:"
echo -e "  • Run integration tests:  ${BLUE}python3 tests/integration_test.py${NC}"
echo -e "  • Run performance test:   ${BLUE}python3 tests/performance_test.py${NC}"
echo -e "  • Run quorum analysis:    ${BLUE}python3 tests/quorum_analysis.py${NC}"
echo -e "  • Latency vs quorum plot: ${BLUE}python3 tests/latency_vs_quorum.py${NC}"
echo -e "  • Check data consistency: ${BLUE}python3 tests/check_consistency.py${NC}"
echo -e "  • View logs:              ${BLUE}docker-compose logs -f${NC}"
echo -e "  • Stop system:            ${BLUE}docker-compose down${NC}"
echo ""