.PHONY: install demo serve test lint public
install:
	python -m pip install -c requirements.lock -e '.[dev,postgres,cloud,tracking]'
demo:
	forecastlab demo
serve:
	forecastlab serve
test:
	pytest -q
lint:
	ruff check forecastlab tests scripts
public:
	python scripts/fetch_public_data.py
	forecastlab train examples/bike-rentals.csv --name 'UCI bike rentals (2011–2012)' --provenance examples/bike-rentals.source.json
