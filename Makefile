.PHONY: all check check-live check-live-live test

all: check

check:
	uv run bulk-url-checker.py --csv_file="urls-localhost.csv" --nu_validator_url="http://localhost:8888/"

check-live:
	uv run bulk-url-checker.py --csv_file="urls-live.csv" --nu_validator_url="http://localhost:8888/"

check-live-live:
	uv run bulk-url-checker.py --csv_file="urls-live.csv" --nu_validator_url="https://validator.w3.org/nu/"

# runs the unit tests with the script's inline dependencies plus the test tools
test:
	uv run --no-project --with-requirements bulk-url-checker.py --with pytest --with responses pytest
