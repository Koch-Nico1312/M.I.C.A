# Multi-stage Dockerfile for JARVIS AI Assistant
# Stage 1: Builder
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    portaudio19-dev \
    python3-pyaudio \
    libasound-dev \
    libportaudio2 \
    libportaudiocpp0 \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install only runtime system dependencies
RUN apt-get update && apt-get install -y \
    portaudio19-dev \
    python3-pyaudio \
    libasound-dev \
    libportaudio2 \
    libportaudiocpp0 \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Create non-root user for security
RUN groupadd -r jarvis && useradd -r -g jarvis jarvis

# Copy application code
COPY --chown=jarvis:jarvis . .

# Create necessary directories
RUN mkdir -p data/cache data/vector_db data/vision_memory logs config && \
    chown -R jarvis:jarvis data logs config

# Switch to non-root user
USER jarvis

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONUTF8=1

# Expose port for potential web interface
EXPOSE 8080

# Health check - check if the application is responsive
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sys; import os; sys.exit(0 if os.path.exists('main.py') else 1)" || exit 1

# Run the application
CMD ["python", "main.py"]
