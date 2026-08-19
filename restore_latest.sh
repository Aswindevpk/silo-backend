#!/bin/bash
set -e

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAINTENANCE_FLAG="/var/www/html/silo-maintenance/.silo_maintenance"

# Load environment variables
if [ -f "$APP_DIR/.env.prod" ]; then
    set -a
    source "$APP_DIR/.env.prod"
    set +a
elif [ -f "$APP_DIR/.env" ]; then
    set -a
    source "$APP_DIR/.env"
    set +a
else
    echo "❌ Error: Could not find .env.prod or .env file in $APP_DIR"
    exit 1
fi

DB_USER="${DB_USER:-silo_user}"
DB_NAME="${DB_NAME:-silo}"

# Ensure we clean up maintenance mode if the script fails midway
cleanup() {
    echo "⚠️  Restore script exited unexpectedly! Lifting maintenance mode..."
    sudo rm -f $MAINTENANCE_FLAG
}
trap cleanup ERR

echo "🚨 Starting Automated Disaster Recovery..."
cd "$APP_DIR"

echo "🔒 1. Enabling Host Nginx Emergency Maintenance Mode..."
sudo touch $MAINTENANCE_FLAG || echo "⚠️ Could not touch maintenance flag, skipping..."

echo "☁️  2. Fetching the latest backup from Cloudflare R2..."
LATEST_DUMP=$(docker compose  exec -T backup-sidecar sh -c "aws s3 ls s3://\${BACKUP_S3_BUCKET}/backup/ --endpoint-url \${AWS_S3_ENDPOINT_URL} | sort | tail -n 1 | awk '{print \$4}'")
echo "   Found latest backup: $LATEST_DUMP"
docker compose  exec -T backup-sidecar sh -c "aws s3 cp s3://\${BACKUP_S3_BUCKET}/backup/$LATEST_DUMP /tmp/latest_backup.dump --endpoint-url \${AWS_S3_ENDPOINT_URL}"

# Copy the dump from the sidecar to the primary db container
docker cp $(docker compose  ps -q backup-sidecar):/tmp/latest_backup.dump /tmp/latest_backup.dump
docker cp /tmp/latest_backup.dump $(docker compose  ps -q db):/tmp/latest_backup.dump

echo "🛡️  3. Quarantining the active database (Zero-Overwrite Rule)..."
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
docker compose  exec -T db psql -U "$DB_USER" -d postgres -c "ALTER DATABASE \"$DB_NAME\" RENAME TO \"${DB_NAME}_corrupted_$TIMESTAMP\";" || echo "⚠️ Could not rename active DB. Continuing..."

echo "🏗️  4. Creating target recovery database..."
docker compose  exec -T db createdb -U "$DB_USER" "${DB_NAME}_recovery"

echo "📥 5. Restoring database schema and data..."
docker compose  exec -T db pg_restore -U "$DB_USER" -d "${DB_NAME}_recovery" --clean --if-exists --no-owner --no-privileges /tmp/latest_backup.dump

echo "🔎 6. Verifying table integrity..."
docker compose  exec -T db psql -U "$DB_USER" -d "${DB_NAME}_recovery" -c "\dt"

echo "🔄 7. Cutting over to restored database..."
docker compose  exec -T db psql -U "$DB_USER" -d postgres -c "ALTER DATABASE \"${DB_NAME}_recovery\" RENAME TO \"$DB_NAME\";"

echo "🔓 8. Disabling Maintenance Mode..."
sudo rm -f $MAINTENANCE_FLAG || echo "⚠️ Could not remove maintenance flag"
trap - ERR

echo "✅ Disaster Recovery Completed Successfully!"
