from __future__ import annotations

import logging
import os
import select
import socket
import time
from typing import Final


LOG = logging.getLogger(__name__)

NETLINK_KOBJECT_UEVENT: Final[int] = 15
UEVENT_GROUP_KERNEL: Final[int] = 1
UEVENT_BUFFER_SIZE: Final[int] = 16 * 1024


class KernelDeviceEventMonitor:
    def __init__(self) -> None:
        self._socket: socket.socket | None = None

        try:
            monitor = socket.socket(
                socket.AF_NETLINK,
                socket.SOCK_DGRAM,
                NETLINK_KOBJECT_UEVENT,
            )
            monitor.bind((os.getpid(), UEVENT_GROUP_KERNEL))
            monitor.setblocking(False)
            self._socket = monitor
        except OSError as exc:
            if self._socket is not None:
                self._socket.close()
                self._socket = None
            LOG.warning(
                "Kernel uevent monitor unavailable, falling back to timed rescans: %s",
                exc,
            )

    def wait(self, timeout_seconds: float) -> bool:
        timeout = max(timeout_seconds, 0.0)
        if self._socket is None:
            if timeout > 0:
                time.sleep(timeout)
            return False

        ready, _, _ = select.select([self._socket], [], [], timeout)
        if not ready:
            return False

        event_seen = False
        while True:
            try:
                payload = self._socket.recv(UEVENT_BUFFER_SIZE)
            except BlockingIOError:
                break
            except OSError as exc:
                LOG.warning(
                    "Kernel uevent monitor failed during recv, falling back to timed rescans: %s",
                    exc,
                )
                self.close()
                return True

            if not payload:
                break

            event_seen = True

        return event_seen

    def close(self) -> None:
        if self._socket is None:
            return
        self._socket.close()
        self._socket = None
