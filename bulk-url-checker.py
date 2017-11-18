#!/usr/bin/env python3.6
import csv
import time
from multiprocessing.pool import ThreadPool
from typing import List, NamedTuple

import click
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class UrlConfig(NamedTuple):
    full_url: str
    expected_status_code: int
    expected_redirect_target: str


@click.command()
@click.option('--csv_file', required=True, help='The csv file containing the urls to check')
@click.option('--nu_validator_url', default=None, help='If provided, each page will be validated using the given validator url. Defaults to None (no validation). Example values: "https://validator.w3.org/nu/" or "http://localhost:8888/"')
@click.option('--thread_amount', type=click.INT, default=10, help='How many process are started to execute the check in parallel.')
def check(csv_file: str, nu_validator_url: str, thread_amount: int):
    """Checks a given amount of URLs (e.g. status codes, redirects, title, valid HTML etc.)"""
    start_time = time.time()
    url_configs = read_url_configs(csv_file)
    url_config_chunks = partition(url_configs, thread_amount)

    pool = ThreadPool(processes=thread_amount)
    async_results = [pool.apply_async(func=check_urls, args=[chunk, nu_validator_url]) for chunk in url_config_chunks]
    all_results = [result.get() for result in async_results]
    errors = flatmap(all_results)
    print(f"--- {time.time() - start_time} seconds ---")

    if len(errors) > 0:
        click.echo(f"==== !! {len(errors)} ERROR(S) OCCURRED !! ===== ")
        for error in errors:
            click.echo(error)
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


def check_urls(url_config_chunk: List[UrlConfig], nu_validator_url: str) -> List[str]:
    errors = []
    for url_config in url_config_chunk:
        errors += check_url(url_config, nu_validator_url)
    return errors


def check_url(url_config: UrlConfig, nu_validator_url: str) -> List[str]:
    url = url_config.full_url
    expected_status_code = url_config.expected_status_code
    expected_redirect_target = url_config.expected_redirect_target
    print(f"Checking {url_config}...")
    is_local_url = "localhost" in url
    response = requests.get(url, allow_redirects=False, verify=(not is_local_url))
    if response.status_code == expected_status_code:
        if expected_redirect_target:
            location = response.headers['Location']
            if location == expected_redirect_target:
                return []
            else:
                return [f"URL {url} doesn't redirect to {expected_redirect_target}. Instead: {location}"]
        else:
            errors = []
            errors += check_include_error(response.text, url)
            soup = BeautifulSoup(response.text, 'html.parser')
            errors += check_lang_definition(soup, url)
            errors += check_canonical_link(soup, url)
            errors += check_metadata(soup, url)
            if nu_validator_url:
                errors += validate_html(url, nu_validator_url)
            return errors
    else:
        return [f"URL {url} doesn't respond with {expected_status_code}. Instead: {response.status_code}"]


def validate_html(url: str, nu_validator_url: str) -> List[str]:
    response = requests.get(url=nu_validator_url, params={'doc': url, 'out': 'json'})
    messages = response.json()['messages']
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
    canonical_link = soup.head.find('link', {'rel': 'canonical'})
    if not canonical_link:
        return [f"URL {request_url} doesn't contain canonical link."]
    request_url_without_query_params = request_url[:request_url.index('?')] if '?' in request_url else request_url
    canonical_href = canonical_link.attrs['href']
    if canonical_href.endswith('/') and not request_url_without_query_params.endswith('/'): # "www.localhost/" vs "www.localhost"
        return []
    if canonical_link.attrs['href'] != request_url_without_query_params:
        return [f"URL {request_url} contains a canonical url with a query parameter!"]
    return []


def check_lang_definition(soup: BeautifulSoup, url: str):
    html_tag = soup.find('html')
    if 'lang' not in html_tag.attrs or 'de' != html_tag.attrs['lang']:
        return [f"URL {url} doesn't contain language 'de' in html tag."]
    return []


def partition(list, chunk_size):
    division = len(list) / chunk_size
    return [list[round(division * i):round(division * (i + 1))] for i in range(chunk_size)]


def flatmap(list: List[List[str]]):
    return [item for sublist in list for item in sublist]


if __name__ == '__main__':
    check()
