# attackshark-battery-bridge

`attackshark-battery-bridge` is a Linux daemon that reads proprietary battery data from supported HID mice and republishes it through the standard Linux battery path.

The current implementation targets the Attack Shark R5 Ultra and exposes its battery status in a form that can be consumed by `power_supply`, UPower, KDE Power Management, and battery widgets.

## Support

- Attack Shark R5 Ultra
- wireless / dongle mode: `373e:0047`
- wired mode: `373e:0046`

## Installation

### GitHub release binary

Published releases include a Linux onefile binary asset:

```text
attackshark-battery-bridge-linux-x86_64
```

Manual installation:

```bash
sudo ./scripts/install.sh ./attackshark-battery-bridge-linux-x86_64
sudo systemctl enable --now attackshark-battery-bridge.service
```

### AUR

The repository contains packaging for the `attackshark-battery-bridge` AUR package. Once published:

```bash
yay -S attackshark-battery-bridge
sudo systemctl enable --now attackshark-battery-bridge.service
```

## Configuration

The default config path is:

```text
/etc/attackshark-battery-bridge/config.toml
```

## Uninstall

```bash
sudo ./scripts/uninstall.sh
```

The uninstall flow removes the binary and service file and leaves the config directory intact.

## Documentation

- [TECHNICAL.md](TECHNICAL.md): architecture, reverse-engineering notes, profile model, release automation
- [packaging/aur/README.md](packaging/aur/README.md): AUR packaging and release-to-AUR sync
