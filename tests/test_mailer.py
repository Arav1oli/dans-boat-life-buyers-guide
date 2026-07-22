import json

from backend import mailer


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def test_resend_delivery_uses_https_api(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(mailer.settings, "resend_api_key", "test-key")
    monkeypatch.setattr(mailer.settings, "smtp_from", "Guide <guide@example.com>")
    monkeypatch.setattr(mailer, "urlopen", fake_urlopen)

    mailer.send_email("buyer@example.com", "Your guide", "Your shortlist")

    request = captured["request"]
    assert request.full_url == "https://api.resend.com/emails"
    assert request.get_header("Authorization") == "Bearer test-key"
    assert captured["timeout"] == 30
    assert json.loads(request.data) == {
        "from": "Guide <guide@example.com>",
        "to": ["buyer@example.com"],
        "subject": "Your guide",
        "text": "Your shortlist",
    }
