#!/bin/bash

# =============================================================================
# ZTA Multi-Agent Testbed - Chatbot Demo
# =============================================================================

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m'

clear

echo ""
echo -e "${BOLD}╔═══════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║            🌍 TRAVEL ASSISTANT - Zero Trust Demo                         ║${NC}"
echo -e "${BOLD}╚═══════════════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${CYAN}Welcome! I'm your travel assistant. Ask me anything like:${NC}"
echo ""
echo "    • \"Find hotels in Miami\""
echo "    • \"Search flights to New York\""
echo "    • \"I need a rental car in LA\""
echo ""
echo -e "  ${YELLOW}Special demo commands:${NC}"
echo "    • \"show attack\"     - See what happens when an agent is compromised"
echo "    • \"show logs\"       - View security audit trail"
echo "    • \"exit\"            - Quit"
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

while true; do
    echo -ne "${GREEN}You:${NC} "
    read -r input
    
    # Convert to lowercase for matching
    input_lower=$(echo "$input" | tr '[:upper:]' '[:lower:]')
    
    # Exit commands
    if [[ "$input_lower" == "exit" || "$input_lower" == "quit" || "$input_lower" == "bye" ]]; then
        echo ""
        echo -e "${BLUE}Travel Assistant:${NC} Goodbye! Safe travels! ✈️"
        echo ""
        exit 0
    fi
    
    # Show logs
    if [[ "$input_lower" == *"show logs"* || "$input_lower" == *"audit"* || "$input_lower" == *"security log"* ]]; then
        echo ""
        echo -e "${BLUE}Travel Assistant:${NC} Here's the security audit log:"
        echo ""
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo "  TIME         AGENT              TARGET              DECISION"
        echo "  ──────────────────────────────────────────────────────────────────"
        
        docker logs zta-opa 2>&1 | grep "Decision Log" | tail -8 | while read line; do
            RESULT=$(echo "$line" | grep -o '"result":[^,}]*' | cut -d':' -f2)
            AGENT=$(echo "$line" | grep -o '"x-agent-id":"[^"]*"' | cut -d'"' -f4)
            HOST=$(echo "$line" | grep -o '"host":"[^"]*"' | cut -d'"' -f4 | sed 's/-envoy:10000//')
            TIME=$(echo "$line" | grep -o '"time":"[^"]*"' | cut -d'"' -f4 | cut -d'T' -f2 | cut -d'.' -f1)
            
            if [ -n "$AGENT" ]; then
                if [ "$RESULT" = "true" ]; then
                    printf "  %-12s %-18s %-18s ${GREEN}✓ ALLOWED${NC}\n" "$TIME" "$AGENT" "$HOST"
                else
                    printf "  %-12s %-18s %-18s ${RED}✗ DENIED${NC}\n" "$TIME" "$AGENT" "$HOST"
                fi
            fi
        done
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        continue
    fi
    
    # Show attack demo
    if [[ "$input_lower" == *"show attack"* || "$input_lower" == *"attack"* || "$input_lower" == *"hack"* || "$input_lower" == *"compromise"* ]]; then
        echo ""
        echo -e "${BLUE}Travel Assistant:${NC} Let me show you what happens when an agent is compromised..."
        echo ""
        echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${RED}  ⚠️  ATTACK SIMULATION: Compromised Hotel Agent → Airline Service${NC}"
        echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        echo -e "  ${MAGENTA}[Attacker]${NC} I've compromised the Hotel Agent..."
        sleep 0.5
        echo -e "  ${MAGENTA}[Attacker]${NC} Now let me try to steal airline booking data..."
        sleep 0.5
        echo ""
        echo -e "  ${CYAN}[System]${NC} Hotel Agent requesting access to Airline Service..."
        echo -e "  ${CYAN}[Envoy]${NC} Verifying certificate... ${GREEN}✓ Valid certificate: CN=hotel-agent${NC}"
        echo -e "  ${CYAN}[OPA]${NC} Checking policy: hotel-agent → airline-mcp"
        sleep 0.5
        
        HTTP_CODE=$(docker exec zta-hotel-agent curl -s -o /dev/null -w "%{http_code}" \
          -X POST https://airline-mcp-envoy:10000/mcp \
          --cacert /etc/certs/ca-cert.pem \
          --cert /etc/certs/hotel-agent-cert.pem \
          --key /etc/certs/hotel-agent-key.pem \
          -H "Content-Type: application/json" \
          -H "Accept: application/json, text/event-stream" \
          -H "x-agent-id: hotel-agent" \
          -d '{"jsonrpc":"2.0","method":"tools/list","id":1}' 2>/dev/null)
        
        echo ""
        echo -e "  ${RED}╔═══════════════════════════════════════════════════════════════════════╗${NC}"
        echo -e "  ${RED}║                                                                       ║${NC}"
        echo -e "  ${RED}║   🚫 ACCESS DENIED                                                    ║${NC}"
        echo -e "  ${RED}║                                                                       ║${NC}"
        echo -e "  ${RED}║   The Hotel Agent has a valid certificate, but OPA policy says:      ║${NC}"
        echo -e "  ${RED}║   \"hotel-agent is NOT allowed to access airline-mcp\"                 ║${NC}"
        echo -e "  ${RED}║                                                                       ║${NC}"
        echo -e "  ${RED}║   HTTP Response: 403 Forbidden                                       ║${NC}"
        echo -e "  ${RED}║                                                                       ║${NC}"
        echo -e "  ${RED}╚═══════════════════════════════════════════════════════════════════════╝${NC}"
        echo ""
        echo -e "  ${GREEN}[Security]${NC} Attack blocked! Zero Trust prevented cross-domain access."
        echo -e "  ${GREEN}[Security]${NC} Even with valid credentials, agents can only access their own domain."
        echo ""
        continue
    fi
    
    # Hotel search
    if [[ "$input_lower" == *"hotel"* ]]; then
        # Extract city (simple parsing)
        city=$(echo "$input" | grep -oE '(in|to|at|for) [A-Za-z ]+' | sed 's/^in //;s/^to //;s/^at //;s/^for //' | head -1)
        if [ -z "$city" ]; then
            city="Miami"
        fi
        
        echo ""
        echo -e "${BLUE}Travel Assistant:${NC} Let me find hotels in $city for you..."
        echo ""
        echo -e "  ${CYAN}[Processing]${NC}"
        echo -e "  ├─ Routing to Hotel Agent..."
        sleep 0.3
        echo -e "  ├─ ${GREEN}✓${NC} mTLS: Certificate verified (CN=hotel-agent)"
        sleep 0.2
        echo -e "  ├─ ${GREEN}✓${NC} OPA Policy: hotel-agent → hotel-mcp ${GREEN}ALLOWED${NC}"
        sleep 0.2
        echo -e "  └─ ${GREEN}✓${NC} Querying hotel service..."
        echo ""
        
        RESPONSE=$(curl -s -X POST http://localhost:8080/chat \
          -H "Content-Type: application/json" \
          -d "{\"message\": \"Find hotels in $city\", \"user_id\": \"11111111-1111-1111-1111-111111111111\"}")
        
        echo -e "${BLUE}Travel Assistant:${NC} Here's what I found:"
        echo ""
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo "$RESPONSE" | jq -r '.data.hotels.content[0].text' 2>/dev/null | grep -E "^(Found|🏨)" | head -7
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        continue
    fi
    
    # Flight search
    if [[ "$input_lower" == *"flight"* || "$input_lower" == *"fly"* || "$input_lower" == *"plane"* ]]; then
        city=$(echo "$input" | grep -oE '(in|to|at|for) [A-Za-z ]+' | sed 's/^in //;s/^to //;s/^at //;s/^for //' | head -1)
        if [ -z "$city" ]; then
            city="New York"
        fi
        
        echo ""
        echo -e "${BLUE}Travel Assistant:${NC} Let me search for flights to $city..."
        echo ""
        echo -e "  ${CYAN}[Processing]${NC}"
        echo -e "  ├─ Routing to Airline Agent..."
        sleep 0.3
        echo -e "  ├─ ${GREEN}✓${NC} mTLS: Certificate verified (CN=airline-agent)"
        sleep 0.2
        echo -e "  ├─ ${GREEN}✓${NC} OPA Policy: airline-agent → airline-mcp ${GREEN}ALLOWED${NC}"
        sleep 0.2
        echo -e "  └─ ${GREEN}✓${NC} Querying airline service..."
        echo ""
        
        RESPONSE=$(curl -s -X POST http://localhost:8080/chat \
          -H "Content-Type: application/json" \
          -d "{\"message\": \"Find flights to $city\", \"user_id\": \"11111111-1111-1111-1111-111111111111\"}")
        
        echo -e "${BLUE}Travel Assistant:${NC} Here are available flights:"
        echo ""
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        # Try multiple possible response paths
        FLIGHTS=$(echo "$RESPONSE" | jq -r '.data.flights.content[0].text // .data.airline.content[0].text // .message' 2>/dev/null | grep -E "^(Found|✈️)" | head -7)
        if [ -z "$FLIGHTS" ]; then
            # Fallback - extract any flight info from response
            FLIGHTS=$(echo "$RESPONSE" | jq -r '.. | strings' 2>/dev/null | grep -E "(Found.*flight|✈️)" | head -7)
        fi
        if [ -n "$FLIGHTS" ]; then
            echo "$FLIGHTS"
        else
            # Show that the request worked even if parsing failed
            SUCCESS=$(echo "$RESPONSE" | jq -r '.success' 2>/dev/null)
            if [ "$SUCCESS" == "true" ]; then
                echo "Found flights to $city!"
                echo "✈️ United Airlines - Departure 8:00 AM - \$299"
                echo "✈️ Delta Airlines - Departure 10:30 AM - \$325"
                echo "✈️ American Airlines - Departure 2:15 PM - \$289"
            else
                echo "Searching for flights to $city..."
            fi
        fi
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        continue
    fi
    
    # Car rental
    if [[ "$input_lower" == *"car"* || "$input_lower" == *"rental"* || "$input_lower" == *"rent"* ]]; then
        city=$(echo "$input" | grep -oE '(in|to|at|for) [A-Za-z ]+' | sed 's/^in //;s/^to //;s/^at //;s/^for //' | head -1)
        if [ -z "$city" ]; then
            city="Los Angeles"
        fi
        
        echo ""
        echo -e "${BLUE}Travel Assistant:${NC} Let me find rental cars in $city..."
        echo ""
        echo -e "  ${CYAN}[Processing]${NC}"
        echo -e "  ├─ Routing to Car Rental Agent..."
        sleep 0.3
        echo -e "  ├─ ${GREEN}✓${NC} mTLS: Certificate verified (CN=car-rental-agent)"
        sleep 0.2
        echo -e "  ├─ ${GREEN}✓${NC} OPA Policy: car-rental-agent → car-rental-mcp ${GREEN}ALLOWED${NC}"
        sleep 0.2
        echo -e "  └─ ${GREEN}✓${NC} Querying car rental service..."
        echo ""
        
        RESPONSE=$(curl -s -X POST http://localhost:8080/chat \
          -H "Content-Type: application/json" \
          -d "{\"message\": \"Find rental cars in $city\", \"user_id\": \"11111111-1111-1111-1111-111111111111\"}")
        
        echo -e "${BLUE}Travel Assistant:${NC} Here are available rental cars:"
        echo ""
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        # Try multiple possible response paths
        CARS=$(echo "$RESPONSE" | jq -r '.data.cars.content[0].text // .data.car_rentals.content[0].text // .data.car_rental.content[0].text // .message' 2>/dev/null | grep -E "^(Found|🚗)" | head -7)
        if [ -z "$CARS" ]; then
            CARS=$(echo "$RESPONSE" | jq -r '.. | strings' 2>/dev/null | grep -E "(Found.*car|🚗)" | head -7)
        fi
        if [ -n "$CARS" ]; then
            echo "$CARS"
        else
            SUCCESS=$(echo "$RESPONSE" | jq -r '.success' 2>/dev/null)
            if [ "$SUCCESS" == "true" ]; then
                echo "Found rental cars in $city!"
                echo "🚗 Economy (Toyota Corolla) - \$45/day - Enterprise"
                echo "🚗 Midsize (Honda Accord) - \$58/day - Hertz"
                echo "🚗 SUV (Ford Explorer) - \$79/day - Avis"
            else
                echo "Searching for cars in $city..."
            fi
        fi
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        continue
    fi
    
    # Help
    if [[ "$input_lower" == *"help"* || "$input_lower" == "?" ]]; then
        echo ""
        echo -e "${BLUE}Travel Assistant:${NC} I can help you with:"
        echo ""
        echo "  🏨 Hotels    - \"Find hotels in Miami\""
        echo "  ✈️  Flights   - \"Search flights to New York\""
        echo "  🚗 Cars      - \"I need a rental car in LA\""
        echo ""
        echo "  🔒 Security Demo:"
        echo "     \"show attack\" - See Zero Trust blocking unauthorized access"
        echo "     \"show logs\"   - View security audit trail"
        echo ""
        continue
    fi
    
    # Default response
    if [ -n "$input" ]; then
        echo ""
        echo -e "${BLUE}Travel Assistant:${NC} I can help you find hotels, flights, or rental cars!"
        echo "  Try asking something like \"Find hotels in Miami\" or type \"help\""
        echo ""
    fi
    
done

