Feature: Full-Stack Issue Tracker Application Design
  As a development team
  I want a complete software design for an Issue Tracker
  So that we have clear architectural guidance before implementation

  Scenario: AC-030-1 - Architecture document is complete
    Given the file docs/design/architecture.md exists
    When I review the architecture document
    Then it contains a system overview section
    And it specifies the tech stack with justification
    And it describes deployment topology
    And it discusses key trade-offs

  Scenario: AC-030-2 - API specification covers all resources
    Given the file docs/design/api_spec.md exists
    When I review the API specification
    Then it covers Issues, Projects, Users, and Comments resources
    And each resource has endpoints with HTTP methods
    And request and response schemas are defined
    And authentication requirements are specified
    And error responses are documented

  Scenario: AC-030-3 - Database schema defines all tables
    Given the file docs/design/database_schema.md exists
    When I review the database schema
    Then it defines tables for users, projects, issues, comments, and activity_log
    And each table has columns with types and constraints
    And primary and foreign keys are specified
    And relationships and cardinality are documented

  Scenario: AC-030-4 - Component breakdown covers all layers
    Given the file docs/design/components.md exists
    When I review the component breakdown
    Then it covers backend modules
    And it covers frontend pages and components
    And it covers background jobs
    And it covers external integration points

  Scenario: AC-030-5 - Design addresses all functional requirements
    Given I review all design documents holistically
    When I check for completeness
    Then user roles are addressed
    And the activity log is designed
    And search and filtering are covered
    And real-time notifications are designed

  Scenario: AC-030-6 - Component diagram is valid Mermaid
    Given the file docs/design/diagrams/component_diagram.mermaid exists
    When I review the component diagram
    Then it is syntactically valid Mermaid
    And it shows system components with interfaces and dependencies

  Scenario: AC-030-7 - Class diagram is valid Mermaid
    Given the file docs/design/diagrams/class_diagram.mermaid exists
    When I review the class diagram
    Then it is syntactically valid Mermaid
    And it shows all domain entities with attributes, types, and relationships

  Scenario: AC-030-8 - Sequence diagram is valid Mermaid
    Given the file docs/design/diagrams/sequence_create_issue.mermaid exists
    When I review the sequence diagram
    Then it is syntactically valid Mermaid
    And it shows the create-issue flow through all layers

  Scenario: AC-030-9 - ER diagram is valid Mermaid
    Given the file docs/design/diagrams/er_diagram.mermaid exists
    When I review the ER diagram
    Then it is syntactically valid Mermaid
    And it shows all tables with columns, keys, and cardinality
