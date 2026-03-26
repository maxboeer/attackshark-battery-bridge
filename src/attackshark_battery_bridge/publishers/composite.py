from __future__ import annotations

from attackshark_battery_bridge.models import BatteryReading, DeviceIdentity
from attackshark_battery_bridge.profiles import BatteryProfile
from attackshark_battery_bridge.publishers.base import Publisher


class CompositePublisher(Publisher):
    def __init__(self, publishers: list[Publisher]) -> None:
        self._publishers = publishers

    def attach(self, device: DeviceIdentity, profile: BatteryProfile) -> None:
        for publisher in self._publishers:
            publisher.attach(device, profile)

    def publish(
        self,
        device: DeviceIdentity,
        profile: BatteryProfile,
        reading: BatteryReading,
    ) -> None:
        for publisher in self._publishers:
            publisher.publish(device, profile, reading)

    def detach(self) -> None:
        for publisher in self._publishers:
            publisher.detach()

