from __future__ import annotations

from attackshark_battery_bridge.config import PublisherConfig
from attackshark_battery_bridge.publishers.base import Publisher
from attackshark_battery_bridge.publishers.composite import CompositePublisher
from attackshark_battery_bridge.publishers.json_status import JsonStatusPublisher
from attackshark_battery_bridge.publishers.uhid import UhidBatteryPublisher


def build_publisher(config: PublisherConfig) -> Publisher:
    backend = config.backend.lower()
    if backend == "uhid":
        return UhidBatteryPublisher(include_charging=config.include_charging)
    if backend == "json":
        return JsonStatusPublisher(config.json_status_path)
    if backend == "both":
        return CompositePublisher(
            [
                UhidBatteryPublisher(include_charging=config.include_charging),
                JsonStatusPublisher(config.json_status_path),
            ]
        )
    raise ValueError(f"unsupported publisher backend: {config.backend}")

