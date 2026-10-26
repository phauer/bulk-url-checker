# Bulk-URL-Checker

Checks a given bulk of URLs from a csv file for:

- Status code
- Redirect target
- Valid HTML (a local [Nu-Validator](https://github.com/validator/validator) service is used. So you don't have to upload your site for validation. Just run the validator against localhost)
- Some Metadata in the HTML head (language, title, canonical URL)
- Search for PHP include error messages

This way, you can do refactorings on your website and be sure that nothing critical broke.

## Usage

You csv file should look like this:

```csv
full_url,expected_status_code,expected_redirect_target
https://www.domain.de/path/,200
https://www.domain.de/oldPath,301,https://www.domain.de/newPath/
http://www.domain.de/path/,301,https://www.domain.de/path/
https://www.domain.de/path/?queryparam,200
```

See [`Makefile`](Makefile) for usage or:

```bash
# live:
./bulk-url-checker.py --csv_file="urls-live.csv" --nu_validator_url="https://validator.w3.org/nu/"

# live URLs but local nu-validator
docker compose up # start the nu-validator locally
./bulk-url-checker.py --csv_file="urls-live.csv" --nu_validator_url="http://localhost:8888/"

# on localhost (assuming that you have a local nu-validator up and running):
./bulk-url-checker.py --csv_file="urls-localhost.csv" --nu_validator_url="http://localhost:8888/"
```

The script exits with code 0 if all checks pass and with code 1 if any error was found, so CI jobs fail on regressions.

## Scheduled Checks

To detect regressions on live sites early, run the checker on a schedule with GitHub Actions. The URL list doesn't have to be public: keep the CSV and the workflow in a separate private repo, and check out this repo inside the job. The official `ghcr.io/validator/validator` image runs the Nu-Validator as a service container:

```yaml
name: Check URLs
on:
  schedule:
    - cron: "0 5 * * *" # daily at 05:00 UTC
  workflow_dispatch:
jobs:
  check:
    runs-on: ubuntu-latest
    services:
      validator:
        image: ghcr.io/validator/validator:latest
        ports: ["8888:8888"]
    steps:
      - uses: actions/checkout@v7
      - uses: actions/checkout@v7
        with:
          repository: phauer/bulk-url-checker
          ref: master
          path: checker
      - uses: astral-sh/setup-uv@v7
      - name: Wait for validator
        run: timeout 60 bash -c 'until curl -sf http://localhost:8888/ >/dev/null; do sleep 2; done'
      - run: uv run checker/bulk-url-checker.py --csv_file=urls-live.csv --nu_validator_url=http://localhost:8888/
```

GitHub emails you when a scheduled run fails.

## Install Dependencies

Requires [uv](https://docs.astral.sh/uv/). The dependencies are declared inline in `bulk-url-checker.py` (PEP 723 script metadata) and pinned in `bulk-url-checker.py.lock`. uv installs them automatically on the first run, so there is no virtual environment to set up. Both `./bulk-url-checker.py` and `uv run bulk-url-checker.py` work.

To update the pinned versions:

```bash
uv lock --script bulk-url-checker.py --upgrade
```

## Tests

The tests live in `tests/` and mock all HTTP calls, so they need neither network access nor a running Nu-Validator:

```bash
make test
```

## Misc

I received a list of the used URLs of my web site from Google Analytics. It provides an csv-export functionality. To remove all data from the csv except the URLs use the following command:

```bash
awk -F "\"*,\"*" '{print $1}' file.csv
```
