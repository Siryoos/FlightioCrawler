#!/bin/bash

# Docker-aware SSL Certificate Generation Script for FlightIO Crawler
# This script generates self-signed certificates for development use inside Docker containers

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

# Check if running inside Docker
if [ -f /.dockerenv ] || [ -n "$DOCKER_ENV" ]; then
    echo "Running inside Docker container..."
    # Use the mounted volume path for Docker
    CERT_DIR="/etc/nginx/ssl"
else
    echo "Running on host system..."
    # Use the current directory for host development
    CERT_DIR="./ssl"
fi

# Create certificate directory if it doesn't exist
echo "Creating certificate directory at $CERT_DIR..."
mkdir -p "$CERT_DIR"

# Check if certificates already exist
if [ -f "$CERT_DIR/${CERT_NAME}.crt" ] && [ -f "$CERT_DIR/${CERT_NAME}.key" ]; then
    echo "Certificates already exist. Skipping generation..."
    echo "To regenerate, delete the existing certificates and run this script again."
    exit 0
fi

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
DNS.4 = nginx
DNS.5 = api
DNS.6 = frontend
DNS.7 = monitor
IP.1 = 127.0.0.1
IP.2 = ::1
IP.3 = 0.0.0.0
EOF

# Generate self-signed certificate
echo "Generating self-signed certificate..."
openssl x509 -req -in "$CERT_DIR/${CERT_NAME}.csr" -signkey "$CERT_DIR/${CERT_NAME}.key" -out "$CERT_DIR/${CERT_NAME}.crt" -days 365 -extensions v3_req -extfile "$CERT_DIR/cert.conf"

# Set proper permissions
echo "Setting permissions..."
chmod 600 "$CERT_DIR/${CERT_NAME}.key"
chmod 644 "$CERT_DIR/${CERT_NAME}.crt"

# Generate DH parameters for perfect forward secrecy
if [ ! -f "$CERT_DIR/dhparam.pem" ]; then
    echo "Generating DH parameters (this may take a while)..."
    openssl dhparam -out "$CERT_DIR/dhparam.pem" 2048
    chmod 644 "$CERT_DIR/dhparam.pem"
else
    echo "DH parameters already exist, skipping generation..."
fi

# Clean up temporary files
rm -f "$CERT_DIR/${CERT_NAME}.csr" "$CERT_DIR/cert.conf"

echo "SSL certificates generated successfully!"
echo "Certificate: $CERT_DIR/${CERT_NAME}.crt"
echo "Private Key: $CERT_DIR/${CERT_NAME}.key"
echo "DH Parameters: $CERT_DIR/dhparam.pem"
echo ""
echo "Certificate details:"
openssl x509 -in "$CERT_DIR/${CERT_NAME}.crt" -text -noout | grep -E "(Subject:|DNS:|IP Address:|Not Before|Not After)"
echo ""
echo "To use these certificates, add the following to your /etc/hosts file:"
echo "127.0.0.1 flightio.local"
echo "127.0.0.1 admin.flightio.local"
echo ""
echo "Note: These are self-signed certificates for development use only."
echo "For production, use certificates from a trusted Certificate Authority." 