# Database Schema

## Entity-Relationship Description
The database schema consists of several tables to manage users, projects, issues, comments, labels, and activity logs. Relationships are established using foreign keys to maintain data integrity.

## Table Definitions

### Users
- **Columns**:
  - `id`: UUID, Primary Key
  - `username`: VARCHAR(255), Unique
  - `email`: VARCHAR(255), Unique
  - `password_hash`: VARCHAR(255)
  - `role`: ENUM('admin', 'project_manager', 'developer', 'viewer')

### Projects
- **Columns**:
  - `id`: UUID, Primary Key
  - `name`: VARCHAR(255), Unique
  - `description`: TEXT
  - `owner_id`: UUID, Foreign Key to Users(id)

### Issues
- **Columns**:
  - `id`: UUID, Primary Key
  - `title`: VARCHAR(255)
  - `description`: TEXT
  - `status`: ENUM('open', 'in_progress', 'resolved', 'closed')
  - `priority`: ENUM('low', 'medium', 'high', 'critical')
  - `assignee_id`: UUID, Foreign Key to Users(id)
  - `project_id`: UUID, Foreign Key to Projects(id)

### Comments
- **Columns**:
  - `id`: UUID, Primary Key
  - `content`: TEXT
  - `author_id`: UUID, Foreign Key to Users(id)
  - `issue_id`: UUID, Foreign Key to Issues(id)

### Labels
- **Columns**:
  - `id`: UUID, Primary Key
  - `name`: VARCHAR(255), Unique

### Issue_Labels
- **Columns**:
  - `issue_id`: UUID, Foreign Key to Issues(id)
  - `label_id`: UUID, Foreign Key to Labels(id)

### Activity_Log
- **Columns**:
  - `id`: UUID, Primary Key
  - `issue_id`: UUID, Foreign Key to Issues(id)
  - `action`: VARCHAR(255)
  - `timestamp`: TIMESTAMP
  - `user_id`: UUID, Foreign Key to Users(id)

## Relationships and Foreign Keys
- Users to Projects: One-to-Many
- Users to Issues: One-to-Many
- Projects to Issues: One-to-Many
- Issues to Comments: One-to-Many
- Issues to Labels: Many-to-Many

## Migration Strategy
Use a tool like Alembic for managing database migrations, ensuring that schema changes are versioned and can be applied consistently across environments.