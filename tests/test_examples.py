import json
from pathlib import Path


def test_example_accounts_are_placeholders():
    path = Path(__file__).resolve().parents[1] / "examples" / "accounts.example.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    passwords = [account["password"] for account in data["accounts"]]
    assert passwords
    assert set(passwords) == {"REPLACE_ME"}
    text = path.read_text(encoding="utf-8")
    assert "accounts.enc" not in text
