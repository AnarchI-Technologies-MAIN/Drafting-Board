# Dockerfile for Anarchi-Technologies Dual-Engine Blog & Revenue Feedback Loop
# Multi-runtime environment (Python 3.12 + Node.js 20) with strict memory bounds

FROM node:20-slim AS base

# Install Python3, pip, and the PostgreSQL client/runtime dependencies required by the workers.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    libpq-dev \
    gcc \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy package descriptors and install npm dependencies.
COPY package.json ./
RUN npm install --omit=dev

# Install the Python PostgreSQL driver and other dependencies for all worker services.
RUN pip3 install --break-system-packages --no-cache-dir \
    psycopg2-binary \
    requests \
    beautifulsoup4 \
    pyyaml

# Copy source code and default data directories.
COPY . .

# Set environment variables for production execution & RAM constraints
ENV NODE_ENV=production
ENV PYTHONUNBUFFERED=1
ENV PORT=3080

# Expose web dashboard port
EXPOSE 3080

# Default command starts the web dashboard and preview server
CMD ["node", "server.js"]
