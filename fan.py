"""Support for Broadlink fans."""

from __future__ import annotations

from typing import Any

from broadlink.exceptions import BroadlinkException

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .broadlink.purifier import FanMode as LifaairFanMode
from .const import DOMAIN
from .entity import BroadlinkEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Broadlink fan."""
    device = hass.data[DOMAIN].devices[config_entry.entry_id]
    fans: list[FanEntity] = []

    if device.api.type == "LIFAAIR":
        fans.append(BroadlinkLifaairFan(device))

    async_add_entities(fans)


class BroadlinkLifaairFan(BroadlinkEntity, FanEntity):
    """Representation of a LIFAair purifier fan."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = FanEntityFeature.SET_SPEED | FanEntityFeature.PRESET_MODE

    def __init__(self, device) -> None:
        """Initialize the fan."""
        super().__init__(device)
        self._attr_unique_id = device.unique_id
        self._attr_preset_modes = [
            "auto",
            "night",
            "turbo",
            "anti_allergy",
            "manual",
        ]
        self._update_state(self._coordinator.data or {})

    def _update_state(self, data: dict[str, Any]) -> None:
        """Update the state of the entity."""
        fan_mode = data.get("fan_mode")
        fan_speed = data.get("fan_speed")

        # fan_mode is an enum from python-broadlink (or None if the main unit is offline).
        mode_name = getattr(fan_mode, "name", None)

        if mode_name is None:
            self._attr_is_on = None
            self._attr_preset_mode = None
        elif mode_name == "OFF":
            self._attr_is_on = False
            self._attr_preset_mode = None
        else:
            self._attr_is_on = True
            # FanMode.MANUAL is exposed as a preset mode, but speed is controlled via percentage.
            if mode_name == "ANTI_ALLERGY":
                self._attr_preset_mode = "anti_allergy"
            else:
                self._attr_preset_mode = mode_name.lower()

        if isinstance(fan_speed, int):
            self._attr_percentage = max(0, min(100, round(fan_speed * 100 / 121)))
        else:
            self._attr_percentage = None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the fan on."""
        if self._attr_preset_mode:
            await self.async_set_preset_mode(self._attr_preset_mode)
            return
        await self.async_set_preset_mode("auto")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        device = self._device
        try:
            await device.async_request(device.api.set_fan_mode, LifaairFanMode.OFF)
        except (BroadlinkException, OSError):
            return
        await self._coordinator.async_request_refresh()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set fan speed percentage (mapped to 0..121)."""
        device = self._device
        speed = max(0, min(121, round(percentage * 121 / 100)))
        try:
            await device.async_request(device.api.set_fan_speed, speed)
        except (BroadlinkException, OSError):
            return
        await self._coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        device = self._device

        mode_map = {
            "auto": LifaairFanMode.AUTO,
            "night": LifaairFanMode.NIGHT,
            "turbo": LifaairFanMode.TURBO,
            "anti_allergy": LifaairFanMode.ANTI_ALLERGY,
            "manual": LifaairFanMode.MANUAL,
        }
        fan_mode = mode_map.get(preset_mode)
        if fan_mode is None:
            return

        try:
            await device.async_request(device.api.set_fan_mode, fan_mode)
        except (BroadlinkException, OSError):
            return
        await self._coordinator.async_request_refresh()

