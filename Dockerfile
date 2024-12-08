# Base image
FROM python:3.9-slim

# Set environment variables
ENV ENVIRONMENT=development

# Set working directory
WORKDIR /app

#RUN echo "deb http://deb.debian.org/debian bullseye main" > /etc/apt/sources.list && \
#    echo "deb http://security.debian.org/debian-security bullseye-security main" >> /etc/apt/sources.list && \
#    echo "deb http://deb.debian.org/debian bullseye-updates main" >> /etc/apt/sources.list

# Install required system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxcomposite1 \
    libxrandr2 \
    libxdamage1 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libgtk-3-0 \
    wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy the Python requirements into the container at /app
COPY requirements.txt /app/

# Install Python dependencies
RUN pip3 install --upgrade pip && pip3 install --no-cache-dir -r requirements.txt
#RUN playwright install

# Copy the Flask app and other necessary files into the container
COPY config.py /app/
COPY data_ingestion.py /app/
COPY main.py /app/
COPY templates /app/templates

# Expose port to run flask app
EXPOSE 8000

# Command to run the application
CMD ["python3", "main.py"]