# ZoniaChatBot - atajos.
# Los dos compose van SIEMPRE juntos: comparten red para que el backend
# resuelva Milvus por nombre de servicio (standalone:19530).

COMPOSE = docker compose -f docker-compose.milvus.yml -f docker-compose.yml

.PHONY: milvus milvus-down up down restart build rebuild logs ps shell attu front-user front-admin

# ── Solo la base vectorial (lo mas habitual en desarrollo) ─────────────
milvus:                ## Milvus 3.0 + etcd + MinIO + Attu
	docker compose -f docker-compose.milvus.yml up -d

milvus-down:
	docker compose -f docker-compose.milvus.yml down

attu:                  ## Abre la GUI de Milvus
	@echo "Attu -> http://localhost:3000"

# ── Stack completo en Docker ──────────────────────────────────────────
up:
	$(COMPOSE) up -d

down:                  ## OJO: -v borraria los datos de Milvus, no se usa aqui
	$(COMPOSE) down

restart: down up

build:
	$(COMPOSE) build

rebuild:
	$(COMPOSE) build --no-cache

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

shell:
	docker exec -it zonia_web /bin/bash

# ── Frontends en local (sin Docker) ───────────────────────────────────
# Los puertos 4202/4203 son los unicos permitidos por el CORS del backend.
front-user:
	npm run start:user

front-admin:
	npm run start:admin
