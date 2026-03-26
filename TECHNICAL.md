# Technical README

## Overview

`attackshark-battery-bridge` is a profile-driven Linux daemon that reads proprietary battery reports from `hidraw` and republishes them through a standard HID battery path.

The first supported target is the Attack Shark R5 Ultra.

## Architecture

The codebase is split into five layers:

- `discovery`: finds the correct `hidraw` node by VID/PID, descriptor fingerprint, and product metadata
- `transport/hidraw`: performs the Linux feature-report exchange
- `drivers`: maps profile-defined requests and responses to a canonical battery model
- `publishers`: republishes battery state through `UHID` and optional JSON status output
- `daemon`: coordinates binding, event-driven reconnects, polling cadence, and lifecycle

## Canonical state model

- `percentage`
- `is_charging`
- `transport_mode`: `wired` or `wireless`
- `charge_state`: `charging`, `discharging`, or `full`

## Publication strategy

The standardized publication path in v1 is `UHID`.

That keeps the bridge on the generic Linux path:

- proprietary mouse battery data is read from `hidraw`
- a virtual HID battery device is exposed through `UHID`
- the kernel surfaces that through `power_supply`
- user space consumes it through UPower and desktop battery tooling

## Verified device state

Verified for the Attack Shark R5 Ultra:

- wireless / dongle PID: `373e:0047`
- wired PID: `373e:0046`
- battery-channel descriptor fingerprint: `06ffff0900a10109001500250175089540b102c0`
- request prefix: `00 00 00 02 02 00 83`
- `raw[8]`: percentage
- `raw[7]`: charging-active flag

Current state mapping:

- wireless (`0047`) -> `discharging`
- wired (`0046`) + `raw[7] == 1` -> `charging`
- wired (`0046`) + `raw[7] == 0` + `raw[8] == 100` -> `full`
- wired (`0046`) + `raw[7] == 0` + `raw[8] < 100` -> `discharging`

## Runtime behavior

- device appearance, disappearance, and wired/wireless mode switches are detected through kernel uevents
- the battery readout is event-driven for rebinding and time-driven for polling
- the current R5 Ultra profile polls at 60-second intervals

## Build and install

Single-file local build:

```bash
./scripts/build-singlefile.sh
```

Manual install from a built binary:

```bash
sudo ./scripts/install.sh dist/attackshark-battery-bridge
sudo systemctl enable --now attackshark-battery-bridge.service
```

The repository also contains release automation for GitHub releases and AUR package metadata updates.
