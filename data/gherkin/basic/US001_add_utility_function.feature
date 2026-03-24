Feature: Email Validation Utility Function
  As a developer
  I want a validate_email utility function
  So that I can validate email addresses consistently across the project

  Scenario: AC-001-1 - Function exists with correct signature and type hints
    Given the file utils/validation.py exists
    When I inspect the validate_email function
    Then it accepts a single str parameter
    And it returns a bool
    And it has type hints on the parameter and return value

  Scenario: AC-001-2 - Valid emails return True
    Given the validate_email function is available
    When I call validate_email with "user@example.com"
    Then the result is True
    When I call validate_email with "user.name+tag@domain.co.uk"
    Then the result is True
    When I call validate_email with "user_name@sub.domain.org"
    Then the result is True

  Scenario: AC-001-3 - Invalid emails return False
    Given the validate_email function is available
    When I call validate_email with "not-an-email"
    Then the result is False
    When I call validate_email with "@missing-local.com"
    Then the result is False
    When I call validate_email with "user@"
    Then the result is False
    When I call validate_email with "user@.com"
    Then the result is False
    When I call validate_email with "user@domain"
    Then the result is False

  Scenario: AC-001-4 - Edge cases handled gracefully
    Given the validate_email function is available
    When I call validate_email with an empty string
    Then the result is False
    When I call validate_email with None
    Then the result is False
    When I call validate_email with whitespace-only input
    Then the result is False
    When I call validate_email with a non-string type
    Then the result is False
