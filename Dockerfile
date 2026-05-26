# Multi-stage production-grade Dockerfile for Django REST Framework
# ----------------------------------------------------------------------

# Stage 1: Build dependencies
FROM python:3.10-slim AS builder

WORKDIR /app

# Prevent python from writing pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies to the user space
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# Stage 2: Runtime runner image
FROM python:3.10-slim AS runner

WORKDIR /app

# Prevent python from writing pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBUG=False
ENV PORT=8000

# Copy installed python dependencies from builder stage
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Install postgres client library runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy backend application files
COPY breathe_esg/ breathe_esg/
COPY breathe_esg_project/ breathe_esg_project/
COPY manage.py .

# Copy sample data parser verification files for quick access/in-app verification
COPY sample_sap_mm.txt .
COPY sample_utility_hh.csv .
COPY sample_navan_travel.csv .

# Expose Django port
EXPOSE 8000

# Run static assets collection for WhiteNoise serving
RUN python manage.py collectstatic --noinput

# Run migrations, seed static sample factors, and serve via Gunicorn
CMD sh -c "python manage.py migrate --noinput && python manage.py seed_sample_data && gunicorn breathe_esg_project.wsgi:application --bind 0.0.0.0:\$PORT"
