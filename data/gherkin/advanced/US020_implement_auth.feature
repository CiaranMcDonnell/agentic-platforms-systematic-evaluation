Feature: JWT Authentication System
  As a user of the application
  I want secure authentication with JWT tokens
  So that I can access protected resources safely

  Scenario: AC-020-1 - Registration creates user and returns tokens
    Given no user with email "new@example.com" exists
    When I send POST /api/auth/register with valid credentials
    Then the response status is 201
    And the response contains an access_token and refresh_token
    And the user is persisted in the database with a hashed password

  Scenario: AC-020-2 - Login returns valid JWT tokens
    Given a registered user with email "user@example.com"
    When I send POST /api/auth/login with correct credentials
    Then the response status is 200
    And the response contains an access_token and refresh_token
    And the access_token is a valid JWT with a 15-minute expiry

  Scenario: AC-020-3 - Token refresh issues new access token
    Given I have a valid refresh_token
    When I send POST /api/auth/refresh with the refresh_token
    Then the response status is 200
    And the response contains a new access_token

  Scenario: AC-020-4 - Logout invalidates refresh token
    Given I have a valid refresh_token
    When I send POST /api/auth/logout with the refresh_token
    Then the response status is 200
    And subsequent refresh requests with that token return 401

  Scenario: AC-020-5 - Password validation enforces strength rules
    Given I attempt to register with password "weak"
    When I send POST /api/auth/register
    Then the response status is 422
    And the error mentions password strength requirements

  Scenario: AC-020-6 - Rate limiting blocks excessive login attempts
    Given a registered user with email "user@example.com"
    When I send 6 failed login attempts within one minute
    Then the 6th response status is 429
    And the response indicates rate limit exceeded

  Scenario: AC-020-7 - Protected routes require valid access token
    Given a protected endpoint exists
    When I send a request without an Authorization header
    Then the response status is 401
    When I send a request with an expired access_token
    Then the response status is 401
    When I send a request with a valid access_token
    Then the response status is 200
