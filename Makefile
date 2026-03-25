# --env-file: подстановка ${DB_*} в docker-compose.yml берётся из корневого .env
# (иначе POSTGRES_* могут остаться дефолтными, а бот подключается с DB_USER из env_file).
COMPOSE = docker compose --env-file .env -f deploy/docker-compose.yml

.PHONY: build up down down-v logs logs-tail clean-logs db-shell migrate revision restart

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

down-v:
	$(COMPOSE) down -v

restart:
	$(COMPOSE) restart bot

logs:
	$(COMPOSE) logs -f --tail=200 bot

# Последние строки без follow (удобно, если «логов нет»)
logs-tail:
	$(COMPOSE) logs --tail=200 bot

# Обнуляет json-логи контейнеров проекта (файлы на хосте). При отказе в доступе — sudo.
clean-logs:
	@for c in $$($(COMPOSE) ps -aq); do \
		p=$$(docker inspect --format='{{.LogPath}}' $$c 2>/dev/null); \
		if [ -n "$$p" ] && [ -f "$$p" ]; then \
			if truncate -s 0 "$$p" 2>/dev/null; then echo "cleared $$p"; \
			else echo "skip (no permission): $$p — sudo truncate -s 0 \"$$p\""; fi; \
		fi; \
	done

# Интерактивный psql (учётные данные из env контейнера Postgres)
db-shell:
	$(COMPOSE) exec db sh -c 'exec psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

migrate:
	$(COMPOSE) exec bot alembic upgrade head

revision:
	$(COMPOSE) exec bot alembic revision --autogenerate -m "$(m)"
