.PHONY: all check check-live check-live-live venv clean

VENV:=.venv
PYTHON:=$(VENV)/bin/python
STAMP:=$(VENV)/.installed

all: check

check: venv
	$(PYTHON) bulk-url-checker.py --csv_file="urls-localhost.csv" --nu_validator_url="http://localhost:8888/"

check-live: venv
	$(PYTHON) bulk-url-checker.py --csv_file="urls-live.csv" --nu_validator_url="http://localhost:8888/"

check-live-live: venv
	$(PYTHON) bulk-url-checker.py --csv_file="urls-live.csv" --nu_validator_url="https://validator.w3.org/nu/"

# creates the venv and (re-)installs the dependencies whenever requirements.txt changes
venv: $(STAMP)

$(STAMP): requirements.txt
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --requirement requirements.txt
	touch $@

clean:
	rm -rf ./$(VENV)
