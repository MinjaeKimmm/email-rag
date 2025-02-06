FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt setup.py ./

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install -e .

COPY . .

RUN mkdir -p /app/data

# Expose Streamlit port
EXPOSE 8501

# Start command with embedding check and healthcheck setup
COPY docker-entrypoint.sh /
RUN chmod +x /docker-entrypoint.sh
CMD ["/docker-entrypoint.sh"]
