# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- 6-agent comprehensive audit with prioritized findings
- `requirements.lock` for reproducible builds
- Timing-attack-safe auth comparison (hmac.compare_digest)
- Silent data loss prevention with backup on decryption failure

### Fixed
- Auth timing attack in Streamlit login
- Silent data loss when storage decryption fails
- Sync blocking calls in async contexts

## [1.0.0] - 2025-07-22

### Added
- Initial release
- CURP, NSS IMSS, INE, SAT trámites
- Streamlit web UI with auth
- FastAPI REST API with rate limiting
- Playwright browser automation with pool
- Captcha solving (2captcha + free solver + IMSS CNN)
- Profile management with Fernet encryption
- Docker multi-stage build
- CI/CD with GitHub Actions
