FROM python:3.12-slim

# Устанавливаем зависимости для компиляции
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libc-dev \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем Poetry
ENV POETRY_VERSION=1.8.3
RUN pip install --no-cache-dir poetry==$POETRY_VERSION

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы Poetry
COPY pyproject.toml poetry.lock ./

# Устанавливаем зависимости с помощью Poetry
RUN poetry config virtualenvs.create false \
    && poetry install --no-root --no-dev --no-interaction

# Копируем исходный код и модель
COPY src/ ./src/
COPY src/detector/models/best.pt ./src/detector/models/best.pt

# Устанавливаем переменную окружения для вывода логов
ENV PYTHONUNBUFFERED=1

# Запускаем приложение
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]