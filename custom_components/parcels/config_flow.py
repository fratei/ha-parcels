"""Config flow for Parcels: one hub entry and one entry per mailbox."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import time
import logging
from typing import Any

from homeassistant import data_entry_flow
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithReload,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    DeviceFilterSelectorConfig,
    DeviceSelector,
    DeviceSelectorConfig,
    EntityFilterSelectorConfig,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
    TimeSelector,
)
import probatio

from .ai import safety
from .application_credentials import provider_from_client_id
from .const import (
    CONF_ADDRESS,
    CONF_AI_MODE,
    CONF_AI_TASK,
    CONF_ARCHIVE_DAYS,
    CONF_COLLAPSE_THRESHOLD,
    CONF_CUTOFF_TIME,
    CONF_ENTRY_TYPE,
    CONF_EXCLUDED_DEVICES,
    CONF_FOLDERS,
    CONF_INTERVAL_MINUTES,
    CONF_ITEM_NAMES,
    CONF_LOOKBACK_DAYS,
    CONF_NOTIFY_PERSONS,
    CONF_OWNER,
    CONF_PARCEL_APP_ADD,
    CONF_PARCEL_APP_DAILY,
    CONF_PARCEL_APP_EVERYONE,
    CONF_PARCEL_APP_IMPORT,
    CONF_PARCEL_APP_KEY,
    CONF_PARCEL_APP_OWNER,
    CONF_PARCEL_APP_POSTCODE,
    CONF_PIN_ON_LOCK_SCREEN,
    CONF_PROVIDER,
    CONF_PURGE_DAYS,
    CONF_SEVENTEENTRACK,
    CONF_START_TIME,
    CONF_TEST_DEVICE,
    CONF_TEST_MODE,
    DEFAULT_AI_MODE,
    DEFAULT_ARCHIVE_DAYS,
    DEFAULT_COLLAPSE_THRESHOLD,
    DEFAULT_CUTOFF_TIME,
    DEFAULT_INTERVAL_MINUTES,
    DEFAULT_ITEM_NAMES,
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_MICROSOFT_FOLDERS,
    DEFAULT_PARCEL_APP_ADD,
    DEFAULT_PARCEL_APP_DAILY,
    DEFAULT_PARCEL_APP_EVERYONE,
    DEFAULT_PARCEL_APP_IMPORT,
    DEFAULT_PIN_ON_LOCK_SCREEN,
    DEFAULT_PURGE_DAYS,
    DEFAULT_SEVENTEENTRACK,
    DEFAULT_START_TIME,
    DOMAIN,
    ENTRY_TYPE_HUB,
    ENTRY_TYPE_MAILBOX,
    HUB_UNIQUE_ID,
    MAX_PARCEL_APP_DAILY,
    MICROSOFT_FOLDERS,
    NAME,
    PROVIDER_GOOGLE,
    PROVIDER_MICROSOFT,
    AIMode,
)
from .mail.errors import MailApiDisabled, MailAuthError, MailError, MailNoMailbox
from .mail.oauth import create_client
from .parcelapp.api import (
    ErrorKind,
    ParcelAppError,
    async_get_deliveries,
    normalize_postcode,
    valid_key,
)

_LOGGER = logging.getLogger(__name__)

AI_CHECK_REASONS = frozenset(
    {
        "not_found",
        "not_ai_task",
        "not_ollama",
        "no_entry",
        "no_model",
        "cloud_model",
        "remote_host",
        "unresolvable",
    }
)
MAX_ARCHIVE_DAYS = 365
MAX_PURGE_DAYS = 3650

HUB_DEFAULTS: dict[str, Any] = {
    CONF_NOTIFY_PERSONS: [],
    CONF_EXCLUDED_DEVICES: [],
    CONF_START_TIME: DEFAULT_START_TIME,
    CONF_CUTOFF_TIME: DEFAULT_CUTOFF_TIME,
    CONF_COLLAPSE_THRESHOLD: DEFAULT_COLLAPSE_THRESHOLD,
    CONF_ITEM_NAMES: DEFAULT_ITEM_NAMES,
    CONF_PIN_ON_LOCK_SCREEN: DEFAULT_PIN_ON_LOCK_SCREEN,
    CONF_SEVENTEENTRACK: DEFAULT_SEVENTEENTRACK,
    CONF_TEST_MODE: False,
    CONF_ARCHIVE_DAYS: DEFAULT_ARCHIVE_DAYS,
    CONF_PURGE_DAYS: DEFAULT_PURGE_DAYS,
    CONF_AI_MODE: DEFAULT_AI_MODE.value,
}


def mailbox_defaults(provider: str) -> dict[str, Any]:
    """Return the default options of a mailbox entry."""
    defaults: dict[str, Any] = {
        CONF_LOOKBACK_DAYS: DEFAULT_LOOKBACK_DAYS,
        CONF_INTERVAL_MINUTES: DEFAULT_INTERVAL_MINUTES,
    }
    if provider == PROVIDER_MICROSOFT:
        defaults[CONF_FOLDERS] = list(DEFAULT_MICROSOFT_FOLDERS)
    return defaults


def _days(maximum: int) -> NumberSelector:
    """Return a number selector for a count of days."""
    return NumberSelector(
        NumberSelectorConfig(
            min=1,
            max=maximum,
            step=1,
            mode=NumberSelectorMode.BOX,
            unit_of_measurement=UnitOfTime.DAYS,
        )
    )


def _mobile_app_devices(*, multiple: bool) -> DeviceSelector:
    """Return a selector of companion app devices."""
    return DeviceSelector(
        DeviceSelectorConfig(
            filter=DeviceFilterSelectorConfig(integration="mobile_app"),
            multiple=multiple,
        )
    )


def _persons(*, multiple: bool) -> EntitySelector:
    """Return a selector of person entities."""
    return EntitySelector(
        EntitySelectorConfig(
            filter=EntityFilterSelectorConfig(domain="person"), multiple=multiple
        )
    )


# The Parcel app settings show once a key is typed, those for adding only
# while adding is on.
_PARCEL_APP_KEY_TYPED = {"field": CONF_PARCEL_APP_KEY, "operator": "exists"}
_PARCEL_APP_ADDING = [
    _PARCEL_APP_KEY_TYPED,
    {"field": CONF_PARCEL_APP_ADD, "value": True},
]


HUB_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_NOTIFY_PERSONS): _persons(multiple=True),
        probatio.Optional(CONF_EXCLUDED_DEVICES): _mobile_app_devices(multiple=True),
        probatio.Required(CONF_START_TIME, default=DEFAULT_START_TIME): TimeSelector(),
        probatio.Required(
            CONF_CUTOFF_TIME, default=DEFAULT_CUTOFF_TIME
        ): TimeSelector(),
        probatio.Required(
            CONF_COLLAPSE_THRESHOLD, default=DEFAULT_COLLAPSE_THRESHOLD
        ): NumberSelector(
            NumberSelectorConfig(min=1, max=10, step=1, mode=NumberSelectorMode.BOX)
        ),
        probatio.Required(
            CONF_ITEM_NAMES, default=DEFAULT_ITEM_NAMES
        ): BooleanSelector(),
        probatio.Required(
            CONF_PIN_ON_LOCK_SCREEN, default=DEFAULT_PIN_ON_LOCK_SCREEN
        ): BooleanSelector(),
        probatio.Required(
            CONF_SEVENTEENTRACK, default=DEFAULT_SEVENTEENTRACK
        ): BooleanSelector(),
        probatio.Optional(CONF_PARCEL_APP_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        data_entry_flow.Optional(
            CONF_PARCEL_APP_OWNER, visible=_PARCEL_APP_KEY_TYPED
        ): _persons(multiple=False),
        data_entry_flow.Required(
            CONF_PARCEL_APP_IMPORT,
            default=DEFAULT_PARCEL_APP_IMPORT,
            visible=_PARCEL_APP_KEY_TYPED,
        ): BooleanSelector(),
        data_entry_flow.Required(
            CONF_PARCEL_APP_ADD,
            default=DEFAULT_PARCEL_APP_ADD,
            visible=_PARCEL_APP_KEY_TYPED,
        ): BooleanSelector(),
        data_entry_flow.Required(
            CONF_PARCEL_APP_EVERYONE,
            default=DEFAULT_PARCEL_APP_EVERYONE,
            visible=_PARCEL_APP_ADDING,
        ): BooleanSelector(),
        data_entry_flow.Required(
            CONF_PARCEL_APP_DAILY,
            default=DEFAULT_PARCEL_APP_DAILY,
            visible=_PARCEL_APP_ADDING,
        ): NumberSelector(
            NumberSelectorConfig(
                min=1, max=MAX_PARCEL_APP_DAILY, step=1, mode=NumberSelectorMode.BOX
            )
        ),
        data_entry_flow.Optional(
            CONF_PARCEL_APP_POSTCODE, visible=_PARCEL_APP_ADDING
        ): TextSelector(),
        probatio.Required(CONF_TEST_MODE, default=False): BooleanSelector(),
        data_entry_flow.Optional(
            CONF_TEST_DEVICE, visible={"field": CONF_TEST_MODE, "value": True}
        ): _mobile_app_devices(multiple=False),
        probatio.Required(CONF_ARCHIVE_DAYS, default=DEFAULT_ARCHIVE_DAYS): _days(
            MAX_ARCHIVE_DAYS
        ),
        probatio.Required(CONF_PURGE_DAYS, default=DEFAULT_PURGE_DAYS): _days(
            MAX_PURGE_DAYS
        ),
        probatio.Optional(CONF_AI_TASK): EntitySelector(
            EntitySelectorConfig(filter=EntityFilterSelectorConfig(domain="ai_task"))
        ),
        probatio.Required(CONF_AI_MODE, default=DEFAULT_AI_MODE.value): SelectSelector(
            SelectSelectorConfig(
                options=[mode.value for mode in AIMode],
                mode=SelectSelectorMode.LIST,
                translation_key=CONF_AI_MODE,
            )
        ),
    }
)


def _mailbox_schema(provider: str) -> probatio.Schema:
    """Return the options schema of a mailbox entry."""
    schema: dict[Any, Any] = {
        probatio.Optional(CONF_OWNER): _persons(multiple=False),
    }
    if provider == PROVIDER_MICROSOFT:
        schema[
            probatio.Required(CONF_FOLDERS, default=list(DEFAULT_MICROSOFT_FOLDERS))
        ] = SelectSelector(
            SelectSelectorConfig(
                options=list(MICROSOFT_FOLDERS),
                multiple=True,
                mode=SelectSelectorMode.LIST,
                translation_key=CONF_FOLDERS,
            )
        )
    schema |= {
        probatio.Required(CONF_LOOKBACK_DAYS, default=DEFAULT_LOOKBACK_DAYS): _days(90),
        probatio.Required(
            CONF_INTERVAL_MINUTES, default=DEFAULT_INTERVAL_MINUTES
        ): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=60,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.MINUTES,
            )
        ),
    }
    return probatio.Schema(schema)


def _time_value(value: Any) -> time:
    """Return a time selector value as a time."""
    return cv.time(value)


def _ai_error(reason: str | None) -> str:
    """Return the form error of a failed AI task check."""
    return f"ai_{reason}" if reason in AI_CHECK_REASONS else "ai_unknown"


class ParcelsFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Add the Parcels hub, then one entry per signed-in mailbox."""

    DOMAIN = DOMAIN
    VERSION = 1
    MINOR_VERSION = 1

    @property
    def logger(self) -> logging.Logger:
        """Return the logger of the flow."""
        return _LOGGER

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow of the hub or of a mailbox."""
        if config_entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_MAILBOX:
            return MailboxOptionsFlow()
        return HubOptionsFlow()

    def _hub_exists(self) -> bool:
        """Return whether the hub entry exists."""
        return any(
            entry.unique_id == HUB_UNIQUE_ID
            or entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_HUB
            for entry in self._async_current_entries(include_ignore=False)
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add the hub first; once it exists, sign in to add a mailbox."""
        if not self._hub_exists():
            return await self.async_step_hub()
        return await self.async_step_pick_implementation(user_input)

    async def async_step_hub(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm and create the hub entry."""
        await self.async_set_unique_id(HUB_UNIQUE_ID)
        self._abort_if_unique_id_configured()
        if user_input is None:
            return self.async_show_form(step_id="hub")
        return self.async_create_entry(
            title=NAME,
            data={CONF_ENTRY_TYPE: ENTRY_TYPE_HUB},
            options=dict(HUB_DEFAULTS),
            description="hub",
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start signing in again after the sign-in expired."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask to sign in again to the same account."""
        entry = self._get_reauth_entry()
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                description_placeholders={
                    CONF_ADDRESS: entry.data.get(CONF_ADDRESS, entry.title)
                },
            )
        return await self.async_step_pick_implementation(
            {"implementation": entry.data["auth_implementation"]}
        )

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Read the mailbox address with the new token and create the entry."""
        provider = getattr(self.flow_impl, "provider", None)
        if provider not in (PROVIDER_MICROSOFT, PROVIDER_GOOGLE):
            provider = provider_from_client_id(getattr(self.flow_impl, "client_id", ""))
        access_token = str(data["token"]["access_token"])

        async def async_get_token(rejected: str | None = None) -> str:
            if rejected is not None:
                raise MailAuthError("the new token was rejected")
            return access_token

        client = create_client(
            provider, async_get_clientsession(self.hass), async_get_token
        )
        try:
            address = (await client.async_get_address()).strip().lower()
        except MailNoMailbox:
            return self.async_abort(reason="no_mailbox")
        except MailApiDisabled:
            return self.async_abort(reason="api_disabled")
        except MailAuthError:
            return self.async_abort(reason="missing_permission")
        except MailError:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected error while reading the mailbox address")
            return self.async_abort(reason="unknown")
        if not address:
            return self.async_abort(reason="no_mailbox")

        await self.async_set_unique_id(address)
        if self.source == SOURCE_REAUTH:
            entry = self._get_reauth_entry()
            placeholders = {CONF_ADDRESS: entry.data.get(CONF_ADDRESS, entry.title)}
            self._abort_if_unique_id_mismatch(
                reason="wrong_account", description_placeholders=placeholders
            )
            if entry.data.get(CONF_PROVIDER, provider) != provider:
                return self.async_abort(
                    reason="wrong_account", description_placeholders=placeholders
                )
            return self.async_update_reload_and_abort(
                entry,
                data_updates={
                    "auth_implementation": data["auth_implementation"],
                    "token": data["token"],
                },
            )

        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=address,
            data={
                **data,
                CONF_ENTRY_TYPE: ENTRY_TYPE_MAILBOX,
                CONF_PROVIDER: provider,
                CONF_ADDRESS: address,
            },
            options=mailbox_defaults(provider),
        )


class HubOptionsFlow(OptionsFlow):
    """Options of the hub: notifications, Live Activities, storage and AI.

    The hub applies them live: a reload would orphan the loaded mailboxes.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the hub options."""
        return await self.async_step_hub()

    async def async_step_hub(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate and store the hub options."""
        errors: dict[str, str] = {}
        if user_input is None:
            values = {**HUB_DEFAULTS, **self.config_entry.options}
        else:
            values = dict(user_input)
            options = self._options(user_input)
            errors = await self._async_validate(options)
            if not errors:
                return self.async_create_entry(data=options)
        return self.async_show_form(
            step_id="hub",
            data_schema=self.add_suggested_values_to_schema(HUB_SCHEMA, values),
            errors=errors,
        )

    def _options(self, user_input: Mapping[str, Any]) -> dict[str, Any]:
        """Return the options to store from the submitted form."""
        test_mode = bool(user_input.get(CONF_TEST_MODE, False))
        test_device = user_input.get(CONF_TEST_DEVICE) or None
        if not test_mode and test_device is None:
            test_device = self.config_entry.options.get(CONF_TEST_DEVICE)
        options: dict[str, Any] = {
            CONF_NOTIFY_PERSONS: list(user_input.get(CONF_NOTIFY_PERSONS) or []),
            CONF_EXCLUDED_DEVICES: list(user_input.get(CONF_EXCLUDED_DEVICES) or []),
            CONF_START_TIME: _time_value(user_input[CONF_START_TIME]).strftime(
                "%H:%M:%S"
            ),
            CONF_CUTOFF_TIME: _time_value(user_input[CONF_CUTOFF_TIME]).strftime(
                "%H:%M:%S"
            ),
            CONF_COLLAPSE_THRESHOLD: int(user_input[CONF_COLLAPSE_THRESHOLD]),
            CONF_ITEM_NAMES: bool(user_input[CONF_ITEM_NAMES]),
            CONF_PIN_ON_LOCK_SCREEN: bool(user_input[CONF_PIN_ON_LOCK_SCREEN]),
            CONF_SEVENTEENTRACK: bool(user_input[CONF_SEVENTEENTRACK]),
            CONF_TEST_MODE: test_mode,
            CONF_ARCHIVE_DAYS: int(user_input[CONF_ARCHIVE_DAYS]),
            CONF_PURGE_DAYS: int(user_input[CONF_PURGE_DAYS]),
            CONF_AI_MODE: str(user_input[CONF_AI_MODE]),
        }
        if test_device:
            options[CONF_TEST_DEVICE] = test_device
        if ai_task := user_input.get(CONF_AI_TASK):
            options[CONF_AI_TASK] = ai_task
        options.update(self._parcel_app_options(user_input))
        return options

    def _parcel_app_options(self, user_input: Mapping[str, Any]) -> dict[str, Any]:
        """Return the Parcel app options to store: none without a key."""
        key = str(user_input.get(CONF_PARCEL_APP_KEY) or "").strip()
        if not key:
            return {}
        options: dict[str, Any] = {
            CONF_PARCEL_APP_KEY: key,
            CONF_PARCEL_APP_IMPORT: bool(
                user_input.get(CONF_PARCEL_APP_IMPORT, DEFAULT_PARCEL_APP_IMPORT)
            ),
            CONF_PARCEL_APP_ADD: bool(
                user_input.get(CONF_PARCEL_APP_ADD, DEFAULT_PARCEL_APP_ADD)
            ),
        }
        if owner := user_input.get(CONF_PARCEL_APP_OWNER):
            options[CONF_PARCEL_APP_OWNER] = owner
        # The settings for adding are hidden while it's off: keep them.
        adding = (
            user_input if options[CONF_PARCEL_APP_ADD] else self.config_entry.options
        )
        options[CONF_PARCEL_APP_EVERYONE] = bool(
            adding.get(CONF_PARCEL_APP_EVERYONE, DEFAULT_PARCEL_APP_EVERYONE)
        )
        options[CONF_PARCEL_APP_DAILY] = int(
            adding.get(CONF_PARCEL_APP_DAILY, DEFAULT_PARCEL_APP_DAILY)
        )
        if postcode := str(adding.get(CONF_PARCEL_APP_POSTCODE) or "").strip():
            options[CONF_PARCEL_APP_POSTCODE] = postcode
        return options

    async def _async_validate(self, options: dict[str, Any]) -> dict[str, str]:
        """Return the form errors of the hub options."""
        errors: dict[str, str] = {}
        if options[CONF_TEST_MODE] and not options.get(CONF_TEST_DEVICE):
            errors[CONF_TEST_DEVICE] = "test_device_required"
        # A cut-off at 00:00 is midnight at the end of the day.
        cutoff = _time_value(options[CONF_CUTOFF_TIME])
        if cutoff != time(0, 0) and cutoff <= _time_value(options[CONF_START_TIME]):
            errors[CONF_CUTOFF_TIME] = "cutoff_before_start"
        if options[CONF_PURGE_DAYS] <= options[CONF_ARCHIVE_DAYS]:
            errors[CONF_PURGE_DAYS] = "purge_before_archive"
        if ai_task := options.get(CONF_AI_TASK):
            check = await safety.async_check_ai_task(self.hass, ai_task)
            if not check.ok:
                errors[CONF_AI_TASK] = _ai_error(check.reason)
        if CONF_PARCEL_APP_KEY in options:
            await self._async_validate_parcel_app(options, errors)
        return errors

    async def _async_validate_parcel_app(
        self, options: dict[str, Any], errors: dict[str, str]
    ) -> None:
        """Check the Parcel app options, and a new key with one request."""
        key = options[CONF_PARCEL_APP_KEY]
        if not valid_key(key):
            errors[CONF_PARCEL_APP_KEY] = "parcel_app_key_invalid"
        if options[CONF_PARCEL_APP_ADD] and (
            postcode := options.get(CONF_PARCEL_APP_POSTCODE)
        ):
            if normalized := normalize_postcode(postcode, self.hass.config.country):
                options[CONF_PARCEL_APP_POSTCODE] = normalized
            else:
                errors[CONF_PARCEL_APP_POSTCODE] = "parcel_app_postcode_invalid"
        if not options.get(CONF_PARCEL_APP_OWNER) and self._mailboxes_have_owners():
            errors[CONF_PARCEL_APP_OWNER] = "parcel_app_owner_required"
        if errors or key == self.config_entry.options.get(CONF_PARCEL_APP_KEY):
            return
        try:
            await async_get_deliveries(self.hass, key, active_only=True)
        except ParcelAppError as err:
            if err.kind is ErrorKind.KEY:
                errors[CONF_PARCEL_APP_KEY] = "parcel_app_key_refused"
            else:
                # The sync checks the key again once Parcel answers.
                _LOGGER.debug("Couldn't check the Parcel app key: %s", err.code)

    def _mailboxes_have_owners(self) -> bool:
        """Return whether any mailbox entry has an owner."""
        return any(
            entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_MAILBOX
            and entry.options.get(CONF_OWNER)
            for entry in self.hass.config_entries.async_entries(DOMAIN)
        )


class MailboxOptionsFlow(OptionsFlowWithReload):
    """Options of a mailbox: owner, folders and polling."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the mailbox options."""
        return await self.async_step_mailbox()

    async def async_step_mailbox(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate and store the mailbox options."""
        provider = self.config_entry.data.get(CONF_PROVIDER, PROVIDER_MICROSOFT)
        schema = _mailbox_schema(provider)
        errors: dict[str, str] = {}
        if user_input is None:
            values = {**mailbox_defaults(provider), **self.config_entry.options}
        else:
            values = dict(user_input)
            options: dict[str, Any] = {
                CONF_LOOKBACK_DAYS: int(user_input[CONF_LOOKBACK_DAYS]),
                CONF_INTERVAL_MINUTES: int(user_input[CONF_INTERVAL_MINUTES]),
            }
            if owner := user_input.get(CONF_OWNER):
                options[CONF_OWNER] = owner
            if provider == PROVIDER_MICROSOFT:
                chosen = set(user_input.get(CONF_FOLDERS) or ())
                options[CONF_FOLDERS] = [f for f in MICROSOFT_FOLDERS if f in chosen]
                if not options[CONF_FOLDERS]:
                    errors[CONF_FOLDERS] = "no_folders"
            if not errors:
                return self.async_create_entry(data=options)
        return self.async_show_form(
            step_id="mailbox",
            data_schema=self.add_suggested_values_to_schema(schema, values),
            errors=errors,
            description_placeholders={
                CONF_ADDRESS: self.config_entry.data.get(
                    CONF_ADDRESS, self.config_entry.title
                )
            },
        )
