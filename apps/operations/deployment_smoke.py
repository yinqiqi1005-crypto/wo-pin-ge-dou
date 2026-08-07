import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


class DeploymentSmokeError(ValueError):
    pass


@dataclass(frozen=True)
class DeploymentSmokeReport:
    checked_at: str
    base_url: str
    health_url: str
    homepage_url: str
    css_url: str
    javascript_url: str
    checks: dict


class AssetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stylesheets = []
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "link" and "stylesheet" in values.get("rel", "").split():
            if values.get("href"):
                self.stylesheets.append(values["href"])
        elif tag == "script" and values.get("src"):
            self.scripts.append(values["src"])


def _read_response(url, *, timeout, opener):
    request = Request(url, headers={"User-Agent": "wo-pin-ge-dou-deployment-smoke/1.0"})
    with opener(request, timeout=timeout) as response:
        status = response.status
        final_url = response.geturl()
        headers = response.headers
        body = response.read()
    if status != 200:
        raise DeploymentSmokeError(f"Expected HTTP 200 from {url}, got {status}.")
    return final_url, headers, body


def _validate_final_url(url, *, expected_host, require_https):
    parsed = urlparse(url)
    if require_https and parsed.scheme != "https":
        raise DeploymentSmokeError(f"Request did not finish on HTTPS: {url}")
    if parsed.hostname != expected_host:
        raise DeploymentSmokeError(
            f"Request finished on unexpected host {parsed.hostname!r}; expected {expected_host!r}."
        )


def _validate_security_headers(headers, *, require_hsts):
    checks = {
        "content_type_nosniff": headers.get("X-Content-Type-Options", "").lower() == "nosniff",
        "frame_options_deny": headers.get("X-Frame-Options", "").upper() == "DENY",
        "referrer_policy": headers.get("Referrer-Policy", "").lower()
        in {"no-referrer", "same-origin", "strict-origin", "strict-origin-when-cross-origin"},
    }
    if require_hsts:
        hsts = headers.get("Strict-Transport-Security", "")
        match = re.search(r"(?:^|;)\s*max-age=(\d+)", hsts, flags=re.IGNORECASE)
        checks["hsts"] = bool(match and int(match.group(1)) > 0)
    else:
        checks["hsts"] = "skipped_for_local_http"
    failed = [name for name, passed in checks.items() if passed is False]
    if failed:
        raise DeploymentSmokeError("Missing or unsafe response headers: " + ", ".join(failed))
    return checks


def _pick_fingerprinted_asset(paths, pattern, label):
    matches = [path for path in paths if re.search(pattern, urlparse(path).path)]
    if len(matches) != 1:
        raise DeploymentSmokeError(
            f"Expected one fingerprinted {label} asset, found {len(matches)}."
        )
    return matches[0]


def run_deployment_smoke(
    base_url,
    *,
    expected_host,
    timeout=10,
    allow_http_localhost=False,
    opener=None,
):
    parsed = urlparse(base_url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise DeploymentSmokeError("base-url cannot contain credentials, query or fragment.")
    if parsed.path not in {"", "/"}:
        raise DeploymentSmokeError("base-url must point to the deployment root.")
    if not parsed.hostname:
        raise DeploymentSmokeError("base-url must include a host.")
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    local_http = parsed.scheme == "http" and allow_http_localhost and parsed.hostname in local_hosts
    if parsed.scheme != "https" and not local_http:
        raise DeploymentSmokeError("Public deployment smoke tests require HTTPS.")
    if parsed.hostname != expected_host:
        raise DeploymentSmokeError(
            f"base-url host {parsed.hostname!r} does not match expected host {expected_host!r}."
        )

    fetch = opener or urlopen
    normalized_base = base_url.rstrip("/") + "/"
    health_url = urljoin(normalized_base, "health/")
    health_final, _, health_body = _read_response(health_url, timeout=timeout, opener=fetch)
    _validate_final_url(
        health_final,
        expected_host=expected_host,
        require_https=not local_http,
    )
    try:
        health_payload = json.loads(health_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeploymentSmokeError("Health response is not valid JSON.") from exc
    if health_payload != {"status": "ok"}:
        raise DeploymentSmokeError("Health response must be exactly {'status': 'ok'}.")

    homepage_final, homepage_headers, homepage_body = _read_response(
        normalized_base,
        timeout=timeout,
        opener=fetch,
    )
    _validate_final_url(
        homepage_final,
        expected_host=expected_host,
        require_https=not local_http,
    )
    security_checks = _validate_security_headers(
        homepage_headers,
        require_hsts=not local_http,
    )
    try:
        homepage_text = homepage_body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DeploymentSmokeError("Homepage is not UTF-8.") from exc
    if "我拼个豆" not in homepage_text or "<html" not in homepage_text.lower():
        raise DeploymentSmokeError("Homepage does not contain the expected product shell.")

    parser = AssetParser()
    parser.feed(homepage_text)
    css_path = _pick_fingerprinted_asset(
        parser.stylesheets,
        r"/static/css/app\.[0-9a-f]{12}\.css$",
        "application CSS",
    )
    javascript_path = _pick_fingerprinted_asset(
        parser.scripts,
        r"/static/js/creation\.[0-9a-f]{12}\.js$",
        "application JavaScript",
    )
    css_url = urljoin(homepage_final, css_path)
    javascript_url = urljoin(homepage_final, javascript_path)
    for asset_url in (css_url, javascript_url):
        _validate_final_url(
            asset_url,
            expected_host=expected_host,
            require_https=not local_http,
        )
        _, _, asset_body = _read_response(asset_url, timeout=timeout, opener=fetch)
        if not asset_body:
            raise DeploymentSmokeError(f"Static asset is empty: {asset_url}")

    return DeploymentSmokeReport(
        checked_at=datetime.now(UTC).isoformat(),
        base_url=normalized_base,
        health_url=health_final,
        homepage_url=homepage_final,
        css_url=css_url,
        javascript_url=javascript_url,
        checks={
            "health": True,
            "homepage": True,
            "fingerprinted_assets": True,
            **security_checks,
        },
    )


def save_deployment_report(report, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as output:
        json.dump(asdict(report), output, ensure_ascii=False, indent=2)
        output.write("\n")
