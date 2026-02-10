Feature: Add Email Validation Utility Function
  As defined in US-001: Add Email Validation Utility Function

  Scenario: AC-001-1 - Function exists with correct signature and type hints
    Given the file utils/validation.py
    When I inspect the module
    Then a function validate_email(email: str) -> bool exists

  Scenario: AC-001-2 - Valid emails return True
    Given the validate_email function
    When called with "user@example.com"
    Then it returns True

  Scenario: AC-001-3 - Invalid emails return False
    Given the validate_email function
    When called with "not-an-email"
    Then it returns False

  Scenario: AC-001-4 - Edge cases handled gracefully
    Given the validate_email function
    When called with "" or None
    Then it returns False without raising an exception
