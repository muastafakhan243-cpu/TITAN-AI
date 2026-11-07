#!/usr/bin/env python3
"""Render runtime-only dashboard credentials into a private Freqtrade config."""
import json
import os
import secrets
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: render_config.py TEMPLATE OUTPUT")
    username = os.environ.get("FREQTRADE_API_USERNAME", "").strip()
    password = os.environ.get("FREQTRADE_API_PASSWORD", "")
    if not username or not password or password == "replace-this-with-a-long-unique-password":
        raise SystemExit(
            "Set a unique FREQTRADE_API_USERNAME and FREQTRADE_API_PASSWORD in your local .env file."
        )
    if len(password) < 16:
        raise SystemExit("Dashboard password must be at least 16 characters.")

    template_path, output_path = map(Path, sys.argv[1:])
    text = template_path.read_text(encoding="utf-8")
    replacements = {
        "__API_USERNAME__": username,
        "__API_PASSWORD__": password,
        "__API_JWT_SECRET__": secrets.token_urlsafe(48),
        "__API_WS_TOKEN__": secrets.token_urlsafe(32),
    }
    for token, value in replacements.items():
        # JSON encoding protects special characters and yields an unquoted string payload.
        text = text.replace(token, json.dumps(value)[1:-1])
    config = json.loads(text)
    if config.get("dry_run") is not True:
        raise SystemExit("Refusing to render a config that is not dry-run.")
    if config.get("trading_mode") != "spot" or config["exchange"].get("pair_whitelist") != ["BTC/USDT"]:
        raise SystemExit("Refusing to render config outside BTC/USDT Spot scope.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    output_path.chmod(0o600)


if __name__ == "__main__":
    main()
