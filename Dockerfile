FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy requirements first
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install system dependencies
RUN apt-get update && \
    apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    poppler-utils && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy app code
COPY . .

# Expose port
EXPOSE 5000

# Run Flask app
CMD ["python", "app.py"]