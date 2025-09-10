"""Tests for ConfigManager and CLI config management in battery_hawk.config.config_manager."""

import os
import subprocess
import sys

import pytest

from src.battery_hawk.config.config_manager import DEFAULTS, ConfigError, ConfigManager


@pytest.fixture
def temp_config_dir(tmp_path: pytest.TempPathFactory) -> str:
    """Fixture for temporary config directory."""
    # Create a temporary directory for config files
    return str(tmp_path)


@pytest.fixture(autouse=True)
def clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixture to clear BATTERYHAWK_ env vars before each test."""
    # Clear BATTERYHAWK_ env vars before each test
    for k in list(os.environ.keys()):
        if k.startswith("BATTERYHAWK_"):
            monkeypatch.delenv(k, raising=False)


def run_cli(args: list[str], config_dir: str) -> tuple[int, str, str]:
    """Run the CLI as a subprocess and return (exit_code, stdout, stderr)."""
    # subprocess.run is safe here because input is controlled and not untrusted (test context)
    cmd = [sys.executable, "-m", "battery_hawk", "--config-dir", config_dir]
    proc = subprocess.run([*cmd, *args], capture_output=True, text=True, check=False)
    return proc.returncode, proc.stdout, proc.stderr


class TestConfigManager:
    """Test suite for ConfigManager."""

    def test_load_defaults_when_missing(self, temp_config_dir: str) -> None:
        """Test loading defaults when config is missing."""
        cm = ConfigManager(str(temp_config_dir), enable_watchers=False)
        for key in DEFAULTS:
            assert cm.get_config(key) == DEFAULTS[key]

    def test_save_and_reload(self, temp_config_dir: str) -> None:
        """Test saving and reloading config section."""
        cm = ConfigManager(str(temp_config_dir), enable_watchers=False)
        sys_cfg = cm.get_config("system")
        sys_cfg["logging"]["level"] = "DEBUG"
        cm.save_config("system")
        # Reload
        cm2 = ConfigManager(str(temp_config_dir), enable_watchers=False)
        assert cm2.get_config("system")["logging"]["level"] == "DEBUG"

    def test_schema_validation_valid(self, temp_config_dir: str) -> None:
        """Test schema validation for valid config."""
        cm = ConfigManager(str(temp_config_dir), enable_watchers=False)
        # Should not raise
        cm._validate_config("system")

    def test_schema_validation_invalid(self, temp_config_dir: str) -> None:
        """Test schema validation for invalid config."""
        cm = ConfigManager(str(temp_config_dir), enable_watchers=False)
        cm.configs["system"].pop("version")
        with pytest.raises(ConfigError):
            cm._validate_config("system")

    def test_env_override_applied(
        self,
        temp_config_dir: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test environment variable override is applied."""
        monkeypatch.setenv("BATTERYHAWK_SYSTEM_LOGGING_LEVEL", '"WARNING"')
        cm = ConfigManager(str(temp_config_dir), enable_watchers=False)
        assert cm.get_config("system")["logging"]["level"] == "WARNING"

    def test_invalid_json_falls_back_to_default(self, temp_config_dir: str) -> None:
        """Test fallback to default config on invalid JSON."""
        # Write invalid JSON
        path = os.path.join(temp_config_dir, "system.json")
        with open(path, "w") as f:
            f.write("{ invalid json }")
        cm = ConfigManager(str(temp_config_dir), enable_watchers=False)
        assert cm.get_config("system") == DEFAULTS["system"]

    def test_register_and_notify_listener(self, temp_config_dir: str) -> None:
        """Test registering and notifying config listeners."""
        cm = ConfigManager(str(temp_config_dir), enable_watchers=False)
        called = {}

        def listener(key: str, config: dict) -> None:
            """Handle config changes as a listener callback."""
            called["key"] = key
            called["config"] = config

        cm.register_listener(listener)
        # Simulate config change
        cm._notify_listeners("system", {"foo": "bar"})
        assert called["key"] == "system"
        assert called["config"] == {"foo": "bar"}


def test_cli_list_sections(temp_config_dir: str) -> None:
    """Test CLI list command for config sections."""
    code, out, err = run_cli(["list"], temp_config_dir)
    assert code == 0
    for section in ["system", "devices", "vehicles"]:
        assert section in out


def test_cli_show_section(temp_config_dir: str) -> None:
    """Test CLI show command for config section."""
    code, out, err = run_cli(["show", "system"], temp_config_dir)
    assert code == 0
    assert "version" in out
    assert "logging" in out


def test_cli_set_and_show_value(temp_config_dir: str) -> None:
    """Test CLI set and show value commands."""
    # Set a value
    code, out, err = run_cli(
        ["set", "system", "logging", "level", '"ERROR"'],
        temp_config_dir,
    )
    assert code == 0
    # Save
    code, out, err = run_cli(["save", "system"], temp_config_dir)
    assert code == 0
    # Show
    code, out, err = run_cli(["show", "system", "logging", "level"], temp_config_dir)
    assert code == 0
    assert "ERROR" in out


def test_cli_show_invalid_section(temp_config_dir: str) -> None:
    """Test CLI show command for invalid section."""
    code, out, err = run_cli(["show", "notasection"], temp_config_dir)
    assert code == 1
    assert "Error" in err


def test_cli_set_invalid_key(temp_config_dir: str) -> None:
    """Test CLI set command for invalid key."""
    code, out, err = run_cli(["set", "system", "notakey", '"foo"'], temp_config_dir)
    assert code == 0  # Setting a new key is allowed
    code, out, err = run_cli(["show", "system", "notakey"], temp_config_dir)
    assert code == 0
    assert "foo" in out
