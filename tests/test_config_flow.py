"""Tests for the Météo-France Montagne config flow."""
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.meteofrance_montagne.api import (
    MeteoFranceMontagneApiError,
    MeteoFranceMontagneAuthError,
)
from custom_components.meteofrance_montagne.const import (
    CONF_MASSIF,
    CONF_MASSIF_NAME,
    CONF_TOKEN,
    DOMAIN,
    NAME,
    SUBENTRY_TYPE_MASSIF,
)

from .conftest import MASSIF_ID, MASSIF_NAME, TOKEN

pytestmark = pytest.mark.usefixtures("mock_call_api")


@pytest.fixture(autouse=True)
def mock_setup_entry():
    """Do not set the entry up once created."""
    with patch(
        "custom_components.meteofrance_montagne.async_setup_entry",
        AsyncMock(return_value=True),
    ) as mock:
        yield mock


async def test_user_flow(hass: HomeAssistant):
    """Create the API entry with its first massif."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: TOKEN}
    )
    assert result["step_id"] == "department"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"department": "Ariège"}
    )
    assert result["step_id"] == "massif"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"massif": MASSIF_NAME}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == {CONF_TOKEN: TOKEN}

    entry = result["result"]
    (subentry,) = entry.subentries.values()
    assert subentry.subentry_type == SUBENTRY_TYPE_MASSIF
    assert subentry.title == f"Ariège - {MASSIF_NAME}"
    assert subentry.unique_id == str(MASSIF_ID)
    assert dict(subentry.data) == {CONF_MASSIF: MASSIF_ID, CONF_MASSIF_NAME: MASSIF_NAME}


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (MeteoFranceMontagneAuthError("401"), "invalid_auth"),
        (MeteoFranceMontagneApiError("500"), "cannot_connect"),
        (RuntimeError("bug"), "unknown"),
    ],
)
async def test_user_flow_errors(hass: HomeAssistant, mock_call_api, error, reason):
    """Show the error, then accept a valid key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    side_effect = mock_call_api.side_effect
    mock_call_api.side_effect = error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "wrong"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}

    mock_call_api.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: TOKEN}
    )
    assert result["step_id"] == "department"


async def test_single_entry(hass: HomeAssistant, config_entry):
    """Allow a single API entry."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_add_massif(hass: HomeAssistant, config_entry):
    """Add a second massif as a subentry."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_MASSIF), context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "department"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"department": "Hautes-Alpes"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"massif": "Champsaur"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    subentry = next(
        sub for sub in config_entry.subentries.values() if sub.unique_id == "16"
    )
    assert subentry.title == "Hautes-Alpes - Champsaur"
    assert dict(subentry.data) == {CONF_MASSIF: 16, CONF_MASSIF_NAME: "Champsaur"}


async def test_add_massif_already_configured(hass: HomeAssistant, config_entry):
    """Refuse a massif already added."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_MASSIF), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"department": "Ariège"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"massif": MASSIF_NAME}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(config_entry.subentries) == 1


async def test_add_massif_invalid_key(hass: HomeAssistant, config_entry, mock_call_api):
    """Abort the massif selection when the stored key is rejected."""
    config_entry.add_to_hass(hass)
    mock_call_api.side_effect = MeteoFranceMontagneAuthError("401")

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_MASSIF), context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_auth"


async def test_reconfigure(hass: HomeAssistant, config_entry):
    """Replace the API key."""
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "new-key"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_TOKEN] == "new-key"


async def test_reauth(hass: HomeAssistant, config_entry, mock_call_api):
    """Ask for a new key until one is accepted."""
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    side_effect = mock_call_api.side_effect
    mock_call_api.side_effect = MeteoFranceMontagneAuthError("401")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "still-wrong"}
    )
    assert result["errors"] == {"base": "invalid_auth"}
    assert config_entry.data[CONF_TOKEN] == TOKEN

    mock_call_api.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "new-key"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_TOKEN] == "new-key"
