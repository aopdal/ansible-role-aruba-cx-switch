#!/usr/bin/env python3
"""
BGP-related filters for NetBox data transformation.

Supports two NetBox BGP plugins:
  - netbox-bgp  : legacy plugin, uses /api/plugins/bgp/session/
  - netbox-routing : newer plugin, uses /api/plugins/routing/bgp/

Public filters
--------------
get_bgp_session_vrf_info          : enrich netbox-bgp sessions with _vrf / _af
normalize_routing_plugin_peers    : normalize netbox-routing peer data into the
                                    same shape as get_bgp_session_vrf_info output
collect_ebgp_vrf_policy_config    : build route-map / prefix-list CLI data
                                    from netbox-bgp policy objects
collect_ebgp_vrf_policy_config_routing : same for netbox-routing objects
"""

from .utils import _debug

# VRF names that are built-in / non-configurable; treated as 'default'
_BUILTIN_VRFS = {"mgmt", "MGMT", "Global", "global", "default", "Default"}


# ---------------------------------------------------------------------------
# netbox-bgp helpers
# ---------------------------------------------------------------------------


def get_bgp_session_vrf_info(sessions, interfaces):
    """
    Enrich netbox-bgp sessions with VRF and address-family information.

    For each session, looks up ``local_address.address`` against every IP
    assigned to a device interface to derive the VRF.  Non-default VRF →
    ``_vrf`` is set to that name; default / no VRF → ``_vrf = 'default'``.
    Address family is inferred from the IP syntax (``':'`` → ipv6).

    Args:
        sessions:   List of BGP session objects from the netbox-bgp plugin.
        interfaces: List of interface objects from NetBox inventory.

    Returns:
        List of session dicts enriched with ``_vrf`` (str) and ``_af`` (str).
    """
    # Build lookup: IP address (CIDR) -> VRF name
    ip_vrf_map = {}

    for intf in interfaces or []:
        if not isinstance(intf, dict):
            continue
        if intf.get("mgmt_only"):
            continue

        vrf_obj = intf.get("vrf")
        if vrf_obj and isinstance(vrf_obj, dict):
            vrf_name = vrf_obj.get("name") or "default"
        else:
            vrf_name = "default"

        if vrf_name in _BUILTIN_VRFS and vrf_name != "default":
            vrf_name = "default"

        for ip_obj in intf.get("ip_addresses") or []:
            addr = ip_obj.get("address") if isinstance(ip_obj, dict) else str(ip_obj)
            if addr:
                ip_vrf_map[addr] = vrf_name
                _debug(
                    f"IP→VRF map: {addr} → '{vrf_name}' "
                    f"(interface '{intf.get('name')}')"
                )

    _debug(f"IP→VRF map built with {len(ip_vrf_map)} entries")

    result = []
    for session in sessions or []:
        if not isinstance(session, dict):
            continue

        local_addr_obj = session.get("local_address") or {}
        local_addr = (
            local_addr_obj.get("address", "")
            if isinstance(local_addr_obj, dict)
            else ""
        )

        vrf_name = ip_vrf_map.get(local_addr, "default")
        af = "ipv6" if ":" in local_addr else "ipv4"

        enriched = dict(session)
        enriched["_vrf"] = vrf_name
        enriched["_af"] = af

        _debug(
            f"Session '{session.get('name', '?')}': "
            f"local_address={local_addr} → VRF='{vrf_name}', AF='{af}'"
        )

        result.append(enriched)

    return result


# ---------------------------------------------------------------------------
# netbox-routing helpers
# ---------------------------------------------------------------------------


def normalize_routing_plugin_peers(  # pylint: disable=too-many-arguments
    routers,
    scopes,
    peers,
    _address_families,
    peer_address_families,
    route_maps,
    device_name,
):
    """
    Normalize netbox-routing BGP objects for ``device_name`` into the same
    enriched-session shape that ``get_bgp_session_vrf_info`` produces for
    netbox-bgp, so that all downstream configure_bgp tasks are unchanged.

    The netbox-routing server-side filters are unreliable (list endpoints
    ignore filter params and always return all objects).  All filtering is
    done client-side here.

    VRF resolution
    --------------
    VRF is explicit in ``scope.vrf``:
      - ``null``          → ``_vrf = 'default'``
      - named VRF object  → ``_vrf = vrf.name``  (built-ins normalised to 'default')

    Address family
    --------------
    Inferred from the *remote* peer IP (``peer.peer.address``):
      - contains ':'  → ``_af = 'ipv6'``
      - otherwise     → ``_af = 'ipv4'``

    Scope VRF / EVPN note
    ---------------------
    During migration from netbox-bgp (which had no address-family concept),
    imported sessions do not carry an ``l2vpn-evpn`` address-family entry in
    netbox-routing.  Peers in a global-VRF scope (``_vrf == 'default'``) are
    treated as EVPN peers by the downstream tasks, matching the legacy
    behaviour.

    Args:
        routers:              All ``bgp/router/`` objects (unfiltered).
        scopes:               All ``bgp/scope/`` objects (unfiltered).
        peers:                All ``bgp/peer/`` objects (unfiltered).
        _address_families:    All ``bgp/address-family/`` objects (unused here
                              but accepted so callers can pass the full dataset).
        peer_address_families: All ``bgp/peer-address-family/`` objects.
        route_maps:           All ``objects/route-map/`` objects (id → name map).
        device_name:          ``inventory_hostname`` of the device to filter for.

    Returns:
        List of normalised peer dicts compatible with netbox-bgp session shape,
        each enriched with ``_vrf``, ``_af``, ``import_policies``,
        ``export_policies``, ``local_address``, ``remote_address``.
    """
    # ------------------------------------------------------------------
    # Build route-map id → name lookup from objects/route-map/ list
    # ------------------------------------------------------------------
    rm_id_to_name = {}
    for rm in route_maps or []:
        if not isinstance(rm, dict):
            continue
        rm_id = rm.get("id")
        if rm_id is not None:
            rm_id_to_name[rm_id] = rm.get("name") or rm.get("display") or str(rm_id)

    # ------------------------------------------------------------------
    # Find router(s) assigned to this device
    # ------------------------------------------------------------------
    device_router_ids = set()
    for router in routers or []:
        if not isinstance(router, dict):
            continue
        obj = router.get("assigned_object")
        if isinstance(obj, dict) and obj.get("name") == device_name:
            device_router_ids.add(router["id"])

    if not device_router_ids:
        _debug(f"normalize_routing_plugin_peers: no router for device '{device_name}'")
        return []

    _debug(
        f"normalize_routing_plugin_peers: router IDs for '{device_name}': "
        f"{device_router_ids}"
    )

    # ------------------------------------------------------------------
    # Collect scope(s) for those routers; build scope_id → vrf_name map
    # ------------------------------------------------------------------
    device_scope_ids = set()
    scope_vrf_map = {}  # scope_id → vrf_name
    scope_asn_map = {}  # scope_id → local ASN int

    for scope in scopes or []:
        if not isinstance(scope, dict):
            continue
        router_obj = scope.get("router") or {}
        if not isinstance(router_obj, dict):
            continue
        if router_obj.get("id") not in device_router_ids:
            continue

        scope_id = scope["id"]
        device_scope_ids.add(scope_id)

        vrf_obj = scope.get("vrf")
        if isinstance(vrf_obj, dict) and vrf_obj.get("name"):
            vrf_name = vrf_obj["name"]
            if vrf_name in _BUILTIN_VRFS and vrf_name != "default":
                vrf_name = "default"
        else:
            vrf_name = "default"
        scope_vrf_map[scope_id] = vrf_name

        asn_obj = router_obj.get("asn") or {}
        if isinstance(asn_obj, dict):
            scope_asn_map[scope_id] = asn_obj.get("asn")

    if not device_scope_ids:
        _debug(f"normalize_routing_plugin_peers: no scopes for device '{device_name}'")
        return []

    # ------------------------------------------------------------------
    # Collect peers belonging to those scopes
    # ------------------------------------------------------------------
    device_peers = []
    device_peer_ids = set()

    for peer in peers or []:
        if not isinstance(peer, dict):
            continue
        scope_obj = peer.get("scope") or {}
        if not isinstance(scope_obj, dict):
            continue
        if scope_obj.get("id") not in device_scope_ids:
            continue
        # Skip explicitly disabled peers
        if peer.get("enabled") is False:
            continue
        device_peers.append(peer)
        device_peer_ids.add(peer["id"])

    _debug(
        f"normalize_routing_plugin_peers: {len(device_peers)} peers "
        f"for '{device_name}'"
    )

    # ------------------------------------------------------------------
    # Build peer_id → {in: [rm_name,...], out: [rm_name,...]} from
    # peer-address-family objects
    # ------------------------------------------------------------------
    peer_routemaps = {}  # peer_id → {"in": [...], "out": [...]}

    for paf in peer_address_families or []:
        if not isinstance(paf, dict):
            continue
        if paf.get("assigned_object_type") != "netbox_routing.bgppeer":
            continue
        peer_id = paf.get("assigned_object_id")
        if peer_id not in device_peer_ids:
            continue

        if peer_id not in peer_routemaps:
            peer_routemaps[peer_id] = {"in": [], "out": []}

        rm_in_id = paf.get("routemap_in")
        rm_out_id = paf.get("routemap_out")

        if rm_in_id is not None:
            rm_name = rm_id_to_name.get(rm_in_id, str(rm_in_id))
            if rm_name not in peer_routemaps[peer_id]["in"]:
                peer_routemaps[peer_id]["in"].append(rm_name)

        if rm_out_id is not None:
            rm_name = rm_id_to_name.get(rm_out_id, str(rm_out_id))
            if rm_name not in peer_routemaps[peer_id]["out"]:
                peer_routemaps[peer_id]["out"].append(rm_name)

    # ------------------------------------------------------------------
    # Normalise each peer into the compat shape
    # ------------------------------------------------------------------
    result = []

    for peer in device_peers:
        scope_obj = peer.get("scope") or {}
        scope_id = scope_obj.get("id")

        vrf_name = scope_vrf_map.get(scope_id, "default")

        source_obj = peer.get("source") or {}
        local_addr = (
            source_obj.get("address", "") if isinstance(source_obj, dict) else ""
        )

        peer_ip_obj = peer.get("peer") or {}
        remote_addr = (
            peer_ip_obj.get("address", "") if isinstance(peer_ip_obj, dict) else ""
        )

        af = "ipv6" if ":" in remote_addr else "ipv4"

        local_asn = scope_asn_map.get(scope_id)
        remote_asn_obj = peer.get("remote_as") or {}
        remote_asn = (
            remote_asn_obj.get("asn") if isinstance(remote_asn_obj, dict) else None
        )

        rms = peer_routemaps.get(peer["id"], {"in": [], "out": []})

        # Use None as policy id — collect_ebgp_vrf_policy_config_routing
        # matches by name, not by id.
        normalized = {
            "name": peer.get("name", ""),
            # Keep legacy field names so existing task references work
            "local_address": {"address": local_addr},
            "remote_address": {"address": remote_addr},
            "local_as": {"asn": local_asn},
            "remote_as": {"asn": remote_asn},
            # Synthesise status so selectattr('status.value', ...) tasks work
            "status": {"value": "active" if peer.get("enabled", True) else "disabled"},
            "_vrf": vrf_name,
            "_af": af,
            "import_policies": [{"id": None, "name": n} for n in rms["in"]],
            "export_policies": [{"id": None, "name": n} for n in rms["out"]],
        }

        _debug(
            f"normalize_routing_plugin_peers: '{peer.get('name')}' "
            f"VRF={vrf_name} AF={af} local={local_addr} remote={remote_addr} "
            f"import={rms['in']} export={rms['out']}"
        )

        result.append(normalized)

    return result


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------


def _action_str(raw):
    """Normalise action field to plain string (permit/deny)."""
    if isinstance(raw, dict):
        return raw.get("value", "permit")
    return str(raw) if raw else "permit"


# ---------------------------------------------------------------------------
# netbox-bgp policy config collector
# ---------------------------------------------------------------------------


def collect_ebgp_vrf_policy_config(sessions, all_policy_rules, all_prefix_list_rules):
    """
    Collect routing policies and prefix lists referenced by BGP VRF sessions
    (netbox-bgp plugin format).

    Expected field names (netbox-bgp)
    ----------------------------------
    Routing policy rule (``/api/plugins/bgp/routing-policy-rule/``):
      - ``routing_policy``  : dict ``{id, name}``
      - ``index``           : int (sequence number)
      - ``action``          : plain string or ``{value, label}`` dict
      - ``match_ip_address``: list of ``{id, name}`` prefix list objects
      - ``match_ipv6_address``: list of ``{id, name}`` prefix list objects
      - ``set_actions``     : dict, e.g. ``{"as-path prepend": [65015], "local-preference": 300}``

    Prefix list rule (``/api/plugins/bgp/prefix-list-rule/``):
      - ``prefix_list``  : dict ``{id, name}``
      - ``index``        : int
      - ``action``       : plain string
      - ``prefix``       : IPAM prefix FK object ``{prefix: "172.27.4.0/24"}``
      - ``prefix_custom``: fallback plain string when IPAM FK is null

    Args:
        sessions:               Enriched BGP session list (with ``_vrf``/``_af``).
        all_policy_rules:       All routing policy rule objects.
        all_prefix_list_rules:  All prefix list rule objects.

    Returns:
        dict with ``prefix_lists`` and ``route_map_rules`` lists.
    """
    # Collect all policy IDs referenced by the sessions
    policy_id_to_name = {}

    for session in sessions or []:
        if not isinstance(session, dict):
            continue
        for direction in ("import_policies", "export_policies"):
            for policy in session.get(direction) or []:
                if not isinstance(policy, dict):
                    continue
                pid = policy.get("id")
                pname = policy.get("name") or str(pid)
                if pid is not None:
                    policy_id_to_name[pid] = pname

    if not policy_id_to_name:
        return {"prefix_lists": [], "route_map_rules": []}

    _debug(
        f"collect_ebgp_vrf_policy_config: {len(policy_id_to_name)} "
        f"referenced policies: {list(policy_id_to_name.values())}"
    )

    referenced_prefix_list_ids = {}  # {pl_id: {"name": str, "af": str}}
    route_map_rules = []

    for rule in all_policy_rules or []:
        if not isinstance(rule, dict):
            continue

        policy_obj = rule.get("routing_policy") or rule.get("policy") or {}
        pid = policy_obj.get("id") if isinstance(policy_obj, dict) else None
        if pid not in policy_id_to_name:
            continue

        policy_name = policy_id_to_name[pid]
        index = rule.get("index", 0)
        action = _action_str(rule.get("action"))

        commands = [f"route-map {policy_name} {action} seq {index}"]

        for af_field, af_cmd, af_key in (
            ("match_ip_address", "match ip address prefix-list", "ipv4"),
            ("match_ipv6_address", "match ipv6 address prefix-list", "ipv6"),
        ):
            match_pfx_raw = rule.get(af_field)
            if not match_pfx_raw:
                continue
            if isinstance(match_pfx_raw, dict):
                match_pfx_raw = [match_pfx_raw]
            for match_pfx in match_pfx_raw if isinstance(match_pfx_raw, list) else []:
                if not isinstance(match_pfx, dict):
                    continue
                pfx_id = match_pfx.get("id")
                pfx_name = match_pfx.get("name") or str(pfx_id)
                if pfx_name:
                    commands.append(f"{af_cmd} {pfx_name}")
                if pfx_id is not None:
                    referenced_prefix_list_ids[pfx_id] = {
                        "name": pfx_name,
                        "af": af_key,
                    }

        set_actions = rule.get("set_actions") or {}
        if isinstance(set_actions, dict):
            local_pref = set_actions.get("local-preference")
            if local_pref is not None:
                commands.append(f"set local-preference {local_pref}")
            prepend = set_actions.get("as-path prepend")
            if prepend is not None:
                asns = (
                    " ".join(str(a) for a in prepend)
                    if isinstance(prepend, list)
                    else str(prepend)
                )
                commands.append(f"set as-path prepend {asns}")

        route_map_rules.append(
            {
                "name": policy_name,
                "index": index,
                "action": action,
                "commands": commands,
            }
        )

    # Collect prefix list rules
    prefix_lists_map = {}

    for rule in all_prefix_list_rules or []:
        if not isinstance(rule, dict):
            continue

        pl_obj = rule.get("prefix_list") or {}
        pl_id = pl_obj.get("id") if isinstance(pl_obj, dict) else None
        if pl_id not in referenced_prefix_list_ids:
            continue

        pl_info = referenced_prefix_list_ids[pl_id]
        pl_name = pl_info["name"]
        pl_af = pl_info["af"]

        if isinstance(pl_obj, dict):
            af_raw = pl_obj.get("address_family")
            if af_raw:
                if isinstance(af_raw, dict):
                    af_val = str(af_raw.get("value") or "").lower()
                else:
                    af_val = str(af_raw).lower()
                if "6" in af_val:
                    pl_af = "ipv6"
                elif af_val:
                    pl_af = "ipv4"

        index = rule.get("index", 0)
        action = _action_str(rule.get("action"))

        prefix_raw = rule.get("prefix") or rule.get("network") or ""
        if isinstance(prefix_raw, dict):
            network = (
                prefix_raw.get("prefix")
                or prefix_raw.get("display")
                or prefix_raw.get("address")
                or ""
            )
        else:
            network = prefix_raw
        if not network:
            network = rule.get("prefix_custom") or ""

        if pl_name not in prefix_lists_map:
            prefix_lists_map[pl_name] = {"af": pl_af, "rules": []}
        prefix_lists_map[pl_name]["rules"].append(
            {"index": index, "action": action, "prefix": str(network)}
        )

    prefix_lists = [
        {
            "name": name,
            "af": data["af"],
            "rules": sorted(data["rules"], key=lambda r: r["index"]),
        }
        for name, data in prefix_lists_map.items()
    ]

    route_map_rules.sort(key=lambda r: (r["name"], r["index"]))

    return {
        "prefix_lists": prefix_lists,
        "route_map_rules": route_map_rules,
    }


# ---------------------------------------------------------------------------
# netbox-routing policy config collector
# ---------------------------------------------------------------------------


def collect_ebgp_vrf_policy_config_routing(
    sessions, all_route_map_entries, all_prefix_list_entries
):
    """
    Collect route-maps and prefix lists referenced by BGP VRF sessions
    (netbox-routing plugin format).

    Expected field names (netbox-routing)
    ---------------------------------------
    Route-map entry (``/api/plugins/routing/objects/route-map-entry/``):
      - ``route_map``         : dict ``{id, name, display}``
      - ``sequence``          : int
      - ``action``            : plain string
      - ``match_prefix_list`` : list of ``{id, name, display}`` (unified IPv4+IPv6)
      - ``set``               : dict, e.g. ``{"as-path prepend": [65015]}``

    Prefix-list entry (``/api/plugins/routing/objects/prefix-list-entry/``):
      - ``prefix_list``        : dict ``{id, name}``
      - ``sequence``           : int
      - ``action``             : plain string
      - ``assigned_prefix``    : IPAM prefix or custom-prefix object with
                                 ``{prefix: "172.27.4.0/24"}``
      - ``assigned_prefix_type``: ``"ipam.prefix"`` or ``"netbox_routing.customprefix"``
      - ``le``                 : optional int (less-than-or-equal prefix length)
      - ``ge``                 : optional int (greater-than-or-equal prefix length)

    Address-family determination for prefix-lists
    -----------------------------------------------
    netbox-routing prefix-lists have no explicit address-family field.  AF is
    inferred from the prefix content: any ``':'`` in the prefix string means
    IPv6, otherwise IPv4.

    Args:
        sessions:                 Enriched peer list (output of
                                  ``normalize_routing_plugin_peers``).
        all_route_map_entries:    All ``objects/route-map-entry/`` objects.
        all_prefix_list_entries:  All ``objects/prefix-list-entry/`` objects.

    Returns:
        dict with ``prefix_lists`` and ``route_map_rules`` lists — same
        structure as ``collect_ebgp_vrf_policy_config``.
    """
    # ------------------------------------------------------------------
    # Collect all route-map names referenced by VRF sessions
    # ------------------------------------------------------------------
    referenced_rm_names = set()

    for session in sessions or []:
        if not isinstance(session, dict):
            continue
        for direction in ("import_policies", "export_policies"):
            for policy in session.get(direction) or []:
                if not isinstance(policy, dict):
                    continue
                name = policy.get("name")
                if name:
                    referenced_rm_names.add(name)

    if not referenced_rm_names:
        return {"prefix_lists": [], "route_map_rules": []}

    _debug(
        f"collect_ebgp_vrf_policy_config_routing: {len(referenced_rm_names)} "
        f"referenced route-maps: {sorted(referenced_rm_names)}"
    )

    # ------------------------------------------------------------------
    # Parse route-map entries; track which prefix-lists they reference
    # ------------------------------------------------------------------
    # Intermediate list; match commands added after AF is known.
    rm_entries = []  # [{name, index, action, commands, _match_pl_names}]
    referenced_pl_names = set()

    for entry in all_route_map_entries or []:
        if not isinstance(entry, dict):
            continue

        rm_obj = entry.get("route_map") or {}
        if not isinstance(rm_obj, dict):
            continue
        rm_name = rm_obj.get("display") or rm_obj.get("name") or ""
        if rm_name not in referenced_rm_names:
            continue

        sequence = entry.get("sequence", entry.get("index", 0))
        action = _action_str(entry.get("action"))

        commands = [f"route-map {rm_name} {action} seq {sequence}"]

        # Collect matched prefix-list names (AF added later)
        match_pl_names = []
        for pl_obj in entry.get("match_prefix_list") or []:
            if not isinstance(pl_obj, dict):
                continue
            pl_name = pl_obj.get("display") or pl_obj.get("name") or ""
            if pl_name:
                match_pl_names.append(pl_name)
                referenced_pl_names.add(pl_name)

        # set actions
        set_dict = entry.get("set") or {}
        if isinstance(set_dict, dict):
            local_pref = set_dict.get("local-preference")
            if local_pref is not None:
                commands.append(f"set local-preference {local_pref}")
            prepend = set_dict.get("as-path prepend")
            if prepend is not None:
                asns = (
                    " ".join(str(a) for a in prepend)
                    if isinstance(prepend, list)
                    else str(prepend)
                )
                commands.append(f"set as-path prepend {asns}")

        rm_entries.append(
            {
                "name": rm_name,
                "index": sequence,
                "action": action,
                "commands": commands,
                "_match_pl_names": match_pl_names,
            }
        )

    # ------------------------------------------------------------------
    # Collect prefix-list entries; determine AF from prefix content
    # ------------------------------------------------------------------
    prefix_lists_map = {}  # pl_name → {"af": str, "rules": [...]}

    for entry in all_prefix_list_entries or []:
        if not isinstance(entry, dict):
            continue

        pl_obj = entry.get("prefix_list") or {}
        pl_name = (
            pl_obj.get("name") or pl_obj.get("display") or ""
            if isinstance(pl_obj, dict)
            else ""
        )
        if pl_name not in referenced_pl_names:
            continue

        sequence = entry.get("sequence", entry.get("index", 0))
        action = _action_str(entry.get("action"))

        # Extract the network string from assigned_prefix
        ap = entry.get("assigned_prefix")
        if isinstance(ap, dict):
            network = ap.get("prefix") or ap.get("display") or ap.get("address") or ""
        elif ap is not None:
            network = str(ap)
        else:
            network = ""

        # Determine AF from prefix content
        af = "ipv6" if ":" in str(network) else "ipv4"

        rule = {"index": sequence, "action": action, "prefix": str(network)}

        # Include le/ge if present (AOS-CX prefix-list supports them)
        le = entry.get("le")
        ge = entry.get("ge")
        if le is not None:
            rule["le"] = le
        if ge is not None:
            rule["ge"] = ge

        if pl_name not in prefix_lists_map:
            prefix_lists_map[pl_name] = {"af": af, "rules": []}
        prefix_lists_map[pl_name]["rules"].append(rule)

        _debug(
            f"prefix-list entry: {pl_name} ({af}) seq {sequence} " f"{action} {network}"
        )

    # ------------------------------------------------------------------
    # Back-fill match commands with correct AF keyword
    # ------------------------------------------------------------------
    route_map_rules = []

    for rm in rm_entries:
        commands = list(rm["commands"])
        for pl_name in rm["_match_pl_names"]:
            pl_info = prefix_lists_map.get(pl_name, {})
            af = pl_info.get("af", "ipv4")
            if af == "ipv6":
                commands.append(f"match ipv6 address prefix-list {pl_name}")
            else:
                commands.append(f"match ip address prefix-list {pl_name}")

        route_map_rules.append(
            {
                "name": rm["name"],
                "index": rm["index"],
                "action": rm["action"],
                "commands": commands,
            }
        )

        _debug(
            f"route-map entry: {rm['name']} {rm['action']} seq {rm['index']} "
            f"→ {len(commands) - 1} match/set command(s)"
        )

    # Sort: by route-map name then sequence
    route_map_rules.sort(key=lambda r: (r["name"], r["index"]))

    prefix_lists = [
        {
            "name": name,
            "af": data["af"],
            "rules": sorted(data["rules"], key=lambda r: r["index"]),
        }
        for name, data in prefix_lists_map.items()
    ]

    return {
        "prefix_lists": prefix_lists,
        "route_map_rules": route_map_rules,
    }
