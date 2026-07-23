# DuGS Runner — runs your workflows, headless.
#
# Everything needed ships in the image: the engine, the nodes, the runner.
# Only your workflows are mounted in, so the image never needs rebuilding
# when a workflow changes.
#
#   docker build -t dugs-runner .
#   docker run -d --name dugs -p 5800:5800 -v ./projects:/data/projects dugs-runner
#
# Alpine + pure standard library, so the whole thing is tiny and has nothing
# to install.
FROM python:3.12-alpine

WORKDIR /runner
COPY dugs_runner.py engine.py node_base.py storage.py tabel_store.py ai_helper.py ./
COPY nodes/ ./nodes/

# your workflows live on a volume so they survive restarts and can be swapped
# without touching the image
ENV DUGS_DATA_DIR=/data \
    DUGS_HOST=0.0.0.0 \
    DUGS_PORT=5800 \
    PYTHONUNBUFFERED=1

RUN mkdir -p /data/projects
VOLUME ["/data"]
EXPOSE 5800

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s \
  CMD python3 -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:5800/health',timeout=3)" || exit 1

CMD ["python3", "/runner/dugs_runner.py"]
