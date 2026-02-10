# REST API Specification

## Authentication
- **Strategy**: JWT (JSON Web Tokens)
- **Endpoints**:
  - `POST /auth/login`: Authenticate user and return JWT
  - `POST /auth/refresh`: Refresh JWT

## Users
- **Endpoints**:
  - `GET /users`: List all users
  - `GET /users/{id}`: Get user by ID
  - `POST /users`: Create a new user
  - `PUT /users/{id}`: Update user by ID
  - `DELETE /users/{id}`: Delete user by ID

## Projects
- **Endpoints**:
  - `GET /projects`: List all projects
  - `GET /projects/{id}`: Get project by ID
  - `POST /projects`: Create a new project
  - `PUT /projects/{id}`: Update project by ID
  - `DELETE /projects/{id}`: Delete project by ID

## Issues
- **Endpoints**:
  - `GET /issues`: List all issues (supports pagination, filtering, sorting)
  - `GET /issues/{id}`: Get issue by ID
  - `POST /issues`: Create a new issue
  - `PUT /issues/{id}`: Update issue by ID
  - `DELETE /issues/{id}`: Delete issue by ID

## Comments
- **Endpoints**:
  - `GET /issues/{issueId}/comments`: List all comments for an issue
  - `POST /issues/{issueId}/comments`: Add a comment to an issue
  - `PUT /comments/{id}`: Update comment by ID
  - `DELETE /comments/{id}`: Delete comment by ID

## Pagination, Filtering, and Sorting
- **Pagination**: Use `page` and `size` query parameters
- **Filtering**: Use query parameters like `status`, `priority`, `assignee`
- **Sorting**: Use `sort` query parameter with field names

## Error Response Format
- **Format**:
  ```json
  {
    "error": "Error message",
    "details": "Additional details"
  }
  ```