"""Configuration management for Battery Hawk with hot-reload and validation."""

import json
import logging
import os
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from watchdog.events import FileSystemEvent

from jsonschema import ValidationError, validate
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

CONFIG_FILES: dict[str, str] = {
    "system": "system.json",
    "devices": "devices.json",
    "vehicles": "vehicles.json",
}

DEFAULTS: dict[str, dict] = {
    "system": {
        "version": "1.0",
        "logging": {"level": "INFO"},
        "bluetooth": {"max_concurrent_connections": 3, "test_mode": False},
        "discovery": {"initial_scan": True, "scan_duration": 10},
        "influxdb": {
            "enabled": False,
            "host": "localhost",
            "port": 8086,
            "database": "battery_hawk",
            "username": "",
            "password": "",
            "timeout": 10000,
            "retries": 3,
            "retention_policies": {
                "default": {
                    "name": "autogen",
                    "duration": "30d",
                    "replication": 1,
                    "shard_duration": "1d",
                    "default": True,
                },
                "long_term": {
                    "name": "long_term",
                    "duration": "365d",
                    "replication": 1,
                    "shard_duration": "7d",
                    "default": False,
                },
                "short_term": {
                    "name": "short_term",
                    "duration": "7d",
                    "replication": 1,
                    "shard_duration": "1h",
                    "default": False,
                },
            },
        },
        "mqtt": {
            "enabled": False,
            "broker": "localhost",
            "port": 1883,
            "username": "",
            "password": "",
            "topic_prefix": "batteryhawk",
            "qos": 1,
            "keepalive": 60,
            "timeout": 10,
            "retries": 3,
            "tls": False,
            "ca_cert": "",
            "cert_file": "",
            "key_file": "",
            # Resilience configuration
            "max_retries": 10,
            "initial_retry_delay": 1.0,
            "max_retry_delay": 300.0,
            "backoff_multiplier": 2.0,
            "jitter_factor": 0.1,
            "connection_timeout": 30.0,
            "health_check_interval": 60.0,
            "message_queue_size": 1000,
            "message_retry_limit": 3,
        },
        "api": {
            "enabled": True,
            "host": "0.0.0.0",  # nosec B104 - Configurable bind address  # noqa: S104
            "port": 5000,
            "debug": False,
        },
    },
    "devices": {"version": "1.0", "devices": {}},
    "vehicles": {"version": "1.0", "vehicles": {}},
}

SCHEMAS: dict[str, dict] = {
    "system": {
        "type": "object",
        "properties": {
            "version": {"type": "string"},
            "logging": {"type": "object"},
            "bluetooth": {"type": "object"},
            "discovery": {"type": "object"},
            "influxdb": {"type": "object"},
            "mqtt": {"type": "object"},
            "api": {"type": "object"},
        },
        "required": [
            "version",
            "logging",
            "bluetooth",
            "discovery",
            "influxdb",
            "mqtt",
            "api",
        ],
    },
    "devices": {
        "type": "object",
        "properties": {
            "version": {"type": "string"},
            "devices": {"type": "object"},
        },
        "required": ["version", "devices"],
    },
    "vehicles": {
        "type": "object",
        "properties": {
            "version": {"type": "string"},
            "vehicles": {"type": "object"},
        },
        "required": ["version", "vehicles"],
    },
}


def merge_defaults(config: dict, default: dict) -> dict:
    """Recursively merge default values into config, filling in missing keys."""
    for k, v in default.items():
        if k not in config:
            config[k] = v
        elif isinstance(v, dict) and isinstance(config[k], dict):
            merge_defaults(config[k], v)
    return config


class ConfigError(Exception):
    """Custom exception for configuration errors."""


class ConfigReloadHandler(FileSystemEventHandler):
    """Watches for file modifications and triggers a reload callback."""

    def __init__(self, reload_callback: Callable[[str], None]) -> None:
        """
        Initialize the handler.

        Args:
            reload_callback: Function to call with the path of the modified file.
        """
        self.reload_callback = reload_callback

    def on_modified(self, event: "FileSystemEvent") -> None:
        """
        Handle file modification events.

        Args:
            event: The file system event.
        """
        if event.is_directory:
            return
        self.reload_callback(str(event.src_path))


class ConfigManager:
    """Manages Battery Hawk configuration files with hot-reload, schema validation, and env var overrides."""

    def __init__(
        self,
        config_dir: str = "/data",
        *,
        enable_watchers: bool = True,
    ) -> None:
        """
        Initialize the ConfigManager.

        Args:
            config_dir: Directory where config files are stored.
            enable_watchers: Whether to enable file watchers (default: True).
        """
        self.config_dir: str = config_dir
        self.configs: dict[str, dict] = {}
        self._listeners: list[Callable[[str, dict], None]] = []
        self.logger = logging.getLogger("battery_hawk.config")
        self._enable_watchers = enable_watchers
        self._load_all_configs()
        if self._enable_watchers:
            self._setup_watchers()

    def _load_all_configs(self) -> None:
        """
        Load all config files, create defaults if missing, and apply env overrides.
        Raises ConfigError if validation fails.
        """
        for key, filename in CONFIG_FILES.items():
            self.configs[key] = self._load_json(filename, DEFAULTS[key], key)
            self._validate_config(key)
        self._apply_env_overrides()

    def _load_json(self, filename: str, default: dict, _key: str) -> dict:
        """
        Load a JSON config file, or create it with defaults if missing or invalid.

        Ensures all required keys are present by merging with defaults.

        Args:
            filename: The config file name.
            default: The default config dict.
            _key: The config section key (unused but kept for API compatibility).

        Returns:
            The loaded or default config dict.
        """
        path = os.path.join(self.config_dir, filename)
        config = None
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    msg = f"Config {filename} must be a dict"
                    raise TypeError(msg)
                config = merge_defaults(data, default.copy())
            except (json.JSONDecodeError, TypeError, OSError):
                self.logger.exception(
                    "Failed to load %s. Restoring default config.",
                    filename,
                )
                # REVIEW-THIS TODO: Handle parse errors, maybe backup and restore default
                config = default.copy()
                self._save_json(filename, config)
        else:
            config = default.copy()
            self._save_json(filename, config)
        return config

    def _save_json(self, filename: str, data: dict) -> None:
        """
        Save a config dict to a JSON file.

        Args:
            filename: The config file name.
            data: The config dict to save.

        Raises:
            ConfigError: If saving fails.
        """
        path = os.path.join(self.config_dir, filename)
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            self.logger.exception("Failed to save %s", filename)
            raise ConfigError(f"Failed to save {filename}: {e}") from e

    def _validate_config(self, key: str) -> None:
        """
        Validate a config dict against its schema.

        Args:
            key: The config section key ('system', 'devices', 'vehicles').

        Raises:
            ConfigError: If validation fails.
        """
        schema = SCHEMAS.get(key, {})
        if not schema:
            # REVIEW-THIS TODO: Implement actual schema
            return
        try:
            validate(instance=self.configs[key], schema=schema)
        except ValidationError as e:
            self.logger.exception("Validation error in %s config: %s", key, e.message)
            raise ConfigError(f"Validation error in {key} config: {e.message}") from e

    def _apply_env_overrides(self) -> None:
        """
        Apply BATTERYHAWK_ environment variable overrides to configs.

        Format: BATTERYHAWK_SECTION_KEY1_KEY2=VALUE (e.g., BATTERYHAWK_SYSTEM_LOGGING_LEVEL=DEBUG).
        """
        for env_key, value in os.environ.items():
            if not env_key.startswith("BATTERYHAWK_"):
                continue
            try:
                # Parse env var: BATTERYHAWK_SECTION_KEY1_KEY2=VALUE
                parts = env_key[12:].lower().split("_")
                section = parts[0]
                keys = parts[1:]
                if section not in self.configs:
                    continue
                d = self.configs[section]
                for k in keys[:-1]:
                    d = d.setdefault(k, {})
                try:
                    parsed_value = json.loads(value)
                except (json.JSONDecodeError, ValueError):
                    parsed_value = value
                d[keys[-1]] = parsed_value
                # After override, ensure required keys are present
                merge_defaults(self.configs[section], DEFAULTS[section].copy())
                self.logger.info(
                    "Applied env override: %s -> %s %s = %s",
                    env_key,
                    section,
                    ".".join(keys),
                    parsed_value,
                )
            except (KeyError, IndexError, TypeError):
                self.logger.exception("Failed to apply env override %s", env_key)

    def _setup_watchers(self) -> None:
        """Set up file watchers for hot-reload capability using watchdog."""
        self._observer = Observer()
        for filename in CONFIG_FILES.values():
            path = os.path.join(self.config_dir, filename)
            handler = ConfigReloadHandler(self._on_config_change)
            self._observer.schedule(handler, os.path.dirname(path), recursive=False)
        self._observer_thread = threading.Thread(
            target=self._observer.start,
            daemon=True,
        )
        self._observer_thread.start()

    def cleanup(self) -> None:
        """Clean up resources, including stopping file watchers."""
        if not self._enable_watchers:
            return
        if hasattr(self, "_observer") and self._observer.is_alive():
            self._observer.stop()
            self._observer.join(timeout=1.0)
        if hasattr(self, "_observer_thread") and self._observer_thread.is_alive():
            self._observer_thread.join(timeout=1.0)

    def _on_config_change(self, path: str) -> None:
        """
        Handle config file changes; reload, re-validate, and notify listeners.

        Args:
            path: The path of the changed config file.
        """
        for key, filename in CONFIG_FILES.items():
            if os.path.join(self.config_dir, filename) == path:
                self.logger.info("Detected change in %s, reloading...", filename)
                self.configs[key] = self._load_json(filename, DEFAULTS[key], key)
                try:
                    self._validate_config(key)
                except ConfigError:
                    self.logger.exception(
                        "Config %s failed validation after reload.",
                        key,
                    )
                self._apply_env_overrides()
                self._notify_listeners(key, self.configs[key])

    def get_config(self, key: str) -> dict:
        """
        Get a config by key ('system', 'devices', 'vehicles').

        Args:
            key: The config section key.

        Returns:
            The config dict for the given key.

        Raises:
            KeyError: If the config key is not found.
        """
        if key not in self.configs:
            raise KeyError(f"Config '{key}' not found.")
        return self.configs[key]

    def save_config(self, key: str) -> None:
        """
        Save a config by key back to its file.

        Args:
            key: The config section key.

        Raises:
            KeyError: If the config key is not recognized.
        """
        if key not in CONFIG_FILES:
            raise KeyError(f"Config '{key}' not recognized.")
        self._save_json(CONFIG_FILES[key], self.configs[key])

    def register_listener(self, callback: Callable[[str, dict], None]) -> None:
        """
        Register a callback to be notified when a config changes.

        Args:
            callback: Function to call with (key, config) when a config changes.
        """
        self._listeners.append(callback)

    def _notify_listeners(self, key: str, config: dict) -> None:
        """
        Notify all registered listeners of a config change.

        Args:
            key: The config section key.
            config: The new config dict.
        """
        for cb in self._listeners:
            try:
                cb(key, config)
            except Exception:  # noqa: PERF203
                self.logger.exception("Listener callback failed")

    def upgrade_version(self, key: str, target_version: str) -> None:
        """
        Stub for version upgrade logic. To be implemented as needed.

        Args:
            key: The config section key.
            target_version: The version to upgrade to.
        """
        self.logger.info(
            "Upgrade for %s to version %s not implemented.",
            key,
            target_version,
        )
