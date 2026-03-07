#!/usr/bin/env python3
"""
BGP-related filters for NetBox data transformation.

Provides functions to enrich BGP session data with VRF and address-family
information derived from the device's interface assignments in NetBox.
"""

from .utils import _debug

# VRF names that are built-in / non-configurable; treated as 'default'
_BUILTIN_VRFS = {"mgmt", "MGMT", "Global", "global", "default", "Default"}


def get_bgp_session_vrf_info(sessions, interfaces):
    """
    Enrich BGP sessions with VRF and address-family information.

    For each session, the function:
      1. Looks up ``local_address.address`` (CIDR) against every IP address
         that is assigned to a device interface (``interface.ip_addresses``).
      2. Takes the VRF from the matched interface.
         - Non-default / custom VRF  → ``_vrf`` is set to that VRF name.
         - Default / no VRF          → ``_vrf`` is set to ``'default'``.
      3. Determines the address family from the IP address syntax:
         - Contains ':'  → ``_af = 'ipv6'``
         - Otherwise     → ``_af = 'ipv4'``

    This allows downstream tasks to split sessions into:
      - Global BGP sessions  (_vrf == 'default')  → EVPN / underlay
      - VRF BGP sessions     (_vrf != 'default')  → L3VPN / VRF peering

    Args:
        sessions:   List of BGP session objects from the NetBox BGP plugin.
        interfaces: List of interface objects from NetBox inventory
                    (nb_inventory with ``interfaces: true``).  Each interface
                    is expected to have an ``ip_addresses`` list and an
                    optional ``vrf`` dict.

    Returns:
        List of session dicts, each enriched with:
          - ``_vrf`` (str): VRF name, or ``'default'``.
          - ``_af``  (str): ``'ipv4'`` or ``'ipv6'``.
    """
    # ------------------------------------------------------------------
    # Build a lookup: IP address (CIDR) -> VRF name, from interface data
    # ------------------------------------------------------------------
    ip_vrf_map = {}

    for intf in interfaces or []:
        if not isinstance(intf, dict):
            continue

        # Skip management-only interfaces
        if intf.get("mgmt_only"):
            continue

        vrf_obj = intf.get("vrf")
        if vrf_obj and isinstance(vrf_obj, dict):
            vrf_name = vrf_obj.get("name") or "default"
        else:
            vrf_name = "default"

        # Normalise built-in VRF names to 'default'
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

    # ------------------------------------------------------------------
    # Enrich each BGP session
    # ------------------------------------------------------------------
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


def collect_ebgp_vrf_policy_config(sessions, all_policy_rules, all_prefix_list_rules):
    """
    Collect routing policies and prefix lists referenced by BGP VRF sessions.

    For each session, reads ``import_policies`` and
    ``export_policies`` (ManyToMany lists from the NetBox BGP plugin).
    Finds the matching rules in ``all_policy_rules``, builds the AOS-CX CLI
    commands for each route-map rule, and collects all prefix list entries
    referenced by those rules from ``all_prefix_list_rules``.

    Expected NetBox BGP plugin API field names
    ------------------------------------------
    Routing policy rule (``/api/plugins/bgp/routing-policy-rule/``):
      - ``routing_policy``  : dict ``{id, name}``
      - ``index``           : int (sequence number)
      - ``action``          : plain string ``"permit"`` or ``"deny"``
      - ``match_ip_address``: list of ``{id, name}`` prefix list objects (ManyToMany)
      - ``set_actions``     : dict of set operations, e.g.
                              ``{"as-path prepend": [65015], "local-preference": 300}``

    Prefix list rule (``/api/plugins/bgp/prefix-list-rule/``):
      - ``prefix_list``  : dict ``{id, name}``
      - ``index``        : int
      - ``action``       : plain string ``"permit"`` or ``"deny"``
      - ``prefix``       : IPAM prefix FK object ``{id, prefix: "172.27.4.0/24", ...}``

    Args:
        sessions:               List of BGP session objects (already enriched
                                with ``_vrf`` / ``_af`` by
                                ``get_bgp_session_vrf_info``).
        all_policy_rules:       All routing policy rule objects from the plugin.
        all_prefix_list_rules:  All prefix list rule objects from the plugin.

    Returns:
        dict:
          - ``prefix_lists`` (list): One entry per referenced prefix list::

                [{"name": "LAB-BLUE-IPV4",
                  "rules": [{"index": 10, "action": "permit",
                              "prefix": "172.27.4.0/24"}]}]

          - ``route_map_rules`` (list): One entry per route-map rule,
            with pre-built AOS-CX CLI commands::

                [{"name": "LAB-BLUE-IPV4-OUT-01", "index": 10,
                  "action": "permit",
                  "commands": ["route-map LAB-BLUE-IPV4-OUT-01 permit 10",
                               "match ip address prefix-list LAB-BLUE-IPV4",
                               "set as-path prepend 65015"]}]
    """

    def _action_str(raw):
        """Normalise action field to plain string (permit/deny)."""
        if isinstance(raw, dict):
            return raw.get("value", "permit")
        return str(raw) if raw else "permit"

    # ------------------------------------------------------------------
    # Collect all policy IDs referenced by the sessions
    # ------------------------------------------------------------------
    policy_id_to_name = {}  # {policy_id: policy_name}

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
        f"collect_ebgp_vrf_policy_config: found {len(policy_id_to_name)} "
        f"referenced policies: {list(policy_id_to_name.values())}"
    )

    # ------------------------------------------------------------------
    # Find matching routing policy rules and build CLI command lists
    # ------------------------------------------------------------------
    referenced_prefix_list_ids = {}  # {prefix_list_id: prefix_list_name}
    route_map_rules = []

    for rule in all_policy_rules or []:
        if not isinstance(rule, dict):
            continue

        # netbox-bgp plugin uses 'routing_policy' as the FK field name;
        # fall back to 'policy' for other implementations
        policy_obj = rule.get("routing_policy") or rule.get("policy") or {}
        pid = policy_obj.get("id") if isinstance(policy_obj, dict) else None
        if pid not in policy_id_to_name:
            continue

        policy_name = policy_id_to_name[pid]
        index = rule.get("index", 0)
        action = _action_str(rule.get("action"))

        commands = [f"route-map {policy_name} {action} seq {index}"]

        # match ip address prefix-list
        # netbox-bgp returns match_ip_address as a ManyToMany list;
        # handle both list and single-object forms
        match_pfx_raw = rule.get("match_ip_address")
        if match_pfx_raw:
            if isinstance(match_pfx_raw, dict):
                match_pfx_raw = [match_pfx_raw]
            for match_pfx in match_pfx_raw if isinstance(match_pfx_raw, list) else []:
                if not isinstance(match_pfx, dict):
                    continue
                pfx_id = match_pfx.get("id")
                pfx_name = match_pfx.get("name") or str(pfx_id)
                if pfx_name:
                    commands.append(f"match ip address prefix-list {pfx_name}")
                if pfx_id is not None:
                    referenced_prefix_list_ids[pfx_id] = pfx_name

        # set actions — stored as a dict: {"as-path prepend": [65015], "local-preference": 300, ...}
        set_actions = rule.get("set_actions") or {}
        if isinstance(set_actions, dict):
            local_pref = set_actions.get("local-preference")
            if local_pref is not None:
                commands.append(f"set local-preference {local_pref}")

            prepend = set_actions.get("as-path prepend")
            if prepend is not None:
                # value is a list of ASNs to prepend, e.g. [65015]
                if isinstance(prepend, list):
                    asns = " ".join(str(a) for a in prepend)
                else:
                    asns = str(prepend)
                commands.append(f"set as-path prepend {asns}")

        route_map_rules.append(
            {
                "name": policy_name,
                "index": index,
                "action": action,
                "commands": commands,
            }
        )

        _debug(
            f"route-map rule: {policy_name} {action} {index} → "
            f"{len(commands) - 1} match/set command(s)"
        )

    # ------------------------------------------------------------------
    # Collect prefix list rules for all referenced prefix lists
    # ------------------------------------------------------------------
    prefix_lists_map = {}  # {prefix_list_name: [rule_dicts]}

    for rule in all_prefix_list_rules or []:
        if not isinstance(rule, dict):
            continue

        pl_obj = rule.get("prefix_list") or {}
        pl_id = pl_obj.get("id") if isinstance(pl_obj, dict) else None
        if pl_id not in referenced_prefix_list_ids:
            continue

        pl_name = referenced_prefix_list_ids[pl_id]
        index = rule.get("index", 0)
        action = _action_str(rule.get("action"))

        # Prefix — netbox-bgp stores it as an IPAM prefix FK object under "prefix";
        # the actual CIDR string is at prefix["prefix"].
        # Falls back to "prefix_custom" (plain string field) or legacy "network".
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
        # If the IPAM FK object was None/missing, try the free-text custom field
        if not network:
            network = rule.get("prefix_custom") or ""

        if pl_name not in prefix_lists_map:
            prefix_lists_map[pl_name] = []
        prefix_lists_map[pl_name].append(
            {"index": index, "action": action, "prefix": str(network)}
        )

        _debug(f"prefix-list rule: {pl_name} seq {index} {action} {network}")

    # Sort rules within each prefix list by sequence number
    prefix_lists = [
        {
            "name": name,
            "rules": sorted(rules, key=lambda r: r["index"]),
        }
        for name, rules in prefix_lists_map.items()
    ]

    # Sort route-map rules by policy name, then sequence number
    route_map_rules.sort(key=lambda r: (r["name"], r["index"]))

    return {
        "prefix_lists": prefix_lists,
        "route_map_rules": route_map_rules,
    }
