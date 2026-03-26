from __future__ import annotations

import argparse
import json
from pathlib import Path

from attackshark_battery_bridge.config import discover_default_config, load_config
from attackshark_battery_bridge.daemon.service import BridgeDaemon
from attackshark_battery_bridge.discovery import find_all_matches, iter_hidraw_devices
from attackshark_battery_bridge.drivers.profile_driver import ProfileBatteryDriver
from attackshark_battery_bridge.logging_utils import configure_logging
from attackshark_battery_bridge.profiles import BatteryProfile, load_profiles
from attackshark_battery_bridge.publishers.factory import build_publisher


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="attackshark-battery-bridge")
    parser.add_argument("--config", type=Path, default=None, help="Path to config TOML")
    subparsers = parser.add_subparsers(dest="command", required=False)

    serve_parser = subparsers.add_parser("serve", help="Run the daemon")
    serve_parser.add_argument(
        "--config",
        type=Path,
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )

    list_parser = subparsers.add_parser("list-devices", help="List hidraw devices and profile matches")
    list_parser.add_argument(
        "--config",
        type=Path,
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )

    probe_parser = subparsers.add_parser("probe", help="Run one direct battery poll")
    probe_parser.add_argument("--profile", default=None, help="Profile id override")
    probe_parser.add_argument(
        "--config",
        type=Path,
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )

    return parser


def _select_profiles(all_profiles: list[BatteryProfile], enabled_ids: list[str]) -> list[BatteryProfile]:
    if not enabled_ids:
        return all_profiles
    allowed = set(enabled_ids)
    return [profile for profile in all_profiles if profile.profile_id in allowed]


def _effective_config_path(explicit_path: Path | None) -> Path | None:
    if explicit_path is not None:
        return explicit_path
    return discover_default_config()


def _argument_config_path(args: argparse.Namespace) -> Path | None:
    subcommand_config = getattr(args, "config", None)
    if subcommand_config is not None:
        return subcommand_config
    return None


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    command = args.command or "serve"

    config_path = _effective_config_path(_argument_config_path(args))
    config = load_config(config_path)
    configure_logging(config.daemon.log_level)

    all_profiles = load_profiles(config.profiles.external_directories)
    selected_profiles = _select_profiles(all_profiles, config.profiles.enabled)

    if command == "list-devices":
        return _list_devices(selected_profiles)
    if command == "probe":
        return _probe(selected_profiles, args.profile)

    publisher = build_publisher(config.publisher)
    daemon = BridgeDaemon(config=config, profiles=selected_profiles, publisher=publisher)
    try:
        return daemon.run()
    finally:
        publisher.detach()


def _list_devices(profiles: list[BatteryProfile]) -> int:
    devices = iter_hidraw_devices()
    matches = {(profile.profile_id, device.hidraw_name) for profile, device in find_all_matches(profiles)}

    payload = []
    for device in devices:
        payload.append(
            {
                "hidraw": str(device.hidraw_path),
                "hid_name": device.hid_name,
                "vid_pid": device.vid_pid,
                "descriptor": device.report_descriptor_hex,
                "matched_profiles": [
                    profile.profile_id
                    for profile in profiles
                    if (profile.profile_id, device.hidraw_name) in matches
                ],
            }
        )

    print(json.dumps(payload, indent=2))
    return 0


def _probe(
    profiles: list[BatteryProfile],
    profile_id: str | None,
) -> int:
    selected = profiles
    if profile_id is not None:
        selected = [profile for profile in profiles if profile.profile_id == profile_id]

    driver = ProfileBatteryDriver()

    for profile, device in find_all_matches(selected):
        reading = driver.poll(device, profile)
        print(
            json.dumps(
                {
                    "profile_id": profile.profile_id,
                    "device": str(device.hidraw_path),
                    "percentage": reading.percentage,
                    "transport_mode": reading.transport_mode,
                    "charge_state": reading.charge_state,
                    "raw_status_flag_name": reading.raw_status_flag_name,
                    "raw_status_flag_value": reading.raw_status_flag_value,
                    "is_charging": reading.is_charging,
                    "observed_at": reading.observed_at.isoformat(),
                },
                indent=2,
            )
        )
        return 0

    print("No matching device found.")
    return 1
