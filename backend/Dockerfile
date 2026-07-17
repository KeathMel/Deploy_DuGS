FROM python:3.12-slim

WORKDIR /app
COPY . /app

# Pure standard library today — nothing to install. This line is here so
# that if a node ever needs a real dependency (e.g. `requests`), adding it
# to requirements.txt is enough; the Dockerfile doesn't need to change.
RUN if [ -s requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

ENV DUGS_API_HOST=0.0.0.0 \
    DUGS_API_PORT=5800 \
    DUGS_DATA_DIR=/data

# Projects / Tabels / Credentials live here — mount a volume at /data to
# persist them across container restarts/rebuilds.
VOLUME ["/data"]

EXPOSE 5800

CMD ["python3", "api.py"]
