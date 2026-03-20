# Use Python 3.10 slim image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire project
COPY . .

# Create required directories
RUN mkdir -p ml/data ml/saved_models instance

# Generate dataset and train model
RUN python ml/generate_dataset.py && python ml/train_model.py

# Initialize database
RUN python reset_db.py

# Expose port 7860 (Hugging Face default)
EXPOSE 7860

# Set environment variables
ENV PORT=7860
ENV PYTHONPATH=/app/backend

# Start gunicorn
CMD ["gunicorn", "--chdir", "backend", "app:create_app()", "--bind", "0.0.0.0:7860", "--workers", "1", "--timeout", "120"]