Feature: Adapter Smoke Test
  As a framework maintainer
  I want a minimal end-to-end task
  So that I can verify a new adapter completes the pipeline without burning tokens

  Scenario: AC-000-1 - hello.py exists with a hello() function
    Given the workspace root does not initially contain hello.py
    When the agent completes the task
    Then hello.py exists at the workspace root
    And hello.py defines a function named hello

  Scenario: AC-000-2 - hello() returns the string "Hello, world!"
    Given hello.py has been created
    When I import hello and call hello()
    Then the return value equals "Hello, world!"
