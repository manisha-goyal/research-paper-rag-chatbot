# Base image
FROM python:3.9-slim

# Set environment variables
ENV ENVIRONMENT=development

# Set working directory
WORKDIR /app

# Copy the Python requirements into the container at /app
COPY requirements.txt /app/

# Install Python dependencies
RUN pip3 install --upgrade pip && pip3 install --no-cache-dir -r requirements.txt

# Copy the Flask app and other necessary files into the container
COPY config.py /app/
COPY data_ingestion.py /app/
COPY main.py /app/
COPY templates /app/templates

# Expose port to run flask app
EXPOSE 8080

# Command to run the application
CMD ["python3", "main.py"]