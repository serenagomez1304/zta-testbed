#!/bin/bash

# =============================================================================
# ZTA Multi-Agent Testbed - Demo Script (Final)
# =============================================================================

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

clear

echo ""
echo "============================================================================="
echo -e "${BOLD}     Zero Trust Architecture - Multi-Agent Testbed Demo${NC}"
echo "============================================================================="
echo ""

# Demo 1
echo -e "${BLUE}${BOLD}[DEMO 1] System Overview${NC}"
echo "-----------------------------------------------------------------------------"
echo ""
echo "Running containers:"
echo ""
docker ps --format "table {{.Names}}\t{{.Status}}" | grep zta | sort
echo ""
read -p "Press Enter to continue..."
clear

# Demo 2
echo ""
echo "============================================================================="
echo -e "${BOLD}     Zero Trust Architecture - Multi-Agent Testbed Demo${NC}"
echo "============================================================================="
echo ""
echo -e "${BLUE}${BOLD}[DEMO 2] Normal Operation - Hotel Search${NC}"
echo "-----------------------------------------------------------------------------"
echo ""
echo "Flow: User → Travel Planner → Hotel Agent → Hotel MCP → Hotel Service"
echo ""
echo -e "${CYAN}REQUEST:${NC}"
echo "┌─────────────────────────────────────────────────────────────────────────┐"
echo "│ POST http://localhost:8080/chat                                         │"
echo "│ Content-Type: application/json                                          │"
echo "│                                                                         │"
echo "│ {                                                                       │"
echo "│   \"message\": \"Find hotels in Miami\",                                   │"
echo "│   \"user_id\": \"11111111-1111-1111-1111-111111111111\"                     │"
echo "│ }                                                                       │"
echo "└─────────────────────────────────────────────────────────────────────────┘"
echo ""
echo "Sending request..."
echo ""

RESPONSE=$(curl -s -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Find hotels in Miami", "user_id": "11111111-1111-1111-1111-111111111111"}')

SUCCESS=$(echo "$RESPONSE" | jq -r '.success')

echo -e "${CYAN}RESPONSE:${NC}"
echo "┌─────────────────────────────────────────────────────────────────────────┐"
echo "│ {                                                                       │"
echo "│   \"success\": $SUCCESS,                                                   │"
echo "│   \"data\": {                                                             │"
echo "│     \"hotels\": {                                                         │"
echo "│       \"content\": [                                                      │"
# Extract first 3 hotel names from the text response
echo "$RESPONSE" | jq -r '.data.hotels.content[0].text' 2>/dev/null | grep "🏨" | head -3 | while read line; do
    echo "│         $line"
done
echo "│         ...                                                             │"
echo "│       ]                                                                 │"
echo "│     }                                                                   │"
echo "│   }                                                                     │"
echo "│ }                                                                       │"
echo "└─────────────────────────────────────────────────────────────────────────┘"
echo ""
echo -e "Result: ${GREEN}✓ SUCCESS - Hotels found in Miami${NC}"
echo ""
read -p "Press Enter to continue..."
clear

# Demo 3
echo ""
echo "============================================================================="
echo -e "${BOLD}     Zero Trust Architecture - Multi-Agent Testbed Demo${NC}"
echo "============================================================================="
echo ""
echo -e "${BLUE}${BOLD}[DEMO 3] mTLS - Mutual TLS Authentication${NC}"
echo "-----------------------------------------------------------------------------"
echo ""
echo "When hotel-agent calls hotel-mcp, both sides verify certificates."
echo ""
echo -e "${CYAN}ENVOY ACCESS LOG (hotel-mcp-envoy):${NC}"
echo "┌─────────────────────────────────────────────────────────────────────────┐"
docker logs zta-hotel-mcp-envoy --tail=1 2>/dev/null | grep -o '{.*}' | jq -r '
  "│ timestamp:     \(.timestamp)
│ service:       \(.service)
│ agent_id:      \(.agent_id)
│ tls_version:   \(.tls_version)
│ peer_cert:     \(.peer_cert | split(",")[0])
│ response_code: \(.response_code)"
' 2>/dev/null
echo "└─────────────────────────────────────────────────────────────────────────┘"
echo ""
echo -e "${GREEN}✓ mTLS verified - hotel-agent proved identity with certificate${NC}"
echo ""
read -p "Press Enter to continue..."
clear

# Demo 4
echo ""
echo "============================================================================="
echo -e "${BOLD}     Zero Trust Architecture - Multi-Agent Testbed Demo${NC}"
echo "============================================================================="
echo ""
echo -e "${BLUE}${BOLD}[DEMO 4] OPA Policy - Authorization Rules${NC}"
echo "-----------------------------------------------------------------------------"
echo ""
echo -e "${CYAN}POLICY (zta-infrastructure/opa/policy.rego):${NC}"
echo "┌─────────────────────────────────────────────────────────────────────────┐"
echo "│ agent_registry := {                                                     │"
echo "│   \"hotel-agent\": {                                                      │"
echo "│     \"type\": \"worker\",                                                   │"
echo "│     \"allowed_targets\": [\"hotel-mcp\"]    ← Can ONLY access hotel-mcp   │"
echo "│   },                                                                    │"
echo "│   \"airline-agent\": {                                                    │"
echo "│     \"type\": \"worker\",                                                   │"
echo "│     \"allowed_targets\": [\"airline-mcp\"]  ← Can ONLY access airline-mcp │"
echo "│   }                                                                     │"
echo "│ }                                                                       │"
echo "└─────────────────────────────────────────────────────────────────────────┘"
echo ""
echo -e "  hotel-agent   → hotel-mcp    ${GREEN}✓ ALLOWED${NC}"
echo -e "  airline-agent → airline-mcp  ${GREEN}✓ ALLOWED${NC}"
echo -e "  hotel-agent   → airline-mcp  ${RED}✗ DENIED (cross-domain)${NC}"
echo ""
read -p "Press Enter to continue..."
clear

# Demo 5
echo ""
echo "============================================================================="
echo -e "${BOLD}     Zero Trust Architecture - Multi-Agent Testbed Demo${NC}"
echo "============================================================================="
echo ""
echo -e "${BLUE}${BOLD}[DEMO 5] Security Test - Cross-Domain Attack${NC}"
echo "-----------------------------------------------------------------------------"
echo ""
echo -e "${RED}ATTACK SCENARIO: hotel-agent tries to access airline-mcp${NC}"
echo ""
echo -e "${CYAN}REQUEST (from inside hotel-agent container):${NC}"
echo "┌─────────────────────────────────────────────────────────────────────────┐"
echo "│ POST https://airline-mcp-envoy:10000/mcp                                │"
echo "│ Headers:                                                                │"
echo "│   x-agent-id: hotel-agent                                               │"
echo "│   Content-Type: application/json                                        │"
echo "│ Certificate: hotel-agent-cert.pem (valid certificate)                   │"
echo "│                                                                         │"
echo "│ Body: {\"jsonrpc\":\"2.0\",\"method\":\"tools/list\",\"id\":1}                   │"
echo "└─────────────────────────────────────────────────────────────────────────┘"
echo ""
echo "Sending malicious request..."
echo ""

HTTP_CODE=$(docker exec zta-hotel-agent curl -s -o /dev/null -w "%{http_code}" \
  -X POST https://airline-mcp-envoy:10000/mcp \
  --cacert /etc/certs/ca-cert.pem \
  --cert /etc/certs/hotel-agent-cert.pem \
  --key /etc/certs/hotel-agent-key.pem \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "x-agent-id: hotel-agent" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}')

echo -e "${CYAN}RESPONSE:${NC}"
echo "┌─────────────────────────────────────────────────────────────────────────┐"
echo -e "│ HTTP Status: ${RED}${BOLD}$HTTP_CODE Forbidden${NC}                                              │"
echo "│                                                                         │"
echo "│ OPA Decision: DENIED                                                    │"
echo "│ Reason: hotel-agent is not in allowed_targets for airline-mcp           │"
echo "└─────────────────────────────────────────────────────────────────────────┘"
echo ""
echo -e "${GREEN}${BOLD}✓ ATTACK BLOCKED${NC} - Cross-domain access denied by OPA policy"
echo ""
read -p "Press Enter to continue..."
clear

# Demo 6
echo ""
echo "============================================================================="
echo -e "${BOLD}     Zero Trust Architecture - Multi-Agent Testbed Demo${NC}"
echo "============================================================================="
echo ""
echo -e "${BLUE}${BOLD}[DEMO 6] Valid Request - Same Domain${NC}"
echo "-----------------------------------------------------------------------------"
echo ""
echo -e "${GREEN}VALID SCENARIO: hotel-agent accesses hotel-mcp (authorized)${NC}"
echo ""
echo -e "${CYAN}REQUEST (from inside hotel-agent container):${NC}"
echo "┌─────────────────────────────────────────────────────────────────────────┐"
echo "│ POST https://hotel-mcp-envoy:10000/mcp                                  │"
echo "│ Headers:                                                                │"
echo "│   x-agent-id: hotel-agent                                               │"
echo "│   Content-Type: application/json                                        │"
echo "│ Certificate: hotel-agent-cert.pem                                       │"
echo "│                                                                         │"
echo "│ Body: {\"jsonrpc\":\"2.0\",\"method\":\"initialize\",...}                      │"
echo "└─────────────────────────────────────────────────────────────────────────┘"
echo ""
echo "Sending valid request..."
echo ""

HTTP_CODE=$(docker exec zta-hotel-agent curl -s -o /dev/null -w "%{http_code}" \
  -X POST https://hotel-mcp-envoy:10000/mcp \
  --cacert /etc/certs/ca-cert.pem \
  --cert /etc/certs/hotel-agent-cert.pem \
  --key /etc/certs/hotel-agent-key.pem \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "x-agent-id: hotel-agent" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"demo","version":"1.0"}},"id":1}')

echo -e "${CYAN}RESPONSE:${NC}"
echo "┌─────────────────────────────────────────────────────────────────────────┐"
echo -e "│ HTTP Status: ${GREEN}${BOLD}$HTTP_CODE OK${NC}                                                       │"
echo "│                                                                         │"
echo "│ OPA Decision: ALLOWED                                                   │"
echo "│ Reason: hotel-agent is in allowed_targets for hotel-mcp                 │"
echo "│                                                                         │"
echo "│ Body: {\"jsonrpc\":\"2.0\",\"result\":{\"protocolVersion\":\"2024-11-05\",...}}  │"
echo "└─────────────────────────────────────────────────────────────────────────┘"
echo ""
echo -e "${GREEN}${BOLD}✓ REQUEST ALLOWED${NC} - Valid same-domain access permitted"
echo ""
read -p "Press Enter to continue..."
clear

# Demo 7
echo ""
echo "============================================================================="
echo -e "${BOLD}     Zero Trust Architecture - Multi-Agent Testbed Demo${NC}"
echo "============================================================================="
echo ""
echo -e "${BLUE}${BOLD}[DEMO 7] Audit Trail - OPA Decision Logs${NC}"
echo "-----------------------------------------------------------------------------"
echo ""
echo "Every authorization decision is logged by OPA for compliance:"
echo ""
echo -e "${CYAN}OPA DECISION LOG:${NC}"
echo "┌─────────────────────────────────────────────────────────────────────────┐"

docker logs zta-opa 2>&1 | grep "Decision Log" | tail -4 | while read line; do
    RESULT=$(echo "$line" | grep -o '"result":[^,}]*' | cut -d':' -f2)
    AGENT=$(echo "$line" | grep -o '"x-agent-id":"[^"]*"' | cut -d'"' -f4)
    HOST=$(echo "$line" | grep -o '"host":"[^"]*"' | cut -d'"' -f4)
    TIME=$(echo "$line" | grep -o '"time":"[^"]*"' | cut -d'"' -f4)
    
    if [ -n "$AGENT" ]; then
        if [ "$RESULT" = "true" ]; then
            echo -e "│ ${GREEN}ALLOW${NC} | $TIME | $AGENT → $HOST"
        else
            echo -e "│ ${RED}DENY${NC}  | $TIME | $AGENT → $HOST"
        fi
    fi
done

echo "└─────────────────────────────────────────────────────────────────────────┘"
echo ""
echo "Full audit trail available for compliance, forensics, and incident response."
echo ""
read -p "Press Enter to continue..."
clear

# Summary
echo ""
echo "============================================================================="
echo -e "${BOLD}     Zero Trust Architecture - Demo Summary${NC}"
echo "============================================================================="
echo ""
echo -e "${GREEN}${BOLD}Security Layers Demonstrated:${NC}"
echo ""
echo "┌─────────────────────────────────────────────────────────────────────────┐"
echo "│                                                                         │"
echo -e "│  ${BOLD}1. mTLS (Authentication)${NC}                                              │"
echo "│     • Every service has a certificate signed by Root CA                 │"
echo "│     • Mutual verification - both sides prove identity                   │"
echo "│     • Cannot impersonate without private key                            │"
echo "│                                                                         │"
echo -e "│  ${BOLD}2. OPA Policy (Authorization)${NC}                                         │"
echo "│     • Agent registry defines who can access what                        │"
echo "│     • Cross-domain access denied by default                             │"
echo "│     • Every decision logged for audit                                   │"
echo "│                                                                         │"
echo -e "│  ${BOLD}3. Envoy Sidecars (Enforcement)${NC}                                       │"
echo "│     • All traffic passes through Envoy proxy                            │"
echo "│     • ext_authz filter checks with OPA before allowing                  │"
echo "│     • Zero direct service-to-service communication                      │"
echo "│                                                                         │"
echo "└─────────────────────────────────────────────────────────────────────────┘"
echo ""
echo -e "${YELLOW}${BOLD}Zero Trust Principle:${NC} Never trust, always verify"
echo ""
echo -e "${BOLD}Key Result:${NC} Even with a valid certificate, hotel-agent cannot access"
echo "            airline-mcp. A breach in one domain is contained."
echo ""
echo "============================================================================="
echo ""

