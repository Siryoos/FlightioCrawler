#!/bin/bash

# SSL Certificate Generation Script for FlightIO Crawler
# This script generates self-signed certificates for development use

set -e

# Configuration
CERT_DIR="/etc/nginx/ssl"
CERT_NAME="server"
COUNTRY="US"
STATE="California"
CITY="San Francisco"
ORGANIZATION="FlightIO"
ORGANIZATIONAL_UNIT="Development"
COMMON_NAME="flightio.local"

# Additional Subject Alternative Names (SANs)
SAN_LIST="DNS:flightio.local,DNS:localhost,DNS:admin.flightio.local,IP:127.0.0.1,IP:::1"

# Create certificate directory if it doesn't exist
echo "Creating certificate directory..."
mkdir -p "$CERT_DIR"

# Generate private key
echo "Generating private key..."
openssl genrsa -out "$CERT_DIR/${CERT_NAME}.key" 2048

# Generate certificate signing request
echo "Generating certificate signing request..."
openssl req -new -key "$CERT_DIR/${CERT_NAME}.key" -out "$CERT_DIR/${CERT_NAME}.csr" -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORGANIZATION/OU=$ORGANIZATIONAL_UNIT/CN=$COMMON_NAME"

# Create configuration file for certificate extensions
cat > "$CERT_DIR/cert.conf" << EOF
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
C = $COUNTRY
ST = $STATE
L = $CITY
O = $ORGANIZATION
OU = $ORGANIZATIONAL_UNIT
CN = $COMMON_NAME

[v3_req]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = flightio.local
DNS.2 = localhost
DNS.3 = admin.flightio.local
IP.1 = 127.0.0.1
IP.2 = ::1
EOF

# Generate self-signed certificate
echo "Generating self-signed certificate..."
openssl x509 -req -in "$CERT_DIR/${CERT_NAME}.csr" -signkey "$CERT_DIR/${CERT_NAME}.key" -out "$CERT_DIR/${CERT_NAME}.crt" -days 365 -extensions v3_req -extfile "$CERT_DIR/cert.conf"

# Set proper permissions
echo "Setting permissions..."
chmod 600 "$CERT_DIR/${CERT_NAME}.key"
chmod 644 "$CERT_DIR/${CERT_NAME}.crt"

# Create DH parameters for perfect forward secrecy
echo "Generating DH parameters (this may take a while)..."
openssl dhparam -out "$CERT_DIR/dhparam.pem" 2048
chmod 644 "$CERT_DIR/dhparam.pem"

# Clean up temporary files
rm -f "$CERT_DIR/${CERT_NAME}.csr" "$CERT_DIR/cert.conf"

echo "SSL certificates generated successfully!"
echo "Certificate: $CERT_DIR/${CERT_NAME}.crt"
echo "Private Key: $CERT_DIR/${CERT_NAME}.key"
echo "DH Parameters: $CERT_DIR/dhparam.pem"
echo ""
echo "To use these certificates, add the following to your /etc/hosts file:"
echo "127.0.0.1 flightio.local"
echo "127.0.0.1 admin.flightio.local"
echo ""
echo "Note: These are self-signed certificates for development use only."
echo "For production, use certificates from a trusted Certificate Authority." 