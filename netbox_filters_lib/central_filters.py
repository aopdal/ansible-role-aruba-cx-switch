"""
HPE Aruba Networking Central connection filters

Decides whether the ``hpe-anw-central`` connection must be enabled or
disabled on a device. Desired state comes from a NetBox device tag (by
default ``hpe-anw-central-mon``); current state from REST facts
(``/system/hpe_anw_central`` -> ``disable``) or, without those, from the
running-config.

AOS-CX hides the enabled state in the running-config: an enabled
connection renders no ``hpe-anw-central`` block at all, a disabled one
renders::

    hpe-anw-central
        disable
"""

from .utils import _debug

_CENTRAL_CONTEXT = "hpe-anw-central"


def has_device_tag(tags=None, tag=None):
    """Return True when the NetBox device tags contain ``tag``.

    Tags are matched on slug or name, case-insensitively. The NetBox
    inventory plugin returns tag slugs as strings; full tag objects (dicts
    with ``slug``/``name``) are accepted too.
    """
    if not tag:
        return False
    wanted = str(tag).lower()
    for t in tags or []:
        if isinstance(t, dict):
            names = (t.get("slug"), t.get("name"))
        else:
            names = (t,)
        if any(n is not None and str(n).lower() == wanted for n in names):
            return True
    return False


def central_disabled_in_running_config(running_config):
    """Return True when the running-config disables the Central connection.

    Looks for a ``disable`` line inside the ``hpe-anw-central`` context. A
    missing context means enabled (AOS-CX does not render ``enable``).
    """
    in_context = False
    for line in str(running_config or "").splitlines():
        if not line.strip() or line.strip() == "!":
            in_context = False
            continue
        if not line[0].isspace():
            in_context = line.strip() == _CENTRAL_CONTEXT
            continue
        if in_context and line.strip() == "disable":
            return True
    return False


def get_central_changes(central_facts=None, tags=None, tag=None, idempotent_mode=False, running_config=None):
    """Return the Central connection change for a device.

    Args:
        central_facts (dict): REST response of ``/system/hpe_anw_central``
            (needs ``disable``), or ``None`` when REST facts were not gathered.
        tags (list): NetBox device tags.
        tag (str): Tag that requests the connection to be enabled.
        idempotent_mode (bool): When True, devices without the tag get the
            connection disabled; otherwise they are left alone.
        running_config (str): Fallback source for the current state when
            ``central_facts`` has no ``disable`` key.

    Returns:
        dict: ``desired`` (enabled|disabled|unmanaged), ``current``
        (enabled|disabled|unknown), ``source`` (rest|running_config|none) and
        ``action`` (``enable``, ``disable`` or ``None``).
    """
    if has_device_tag(tags, tag):
        desired = "enabled"
    elif idempotent_mode:
        desired = "disabled"
    else:
        desired = "unmanaged"

    if isinstance(central_facts, dict) and "disable" in central_facts:
        current = "disabled" if central_facts.get("disable") else "enabled"
        source = "rest"
    elif running_config is not None:
        current = "disabled" if central_disabled_in_running_config(running_config) else "enabled"
        source = "running_config"
    else:
        current = "unknown"
        source = "none"

    action = None
    if desired != "unmanaged" and desired != current:
        action = "enable" if desired == "enabled" else "disable"

    _debug(f"Central: desired={desired} current={current} ({source}) action={action}")
    return {"desired": desired, "current": current, "source": source, "action": action}
