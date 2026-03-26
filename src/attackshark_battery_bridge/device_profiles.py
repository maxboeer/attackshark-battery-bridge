from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
import sys
import tomllib

from attackshark_battery_bridge.exceptions import ParseError, ProfileError
from attackshark_battery_bridge.models import (
    BatteryReading,
    CHARGE_STATE_CHARGING,
    CHARGE_STATE_DISCHARGING,
    CHARGE_STATE_FULL,
    CHARGE_STATE_UNKNOWN,
    DeviceIdentity,
    TRANSPORT_MODE_UNKNOWN,
    TRANSPORT_MODE_WIRED,
    TRANSPORT_MODE_WIRELESS,
)


def _normalize_hex(value: str) -> str:
    return "".join(value.split()).lower()


def _decode_hex(value: str) -> bytes:
    normalized = _normalize_hex(value)
    if len(normalized) % 2 != 0:
        raise ProfileError(f"hex string must contain full bytes: {value!r}")
    return bytes.fromhex(normalized)


@dataclass(frozen=True, slots=True)
class DeviceMatchSpec:
    vid: int
    pids: tuple[int, ...]
    descriptor_fingerprint_hex: str
    product_name_contains: str | None = None
    transport_mode_by_pid: dict[int, str] | None = None

    def matches(self, device: DeviceIdentity) -> bool:
        if device.vendor_id != self.vid or device.product_id not in self.pids:
            return False
        if device.report_descriptor_hex != self.descriptor_fingerprint_hex:
            return False
        if self.product_name_contains and self.product_name_contains.lower() not in device.hid_name.lower():
            return False
        return True

    def transport_mode_for(self, device: DeviceIdentity) -> str:
        if self.transport_mode_by_pid is None:
            return TRANSPORT_MODE_UNKNOWN
        return self.transport_mode_by_pid.get(device.product_id, TRANSPORT_MODE_UNKNOWN)


@dataclass(frozen=True, slots=True)
class PollProtocol:
    mode: str
    report_length: int
    request_prefix: bytes
    response_prefix: bytes
    response_delay_ms: int
    poll_interval_seconds: float
    retry_response_prefixes: tuple[bytes, ...]
    max_follow_up_gets: int

    def build_request(self) -> bytes:
        if len(self.request_prefix) > self.report_length:
            raise ProfileError("request_prefix is longer than report_length")
        return self.request_prefix.ljust(self.report_length, b"\x00")


@dataclass(frozen=True, slots=True)
class ResponseMapping:
    percentage_index: int
    status_flag_index: int | None
    status_flag_name: str | None
    status_flag_semantics: str
    publish_charging_by_default: bool

    def parse(self, payload: bytes, transport_mode: str) -> BatteryReading:
        if self.percentage_index >= len(payload):
            raise ParseError("response too short for battery percentage")

        percentage = payload[self.percentage_index]
        if not 0 <= percentage <= 100:
            raise ParseError(f"battery percentage out of range: {percentage}")

        raw_flag_value: int | None = None
        if self.status_flag_index is not None:
            if self.status_flag_index >= len(payload):
                raise ParseError("response too short for status flag")
            raw_flag_value = payload[self.status_flag_index]

        is_charging: bool | None = None
        if (
            self.status_flag_semantics in {"charging_assumed", "charging_active"}
            and raw_flag_value in (0, 1)
        ):
            is_charging = bool(raw_flag_value)

        charge_state = _map_charge_state(
            percentage=percentage,
            is_charging=is_charging,
            transport_mode=transport_mode,
        )

        return BatteryReading.now(
            percentage=percentage,
            raw_status_flag_name=self.status_flag_name,
            raw_status_flag_value=raw_flag_value,
            is_charging=is_charging,
            transport_mode=transport_mode,
            charge_state=charge_state,
        )


@dataclass(frozen=True, slots=True)
class BatteryProfile:
    profile_id: str
    name: str
    match: DeviceMatchSpec
    poll_protocol: PollProtocol
    response_mapping: ResponseMapping
    notes: list[str]

    @property
    def default_publish_charging(self) -> bool:
        return self.response_mapping.publish_charging_by_default

    def matches(self, device: DeviceIdentity) -> bool:
        return self.match.matches(device)

    def transport_mode_for(self, device: DeviceIdentity) -> str:
        return self.match.transport_mode_for(device)

    def build_request(self) -> bytes:
        return self.poll_protocol.build_request()

    def parse_response(self, payload: bytes, device: DeviceIdentity) -> BatteryReading:
        if len(payload) != self.poll_protocol.report_length:
            raise ParseError(
                f"expected {self.poll_protocol.report_length} bytes, got {len(payload)}"
            )
        if self.poll_protocol.response_prefix and not payload.startswith(
            self.poll_protocol.response_prefix
        ):
            prefix = payload[: len(self.poll_protocol.response_prefix)].hex()
            raise ParseError(
                f"unexpected response prefix {prefix}, expected {self.poll_protocol.response_prefix.hex()}"
            )
        return self.response_mapping.parse(
            payload,
            transport_mode=self.transport_mode_for(device),
        )


def _map_charge_state(
    percentage: int,
    is_charging: bool | None,
    transport_mode: str,
) -> str:
    if transport_mode == TRANSPORT_MODE_WIRELESS:
        return CHARGE_STATE_DISCHARGING
    if transport_mode == TRANSPORT_MODE_WIRED:
        if is_charging is True:
            return CHARGE_STATE_CHARGING
        if percentage >= 100:
            return CHARGE_STATE_FULL
        if is_charging is False:
            return CHARGE_STATE_DISCHARGING
    return CHARGE_STATE_UNKNOWN


def _parse_profile(raw: dict[str, object]) -> BatteryProfile:
    try:
        match_raw = raw["match"]
        protocol_raw = raw["protocol"]
        response_raw = raw["response"]
    except KeyError as exc:
        raise ProfileError(f"missing section in profile: {exc}") from exc

    if not isinstance(match_raw, dict) or not isinstance(protocol_raw, dict) or not isinstance(response_raw, dict):
        raise ProfileError("profile sections must be tables")

    if "pids" in match_raw:
        pids = tuple(int(str(item), 16) for item in match_raw["pids"])
    else:
        pids = (int(str(match_raw["pid"]), 16),)

    return BatteryProfile(
        profile_id=str(raw["id"]),
        name=str(raw["name"]),
        match=DeviceMatchSpec(
            vid=int(str(match_raw["vid"]), 16),
            pids=pids,
            descriptor_fingerprint_hex=_normalize_hex(
                str(match_raw["report_descriptor_hex"])
            ),
            product_name_contains=(
                str(match_raw["product_name_contains"])
                if "product_name_contains" in match_raw
                else None
            ),
            transport_mode_by_pid={
                int(str(pid_hex), 16): str(mode)
                for pid_hex, mode in match_raw.get("transport_mode_by_pid", {}).items()
            }
            or None,
        ),
        poll_protocol=PollProtocol(
            mode=str(protocol_raw.get("mode", "feature_set_then_get")),
            report_length=int(protocol_raw["report_length"]),
            request_prefix=_decode_hex(str(protocol_raw["request_prefix_hex"])),
            response_prefix=_decode_hex(str(protocol_raw["response_prefix_hex"])),
            response_delay_ms=int(protocol_raw.get("response_delay_ms", 20)),
            poll_interval_seconds=float(protocol_raw.get("poll_interval_seconds", 30.0)),
            retry_response_prefixes=tuple(
                _decode_hex(str(item))
                for item in protocol_raw.get("retry_response_prefixes_hex", [])
            ),
            max_follow_up_gets=int(protocol_raw.get("max_follow_up_gets", 0)),
        ),
        response_mapping=ResponseMapping(
            percentage_index=int(response_raw["percentage_index"]),
            status_flag_index=(
                int(response_raw["status_flag_index"])
                if "status_flag_index" in response_raw
                else None
            ),
            status_flag_name=(
                str(response_raw["status_flag_name"])
                if "status_flag_name" in response_raw
                else None
            ),
            status_flag_semantics=str(
                response_raw.get("status_flag_semantics", "unknown")
            ),
            publish_charging_by_default=bool(
                response_raw.get("publish_charging_by_default", False)
            ),
        ),
        notes=[
            str(item)
            for item in response_raw.get("notes", raw.get("notes", []))
        ],
    )


def load_profile_file(path: Path) -> BatteryProfile:
    with path.open("rb") as handle:
        return _parse_profile(tomllib.load(handle))


def _builtin_profile_dirs() -> list[Path]:
    candidates: list[Path] = []

    try:
        resource_dir = resources.files("attackshark_battery_bridge").joinpath("profiles")
        resource_path = Path(str(resource_dir))
        candidates.append(resource_path)
    except Exception:
        pass

    module_dir = Path(__file__).resolve().parent
    candidates.append(module_dir / "profiles")

    mei_pass = getattr(sys, "_MEIPASS", None)
    if mei_pass:
        candidates.append(Path(mei_pass) / "attackshark_battery_bridge" / "profiles")

    unique_candidates: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            unique_candidates.append(candidate)
    return unique_candidates


def load_builtin_profiles() -> list[BatteryProfile]:
    for package_root in _builtin_profile_dirs():
        if not package_root.exists():
            continue
        profiles: list[BatteryProfile] = []
        for entry in sorted(package_root.iterdir(), key=lambda item: item.name):
            if entry.name.endswith(".toml") and entry.is_file():
                profiles.append(_parse_profile(tomllib.loads(entry.read_text())))
        if profiles:
            return profiles

    searched = ", ".join(str(path) for path in _builtin_profile_dirs())
    raise ProfileError(f"no built-in profile directory found; searched: {searched}")


def load_profiles(extra_dirs: list[Path] | None = None) -> list[BatteryProfile]:
    profiles = {profile.profile_id: profile for profile in load_builtin_profiles()}
    for directory in extra_dirs or []:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.toml")):
            profile = load_profile_file(path)
            profiles[profile.profile_id] = profile
    return list(profiles.values())
