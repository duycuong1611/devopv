.PHONY: up down build logs ps test clean

up:
	docker compose up --build

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f --tail=150

ps:
	docker compose ps

test:
	docker compose run --rm api pytest -q

clean:
	docker compose down -v --remove-orphans
