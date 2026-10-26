import pytest
import requests
import responses
from bs4 import BeautifulSoup
from click.testing import CliRunner

URL = "https://www.domain.de/path/"
VALIDATOR_URL = "http://localhost:8888/"


def html_page(lang="de", title="My Page", canonical=URL, body=""):
    lang_attr = f' lang="{lang}"' if lang is not None else ""
    title_tag = f"<title>{title}</title>" if title is not None else ""
    canonical_tag = f'<link rel="canonical" href="{canonical}">' if canonical is not None else ""
    return f"<!DOCTYPE html><html{lang_attr}><head>{title_tag}{canonical_tag}</head><body>{body}</body></html>"


def soup_of(html):
    return BeautifulSoup(html, "html.parser")


def write_csv(tmp_path, content):
    csv_file = tmp_path / "urls.csv"
    csv_file.write_text(content, encoding="utf-8")
    return str(csv_file)


class TestReadUrlConfigs:
    def test_reads_all_columns(self, checker, tmp_path):
        csv_file = write_csv(tmp_path, "full_url,expected_status_code,expected_redirect_target\n"
                                       "https://www.domain.de/oldPath,301,https://www.domain.de/newPath/\n")

        configs = checker.read_url_configs(csv_file)

        assert configs == [checker.UrlConfig("https://www.domain.de/oldPath", 301, "https://www.domain.de/newPath/")]

    def test_status_code_is_parsed_as_int(self, checker, tmp_path):
        csv_file = write_csv(tmp_path, "full_url,expected_status_code,expected_redirect_target\n"
                                       f"{URL},200\n")

        [config] = checker.read_url_configs(csv_file)

        assert config.expected_status_code == 200

    @pytest.mark.parametrize("row", [f"{URL},200", f"{URL},200,"])
    def test_missing_or_empty_redirect_target_is_falsy(self, checker, tmp_path, row):
        csv_file = write_csv(tmp_path, f"full_url,expected_status_code,expected_redirect_target\n{row}\n")

        [config] = checker.read_url_configs(csv_file)

        assert not config.expected_redirect_target

    def test_keeps_query_params_and_order(self, checker, tmp_path):
        csv_file = write_csv(tmp_path, "full_url,expected_status_code,expected_redirect_target\n"
                                       "https://a.de/?q=1,200\n"
                                       "https://b.de/,404\n")

        configs = checker.read_url_configs(csv_file)

        assert [c.full_url for c in configs] == ["https://a.de/?q=1", "https://b.de/"]

    def test_header_only_yields_no_configs(self, checker, tmp_path):
        csv_file = write_csv(tmp_path, "full_url,expected_status_code,expected_redirect_target\n")

        assert checker.read_url_configs(csv_file) == []

    def test_invalid_status_code_raises(self, checker, tmp_path):
        csv_file = write_csv(tmp_path, f"full_url,expected_status_code,expected_redirect_target\n{URL},abc\n")

        with pytest.raises(ValueError):
            checker.read_url_configs(csv_file)


class TestPartition:
    @pytest.mark.parametrize("items,chunk_amount", [
        (list(range(10)), 3),
        (list(range(10)), 10),
        (list(range(3)), 10),
        (list(range(1)), 1),
        ([], 4),
    ])
    def test_keeps_all_items_in_order(self, checker, items, chunk_amount):
        chunks = checker.partition(items, chunk_amount)

        assert len(chunks) == chunk_amount
        assert checker.flatmap(chunks) == items

    def test_chunks_are_balanced(self, checker):
        chunks = checker.partition(list(range(10)), 3)

        sizes = [len(chunk) for chunk in chunks]
        assert max(sizes) - min(sizes) <= 1


class TestFlatmap:
    def test_flattens_one_level(self, checker):
        assert checker.flatmap([["a"], [], ["b", "c"]]) == ["a", "b", "c"]

    def test_empty(self, checker):
        assert checker.flatmap([]) == []


class TestCheckLangDefinition:
    def test_de_is_fine(self, checker):
        assert checker.check_lang_definition(soup_of(html_page(lang="de")), URL) == []

    @pytest.mark.parametrize("lang", ["en", "de-DE", "", None])
    def test_other_or_missing_lang_is_an_error(self, checker, lang):
        errors = checker.check_lang_definition(soup_of(html_page(lang=lang)), URL)

        assert errors == [f"URL {URL} doesn't contain language 'de' in html tag."]

    def test_missing_html_tag_is_an_error(self, checker):
        errors = checker.check_lang_definition(soup_of("just text"), URL)

        assert errors == [f"URL {URL} doesn't contain language 'de' in html tag."]


class TestCheckMetadata:
    def test_title_is_fine(self, checker):
        assert checker.check_metadata(soup_of(html_page(title="Hello")), URL) == []

    @pytest.mark.parametrize("title", [None, "", "   \n "])
    def test_missing_or_blank_title_is_an_error(self, checker, title):
        errors = checker.check_metadata(soup_of(html_page(title=title)), URL)

        assert errors == [f"URL {URL} doesn't have a title"]


class TestCheckIncludeError:
    def test_php_include_warning_is_an_error(self, checker):
        html = html_page(body="Warning: include(foo.php): failed to open stream: No such file")

        assert checker.check_include_error(html, URL) == [f"URL {URL} probably contains an include error."]

    def test_clean_page_is_fine(self, checker):
        assert checker.check_include_error(html_page(), URL) == []


class TestCheckCanonicalLink:
    def test_matching_canonical_is_fine(self, checker):
        assert checker.check_canonical_link(soup_of(html_page(canonical=URL)), URL) == []

    def test_query_params_of_request_url_are_ignored(self, checker):
        soup = soup_of(html_page(canonical=URL))

        assert checker.check_canonical_link(soup, f"{URL}?utm_source=foo&bar=1") == []

    def test_canonical_with_trailing_slash_matches_request_url_without(self, checker):
        soup = soup_of(html_page(canonical="https://www.domain.de/"))

        assert checker.check_canonical_link(soup, "https://www.domain.de") == []

    def test_trailing_slash_leniency_still_compares_the_url(self, checker):
        soup = soup_of(html_page(canonical="https://www.other.de/"))

        errors = checker.check_canonical_link(soup, "https://www.domain.de/path")

        assert errors == ["URL https://www.domain.de/path has canonical URL https://www.other.de/ "
                          "instead of https://www.domain.de/path"]

    def test_canonical_with_query_param_is_an_error(self, checker):
        soup = soup_of(html_page(canonical=f"{URL}?page=2"))

        errors = checker.check_canonical_link(soup, f"{URL}?page=2")

        assert errors == [f"URL {URL}?page=2 has canonical URL {URL}?page=2 instead of {URL}"]

    def test_different_canonical_is_an_error(self, checker):
        soup = soup_of(html_page(canonical="https://www.domain.de/other/"))

        errors = checker.check_canonical_link(soup, URL)

        assert errors == [f"URL {URL} has canonical URL https://www.domain.de/other/ instead of {URL}"]

    def test_missing_canonical_is_an_error(self, checker):
        errors = checker.check_canonical_link(soup_of(html_page(canonical=None)), URL)

        assert errors == [f"URL {URL} doesn't contain canonical link."]

    def test_canonical_without_href_is_an_error(self, checker):
        soup = soup_of('<html lang="de"><head><link rel="canonical"></head></html>')

        assert checker.check_canonical_link(soup, URL) == [f"URL {URL} doesn't contain canonical link."]

    def test_missing_head_is_an_error(self, checker):
        soup = soup_of('<html lang="de"><body>no head</body></html>')

        assert checker.check_canonical_link(soup, URL) == [f"URL {URL} doesn't contain canonical link."]

    def test_canonical_outside_head_is_ignored(self, checker):
        soup = soup_of(f'<html lang="de"><head></head><body><link rel="canonical" href="{URL}"></body></html>')

        assert checker.check_canonical_link(soup, URL) == [f"URL {URL} doesn't contain canonical link."]


class TestValidateHtml:
    @responses.activate
    def test_no_messages_is_fine(self, checker):
        validator_call = responses.get(VALIDATOR_URL, json={"messages": []})

        assert checker.validate_html(URL, VALIDATOR_URL) == []
        assert validator_call.calls[0].request.params == {"doc": URL, "out": "json"}

    @responses.activate
    def test_messages_are_reported_with_link_to_html_report(self, checker):
        responses.get(VALIDATOR_URL, json={"messages": [{"type": "error"}, {"type": "info"}]})

        [error] = checker.validate_html(URL, VALIDATOR_URL)

        assert error.startswith(f"URL {URL} has 2 validation errors. See {VALIDATOR_URL}?")
        assert "out=html" in error
        assert "out=json" not in error

    @responses.activate
    def test_unreachable_validator_is_an_error(self, checker):
        responses.get(VALIDATOR_URL, body=requests.ConnectionError("refused"))

        errors = checker.validate_html(URL, VALIDATOR_URL)

        assert errors == [f"URL {URL} couldn't be validated by {VALIDATOR_URL}: refused"]

    def test_validator_request_has_a_timeout(self, checker, monkeypatch):
        captured = {}

        def fake_get(**kwargs):
            captured.update(kwargs)
            raise requests.Timeout("read timed out")

        monkeypatch.setattr(checker.requests, "get", fake_get)

        errors = checker.validate_html(URL, VALIDATOR_URL)

        assert captured["timeout"] == checker.REQUEST_TIMEOUT_SECONDS
        assert errors == [f"URL {URL} couldn't be validated by {VALIDATOR_URL}: read timed out"]

    @responses.activate
    def test_non_json_validator_response_is_an_error(self, checker):
        responses.get(VALIDATOR_URL, body="<html>Bad Gateway</html>", status=502)

        [error] = checker.validate_html(URL, VALIDATOR_URL)

        assert error.startswith(f"URL {URL} couldn't be validated by {VALIDATOR_URL}:")


class TestCheckUrl:
    @responses.activate
    def test_valid_page_has_no_errors(self, checker):
        responses.get(URL, body=html_page())

        assert checker.check_url(checker.UrlConfig(URL, 200, None), None) == []

    @responses.activate
    def test_unexpected_status_code_is_an_error(self, checker):
        responses.get(URL, body=html_page(), status=404)

        errors = checker.check_url(checker.UrlConfig(URL, 200, None), None)

        assert errors == [f"URL {URL} doesn't respond with 200. Instead: 404"]

    @responses.activate
    def test_redirects_are_not_followed(self, checker):
        responses.get(URL, status=301, headers={"Location": "https://www.domain.de/new/"})

        errors = checker.check_url(checker.UrlConfig(URL, 200, None), None)

        assert errors == [f"URL {URL} doesn't respond with 200. Instead: 301"]
        assert len(responses.calls) == 1

    @responses.activate
    def test_expected_redirect_is_fine(self, checker):
        responses.get(URL, status=301, headers={"Location": "https://www.domain.de/new/"})

        assert checker.check_url(checker.UrlConfig(URL, 301, "https://www.domain.de/new/"), None) == []

    @responses.activate
    def test_redirect_to_wrong_target_is_an_error(self, checker):
        responses.get(URL, status=301, headers={"Location": "https://www.domain.de/wrong/"})

        errors = checker.check_url(checker.UrlConfig(URL, 301, "https://www.domain.de/new/"), None)

        assert errors == [f"URL {URL} doesn't redirect to https://www.domain.de/new/. Instead: https://www.domain.de/wrong/"]

    @responses.activate
    def test_redirect_without_location_header_is_an_error(self, checker):
        responses.get(URL, status=301)

        errors = checker.check_url(checker.UrlConfig(URL, 301, "https://www.domain.de/new/"), None)

        assert errors == [f"URL {URL} doesn't redirect to https://www.domain.de/new/. Instead: None"]

    @responses.activate
    def test_redirect_skips_content_checks_and_validation(self, checker):
        responses.get(URL, status=301, headers={"Location": "https://www.domain.de/new/"}, body="no html")

        assert checker.check_url(checker.UrlConfig(URL, 301, "https://www.domain.de/new/"), VALIDATOR_URL) == []
        assert len(responses.calls) == 1

    @responses.activate
    def test_collects_all_content_errors(self, checker):
        responses.get(URL, body=html_page(lang="en", title=None, canonical=None, body="failed to open stream"))

        errors = checker.check_url(checker.UrlConfig(URL, 200, None), None)

        assert errors == [
            f"URL {URL} probably contains an include error.",
            f"URL {URL} doesn't contain language 'de' in html tag.",
            f"URL {URL} doesn't contain canonical link.",
            f"URL {URL} doesn't have a title",
        ]

    @responses.activate
    def test_validates_page_when_validator_url_given(self, checker):
        responses.get(URL, body=html_page())
        responses.get(VALIDATOR_URL, json={"messages": [{"type": "error"}]})

        [error] = checker.check_url(checker.UrlConfig(URL, 200, None), VALIDATOR_URL)

        assert error.startswith(f"URL {URL} has 1 validation errors.")

    @responses.activate
    def test_skips_validation_without_validator_url(self, checker):
        responses.get(URL, body=html_page())

        checker.check_url(checker.UrlConfig(URL, 200, None), None)

        assert len(responses.calls) == 1

    @responses.activate
    def test_unreachable_url_is_an_error(self, checker):
        responses.get(URL, body=requests.ConnectionError("connection refused"))

        errors = checker.check_url(checker.UrlConfig(URL, 200, None), None)

        assert errors == [f"URL {URL} couldn't be requested: connection refused"]

    @pytest.mark.parametrize("url,expected_verify", [
        ("http://localhost:8080/path/", False),
        ("https://www.domain.de/path/", True),
    ])
    def test_tls_verification_is_only_disabled_for_localhost(self, checker, monkeypatch, url, expected_verify):
        captured = {}

        def fake_get(requested_url, **kwargs):
            captured.update(kwargs)
            response = requests.Response()
            response.status_code = 404
            return response

        monkeypatch.setattr(checker.requests, "get", fake_get)

        checker.check_url(checker.UrlConfig(url, 200, None), None)

        assert captured["verify"] is expected_verify
        assert captured["allow_redirects"] is False
        assert captured["timeout"] == checker.REQUEST_TIMEOUT_SECONDS

    @responses.activate
    def test_timeout_is_an_error(self, checker):
        responses.get(URL, body=requests.Timeout("read timed out"))

        errors = checker.check_url(checker.UrlConfig(URL, 200, None), None)

        assert errors == [f"URL {URL} couldn't be requested: read timed out"]


class TestCli:
    CSV_HEADER = "full_url,expected_status_code,expected_redirect_target\n"

    @responses.activate
    def test_reports_success(self, checker, tmp_path):
        responses.get(URL, body=html_page())
        csv_file = write_csv(tmp_path, f"{self.CSV_HEADER}{URL},200\n")

        result = CliRunner().invoke(checker.check, ["--csv_file", csv_file])

        assert result.exit_code == 0
        assert "Everything went fine!" in result.output

    @responses.activate
    def test_reports_errors_of_all_urls(self, checker, tmp_path):
        urls = [f"https://www.domain.de/page{i}/" for i in range(5)]
        for url in urls:
            responses.get(url, status=500)
        csv_file = write_csv(tmp_path, self.CSV_HEADER + "".join(f"{url},200\n" for url in urls))

        result = CliRunner().invoke(checker.check, ["--csv_file", csv_file, "--thread_amount", "2"])

        assert result.exit_code == 1
        assert "==== !! 5 ERROR(S) OCCURRED !! =====" in result.output
        for url in urls:
            assert f"URL {url} doesn't respond with 200. Instead: 500" in result.output

    @responses.activate
    def test_one_unreachable_url_does_not_abort_the_run(self, checker, tmp_path):
        broken_url = "https://www.domain.de/broken/"
        responses.get(URL, body=html_page())
        responses.get(broken_url, body=requests.ConnectionError("connection refused"))
        csv_file = write_csv(tmp_path, f"{self.CSV_HEADER}{URL},200\n{broken_url},200\n")

        result = CliRunner().invoke(checker.check, ["--csv_file", csv_file])

        assert result.exit_code == 1
        assert "==== !! 1 ERROR(S) OCCURRED !! =====" in result.output
        assert f"URL {broken_url} couldn't be requested: connection refused" in result.output

    @responses.activate
    def test_validation_errors_alone_fail_the_run(self, checker, tmp_path):
        responses.get(URL, body=html_page())
        responses.get(VALIDATOR_URL, json={"messages": [{"type": "error"}]})
        csv_file = write_csv(tmp_path, f"{self.CSV_HEADER}{URL},200\n")

        result = CliRunner().invoke(checker.check, ["--csv_file", csv_file, "--nu_validator_url", VALIDATOR_URL])

        assert result.exit_code == 1
        assert "==== !! 1 ERROR(S) OCCURRED !! =====" in result.output
        assert f"URL {URL} has 1 validation errors." in result.output

    def test_csv_file_is_required(self, checker):
        result = CliRunner().invoke(checker.check, [])

        assert result.exit_code != 0
        assert "--csv_file" in result.output
