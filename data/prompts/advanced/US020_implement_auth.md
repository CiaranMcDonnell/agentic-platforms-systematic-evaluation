# Prompt

Implement a JWT-based authentication system with the following:

Endpoints:
1. POST /api/auth/register
   - Accepts: email, password, display_name
   - Validates password strength (8+ chars, mixed case, digit)
   - Hashes password with bcrypt
   - Returns user profile + access token + refresh token

2. POST /api/auth/login
   - Accepts: email, password
   - Verifies credentials
   - Returns access token (15min) + refresh token (7 days)
   - Rate limit: 5 attempts per minute per email

3. POST /api/auth/refresh
   - Accepts: refresh_token
   - Returns new access token
   - Rotates refresh token

4. POST /api/auth/logout
   - Accepts: refresh_token
   - Invalidates the refresh token

5. Add authentication middleware/dependency for protected routes

Security requirements:
- Passwords hashed with bcrypt (cost factor 12)
- JWT signed with HS256, configurable secret from env
- Refresh tokens stored in database, support revocation
- Rate limiting on login endpoint

Testing:
- Unit tests for all endpoints
- Test token expiry, refresh rotation, and revocation
- Test password validation rules
- Test rate limiting behavior

# Context

The project uses FastAPI with an existing app instance in app/main.py.
Database: async SQLAlchemy with PostgreSQL.
Environment variables loaded via pydantic-settings.
Use python-jose for JWT, passlib[bcrypt] for password hashing.
Follow existing patterns in the codebase.
