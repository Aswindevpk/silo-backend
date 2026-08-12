#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

APP_DIR="/var/www/silo"
MAINTENANCE_FLAG="/var/www/html/silo-maintenance/.silo_maintenance"
HEALTH_ENDPOINT="http://127.0.0.1:8000/health/"

# --- Cleanup Trap ---
# Ensures maintenance mode is disabled if the script crashes midway.
cleanup() {
    echo "⚠️  Deployment script exited unexpectedly! Ensuring maintenance mode is lifted..."
    sudo rm -f $MAINTENANCE_FLAG
}
trap cleanup ERR

echo "🚀 Starting Safe Cutover Deployment..."

cd $APP_DIR

echo "🔒 1. Enabling Host Nginx Emergency Maintenance Mode..."
sudo touch $MAINTENANCE_FLAG

echo "📥 2. Pulling new Docker images..."
docker compose pull

echo "⚙️  3. Running Django migrations..."
# Run migrations using the new image, but without bringing the full stack down
docker compose run --rm web python manage.py migrate --noinput

echo "📦 4. Collecting static files..."
docker compose run --rm web python manage.py collectstatic --noinput

echo "🔄 5. Re-creating and starting containers..."
docker compose up -d --force-recreate web celery

echo "🩺 6. Running Health Check Loop..."
MAX_RETRIES=15
RETRY_COUNT=0
HEALTHY=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    HTTP_STATUS=$(curl -o /dev/null -s -w "%{http_code}" -H "Host: silo-api.aswindev.in" -H "X-Forwarded-Proto: https" $HEALTH_ENDPOINT || true)
    HTTP_STATUS=${HTTP_STATUS:-000}
    
    if [ "$HTTP_STATUS" -eq 200 ]; then
        echo "✅ Health check passed! (HTTP 200)"
        HEALTHY=true
        break
    else
        echo "⏳ Waiting for app to become healthy... (Status: $HTTP_STATUS, Attempt: $((RETRY_COUNT + 1))/$MAX_RETRIES)"
        sleep 2
        RETRY_COUNT=$((RETRY_COUNT + 1))
    fi
done

if [ "$HEALTHY" = false ]; then
    echo "❌ Health check failed after $MAX_RETRIES attempts."
    echo "🚨 LEAVING APP IN MAINTENANCE MODE. PLEASE INVESTIGATE."
    exit 1
fi

echo "🔓 7. Disabling Maintenance Mode..."
sudo rm -f $MAINTENANCE_FLAG
trap - ERR # Remove error trap on success

echo "🎉 Deployment completed successfully!"