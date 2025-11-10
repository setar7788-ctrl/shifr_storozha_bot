# Используем официальный Python-образ
FROM python:3.11

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем все файлы проекта
COPY . .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем переменные окружения (TOKEN будет добавлен через Fly)
ENV PYTHONUNBUFFERED=1

# Команда запуска бота
CMD ["python", "storoz_bot.py"]
