"""Idempotent OCI network bootstrap: VCN, internet gateway, subnet.

Everything here is safe to call repeatedly — existing resources are
looked up by display name first and reused, which is what makes container
restarts cheap.
"""

from oci.core.models import (
    CreateInternetGatewayDetails,
    CreateSubnetDetails,
    CreateVcnDetails,
    EgressSecurityRule,
    IcmpOptions,
    IngressSecurityRule,
    PortRange,
    RouteRule,
    TcpOptions,
    UpdateRouteTableDetails,
    UpdateSecurityListDetails,
)

from .logging import log
from .state import load_state, save_state

# Defaults for the network names/CIDRs; the actual values come from cfg
# (overridable via VCN_NAME / SUBNET_NAME / IG_NAME / VCN_CIDR /
# SUBNET_CIDR in .env).
DEFAULTS = {
    "vcn_name": "free-tier-hunter-vcn",
    "subnet_name": "free-tier-hunter-subnet",
    "ig_name": "free-tier-hunter-ig",
    "vcn_cidr": "10.0.0.0/16",
    "subnet_cidr": "10.0.0.0/24",
}


def first_available(items):
    return next(
        (i for i in items if i.lifecycle_state not in ("TERMINATED", "TERMINATING")),
        None,
    )


def ensure_network(vnet, cfg):
    """Idempotently make sure a VCN / IG / subnet suitable for a public
    instance with SSH open exists, and return the subnet OCID."""
    tenancy = cfg["tenancy"]
    names = {
        k: cfg.get(k) or DEFAULTS[k]
        for k in ("vcn_name", "subnet_name", "ig_name", "vcn_cidr", "subnet_cidr")
    }
    vcn = first_available(vnet.list_vcns(tenancy, display_name=names["vcn_name"]).data)
    if vcn is None:
        vcn = vnet.create_vcn(
            CreateVcnDetails(
                compartment_id=tenancy,
                display_name=names["vcn_name"],
                cidr_blocks=[names["vcn_cidr"]],
            )
        ).data
        log(f"created VCN {vcn.id}")
    else:
        log(f"using VCN {vcn.id}")

    ig = first_available(
        vnet.list_internet_gateways(
            tenancy, vcn_id=vcn.id, display_name=names["ig_name"]
        ).data
    )
    if ig is None:
        ig = vnet.create_internet_gateway(
            CreateInternetGatewayDetails(
                compartment_id=tenancy,
                vcn_id=vcn.id,
                display_name=names["ig_name"],
                is_enabled=True,
            )
        ).data
        log(f"created internet gateway {ig.id}")
    else:
        log(f"using internet gateway {ig.id}")

    vnet.update_route_table(
        vcn.default_route_table_id,
        UpdateRouteTableDetails(
            route_rules=[
                RouteRule(
                    destination="0.0.0.0/0",
                    destination_type="CIDR_BLOCK",
                    network_entity_id=ig.id,
                )
            ]
        ),
    )

    sl_id = vcn.default_security_list_id
    vnet.update_security_list(
        sl_id,
        UpdateSecurityListDetails(
            ingress_security_rules=[
                IngressSecurityRule(
                    protocol="6",
                    source="0.0.0.0/0",
                    source_type="CIDR_BLOCK",
                    tcp_options=TcpOptions(
                        destination_port_range=PortRange(min=22, max=22)
                    ),
                ),
                IngressSecurityRule(
                    protocol="1",
                    source="0.0.0.0/0",
                    source_type="CIDR_BLOCK",
                    icmp_options=IcmpOptions(type=3, code=4),
                ),
                IngressSecurityRule(
                    protocol="1",
                    source=names["vcn_cidr"],
                    source_type="CIDR_BLOCK",
                    icmp_options=IcmpOptions(type=3, code=4),
                ),
                IngressSecurityRule(
                    protocol="all", source=names["vcn_cidr"], source_type="CIDR_BLOCK"
                ),
            ],
            egress_security_rules=[
                EgressSecurityRule(
                    protocol="all",
                    destination="0.0.0.0/0",
                    destination_type="CIDR_BLOCK",
                ),
            ],
        ),
    )

    subnet = first_available(
        vnet.list_subnets(
            tenancy, vcn_id=vcn.id, display_name=names["subnet_name"]
        ).data
    )
    if subnet is None:
        subnet = vnet.create_subnet(
            CreateSubnetDetails(
                compartment_id=tenancy,
                vcn_id=vcn.id,
                display_name=names["subnet_name"],
                cidr_block=names["subnet_cidr"],
                route_table_id=vcn.default_route_table_id,
                security_list_ids=[sl_id],
                prohibit_public_ip_on_vnic=False,
            )
        ).data
        log(f"created subnet {subnet.id}")
    else:
        log(f"using subnet {subnet.id}")

    state = load_state()
    state.update(
        {
            "vcn": vcn.id,
            "internet_gateway": ig.id,
            "route_table": vcn.default_route_table_id,
            "security_list": sl_id,
            "subnet": subnet.id,
        }
    )
    save_state(state)
    return subnet.id
