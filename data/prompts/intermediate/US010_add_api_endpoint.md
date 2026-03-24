# Prompt

Add REST API endpoints for user profile management to a FastAPI application.

Requirements:
1. Create `GET /api/users/{user_id}/profile` — returns the user's profile.
   - Return 200 with the profile JSON on success.
   - Return 404 with `{"detail": "User not found"}` for unknown user IDs.
2. Create `PUT /api/users/{user_id}/profile` — updates the user's profile.
   - Accept a JSON body with optional fields: `display_name`, `bio`, `avatar_url`.
   - Validate the body with a Pydantic schema; return 422 on invalid input.
   - Return 200 with the updated profile on success.
3. Define Pydantic request/response schemas in `app/schemas/profile.py`.
4. Add the router to `app/main.py`.
5. Write unit tests in `tests/test_profiles.py` covering all success and error paths.

Files to create or modify:
- `app/routers/profiles.py` (create)
- `app/schemas/profile.py` (create)
- `tests/test_profiles.py` (create)
- `app/main.py` (modify — register the new router)

# Context

You are working in a FastAPI project with the following structure:

```
app/
  __init__.py
  main.py          # FastAPI app instance, existing routers already mounted
  models/
    user.py        # SQLAlchemy User model with id, email, display_name, bio, avatar_url
  routers/
    __init__.py
  schemas/
    __init__.py
tests/
  __init__.py
  conftest.py      # Provides a `client` fixture (TestClient)
```

The project uses SQLAlchemy with an async session and FastAPI dependency
injection. A `get_db` dependency is available in `app/dependencies.py`.
Python 3.10+, pytest, httpx for testing.
