#!/usr/bin/env bash
set -e

# Build the IR code database if it doesn't exist yet
if [ ! -f /data/irdb.sqlite3 ]; then
    echo "Building IR code database from Flipper-IRDB..."
    python3 /app/scripts/build_database.py /data/Flipper-IRDB /data/irdb.sqlite3
fi

echo "Starting IR Remote Wizard..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8080 --app-dir /app
