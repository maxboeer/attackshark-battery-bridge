class BatteryBridgeError(Exception):
    """Base exception for the bridge."""


class ProfileError(BatteryBridgeError):
    """Raised when a device profile is invalid."""


class DiscoveryError(BatteryBridgeError):
    """Raised when discovery cannot inspect hidraw devices."""


class TransportError(BatteryBridgeError):
    """Raised when hidraw transport fails."""


class ParseError(BatteryBridgeError):
    """Raised when a device response cannot be parsed."""

