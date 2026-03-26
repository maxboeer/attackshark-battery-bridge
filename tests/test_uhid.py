from __future__ import annotations

import struct
import sys
from pathlib import Path
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from attackshark_battery_bridge.models import DeviceIdentity
from attackshark_battery_bridge.models import BatteryReading
from attackshark_battery_bridge.publishers.uhid import (
    UHID_CREATE2_FORMAT,
    UHID_EVENT_MAX_SIZE,
    _build_create2_event,
    _device_uniq,
    _build_report_descriptor,
    UhidBatteryPublisher,
)


class UhidTests(unittest.TestCase):
    def test_create2_event_has_expected_size(self) -> None:
        device = DeviceIdentity(
            hidraw_name="hidraw6",
            hidraw_path=Path("/dev/hidraw6"),
            sysfs_path=Path("/sys/class/hidraw/hidraw6/device"),
            bus=0x0003,
            vendor_id=0x373E,
            product_id=0x0047,
            hid_name="ATTACK SHARK R5 Ultra Mouse 2.4G",
            physical_path=None,
            unique_id=None,
            report_descriptor_hex="06ffff0900a10109001500250175089540b102c0",
        )
        descriptor = _build_report_descriptor(include_charging=True)
        event = _build_create2_event(device, descriptor)
        self.assertEqual(len(event), struct.calcsize(UHID_CREATE2_FORMAT))
        self.assertLessEqual(len(event), UHID_EVENT_MAX_SIZE)

    def test_descriptor_contains_battery_and_anchor_collections(self) -> None:
        descriptor = _build_report_descriptor(include_charging=True)
        self.assertIn(bytes.fromhex("058405850965"), descriptor)
        self.assertIn(bytes.fromhex("05010902a1010901a1008502"), descriptor)

    def test_payload_layout_matches_battery_collection(self) -> None:
        publisher = UhidBatteryPublisher(include_charging=True)
        payload = publisher._build_report_payload(percentage=95, is_charging=False)
        self.assertEqual(payload[0], 1)
        self.assertEqual(payload[3], 95)
        self.assertEqual(payload[4], 0)
        self.assertEqual(len(payload), 12)

    def test_attach_recreates_virtual_device_when_identity_changes_on_same_hidraw(self) -> None:
        wireless_device = DeviceIdentity(
            hidraw_name="hidraw6",
            hidraw_path=Path("/dev/hidraw6"),
            sysfs_path=Path("/sys/class/hidraw/hidraw6/device"),
            bus=0x0003,
            vendor_id=0x373E,
            product_id=0x0047,
            hid_name="ATTACK SHARK R5 Ultra Mouse 2.4G",
            physical_path=None,
            unique_id=None,
            report_descriptor_hex="06ffff0900a10109001500250175089540b102c0",
        )
        wired_device = DeviceIdentity(
            hidraw_name="hidraw6",
            hidraw_path=Path("/dev/hidraw6"),
            sysfs_path=Path("/sys/class/hidraw/hidraw6/device"),
            bus=0x0003,
            vendor_id=0x373E,
            product_id=0x0046,
            hid_name="ATTACK SHARK R5 Ultra Mouse Wired",
            physical_path=None,
            unique_id=None,
            report_descriptor_hex="06ffff0900a10109001500250175089540b102c0",
        )
        profile = type("Profile", (), {"profile_id": "attack_shark_r5_ultra"})()
        publisher = UhidBatteryPublisher(include_charging=True)

        with (
            patch("attackshark_battery_bridge.publishers.uhid.os.open", side_effect=[10, 11]) as open_mock,
            patch("attackshark_battery_bridge.publishers.uhid.os.write") as write_mock,
            patch("attackshark_battery_bridge.publishers.uhid.os.close") as close_mock,
            patch.object(publisher, "_drain_events"),
            patch.object(publisher, "_wait_until_ready", return_value=True),
        ):
            publisher.attach(wireless_device, profile)
            publisher.attach(wired_device, profile)

        self.assertEqual(open_mock.call_count, 2)
        close_mock.assert_called_once_with(10)
        self.assertGreaterEqual(write_mock.call_count, 3)

    def test_publish_sets_current_report_before_attach(self) -> None:
        device = DeviceIdentity(
            hidraw_name="hidraw6",
            hidraw_path=Path("/dev/hidraw6"),
            sysfs_path=Path("/sys/class/hidraw/hidraw6/device"),
            bus=0x0003,
            vendor_id=0x373E,
            product_id=0x0047,
            hid_name="ATTACK SHARK R5 Ultra Mouse 2.4G",
            physical_path=None,
            unique_id=None,
            report_descriptor_hex="06ffff0900a10109001500250175089540b102c0",
        )
        profile = type("Profile", (), {"profile_id": "attack_shark_r5_ultra"})()
        reading = BatteryReading.now(
            percentage=87,
            raw_status_flag_name="charging_active_flag",
            raw_status_flag_value=0,
            is_charging=False,
            transport_mode="wireless",
            charge_state="discharging",
        )
        publisher = UhidBatteryPublisher(include_charging=True)
        expected_report = publisher._build_report_payload(percentage=87, is_charging=False)
        seen_report: bytes | None = None

        def fake_attach(*_args) -> None:
            nonlocal seen_report
            seen_report = publisher._current_report
            publisher._fd = 10

        with (
            patch.object(publisher, "attach", side_effect=fake_attach),
            patch.object(publisher, "_wait_until_ready", return_value=True),
            patch.object(publisher, "_drain_events"),
            patch("attackshark_battery_bridge.publishers.uhid.os.write"),
        ):
            publisher.publish(device, profile, reading)

        self.assertEqual(seen_report, expected_report)

    def test_device_uniq_uses_fallback_without_unique_id(self) -> None:
        device = DeviceIdentity(
            hidraw_name="hidraw6",
            hidraw_path=Path("/dev/hidraw6"),
            sysfs_path=Path("/sys/class/hidraw/hidraw6/device"),
            bus=0x0003,
            vendor_id=0x373E,
            product_id=0x0047,
            hid_name="ATTACK SHARK R5 Ultra Mouse 2.4G",
            physical_path=None,
            unique_id=None,
            report_descriptor_hex="06ffff0900a10109001500250175089540b102c0",
        )
        self.assertEqual(_device_uniq(device), "373e:0047:hidraw6")

    def test_wait_until_ready_requires_start_and_registered_device(self) -> None:
        publisher = UhidBatteryPublisher(include_charging=True)
        publisher._fd = 10
        publisher._active_uniq = "373e:0047:hidraw6"
        start_event = struct.pack("<I", 2).ljust(UHID_EVENT_MAX_SIZE, b"\x00")

        with (
            patch("attackshark_battery_bridge.publishers.uhid.select.select", return_value=([10], [], [])),
            patch(
                "attackshark_battery_bridge.publishers.uhid.os.read",
                side_effect=[start_event, BlockingIOError(), BlockingIOError()],
            ),
            patch.object(publisher, "_virtual_device_registered", side_effect=[False, True]),
        ):
            self.assertTrue(publisher._wait_until_ready(0.1))


if __name__ == "__main__":
    unittest.main()
