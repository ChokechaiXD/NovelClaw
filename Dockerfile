FROM python:3.12-slim AS python-base
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md LICENSE ./
COPY tools/ tools/
RUN pip install --no-cache-dir -e . && pip install --no-cache-dir -e .[test]
FROM node:20-slim AS reader-base
WORKDIR /app/reader
COPY reader/package*.json ./
RUN npm ci --only=production
COPY reader/ .
FROM python:3.12-slim
WORKDIR /app
COPY --from=node:20-slim /usr/local/bin/node /usr/local/bin/
COPY --from=python-base /app /app
COPY --from=python-base /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages/
COPY --from=reader-base /app/reader /app/reader
RUN mkdir -p /app/novels /app/logs
ENV PYTHONUNBUFFERED=1 NOVELCLAW_ROOT=/app/novels PORT=4173 NODE_ENV=production
EXPOSE 4173
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD curl -f http://localhost:4173/api/novels || exit 1
CMD ["node", "reader/server.js"]
