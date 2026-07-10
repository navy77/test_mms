FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Create the log directory
RUN mkdir -p /app/log

# Expose the dashboard backend port
EXPOSE 8001

# Run the FastAPI application
CMD ["python", "main.py"]
