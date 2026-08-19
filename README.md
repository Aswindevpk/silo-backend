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

### 🔍 Viewing Logs
To see real-time logs for specific services, you can use the `logs -f` command:
- **Web App:** `docker compose logs -f web`
- **Celery Worker:** `docker compose logs -f celery`
- **PostgreSQL Database:** `docker compose logs -f db`
- **Redis Cache:** `docker compose logs -f redis`
- **All Services:** `docker compose logs -f`

### 💾 Local Database Backup & Restore
If you need to backup your local database or restore a dump file (like one downloaded from production), you can run these commands against your local database container (`silo_db`):

**Backup Local Database:**
```bash
docker exec silo_db pg_dump -U $DB_USER -Fc $DB_NAME > local_backup.dump
```

**Restore to Local Database:**
Assuming you have a file named `prod_backup.dump` in your current folder:
```bash
# 1. Copy the backup file into your local database container
docker cp prod_backup.dump silo_db:/tmp/prod_backup.dump

# 2. Quarantine your current local database (renames it to ${DB_NAME}_old)
docker exec silo_db psql -U $DB_USER -d postgres -c "ALTER DATABASE $DB_NAME RENAME TO ${DB_NAME}_old_$(date +%s);"

# 3. Create a fresh, empty database
docker exec silo_db createdb -U $DB_USER $DB_NAME

# 4. Restore the data into the fresh database
docker exec silo_db pg_restore -U $DB_USER -d $DB_NAME --clean --if-exists --no-owner --no-privileges /tmp/prod_backup.dump

# 5. Clean up the temporary file
docker exec silo_db rm /tmp/prod_backup.dump
```

### ⚠️ Safe vs. Destructive Commands
Knowing how to restart or stop your app safely is crucial. 

**✅ SAFE COMMANDS (Keeps your database data intact):**
- **Stop all containers:** `docker compose down` (Safely stops the app)
- **Start all containers:** `docker compose up -d` (Resumes where you left off)
- **Restart one service:** `docker compose restart web`
- **Run Django commands:** `docker compose exec web python manage.py <command>`

**❌ DESTRUCTIVE COMMANDS (Deletes data):**
- **Wipe everything (Containers + Database Volumes):** 
  ```bash
  docker compose down -v
  ```
  *⚠️ WARNING: The `-v` flag deletes your named volumes (Postgres and Redis data). ALL your local database data and queued tasks will be permanently lost.*

## Production Operations

### 🌐 Viewing Production Logs
To check the status of your live application:
- **Web App:** `docker compose logs -f web`
- **Backup Sidecar:** `docker compose logs -f backup-sidecar`
- **Celery Worker:** `docker compose logs -f celery`
- **PostgreSQL Database:** `docker compose logs -f db`
- **Redis Cache:** `docker compose logs -f redis`
- **All Services:** `docker compose logs -f`

### 💾 Production Database Backup & Restore

#### ☁️ Automated Cloudflare Backups
In production, your backups are automatically synced to Cloudflare R2 every midnight by the `backup-sidecar`.

**Trigger a Manual Cloudflare Backup:**
```bash
docker compose exec backup-sidecar sh backup.sh
```

**Perform Emergency Disaster Recovery (Restore from Cloudflare R2):**
If the production database crashes, you can run the automated recovery script. This script automatically downloads the latest dump from Cloudflare R2, quarantines the broken database, restores the data, and swaps it out safely.
```bash
chmod +x restore_latest.sh
./restore_latest.sh
```

#### 🛠️ Pure Manual Backup & Restore (No Cloudflare)
If you want to manually create a dump file on the VPS disk or restore a file directly without involving Cloudflare, use these commands against the `db` service:

**Manual Local Backup (on the VPS):**
```bash
docker compose exec db pg_dump -U $DB_USER -Fc $DB_NAME > manual_prod_backup.dump
```

**Manual Local Restore (on the VPS):**
Assuming you have a file named `manual_prod_backup.dump` on the VPS:
```bash
# 1. Copy the backup file into the database container
docker cp ./manual_prod_backup.dump silo_db_prod:/tmp/manual_prod_backup.dump
# verify the file has been copied
docker compose exec db ls -l /tmp

# 2. Quarantine your current database (renames it to ${DB_NAME}_old)
docker compose exec db psql -U $DB_USER -d postgres -c "ALTER DATABASE $DB_NAME RENAME TO ${DB_NAME}_old_$(date +%s);"

# if any ERROR:  database "silo" is being accessed by other users
# 1. create a fresh db
# 2. change the db name in .env
# 3. restart the services


# 3. Create a fresh, empty database
docker compose exec db createdb -U $DB_USER $DB_NAME

# 4. Restore the data into the fresh database
docker compose exec db pg_restore -U $DB_USER -d $DB_NAME --clean --if-exists --no-owner --no-privileges /tmp/manual_prod_backup.dump

# 5. Clean up the temporary file
docker compose exec db rm /tmp/manual_prod_backup.dump
```

### ⚙️ Running Production Django Commands
To run commands like creating an admin user on the live database:
```bash
docker compose exec web python manage.py createsuperuser
```