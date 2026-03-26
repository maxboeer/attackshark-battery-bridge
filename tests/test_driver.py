from __future__ import annotations

import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from attackshark_battery_bridge.drivers.profile_driver import ProfileBatteryDriver
from attackshark_battery_bridge.models import DeviceIdentity
from attackshark_battery_bridge.profiles import load_builtin_profiles


class FakeTransport:
    def __init__(self, response: bytes | list[bytes]) -> None:
        self.responses = response if isinstance(response, list) else [response]
        self.calls: list[tuple[str, bytes, int, str, int]] = []

    def exchange(
        self,
        device_path: str,
        request: bytes,
        response_length: int,
        mode: str,
        response_delay_ms: int,
    ) -> bytes:
        self.calls.append((device_path, request, response_length, mode, response_delay_ms))
        if len(self.responses) == 1:
            return self.responses[0]
        return self.responses.pop(0)


class ProfileDriverTests(unittest.TestCase):
    def test_driver_parses_attack_shark_wireless_sample(self) -> None:
        profile = next(
            profile
            for profile in load_builtin_profiles()
            if profile.profile_id == "attack_shark_r5_ultra"
        )
        response = bytes.fromhex(
            "00 a1 00 02 02 00 83 00 60 " + "00 " * 56
        )
        driver = ProfileBatteryDriver(transport=FakeTransport(response))
        reading = driver.poll(
            device=DeviceIdentity(
                hidraw_name="hidraw9",
                hidraw_path=Path("/dev/hidraw9"),
                sysfs_path=Path("/sys/class/hidraw/hidraw9/device"),
                bus=0x0003,
                vendor_id=0x373E,
                product_id=0x0047,
                hid_name="Attack Shark R5 Ultra",
                physical_path=None,
                unique_id=None,
                report_descriptor_hex="06ffff0900a10109001500250175089540b102c0",
            ),
            profile=profile,
        )
        self.assertEqual(reading.percentage, 96)
        self.assertEqual(reading.raw_status_flag_value, 0)
        self.assertFalse(reading.is_charging)
        self.assertEqual(reading.transport_mode, "wireless")
        self.assertEqual(reading.charge_state, "discharging")

    def test_driver_parses_attack_shark_wired_charging_sample(self) -> None:
        profile = next(
            profile
            for profile in load_builtin_profiles()
            if profile.profile_id == "attack_shark_r5_ultra"
        )
        response = bytes.fromhex(
            "00 a1 00 02 02 00 83 01 5e " + "00 " * 56
        )
        driver = ProfileBatteryDriver(transport=FakeTransport(response))
        reading = driver.poll(
            device=DeviceIdentity(
                hidraw_name="hidraw17",
                hidraw_path=Path("/dev/hidraw17"),
                sysfs_path=Path("/sys/class/hidraw/hidraw17/device"),
                bus=0x0003,
                vendor_id=0x373E,
                product_id=0x0046,
                hid_name="Attack Shark R5 Ultra",
                physical_path=None,
                unique_id=None,
                report_descriptor_hex="06ffff0900a10109001500250175089540b102c0",
            ),
            profile=profile,
        )
        self.assertEqual(reading.percentage, 94)
        self.assertTrue(reading.is_charging)
        self.assertEqual(reading.transport_mode, "wired")
        self.assertEqual(reading.charge_state, "charging")

    def test_driver_parses_attack_shark_wired_full_sample(self) -> None:
        profile = next(
            profile
            for profile in load_builtin_profiles()
            if profile.profile_id == "attack_shark_r5_ultra"
        )
        response = bytes.fromhex(
            "00 a1 00 02 02 00 83 00 64 " + "00 " * 56
        )
        driver = ProfileBatteryDriver(transport=FakeTransport(response))
        reading = driver.poll(
            device=DeviceIdentity(
                hidraw_name="hidraw17",
                hidraw_path=Path("/dev/hidraw17"),
                sysfs_path=Path("/sys/class/hidraw/hidraw17/device"),
                bus=0x0003,
                vendor_id=0x373E,
                product_id=0x0046,
                hid_name="Attack Shark R5 Ultra",
                physical_path=None,
                unique_id=None,
                report_descriptor_hex="06ffff0900a10109001500250175089540b102c0",
            ),
            profile=profile,
        )
        self.assertEqual(reading.percentage, 100)
        self.assertFalse(reading.is_charging)
        self.assertEqual(reading.transport_mode, "wired")
        self.assertEqual(reading.charge_state, "full")

    def test_driver_parses_attack_shark_wired_discharging_sample(self) -> None:
        profile = next(
            profile
            for profile in load_builtin_profiles()
            if profile.profile_id == "attack_shark_r5_ultra"
        )
        response = bytes.fromhex(
            "00 a1 00 02 02 00 83 00 5e " + "00 " * 56
        )
        driver = ProfileBatteryDriver(transport=FakeTransport(response))
        reading = driver.poll(
            device=DeviceIdentity(
                hidraw_name="hidraw17",
                hidraw_path=Path("/dev/hidraw17"),
                sysfs_path=Path("/sys/class/hidraw/hidraw17/device"),
                bus=0x0003,
                vendor_id=0x373E,
                product_id=0x0046,
                hid_name="Attack Shark R5 Ultra",
                physical_path=None,
                unique_id=None,
                report_descriptor_hex="06ffff0900a10109001500250175089540b102c0",
            ),
            profile=profile,
        )
        self.assertEqual(reading.percentage, 94)
        self.assertFalse(reading.is_charging)
        self.assertEqual(reading.transport_mode, "wired")
        self.assertEqual(reading.charge_state, "discharging")

    def test_driver_retries_after_ack_response(self) -> None:
        profile = next(
            profile
            for profile in load_builtin_profiles()
            if profile.profile_id == "attack_shark_r5_ultra"
        )
        ack = bytes.fromhex(
            "00 a3 02 02 00 83 00 " + "00 " * 58
        )
        data = bytes.fromhex(
            "00 a1 00 02 02 00 83 00 62 " + "00 " * 56
        )
        transport = FakeTransport([ack, data])
        driver = ProfileBatteryDriver(transport=transport)
        reading = driver.poll(
            device=DeviceIdentity(
                hidraw_name="hidraw6",
                hidraw_path=Path("/dev/hidraw6"),
                sysfs_path=Path("/sys/class/hidraw/hidraw6/device"),
                bus=0x0003,
                vendor_id=0x373E,
                product_id=0x0047,
                hid_name="Attack Shark R5 Ultra Mouse 2.4G",
                physical_path=None,
                unique_id=None,
                report_descriptor_hex="06ffff0900a10109001500250175089540b102c0",
            ),
            profile=profile,
        )
        self.assertEqual(reading.percentage, 98)
        self.assertEqual(reading.charge_state, "discharging")
        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(transport.calls[0][3], "feature_set_then_get")
        self.assertEqual(transport.calls[1][3], "feature_get")


if __name__ == "__main__":
    unittest.main()
