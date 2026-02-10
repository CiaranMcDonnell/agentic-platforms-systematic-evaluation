Feature: Add REST API Endpoint for User Profiles
  As defined in US-010: Add REST API Endpoint for User Profiles

  Scenario: AC-010-1 - GET endpoint returns profile for valid user
    Given a user with id "user-123" exists
    When I send GET /api/users/user-123/profile
    Then I receive 200 with the user's profile JSON

  Scenario: AC-010-2 - GET endpoint returns 404 for unknown user
    Given no user with id "unknown" exists
    When I send GET /api/users/unknown/profile
    Then I receive 404

  Scenario: AC-010-3 - PUT endpoint updates profile
    Given a user with id "user-123" exists
    When I send PUT /api/users/user-123/profile with {"display_name": "New Name"}
    Then I receive 200 with the updated profile
    And the display_name is "New Name"

  Scenario: AC-010-4 - Pydantic validation rejects invalid input
    Given a user with id "user-123" exists
    When I send PUT /api/users/user-123/profile with {"bio": 12345}
    Then I receive 422
