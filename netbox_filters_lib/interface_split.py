"""
Interface split (breakout) helpers.

NetBox 4.7 added a ``channels`` field on interfaces. A physical port with
``channels: 4`` is a breakout port: on AOS-CX the parent gets ``split 4``
and the device creates the child interfaces ``<parent>:1`` ... ``<parent>:4``
(modelled in NetBox as separate interfaces with ``parent`` set to the port
and ``channel_id`` 1-4). The children are configured like any other
physical interface; only the parent needs the ``split`` command.

NetBox 4.6 and older have no ``channels`` field at all, so a missing key
must behave exactly like ``channels: null`` (no split).

Device state is read from the REST API split attributes when available
(``aoscx_interface_split_facts``), otherwise from ``show running-config``.
"""

import re

from .utils import get_interface_type_value

_INTERFACE_RE = re.compile(r"^interface (\S+)\s*$")
_SPLIT_RE = re.compile(r"^split(?:\s+(\d+))?\s*$")


def _desired_channels(interface):
    """Return the desired split count for a NetBox interface, or None."""
    if not isinstance(interface, dict):
        return None
    if get_interface_type_value(interface) in ("virtual", "lag"):
        return None
    channels = interface.get("channels")
    if channels is None or isinstance(channels, bool):
        return None
    try:
        channels = int(channels)
    except (TypeError, ValueError):
        return None
    return channels if channels > 1 else None


def parse_interface_splits(running_config):
    """
    Return the ``split`` state of every interface in a running-config.

    Args:
        running_config: Full ``show running-config`` text from the device.

    Returns:
        Dict of interface name -> split count (int). A bare ``split`` line
        (platform default count) is reported as ``0``.
    """
    splits = {}
    if not running_config or not isinstance(running_config, str):
        return splits

    current = None
    for raw_line in running_config.splitlines():
        if raw_line and not raw_line[0].isspace():
            match = _INTERFACE_RE.match(raw_line.strip())
            current = match.group(1) if match else None
            continue
        if current is None:
            continue
        match = _SPLIT_RE.match(raw_line.strip())
        if match:
            splits[current] = int(match.group(1)) if match.group(1) else 0
    return splits


def parse_rest_interface_splits(split_facts):
    """
    Return the split state of every interface from REST API facts.

    ``split_facts`` is the ``/system/interfaces`` response with the
    ``split_admin_status``, ``split_children`` and ``split_parent``
    attributes. A splittable port always lists its children; whether it is
    actually split shows in the admin status: the split port itself goes
    ``inactive`` and its children in use go ``active``. Unsplit: port
    ``active``, children ``inactive``. Not splittable: ``none`` / ``null``.

    Args:
        split_facts: Dict of interface name -> split attributes.

    Returns:
        Dict of splittable port name -> split count (int, the number of
        active children) or None when the port is not split. Ports that
        cannot be split are left out.
    """
    splits = {}
    if not isinstance(split_facts, dict):
        return splits

    for name, attrs in split_facts.items():
        if not isinstance(attrs, dict):
            continue
        children = attrs.get("split_children")
        if not isinstance(children, dict) or not children:
            continue
        if attrs.get("split_admin_status") != "inactive":
            splits[name] = None
            continue
        active = [
            child
            for child in children
            if isinstance(split_facts.get(child), dict)
            and split_facts[child].get("split_admin_status") == "active"
        ]
        # Children missing from the response: still split, count unknown.
        splits[name] = len(active) if active else 0
    return splits


def get_interfaces_to_split(interfaces, running_config=None, split_facts=None):
    """
    Find NetBox interfaces whose ``channels`` value needs a ``split`` push.

    Only adds splits; never removes one. Un-splitting is destructive (it
    deletes the child interfaces and their config) and a NetBox 4.6 instance
    cannot express "split" at all, so a missing/null ``channels`` is never
    treated as "un-split this port".

    Device state comes from ``split_facts`` (REST API, preferred) when it
    carries ``split_children`` attributes, otherwise from ``running_config``.

    Args:
        interfaces: List of NetBox interface dicts.
        running_config: ``show running-config`` text.
        split_facts: REST ``/system/interfaces`` split attributes, see
            parse_rest_interface_splits. With neither source, every
            interface with ``channels`` > 1 is returned.

    Returns:
        List of dicts ``{"name", "channels", "current", "supported"}``
        sorted by name. ``current`` is the split count on the device (None
        when the port is not split, 0 when split with unknown count).
        ``supported`` is False when the REST facts show the port cannot be
        split; it is always True without REST facts (cannot tell).
    """
    if not isinstance(interfaces, list):
        return []

    # Only trust REST facts that actually carry the split attributes:
    # firmware that ignores unknown attributes would otherwise make every
    # port look unsplittable.
    use_rest = isinstance(split_facts, dict) and any(
        isinstance(attrs, dict) and "split_children" in attrs
        for attrs in split_facts.values()
    )
    if use_rest:
        device_splits = parse_rest_interface_splits(split_facts)
    else:
        device_splits = parse_interface_splits(running_config)

    result = []
    for interface in interfaces:
        channels = _desired_channels(interface)
        if channels is None:
            continue
        name = interface.get("name")
        if not name:
            continue
        supported = name in device_splits if use_rest else True
        current = device_splits.get(name)
        # 0 = split with unknown count (bare "split", or children missing
        # from REST facts); re-splitting wipes the port config, so leave it.
        if current == channels or current == 0:
            continue
        result.append(
            {
                "name": name,
                "channels": channels,
                "current": current,
                "supported": supported,
            }
        )

    return sorted(result, key=lambda item: item["name"])
