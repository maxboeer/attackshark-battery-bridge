from __future__ import annotations

import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from attackshark_battery_bridge.cli import _build_parser


class CliTests(unittest.TestCase):
    def test_config_before_subcommand_is_accepted(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(
            ["--config", "/etc/attackshark-battery-bridge/config.toml", "serve"]
        )
        self.assertEqual(args.command, "serve")
        self.assertEqual(
            args.config,
            Path("/etc/attackshark-battery-bridge/config.toml"),
        )

    def test_config_after_subcommand_is_accepted(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(
            ["serve", "--config", "/etc/attackshark-battery-bridge/config.toml"]
        )
        self.assertEqual(args.command, "serve")
        self.assertEqual(
            args.config,
            Path("/etc/attackshark-battery-bridge/config.toml"),
        )


if __name__ == "__main__":
    unittest.main()
