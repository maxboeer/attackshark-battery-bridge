# attackshark-battery-bridge

`attackshark-battery-bridge` is a system daemon that polls proprietary mouse battery data from `hidraw` and republishes it through a standard Linux HID battery path so `power_supply`, UPower, and battery widgets can consume it.

## v1 architecture

The v1 is intentionally split into five layers:

- `discovery`: scans `/sys/class/hidraw`, fingerprints the correct node by VID/PID and report descriptor, infers `transport_mode` from PID, and rebinds after replug or mode changes.
- `transport/hidraw`: performs the Linux `hidraw` feature-report exchange without hardcoded `/dev/hidrawX` paths.
- `drivers`: runs a generic profile-driven battery poller based on a per-device TOML profile and maps the raw report to a canonical state model.
- `publishers`: republishes the battery state. The primary backend is `UHID`, which exposes a virtual HID battery device that the kernel can surface through `power_supply`. A JSON status publisher is included for validation and debugging.
- `daemon`: coordinates discovery, event-driven reconnects, periodic polling, logging, and lifecycle.

The internal canonical battery state in v1 is:

- `percentage`
- `is_charging`
- `transport_mode` as `wired` or `wireless`
- `charge_state` as `charging`, `discharging`, or `full`

## Why UHID in v1

The preferred standardized path in v1 is `UHID`, because the Linux HID stack already maps standard battery usages such as `AbsoluteStateOfCharge` and `Charging` into `power_supply`, which is what UPower consumes. That keeps the bridge out of desktop-specific code and makes installation and uninstallation clean.

The JSON publisher is not the main publication path. It exists to make reverse-engineering and field validation easier.

Current limitation:

- the bridge keeps a cleaner three-state public model, but the generic HID battery publication path is still centered on capacity plus charging-bit semantics. The JSON publisher preserves the bridge state used by the daemon.

## Repository structure

```text
.
├── main.py
├── pyproject.toml
├── scripts/
│   ├── build-singlefile.sh
│   ├── install.sh
│   └── uninstall.sh
├── src/attackshark_battery_bridge/
│   ├── cli.py
│   ├── config.py
│   ├── discovery.py
│   ├── daemon/
│   │   ├── service.py
│   │   └── uevent.py
│   ├── drivers/
│   │   └── profile_driver.py
│   ├── profiles/
│   │   └── attack_shark_r5_ultra.toml
│   ├── publishers/
│   │   ├── base.py
│   │   ├── composite.py
│   │   ├── factory.py
│   │   ├── json_status.py
│   │   └── uhid.py
│   └── transport/
│       └── hidraw.py
├── systemd/
│   └── attackshark-battery-bridge.service
└── tests/
    ├── test_driver.py
    └── test_profiles.py
```

## What is verified vs assumed

Verified for the Attack Shark R5 Ultra profile:

- device identities:
  - wireless / dongle: `373e:0047`
  - wired / cable: `373e:0046`
- relevant feature-channel descriptor fingerprint: `06ffff0900a10109001500250175089540b102c0`
- full 65-byte battery query buffer starts with: `00 00 00 02 02 00 83`
- response semantics:
  - `raw[8]`: battery percentage
  - `raw[7]`: charging-active flag
- transport mode comes from PID, not from `raw[7]`
- observed on 2026-03-26 in a live local probe: the wireless path on `/dev/hidraw6` returned `98%`

Current assumptions, kept explicit in code and config:

- a transient `a3` response may appear before the battery payload; the driver now retries with follow-up `GFEATURE` reads
- `root` is the default service model in v1 because it simplifies access to `/dev/hidraw*`, `/dev/uhid`, and kernel uevent monitoring
- the same descriptor fingerprint identifies the proprietary battery channel for both wired and wireless modes

Runtime behavior in the current daemon:

- device appearance, disappearance, and wired/wireless mode switches are picked up via kernel uevents and trigger an immediate rebind
- the battery feature report is only polled on the normal device cadence, which is currently once every 60 seconds for the Attack Shark R5 Ultra profile

## State mapping

The current v1 state machine maps the Attack Shark reports as follows:

- wireless (`0047`) -> `discharging`
- wired (`0046`) + `raw[7] == 1` -> `charging`
- wired (`0046`) + `raw[7] == 0` + `raw[8] == 100` -> `full`
- wired (`0046`) + `raw[7] == 0` + `raw[8] < 100` -> `discharging`

## Running from source

```bash
./.venv/bin/python -m unittest discover -s tests -v
./.venv/bin/python main.py list-devices
./.venv/bin/python main.py serve --config packaging/config.example.toml
```

## Building a single-file executable

The repository includes a PyInstaller build script that uses the existing `.venv`:

```bash
./scripts/build-singlefile.sh
```

PyInstaller is declared as an optional build dependency in `pyproject.toml`, but it is not installed automatically.

## Installing as a system service

```bash
./scripts/install.sh dist/attackshark-battery-bridge
sudo systemctl enable --now attackshark-battery-bridge.service
```

## Open decisions to confirm

- whether v1 should remain root-only or ship an immediate `udev`-rule path
- whether the first release should target Arch first or generic systemd distributions from the start
- which license the project should use
