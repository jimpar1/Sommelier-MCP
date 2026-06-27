FROM eclipse-temurin:17-jre AS jre

FROM python:3.12-slim

COPY --from=jre /opt/java/openjdk /opt/java/openjdk
ENV JAVA_HOME=/opt/java/openjdk \
    PATH=/opt/java/openjdk/bin:$PATH

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY data ./data

ENV WINE_DSS_DATA_DIR=/app/data \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000 \
    PYTHONPATH=/app/src

EXPOSE 8000
CMD ["python", "-m", "server"]
