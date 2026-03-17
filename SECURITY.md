# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please:

1. **Do NOT** open a public issue
2. Email: security@hylilabs.com or contact maintainers privately
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will respond within 48 hours and work with you to resolve the issue.

## Security Best Practices

### API Keys

- Never commit API keys to the repository
- Use `.env` files for local development
- Use `.env.example` as a template (no real keys)
- Rotate keys if accidentally exposed

### Data Protection

- HyliLabs is KVKK (Turkish Data Protection Law) compliant
- All CV data is processed with user consent
- Audit logs track all data access
- Company-level data isolation is enforced

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 1.x.x   | Supported          |
| < 1.0   | Not Supported      |
