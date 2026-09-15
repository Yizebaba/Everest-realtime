FROM mcr.microsoft.com/playwright/python:v1.62.0-noble
USER root
RUN apt-get update && apt-get install -y --no-install-recommends fonts-noto-cjk && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt pytest
COPY --chown=pwuser:pwuser everest ./everest
COPY --chown=pwuser:pwuser monitor.py worker.py ./
COPY --chown=pwuser:pwuser config ./config
COPY --chown=pwuser:pwuser tests ./tests
COPY --chown=pwuser:pwuser data-sources ./data-sources
RUN mkdir -p /app/data && chown -R pwuser:pwuser /app
ENV PYTHONUNBUFFERED=1 EVEREST_BROWSER_CHANNEL=chromium EVEREST_FONT=/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc EVEREST_NOTIFY_FILE=/run/secrets/notify_config
USER pwuser
ENTRYPOINT ["python", "-B", "monitor.py"]
CMD ["catalog"]
