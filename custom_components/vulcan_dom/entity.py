"""Bazowa encja: jedno urządzenie na ucznia."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import model as m
from .const import DOMAIN
from .coordinator import VulcanCoordinator


class VulcanEntity(CoordinatorEntity[VulcanCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: VulcanCoordinator, pupil_id: int, key: str) -> None:
        super().__init__(coordinator)
        self.pupil_id = pupil_id
        self._attr_unique_id = f"{pupil_id}_{key}"
        self._attr_translation_key = key
        pupil = coordinator.data[pupil_id]
        acc = coordinator.account_for(pupil_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(pupil_id))},
            name=pupil.name,
            manufacturer="VULCAN (nieoficjalnie)",
            model=f"klasa {acc.get('ClassDisplay') or '?'}",
            suggested_area=None,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def pupil(self) -> m.PupilData | None:
        return (self.coordinator.data or {}).get(self.pupil_id)

    @property
    def available(self) -> bool:
        return super().available and self.pupil is not None
