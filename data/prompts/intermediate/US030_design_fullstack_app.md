# Prompt

Produce a complete software design for a full-stack Issue Tracker application.
Write all design artefacts as files under `docs/design/`.

Required deliverables:

1. **Architecture document** (`docs/design/architecture.md`)
   - System overview, tech stack choices, deployment topology, key trade-offs.

2. **REST API specification** (`docs/design/api_spec.md`)
   - Resources: Issues, Projects, Users, Comments.
   - For each resource: endpoints, HTTP methods, request/response schemas,
     authentication requirements, error responses.

3. **Database schema** (`docs/design/database_schema.md`)
   - All tables with columns, types, constraints, primary/foreign keys.
   - Relationships and cardinality.

4. **Component breakdown** (`docs/design/components.md`)
   - Backend modules, frontend pages/components, background jobs,
     external integration points.

5. **Mermaid diagrams** (all in `docs/design/diagrams/`):
   - `component_diagram.mermaid` — system components, interfaces, dependencies.
   - `class_diagram.mermaid` — domain entities with attributes, types, relationships.
   - `sequence_create_issue.mermaid` — the create-issue flow through all layers.
   - `er_diagram.mermaid` — all tables with columns, keys, cardinality.

All Mermaid files must be syntactically valid and renderable.

# Context

This is a greenfield project. The Issue Tracker should support:
- Multiple projects, each with its own issues.
- User roles: Admin, Project Manager, Developer, Reporter.
- Issue fields: title, description, status (open/in-progress/resolved/closed),
  priority (low/medium/high/critical), assignee, reporter, labels, due date.
- Comments on issues with markdown support.
- Activity log tracking all changes.
- Search and filtering by status, priority, assignee, label, date range.
- Real-time notifications (WebSocket or SSE) for issue updates.

Assume a modern stack: Python (FastAPI) backend, React frontend, PostgreSQL
database, Redis for caching/pub-sub.
