FROM python:3.12-slim

RUN pip install --no-cache-dir oci

WORKDIR /app
COPY oci_hunter/ /app/oci_hunter/

ENTRYPOINT ["python", "-u", "-m", "oci_hunter"]
