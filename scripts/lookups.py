"""Lookup functions for cross-link relationships between resources.

Each function takes (data, item) and returns a list of related items
from another resource type. Referenced by name in resource YAML files.
"""


def route_table_for_subnet(data, subnet):
    """Find the route table associated with a subnet."""
    subnet_id = subnet["SubnetId"]
    for rt in data.get("route_tables", []):
        for assoc in rt.get("Associations", []):
            if assoc.get("SubnetId") == subnet_id:
                return [rt]
    # Fall back to main route table
    for rt in data.get("route_tables", []):
        if rt["VpcId"] == subnet["VpcId"]:
            for assoc in rt.get("Associations", []):
                if assoc.get("Main"):
                    return [rt]
    return []


def nacl_for_subnet(data, subnet):
    """Find the network ACL associated with a subnet."""
    subnet_id = subnet["SubnetId"]
    for nacl in data.get("network_acls", []):
        for assoc in nacl.get("Associations", []):
            if assoc.get("SubnetId") == subnet_id:
                return [nacl]
    return []


def security_groups_for_subnet(data, subnet):
    """Find security groups used by instances in a subnet."""
    subnet_id = subnet["SubnetId"]
    sgs = {}
    for r in data.get("instances", []):
        for i in r.get("Instances", []) if isinstance(r, dict) else []:
            if i.get("SubnetId") == subnet_id:
                for sg in i.get("SecurityGroups", []):
                    sgs[sg["GroupId"]] = sg
    # Also check security_groups data directly for this VPC
    if not sgs:
        for sg in data.get("security_groups", []):
            if sg.get("VpcId") == subnet.get("VpcId"):
                sgs[sg["GroupId"]] = sg
    return list(sgs.values())


def subnets_for_route_table(data, rt):
    """Find subnets associated with a route table."""
    result = []
    for assoc in rt.get("Associations", []):
        subnet_id = assoc.get("SubnetId")
        if subnet_id:
            for s in data.get("subnets", []):
                if s["SubnetId"] == subnet_id:
                    result.append(s)
    return result


def subnets_for_nacl(data, nacl):
    """Find subnets associated with a network ACL."""
    result = []
    for assoc in nacl.get("Associations", []):
        subnet_id = assoc.get("SubnetId")
        if subnet_id:
            for s in data.get("subnets", []):
                if s["SubnetId"] == subnet_id:
                    result.append(s)
    return result


def subnets_for_eks(data, cluster):
    """Find subnets associated with an EKS cluster."""
    subnet_ids = cluster.get("subnetIds", [])
    return [s for s in data.get("subnets", []) if s["SubnetId"] in subnet_ids]


def security_groups_for_eks(data, cluster):
    """Find security groups associated with an EKS cluster."""
    sg_ids = set(cluster.get("securityGroupIds", []))
    cluster_sg = cluster.get("clusterSecurityGroupId")
    if cluster_sg:
        sg_ids.add(cluster_sg)
    return [sg for sg in data.get("security_groups", []) if sg["GroupId"] in sg_ids]


LOOKUPS = {
    "route_table_for_subnet": route_table_for_subnet,
    "nacl_for_subnet": nacl_for_subnet,
    "security_groups_for_subnet": security_groups_for_subnet,
    "subnets_for_route_table": subnets_for_route_table,
    "subnets_for_nacl": subnets_for_nacl,
    "subnets_for_eks": subnets_for_eks,
    "security_groups_for_eks": security_groups_for_eks,
}
