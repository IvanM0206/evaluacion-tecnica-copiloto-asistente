FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN python manage.py collectstatic --noinput

EXPOSE 8000
# migrate y seed son idempotentes, así cada `up` arranca con la base lista.
# Hace falta más de un hilo: las vistas del front llaman a la API en este mismo servidor.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py seed_dataset && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --threads 4 --timeout 60"]
