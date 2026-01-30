#!/bin/bash
# =============================================================================
# mTLS Certificate Generation Script for ZTA Multi-Agent Testbed
# =============================================================================

set -e

CERT_DIR="$(dirname "$0")"
cd "$CERT_DIR"

CA_DAYS=3650
CERT_DAYS=365

echo "=== Generating mTLS Certificates ==="

# =============================================================================
# Step 1: Create Root CA with proper extensions
# =============================================================================
echo "[1/3] Creating Root CA..."

# CA config with key usage
cat > ca.cnf << 'EOF'
[req]
default_bits = 4096
prompt = no
default_md = sha256
distinguished_name = dn
x509_extensions = v3_ca

[dn]
C = US
ST = Pennsylvania
L = Pittsburgh
O = ZTA-Testbed
OU = Certificate Authority
CN = ZTA-Root-CA

[v3_ca]
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always,issuer
basicConstraints = critical, CA:TRUE, pathlen:0
keyUsage = critical, digitalSignature, cRLSign, keyCertSign
EOF

openssl genrsa -out ca-key.pem 4096
openssl req -new -x509 -days $CA_DAYS -key ca-key.pem -out ca-cert.pem -config ca.cnf
echo "  ✓ CA certificate created"

# =============================================================================
# Step 2: Create Service Certificates
# =============================================================================
echo "[2/3] Creating Service Certificates..."

generate_cert() {
    local SERVICE=$1
    shift
    local DNS_NAMES="$@"
    
    echo "  Creating: $SERVICE"
    
    # Create config with SANs and proper extensions
    cat > "${SERVICE}.cnf" << EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
req_extensions = req_ext

[dn]
C = US
ST = Pennsylvania
L = Pittsburgh
O = ZTA-Testbed
OU = ${SERVICE}
CN = ${SERVICE}

[req_ext]
subjectAltName = @alt_names
basicConstraints = CA:FALSE
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth, clientAuth

[alt_names]
EOF
    
    # Add DNS names
    local i=1
    for dns in $DNS_NAMES; do
        echo "DNS.$i = $dns" >> "${SERVICE}.cnf"
        i=$((i+1))
    done
    
    # Create extension config for signing
    cat > "${SERVICE}-ext.cnf" << EOF
subjectAltName = @alt_names
basicConstraints = CA:FALSE
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth, clientAuth

[alt_names]
EOF
    
    local i=1
    for dns in $DNS_NAMES; do
        echo "DNS.$i = $dns" >> "${SERVICE}-ext.cnf"
        i=$((i+1))
    done
    
    # Generate key and CSR
    openssl genrsa -out "${SERVICE}-key.pem" 2048 2>/dev/null
    openssl req -new -key "${SERVICE}-key.pem" -out "${SERVICE}.csr" -config "${SERVICE}.cnf"
    
    # Sign with CA
    openssl x509 -req -days $CERT_DAYS \
        -in "${SERVICE}.csr" \
        -CA ca-cert.pem \
        -CAkey ca-key.pem \
        -CAcreateserial \
        -out "${SERVICE}-cert.pem" \
        -extfile "${SERVICE}-ext.cnf" 2>/dev/null
    
    # Cleanup temp files
    rm -f "${SERVICE}.csr" "${SERVICE}.cnf" "${SERVICE}-ext.cnf"
    
    # Verify
    openssl verify -CAfile ca-cert.pem "${SERVICE}-cert.pem" >/dev/null 2>&1 && echo "    ✓ Verified"
}

# Generate certs for all services
generate_cert "travel-planner" "travel-planner" "travel-planner-envoy" "localhost" "zta-travel-planner"
generate_cert "airline-agent" "airline-agent" "airline-agent-envoy" "localhost" "zta-airline-agent"
generate_cert "hotel-agent" "hotel-agent" "hotel-agent-envoy" "localhost" "zta-hotel-agent"
generate_cert "car-rental-agent" "car-rental-agent" "car-rental-agent-envoy" "localhost" "zta-car-rental-agent"
generate_cert "airline-mcp" "airline-mcp" "airline-mcp-envoy" "localhost" "zta-airline-mcp"
generate_cert "hotel-mcp" "hotel-mcp" "hotel-mcp-envoy" "localhost" "zta-hotel-mcp"
generate_cert "car-rental-mcp" "car-rental-mcp" "car-rental-mcp-envoy" "localhost" "zta-car-rental-mcp"
generate_cert "opa" "opa" "localhost" "zta-opa"

# Cleanup
rm -f ca.cnf ca-cert.srl

# =============================================================================
# Step 3: Summary
# =============================================================================
echo "[3/3] Summary"
echo ""
echo "Certificates created:"
ls -1 *.pem | sed 's/^/  /'
echo ""
echo "=== Done ==="
