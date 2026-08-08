.PHONY: catalog test api frontend

catalog:
	uv run --project backend kitchen-almanac catalog build
	uv run --project backend kitchen-almanac catalog validate

test:
	uv run --project backend pytest

api:
	uv run --project backend uvicorn kitchen_almanac.main:app --reload

frontend:
	cd frontend && npm run dev
