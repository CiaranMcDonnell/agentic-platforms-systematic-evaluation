# Prompt

Add REST API endpoints for user profile management:

1. GET /api/users/{user_id}/profile
   - Returns the user's profile as JSON
   - Returns 404 if user not found
   - Response includes: user_id, display_name, email, bio, avatar_url, created_at

2. PUT /api/users/{user_id}/profile
   - Updates the user's profile
   - Accepts JSON body with optional fields: display_name, bio, avatar_url
   - Validates input with Pydantic models
   - Returns updated profile
   - Returns 404 if user not found
   - Returns 422 for invalid input

3. Add Pydantic models for request/response validation

4. Write unit tests covering success and error cases

# Context

The project uses FastAPI with an existing app instance in app/main.py.
Database access uses an async repository pattern (app/repositories/).
Existing tests use pytest with httpx AsyncClient.
Follow existing patterns in app/routers/ for new endpoints.
