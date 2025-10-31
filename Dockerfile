# Use official lightweight Python image
FROM python:3.12-alpine

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies at build time
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the watcher script
COPY watcher.py .

# Default command
CMD ["python", "watcher.py"]
