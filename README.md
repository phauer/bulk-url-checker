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

## Install Dependencies

Requires [uv](https://docs.astral.sh/uv/). The dependencies are declared inline in `bulk-url-checker.py` (PEP 723 script metadata) and pinned in `bulk-url-checker.py.lock`. uv installs them automatically on the first run, so there is no virtual environment to set up. Both `./bulk-url-checker.py` and `uv run bulk-url-checker.py` work.

To update the pinned versions:

```bash
uv lock --script bulk-url-checker.py --upgrade
```

## Misc

I received a list of the used URLs of my web site from Google Analytics. It provides an csv-export functionality. To remove all data from the csv except the URLs use the following command:

```bash
awk -F "\"*,\"*" '{print $1}' file.csv
```
