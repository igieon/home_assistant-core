"""The Nibe Heat Pump integration."""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from nibe.coil import Coil
from nibe.connection import Connection
from nibe.connection.nibegw import NibeGW
from nibe.exceptions import CoilNotFoundException, CoilReadException
from nibe.heatpump import HeatPump, Model
from tenacity import RetryError, retry, retry_if_exception_type, stop_after_attempt

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_MODEL,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo, async_generate_entity_id
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_CONNECTION_TYPE,
    CONF_CONNECTION_TYPE_NIBEGW,
    CONF_LISTENING_PORT,
    CONF_REMOTE_READ_PORT,
    CONF_REMOTE_WRITE_PORT,
    CONF_WORD_SWAP,
    DOMAIN,
    LOGGER,
)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]
COIL_READ_RETRIES = 5


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nibe Heat Pump from a config entry."""

    heatpump = HeatPump(Model[entry.data[CONF_MODEL]])
    heatpump.word_swap = entry.data[CONF_WORD_SWAP]
    await hass.async_add_executor_job(heatpump.initialize)

    connection_type = entry.data[CONF_CONNECTION_TYPE]

    if connection_type == CONF_CONNECTION_TYPE_NIBEGW:
        connection = NibeGW(
            heatpump,
            entry.data[CONF_IP_ADDRESS],
            entry.data[CONF_REMOTE_READ_PORT],
            entry.data[CONF_REMOTE_WRITE_PORT],
            listening_port=entry.data[CONF_LISTENING_PORT],
        )
    else:
        raise HomeAssistantError(f"Connection type {connection_type} is not supported.")

    await connection.start()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, connection.stop)
    )

    coordinator = Coordinator(hass, heatpump, connection)

    data = hass.data.setdefault(DOMAIN, {})
    data[entry.entry_id] = coordinator

    reg = dr.async_get(hass)
    reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        manufacturer="NIBE Energy Systems",
        model=heatpump.model.name,
        name=heatpump.model.name,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Trigger a refresh again now that all platforms have registered
    hass.async_create_task(coordinator.async_refresh())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: Coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.connection.stop()

    return unload_ok


class Coordinator(DataUpdateCoordinator[dict[int, Coil]]):
    """Update coordinator for nibe heat pumps."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        heatpump: HeatPump,
        connection: Connection,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass, LOGGER, name="Nibe Heat Pump", update_interval=timedelta(seconds=60)
        )

        self.data = {}
        self.connection = connection
        self.heatpump = heatpump

    @property
    def coils(self) -> list[Coil]:
        """Return the full coil database."""
        return self.heatpump.get_coils()

    @property
    def unique_id(self) -> str:
        """Return unique id for this coordinator."""
        return self.config_entry.unique_id or self.config_entry.entry_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the main device."""
        return DeviceInfo(identifiers={(DOMAIN, self.unique_id)})

    def get_coil_value(self, coil: Coil) -> int | str | float | None:
        """Return a coil with data and check for validity."""
        if coil := self.data.get(coil.address):
            return coil.value
        return None

    def get_coil_float(self, coil: Coil) -> float | None:
        """Return a coil with float and check for validity."""
        if value := self.get_coil_value(coil):
            return float(value)
        return None

    async def async_write_coil(self, coil: Coil, value: int | float | str) -> None:
        """Write coil and update state."""
        coil.value = value
        coil = await self.connection.write_coil(coil)

        if self.data:
            self.data[coil.address] = coil
            self.async_update_listeners()

    async def _async_update_data(self) -> dict[int, Coil]:
        @retry(
            retry=retry_if_exception_type(CoilReadException),
            stop=stop_after_attempt(COIL_READ_RETRIES),
        )
        async def read_coil(coil: Coil):
            return await self.connection.read_coil(coil)

        callbacks: dict[int, list[CALLBACK_TYPE]] = defaultdict(list)
        for update_callback, context in list(self._listeners.values()):
            assert isinstance(context, set)
            for address in context:
                callbacks[address].append(update_callback)

        result: dict[int, Coil] = {}

        for address, callback_list in callbacks.items():
            try:
                coil = self.heatpump.get_coil_by_address(address)
                self.data[coil.address] = result[coil.address] = await read_coil(coil)
            except (CoilReadException, RetryError) as exception:
                raise UpdateFailed(f"Failed to update: {exception}") from exception
            except CoilNotFoundException as exception:
                self.logger.debug("Skipping missing coil: %s", exception)

            for update_callback in callback_list:
                update_callback()

        return result


class CoilEntity(CoordinatorEntity[Coordinator]):
    """Base for coil based entities."""

    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, coordinator: Coordinator, coil: Coil, entity_format: str
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator, {coil.address})
        self.entity_id = async_generate_entity_id(
            entity_format, coil.name, hass=coordinator.hass
        )
        self._attr_name = coil.title
        self._attr_unique_id = f"{coordinator.unique_id}-{coil.address}"
        self._attr_device_info = coordinator.device_info
        self._coil = coil

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self._coil.address in (
            self.coordinator.data or {}
        )

    def _async_read_coil(self, coil: Coil):
        """Update state of entity based on coil data."""

    async def _async_write_coil(self, value: int | float | str):
        """Write coil and update state."""
        await self.coordinator.async_write_coil(self._coil, value)

    def _handle_coordinator_update(self) -> None:
        coil = self.coordinator.data.get(self._coil.address)
        if coil is None:
            return

        self._coil = coil
        self._async_read_coil(coil)
        self.async_write_ha_state()
