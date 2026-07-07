#!/usr/bin/env python3
"""
Static route filters for NetBox data transformation

Compares desired static routes (from the NetBox ``static_routes``
config_context, organised per VRF) against the current device state
(``aoscx_static_route_facts``, gathered via REST API) to compute the
minimal set of create/update and delete operations.

The ``arubanetworks.aoscx.aoscx_static_route`` module is not idempotent:
pyaoscx always deletes and recreates the route's single next-hop (id 0)
on every ``state: create`` call, so every invocation reports
``changed: True`` regardless of whether anything actually changed. This
module pre-compares desired vs. actual state so the role only pushes
routes that differ, matching the pattern used for L3 interfaces.

Only a single next-hop per prefix is supported (no ECMP) - this mirrors
the pyaoscx/module limitation (next-hop is always id 0).
"""

from .utils import _debug

_DEFAULT_TYPE = "forward"
_DEFAULT_DISTANCE = 1


def get_static_route_changes(static_routes, static_route_facts=None):
    """Compute static routes that need to be created/updated or deleted.

    Args:
        static_routes (dict): NetBox config_context ``static_routes`` value.
            Keyed by VRF name, each value a list of route dicts with keys:
            ``prefix`` (required), ``type`` (forward/blackhole/reject,
            default ``forward``), ``next_hop`` (IP address, optional),
            ``next_hop_interface`` (optional), ``distance`` (default 1).
        static_route_facts (dict or None): Current device state, keyed by
            VRF name then prefix, e.g.::

                {
                  "default": {
                    "0.0.0.0/0": {
                      "type": "forward",
                      "distance": 1,
                      "next_hop_ip_address": "172.18.17.33",
                      "next_hop_interface": None,
                    }
                  }
                }

            When ``None``, facts are unavailable (REST API fact gathering
            disabled) - every desired route is pushed and no deletions are
            computed (deletion requires a reliable view of device state).

    Returns:
        dict: ``{"routes_to_apply": [...], "routes_to_delete": [...]}``.
        Each entry in ``routes_to_apply`` contains the full set of
        ``aoscx_static_route`` module parameters (``vrf_name``,
        ``destination_address_prefix``, ``type``, ``distance``,
        ``next_hop_ip_address``, ``next_hop_interface``). Each entry in
        ``routes_to_delete`` contains ``vrf_name`` and
        ``destination_address_prefix``.
    """
    if not isinstance(static_routes, dict):
        _debug("No static_routes provided (not a dict) - nothing to configure")
        static_routes = {}

    facts_available = isinstance(static_route_facts, dict)
    if not facts_available:
        _debug("No static_route_facts provided - all desired routes will be pushed")

    routes_to_apply = []
    desired_keys = set()

    for vrf_name, routes in static_routes.items():
        if not isinstance(routes, list):
            continue
        for route in routes:
            if not isinstance(route, dict):
                continue
            prefix = route.get("prefix")
            if not prefix:
                _debug(f"Skipping route with no prefix in VRF {vrf_name}")
                continue

            route_type = route.get("type") or _DEFAULT_TYPE
            distance = int(route.get("distance", _DEFAULT_DISTANCE))
            next_hop_ip = route.get("next_hop") or None
            next_hop_interface = route.get("next_hop_interface") or None

            desired_keys.add((vrf_name, prefix))

            entry = {
                "vrf_name": vrf_name,
                "destination_address_prefix": prefix,
                "type": route_type,
                "distance": distance,
                "next_hop_ip_address": next_hop_ip,
                "next_hop_interface": next_hop_interface,
            }

            if not facts_available:
                routes_to_apply.append(entry)
                continue

            current = (static_route_facts.get(vrf_name) or {}).get(prefix)
            if current is None:
                _debug(f"Route {prefix} in VRF {vrf_name} not found on device - will create")
                routes_to_apply.append(entry)
                continue

            if (
                str(current.get("type")) != str(route_type)
                or int(current.get("distance", _DEFAULT_DISTANCE)) != distance
                or (current.get("next_hop_ip_address") or None) != next_hop_ip
                or (current.get("next_hop_interface") or None) != next_hop_interface
            ):
                _debug(f"Route {prefix} in VRF {vrf_name} differs from device state - will update")
                routes_to_apply.append(entry)

    routes_to_delete = []
    if facts_available:
        for vrf_name, prefixes in static_route_facts.items():
            if not isinstance(prefixes, dict):
                continue
            for prefix in prefixes:
                if (vrf_name, prefix) not in desired_keys:
                    _debug(f"Route {prefix} in VRF {vrf_name} not in NetBox - will delete")
                    routes_to_delete.append(
                        {"vrf_name": vrf_name, "destination_address_prefix": prefix}
                    )

    _debug(
        f"Static route changes: {len(routes_to_apply)} to apply, "
        f"{len(routes_to_delete)} to delete"
    )

    return {"routes_to_apply": routes_to_apply, "routes_to_delete": routes_to_delete}
