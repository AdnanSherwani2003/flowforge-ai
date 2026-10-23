FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt constraints.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip==26.2.2 \
    && python -m pip install --no-cache-dir -r requirements.txt -c constraints.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app
COPY tests ./tests

# Installation tools are unnecessary at runtime; omit their vendored attack surface.
RUN chown -R 10001:10001 /app \
    && python -m pip uninstall -y pip

USER 10001

EXPOSE 8001

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8001"]
