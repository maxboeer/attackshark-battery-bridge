from __future__ import annotations

import logging
import time

from attackshark_battery_bridge.config import AppConfig
from attackshark_battery_bridge.daemon.uevent import KernelDeviceEventMonitor
from attackshark_battery_bridge.discovery import find_first_matching_device
from attackshark_battery_bridge.drivers.profile_driver import ProfileBatteryDriver
from attackshark_battery_bridge.exceptions import BatteryBridgeError
from attackshark_battery_bridge.models import DeviceBinding
from attackshark_battery_bridge.profiles import BatteryProfile
from attackshark_battery_bridge.publishers.base import Publisher


LOG = logging.getLogger(__name__)


class BridgeDaemon:
    def __init__(
        self,
        config: AppConfig,
        profiles: list[BatteryProfile],
        publisher: Publisher,
        event_monitor: KernelDeviceEventMonitor | None = None,
    ) -> None:
        self._config = config
        self._profiles = profiles
        self._publisher = publisher
        self._driver = ProfileBatteryDriver()
        self._event_monitor = event_monitor or KernelDeviceEventMonitor()

    def run(self) -> int:
        active: DeviceBinding | None = None
        next_poll_at = 0.0

        while True:
            if active is None:
                active = self._bind_device()
                if active is None:
                    self._event_monitor.wait(self._config.daemon.scan_interval_seconds)
                    continue
                LOG.info(
                    "Bound profile %s to %s (%s)",
                    active.profile_id,
                    active.device.hidraw_path,
                    active.device.hid_name,
                )
                next_poll_at = 0.0

            profile = self._profile_by_id(active.profile_id)
            active, should_poll = self._await_next_poll_or_device_change(
                active,
                profile,
                next_poll_at,
            )
            if active is None:
                next_poll_at = 0.0
                continue
            if not should_poll:
                continue

            try:
                reading = self._driver.poll(
                    device=active.device,
                    profile=profile,
                )
                self._publisher.publish(active.device, profile, reading)
                LOG.info(
                    "Battery %s%% state=%s mode=%s from %s on %s",
                    reading.percentage,
                    reading.charge_state,
                    reading.transport_mode,
                    active.profile_id,
                    active.device.hidraw_path,
                )
                next_poll_at = time.monotonic() + max(
                    profile.poll_protocol.poll_interval_seconds,
                    1.0,
                )
            except BatteryBridgeError as exc:
                LOG.warning("Polling failed for %s: %s", active.device.hidraw_path, exc)
                self._publisher.detach()
                active = None
                next_poll_at = 0.0
                self._event_monitor.wait(self._config.daemon.scan_interval_seconds)
            except OSError as exc:
                LOG.warning("Device %s disappeared: %s", active.device.hidraw_path, exc)
                self._publisher.detach()
                active = None
                next_poll_at = 0.0
                self._event_monitor.wait(self._config.daemon.scan_interval_seconds)

    def _await_next_poll_or_device_change(
        self,
        active: DeviceBinding,
        profile: BatteryProfile,
        next_poll_at: float,
    ) -> tuple[DeviceBinding | None, bool]:
        while True:
            refreshed = self._refresh_binding(active, profile)
            if refreshed is None:
                return None, False

            binding_changed = refreshed.device != active.device
            active = refreshed
            if binding_changed:
                return active, True

            now = time.monotonic()
            if next_poll_at <= now:
                return active, True

            if not self._event_monitor.wait(next_poll_at - now):
                return active, True

    def _refresh_binding(
        self,
        active: DeviceBinding,
        profile: BatteryProfile,
    ) -> DeviceBinding | None:
        current_device = find_first_matching_device(profile)
        if current_device is None:
            LOG.info(
                "No matching device for profile %s is currently present; detaching publishers",
                active.profile_id,
            )
            self._publisher.detach()
            return None

        if current_device == active.device:
            return active

        LOG.info(
            "Rebound profile %s from %s (%s, %s) to %s (%s, %s)",
            active.profile_id,
            active.device.hidraw_path,
            active.device.hid_name,
            active.device.vid_pid,
            current_device.hidraw_path,
            current_device.hid_name,
            current_device.vid_pid,
        )
        return DeviceBinding(
            profile_id=active.profile_id,
            profile_name=active.profile_name,
            device=current_device,
        )

    def _bind_device(self) -> DeviceBinding | None:
        for profile in self._profiles:
            device = find_first_matching_device(profile)
            if device is None:
                continue
            return DeviceBinding(
                profile_id=profile.profile_id,
                profile_name=profile.name,
                device=device,
            )
        return None

    def _profile_by_id(self, profile_id: str) -> BatteryProfile:
        for profile in self._profiles:
            if profile.profile_id == profile_id:
                return profile
        raise LookupError(profile_id)
