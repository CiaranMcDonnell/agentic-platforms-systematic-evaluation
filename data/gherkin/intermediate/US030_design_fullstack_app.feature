Feature: US-030 Design Full-Stack Issue Tracker Application

  Scenario: AC-030-1 - Architecture document is complete
    Given the file docs/design/architecture.md
    When I inspect its contents
    Then it contains a system overview section
    And it contains technology stack choices with justifications
    And it contains deployment topology
    And it contains architectural decisions and trade-offs

  Scenario: AC-030-2 - API specification covers all resources
    Given the file docs/design/api_spec.md
    When I inspect its contents
    Then it defines endpoints for Issues, Projects, Users, and Comments
    And each endpoint specifies HTTP method, path, and request/response schemas
    And it describes the authentication strategy
    And it describes pagination and error handling conventions

  Scenario: AC-030-3 - Database schema is well-defined
    Given the file docs/design/database_schema.md
    When I inspect its contents
    Then it defines tables for users, projects, issues, comments, labels, issue_labels, and activity_log
    And each table has columns with types and constraints
    And foreign key relationships are documented

  Scenario: AC-030-4 - Component breakdown covers frontend and backend
    Given the file docs/design/components.md
    When I inspect its contents
    Then it lists backend service modules
    And it lists frontend page components with routing
    And it describes background jobs
    And it identifies integration points between frontend and backend

  Scenario: AC-030-5 - Design addresses all functional requirements
    Given all design documents
    When I review them holistically
    Then the design supports multiple projects with issues
    And issues have status, priority, assignee, labels, and comments
    And user roles (admin, project_manager, developer, viewer) are defined
    And activity logging is designed
    And full-text search is addressed
    And real-time WebSocket updates are planned

  Scenario: AC-030-6 - Component diagram is valid PlantUML
    Given the file docs/design/diagrams/component_diagram.puml
    When I parse it as PlantUML
    Then it starts with @startuml and ends with @enduml
    And it shows Frontend, API Gateway, Backend Services, Database, Cache, and WebSocket Server
    And it shows interfaces and dependencies between components

  Scenario: AC-030-7 - Class diagram is valid PlantUML
    Given the file docs/design/diagrams/class_diagram.puml
    When I parse it as PlantUML
    Then it starts with @startuml and ends with @enduml
    And it defines entities for User, Project, Issue, Comment, Label, and ActivityLog
    And each entity has attributes with types
    And relationships show cardinality

  Scenario: AC-030-8 - Sequence diagram is valid PlantUML
    Given the file docs/design/diagrams/sequence_create_issue.puml
    When I parse it as PlantUML
    Then it starts with @startuml and ends with @enduml
    And it shows Client, API, Auth Middleware, IssueService, Database, ActivityLog, and WebSocket participants
    And it shows the complete request-response flow for creating an issue

  Scenario: AC-030-9 - ER diagram is valid PlantUML
    Given the file docs/design/diagrams/er_diagram.puml
    When I parse it as PlantUML
    Then it starts with @startuml and ends with @enduml
    And it defines entity blocks for all database tables
    And it shows primary keys, foreign keys, and relationships with cardinality
