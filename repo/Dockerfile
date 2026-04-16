FROM python:3.11-slim AS build
WORKDIR /app

# Install SQLCipher system library for production DB encryption
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsqlcipher-dev gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir pysqlcipher3==1.2.1

FROM python:3.11-slim
WORKDIR /app

# Runtime SQLCipher library
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsqlcipher0 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build /usr/local/bin /usr/local/bin
COPY . .
RUN mkdir -p instance uploads
EXPOSE 5000
ENTRYPOINT ["python", "run.py"]
