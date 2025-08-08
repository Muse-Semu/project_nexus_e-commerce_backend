FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Collect static files (for production)
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# Use Gunicorn for production
CMD ["sh", "-c", "python manage.py makemigrations && python manage.py migrate && python manage.py createsuperuser --noinput --email admin@example.com && gunicorn ecommerce_backend.wsgi:application --bind 0.0.0.0:8000"]