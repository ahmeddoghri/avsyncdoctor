FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY . .
RUN pip install --no-cache-dir .
EXPOSE 8090
CMD ["avsyncdoctor", "serve", "--host", "0.0.0.0", "--port", "8090"]
