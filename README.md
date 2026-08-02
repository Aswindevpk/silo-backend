# Silo Backend

This is the backend service for Silo, built with Django, PostgreSQL, Redis, and Celery.

## Local Development (Docker Compose)

For local development, we use Docker Compose to run the entire backend stack (Django, PostgreSQL, Redis, and Celery) with hot-reloading enabled.

### Prerequisites
- Docker & Docker Compose installed on your system.

### 1. Environment Setup
Create a `.env` file from the example if you haven't already:
```bash
cp .env.example .env
```
Ensure your `.env` contains the correct database and redis settings:
```env
DB_NAME=silo
DB_USER=silo_user
DB_PASSWORD=silo_password
DB_HOST=db
REDIS_URL=redis://redis:6379/0
```

### 2. Start the Application
To build and start all containers in the background, run:
```bash
docker compose up -d --build
```

### 3. Run Migrations
Since your database runs inside Docker, you must apply migrations to the container's database:
```bash
docker compose exec web uv run python manage.py migrate
```

### 4. Default Admin Account
A default admin account has been created for local development. You can log into the Django Admin dashboard at `http://localhost:8000/admin/` with these credentials:

- **Email:** `admin@silo.com`
- **Username:** `admin`
- **Password:** `password`

*(If you ever wipe your database and need to recreate this user, you can run: `docker compose exec web uv run python manage.py createsuperuser`)*

## Interacting with the Containers

- **View Logs:** To see real-time logs for a specific service (e.g. `web` or `celery`), run:
  ```bash
  docker compose logs -f web
  ```
- **Run Django Management Commands:**
  ```bash
  docker compose exec web uv run python manage.py <command>
  ```
- **Stop Containers:** (Preserves database data)
  ```bash
  docker compose down
  ```
- **Wipe Database:** (Deletes containers AND the database volume)
  ```bash
  docker compose down -v
  ```