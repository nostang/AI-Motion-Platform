FROM python:3.13-slim

WORKDIR /app

COPY requirements.runtime.txt .

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.runtime.txt \
    && pip uninstall -y opencv-contrib-python opencv-python \
    && pip install --no-cache-dir --force-reinstall opencv-contrib-python-headless==5.0.0.93

COPY . .

EXPOSE 8080

CMD ["uvicorn", "api_main:app", "--host", "0.0.0.0", "--port", "8080"]
