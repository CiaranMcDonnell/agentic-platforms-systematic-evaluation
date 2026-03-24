Feature: REST API Endpoint for User Profiles
  As an API consumer
  I want endpoints to read and update user profiles
  So that users can manage their profile information

  Scenario: AC-010-1 - GET endpoint returns profile for valid user
    Given a user with id 1 exists in the database
    When I send GET /api/users/1/profile
    Then the response status is 200
    And the response contains display_name, bio, and avatar_url

  Scenario: AC-010-2 - GET endpoint returns 404 for unknown user
    Given no user with id 999 exists in the database
    When I send GET /api/users/999/profile
    Then the response status is 404
    And the response body contains "User not found"

  Scenario: AC-010-3 - PUT endpoint updates profile
    Given a user with id 1 exists in the database
    When I send PUT /api/users/1/profile with {"display_name": "New Name", "bio": "Updated bio"}
    Then the response status is 200
    And the response contains the updated display_name and bio

  Scenario: AC-010-4 - Pydantic validation rejects invalid input
    Given a user with id 1 exists in the database
    When I send PUT /api/users/1/profile with an invalid payload
    Then the response status is 422
    And the response contains validation error details
