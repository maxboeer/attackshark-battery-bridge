from __future__ import annotations

import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from attackshark_battery_bridge.config import AppConfig
from attackshark_battery_bridge.daemon.service import BridgeDaemon
from attackshark_battery_bridge.models import DeviceBinding, DeviceIdentity
from attackshark_battery_bridge.profiles import load_builtin_profiles
from attackshark_battery_bridge.publishers.json_status import JsonStatusPublisher


def _device(
    *,
    hidraw_name: str = "hidraw6",
    product_id: int = 0x0047,
    hid_name: str = "ATTACK SHARK R5 Ultra Mouse 2.4G",
) -> DeviceIdentity:
    return DeviceIdentity(
        hidraw_name=hidraw_name,
        hidraw_path=Path(f"/dev/{hidraw_name}"),
        sysfs_path=Path(f"/sys/class/hidraw/{hidraw_name}/device"),
        bus=0x0003,
        vendor_id=0x373E,
        product_id=product_id,
        hid_name=hid_name,
        physical_path=None,
        unique_id=None,
        report_descriptor_hex="06ffff0900a10109001500250175089540b102c0",
    )


class _RecordingPublisher:
    def __init__(self) -> None:
        self.attach_calls: list[tuple[DeviceIdentity, str]] = []
        self.detach_calls = 0

    def attach(self, device: DeviceIdentity, profile) -> None:
        self.attach_calls.append((device, profile.profile_id))

    def detach(self) -> None:
        self.detach_calls += 1


class _RecordingMonitor:
    def __init__(self, responses: list[bool] | None = None) -> None:
        self.responses = list(responses or [])
        self.wait_calls: list[float] = []

    def wait(self, timeout_seconds: float) -> bool:
        self.wait_calls.append(timeout_seconds)
        if not self.responses:
            return False
        return self.responses.pop(0)


class BridgeDaemonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = next(
            profile
            for profile in load_builtin_profiles()
            if profile.profile_id == "attack_shark_r5_ultra"
        )
        self.publisher = _RecordingPublisher()
        self.monitor = _RecordingMonitor()
        self.daemon = BridgeDaemon(
            config=AppConfig(),
            profiles=[self.profile],
            publisher=self.publisher,
            event_monitor=self.monitor,
        )

    def test_refresh_binding_rebinds_when_device_identity_changes(self) -> None:
        active = DeviceBinding(
            profile_id=self.profile.profile_id,
            profile_name=self.profile.name,
            device=_device(product_id=0x0047),
        )
        refreshed_device = _device(product_id=0x0046, hid_name="ATTACK SHARK R5 Ultra Mouse Wired")

        with patch(
            "attackshark_battery_bridge.daemon.service.find_first_matching_device",
            return_value=refreshed_device,
        ):
            refreshed = self.daemon._refresh_binding(active, self.profile)

        self.assertIsNotNone(refreshed)
        assert refreshed is not None
        self.assertEqual(refreshed.device.product_id, 0x0046)
        self.assertEqual(len(self.publisher.attach_calls), 0)
        self.assertEqual(self.publisher.detach_calls, 0)

    def test_refresh_binding_detaches_when_device_disappears(self) -> None:
        active = DeviceBinding(
            profile_id=self.profile.profile_id,
            profile_name=self.profile.name,
            device=_device(product_id=0x0047),
        )

        with patch(
            "attackshark_battery_bridge.daemon.service.find_first_matching_device",
            return_value=None,
        ):
            refreshed = self.daemon._refresh_binding(active, self.profile)

        self.assertIsNone(refreshed)
        self.assertEqual(self.publisher.detach_calls, 1)

    def test_wait_loop_polls_on_timeout_without_extra_rebind(self) -> None:
        active = DeviceBinding(
            profile_id=self.profile.profile_id,
            profile_name=self.profile.name,
            device=_device(product_id=0x0047),
        )

        with (
            patch.object(self.daemon, "_refresh_binding", return_value=active),
            patch("attackshark_battery_bridge.daemon.service.time.monotonic", return_value=10.0),
        ):
            refreshed, should_poll = self.daemon._await_next_poll_or_device_change(
                active,
                self.profile,
                next_poll_at=25.0,
            )

        self.assertEqual(refreshed, active)
        self.assertTrue(should_poll)
        self.assertEqual(self.monitor.wait_calls, [15.0])

    def test_wait_loop_polls_immediately_after_kernel_event_rebind(self) -> None:
        wireless = DeviceBinding(
            profile_id=self.profile.profile_id,
            profile_name=self.profile.name,
            device=_device(product_id=0x0047),
        )
        wired = DeviceBinding(
            profile_id=self.profile.profile_id,
            profile_name=self.profile.name,
            device=_device(product_id=0x0046, hid_name="ATTACK SHARK R5 Ultra Mouse"),
        )
        self.monitor.responses = [True]

        with (
            patch.object(self.daemon, "_refresh_binding", side_effect=[wireless, wired]),
            patch("attackshark_battery_bridge.daemon.service.time.monotonic", return_value=10.0),
        ):
            refreshed, should_poll = self.daemon._await_next_poll_or_device_change(
                wireless,
                self.profile,
                next_poll_at=70.0,
            )

        self.assertEqual(refreshed, wired)
        self.assertTrue(should_poll)
        self.assertEqual(self.monitor.wait_calls, [60.0])

    def test_bind_device_returns_match_without_preattaching_publisher(self) -> None:
        wireless = _device(product_id=0x0047)

        with patch(
            "attackshark_battery_bridge.daemon.service.find_first_matching_device",
            return_value=wireless,
        ):
            binding = self.daemon._bind_device()

        self.assertIsNotNone(binding)
        assert binding is not None
        self.assertEqual(binding.device, wireless)
        self.assertEqual(self.publisher.attach_calls, [])


class JsonStatusPublisherTests(unittest.TestCase):
    def test_detach_removes_status_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "status.json"
            output_path.write_text("{}\n", encoding="utf-8")

            publisher = JsonStatusPublisher(output_path=output_path)
            publisher.detach()

            self.assertFalse(output_path.exists())


if __name__ == "__main__":
    unittest.main()
