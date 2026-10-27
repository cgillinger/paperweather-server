FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Europe/Stockholm

# Non-root user; /data holds cache and logs (mounted as a volume in compose.yaml)
RUN echo 'weather:x:1000:' >> /etc/group \
    && echo 'weather:x:1000:1000::/app:/usr/sbin/nologin' >> /etc/passwd \
    && mkdir -p /app /data/cache /data/logs \
    && ln -s /data/cache /app/cache \
    && ln -s /data/logs /app/logs \
    && chown -R weather:weather /app /data

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=weather:weather main_web.py ./
COPY --chown=weather:weather modules ./modules
COPY --chown=weather:weather templates ./templates
COPY --chown=weather:weather fonts ./fonts
COPY --chown=weather:weather icons ./icons

USER weather
VOLUME /data
EXPOSE 8037

HEALTHCHECK --interval=60s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8037/weather.png', timeout=8)" || exit 1

# config.json is mounted read-only at /app/config.json
CMD ["python", "main_web.py"]
