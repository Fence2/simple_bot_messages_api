# Простое REST API для обработки сообщений от бота

## Запуск

### Локально

Из корня проекта:
```bash
docker compose up --build
```

- API: http://localhost:8000
- Проверка успешного подключения к БД: http://localhost:8000/health
- REST API документация: http://localhost:8000/docs
- PostgreSQL с хоста: `localhost:5432`


Остановка: `docker compose down`.  
Логи пишутся в `./logs/ГГГГ/ММ/ГГГГ-ММ-ДД.log` на хосте и остаются после остановки.
