# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

### How to Report

1. **Email**: Send details to the repository owner via GitHub private message
2. **Include**:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### What to Expect

- **Acknowledgment**: Within 48 hours
- **Assessment**: Within 1 week
- **Fix timeline**: Depends on severity
  - Critical (auth bypass, data leak): 24-72 hours
  - High (injection, privilege escalation): 1 week
  - Medium (information disclosure): 2 weeks
  - Low (minor issues): Next release

## Scope

### In Scope

- Authentication and authorization bypass
- Personal data (PII) exposure — CURP, RFC, NSS, email
- Remote code execution
- SQL/NoSQL injection
- Cross-site scripting (XSS)
- Path traversal
- Cryptographic weaknesses
- Rate limiting bypass
- Session hijacking

### Out of Scope

- Denial of service (DoS) against government portals
- Social engineering attacks
- Issues in third-party dependencies (report to upstream)
- Issues requiring physical access to the server

## Security Measures

This project implements:

- **Encryption**: Fernet symmetric encryption with bcrypt KDF for stored profiles
- **Authentication**: Timing-safe password comparison (`hmac.compare_digest`)
- **Input validation**: Regex-based validation for CURP, RFC, email with PII masking in errors
- **Rate limiting**: Per-endpoint configurable limits via slowapi
- **PII protection**: Automatic sanitization in logs, masked CLI output
- **Docker**: Non-root user, multi-stage build, resource limits
- **Browser automation**: Anti-detection evasion, telemetry disabled

## Known Limitations

- Password-based authentication (no MFA)
- No request size limits configured
- Debug mode can bypass CAPTCHA solving
- Profiles stored on filesystem (not encrypted at rest in transit)

## Updates

This security policy is effective as of July 2025 and will be updated as the project evolves.
