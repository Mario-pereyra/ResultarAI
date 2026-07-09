# ADR-0008 — Stack de autenticación Python: sesiones firmadas + Argon2id + TOTP

- **Estado:** aceptado (2026-07-09)

## Contexto

El pivote 2026-07-09 mueve el backend de Node/Mastra + Better Auth (intento `design/` 2026-06) a Python + FastAPI ([ADR-0003](0003-stack-langgraph-litellm-langfuse-mcp.md)). Better Auth queda descartada solo por incompatibilidad de stack (es una librería Node). El change `d11-identidad-acceso` necesita: sesiones server-side firmadas con revocación, roles Admin/Técnico/Funcional, **sin registro público** de usuarios (los crea un Admin), TOTP obligatorio para Admin y opcional para el resto, y acuerdo de uso auditado con re-aceptación. La regla dura del proyecto es clara: **nunca criptografía artesanal, solo librerías mantenidas**.

Se evaluaron dos caminos: (a) `fastapi-users`, la librería de mayor adopción para auth "batteries-included" sobre FastAPI, y (b) una capa propia delgada construida sobre primitivas criptográficas mantenidas (`argon2-cffi` para hashing de contraseñas, `itsdangerous` o `passlib` para firmar tokens de sesión, `pyotp` para TOTP).

## Decisión

**Capa propia delgada sobre librerías criptográficas mantenidas**, no `fastapi-users`:

1. **Contraseñas:** hashing con **Argon2id** vía `argon2-cffi` (ganador del Password Hashing Competition, recomendado por OWASP como primera opción sobre bcrypt/scrypt/PBKDF2 en 2026).
2. **Sesiones:** server-side, con el estado de sesión en Postgres (tabla propia, no JWT stateless) y un identificador de sesión firmado con `itsdangerous` (o `passlib` si se necesita compatibilidad adicional de esquemas) entregado en cookie `HttpOnly` + `Secure` + `SameSite`. Ser server-side es lo que habilita **revocación inmediata** (logout global, expiración forzada de un Admin) — un JWT autocontenido no se puede revocar sin lista negra, que reintroduce el estado que se buscaba evitar.
3. **TOTP:** `pyotp` (RFC 6238) para el segundo factor, obligatorio en rol Admin, opcional en Técnico/Funcional, con códigos de recuperación de un solo uso.
4. Todo el código de auth vive en `core/` solo como *ports* (`AuthPort`, `SessionPort`); la implementación con estas librerías es un adapter (`adapters/auth_*`), igual que el resto del stack (regla dura 1).
5. Sin flujo de registro público ni verificación de email: los usuarios los crea un Admin (`d11-identidad-acceso`); esto es lo que hace innecesaria la parte más grande de `fastapi-users`.

## Alternativas consideradas

1. **`fastapi-users`** — evaluada en serio, no descartada por defecto. Da de fábrica registro, verificación de email, reseteo de contraseña, OAuth social y ya usa `passlib`/Argon2 por debajo. Rechazada para este proyecto porque: (a) su superficie principal —registro público, verificación por email, flujos OAuth— no aplica (no hay alta pública de usuarios, ver `d11-identidad-acceso`); (b) su modelo de sesión por defecto es JWT o backend de cookie con su propio ciclo de vida, y adaptarlo al requisito de revocación server-side + TOTP por rol exige tanto código propio como construir la capa delgada directamente; (c) es una dependencia más grande y con más superficie que gobernar en `core`/adapters por una fracción pequeña de su funcionalidad. Se reevalúa si el roadmap agrega login social o registro público (ninguno está previsto: ver "no-objetivos" en `docs/01-vision.md`).
2. **JWT stateless (access + refresh token) sin sesión server-side** — rechazada: revocar un token comprometido o forzar cierre de sesión de un usuario exige lista negra o TTL corto con refresh constante; ninguna de las dos es más simple que una sesión server-side, y el requisito explícito de `d11` es revocación inmediata.
3. **bcrypt o scrypt en lugar de Argon2id** — rechazada: Argon2id es la recomendación vigente de OWASP (2026) por resistencia a ataques con GPU/ASIC; no hay razón para usar el estándar anterior en un proyecto greenfield.
4. **Better Auth** — descartada solo por stack: es una librería Node/TypeScript, incompatible con el backend Python decidido en ADR-0003. No hay evaluación de fondo porque el criterio de exclusión es binario (lenguaje).
5. **Criptografía propia (hash o firma hechos a mano)** — descartada de plano: viola la regla dura del proyecto; toda primitiva usa una librería mantenida y auditada.

## Consecuencias

- (+) Revocación de sesión inmediata y auditable (coherente con el audit log append-only, regla dura 4).
- (+) Superficie de auth mínima y explícita: solo lo que `d11-identidad-acceso` pide, sin código muerto de flujos que el producto no usa (registro público, OAuth social).
- (+) Cada primitiva (Argon2id, firma de tokens, TOTP) viene de una librería mantenida y con revisión pública — cumple la regla de no criptografía artesanal.
- (−) Más código propio que integrar `fastapi-users` de fábrica → mitigado: la superficie es chica (login, logout, sesión, TOTP, roles) y corre bajo el mismo régimen de tests/CI que el resto de `core`/adapters.
- (−) Sin camino gratuito a OAuth social o SSO empresarial si el producto lo necesitara más adelante → aceptado: no está en el alcance actual (`docs/01-vision.md`); se reevaluaría con un ADR nuevo si aparece ese requisito.

## Fuentes

- OWASP Password Storage Cheat Sheet (Argon2id como primera opción) — https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- `argon2-cffi` (bindings Python mantenidos de la librería de referencia Argon2) — https://argon2-cffi.readthedocs.io/
- `itsdangerous` (firma de tokens, usado internamente por Flask/Django-adjacent stacks) — https://itsdangerous.palletsprojects.com/
- `passlib` — https://passlib.readthedocs.io/
- `pyotp` (TOTP/HOTP, RFC 4226/6238) — https://pyauth.github.io/pyotp/
- `fastapi-users` (evaluada y descartada) — https://fastapi-users.github.io/fastapi-users/
- OWASP Session Management Cheat Sheet (revocación server-side) — https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- `docs/07-roadmap.md`, tabla "Cambios adoptados" (fila "Runtime backend") y change `d11-identidad-acceso`.
