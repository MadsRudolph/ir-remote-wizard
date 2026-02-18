#!/usr/bin/with-contenv bashio
# ==============================================================================
# Initialize the IR code database on first run
# ==============================================================================

if ! bashio::fs.file_exists "/data/irdb.sqlite3"; then
    bashio::log.info "Building IR code database from Flipper-IRDB..."

    if ! bashio::fs.directory_exists "/data/Flipper-IRDB"; then
        bashio::log.info "Cloning Flipper-IRDB repository..."
        git clone --depth 1 https://github.com/Lucaslhm/Flipper-IRDB.git /data/Flipper-IRDB
    fi

    python3 /app/scripts/build_database.py /data/Flipper-IRDB /data/irdb.sqlite3
    bashio::log.info "Database built successfully."
else
    bashio::log.info "IR code database already exists."
fi
