#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "urllib3>=2.8",
#   "requests>=2.34",
#   "beautifulsoup4>=4.15",
#   "click>=8.5",
# ]
# ///
import csv
import time
from multiprocessing.pool import ThreadPool
from typing import List, NamedTuple

import click
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REQUEST_TIMEOUT_SECONDS = 30
# retries smooth over flaky networks (e.g. on CI runners), so a single slow response doesn't fail the whole run
REQUEST_RETRIES = 2
RETRY_DELAY_SECONDS = 5


class UrlConfig(NamedTuple):
    full_url: str
    expected_status_code: int
    expected_redirect_target: str


@click.command()
@click.option('--csv_file', required=True, help='The csv file containing the urls to check')
@click.option('--nu_validator_url', default=None, help='If provided, each page will be validated using the given validator url. Defaults to None (no validation). Example values: "https://validator.w3.org/nu/" or "http://localhost:8888/"')
@click.option('--thread_amount', type=click.INT, default=10, help='How many process are started to execute the check in parallel.')
@click.option('--lang', default='de', show_default=True, help='Expected value of the lang attribute of the html tag (exact match). Example values: "de", "de-DE", "en-US"')
def check(csv_file: str, nu_validator_url: str, thread_amount: int, lang: str):
    """Checks a given amount of URLs (e.g. status codes, redirects, title, valid HTML etc.)"""
    start_time = time.time()
    url_configs = read_url_configs(csv_file)
    url_config_chunks = partition(url_configs, thread_amount)

    pool = ThreadPool(processes=thread_amount)
    async_results = [pool.apply_async(func=check_urls, args=[chunk, nu_validator_url, lang]) for chunk in url_config_chunks]
    all_results = [result.get() for result in async_results]
    errors = flatmap(all_results)
    print(f"--- {time.time() - start_time} seconds ---")

    if len(errors) > 0:
        click.echo(f"==== !! {len(errors)} ERROR(S) OCCURRED !! ===== ")
        for error in errors:
            click.echo(error)
        raise SystemExit(1)  # non-zero exit code lets CI jobs fail
    else:
        click.echo("Everything went fine!")


def read_url_configs(file_name: str) -> List[UrlConfig]:
    with open(file_name, newline='\n', encoding="utf-8") as urlFile:
        reader = csv.DictReader(urlFile, delimiter=',', quotechar='|')
        return [map_to_url_config(row) for row in reader]


def map_to_url_config(row):
    return UrlConfig(full_url=row["full_url"],
                     expected_status_code=int(row["expected_status_code"]),
                     expected_redirect_target=row["expected_redirect_target"])


def check_urls(url_config_chunk: List[UrlConfig], nu_validator_url: str, expected_lang: str = 'de') -> List[str]:
    errors = []
    for url_config in url_config_chunk:
        errors += check_url(url_config, nu_validator_url, expected_lang)
    return errors


def check_url(url_config: UrlConfig, nu_validator_url: str, expected_lang: str = 'de') -> List[str]:
    url = url_config.full_url
    expected_status_code = url_config.expected_status_code
    expected_redirect_target = url_config.expected_redirect_target
    print(f"Checking {url_config}...")
    is_local_url = "localhost" in url
    try:
        response = get_with_retries(url, allow_redirects=False, verify=(not is_local_url), timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as e:
        return [f"URL {url} couldn't be requested: {e}"]
    if response.status_code == expected_status_code:
        if expected_redirect_target:
            location = response.headers.get('Location')
            if location == expected_redirect_target:
                return []
            else:
                return [f"URL {url} doesn't redirect to {expected_redirect_target}. Instead: {location}"]
        else:
            errors = []
            errors += check_include_error(response.text, url)
            soup = BeautifulSoup(response.text, 'html.parser')
            errors += check_lang_definition(soup, url, expected_lang)
            errors += check_canonical_link(soup, url)
            errors += check_metadata(soup, url)
            if nu_validator_url:
                errors += validate_html(url, nu_validator_url)
            return errors
    else:
        return [f"URL {url} doesn't respond with {expected_status_code}. Instead: {response.status_code}"]


def get_with_retries(url: str, **kwargs) -> requests.Response:
    """GET request that is retried on timeouts and connection errors. HTTP error status codes are returned as they are."""
    for attempt in range(1, REQUEST_RETRIES + 1):
        try:
            return requests.get(url, **kwargs)
        except (requests.Timeout, requests.ConnectionError) as e:
            print(f"Retry {attempt}/{REQUEST_RETRIES} for {url} after: {e}")
            time.sleep(RETRY_DELAY_SECONDS * attempt)
    return requests.get(url, **kwargs)


def validate_html(url: str, nu_validator_url: str) -> List[str]:
    try:
        response = get_with_retries(nu_validator_url, params={'doc': url, 'out': 'json'}, timeout=REQUEST_TIMEOUT_SECONDS)
        messages = response.json()['messages']
    except (requests.RequestException, ValueError, KeyError) as e:
        return [f"URL {url} couldn't be validated by {nu_validator_url}: {e}"]
    if len(messages) != 0:
        return [f"URL {url} has {len(messages)} validation errors. See {response.url.replace('out=json', 'out=html')}"]
    return []


def check_metadata(soup: BeautifulSoup, url) -> List[str]:
    if soup.title is None or len(soup.title.text.strip()) == 0:
        return [f"URL {url} doesn't have a title"]
    return []


def check_include_error(html_string: str, url: str) -> List[str]:
    if "failed to open stream" in html_string:
        return [f"URL {url} probably contains an include error."]
    return []


def check_canonical_link(soup: BeautifulSoup, request_url) -> List[str]:
    canonical_link = soup.head.find('link', {'rel': 'canonical'}) if soup.head else None
    canonical_href = canonical_link.attrs.get('href') if canonical_link else None
    if not canonical_href:
        return [f"URL {request_url} doesn't contain canonical link."]
    request_url_without_query_params = request_url[:request_url.index('?')] if '?' in request_url else request_url
    if canonical_href == request_url_without_query_params + '/':  # "www.localhost/" vs "www.localhost"
        return []
    if canonical_href != request_url_without_query_params:
        return [f"URL {request_url} has canonical URL {canonical_href} instead of {request_url_without_query_params}"]
    return []


def check_lang_definition(soup: BeautifulSoup, url: str, expected_lang: str = 'de'):
    html_tag = soup.find('html')
    if html_tag is None or html_tag.attrs.get('lang') != expected_lang:
        return [f"URL {url} doesn't contain language '{expected_lang}' in html tag."]
    return []


def partition(list, chunk_size):
    division = len(list) / chunk_size
    return [list[round(division * i):round(division * (i + 1))] for i in range(chunk_size)]


def flatmap(list: List[List[str]]):
    return [item for sublist in list for item in sublist]


if __name__ == '__main__':
    check()
