"""
Configuration manager for Omarchy System Monitor.
Handles user preferences persistence in ~/.config/omarchy-sysmon/config.json.
"""
import os
import json
from typing import Any

DEFAULT_CONFIG = {
    "theme": "system",                # "system", "dark", "light"
    "refresh_interval_sec": 1.0,     # Main metrics refresh interval
    "process_refresh_interval_sec": 2.0, # Process list refresh interval
    "history_duration_sec": 60,       # History duration in seconds
    "temperature_unit": "C",          # "C" or "F"
    "show_cards": {
        "cpu": True,
        "memory": True,
        "gpu": True,
        "disk": True,
        "network": True,
        "battery": True,
        "temperature": True,
    }
}

class ConfigManager:
    def __init__(self):
        self.config_dir = os.path.expanduser("~/.config/omarchy-sysmon")
        self.config_file = os.path.join(self.config_dir, "config.json")
        self._config = dict(DEFAULT_CONFIG)
        self.load()

    def load(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._merge_dict(self._config, data)
            except Exception as e:
                print(f"[Config] Error loading config: {e}")

    def _merge_dict(self, base: dict, override: dict):
        for k, v in override.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                self._merge_dict(base[k], v)
            else:
                base[k] = v

    def save(self):
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            temp_file = self.config_file + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2)
            os.replace(temp_file, self.config_file)
        except Exception as e:
            print(f"[Config] Error saving config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any):
        self._config[key] = value
        self.save()

    def get_show_card(self, card_name: str) -> bool:
        cards = self._config.get("show_cards", {})
        return cards.get(card_name, True)

    def set_show_card(self, card_name: str, show: bool):
        if "show_cards" not in self._config:
            self._config["show_cards"] = {}
        self._config["show_cards"][card_name] = show
        self.save()

    def reset_to_defaults(self):
        self._config = dict(DEFAULT_CONFIG)
        self.save()
