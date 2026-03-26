from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


TRANSPORT_MODE_WIRED = "wired"
TRANSPORT_MODE_WIRELESS = "wireless"
TRANSPORT_MODE_UNKNOWN = "unknown"

CHARGE_STATE_CHARGING = "charging"
CHARGE_STATE_DISCHARGING = "discharging"
CHARGE_STATE_FULL = "full"
CHARGE_STATE_UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class DeviceIdentity:
    hidraw_name: str
    hidraw_path: Path
    sysfs_path: Path
    bus: int
    vendor_id: int
    product_id: int
    hid_name: str
    physical_path: str | None
    unique_id: str | None
    report_descriptor_hex: str

    @property
    def vid_pid(self) -> str:
        return f"{self.vendor_id:04x}:{self.product_id:04x}"


@dataclass(frozen=True, slots=True)
class BatteryReading:
    percentage: int
    raw_status_flag_name: str | None
    raw_status_flag_value: int | None
    is_charging: bool | None
    transport_mode: str
    charge_state: str
    observed_at: datetime

    @classmethod
    def now(
        cls,
        percentage: int,
        raw_status_flag_name: str | None,
        raw_status_flag_value: int | None,
        is_charging: bool | None,
        transport_mode: str,
        charge_state: str,
    ) -> "BatteryReading":
        return cls(
            percentage=percentage,
            raw_status_flag_name=raw_status_flag_name,
            raw_status_flag_value=raw_status_flag_value,
            is_charging=is_charging,
            transport_mode=transport_mode,
            charge_state=charge_state,
            observed_at=datetime.now(UTC),
        )


@dataclass(frozen=True, slots=True)
class DeviceBinding:
    profile_id: str
    profile_name: str
    device: DeviceIdentity
