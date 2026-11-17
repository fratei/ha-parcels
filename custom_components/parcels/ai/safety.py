"""Check that an AI task is a local Ollama model on the Home Assistant host.

E-mail text may only be read by a model that runs on the Home Assistant
host itself. An AI task entity passes when it belongs to the Ollama
integration, its subentry selects a model that isn't an Ollama cloud model,
and the Ollama server's host is loopback, ``localhost`` or an add-on on the
Supervisor's internal network (172.30.32.0/23). Every other entity is
refused with a reason that the config flow shows as ``ai_<reason>``.
"""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import socket
from urllib.parse import urlsplit

from homeassistant.const import CONF_MODEL, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

AI_TASK_DOMAIN = "ai_task"
OLLAMA_DOMAIN = "ollama"

REASON_OK = "ok"
REASON_NOT_FOUND = "not_found"
REASON_NOT_AI_TASK = "not_ai_task"
REASON_NOT_OLLAMA = "not_ollama"
REASON_NO_ENTRY = "no_entry"
REASON_NO_MODEL = "no_model"
REASON_CLOUD_MODEL = "cloud_model"
REASON_REMOTE_HOST = "remote_host"
REASON_UNRESOLVABLE = "unresolvable"

REASONS: tuple[str, ...] = (
    REASON_OK,
    REASON_NOT_FOUND,
    REASON_NOT_AI_TASK,
    REASON_NOT_OLLAMA,
    REASON_NO_ENTRY,
    REASON_NO_MODEL,
    REASON_CLOUD_MODEL,
    REASON_REMOTE_HOST,
    REASON_UNRESOLVABLE,
)

# Add-ons such as the Ollama add-on run on this Supervisor network.
SUPERVISOR_NETWORK = ipaddress.ip_network("172.30.32.0/23")


@dataclass(frozen=True, slots=True)
class AICheck:
    """Whether an AI task entity may be used for e-mail text."""

    ok: bool
    reason: str
    model: str | None = None
    host: str | None = None


def is_cloud_model(model: str) -> bool:
    """Return True for Ollama cloud models such as ``gpt-oss:120b-cloud``.

    A model is a cloud model when its name or its tag ends in "cloud".
    """
    model = model.strip()
    name, sep, tag = model.rpartition(":")
    if not sep or "/" in tag:
        name, tag = model, ""
    base = name.rstrip("/").rpartition("/")[2]
    return any(part.lower().endswith("cloud") for part in (base, tag) if part)


def host_from_url(url: object) -> str | None:
    """Return the lowercased host name of an Ollama server URL."""
    if not isinstance(url, str) or not url.strip():
        return None
    url = url.strip()
    if "://" not in url:
        url = f"http://{url}"
    try:
        host = urlsplit(url).hostname
    except ValueError:
        return None
    if not host:
        return None
    return host.rstrip(".").lower() or None


def is_local_address(address: str) -> bool:
    """Return True for a loopback address or one on the Supervisor network."""
    try:
        ip = ipaddress.ip_address(address.partition("%")[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if ip.is_loopback:
        return True
    return isinstance(ip, ipaddress.IPv4Address) and ip in SUPERVISOR_NETWORK


async def async_check_host(hass: HomeAssistant, host: str) -> str:
    """Return ``ok``, ``remote_host`` or ``unresolvable`` for an Ollama host.

    Host names are resolved in the executor; every address they resolve to
    must be local.
    """
    if host == "localhost":
        return REASON_OK
    try:
        ipaddress.ip_address(host.partition("%")[0])
    except ValueError:
        pass
    else:
        return REASON_OK if is_local_address(host) else REASON_REMOTE_HOST
    try:
        infos = await hass.async_add_executor_job(socket.getaddrinfo, host, None)
    except OSError, UnicodeError, ValueError:
        return REASON_UNRESOLVABLE
    addresses = {str(info[4][0]) for info in infos if info[4]}
    if not addresses:
        return REASON_UNRESOLVABLE
    if all(is_local_address(address) for address in addresses):
        return REASON_OK
    return REASON_REMOTE_HOST


async def async_check_ai_task(hass: HomeAssistant, entity_id: str) -> AICheck:
    """Check that an AI task runs on a local Ollama model on the HA host."""
    entity = er.async_get(hass).async_get(entity_id)
    if entity is None:
        return AICheck(ok=False, reason=REASON_NOT_FOUND)
    if entity.domain != AI_TASK_DOMAIN:
        return AICheck(ok=False, reason=REASON_NOT_AI_TASK)
    if entity.platform != OLLAMA_DOMAIN:
        return AICheck(ok=False, reason=REASON_NOT_OLLAMA)
    entry = (
        hass.config_entries.async_get_entry(entity.config_entry_id)
        if entity.config_entry_id
        else None
    )
    if entry is None or entry.domain != OLLAMA_DOMAIN:
        return AICheck(ok=False, reason=REASON_NO_ENTRY)
    host = host_from_url(entry.data.get(CONF_URL))
    subentry = None
    if entity.config_subentry_id:
        subentry = entry.subentries.get(entity.config_subentry_id)
    if subentry is None and entity.unique_id:
        subentry = entry.subentries.get(entity.unique_id)
    model = subentry.data.get(CONF_MODEL) if subentry is not None else None
    if not isinstance(model, str) or not model.strip():
        return AICheck(ok=False, reason=REASON_NO_MODEL, host=host)
    model = model.strip()
    if is_cloud_model(model):
        return AICheck(ok=False, reason=REASON_CLOUD_MODEL, model=model, host=host)
    if host is None:
        return AICheck(ok=False, reason=REASON_UNRESOLVABLE, model=model)
    reason = await async_check_host(hass, host)
    return AICheck(ok=reason == REASON_OK, reason=reason, model=model, host=host)
