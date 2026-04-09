FROM python:3.11-slim

WORKDIR /app

# Install prod dependencies only
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copy application code
COPY kalshi_bot/ kalshi_bot/
COPY main.py .

# Health check: verifies required env vars are present
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "from kalshi_bot.config import Config; Config.validate_required()"

# Default to dry-run; override via BOT_MODE env var in ECS task definition
ENV BOT_MODE=dry_run

CMD ["sh", "-c", "python main.py --${BOT_MODE}"]
