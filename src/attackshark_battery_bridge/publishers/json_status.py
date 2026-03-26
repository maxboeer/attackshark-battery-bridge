from __future__ import annotations

import json
from pathlib import Path
import tempfile

from attackshark_battery_bridge.models import BatteryReading, DeviceIdentity
from attackshark_battery_bridge.profiles import BatteryProfile
from attackshark_battery_bridge.publishers.base import Publisher


class JsonStatusPublisher(Publisher):
    def __init__(self, output_path: Path) -> None:
        self._output_path = output_path

    def publish(
        self,
        device: DeviceIdentity,
        profile: BatteryProfile,
        reading: BatteryReading,
    ) -> None:
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "profile_id": profile.profile_id,
            "profile_name": profile.name,
            "device": {
                "hidraw": str(device.hidraw_path),
                "hid_name": device.hid_name,
                "vid_pid": device.vid_pid,
            },
            "battery": {
                "percentage": reading.percentage,
                "is_charging": reading.is_charging,
                "transport_mode": reading.transport_mode,
                "charge_state": reading.charge_state,
                "raw_status_flag_name": reading.raw_status_flag_name,
                "raw_status_flag_value": reading.raw_status_flag_value,
                "observed_at": reading.observed_at.isoformat(),
            },
        }

        with tempfile.NamedTemporaryFile(
            "w",
            dir=self._output_path.parent,
            encoding="utf-8",
            delete=False,
        ) as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            temp_path = Path(handle.name)

        temp_path.replace(self._output_path)

    def detach(self) -> None:
        try:
            self._output_path.unlink()
        except FileNotFoundError:
            return
