from __future__ import annotations

from attackshark_battery_bridge.exceptions import ParseError
from attackshark_battery_bridge.models import BatteryReading, DeviceIdentity
from attackshark_battery_bridge.profiles import BatteryProfile
from attackshark_battery_bridge.transport.hidraw import HidrawFeatureTransport


class ProfileBatteryDriver:
    def __init__(self, transport: HidrawFeatureTransport | None = None) -> None:
        self._transport = transport or HidrawFeatureTransport()

    def poll(
        self,
        device: DeviceIdentity,
        profile: BatteryProfile,
    ) -> BatteryReading:
        request = profile.build_request()
        response = self._transport.exchange(
            device_path=str(device.hidraw_path),
            request=request,
            response_length=profile.poll_protocol.report_length,
            mode=profile.poll_protocol.mode,
            response_delay_ms=profile.poll_protocol.response_delay_ms,
        )

        remaining_follow_up_gets = profile.poll_protocol.max_follow_up_gets
        while (
            remaining_follow_up_gets > 0
            and any(
                response.startswith(prefix)
                for prefix in profile.poll_protocol.retry_response_prefixes
            )
        ):
            response = self._transport.exchange(
                device_path=str(device.hidraw_path),
                request=request,
                response_length=profile.poll_protocol.report_length,
                mode="feature_get",
                response_delay_ms=profile.poll_protocol.response_delay_ms,
            )
            remaining_follow_up_gets -= 1

        try:
            return profile.parse_response(response, device=device)
        except ParseError:
            raise
