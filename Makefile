.PHONY: all check check-live check-live-live

all: check

check:
	uv run bulk-url-checker.py --csv_file="urls-localhost.csv" --nu_validator_url="http://localhost:8888/"

check-live:
	uv run bulk-url-checker.py --csv_file="urls-live.csv" --nu_validator_url="http://localhost:8888/"

check-live-live:
	uv run bulk-url-checker.py --csv_file="urls-live.csv" --nu_validator_url="https://validator.w3.org/nu/"
