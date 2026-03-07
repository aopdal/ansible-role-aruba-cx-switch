# BGP Hybrid Configuration

> **Deprecated:** The config_context fallback for BGP has been removed. BGP configuration now exclusively uses the [NetBox BGP plugin](NETBOX_BGP_PLUGIN.md).

If you were previously relying on `bgp_as`, `bgp_peers`, `bgp_ipv4_peers`, `bgp_vrfs`, `bgp_rr_clients`, or `bgp_additional_config` from `config_context`, migrate your BGP sessions to the NetBox BGP plugin.

See [BGP_CONFIGURATION.md](BGP_CONFIGURATION.md) for current usage.
