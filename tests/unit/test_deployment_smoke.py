import json

import pytest

from apps.operations.deployment_smoke import (
    DeploymentSmokeError,
    run_deployment_smoke,
    save_deployment_report,
)

HOMEPAGE = b"""<!doctype html><html lang="zh-Hans"><head>
<title>\xe6\x88\x91\xe6\x8b\xbc\xe4\xb8\xaa\xe8\xb1\x86</title>
<link rel="stylesheet" href="/static/css/app.012345abcdef.css">
</head><body><script src="/static/js/creation.fedcba543210.js"></script></body></html>"""
SECURE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
}


class FakeResponse:
    def __init__(self, url, body, *, status=200, headers=None, final_url=None):
        self.url = url
        self.body = body
        self.status = status
        self.headers = headers or {}
        self.final_url = final_url or url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def geturl(self):
        return self.final_url

    def read(self):
        return self.body


def make_opener(*, homepage=HOMEPAGE, headers=None, health=b'{"status": "ok"}'):
    responses = {
        "https://demo.example/health/": FakeResponse("https://demo.example/health/", health),
        "https://demo.example/": FakeResponse(
            "https://demo.example/",
            homepage,
            headers=SECURE_HEADERS if headers is None else headers,
        ),
        "https://demo.example/static/css/app.012345abcdef.css": FakeResponse(
            "https://demo.example/static/css/app.012345abcdef.css", b"body{color:#222}"
        ),
        "https://demo.example/static/js/creation.fedcba543210.js": FakeResponse(
            "https://demo.example/static/js/creation.fedcba543210.js", b"(()=>{})()"
        ),
    }

    def opener(request, *, timeout):
        assert timeout == 7
        return responses[request.full_url]

    return opener


def test_https_deployment_smoke_checks_pages_assets_headers_and_saves_evidence(tmp_path):
    report = run_deployment_smoke(
        "https://demo.example",
        expected_host="demo.example",
        timeout=7,
        opener=make_opener(),
    )

    assert report.checks == {
        "health": True,
        "homepage": True,
        "fingerprinted_assets": True,
        "content_type_nosniff": True,
        "frame_options_deny": True,
        "referrer_policy": True,
        "hsts": True,
    }
    destination = tmp_path / "evidence" / "smoke.json"
    save_deployment_report(report, destination)
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["base_url"] == "https://demo.example/"
    assert payload["css_url"].endswith("app.012345abcdef.css")

    with pytest.raises(FileExistsError):
        save_deployment_report(report, destination)


def test_public_smoke_rejects_http_before_network_access():
    def forbidden_opener(*args, **kwargs):
        raise AssertionError("Network must not be touched")

    with pytest.raises(DeploymentSmokeError, match="require HTTPS"):
        run_deployment_smoke(
            "http://demo.example",
            expected_host="demo.example",
            opener=forbidden_opener,
        )


def test_smoke_rejects_a_base_url_that_does_not_match_expected_host():
    with pytest.raises(DeploymentSmokeError, match="does not match expected host"):
        run_deployment_smoke(
            "https://wrong.example",
            expected_host="demo.example",
            opener=make_opener(),
        )


@pytest.mark.parametrize(
    ("health", "message"),
    [
        (b"not-json", "not valid JSON"),
        (b'{"status": "degraded"}', "must be exactly"),
    ],
)
def test_smoke_rejects_invalid_or_degraded_health_response(health, message):
    with pytest.raises(DeploymentSmokeError, match=message):
        run_deployment_smoke(
            "https://demo.example",
            expected_host="demo.example",
            timeout=7,
            opener=make_opener(health=health),
        )


@pytest.mark.parametrize(
    "missing_header",
    [
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Strict-Transport-Security",
    ],
)
def test_smoke_rejects_each_missing_security_header(missing_header):
    headers = {key: value for key, value in SECURE_HEADERS.items() if key != missing_header}

    with pytest.raises(DeploymentSmokeError, match="Missing or unsafe response headers"):
        run_deployment_smoke(
            "https://demo.example",
            expected_host="demo.example",
            timeout=7,
            opener=make_opener(headers=headers),
        )


@pytest.mark.parametrize(
    ("homepage", "message"),
    [
        (
            HOMEPAGE.replace(b"app.012345abcdef.css", b"app.css"),
            "fingerprinted application CSS",
        ),
        (
            HOMEPAGE.replace(b"creation.fedcba543210.js", b"creation.js"),
            "fingerprinted application JavaScript",
        ),
    ],
)
def test_smoke_rejects_non_fingerprinted_application_assets(homepage, message):
    with pytest.raises(DeploymentSmokeError, match=message):
        run_deployment_smoke(
            "https://demo.example",
            expected_host="demo.example",
            timeout=7,
            opener=make_opener(homepage=homepage),
        )


def test_smoke_rejects_redirect_to_an_unexpected_host():
    opener = make_opener()

    def redirected(request, *, timeout):
        response = opener(request, timeout=timeout)
        if request.full_url.endswith("/health/"):
            response.final_url = "https://attacker.example/health/"
        return response

    with pytest.raises(DeploymentSmokeError, match="unexpected host"):
        run_deployment_smoke(
            "https://demo.example",
            expected_host="demo.example",
            timeout=7,
            opener=redirected,
        )
