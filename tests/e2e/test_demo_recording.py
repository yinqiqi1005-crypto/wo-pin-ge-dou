from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RECORDING_PATH = PROJECT_ROOT / "docs/demo-recordings/basic-flow.webm"


def test_internal_demo_recording_is_a_playable_desktop_video(browser):
    assert RECORDING_PATH.stat().st_size > 100_000
    page = browser.new_page()

    page.goto(RECORDING_PATH.as_uri())
    video = page.locator("video")
    video.wait_for()
    page.wait_for_function("document.querySelector('video').readyState >= 1")

    metadata = video.evaluate(
        "element => ({width: element.videoWidth, height: element.videoHeight, "
        "duration: element.duration})"
    )
    assert metadata["width"] == 1280
    assert metadata["height"] == 900
    assert metadata["duration"] > 1
    page.close()
