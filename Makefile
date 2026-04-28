# Redato — orquestrador de dev local end-to-end
#
# Veja `backend/notamil-backend/redato_backend/portal/RUN_LOCAL.md`
# pra contexto completo + roteiro de uso.
#
# Targets principais:
#   make demo          — popula DB + sobe portal + bot + frontend (3 procs)
#   make setup-demo    — só popula o DB (não sobe servers)
#   make run-portal    — só portal API (8091)
#   make run-bot       — só bot WhatsApp (8090)
#   make run-frontend  — só Next.js (3010)
#   make stop          — derruba processos rodando nas 3 portas
#   make health        — checa /admin/health/full
#   make whoami        — mostra creds e códigos de turma
#   make reset-db      — DROP + CREATE database (cuidado)

BACKEND := backend/notamil-backend
FRONTEND := redato_frontend
DB_NAME ?= redato_portal_dev
DB_URL ?= postgresql://$(USER)@localhost:5432/$(DB_NAME)
PORTAL_PORT := 8091
BOT_PORT := 8090
FRONT_PORT := 3010
PIDS_DIR := .demo-pids

# Carrega .env do backend (se existir) — propaga DATABASE_URL e amigos
# pros sub-makes.
ifneq (,$(wildcard $(BACKEND)/.env))
include $(BACKEND)/.env
export
endif


.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?##' Makefile | awk -F':.*?## ' '{printf "  %-18s %s\n", $$1, $$2}'


# ──────────────────────────────────────────────────────────────────────
# DB lifecycle
# ──────────────────────────────────────────────────────────────────────

.PHONY: db-create
db-create: ## Cria database Postgres (idempotente)
	@psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$(DB_NAME)'" \
		| grep -q 1 || createdb $(DB_NAME)
	@echo "DB pronto: $(DB_URL)"


.PHONY: reset-db
reset-db: ## DROP + CREATE database (apaga todos os dados!)
	@echo "Apagando $(DB_NAME)…"
	@dropdb --if-exists $(DB_NAME)
	@createdb $(DB_NAME)
	@echo "DB limpo."


.PHONY: setup-demo
setup-demo: db-create ## Popula DB com escola/coord/prof/turmas/atividade/envios sintéticos
	cd $(BACKEND) && DATABASE_URL=$(DB_URL) python scripts/setup_demo.py


# ──────────────────────────────────────────────────────────────────────
# Run servers (foreground, ideal pra ter num terminal cada)
# ──────────────────────────────────────────────────────────────────────

.PHONY: run-portal
run-portal: ## Sobe portal FastAPI na 8091 (foreground)
	cd $(BACKEND) && DATABASE_URL=$(DB_URL) \
		uvicorn redato_backend.portal.portal_app:app \
		--host 127.0.0.1 --port $(PORTAL_PORT) --reload


.PHONY: run-bot
run-bot: ## Sobe bot WhatsApp sandbox na 8090 (foreground)
	cd $(BACKEND) && DATABASE_URL=$(DB_URL) TWILIO_VALIDATE_SIGNATURE=0 \
		uvicorn redato_backend.whatsapp.app:app \
		--host 127.0.0.1 --port $(BOT_PORT) --reload


.PHONY: run-frontend
run-frontend: ## Sobe Next.js na 3010 (foreground)
	cd $(FRONTEND) && \
		NEXT_PUBLIC_API_URL=http://localhost:$(PORTAL_PORT) \
		REDATO_SESSION_COOKIE=redato_session \
		npx next dev -p $(FRONT_PORT)


# ──────────────────────────────────────────────────────────────────────
# Demo: sobe os 3 em background + setup
# ──────────────────────────────────────────────────────────────────────

.PHONY: demo
demo: setup-demo ## Setup demo + sobe portal + bot + frontend em background
	@DATABASE_URL=$(DB_URL) python3 scripts/demo_up.py
	@$(MAKE) -s whoami


.PHONY: stop
stop: ## Derruba os 3 servers iniciados pelo `make demo`
	@python3 scripts/demo_up.py --stop


.PHONY: status
status: ## Mostra estado dos servers
	@python3 scripts/demo_up.py --status


# ──────────────────────────────────────────────────────────────────────
# Inspeção
# ──────────────────────────────────────────────────────────────────────

.PHONY: health
health: ## Checa /admin/health/full do portal
	@curl -fsS http://localhost:$(PORTAL_PORT)/admin/health/full \
		| python3 -m json.tool 2>/dev/null \
		|| echo "(portal ainda não respondeu)"


.PHONY: whoami
whoami: ## Mostra credenciais e códigos de turma da demo
	@echo ""
	@echo "════════════════════════════════════════════════════════════"
	@echo "  Redato — demo local"
	@echo "════════════════════════════════════════════════════════════"
	@echo ""
	@echo "URLs"
	@echo "  Portal (frontend):   http://localhost:$(FRONT_PORT)"
	@echo "  Backend API:         http://localhost:$(PORTAL_PORT)"
	@echo "  Bot WhatsApp:        http://localhost:$(BOT_PORT)/twilio/webhook"
	@echo "  Health:              http://localhost:$(PORTAL_PORT)/admin/health/full"
	@echo ""
	@echo "Credenciais (senha = demo123):"
	@echo "  Professora:   prof@demo.redato"
	@echo "  Coordenadora: coord@demo.redato"
	@echo ""
	@echo "Códigos de turma (pra simular cadastro de aluno):"
	@psql -d $(DB_NAME) -tA -c "SELECT codigo || ': ' || codigo_join FROM turmas WHERE deleted_at IS NULL ORDER BY codigo;" 2>/dev/null \
		| sed 's/^/  /' || echo "  (DB não respondeu — rode make setup-demo)"
	@echo ""


.PHONY: logs-portal
logs-portal: ## tail dos logs do portal
	@tail -f $(PIDS_DIR)/portal.log

.PHONY: logs-bot
logs-bot: ## tail dos logs do bot
	@tail -f $(PIDS_DIR)/bot.log

.PHONY: logs-frontend
logs-frontend: ## tail dos logs do frontend
	@tail -f $(PIDS_DIR)/frontend.log
