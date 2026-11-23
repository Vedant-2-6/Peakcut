# PeakCut: Dockerfile optimized for Hugging Face Spaces & Cloud Deployment
FROM python:3.11-slim

# Install system dependencies: ffmpeg, nodejs, git, fonts for video subtitles
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    curl \
    git \
    nodejs \
    npm \
    fonts-noto-core \
    fonts-noto-cjk \
 && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces requires running as non-root user (user: UID 1000)
RUN useradd -m -u 1000 user

WORKDIR /app

# Clone and build YouTube POT provider server
RUN git clone --depth=1 https://github.com/Brainstrain/bgutil-ytdlp-pot-provider.git /app/bgutil-ytdlp-pot-provider \
 && cd /app/bgutil-ytdlp-pot-provider/server \
 && npm install \
 && npm run build

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY studio studio
COPY web web
COPY deploy deploy
COPY entrypoint.sh /app/entrypoint.sh

# Create data directory and assign permissions to user (UID 1000)
RUN mkdir -p /app/data && chown -R user:user /app && chmod +x /app/entrypoint.sh

# Switch to non-root user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PORT=7860 \
    PEAKCUT_PORT=7860 \
    PEAKCUT_HOST=0.0.0.0 \
    PEAKCUT_DATA=/app/data \
    PEAKCUT_TRUST_PROXY=1 \
    PYTHONUNBUFFERED=1

EXPOSE 7860

CMD ["/app/entrypoint.sh"]
