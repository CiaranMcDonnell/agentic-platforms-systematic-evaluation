Feature: Implement JWT Authentication System
  As defined in US-020: Implement JWT Authentication System

  Scenario: AC-020-1 - Registration creates user and returns tokens
    Given no user with email "new@example.com" exists
    When I POST /api/auth/register with valid credentials
    Then I receive 201 with access_token, refresh_token, and user profile

  Scenario: AC-020-2 - Login returns valid JWT tokens
    Given a registered user with email "user@example.com"
    When I POST /api/auth/login with correct credentials
    Then I receive 200 with access_token and refresh_token
    And the access_token is a valid JWT with user_id claim

  Scenario: AC-020-3 - Token refresh issues new access token
    Given a valid refresh_token
    When I POST /api/auth/refresh
    Then I receive a new access_token and rotated refresh_token

  Scenario: AC-020-4 - Logout invalidates refresh token
    Given a valid refresh_token
    When I POST /api/auth/logout
    Then the refresh_token is no longer valid for refresh

  Scenario: AC-020-5 - Password validation enforces strength rules
    When I POST /api/auth/register with password "weak"
    Then I receive 422 with password strength error

  Scenario: AC-020-6 - Rate limiting blocks excessive login attempts
    Given 5 failed login attempts for "user@example.com" in one minute
    When I attempt a 6th login
    Then I receive 429 Too Many Requests

  Scenario: AC-020-7 - Protected routes require valid access token
    Given a protected endpoint
    When I request it without a valid Authorization header
    Then I receive 401 Unauthorized
