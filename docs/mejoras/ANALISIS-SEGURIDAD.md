# Análisis de Seguridad

**Proyecto:** agente-tramites-gobmx  
**Fecha:** 2026-07-08  
**Analista:** Señor Arquitecto (subagente especializado)

---

## Vulnerabilidades Críticas (Prioridad Inmediata)

### 🔴 C1 — `--no-sandbox` en Playwright (Container Escape)

**Archivo:** `src/modules/base.py:116`
```python
browser = await p.firefox.launch(
    headless=HEADLESS,
    args=["--no-sandbox"],  # DESACTIVA SANDBOX
)
```

El sandbox de Firefox es la última línea de defensa contra exploits. Sin él, un RCE en Playwright es un RCE en el host. En Docker, rompe el aislamiento.

**Fix:** Eliminar `--no-sandbox` o condicionarlo a flag explícito `PLAYWRIGHT_NO_SANDBOX=true`.

### 🔴 C2 — CORS `allow_origins="*"` por defecto

**Archivo:** `src/api.py:146`
```python
allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
```

Si la API se despliega sin configurar CORS_ORIGINS, cualquier sitio web puede hacer requests cross-origin. Riesgo de CSRF.

**Fix:** En producción, no permitir `*`. Validar que CORS_ORIGINS esté configurada explícitamente.

### 🔴 C3 — Salt estático en PBKDF2 para Fernet

**Archivo:** `src/utils/storage.py:40`
```python
stretched = hashlib.pbkdf2_hmac("sha256", raw_key.encode(), b"fernet-key-salt", 600_000)
```

El salt hardcodeado anula el propósito del salt: misma STORAGE_KEY = misma clave Fernet. Ataque de diccionario offline posible.

**Fix:** Usar `secrets.token_bytes(16)` y persistir en archivo `.storage_salt`.

### 🔴 C4 — `DISABLE_API_AUTH` permite desactivar autenticación por env var

**Archivo:** `src/api.py:73-74`

Cualquier persona con acceso al entorno puede desactivar toda la autenticación de la API.

**Fix:** No permitir override por env var en producción. API_KEY debe ser obligatoria.

### 🟠 C5 — API key de Anthropic validada solo por prefijo `sk-ant-`

**Archivo:** `src/utils/claude.py:49`

Validar solo el prefijo no es seguridad real. Si alguien comitea una key real, pasa la validación.

**Fix:** Validar largo mínimo (~40+ chars después del prefijo) + git hook detector.

---

## Vulnerabilidades Medias

| ID | Hallazgo | Archivo | Fix |
|----|----------|---------|-----|
| M1 | IMAP sin verificación explícita de certificado TLS | `mail_reader.py:55` | Agregar `ssl.create_default_context()` con verificación |
| M2 | PII exfiltrable por stdout (`print()` directo) | `storage.py:88`, `free_captcha.py:134` | Pasar por TramiteLogger o sanitizar |
| M3 | `subprocess.run` con path de PDF — potencial command injection | `base.py:447-449` | Validar path o usar `os.startfile()` en Windows |
| M4 | URL de audio challenge sin validación (SSRF potencial) | `free_captcha.py:217-223` | Validar que empiece con `https://` |
| M5 | `exc_info=True` expone trazas con posible PII | `api.py:225,241` | Usar flag controlado `VERBOSE` |
| M6 | Hash determinístico por alias (salt derivado del alias) | `storage.py:73-76` | Usar salt aleatorio por campo |
| M7 | Sin verificación de integridad en descargas de PDF | Módulos varios | Checksum SHA-256 post-descarga |

---

## Buenas Prácticas (lo que ya está bien)

- ✅ `secrets_manager.py` centraliza secretos con soporte Windows Credential Manager
- ✅ `store_all()` chequea placeholders antes de migrar
- ✅ `config.env` en `.gitignore` y `.dockerignore`
- ✅ Fernet (AES-128-CBC + HMAC-SHA256) — algoritmo correcto
- ✅ PBKDF2 con 600k iteraciones para key stretching
- ✅ Sanitización automática de PII en logs (CURP, NSS, email)
- ✅ Docker multi-stage + non-root user (uid 1000)
- ✅ HEALTHCHECK en Dockerfile
- ✅ Rate limiting con slowapi configurable
- ✅ Validación CURP con regex en API
- ✅ Pydantic models con field_validator
- ✅ Docs/Redoc desactivados en producción

---

## Recomendaciones Concretas

1. **Eliminar `--no-sandbox`** de `base.py:116` o hacerlo condicional
2. **CORS restrictivo** en producción con validación de origen
3. **Salt aleatorio** para PBKDF2 con migración de perfiles existentes
4. **Eliminar `DISABLE_API_AUTH`** o limitarlo a desarrollo
5. **Verificación TLS** en IMAP (mail_reader.py)
6. **Pre-commit hook** para detectar patrones de API keys
7. **Ejecutar `pip-audit`** en CI para detectar CVEs conocidos

---

## Resumen de Prioridades

| # | Hallazgo | Archivo | Severidad |
|---|----------|---------|-----------|
| 1 | `--no-sandbox` desactiva aislamiento | `base.py:116` | 🔴 Crítica |
| 2 | CORS `*` por defecto | `api.py:146` | 🔴 Crítica |
| 3 | Salt estático en PBKDF2 | `storage.py:40` | 🔴 Crítica |
| 4 | DISABLE_API_AUTH existe | `api.py:74` | 🔴 Crítica |
| 5 | API key Anthropic solo valida prefijo | `claude.py:49` | 🟠 Alta |
| 6 | IMAP sin verificación de cert | `mail_reader.py:55` | 🟡 Media |
| 7 | PII en stdout por `print()` | Varios | 🟡 Media |
| 8 | URL de audio sin validar | `free_captcha.py:217` | 🟡 Media |
| 9 | Hash determinístico por alias | `storage.py:73` | 🟡 Media |
| 10 | `exc_info=True` expone trazas | `api.py:225,241` | 🟡 Media |
