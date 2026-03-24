# Prompt

Implement a complete JWT-based authentication system for a FastAPI application.

Requirements:
1. **Register** — `POST /api/auth/register`
   - Accept `email`, `password`, `display_name`.
   - Hash the password (bcrypt).
   - Create the user in the database.
   - Return access and refresh tokens.
2. **Login** — `POST /api/auth/login`
   - Accept `email` and `password`.
   - Verify credentials; return 401 on mismatch.
   - Return access token (short-lived, 15 min) and refresh token (long-lived, 7 days).
3. **Refresh** — `POST /api/auth/refresh`
   - Accept a valid refresh token.
   - Issue a new access token without requiring re-login.
4. **Logout** — `POST /api/auth/logout`
   - Accept the refresh token and invalidate it (token blocklist or DB flag).
5. **Password validation** — enforce minimum 8 characters, at least one uppercase,
   one lowercase, one digit, one special character.
6. **Rate limiting** — limit login attempts to 5 per minute per email address.
   Return 429 on excess.
7. **Protected routes** — create a `get_current_user` dependency that extracts and
   validates the access token from the `Authorization: Bearer <token>` header.
   Return 401 if missing/invalid/expired.

Files to create or modify:
- `app/routers/auth.py` (create)
- `app/schemas/auth.py` (create)
- `app/services/auth_service.py` (create)
- `app/dependencies/auth.py` (create)
- `app/models/user.py` (modify — add hashed_password, is_active fields)
- `app/main.py` (modify — register auth router)
- `tests/test_auth.py` (create — comprehensive tests)

# Context

You are working in a FastAPI project with SQLAlchemy (async), an existing User
model, and a `get_db` dependency. The project has `pytest` and `httpx` for
testing, and `python-jose` and `passlib[bcrypt]` are available as dependencies.

The project structure follows the same layout described in US-010. There is no
existing authentication — you are adding it from scratch.

Python 3.10+. Use environment variables (`SECRET_KEY`, `ALGORITHM`) for JWT
configuration with sensible defaults.
