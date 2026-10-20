---
name: percepcion-dev-login-local
description: Cómo entrar al portal local como cualquier usuario (p.ej. Alberto) sin OAuth real, para probar Percepción y otros paneles
metadata:
  type: reference
---

Para probar la Torre en local (frontend :8001, backend :8011) como un usuario arbitrario sin Google OAuth:

1. `GET http://127.0.0.1:8011/auth/dev-login?email=<email>&name=<name>` — solo funciona con `app_env=dev` (si no, 404). Acepta cualquier email de dominio permitido (`ucn.cl`, `ce.ucn.cl`). Devuelve `session_token` + `user`.
2. La app requiere DOS claves en `localStorage`, no solo el token:
   - `torre-control-ai-session-token` = el `session_token`
   - `torre-control-ai-user` = el objeto `user` (JSON) — App.tsx en el mount valida `storedUser?.allowed && token` (App.tsx:348).
3. Recargar. Un usuario `ucn_user` (rol default de Alberto) ve pocas pestañas; el botón "Perfil admin" cambia a `director_admin` (Alberto tiene `available_profiles: [ucn_user, engineer, director_admin]`) y ahí aparece **Percepción** (grupo "indicadores", solo tiers altos).

Percepción vista OK con datos reales de `percepcion_real_preview.db`: índice 48, confianza 68%, sedes Antofagasta/Coquimbo, tema Académico domina. Ver [[percepcion-arquitectura]].
