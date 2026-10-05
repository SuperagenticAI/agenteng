import pytest

from agenteng.config import Settings


@pytest.mark.parametrize(
    "url",
    [
        "",
        "a2a.agentengineering.world",
        "AGENTENG_PUBLIC_URL=https://a2a.agentengineering.world",
        '"https://a2a.agentengineering.world"',
        " https://a2a.agentengineering.world",
        "https://a2a.agentengineering.world/health",
        "https://user:private@example.org",
        "https://example.org:invalid",
        "https://example.org:99999",
        "http://example.org",
    ],
)
def test_invalid_public_url_is_rejected_before_serving(monkeypatch, url):
    monkeypatch.setenv("AGENTENG_PUBLIC_URL", url)
    with pytest.raises(ValueError, match="Invalid AGENTENG_PUBLIC_URL") as error:
        Settings.from_env()
    assert "private" not in str(error.value)


@pytest.mark.parametrize(
    "url",
    [
        "https://a2a.agentengineering.world",
        "https://agenteng-719159243945.europe-west1.run.app",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://[::1]:8080",
    ],
)
def test_public_url_is_normalized_for_all_transports(monkeypatch, url):
    monkeypatch.setenv("AGENTENG_PUBLIC_URL", url + "/")
    assert Settings.from_env().public_url == url
    assert Settings(public_url=url + "/").public_url == url
