#!/usr/bin/env python3
"""
BGP-related filters for NetBox data transformation.

Provides functions to enrich BGP session data with VRF and address-family
information derived from the device's interface assignments in NetBox.
"""

import re

from .utils import _debug, is_ipv6_address

# VRF names that are built-in / non-configurable; treated as 'default'
_BUILTIN_VRFS = {"mgmt", "MGMT", "Global", "global", "default", "Default"}

# BGP redistribution is not part of the netbox-bgp plugin's session data
# model, so it is driven by the 'bgp_redistribute' NetBox config_context key
# instead - see docs/BGP_CONFIGURATION.md#bgp-redistribution.
_VALID_BGP_ADDRESS_FAMILIES = {"ipv4", "ipv6"}
_VALID_REDISTRIBUTE_PROTOCOLS = {
    "connected", "static", "ospf", "ospfv3", "rip"}

# Generic per-neighbor address-family CLI options (e.g. 'soft-reconfiguration
# inbound') are likewise not part of the netbox-bgp plugin's session data
# model, so they are driven by the 'bgp_neighbor_options' NetBox
# config_context key - see docs/BGP_CONFIGURATION.md#bgp-neighbor-options.
# These keywords are already managed elsewhere in tasks/configure_bgp.yml
# (remote-as, update-source, route-maps, etc.) - cleanup must never touch
# lines starting with one of them, even if absent from bgp_neighbor_options,
# or it would fight those other tasks.
_RESERVED_NEIGHBOR_KEYWORDS = {
    "remote-as",
    "update-source",
    "activate",
    "send-community",
    "route-map",
    "next-hop-self",
    "route-reflector-client",
}
_NEIGHBOR_LINE_RE = re.compile(r"^neighbor (\S+) (.+)$")

# Some neighbor options (e.g. 'fall-over bfd') are configured directly under
# 'router bgp <asn>' / 'vrf <name>', not inside an address-family block - see
# AOS-CX CLI reference. The 'general' scope in 'bgp_neighbor_options' targets
# that level, as opposed to 'ipv4'/'ipv6' which target the matching
# address-family block.
_NEIGHBOR_OPTION_GENERAL_SCOPE = "general"


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
            addr = ip_obj.get("address") if isinstance(
                ip_obj, dict) else str(ip_obj)
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
        af = "ipv6" if is_ipv6_address(local_addr) else "ipv4"

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
    # Values are dicts {"name": str, "af": "ipv4"|"ipv6"} so we can emit
    # the correct CLI keyword when configuring the prefix list itself.
    referenced_prefix_list_ids = {}  # {prefix_list_id: {"name": str, "af": str}}
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

        # match ip/ipv6 address prefix-list
        # netbox-bgp returns match_ip_address (IPv4) and match_ipv6_address (IPv6)
        # as ManyToMany lists; handle both list and single-object forms.
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
    # {prefix_list_name: {"af": str, "rules": [rule_dicts]}}
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

        # If the prefix list object itself carries an address_family field, prefer it.
        # The netbox-bgp plugin may return e.g. {"value": "ipv6", "label": "IPv6"}
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
            prefix_lists_map[pl_name] = {"af": pl_af, "rules": []}
        prefix_lists_map[pl_name]["rules"].append(
            {"index": index, "action": action, "prefix": str(network)}
        )

        _debug(
            f"prefix-list rule: {pl_name} ({pl_af}) seq {index} {action} {network}")

    # Sort rules within each prefix list by sequence number
    prefix_lists = [
        {
            "name": name,
            "af": data["af"],
            "rules": sorted(data["rules"], key=lambda r: r["index"]),
        }
        for name, data in prefix_lists_map.items()
    ]

    # Sort route-map rules by policy name, then sequence number
    route_map_rules.sort(key=lambda r: (r["name"], r["index"]))

    return {
        "prefix_lists": prefix_lists,
        "route_map_rules": route_map_rules,
    }


def get_bgp_redistribute_config(bgp_redistribute):
    """
    Flatten the 'bgp_redistribute' NetBox config_context into a list of
    per-VRF, per-address-family redistribution entries.

    Expected config_context shape::

        bgp_redistribute:
          default:                 # global 'router bgp' context (no VRF)
            ipv4: [connected, static]
            ipv6: [static]
          lab-blue:                 # must match an existing VRF name
            ipv4: [static]
            ipv6: [static]

    Unknown/invalid address families or protocols are skipped rather than
    raised, consistent with this role's tolerant handling of malformed
    config_context data elsewhere (e.g. static_route_filters).

    Args:
        bgp_redistribute: The 'bgp_redistribute' config_context dict, keyed
            by VRF name ('default' for the global BGP instance), each
            mapping an address family ('ipv4'/'ipv6') to a list of
            protocols to redistribute.

    Returns:
        List of dicts, one per (vrf, af, protocol) combination, sorted for
        deterministic ordering::

            [{"vrf": "default", "af": "ipv4", "protocol": "connected"},
             {"vrf": "lab-blue", "af": "ipv4", "protocol": "static"}]
    """
    result = []

    if not isinstance(bgp_redistribute, dict):
        return result

    for vrf_name, af_map in bgp_redistribute.items():
        if not isinstance(af_map, dict):
            continue

        for af, protocols in af_map.items():
            if af not in _VALID_BGP_ADDRESS_FAMILIES:
                _debug(
                    f"get_bgp_redistribute_config: skipping unknown address "
                    f"family '{af}' for VRF '{vrf_name}'"
                )
                continue
            if not isinstance(protocols, list):
                continue

            for protocol in protocols:
                if protocol not in _VALID_REDISTRIBUTE_PROTOCOLS:
                    _debug(
                        f"get_bgp_redistribute_config: skipping unsupported "
                        f"protocol '{protocol}' for VRF '{vrf_name}' ({af})"
                    )
                    continue

                result.append(
                    {"vrf": vrf_name, "af": af, "protocol": protocol})

    result.sort(key=lambda entry: (
        entry["vrf"], entry["af"], entry["protocol"]))
    return result


def _iter_bgp_lines(running_config, local_asn):
    """
    Walk 'show running-config' text and yield every line found under the
    'router bgp <local_asn>' instance, whether it sits directly under
    'router bgp' / 'vrf <name>' or inside an 'address-family (ipv4|ipv6)
    unicast' block.

    Tracks context ('vrf <name>' / 'exit-vrf', 'address-family ... unicast'
    / 'exit-address-family') structurally rather than by counting
    whitespace, so it tolerates minor indentation differences in the
    device's running-config output.

    Args:
        running_config: Full 'show running-config' text from the device.
        local_asn: The device's BGP ASN, used to scope parsing to the
            correct 'router bgp' block (a device can only run one).

    Yields:
        (vrf, af, line) tuples for each non-empty, non-structural line -
        'af' is None for lines directly under 'router bgp' / 'vrf <name>'
        (outside any address-family block), or 'ipv4'/'ipv6' for lines
        inside the matching 'address-family ... unicast' block. 'vrf' is
        'default' for the global BGP instance.
    """
    if not running_config:
        return

    router_bgp_re = re.compile(rf"^router bgp {re.escape(str(local_asn))}$")
    af_re = re.compile(r"^address-family (ipv4|ipv6) unicast$")

    in_bgp = False
    current_vrf = "default"
    current_af = None

    for raw_line in running_config.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # A new top-level (non-indented) statement ends the router bgp block.
        if not raw_line[0].isspace():
            in_bgp = bool(router_bgp_re.match(line))
            current_vrf = "default"
            current_af = None
            continue

        if not in_bgp:
            continue

        af_match = af_re.match(line)
        if line.startswith("vrf "):
            current_vrf = line[len("vrf "):].strip()
            current_af = None
            continue
        if line == "exit-vrf":
            current_vrf = "default"
            current_af = None
            continue
        if af_match:
            current_af = af_match.group(1)
            continue
        if line == "exit-address-family":
            current_af = None
            continue

        yield current_vrf, current_af, line


def _parse_bgp_redistribute_from_config(running_config, local_asn):
    """
    Parse 'redistribute <protocol>' statements out of 'show running-config'
    text, scoped to the 'router bgp <local_asn>' block. 'redistribute' is
    only valid inside an address-family block, so lines outside one are
    ignored.

    Args:
        running_config: Full 'show running-config' text from the device.
        local_asn: The device's BGP ASN, used to scope parsing to the
            correct 'router bgp' block (a device can only run one).

    Returns:
        List of {"vrf": str, "af": "ipv4"|"ipv6", "protocol": str} dicts -
        every redistribute statement currently configured under that BGP
        instance, regardless of whether this role manages it.
    """
    result = []
    for vrf, af, line in _iter_bgp_lines(running_config, local_asn):
        if af is not None and line.startswith("redistribute "):
            protocol = line[len("redistribute "):].strip()
            result.append({"vrf": vrf, "af": af, "protocol": protocol})
    return result


def get_stale_bgp_redistribute(bgp_redistribute, running_config, local_asn):
    """
    Compute BGP redistribute entries present on the device but no longer
    present in the 'bgp_redistribute' NetBox config_context.

    'aoscx_config' (used to push desired redistribute entries, see
    get_bgp_redistribute_config) only ever adds missing lines - it never
    removes ones that were deleted from config_context. This diffs the
    actual running-config against the desired state to find explicit
    'no redistribute' candidates, for use in idempotent cleanup.

    Args:
        bgp_redistribute: The 'bgp_redistribute' config_context dict (see
            get_bgp_redistribute_config for the expected shape).
        running_config: Full 'show running-config' text from the device.
        local_asn: The device's BGP ASN (device_bgp_sessions[0].local_as.asn).

    Returns:
        List of {"vrf": str, "af": str, "protocol": str} dicts to remove.
    """
    desired = get_bgp_redistribute_config(bgp_redistribute)
    desired_keys = {(d["vrf"], d["af"], d["protocol"]) for d in desired}

    current = _parse_bgp_redistribute_from_config(running_config, local_asn)

    stale = [
        entry
        for entry in current
        if (entry["vrf"], entry["af"], entry["protocol"]) not in desired_keys
    ]

    if stale:
        _debug(
            f"get_stale_bgp_redistribute: {len(stale)} stale entrie(s) found")

    return stale


def get_bgp_neighbor_options_config(bgp_neighbor_options, sessions):
    """
    Flatten the 'bgp_neighbor_options' NetBox config_context into a list of
    per-VRF, per-scope, per-neighbor CLI option entries.

    The netbox-bgp plugin's session model does not cover generic per-neighbor
    options, so this supports adding arbitrary ones via config_context
    without extending the plugin. Each neighbor IP is matched against live
    session data (enriched with '_vrf' / '_af' by get_bgp_session_vrf_info)
    to determine which VRF(s) it is actually configured under - unmatched
    neighbor IPs are skipped rather than blindly pushed.

    Two scopes are supported per neighbor:
      - 'ipv4' / 'ipv6': options configured inside the matching
        'address-family ... unicast' block (e.g. 'soft-reconfiguration
        inbound'). Resolved against sessions matching that address family.
      - 'general': options configured directly under 'router bgp' / 'vrf
        <name>', outside any address-family block (e.g. 'fall-over bfd').
        Resolved against all VRFs the neighbor IP is peered under,
        regardless of address family.

    Lines starting with a keyword already managed by other tasks in
    tasks/configure_bgp.yml (e.g. 'remote-as', 'route-map', 'activate') are
    also skipped, so this feature cannot fight those tasks.

    Expected config_context shape::

        bgp_neighbor_options:
          172.27.250.32:                 # neighbor IP, no CIDR
            general:
              - "fall-over bfd"
            ipv4:
              - "soft-reconfiguration inbound"
          2001:db8::1:
            ipv6:
              - "soft-reconfiguration inbound"

    Args:
        bgp_neighbor_options: The 'bgp_neighbor_options' config_context
            dict, keyed by neighbor IP, each mapping a scope
            ('ipv4'/'ipv6'/'general') to a list of CLI option strings
            (everything after 'neighbor <ip> ').
        sessions: List of BGP session objects, already enriched with
            '_vrf' / '_af' by get_bgp_session_vrf_info.

    Returns:
        List of dicts, one per (vrf, af, neighbor_ip, command) combination,
        sorted for deterministic ordering. 'af' is None for 'general'-scope
        entries::

            [{"vrf": "default", "af": None, "neighbor_ip": "172.27.250.32",
              "command": "fall-over bfd"},
             {"vrf": "default", "af": "ipv4", "neighbor_ip": "172.27.250.32",
              "command": "soft-reconfiguration inbound"}]
    """
    result = []

    if not isinstance(bgp_neighbor_options, dict):
        return result

    # Build a lookup: neighbor IP -> set of (vrf, af) contexts it is
    # actually configured under, from live session data.
    ip_to_contexts = {}
    for session in sessions or []:
        if not isinstance(session, dict):
            continue
        remote_addr_obj = session.get("remote_address") or {}
        remote_addr = (
            remote_addr_obj.get("address", "")
            if isinstance(remote_addr_obj, dict)
            else ""
        )
        neighbor_ip = remote_addr.split("/")[0] if remote_addr else ""
        if not neighbor_ip:
            continue
        vrf = session.get("_vrf", "default")
        af = session.get("_af")
        ip_to_contexts.setdefault(neighbor_ip, set()).add((vrf, af))

    for neighbor_ip, scope_map in bgp_neighbor_options.items():
        if not isinstance(scope_map, dict):
            continue

        contexts = ip_to_contexts.get(neighbor_ip)
        if not contexts:
            _debug(
                f"get_bgp_neighbor_options_config: skipping neighbor "
                f"'{neighbor_ip}' - no matching BGP session found"
            )
            continue

        for scope, commands in scope_map.items():
            if scope == _NEIGHBOR_OPTION_GENERAL_SCOPE:
                af = None
                vrfs = {vrf for vrf, _af in contexts}
            elif scope in _VALID_BGP_ADDRESS_FAMILIES:
                af = scope
                vrfs = {vrf for vrf, session_af in contexts if session_af == af}
            else:
                _debug(
                    f"get_bgp_neighbor_options_config: skipping unknown "
                    f"scope '{scope}' for neighbor '{neighbor_ip}'"
                )
                continue

            if not isinstance(commands, list):
                continue

            if not vrfs:
                _debug(
                    f"get_bgp_neighbor_options_config: skipping neighbor "
                    f"'{neighbor_ip}' - no session found for scope '{scope}'"
                )
                continue

            for command in commands:
                if not command:
                    continue
                keyword = command.split(" ", 1)[0]
                if keyword in _RESERVED_NEIGHBOR_KEYWORDS:
                    _debug(
                        f"get_bgp_neighbor_options_config: skipping reserved "
                        f"keyword '{keyword}' for neighbor '{neighbor_ip}' - "
                        "already managed by tasks/configure_bgp.yml"
                    )
                    continue
                for vrf in vrfs:
                    result.append(
                        {
                            "vrf": vrf,
                            "af": af,
                            "neighbor_ip": neighbor_ip,
                            "command": command,
                        }
                    )

    result.sort(
        key=lambda entry: (
            entry["vrf"],
            entry["af"] or "",
            entry["neighbor_ip"],
            entry["command"],
        )
    )
    return result


def _parse_bgp_neighbor_options_from_config(running_config, local_asn):
    """
    Parse 'neighbor <ip> <options>' statements out of 'show running-config'
    text, scoped to the 'router bgp <local_asn>' block.

    Lines whose first keyword is in _RESERVED_NEIGHBOR_KEYWORDS are skipped,
    since those are already managed by other tasks in
    tasks/configure_bgp.yml and must never be treated as candidates for
    removal by this feature's cleanup.

    Args:
        running_config: Full 'show running-config' text from the device.
        local_asn: The device's BGP ASN, used to scope parsing to the
            correct 'router bgp' block (a device can only run one).

    Returns:
        List of {"vrf": str, "af": "ipv4"|"ipv6"|None, "neighbor_ip": str,
        "command": str} dicts - every non-reserved per-neighbor option
        currently configured under that BGP instance. 'af' is None for
        options configured outside any address-family block.
    """
    result = []
    for vrf, af, line in _iter_bgp_lines(running_config, local_asn):
        match = _NEIGHBOR_LINE_RE.match(line)
        if not match:
            continue

        neighbor_ip, rest = match.group(1), match.group(2)
        keyword = rest.split(" ", 1)[0]
        if keyword in _RESERVED_NEIGHBOR_KEYWORDS:
            continue

        result.append(
            {"vrf": vrf, "af": af, "neighbor_ip": neighbor_ip, "command": rest}
        )

    return result


def get_stale_bgp_neighbor_options(
    bgp_neighbor_options, sessions, running_config, local_asn
):
    """
    Compute BGP neighbor options (address-family-scoped or 'general') present
    on the device but no longer present in the 'bgp_neighbor_options' NetBox
    config_context.

    Mirrors get_stale_bgp_redistribute: 'aoscx_config' only ever adds
    missing lines, so this diffs the actual running-config against the
    desired state to find explicit 'no neighbor <ip> <options>' candidates
    for idempotent cleanup. Lines matching a reserved keyword (see
    _RESERVED_NEIGHBOR_KEYWORDS) are excluded by
    _parse_bgp_neighbor_options_from_config before the diff even runs, so
    this can never suggest removing a line owned by another task.

    Args:
        bgp_neighbor_options: The 'bgp_neighbor_options' config_context
            dict (see get_bgp_neighbor_options_config for the expected
            shape).
        sessions: List of BGP session objects, enriched with '_vrf' /
            '_af' by get_bgp_session_vrf_info.
        running_config: Full 'show running-config' text from the device.
        local_asn: The device's BGP ASN (device_bgp_sessions[0].local_as.asn).

    Returns:
        List of {"vrf": str, "af": str|None, "neighbor_ip": str,
        "command": str} dicts to remove. 'af' is None for 'general'-scope
        (non-address-family) entries.
    """
    desired = get_bgp_neighbor_options_config(bgp_neighbor_options, sessions)
    desired_keys = {
        (d["vrf"], d["af"], d["neighbor_ip"], d["command"]) for d in desired
    }

    current = _parse_bgp_neighbor_options_from_config(
        running_config, local_asn)

    stale = [
        entry
        for entry in current
        if (entry["vrf"], entry["af"], entry["neighbor_ip"], entry["command"])
        not in desired_keys
    ]

    if stale:
        _debug(
            f"get_stale_bgp_neighbor_options: {len(stale)} stale entrie(s) found")

    return stale


def get_bgp_bfd_enabled(bgp_neighbor_options, sessions):
    """
    AOS-CX's 'bfd' command is global - configured as a single top-level
    line (alongside things like 'clock timezone' and 'no ip icmp
    redirect'), not nested under 'router bgp'/'vrf' and not per-VRF. It
    must be enabled before 'neighbor <ip> fall-over bfd' has any effect;
    the per-neighbor option alone does not turn BFD on. Rather than
    requiring a second, easy-to-forget config_context entry that could
    drift out of sync with the neighbor options, this derives whether
    'bfd' is needed directly from any neighbor declaring 'fall-over bfd'
    in the 'general' scope of 'bgp_neighbor_options'.

    NOTE: 'bfd' is a switch-wide toggle also usable by OSPF/static routes.
    If those features start managing it too, this and
    get_stale_bgp_bfd() must be combined with their equivalent checks
    before deciding to push 'no bfd', so cleanup here doesn't disable BFD
    for a feature it doesn't know about.

    Args:
        bgp_neighbor_options: The 'bgp_neighbor_options' config_context
            dict (see get_bgp_neighbor_options_config for the expected
            shape).
        sessions: List of BGP session objects, enriched with '_vrf' /
            '_af' by get_bgp_session_vrf_info.

    Returns:
        True if any neighbor declares 'fall-over bfd', meaning the global
        'bfd' line must be present.
    """
    entries = get_bgp_neighbor_options_config(bgp_neighbor_options, sessions)
    return any(
        entry["af"] is None and entry["command"] == "fall-over bfd"
        for entry in entries
    )


def _is_global_bfd_enabled(running_config):
    """
    Check whether the global 'bfd' line is present in 'show running-config'
    text, outside any nested context (VLAN, VRF, router bgp, etc.) - AOS-CX
    configures it as a top-level, unindented command.
    """
    if not running_config:
        return False
    for raw_line in running_config.splitlines():
        if raw_line.strip() == "bfd" and not raw_line[:1].isspace():
            return True
    return False


def get_stale_bgp_bfd(bgp_neighbor_options, sessions, running_config):
    """
    Determine whether the global 'bfd' line is currently configured on the
    device but no BGP neighbor declares 'fall-over bfd' anymore, so 'bfd'
    should be disabled (see the NOTE on get_bgp_bfd_enabled about other
    features sharing this same global toggle).

    Args:
        bgp_neighbor_options: The 'bgp_neighbor_options' config_context dict.
        sessions: List of BGP session objects, enriched with '_vrf' / '_af'
            by get_bgp_session_vrf_info.
        running_config: Full 'show running-config' text from the device.

    Returns:
        True if 'no bfd' should be pushed.
    """
    if not _is_global_bfd_enabled(running_config):
        return False

    stale = not get_bgp_bfd_enabled(bgp_neighbor_options, sessions)
    if stale:
        _debug("get_stale_bgp_bfd: global 'bfd' is stale, no longer needed by BGP")

    return stale
