from __future__ import annotations

import fcntl
import os
import time

from attackshark_battery_bridge.exceptions import TransportError


_IOC_NRBITS = 8
_IOC_TYPEBITS = 8
_IOC_SIZEBITS = 14
_IOC_DIRBITS = 2

_IOC_NRSHIFT = 0
_IOC_TYPESHIFT = _IOC_NRSHIFT + _IOC_NRBITS
_IOC_SIZESHIFT = _IOC_TYPESHIFT + _IOC_TYPEBITS
_IOC_DIRSHIFT = _IOC_SIZESHIFT + _IOC_SIZEBITS

_IOC_WRITE = 1
_IOC_READ = 2


def _ioc(direction: int, type_char: str, number: int, size: int) -> int:
    return (
        (direction << _IOC_DIRSHIFT)
        | (ord(type_char) << _IOC_TYPESHIFT)
        | (number << _IOC_NRSHIFT)
        | (size << _IOC_SIZESHIFT)
    )


def hidiocsfeature(length: int) -> int:
    return _ioc(_IOC_WRITE | _IOC_READ, "H", 0x06, length)


def hidiocgfeature(length: int) -> int:
    return _ioc(_IOC_WRITE | _IOC_READ, "H", 0x07, length)


class HidrawFeatureTransport:
    def exchange(
        self,
        device_path: str,
        request: bytes,
        response_length: int,
        mode: str,
        response_delay_ms: int,
    ) -> bytes:
        if len(request) != response_length:
            raise TransportError("request length must match response length")

        try:
            fd = os.open(device_path, os.O_RDWR | os.O_CLOEXEC)
        except OSError as exc:
            raise TransportError(f"failed to open {device_path}: {exc}") from exc

        try:
            if mode == "feature_set_then_get":
                request_buffer = bytearray(request)
                fcntl.ioctl(fd, hidiocsfeature(len(request_buffer)), request_buffer, True)
                if response_delay_ms > 0:
                    time.sleep(response_delay_ms / 1000.0)
                response_buffer = bytearray(request)
                fcntl.ioctl(fd, hidiocgfeature(len(response_buffer)), response_buffer, True)
                return bytes(response_buffer)

            if mode == "feature_get":
                response_buffer = bytearray(request)
                fcntl.ioctl(fd, hidiocgfeature(len(response_buffer)), response_buffer, True)
                return bytes(response_buffer)

            raise TransportError(f"unsupported hidraw mode: {mode}")
        except OSError as exc:
            raise TransportError(f"hidraw feature exchange failed on {device_path}: {exc}") from exc
        finally:
            os.close(fd)

