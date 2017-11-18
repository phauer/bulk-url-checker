.PHONY: check check-live, check-live-live

SHELL:=/bin/bash
VENV:=.venv
ACTIVATE=source $(VENV)/bin/activate

all: check

check: $(VENV)
	$(ACTIVATE);\
	python3 bulk-url-checker.py --csv_file="urls-localhost.csv" --nu_validator_url="http://localhost:8888/"

check-live: $(VENV)
	$(ACTIVATE);\
	python3 bulk-url-checker.py --csv_file="urls-live.csv" --nu_validator_url="http://localhost:8888/"

check-live-live: $(VENV)
	$(ACTIVATE);\
	python3 bulk-url-checker.py --csv_file="urls-live.csv" --nu_validator_url="https://validator.w3.org/nu/"

$(VENV):
	sudo apt install python3.6-venv
	python3.6 -m venv $(VENV)
	$(ACTIVATE);\
	pip3 install --requirement requirements.txt

clean:
	rm -r ./$(VENV)