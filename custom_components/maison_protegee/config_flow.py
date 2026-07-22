from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .api import MaisonProtegeeAPI
from .bootstrap import setup_import_path
from .const import (
    CONF_ENABLE_ALARM_PANEL,
    CONF_ENABLE_DIAGNOSTICS,
    CONF_ENABLE_EQUIPMENT,
    CONF_ENABLE_EVENTS,
    CONF_ENABLE_TEMPERATURES,
    DOMAIN,
)

setup_import_path()

from maison_protegee.exceptions import ApiError, AuthenticationError  # noqa: E402

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_ENABLE_ALARM_PANEL, default=True): bool,
        vol.Optional(CONF_ENABLE_TEMPERATURES, default=True): bool,
        vol.Optional(CONF_ENABLE_EQUIPMENT, default=True): bool,
        vol.Optional(CONF_ENABLE_EVENTS, default=True): bool,
        vol.Optional(CONF_ENABLE_DIAGNOSTICS, default=True): bool,
    }
)


class MaisonProtegeeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> MaisonProtegeeOptionsFlowHandler:
        return MaisonProtegeeOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self._abort_if_unique_id_configured()

            api = MaisonProtegeeAPI(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            try:
                if await api.async_authenticate():
                    if not api.contract_id:
                        errors["base"] = "no_contract"
                    else:
                        return self.async_create_entry(
                            title=user_input[CONF_USERNAME],
                            data=user_input,
                        )
                else:
                    errors["base"] = "invalid_auth"
            except (AuthenticationError, ApiError) as err:
                _LOGGER.error("Authentication failed during config flow: %s", err)
                errors["base"] = "invalid_auth"
            except OSError as err:
                _LOGGER.exception("Connection error during authentication: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during authentication")
                errors["base"] = "unknown"
            finally:
                await api.async_logout(force=True)

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return await self.async_step_user(user_input)


class MaisonProtegeeOptionsFlowHandler(config_entries.OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        config_entry = self.config_entry

        if user_input is not None:
            new_password = user_input.get(CONF_PASSWORD, "").strip()
            current_password = config_entry.data.get(CONF_PASSWORD)
            current_username = config_entry.data.get(CONF_USERNAME)

            password_changed = bool(new_password) and new_password != current_password
            username_changed = user_input[CONF_USERNAME] != current_username

            if password_changed or username_changed:
                password_to_use = new_password if password_changed else current_password
                username_to_use = user_input[CONF_USERNAME]

                if not password_to_use:
                    errors["base"] = "password_required"
                else:
                    if config_entry.entry_id in self.hass.data.get(DOMAIN, {}):
                        await self.hass.data[DOMAIN][config_entry.entry_id]["api"].async_logout(
                            force=True
                        )

                    api = MaisonProtegeeAPI(username_to_use, password_to_use)
                    try:
                        if await api.async_authenticate():
                            return self.async_create_entry(
                                data=_merge_options(config_entry.data, user_input, username_to_use, password_to_use)
                            )
                        errors["base"] = "invalid_auth"
                    except (AuthenticationError, ApiError):
                        errors["base"] = "invalid_auth"
                    except OSError:
                        errors["base"] = "cannot_connect"
                    except Exception:
                        errors["base"] = "unknown"
                    finally:
                        await api.async_logout(force=True)
            else:
                return self.async_create_entry(
                    data=_merge_options(config_entry.data, user_input)
                )

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(config_entry),
            errors=errors,
        )


def _merge_options(
    current: dict[str, Any],
    user_input: dict[str, Any],
    username: str | None = None,
    password: str | None = None,
) -> dict[str, Any]:
    updated = dict(current)
    if username is not None:
        updated[CONF_USERNAME] = username
    if password is not None:
        updated[CONF_PASSWORD] = password
    updated[CONF_ENABLE_ALARM_PANEL] = user_input.get(CONF_ENABLE_ALARM_PANEL, True)
    updated[CONF_ENABLE_TEMPERATURES] = user_input.get(CONF_ENABLE_TEMPERATURES, True)
    updated[CONF_ENABLE_EQUIPMENT] = user_input.get(CONF_ENABLE_EQUIPMENT, True)
    updated[CONF_ENABLE_EVENTS] = user_input.get(CONF_ENABLE_EVENTS, True)
    updated[CONF_ENABLE_DIAGNOSTICS] = user_input.get(CONF_ENABLE_DIAGNOSTICS, True)
    return updated


def _options_schema(config_entry: config_entries.ConfigEntry) -> vol.Schema:
    data = config_entry.data
    return vol.Schema(
        {
            vol.Required(CONF_USERNAME, default=data.get(CONF_USERNAME)): str,
            vol.Optional(CONF_PASSWORD, default=""): str,
            vol.Optional(
                CONF_ENABLE_ALARM_PANEL,
                default=data.get(CONF_ENABLE_ALARM_PANEL, True),
            ): bool,
            vol.Optional(
                CONF_ENABLE_TEMPERATURES,
                default=data.get(CONF_ENABLE_TEMPERATURES, True),
            ): bool,
            vol.Optional(
                CONF_ENABLE_EQUIPMENT,
                default=data.get(CONF_ENABLE_EQUIPMENT, True),
            ): bool,
            vol.Optional(
                CONF_ENABLE_EVENTS,
                default=data.get(CONF_ENABLE_EVENTS, True),
            ): bool,
            vol.Optional(
                CONF_ENABLE_DIAGNOSTICS,
                default=data.get(CONF_ENABLE_DIAGNOSTICS, True),
            ): bool,
        }
    )
