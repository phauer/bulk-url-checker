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
docker-compose up # start the nu-validator locally
./bulk-url-checker.py --csv_file="urls-live.csv" --nu_validator_url="http://localhost:8888/"

# on localhost (assuming that you have a local nu-validator up and running):
./bulk-url-checker.py --csv_file="urls-localhost.csv" --nu_validator_url="http://localhost:8888/"
```

## Install Python 3.6 and Deps

See [here](https://askubuntu.com/questions/865554/how-do-i-install-python-3-6-using-apt-get). For Ubuntu 16.04:

```bash
sudo add-apt-repository ppa:jonathonf/python-3.6
sudo apt-get update
sudo apt-get install python3.6 python3.6-dev python3.6-venv

# many ubuntu components (like gnome-terminal) are relying on python 3.5.
# So you can't change the symlink python3 to point to 3.6
# sudo rm /usr/bin/python3
# sudo ln -s /usr/bin/python3.6 /usr/bin/python3

# re-install requirements with pip
sudo pip3 install -r requirements.txt
```

## Misc

I received a list of the used URLs of my web site from Google Analytics. It provides an csv-export functionality. To remove all data from the csv except the URLs use the following command:

```bash
awk -F "\"*,\"*" '{print $1}' file.csv
```
