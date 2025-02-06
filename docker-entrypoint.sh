#!/bin/bash

set -e

# Function to check if Elasticsearch is ready
check_es() {
    echo "Checking Elasticsearch connection..."
    health_status=$(curl -s -u elastic:${ELASTIC_PASSWORD} "http://elasticsearch:9200/_cluster/health" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    echo "Elasticsearch health status: ${health_status:-unknown}"
    if [ "${health_status}" = "yellow" ] || [ "${health_status}" = "green" ]; then
        return 0
    fi
    return 1
}

# Wait for Elasticsearch to be ready
echo "Waiting for Elasticsearch to be ready..."
retries=0
until check_es; do
    retries=$((retries + 1))
    if [ $retries -gt 30 ]; then
        echo "Error: Elasticsearch did not become ready in time"
        exit 1
    fi
    echo "Elasticsearch is not ready - sleeping 5s (attempt $retries/30)"
    sleep 5
done
echo "Elasticsearch is ready!"

# Run the main application
echo "Starting email-rag application..."
python main.py embed-emails && streamlit run pipeline/chat/app.py --server.address=0.0.0.0
