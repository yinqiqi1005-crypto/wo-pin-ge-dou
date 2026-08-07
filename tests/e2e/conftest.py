import os

import pytest
from playwright.sync_api import sync_playwright

# Playwright's synchronous API owns an event loop in the test thread. Django's
# live-server database work remains synchronous and isolated to this test process.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")


@pytest.fixture
def browser(django_db_setup):
    executable = os.getenv("E2E_BROWSER_EXECUTABLE")
    launch_options = {"headless": True}
    if executable:
        launch_options["executable_path"] = executable
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**launch_options)
        yield browser
        browser.close()
