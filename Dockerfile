# Imagen Lambda (arm64/Graviton) con Playwright + Chromium para el scraper DIAN.
#
# Estrategia: partir de la imagen oficial de Playwright (trae Chromium + todas
# las libs del SO ya resueltas, que es la parte difícil en Lambda) y añadir el
# Runtime Interface Client (RIC) de AWS Lambda para Python, en vez de partir de
# la imagen Lambda y pelear con las dependencias de Chromium.
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

# Directorio de trabajo del código
WORKDIR /var/task

# Dependencias Python del proyecto + Runtime Interface Client de Lambda
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir awslambdaric

# Los navegadores ya vienen en la imagen de Playwright en /ms-playwright.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Código de la aplicación
COPY dian_bot ./dian_bot
COPY lambda_handler.py .

# Lambda solo permite escribir en /tmp -> estado, histórico y caches de Chromium.
ENV STATE_PATH=/tmp/last_availability.json \
    HISTORY_PATH=/tmp/history.jsonl \
    HEADLESS=true \
    HOME=/tmp \
    XDG_CACHE_HOME=/tmp/.cache \
    XDG_CONFIG_HOME=/tmp/.config \
    FONTCONFIG_PATH=/etc/fonts

# El Runtime Interface Client hace de entrypoint de Lambda.
ENTRYPOINT ["python", "-m", "awslambdaric"]
CMD ["lambda_handler.handler"]
