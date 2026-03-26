from __future__ import annotations

import errno
import logging
import os
from pathlib import Path
import select
import struct
import time
from typing import Final

from attackshark_battery_bridge.models import BatteryReading, DeviceIdentity
from attackshark_battery_bridge.profiles import BatteryProfile
from attackshark_battery_bridge.publishers.base import Publisher


LOG = logging.getLogger(__name__)

UHID_PATH: Final[str] = "/dev/uhid"
UHID_DESTROY: Final[int] = 1
UHID_START: Final[int] = 2
UHID_STOP: Final[int] = 3
UHID_OPEN: Final[int] = 4
UHID_CLOSE: Final[int] = 5
UHID_GET_REPORT: Final[int] = 9
UHID_GET_REPORT_REPLY: Final[int] = 10
UHID_CREATE2: Final[int] = 11
UHID_INPUT2: Final[int] = 12
UHID_SET_REPORT: Final[int] = 13
UHID_SET_REPORT_REPLY: Final[int] = 14

UHID_INPUT_REPORT: Final[int] = 2
UHID_EVENT_MAX_SIZE: Final[int] = 4380
UHID_INPUT2_DATA_SIZE: Final[int] = 4096
UHID_REPORT_ID: Final[int] = 1
UHID_CREATE2_FORMAT: Final[str] = "<I128s64s64sHHIIII4096s"
SYS_HID_DEVICE_ROOT: Final[Path] = Path("/sys/bus/hid/devices")
UHID_READY_TIMEOUT_SECONDS: Final[float] = 0.25


def _encode_string(value: str, length: int) -> bytes:
    return value.encode("utf-8", "ignore")[: length - 1].ljust(length, b"\x00")


def _device_uniq(device: DeviceIdentity) -> str:
    return device.unique_id or f"{device.vendor_id:04x}:{device.product_id:04x}:{device.hidraw_name}"


def _build_report_descriptor(include_charging: bool) -> bytes:
    descriptor = bytearray(
        [
            0x05,
            0x01,
            0x09,
            0x07,
            0xA1,
            0x01,
            0x85,
            UHID_REPORT_ID,
            0x75,
            0x08,
            0x95,
            0x02,
            0x81,
            0x01,
            0x05,
            0x84,
            0x05,
            0x85,
            0x09,
            0x65,
            0x15,
            0x00,
            0x26,
            0x64,
            0x00,
            0x75,
            0x08,
            0x95,
            0x01,
            0x81,
            0x02,
        ]
    )
    if include_charging:
        descriptor.extend(
            [
                0x09,
                0x44,
                0x15,
                0x00,
                0x25,
                0x01,
                0x75,
                0x01,
                0x95,
                0x01,
                0x81,
                0x02,
                0x75,
                0x07,
                0x95,
                0x01,
                0x81,
                0x03,
            ]
        )
    descriptor.extend(
        [
            0x75,
            0x08,
            0x95,
            0x07,
            0x81,
            0x01,
            0xC0,
            0x05,
            0x01,
            0x09,
            0x02,
            0xA1,
            0x01,
            0x09,
            0x01,
            0xA1,
            0x00,
            0x85,
            0x02,
            0x05,
            0x09,
            0x19,
            0x01,
            0x29,
            0x03,
            0x15,
            0x00,
            0x25,
            0x01,
            0x75,
            0x01,
            0x95,
            0x03,
            0x81,
            0x02,
            0x75,
            0x05,
            0x95,
            0x01,
            0x81,
            0x03,
            0x05,
            0x01,
            0x09,
            0x30,
            0x09,
            0x31,
            0x15,
            0x81,
            0x25,
            0x7F,
            0x75,
            0x08,
            0x95,
            0x02,
            0x81,
            0x06,
            0xC0,
            0xC0,
        ]
    )
    return bytes(descriptor)


def _build_create2_event(
    device: DeviceIdentity,
    descriptor: bytes,
) -> bytes:
    name = f"{device.hid_name} Battery Bridge"
    phys = f"attackshark-battery-bridge/{device.hidraw_name}"
    uniq = _device_uniq(device)

    return struct.pack(
        UHID_CREATE2_FORMAT,
        UHID_CREATE2,
        _encode_string(name, 128),
        _encode_string(phys, 64),
        _encode_string(uniq, 64),
        len(descriptor),
        device.bus,
        device.vendor_id,
        device.product_id,
        0,
        0,
        descriptor.ljust(4096, b"\x00"),
    )


class UhidBatteryPublisher(Publisher):
    def __init__(self, include_charging: bool) -> None:
        self._include_charging = include_charging
        self._fd: int | None = None
        self._active_key: tuple[str, str, int, int, str, str | None] | None = None
        self._active_uniq: str | None = None
        self._started = False
        self._current_report = self._build_report_payload(percentage=100, is_charging=None)

    def attach(self, device: DeviceIdentity, profile: BatteryProfile) -> None:
        key = (
            profile.profile_id,
            str(device.hidraw_path),
            device.vendor_id,
            device.product_id,
            device.hid_name,
            device.unique_id,
        )
        if self._active_key == key and self._fd is not None:
            self._drain_events()
            return

        self.detach()

        fd = os.open(UHID_PATH, os.O_RDWR | os.O_CLOEXEC | os.O_NONBLOCK)
        descriptor = _build_report_descriptor(self._include_charging)
        event = _build_create2_event(device, descriptor)
        os.write(fd, event)

        self._fd = fd
        self._active_key = key
        self._active_uniq = _device_uniq(device)
        self._started = False
        self._drain_events()
        if not self._wait_until_ready(UHID_READY_TIMEOUT_SECONDS):
            LOG.debug("UHID device %s did not report ready within %.3fs", key, UHID_READY_TIMEOUT_SECONDS)

    def publish(
        self,
        device: DeviceIdentity,
        profile: BatteryProfile,
        reading: BatteryReading,
    ) -> None:
        self._current_report = self._build_report_payload(
            percentage=reading.percentage,
            is_charging=reading.is_charging,
        )
        self.attach(device, profile)
        if self._fd is None:
            raise RuntimeError("UHID device is not attached")

        self._wait_until_ready(UHID_READY_TIMEOUT_SECONDS)
        self._drain_events()
        event = struct.pack(
            "<IH4096s",
            UHID_INPUT2,
            len(self._current_report),
            self._current_report.ljust(UHID_INPUT2_DATA_SIZE, b"\x00"),
        )
        os.write(self._fd, event)
        self._drain_events()

    def detach(self) -> None:
        if self._fd is None:
            self._active_key = None
            return

        try:
            os.write(self._fd, struct.pack("<I", UHID_DESTROY))
        except OSError:
            pass
        finally:
            os.close(self._fd)
            self._fd = None
            self._active_key = None
            self._active_uniq = None
            self._started = False

    def _build_report_payload(self, percentage: int, is_charging: bool | None) -> bytes:
        if self._include_charging:
            charging_bit = 1 if is_charging else 0
            return bytes([UHID_REPORT_ID, 0, 0, percentage, charging_bit, 0, 0, 0, 0, 0, 0, 0])
        return bytes([UHID_REPORT_ID, 0, 0, percentage, 0, 0, 0, 0, 0, 0, 0])

    def _drain_events(self) -> None:
        if self._fd is None:
            return

        while True:
            try:
                payload = os.read(self._fd, UHID_EVENT_MAX_SIZE)
            except BlockingIOError:
                return
            except OSError as exc:
                if exc.errno == errno.EAGAIN:
                    return
                raise

            if not payload:
                return

            event_type = struct.unpack_from("<I", payload, 0)[0]
            if event_type == UHID_START:
                self._started = True
                continue
            if event_type == UHID_STOP:
                self._started = False
                continue
            if event_type in (UHID_OPEN, UHID_CLOSE):
                continue
            if event_type == UHID_GET_REPORT:
                request_id = struct.unpack_from("<I", payload, 4)[0]
                report_number = payload[8]
                report_type = payload[9]
                self._reply_get_report(request_id, report_number, report_type)
                continue
            if event_type == UHID_SET_REPORT:
                request_id = struct.unpack_from("<I", payload, 4)[0]
                self._reply_set_report(request_id)
                continue
            LOG.debug("Ignoring UHID event type %s", event_type)

    def _reply_get_report(self, request_id: int, report_number: int, report_type: int) -> None:
        if self._fd is None:
            return

        if report_number != UHID_REPORT_ID or report_type != UHID_INPUT_REPORT:
            err = errno.EOPNOTSUPP
            data = b""
        else:
            err = 0
            data = self._current_report

        event = struct.pack(
            "<IIHH4096s",
            UHID_GET_REPORT_REPLY,
            request_id,
            err,
            len(data),
            data.ljust(UHID_INPUT2_DATA_SIZE, b"\x00"),
        )
        os.write(self._fd, event)

    def _reply_set_report(self, request_id: int) -> None:
        if self._fd is None:
            return
        event = struct.pack("<IIH", UHID_SET_REPORT_REPLY, request_id, errno.EOPNOTSUPP)
        os.write(self._fd, event)

    def _wait_until_ready(self, timeout_seconds: float) -> bool:
        if self._fd is None:
            return False

        deadline = time.monotonic() + max(timeout_seconds, 0.0)
        while True:
            self._drain_events()
            if self._started and self._virtual_device_registered():
                return True

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return self._started and self._virtual_device_registered()

            ready, _, _ = select.select([self._fd], [], [], min(remaining, 0.05))
            if not ready:
                continue

    def _virtual_device_registered(self) -> bool:
        if self._active_uniq is None:
            return False

        try:
            for uniq_path in SYS_HID_DEVICE_ROOT.glob("*/uniq"):
                try:
                    if uniq_path.read_text(encoding="utf-8").strip() == self._active_uniq:
                        return True
                except OSError:
                    continue
        except OSError:
            return False

        return False
