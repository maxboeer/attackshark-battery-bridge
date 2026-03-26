from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tomllib


DEFAULT_CONFIG_PATHS = (
    Path("/etc/attackshark-battery-bridge/config.toml"),
    Path("packaging/config.example.toml"),
)


@dataclass(slots=True)
class DaemonConfig:
    scan_interval_seconds: float = 3.0
    log_level: str = "INFO"


@dataclass(slots=True)
class PublisherConfig:
    backend: str = "uhid"
    json_status_path: Path = Path("/run/attackshark-battery-bridge/status.json")
    include_charging: bool = True


@dataclass(slots=True)
class ProfilesConfig:
    enabled: list[str] = field(default_factory=list)
    external_directories: list[Path] = field(default_factory=list)


@dataclass(slots=True)
class AppConfig:
    daemon: DaemonConfig = field(default_factory=DaemonConfig)
    publisher: PublisherConfig = field(default_factory=PublisherConfig)
    profiles: ProfilesConfig = field(default_factory=ProfilesConfig)


def discover_default_config() -> Path | None:
    for candidate in DEFAULT_CONFIG_PATHS:
        if candidate.exists():
            return candidate
    return None


def load_config(path: Path | None) -> AppConfig:
    if path is None:
        return AppConfig()

    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    daemon_raw = raw.get("daemon", {})
    publisher_raw = raw.get("publisher", {})
    profiles_raw = raw.get("profiles", {})

    return AppConfig(
        daemon=DaemonConfig(
            scan_interval_seconds=float(daemon_raw.get("scan_interval_seconds", 3.0)),
            log_level=str(daemon_raw.get("log_level", "INFO")).upper(),
        ),
        publisher=PublisherConfig(
            backend=str(publisher_raw.get("backend", "uhid")),
            json_status_path=Path(
                publisher_raw.get(
                    "json_status_path",
                    "/run/attackshark-battery-bridge/status.json",
                )
            ),
            include_charging=bool(publisher_raw.get("include_charging", True)),
        ),
        profiles=ProfilesConfig(
            enabled=[str(item) for item in profiles_raw.get("enabled", [])],
            external_directories=[
                Path(item) for item in profiles_raw.get("external_directories", [])
            ],
        ),
    )
