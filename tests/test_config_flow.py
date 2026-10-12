"""Kreator: rejestracja, błędy, ponowna rejestracja, opcje."""

from __future__ import annotations

import json

from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType

from custom_components.vulcan_dom.const import (
    CONF_AP_JSON,
    CONF_CREDENTIAL,
    CONF_SCAN_INTERVAL,
    CONF_TENANT,
    CONF_WRITE_LIMIT,
    DOMAIN,
)

from . import dane


async def start(hass):
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})


async def test_rejestracja_tworzy_wpis(hass, api_patch):
    flow = await start(hass)
    assert flow["type"] is FlowResultType.FORM and flow["step_id"] == "user"

    done = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {CONF_AP_JSON: json.dumps(dane.ap_payload())}
    )
    assert done["type"] is FlowResultType.CREATE_ENTRY
    assert done["title"] == "eduVULCAN – Ala Testowa"
    assert done["data"][CONF_TENANT] == dane.TENANT
    assert done["data"][CONF_CREDENTIAL]["private_key"]
    assert done["result"].unique_id == f"{dane.TENANT}-{dane.LOGIN_ID}"
    # dane z /api/ap nie lądują we wpisie
    assert CONF_AP_JSON not in done["data"]
    assert api_patch.path_calls("mobile/register/jwt")


async def test_wklejka_nie_z_api_ap(hass, api_patch):
    flow = await start(hass)
    done = await hass.config_entries.flow.async_configure(flow["flow_id"], {CONF_AP_JSON: "to nie json"})
    assert done["type"] is FlowResultType.FORM and done["errors"] == {"base": "invalid_ap"}


async def test_niezaakceptowane_zgody(hass, api_patch):
    zle = {**dane.ap_payload(), "IsConsentAccepted": False}
    flow = await start(hass)
    done = await hass.config_entries.flow.async_configure(flow["flow_id"], {CONF_AP_JSON: json.dumps(zle)})
    assert done["errors"] == {"base": "invalid_ap"}


async def test_odmowa_rejestracji_po_stronie_vulcana(hass, api_patch):
    api_patch.fail["mobile/register/jwt"] = (200, 202)  # nieprawidłowy token
    flow = await start(hass)
    done = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {CONF_AP_JSON: json.dumps(dane.ap_payload())}
    )
    assert done["errors"] == {"base": "rejected"}


async def test_brak_polaczenia(hass, api_patch):
    api_patch.fail["mobile/register/jwt"] = (502, 0)
    flow = await start(hass)
    done = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {CONF_AP_JSON: json.dumps(dane.ap_payload())}
    )
    assert done["errors"] == {"base": "cannot_connect"}


async def test_konto_bez_uczniow(hass, api_patch):
    api_patch.data["mobile/register/hebe"] = []
    flow = await start(hass)
    done = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {CONF_AP_JSON: json.dumps(dane.ap_payload())}
    )
    assert done["errors"] == {"base": "no_pupils"}


async def test_to_samo_konto_drugi_raz_jest_odrzucone(hass, entry, api_patch):
    flow = await start(hass)
    done = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {CONF_AP_JSON: json.dumps(dane.ap_payload())}
    )
    assert done["type"] is FlowResultType.ABORT and done["reason"] == "already_configured"


async def test_reauth_odswieza_klucz_urzadzenia(hass, entry, setup_entry):
    flow = await entry.start_reauth_flow(hass)
    assert flow["step_id"] == "reauth_confirm"
    done = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {CONF_AP_JSON: json.dumps(dane.ap_payload())}
    )
    await hass.async_block_till_done()
    assert done["type"] is FlowResultType.ABORT and done["reason"] == "reauth_successful"


async def test_reauth_z_innego_konta_odrzucony(hass, entry, setup_entry):
    setup_entry.data["mobile/register/hebe"] = [
        {**dane.ACCOUNT, "Pupil": {**dane.ACCOUNT["Pupil"], "LoginId": 9999}}
    ]
    flow = await entry.start_reauth_flow(hass)
    done = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {CONF_AP_JSON: json.dumps(dane.ap_payload())}
    )
    assert done["type"] is FlowResultType.ABORT and done["reason"] == "wrong_account"


async def test_opcje_zapisuja_sie_jako_liczby(hass, entry, setup_entry):
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    done = await hass.config_entries.options.async_configure(
        flow["flow_id"],
        {CONF_SCAN_INTERVAL: 45, "quiet_start": 23, "quiet_end": 5, CONF_WRITE_LIMIT: 3},
    )
    await hass.async_block_till_done()
    assert done["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_SCAN_INTERVAL] == 45
    assert all(isinstance(v, int) for v in entry.options.values())
