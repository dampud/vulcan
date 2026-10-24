"""Rodzeństwo na jednym koncie rodzica: wspólny LoginId, osobne Pupil.Id.

eduVULCAN zwraca dla każdego dziecka ten sam LoginId (to identyfikator konta
logowania rodzica), a odróżnia je dopiero Pupil.Id. Integracja ma pokazać każde
dziecko osobno i nie zgubić historii encji przy przejściu z dawnego klucza.
"""

from __future__ import annotations

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.vulcan_dom.const import DOMAIN

from . import dane

SIOSTRA_ID = dane.PUPIL_ID + 1
SIOSTRA = {
    **dane.ACCOUNT,
    "Pupil": {"Id": SIOSTRA_ID, "LoginId": dane.LOGIN_ID, "FirstName": "Ola", "Surname": "Testowa"},
    "ClassDisplay": "2b",
}


async def test_kazde_dziecko_ma_wlasne_urzadzenie(hass, entry, api_patch):
    api_patch.data["mobile/register/hebe"] = [dane.ACCOUNT, SIOSTRA]
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert set(entry.runtime_data.data) == {dane.PUPIL_ID, SIOSTRA_ID}

    dev_reg = dr.async_get(hass)
    urzadzenia = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
    assert sorted(d.name for d in urzadzenia) == ["Ala Testowa", "Ola Testowa"]
    assert {d.model for d in urzadzenia} == {"klasa 5a", "klasa 2b"}

    assert hass.states.get("sensor.ala_testowa_oceny") is not None
    assert hass.states.get("sensor.ola_testowa_oceny") is not None
    assert hass.states.get("calendar.ola_testowa_plan_lekcji") is not None


async def test_migracja_z_login_id_zachowuje_encje(hass, entry, api_patch):
    """Wpisy sprzed poprawki (klucz LoginId) przechodzą na Pupil.Id bez duplikatów."""
    dev_reg = dr.async_get(hass)
    stare_urzadzenie = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, str(dane.LOGIN_ID))},
        name="Ala Testowa",
    )
    ent_reg = er.async_get(hass)
    stara = ent_reg.async_get_or_create(
        "sensor", DOMAIN, f"{dane.LOGIN_ID}_grades",
        config_entry=entry, suggested_object_id="ala_testowa_oceny",
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    po = ent_reg.async_get(stara.entity_id)
    assert po.unique_id == f"{dane.PUPIL_ID}_grades"
    assert hass.states.get("sensor.ala_testowa_oceny") is not None
    assert hass.states.get("sensor.ala_testowa_oceny_2") is None

    urzadzenia = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
    assert [d.id for d in urzadzenia] == [stare_urzadzenie.id]
    assert urzadzenia[0].identifiers == {(DOMAIN, str(dane.PUPIL_ID))}
