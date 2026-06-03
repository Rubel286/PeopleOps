FROM python:3.11-slim

# Install system dependencies and Redis
RUN apt-get update && apt-get install -y --no-install-recommends \
    redis-server \
    build-essential \
    && rm -rf /var/lib/apt-get/lists/*

# Set up working directory
WORKDIR /app

# Copy requirements file first to cache pip dependencies
COPY requirements.txt .

# Install Python requirements
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application files
COPY . .

# Expose the default Hugging Face Spaces port
EXPOSE 7860

# Write a start script to initialize DB seeders, start Redis, and start the app
RUN echo '#!/bin/bash\n\
service redis-server start\n\
# Initialize database seed if running for the first time\n\
flask --app manage.py seed-db || true\n\
# Start Flask App\n\
python run.py' > /app/start.sh && chmod +x /app/start.sh

# Run the start script
CMD ["/app/start.sh"]
