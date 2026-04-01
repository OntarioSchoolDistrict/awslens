#!/usr/bin/env python3
"""Generic D2 diagram generator driven by config.yaml and resource YAML files."""

import argparse
import glob
import json
import os
import shutil
import sys
from datetime import datetime

import boto3
import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
DIAGRAMS_DIR = os.path.join(REPO_ROOT, "diagrams")
RESOURCES_DIR = os.path.join(SCRIPT_DIR, "resources")
CACHE_DIR = os.path.join(REPO_ROOT, ".cache")

CONFIG_PATH = os.path.join(REPO_ROOT, "config.yaml")

# Icon paths
ICON_BASE = "aws-icon-package"
ICON_SVC = f"{ICON_BASE}/Architecture-Service-Icons_01302026"
ICON_RES = f"{ICON_BASE}/Resource-Icons_01302026/Res_Networking-Content-Delivery"
ICONS = {
    "aws": f"{ICON_BASE}/Architecture-Group-Icons_01302026/AWS-Cloud_32.svg",
    "vpc": f"{ICON_SVC}/Arch_Networking-Content-Delivery/64/Arch_Amazon-Virtual-Private-Cloud_64.svg",
    "subnet": f"{ICON_RES}/Res_Amazon-VPC_Virtual-private-cloud-VPC_48.svg",
    "igw": f"{ICON_RES}/Res_Amazon-VPC_Internet-Gateway_48.svg",
    "route_table": f"{ICON_RES}/Res_Amazon-Route-53_Route-Table_48.svg",
    "nacl": f"{ICON_RES}/Res_Amazon-VPC_Network-Access-Control-List_48.svg",
    "security_group": f"{ICON_SVC}/Arch_Security-Identity/64/Arch_AWS-Network-Firewall_64.svg",
    "nat_gateway": f"{ICON_RES}/Res_Amazon-VPC_NAT-Gateway_48.svg",
    "ec2": f"{ICON_SVC}/Arch_Compute/64/Arch_Amazon-EC2_64.svg",
    "elb": f"{ICON_SVC}/Arch_Networking-Content-Delivery/64/Arch_Elastic-Load-Balancing_64.svg",
    "rds": f"{ICON_SVC}/Arch_Databases/64/Arch_Amazon-RDS_64.svg",
    "lambda": f"{ICON_SVC}/Arch_Compute/64/Arch_AWS-Lambda_64.svg",
    "s3": f"{ICON_SVC}/Arch_Storage/64/Arch_Amazon-Simple-Storage-Service_64.svg",
    "cloudfront": f"{ICON_SVC}/Arch_Networking-Content-Delivery/64/Arch_Amazon-CloudFront_64.svg",
    "sns": f"{ICON_SVC}/Arch_Application-Integration/64/Arch_Amazon-Simple-Notification-Service_64.svg",
    "sqs": f"{ICON_SVC}/Arch_Application-Integration/64/Arch_Amazon-Simple-Queue-Service_64.svg",
    "eks": f"{ICON_SVC}/Arch_Containers/64/Arch_Amazon-Elastic-Kubernetes-Service_64.svg",
    "vpc_peering": f"{ICON_RES}/Res_Amazon-VPC_Peering-Connection_48.svg",
    "vpn": f"{ICON_RES}/Res_Amazon-VPC_VPN-Connection_48.svg",
    "route53": f"{ICON_SVC}/Arch_Networking-Content-Delivery/64/Arch_Amazon-Route-53_64.svg",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def load_resource_defs(config):
    """Load resource YAML files for resources listed in config."""
    enabled = config.get("resources", [])
    defs = {}
    for yaml_file in glob.glob(os.path.join(RESOURCES_DIR, "*.yaml")):
        if os.path.basename(yaml_file) == "resource.yaml.example":
            continue
        with open(yaml_file) as f:
            rdef = yaml.safe_load(f)
        if rdef["key"] in enabled:
            defs[rdef["key"]] = rdef
    return defs


def get_name(tags):
    for t in (tags or []):
        if t["Key"] == "Name":
            return t["Value"]
    return None


def safe_id(s):
    return str(s).replace("-", "_").replace(".", "_").replace("/", "_").replace(":", "_")


def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    print(f"  wrote {os.path.relpath(path, REPO_ROOT)}")


def get_scope(rdef):
    """Return the filter scope for a resource definition."""
    return rdef.get("filter", {}).get("scope", "vpc")


def resolve_link(resource_defs, from_key, to_key, to_id):
    """Compute relative HTML link between two resource pages."""
    from_path = resource_defs[from_key]["links"]["html_path"]
    to_path = resource_defs[to_key]["links"]["html_path"].format(id=safe_id(to_id))
    from_depth = from_path.count("/")
    prefix = "../" * from_depth
    return f"{prefix}{to_path}"


def resolve_grid_link(resource_defs, from_key, to_key):
    """Compute relative HTML link from a detail page to a grid page."""
    from_path = resource_defs[from_key]["links"]["html_path"]
    to_path = resource_defs[to_key]["links"]["html_path"]
    from_depth = from_path.count("/")
    prefix = "../" * from_depth
    if "/" in to_path:
        grid_dir = to_path.split("/")[0]
        return f"{prefix}{grid_dir}/index.html"
    return f"{prefix}{to_path}"


def back_link(rdef):
    depth = rdef["links"]["html_path"].count("/")
    return "../index.html" if depth > 0 else "./index.html"


def detail_back_link():
    return "./index.html"


def get_layout(config, key=None):
    defaults = config.get("layout_defaults", {})
    result = {}
    for k in ["grid_columns", "grid_gap", "tile_width", "tile_height", "tile_font_size"]:
        result[k] = defaults.get(k)
    return result


def apply_grid(w, config):
    layout = get_layout(config)
    cols = layout.get("grid_columns")
    gap = layout.get("grid_gap")
    if cols:
        w(f"  grid-columns: {cols}")
    if gap:
        w(f"  grid-gap: {gap}")


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

# Services that require us-east-1 regardless of configured region
GLOBAL_SERVICES = {"s3", "cloudfront", "route53"}


def fetch_all(resource_defs, region):
    """Fetch AWS data for all resource types."""
    clients = {}
    data = {}

    for key, rdef in resource_defs.items():
        fetch = rdef["fetch"]
        service = fetch["service"]
        client_key = f"{service}:{region}"
        if service in GLOBAL_SERVICES:
            client_key = f"{service}:us-east-1"
        if client_key not in clients:
            client_region = "us-east-1" if service in GLOBAL_SERVICES else region
            clients[client_key] = boto3.client(service, region_name=client_region)
        client = clients[client_key]

        method = getattr(client, fetch["method"])
        result = method()
        # Handle nested result_key like DistributionList.Items
        items = result
        for part in fetch["result_key"].split("."):
            items = items.get(part) if isinstance(items, dict) else items
        items = items or []

        # Flatten nested lists (e.g. Reservations[].Instances[])
        flatten = fetch.get("flatten")
        if flatten and items:
            list_field, sub_field = flatten.split("[].")
            flat = []
            for outer in items:
                flat.extend(outer.get(sub_field, []))
            items = flat

        # Convert string lists to dicts (e.g. SQS QueueUrls, EKS cluster names)
        wrap_as = fetch.get("wrap_as")
        if wrap_as and items and isinstance(items[0], str):
            items = [{wrap_as: s} for s in items]

        # Run enricher plugin if specified
        enrich_name = fetch.get("enrich")
        if enrich_name:
            from enrichment import run_enricher
            items = run_enricher(enrich_name, items, region)

        data[key] = items

    # Also fetch VPCs (always needed)
    ec2_key = f"ec2:{region}"
    if ec2_key not in clients:
        clients[ec2_key] = boto3.client("ec2", region_name=region)
    data["vpcs"] = clients[ec2_key].describe_vpcs()["Vpcs"]

    return data


def resolve_field(item, field):
    """Resolve a dotted field path like 'DBSubnetGroup.VpcId' on an item."""
    for part in field.split("."):
        if item is None:
            return None
        item = item.get(part) if isinstance(item, dict) else None
    return item


def filter_for_vpc(rdef, items, vpc_id):
    """Filter items for a specific VPC using the resource definition."""
    filt = rdef.get("filter", {})
    field = filt.get("field", "")

    if not field:
        return items

    # Handle array bracket syntax like Attachments[].VpcId
    if "[]." in field:
        list_field, sub_field = field.split("[].", 1)
        return [item for item in items
                if any(resolve_field(a, sub_field) == vpc_id
                       for a in item.get(list_field, []))]

    # Handle dotted paths like DBSubnetGroup.VpcId
    return [item for item in items if resolve_field(item, field) == vpc_id]


def get_item_id(rdef, item):
    return item[rdef["id_field"]]


def get_item_name(rdef, item):
    name = get_name(item.get("Tags"))
    if not name and rdef.get("name_field"):
        name = item.get(rdef["name_field"])
    return name or get_item_id(rdef, item)


# ---------------------------------------------------------------------------
# D2 generation
# ---------------------------------------------------------------------------

def format_tile_label(rdef, item):
    """Format a grid tile label from the template."""
    template = rdef.get("grid", {}).get("tile_label", "{Name}")
    name = get_item_name(rdef, item)

    # Build substitution dict
    subs = {"Name": name}
    subs[rdef["id_field"]] = get_item_id(rdef, item)

    # Add all top-level string/number fields
    for k, v in item.items():
        if isinstance(v, (str, int, float, bool)):
            subs[k] = str(v)

    # Computed fields
    subs["main_or_custom"] = "Main" if any(
        a.get("Main") for a in item.get("Associations", [])
    ) else "Custom"
    subs["default_or_custom"] = "Default" if item.get("IsDefault") else "Custom"
    subs["route_count"] = str(len(item.get("Routes", [])))
    subs["subnet_count"] = str(len([a for a in item.get("Associations", []) if a.get("SubnetId")]))
    subs["inbound_count"] = str(len(item.get("IpPermissions", [])))
    subs["outbound_count"] = str(len(item.get("IpPermissionsEgress", [])))

    # Escape quotes in all values
    for k, v in subs.items():
        subs[k] = v.replace('"', "'")

    # Substitute
    for k, v in subs.items():
        template = template.replace(f"{{{k}}}", v)

    # Ensure newlines in template are D2 escaped
    template = template.replace("\n", "\\n")

    return template


def format_rule(perm):
    """Format a security group or NACL rule."""
    # NACL entry format
    if "RuleNumber" in perm:
        rule_num = perm.get("RuleNumber", "")
        if rule_num == 32767:
            rule_num = "*"
        protocol = perm.get("Protocol", "")
        if protocol == "-1":
            protocol = "All"
        elif protocol == "6":
            protocol = "TCP"
        elif protocol == "17":
            protocol = "UDP"
        cidr = perm.get("CidrBlock") or perm.get("Ipv6CidrBlock", "")
        action = perm.get("RuleAction", "")
        port_range = perm.get("PortRange")
        if port_range:
            fr, to = port_range.get("From", ""), port_range.get("To", "")
            ports = str(fr) if fr == to else f"{fr}-{to}"
        else:
            ports = "All"
        return f"{rule_num}: {protocol} {ports} {cidr} {action}"

    # Security group permission format
    protocol = perm.get("IpProtocol", "")
    if protocol == "-1":
        protocol = "All"
    from_port = perm.get("FromPort", "")
    to_port = perm.get("ToPort", "")
    if from_port == -1 or protocol == "All":
        ports = "All"
    elif from_port == to_port:
        ports = str(from_port)
    else:
        ports = f"{from_port}-{to_port}"
    sources = []
    for r in perm.get("IpRanges", []):
        sources.append(r.get("CidrIp", ""))
    for r in perm.get("Ipv6Ranges", []):
        sources.append(r.get("CidrIpv6", ""))
    for g in perm.get("UserIdGroupPairs", []):
        sources.append(g.get("GroupId", ""))
    source_text = ", ".join(sources) if sources else "N/A"
    return f"{protocol} {ports} {source_text}"


def format_route(route):
    """Format a route table route."""
    dest = route.get("DestinationCidrBlock") or route.get("DestinationIpv6CidrBlock", "")
    target = (route.get("GatewayId") or route.get("NatGatewayId")
              or route.get("VpcPeeringConnectionId") or route.get("NetworkInterfaceId")
              or route.get("TransitGatewayId") or "local")
    state = route.get("State", "")
    return f"{dest} → {target} ({state})"


def generate_grid(config, resource_defs, rdef, items):
    """Generate a grid or leaf D2 page."""
    key = rdef["key"]
    lines = []
    w = lines.append

    w(f"{key}_container: \"{rdef['label']}\" {{")
    w("  style.font-size: 24")
    w(f"  link: {back_link(rdef)}")
    w("  style.font-color: '#000000'")
    apply_grid(w, config)

    group_by = rdef.get("grid", {}).get("group_by")
    icon_key = rdef.get("grid", {}).get("tile_icon", rdef["icon"])

    if group_by:
        groups = {}
        for item in items:
            gval = item.get(group_by, "unknown")
            groups.setdefault(gval, []).append(item)
        for gval in sorted(groups):
            gid = safe_id(gval)
            w(f"  {gid}: \"{gval}\" {{")
            for item in groups[gval]:
                iid = safe_id(get_item_id(rdef, item))
                label = format_tile_label(rdef, item)
                w(f"    {iid}: \"{label}\" {{")
                w(f"      icon: {ICONS[icon_key]}")
                if rdef["type"] == "drilldown":
                    w(f"      link: layers.{iid}")
                w("    }")
            w("  }")
    else:
        for item in items:
            iid = safe_id(get_item_id(rdef, item))
            label = format_tile_label(rdef, item)
            w(f"  {iid}: \"{label}\" {{")
            w(f"    icon: {ICONS[icon_key]}")
            if rdef["type"] == "drilldown":
                w(f"    link: layers.{iid}")
            w("  }")

    w("}")

    if rdef["type"] == "drilldown":
        w("")
        w("layers: {")
        for item in items:
            raw_id = get_item_id(rdef, item)
            iid = safe_id(raw_id)
            d2_file = rdef["links"]["d2_detail"].format(raw_id=raw_id)
            w(f"  {iid}: @{d2_file}")
        w("}")

    return "\n".join(lines)


def _escape(s):
    """Escape a string for use in D2 double-quoted labels."""
    return str(s).replace('"', "'").replace("\n", "\\n")


def _render_section(w, config, resource_defs, rdef, item, data, section, indent="  "):
    """Render a single detail section. Returns True if content was written."""
    from lookups import LOOKUPS

    skey = section["key"]
    slabel = section["label"]
    stype = section.get("type", "fields")
    sicon = section.get("icon")

    if stype == "fields":
        field_values = []
        for f in section.get("fields", []):
            val = item.get(f)
            if val is None:
                if f == "main_or_custom":
                    val = "Main" if any(a.get("Main") for a in item.get("Associations", [])) else "Custom"
                elif f == "default_or_custom":
                    val = "Default" if item.get("IsDefault") else "Custom"
                else:
                    val = ""
            field_values.append(_escape(val))
        text = "\\n".join(field_values)
        w(f"{indent}{skey}: \"{slabel}\\n{text}\" {{")
        if sicon:
            w(f"{indent}  icon: {ICONS[sicon]}")
        w(f"{indent}}}")
        return True

    elif stype == "cross_link":
        lookup_fn = LOOKUPS.get(section.get("lookup"))
        if lookup_fn:
            related = lookup_fn(data, item)
            if related:
                rel = related[0]
                target_rdef = resource_defs[section["target"]]
                rel_id = get_item_id(target_rdef, rel)
                rel_name = _escape(get_item_name(target_rdef, rel))
                link = resolve_link(resource_defs, rdef["key"], section["target"], rel_id)
                w(f"{indent}{skey}: \"{slabel}\\n{rel_name}\" {{")
                if sicon:
                    w(f"{indent}  icon: {ICONS[sicon]}")
                w(f"{indent}  link: {link}")
                w(f"{indent}}}")
                return True

    elif stype == "cross_link_list":
        lookup_fn = LOOKUPS.get(section.get("lookup"))
        if lookup_fn:
            related = lookup_fn(data, item)
            if related:
                sub = section.get("sub_container")
                w(f"{indent}{skey}: \"{slabel} ({len(related)})\" {{")
                layout = get_layout(config)
                cols = layout.get("grid_columns")
                gap = layout.get("grid_gap")
                if cols:
                    w(f"{indent}  grid-columns: {cols}")
                if gap:
                    w(f"{indent}  grid-gap: {gap}")
                if sub:
                    grid_link = resolve_grid_link(resource_defs, rdef["key"], section["target"])
                    w(f"{indent}  link: {grid_link}")
                    w(f"{indent}  style.font-color: '#000000'")
                target_rdef = resource_defs[section["target"]]
                for rel in related:
                    rel_id = get_item_id(target_rdef, rel)
                    rel_name = _escape(get_item_name(target_rdef, rel))
                    rid = safe_id(rel_id)
                    link = resolve_link(resource_defs, rdef["key"], section["target"], rel_id)
                    w(f"{indent}  {rid}: \"{rel_name}\\n{rel_id}\" {{")
                    if sicon:
                        w(f"{indent}    icon: {ICONS[sicon]}")
                    w(f"{indent}    link: {link}")
                    w(f"{indent}  }}")
                w(f"{indent}}}")
                return True

    elif stype == "rules":
        source = section.get("source", "")
        direction = section.get("direction", "")
        entries = item.get(source, [])
        if direction == "inbound":
            entries = [e for e in entries if not e.get("Egress", False)]
        elif direction == "outbound":
            entries = [e for e in entries if e.get("Egress", True)]
        entries.sort(key=lambda e: e.get("RuleNumber", 0))
        if entries:
            rule_lines = "\\n".join(format_rule(e) for e in entries)
            w(f"{indent}{skey}: \"{slabel}\\n{rule_lines}\" {{")
            w(f"{indent}}}")
            return True

    elif stype == "text":
        source = section.get("source", "")
        items_list = item.get(source, [])
        if items_list:
            text_lines = "\\n".join(format_route(r) for r in items_list)
            w(f"{indent}{skey}: \"{slabel}\\n{text_lines}\" {{")
            w(f"{indent}}}")
            return True

    return False


def generate_detail(config, resource_defs, rdef, item, data):
    """Generate a detail D2 page for a single item."""
    name = get_item_name(rdef, item)
    lines = []
    w = lines.append

    w(f"{safe_id(name)}_detail: \"{name}\" {{")
    w("  style.font-size: 24")
    w(f"  link: {detail_back_link()}")
    w("  style.font-color: '#000000'")

    sections = rdef.get("detail", {}).get("sections", [])

    # Group sections by row
    rows = {}
    ungrouped = []
    for section in sections:
        row = section.get("row")
        if row is not None:
            rows.setdefault(row, []).append(section)
        else:
            ungrouped.append(section)

    # Render ungrouped sections (no row specified) — backwards compatible
    if not rows:
        for section in ungrouped:
            _render_section(w, config, resource_defs, rdef, item, data, section)
    else:
        # Force outer container into grid mode so rows stack properly
        w("  grid-columns: 1")
        # Render in order: process sections by their position in the original list
        # but wrap row groups in grid containers
        rendered_rows = set()
        for section in sections:
            row = section.get("row")
            if row is None:
                _render_section(w, config, resource_defs, rdef, item, data, section)
            elif row not in rendered_rows:
                rendered_rows.add(row)
                row_sections = rows[row]
                w(f"  row_{row}: \" \" {{")
                w(f"    grid-columns: {len(row_sections)}")
                for rs in row_sections:
                    _render_section(w, config, resource_defs, rdef, item, data, rs, indent="    ")
                w("  }")

    w("}")
    return "\n".join(lines)


def generate_main(config, regions):
    """Generate the top-level main.d2 file."""
    org_name = config.get("org_name", "AWS")
    lines = []
    w = lines.append

    w(f"{org_name}: {{")
    w("  style.font-size: 28")
    for region in regions:
        rid = safe_id(region)
        w(f"  {region}: {region} {{")
        w(f"    icon: {ICONS['aws']}")
        w(f"    link: layers.{rid}")
        w("  }")
    w("}")
    w("")
    w("layers: {")
    for region in regions:
        rid = safe_id(region)
        w(f"  {rid}: @{region}.d2")
    w("}")

    return "\n".join(lines)


def generate_region(config, resource_defs, data, region):
    """Generate a region-level D2 file."""
    rid = safe_id(region)
    enabled = config.get("resources", [])
    lines = []
    w = lines.append

    w(f"{rid}_container: \"{region}\" {{")
    w("  style.font-size: 24")
    w("  link: ../index.html")
    w("  style.font-color: '#000000'")
    apply_grid(w, config)

    for vpc in data["vpcs"]:
        vpc_id = vpc["VpcId"]
        vid = safe_id(vpc_id)
        name = get_name(vpc.get("Tags")) or vpc_id
        cidr = vpc["CidrBlock"]
        w(f"  {vid}: \"{name}\\n{cidr}\" {{")
        w(f"    icon: {ICONS['vpc']}")
        w(f"    link: layers.{vid}")
        w("  }")

    # Region/global scoped resources
    for key in enabled:
        if key not in resource_defs:
            continue
        rdef = resource_defs[key]
        if get_scope(rdef) == "vpc":
            continue
        items = data.get(key, [])
        if not items:
            continue
        w(f"  {rdef['key']}: \"{rdef['label']} ({len(items)})\" {{")
        w(f"    icon: {ICONS[rdef['icon']]}")
        w(f"    link: layers.{rdef['key']}")
        w("  }")

    w("}")
    w("")
    w("layers: {")
    for vpc in data["vpcs"]:
        vid = safe_id(vpc["VpcId"])
        w(f"  {vid}: @{vpc['VpcId']}/{vpc['VpcId']}.d2")
    for key in enabled:
        if key not in resource_defs:
            continue
        rdef = resource_defs[key]
        if get_scope(rdef) == "vpc":
            continue
        items = data.get(key, [])
        if not items:
            continue
        w(f"  {rdef['key']}: @{region}/{rdef['links']['d2_grid']}")
    w("}")

    return "\n".join(lines)


def generate_vpc(config, resource_defs, data, vpc):
    """Generate a VPC overview D2 file with tiles from resource definitions."""
    vpc_id = vpc["VpcId"]
    name = get_name(vpc.get("Tags")) or vpc_id
    cidr = vpc["CidrBlock"]
    vid = safe_id(vpc_id)

    enabled = config.get("resources", [])
    lines = []
    w = lines.append

    w(f"{vid}_container: \"{name} ({cidr})\" {{")
    w("  style.font-size: 24")
    w("  link: ../index.html")
    w("  style.font-color: '#000000'")
    apply_grid(w, config)

    for key in enabled:
        if key not in resource_defs:
            continue
        rdef = resource_defs[key]
        if get_scope(rdef) != "vpc":
            continue
        items = filter_for_vpc(rdef, data.get(key, []), vpc_id)
        if not items:
            continue
        w(f"  {rdef['key']}: \"{rdef['label']} ({len(items)})\" {{")
        w(f"    icon: {ICONS[rdef['icon']]}")
        w(f"    link: layers.{rdef['key']}")
        w("  }")

    w("}")
    w("")
    w("layers: {")
    for key in enabled:
        if key not in resource_defs:
            continue
        rdef = resource_defs[key]
        if get_scope(rdef) != "vpc":
            continue
        items = filter_for_vpc(rdef, data.get(key, []), vpc_id)
        if not items:
            continue
        w(f"  {rdef['key']}: @{rdef['links']['d2_grid']}")
    w("}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

VALIDATE_CHECKS = {
    "subnets":        {"service": "ec2",            "method": "describe_subnets",               "result_key": "Subnets",               "label": "Subnets"},
    "igw":            {"service": "ec2",            "method": "describe_internet_gateways",     "result_key": "InternetGateways",      "label": "Internet Gateways"},
    "route_tables":   {"service": "ec2",            "method": "describe_route_tables",          "result_key": "RouteTables",           "label": "Route Tables"},
    "nacls":          {"service": "ec2",            "method": "describe_network_acls",          "result_key": "NetworkAcls",           "label": "Network ACLs"},
    "security_groups":{"service": "ec2",            "method": "describe_security_groups",       "result_key": "SecurityGroups",        "label": "Security Groups"},
    "nat_gateways":   {"service": "ec2",            "method": "describe_nat_gateways",          "result_key": "NatGateways",           "label": "NAT Gateways"},
    "ec2_instances":  {"service": "ec2",            "method": "describe_instances",             "result_key": "Reservations",          "label": "EC2 Instances"},
    "elb":            {"service": "elbv2",          "method": "describe_load_balancers",        "result_key": "LoadBalancers",         "label": "Load Balancers"},
    "rds":            {"service": "rds",            "method": "describe_db_instances",           "result_key": "DBInstances",           "label": "RDS Instances"},
    "lambda_fns":    {"service": "lambda",         "method": "list_functions",                 "result_key": "Functions",             "label": "Lambda Functions"},
    "s3":             {"service": "s3",             "method": "list_buckets",                   "result_key": "Buckets",               "label": "S3 Buckets"},
    "cloudfront":     {"service": "cloudfront",     "method": "list_distributions",             "result_key": "DistributionList.Items","label": "CloudFront Distributions"},
    "sns":            {"service": "sns",            "method": "list_topics",                    "result_key": "Topics",                "label": "SNS Topics"},
    "sqs":            {"service": "sqs",            "method": "list_queues",                    "result_key": "QueueUrls",             "label": "SQS Queues"},
    "eks":            {"service": "eks",            "method": "list_clusters",                  "result_key": "clusters",              "label": "EKS Clusters"},
    "vpc_peering":    {"service": "ec2",            "method": "describe_vpc_peering_connections","result_key": "VpcPeeringConnections", "label": "VPC Peering Connections"},
    "vpn":            {"service": "ec2",            "method": "describe_vpn_connections",       "result_key": "VpnConnections",        "label": "VPN Connections"},
    "route53":        {"service": "route53",        "method": "list_hosted_zones",              "result_key": "HostedZones",           "label": "Route 53 Hosted Zones"},
}


def run_validate(config, resource_defs, region):
    """Query AWS for well-known resource types and compare against registered resources."""
    registered = set(config.get("resources", []))
    clients = {}
    found_registered = []
    found_unregistered = []

    for key, check in VALIDATE_CHECKS.items():
        service = check["service"]
        try:
            if service not in clients:
                region_arg = region
                if service in ("s3", "cloudfront", "route53"):
                    region_arg = "us-east-1"
                clients[service] = boto3.client(service, region_name=region_arg)
            result = getattr(clients[service], check["method"])()
            # Handle nested result_key like DistributionList.Items
            items = result
            for part in check["result_key"].split("."):
                items = items.get(part) if isinstance(items, dict) else items
            count = len(items) if items else 0
        except Exception:
            count = 0

        if count == 0:
            continue

        entry = {"key": key, "label": check["label"], "count": count}
        if key in registered:
            found_registered.append(entry)
        else:
            found_unregistered.append(entry)

    return found_registered, found_unregistered


def generate_validate_html(config, region, registered, unregistered):
    """Generate the validation HTML report."""
    org_name = config.get("org_name", "AWS")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows_reg = ""
    for r in registered:
        rows_reg += f'        <tr><td>{r["label"]}</td><td class="count">{r["count"]}</td></tr>\n'

    rows_unreg = ""
    for r in unregistered:
        rows_unreg += (f'        <tr><td>{r["label"]}</td><td class="count">{r["count"]}</td>'
                       f'<td class="unregistered">Not registered</td></tr>\n')

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Validation Report &mdash; {org_name}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; color: #333; }}
        h1 {{ color: #232f3e; border-bottom: 2px solid #ff9900; padding-bottom: 10px; }}
        h2 {{ color: #232f3e; margin-top: 30px; }}
        .timestamp {{ color: #666; font-size: 14px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 10px 15px; text-align: left; }}
        th {{ background: #232f3e; color: white; }}
        tr:nth-child(even) {{ background: #f9f9f9; }}
        .registered {{ color: #1a8754; font-weight: bold; }}
        .unregistered {{ color: #dc3545; font-weight: bold; }}
        .count {{ text-align: right; font-family: monospace; }}
        .summary {{ background: #f0f0f0; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        a {{ color: #0073bb; }}
    </style>
</head>
<body>
    <h1>Validation Report</h1>
    <p class="timestamp">Generated: {timestamp} &mdash; Region: {region}</p>
    <p><a href="main/index.html">&larr; Back to diagrams</a></p>

    <div class="summary">
        <strong>{len(registered)}</strong> registered resource types found &mdash;
        <strong>{len(unregistered)}</strong> AWS resource types not yet registered
    </div>

    <h2>Registered Resources</h2>
    <table>
        <tr><th>Resource Type</th><th class="count">Count</th></tr>
{rows_reg}    </table>

    <h2>Not Yet Registered</h2>
    <p>These AWS resources exist in the account but are not in the diagram registry.</p>
    <table>
        <tr><th>Resource Type</th><th class="count">Count</th><th>Status</th></tr>
{rows_unreg}    </table>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def clean_generated():
    html_dir = os.path.join(REPO_ROOT, "html")
    icon_symlink = os.path.join(DIAGRAMS_DIR, "aws-icon-package")

    if os.path.exists(DIAGRAMS_DIR):
        for entry in os.listdir(DIAGRAMS_DIR):
            path = os.path.join(DIAGRAMS_DIR, entry)
            if entry == "aws-icon-package":
                continue
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path)
            elif entry.endswith(".d2"):
                os.remove(path)

    if os.path.exists(html_dir):
        for entry in os.listdir(html_dir):
            if entry in ("aws-icon-package", "validate.html", ".gitkeep"):
                continue
            path = os.path.join(html_dir, entry)
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)

    icon_src = os.path.join(html_dir, "aws-icon-package")
    if os.path.isdir(icon_src) and not os.path.islink(icon_symlink):
        os.makedirs(DIAGRAMS_DIR, exist_ok=True)
        os.symlink(icon_src, icon_symlink)

    print("Cleaned generated files.")


def cache_file(region):
    return os.path.join(CACHE_DIR, f"{region}.json")


def save_cache(data, region):
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = cache_file(region)
    with open(path, "w") as f:
        json.dump(data, f, default=str)
    print(f"  cached to {os.path.relpath(path, REPO_ROOT)}")


def load_cache(region):
    path = cache_file(region)
    if not os.path.exists(path):
        print(f"Error: no cached data for {region}. Run without --dry-run first.")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Generate D2 diagrams from AWS data.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Use cached AWS data instead of fetching")
    parser.add_argument("--validate", action="store_true",
                        help="Check AWS for resource types not in config")
    args = parser.parse_args()

    config = load_config()
    resource_defs = load_resource_defs(config)
    regions = config.get("regions", ["us-west-2"])

    clean_generated()

    # Fetch or load data for each region
    for region in regions:
        if args.dry_run:
            print(f"Dry run — loading cached data for {region}...")
            data = load_cache(region)
        else:
            print(f"Fetching AWS data from {region}...")
            data = fetch_all(resource_defs, region)
            save_cache(data, region)

        # Summary
        summary = [f"{len(data.get('vpcs', []))} VPCs"]
        for key in config.get("resources", []):
            if key in resource_defs:
                summary.append(f"{len(data.get(key, []))} {resource_defs[key]['label'].lower()}")
        print(f"  {', '.join(summary)}")

        if args.validate:
            print(f"\nValidating AWS resources for {region}...")
            registered, unregistered = run_validate(config, resource_defs, region)
            html_dir = os.path.join(REPO_ROOT, "html")
            html = generate_validate_html(config, region, registered, unregistered)
            write_file(os.path.join(html_dir, "validate.html"), html)
            for r in registered:
                print(f"  ✓ {r['label']}: {r['count']}")
            for r in unregistered:
                print(f"  ✗ {r['label']}: {r['count']} (not registered)")
            print(f"\nReport: html/validate.html")
            return

        print("Generating D2 files...")

        # Main and region files
        if region == regions[0]:
            write_file(os.path.join(DIAGRAMS_DIR, "main.d2"),
                       generate_main(config, regions))
        write_file(os.path.join(DIAGRAMS_DIR, f"{region}.d2"),
                   generate_region(config, resource_defs, data, region))

        # Region/global scoped resources
        region_dir = os.path.join(DIAGRAMS_DIR, region)
        for key in config.get("resources", []):
            if key not in resource_defs:
                continue
            rdef = resource_defs[key]
            if get_scope(rdef) == "vpc":
                continue
            items = data.get(key, [])
            if not items:
                continue

            write_file(
                os.path.join(region_dir, rdef["links"]["d2_grid"]),
                generate_grid(config, resource_defs, rdef, items),
            )

            if rdef["type"] == "drilldown" and "d2_detail" in rdef["links"]:
                for item in items:
                    raw_id = get_item_id(rdef, item)
                    d2_file = rdef["links"]["d2_detail"].format(raw_id=raw_id)
                    write_file(
                        os.path.join(region_dir, d2_file),
                        generate_detail(config, resource_defs, rdef, item, data),
                    )

        # Per-VPC files
        for vpc in data["vpcs"]:
            vpc_id = vpc["VpcId"]
            vpc_dir = os.path.join(DIAGRAMS_DIR, vpc_id)

            write_file(os.path.join(vpc_dir, f"{vpc_id}.d2"),
                       generate_vpc(config, resource_defs, data, vpc))

            for key in config.get("resources", []):
                if key not in resource_defs:
                    continue
                rdef = resource_defs[key]
                if get_scope(rdef) != "vpc":
                    continue
                items = filter_for_vpc(rdef, data.get(key, []), vpc_id)
                if not items:
                    continue

                # Grid file
                write_file(
                    os.path.join(vpc_dir, rdef["links"]["d2_grid"]),
                    generate_grid(config, resource_defs, rdef, items),
                )

                # Detail files (drilldown only)
                if rdef["type"] == "drilldown" and "d2_detail" in rdef["links"]:
                    for item in items:
                        raw_id = get_item_id(rdef, item)
                        d2_file = rdef["links"]["d2_detail"].format(raw_id=raw_id)
                        write_file(
                            os.path.join(vpc_dir, d2_file),
                            generate_detail(config, resource_defs, rdef, item, data),
                        )

    print("Done.")


if __name__ == "__main__":
    main()
