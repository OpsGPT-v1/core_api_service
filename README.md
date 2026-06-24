# OpsGPT Core API Service

The **Core API Service** serves as the central system of record (SoR) and backend engine for the OpsGPT platform. It acts as the primary interface to the PostgreSQL database, managing users, roles, projects, monitoring sources, incidents, timeline events, knowledge base entries, and audit logging.

---

## Technical Stack & Architecture

*   **Runtime**: Python 3.11+
*   **Web Framework**: FastAPI (Uvicorn server)
*   **ORM**: SQLAlchemy 2.0 (declarative mappings)
*   **DB Migration & Driver**: PostgreSQL / `psycopg2`
*   **Authentication**: JWT-based stateless tokens (HS256)

---

## Database Models & Entity Relations

All data tables share the unified Postgres database instance (`opsgpt_db`). The database schema consists of the following key tables:

```mermaid
erDiagram
    USERS {
        int id PK
        string name
        string email UK
        string password_hash
        string role
        boolean is_active
        datetime created_at
        datetime updated_at
    }
    PROJECTS {
        int id PK
        string project_id UK
        string name
        string description
        string environment
        string owner_team
        boolean is_active
        int created_by FK
        datetime created_at
    }
    PROJECT_MEMBERSHIPS {
        int id PK
        string project_id FK
        int user_id FK
        datetime created_at
    }
    MONITORING_SOURCES {
        int id PK
        string source_id UK
        string project_id FK
        string source_type
        string source_name
        string prometheus_url
        string alertmanager_url
        string dashboard_url
        string description
        string webhook_token UK
        string webhook_path
        boolean is_active
        int created_by FK
        datetime created_at
    }
    INCIDENTS {
        int id PK
        string incident_id UK
        string project_id FK
        string title
        string service_name
        string severity
        string status
        string ai_summary
        string root_cause
        jsonb supporting_evidence
        float confidence_score
        jsonb recommended_fix
        jsonb related_alert_ids
        string source_type
        string namespace
        string cluster
        datetime created_at
        datetime resolved_at
        int resolved_by FK
    }
    INCIDENT_TIMELINE {
        int id PK
        string incident_id FK
        string event_type
        string message
        int created_by FK
        datetime created_at
    }
    RESOLUTION_NOTES {
        int id PK
        string incident_id FK
        string notes
        int created_by FK
        datetime created_at
    }
    AUDIT_LOGS {
        int id PK
        int user_id FK
        string action
        string entity_type
        string entity_id
        jsonb old_value
        jsonb new_value
        datetime created_at
    }
    KNOWLEDGE_BASE {
        int id PK
        string title
        string project_id FK
        string service_name
        string root_cause
        string summary
        jsonb resolution_steps
        string source_incident_id
        datetime created_at
        datetime updated_at
    }

    USERS ||--o{ PROJECTS : "creates"
    USERS ||--o{ PROJECT_MEMBERSHIPS : "assigned_to"
    PROJECTS ||--o{ PROJECT_MEMBERSHIPS : "has_members"
    PROJECTS ||--o{ MONITORING_SOURCES : "has_webhooks"
    PROJECTS ||--o{ INCIDENTS : "triggers"
    INCIDENTS ||--o{ INCIDENT_TIMELINE : "logs"
    INCIDENTS ||--o{ RESOLUTION_NOTES : "has_notes"
    USERS ||--o{ AUDIT_LOGS : "triggers_audit"
```

---

## Role-Based Access Control (RBAC)

The application enforces standard role checks on API endpoints:
*   `admin`: Full platform control. Only administrators can query/search users, modify roles, create projects, and assign project memberships.
*   `senior_engineer`: Can view and update incident statuses, write incident resolution notes, and create knowledge base articles.
*   `engineer`: General team member. Can view assigned projects, view incidents, search and read knowledge base articles.
*   `reader`: Read-only access to assigned projects and incidents.

---

## API Endpoints Reference

### 1. Authentication Paths (`/api/core/auth`)

| Method | Path | Auth | Roles | Description |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/auth/login` | None | Public | Validates email & password, returns JWT token + user details. |
| `GET` | `/auth/me` | JWT | All | Returns currently authenticated user details. |
| `POST` | `/auth/logout` | None | Public | Instructs client to clear cached credentials. |

### 2. User Management Paths (`/api/core/users`)

| Method | Path | Auth | Roles | Description |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/users/me` | JWT | All | Same as `/auth/me`. |
| `GET` | `/users` | JWT | `admin` | Lists all registered users ordered alphabetically. |
| `GET` | `/users/search` | JWT | `admin` | Search users by name/email/role (limit 20). Query param: `query`. |
| `POST` | `/users` | JWT | `admin` | Registers a new user. Emits an audit log. |
| `PATCH` | `/users/{user_id}/role` | JWT | `admin` | Updates a target user's role. Emits an audit log. |

### 3. Project & Monitoring Source Paths (`/api/core/projects`)

*Admins can read all projects. Non-admins are limited to projects they are assigned to via `project_memberships`.*

| Method | Path | Auth | Roles | Description |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/projects` | JWT | All | Lists active projects. Filtered by membership for non-admins. |
| `POST` | `/projects` | JWT | `admin` | Creates a project. Automatically joins creator to the project. |
| `GET` | `/projects/{project_id}` | JWT | All | Retrieves details for a specific project. |
| `PATCH` | `/projects/{project_id}` | JWT | `admin` | Updates project details (name, team, env, status). |
| `DELETE` | `/projects/{project_id}` | JWT | `admin` | Safe soft-deletes a project (sets `is_active = false`). |
| `GET` | `/projects/{project_id}/members` | JWT | All | Lists users assigned to a project. |
| `POST` | `/projects/{project_id}/members` | JWT | `admin` | Assigns a user to a project. |
| `DELETE` | `/projects/{project_id}/members/{user_id}`| JWT | `admin` | Removes a user from a project. |
| `GET` | `/projects/{project_id}/monitoring-sources` | JWT | All | Lists Prometheus webhook configurations. |
| `POST` | `/projects/{project_id}/monitoring-sources` | JWT | `admin` | Registers a monitoring source. Generates a secure random webhook token. |
| `GET` | `/projects/{project_id}/monitoring-sources/{source_id}` | JWT | All | Retrieves metadata for a specific monitoring source. |
| `PATCH` | `/projects/{project_id}/monitoring-sources/{source_id}` | JWT | `admin` | Updates monitoring source metadata. |
| `DELETE` | `/projects/{project_id}/monitoring-sources/{source_id}`| JWT | `admin` | Deactivates a monitoring source (sets `is_active = false`). |
| `GET` | `/projects/{project_id}/dashboard/summary` | JWT | All | Returns count of total, open, critical, and resolved incidents. |
| `GET` | `/projects/{project_id}/incidents` | JWT | All | Lists incidents created for this project (limit 200). |
| `GET` | `/projects/{project_id}/incidents/{incident_id}` | JWT | All | Retrieves a single incident record within the project. |

### 4. Incident Operational Paths (`/api/core/incidents`)

| Method | Path | Auth | Roles | Description |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/incidents` | JWT | All | Lists all visible incidents (admins see all; others see members-only). |
| `GET` | `/incidents/{incident_id}` | JWT | All | Retrieves details for a single incident. |
| `PATCH` | `/incidents/{incident_id}/status` | JWT | `senior_engineer`, `admin` | Changes incident status (e.g. `resolved`). dispatches event to notification service. |
| `POST` | `/incidents/{incident_id}/resolution-notes`| JWT | `senior_engineer`, `admin` | Adds a resolution note. Appends timeline event and routes notification. |
| `GET` | `/incidents/{incident_id}/timeline` | JWT | All | Returns audit/timeline event stream for this incident. |
| `GET` | `/incidents/{incident_id}/similar` | JWT | All | Returns historical incidents sharing the same `service_name` (limit 10). |

### 5. Knowledge Base Paths (`/api/core/knowledge-base`)

| Method | Path | Auth | Roles | Description |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/knowledge-base` | JWT | All | Lists KB articles. Filters by project memberships for non-admins. |
| `GET` | `/knowledge-base/{kb_id}` | JWT | All | Retrieves details of a specific KB entry. |
| `POST` | `/knowledge-base` | JWT | `senior_engineer`, `admin` | Commits a new KB entry. Logs audit trace. |

### 6. Platform Audit Trails (`/api/core/audit-logs`)

| Method | Path | Auth | Roles | Description |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/audit-logs` | JWT | `admin` | Retrieves the global event audit history logs (limit 200). |

---

## Internal Microservices APIs (`/api/core/internal`)

FastAPI routes prefixed with `/internal` are reserved for communication between microservices (e.g. alerts ingestion writing, correlation creating, or validation queries). 
*   **Security Header**: Must supply header `X-Internal-API-Key: <INTERNAL_API_KEY>` on every request.

| Method | Path | Description |
| :--- | :--- | :--- |
| `POST` | `/internal/incidents` | Registers or retrieves an incident. Logs creation event to timeline, and invokes Slack webhook dispatcher. |
| `PATCH` | `/internal/incidents/{incident_id}/analysis` | Updates AI fields (`root_cause`, `ai_summary`, `confidence_score`, `recommended_fix`) once Azure AI Foundry completes. Logs timeline event and dispatches update notification. |
| `POST` | `/internal/incidents/{incident_id}/timeline` | Appends a timeline event record directly. |
| `GET` | `/internal/projects/{project_id}/monitoring-sources/validate` | Validates that a project has a matching webhook token. Query param: `token`. |

---

## Key Configurations & Environment Variables

Create a local `.env` file in the service root using the settings below:

| Environment Variable | Default Value | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `postgresql://opsgpt_user:opsgpt_password@opsgpt-db:5432/opsgpt_db` | Connection string to PostgreSQL database. |
| `JWT_SECRET_KEY` | `change-me` | Symmetric signing secret for JWT access tokens. |
| `JWT_ALGORITHM` | `HS256` | Hash algorithm for tokens. |
| `JWT_EXPIRE_MINUTES` | `60` | Token expiration lifespan. |
| `INTERNAL_API_KEY` | `change-me-internal-key` | Secret key used for authenticating internal requests from other microservices. |
| `NOTIFICATION_SERVICE_URL` | `http://notification-service:8004` | Destination address for dispatching notification events. |
| `ENABLE_NOTIFICATIONS` | `True` | Flag to enable or disable webhook notifications. |
| `CORS_ORIGINS` | `*` | Allowed CORS origins list. |
| `DB_INIT_MAX_ATTEMPTS` | `30` | Number of times to check database connection on startup before failing. |
| `DB_INIT_DELAY_SECONDS` | `2` | Delay between database connection checks. |
