#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


PLUGIN_ID = "openclaw-websearch-pro"
PLUGIN_DIR = str(Path(__file__).resolve().parents[1])
CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"
PREVIEW_FILE = str(Path.home() / ".openclaw" / "workspace" / ".openclaw" / "websearch-pro-preview.json")
AUTH_PREVIEW_FILE = str(Path.home() / ".openclaw" / "workspace" / ".openclaw" / "websearch-pro-auth-preview.json")


def ensure_plugin_config(config: dict) -> dict:
    plugins = config.setdefault("plugins", {})
    allow = plugins.setdefault("allow", [])
    if PLUGIN_ID not in allow:
        allow.append(PLUGIN_ID)
    entries = plugins.setdefault("entries", {})
    entry = entries.setdefault(PLUGIN_ID, {})
    entry["enabled"] = True
    plugin_cfg = entry.setdefault("config", {})
    plugin_cfg.setdefault("enabled", True)
    plugin_cfg.setdefault("proactiveSearch", True)
    plugin_cfg.setdefault("injectBeforePromptBuild", True)
    plugin_cfg.setdefault("previewFile", PREVIEW_FILE)
    plugin_cfg.setdefault("authPreviewFile", AUTH_PREVIEW_FILE)
    plugin_cfg.setdefault("defaultIntent", "auto")
    plugin_cfg.setdefault("maxInitialResults", 8)
    plugin_cfg.setdefault("maxDeepResults", 5)
    plugin_cfg.setdefault("maxRefineRounds", 2)
    return config


def main() -> int:
    if not CONFIG_PATH.exists():
        print(json.dumps({"error": f"missing_config:{CONFIG_PATH}"}, ensure_ascii=False))
        return 1
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    updated = ensure_plugin_config(config)
    CONFIG_PATH.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "plugin_id": PLUGIN_ID,
                "plugin_dir": PLUGIN_DIR,
                "config_path": str(CONFIG_PATH),
                "previewFile": PREVIEW_FILE,
                "authPreviewFile": AUTH_PREVIEW_FILE,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
