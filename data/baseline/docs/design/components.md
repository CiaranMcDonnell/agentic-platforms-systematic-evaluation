# Component Breakdown

## Backend Service Modules
- **Auth Module**: Handles user authentication and authorization using JWT.
- **Issues Module**: Manages issue creation, updates, deletion, and retrieval.
- **Projects Module**: Manages project creation, updates, deletion, and retrieval.
- **Comments Module**: Manages comments on issues.
- **Notifications Module**: Handles real-time notifications and email alerts.

## Frontend Page Components and Routing
- **Login Page**: User authentication interface.
- **Dashboard**: Overview of projects and issues.
- **Project Page**: Detailed view of a single project and its issues.
- **Issue Page**: Detailed view of a single issue, including comments and activity log.
- **User Management Page**: Admin interface for managing users.

## Shared Types/Interfaces
- **User**: Interface defining user properties like `id`, `username`, `email`, `role`.
- **Project**: Interface defining project properties like `id`, `name`, `description`.
- **Issue**: Interface defining issue properties like `id`, `title`, `status`, `priority`.
- **Comment**: Interface defining comment properties like `id`, `content`, `author`.

## Background Jobs
- **Email Notifications**: Sends email alerts for issue updates and comments.
- **Activity Digests**: Compiles and sends daily/weekly activity summaries to users.

## Integration Points
- **Frontend to Backend**: REST API calls for data retrieval and manipulation.
- **WebSocket Server**: For real-time updates on issue changes.
- **Database**: Direct interaction through ORM for data persistence.