# SSL Certificate Setup for FlightIO Crawler

This directory contains SSL certificates and configuration files for the FlightIO Crawler nginx setup.

## Files

### Development Certificates (Self-Signed)
- `server.crt` - Self-signed SSL certificate for development
- `server.key` - Private key for the SSL certificate
- `dhparam.pem` - Diffie-Hellman parameters for perfect forward secrecy

### Scripts
- `docker-generate-cert.sh` - Docker-aware certificate generation script
- `generate_cert.sh` - Host-based certificate generation script

### Configuration
- `production-ssl.conf` - Production SSL configuration template

## Development Setup

### Current Status
✅ Self-signed certificates have been generated for development use.

The current certificates include the following domains:
- `flightio.local`
- `localhost`
- `admin.flightio.local`
- `nginx` (for Docker internal networking)
- `api` (for Docker internal networking)
- `frontend` (for Docker internal networking)
- `monitor` (for Docker internal networking)

### Usage
1. Add the following entries to your `/etc/hosts` file:
   ```
   127.0.0.1 flightio.local
   127.0.0.1 admin.flightio.local
   ```

2. Access the application via:
   - Main application: `https://flightio.local`
   - Admin interface: `https://admin.flightio.local:8443`

3. Your browser will show a security warning for self-signed certificates. This is normal for development.

## Production Setup

### Certificate Requirements
For production deployment, you'll need:
1. **SSL Certificate** from a trusted Certificate Authority (CA)
2. **Private Key** corresponding to the certificate
3. **Intermediate Certificate Chain** (if provided by CA)

### Recommended Certificate Authorities
- **Let's Encrypt** (free, automated renewal)
- **DigiCert** (commercial, extended validation available)
- **Cloudflare** (integrated with CDN services)
- **AWS Certificate Manager** (for AWS deployments)

### Let's Encrypt Setup
```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Generate certificates
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Test automatic renewal
sudo certbot renew --dry-run
```

### Manual Certificate Installation
1. Replace `server.crt` with your production certificate
2. Replace `server.key` with your production private key
3. Update `production-ssl.conf` with correct paths
4. Include the configuration in your nginx setup
5. Test configuration: `nginx -t`
6. Reload nginx: `systemctl reload nginx`

## Security Features

### Current Configuration
- **TLS 1.2 and 1.3** support only
- **Perfect Forward Secrecy** via DH parameters
- **OCSP Stapling** for certificate validation
- **Security Headers** (HSTS, CSP, etc.)
- **Modern cipher suites** for optimal security

### Certificate Validation
```bash
# Check certificate details
openssl x509 -in server.crt -text -noout

# Verify certificate chain
openssl verify -CAfile ca-bundle.crt server.crt

# Test SSL configuration
openssl s_client -connect flightio.local:443 -servername flightio.local
```

## Troubleshooting

### Common Issues
1. **Certificate not found**: Ensure files are in `/etc/nginx/ssl/` within containers
2. **Permission denied**: Verify `server.key` has 600 permissions
3. **DH parameters missing**: Run certificate generation script to create `dhparam.pem`
4. **Browser warnings**: Expected for self-signed certificates in development

### Regenerating Certificates
```bash
# For development
./docker-generate-cert.sh

# For production
# Follow your CA's specific instructions
```

## Docker Integration

The certificates work seamlessly with Docker containers:
- Volume mounted to `/etc/nginx/ssl/` in nginx container
- Scripts detect Docker environment automatically
- Includes Docker service names in certificate SANs

## Certificate Expiry

### Development
- Self-signed certificates expire after 1 year
- Regenerate using provided scripts before expiration

### Production
- Set up automated renewal (especially for Let's Encrypt)
- Monitor certificate expiry dates
- Have alerting in place for upcoming expirations

## Security Best Practices

1. **Keep private keys secure** (600 permissions, encrypted storage)
2. **Use strong cipher suites** (see production-ssl.conf)
3. **Enable HSTS** with appropriate max-age
4. **Implement certificate pinning** for critical applications
5. **Regular security audits** of SSL configuration
6. **Monitor certificate transparency logs**

For additional security hardening, refer to the main security documentation. 