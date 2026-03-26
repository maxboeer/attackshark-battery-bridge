from __future__ import annotations

from attackshark_battery_bridge.models import BatteryReading, DeviceIdentity
from attackshark_battery_bridge.profiles import BatteryProfile


class Publisher:
    def attach(self, device: DeviceIdentity, profile: BatteryProfile) -> None:
        return None

    def publish(
        self,
        device: DeviceIdentity,
        profile: BatteryProfile,
        reading: BatteryReading,
    ) -> None:
        raise NotImplementedError

    def detach(self) -> None:
        return None

