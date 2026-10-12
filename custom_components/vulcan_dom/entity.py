"""Bazowa encja: jedno urządzenie na ucznia."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import model as m
from .const import DOMAIN
from .coordinator import VulcanCoordinator


class VulcanEntity(CoordinatorEntity[VulcanCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: VulcanCoordinator, login_id: int, key: str) -> None:
        super().__init__(coordinator)
        self.login_id = login_id
        self._attr_unique_id = f"{login_id}_{key}"
        self._attr_translation_key = key
        pupil = coordinator.data[login_id]
        acc = coordinator.account_for(login_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(login_id))},
            name=pupil.name,
            manufacturer="VULCAN (nieoficjalnie)",
            model=f"klasa {acc.get('ClassDisplay') or '?'}",
            suggested_area=None,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def pupil(self) -> m.PupilData | None:
        return (self.coordinator.data or {}).get(self.login_id)

    @property
    def available(self) -> bool:
        return super().available and self.pupil is not None
