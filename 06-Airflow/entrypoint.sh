#!/usr/bin/env bash

if [ "$1" = "api-server" ] || [ "$1" = "webserver" ]; then
    echo "Initializing the Airflow database..."
    airflow db migrate

    echo "Creating admin user..."
    airflow users create \
        --username admin \
        --firstname admin \
        --lastname admin \
        --role Admin \
        --email admin@example.com \
        --password admin || echo "Admin user might already exist."
fi

echo "Starting $1..."
exec airflow "$1"
