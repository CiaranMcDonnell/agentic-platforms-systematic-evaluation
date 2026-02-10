# Prompt

You are a senior software architect. Design a full-stack **Issue Tracker** application.

Produce the following design artifacts by writing them as files:

1. **`docs/design/architecture.md`** — High-level architecture document:
   - System overview and goals
   - Technology stack choices with justification (Python/FastAPI backend, React/Next.js frontend, PostgreSQL database)
   - Deployment topology (single-server Docker Compose)
   - Key architectural decisions and trade-offs

2. **`docs/design/api_spec.md`** — REST API specification:
   - All endpoints grouped by resource (Issues, Projects, Users, Comments)
   - HTTP methods, URL paths, request/response schemas
   - Authentication strategy (JWT)
   - Pagination, filtering, and sorting conventions
   - Error response format

3. **`docs/design/database_schema.md`** — Database design:
   - Entity-relationship description
   - Table definitions with columns, types, constraints, and indexes
   - Tables needed: users, projects, issues, comments, labels, issue_labels, activity_log
   - Relationships and foreign keys
   - Migration strategy

4. **`docs/design/components.md`** — Component breakdown:
   - Backend service modules (auth, issues, projects, comments, notifications)
   - Frontend page components and routing
   - Shared types/interfaces
   - Background jobs (email notifications, activity digests)
   - Integration points between frontend and backend

5. **`docs/design/diagrams/component_diagram.puml`** — PlantUML component diagram:
   - Show all major system components (Frontend, API Gateway, Backend Services, Database, Cache, WebSocket Server)
   - Show interfaces and dependencies between components
   - Use `@startuml` / `@enduml` syntax

6. **`docs/design/diagrams/class_diagram.puml`** — PlantUML class/domain model diagram:
   - Show all domain entities: User, Project, Issue, Comment, Label, ActivityLog
   - Include key attributes and types for each entity
   - Show relationships (one-to-many, many-to-many) with cardinality
   - Use `@startuml` / `@enduml` syntax

7. **`docs/design/diagrams/sequence_create_issue.puml`** — PlantUML sequence diagram for creating an issue:
   - Show the full flow: Client → API → Auth Middleware → IssueService → Database → ActivityLog → WebSocket broadcast
   - Include request/response payloads
   - Use `@startuml` / `@enduml` syntax

8. **`docs/design/diagrams/er_diagram.puml`** — PlantUML entity-relationship diagram:
   - Show all database tables with their columns
   - Show primary keys, foreign keys, and indexes
   - Show all relationships with cardinality
   - Use `@startuml` / `@enduml` syntax with `entity` blocks

Requirements for the design:
- Support multiple projects, each with its own issues
- Issues have: title, description, status (open/in_progress/resolved/closed), priority (low/medium/high/critical), assignee, labels, comments
- User roles: admin, project_manager, developer, viewer
- Activity log tracking all changes to issues
- Full-text search on issue title and description
- Real-time updates via WebSocket for issue changes

# Context

The project baseline has an empty `docs/design/` directory ready for your output.
Create `docs/design/diagrams/` as a subdirectory for the PlantUML files.
You have access to read_file, write_file, list_directory, and execute_shell tools.
Write each design document as a separate markdown file and each diagram as a `.puml` file.
All `.puml` files must use valid PlantUML syntax that renders on plantuml.com or PlantText.
Focus on completeness, clarity, and practical implementability.
