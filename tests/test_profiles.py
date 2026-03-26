from __future__ import annotations

import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from attackshark_battery_bridge.exceptions import ParseError
from attackshark_battery_bridge.profiles import load_builtin_profiles


class ProfileTests(unittest.TestCase):
    def test_attack_shark_profile_loads(self) -> None:
        profile = next(
            profile
            for profile in load_builtin_profiles()
            if profile.profile_id == "attack_shark_r5_ultra"
        )
        self.assertEqual(profile.match.vid, 0x373E)
        self.assertEqual(profile.match.pids, (0x0046, 0x0047))
        self.assertEqual(
            profile.match.transport_mode_by_pid,
            {0x0046: "wired", 0x0047: "wireless"},
        )
        self.assertEqual(profile.poll_protocol.report_length, 65)
        self.assertEqual(profile.build_request()[:7].hex(), "00000002020083")

    def test_response_prefix_is_enforced(self) -> None:
        profile = next(
            profile
            for profile in load_builtin_profiles()
            if profile.profile_id == "attack_shark_r5_ultra"
        )
        with self.assertRaises(ParseError):
            profile.parse_response(
                bytes(65),
                device=type(
                    "Device",
                    (),
                    {
                        "product_id": 0x0047,
                    },
                )(),
            )


if __name__ == "__main__":
    unittest.main()
