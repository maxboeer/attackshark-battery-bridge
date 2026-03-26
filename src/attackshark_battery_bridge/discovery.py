from __future__ import annotations

from pathlib import Path

from attackshark_battery_bridge.models import DeviceIdentity
from attackshark_battery_bridge.profiles import BatteryProfile


SYS_HIDRAW_ROOT = Path("/sys/class/hidraw")
DEV_HIDRAW_ROOT = Path("/dev")


def _parse_uevent(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        key, _, value = line.partition("=")
        if key:
            values[key] = value
    return values


def _parse_hid_id(raw: str) -> tuple[int, int, int]:
    bus_raw, vendor_raw, product_raw = raw.split(":")
    return int(bus_raw, 16), int(vendor_raw, 16), int(product_raw, 16)


def iter_hidraw_devices() -> list[DeviceIdentity]:
    devices: list[DeviceIdentity] = []
    if not SYS_HIDRAW_ROOT.exists():
        return devices

    for hidraw_dir in sorted(SYS_HIDRAW_ROOT.glob("hidraw*")):
        device_dir = (hidraw_dir / "device").resolve()
        uevent_path = device_dir / "uevent"
        descriptor_path = device_dir / "report_descriptor"
        if not uevent_path.exists() or not descriptor_path.exists():
            continue

        uevent = _parse_uevent(uevent_path)
        if "HID_ID" not in uevent:
            continue

        bus, vendor_id, product_id = _parse_hid_id(uevent["HID_ID"])
        report_descriptor_hex = descriptor_path.read_bytes().hex()
        hid_name = uevent.get("HID_NAME", hidraw_dir.name)

        devices.append(
            DeviceIdentity(
                hidraw_name=hidraw_dir.name,
                hidraw_path=DEV_HIDRAW_ROOT / hidraw_dir.name,
                sysfs_path=device_dir,
                bus=bus,
                vendor_id=vendor_id,
                product_id=product_id,
                hid_name=hid_name,
                physical_path=uevent.get("HID_PHYS"),
                unique_id=uevent.get("HID_UNIQ"),
                report_descriptor_hex=report_descriptor_hex,
            )
        )

    return devices


def find_first_matching_device(profile: BatteryProfile) -> DeviceIdentity | None:
    for device in iter_hidraw_devices():
        if profile.matches(device):
            return device
    return None


def find_all_matches(profiles: list[BatteryProfile]) -> list[tuple[BatteryProfile, DeviceIdentity]]:
    matches: list[tuple[BatteryProfile, DeviceIdentity]] = []
    devices = iter_hidraw_devices()
    for profile in profiles:
        for device in devices:
            if profile.matches(device):
                matches.append((profile, device))
    return matches

