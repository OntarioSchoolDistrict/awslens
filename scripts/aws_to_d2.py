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
    "security_group": f"{ICON_BASE}/Architecture-Service-Icons_01302026/Arch_Security-Identity/64/Arch_AWS-Network-Firewall_64.svg",
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
    return str(s).replace("-", "_").replace(".", "_").replace("/", "_")


def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    print(f"  wrote {os.path.relpath(path, REPO_ROOT)}")


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

def fetch_all(resource_defs, region):
    """Fetch AWS data for all resource types."""
    clients = {}
    data = {}

    for key, rdef in resource_defs.items():
        fetch = rdef["fetch"]
        service = fetch["service"]
        if service not in clients:
            clients[service] = boto3.client(service, region_name=region)
        client = clients[service]

        method = getattr(client, fetch["method"])
        result = method()
        items = result[fetch["result_key"]]
        data[key] = items

    # Also fetch VPCs (always needed)
    if "ec2" not in clients:
        clients["ec2"] = boto3.client("ec2", region_name=region)
    data["vpcs"] = clients["ec2"].describe_vpcs()["Vpcs"]

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


def generate_detail(config, resource_defs, rdef, item, data):
    """Generate a detail D2 page for a single item."""
    from lookups import LOOKUPS

    name = get_item_name(rdef, item)
    lines = []
    w = lines.append

    w(f"{safe_id(name)}_detail: \"{name}\" {{")
    w("  style.font-size: 24")
    w(f"  link: {detail_back_link()}")
    w("  style.font-color: '#000000'")

    for section in rdef.get("detail", {}).get("sections", []):
        skey = section["key"]
        slabel = section["label"]
        stype = section.get("type", "fields")
        sicon = section.get("icon")

        if stype == "fields":
            field_values = []
            for f in section.get("fields", []):
                val = item.get(f)
                if val is None:
                    # Check computed fields
                    if f == "main_or_custom":
                        val = "Main" if any(a.get("Main") for a in item.get("Associations", [])) else "Custom"
                    elif f == "default_or_custom":
                        val = "Default" if item.get("IsDefault") else "Custom"
                    else:
                        val = ""
                field_values.append(_escape(val))
            text = "\\n".join(field_values)
            w(f"  {skey}: \"{slabel}\\n{text}\" {{")
            if sicon:
                w(f"    icon: {ICONS[sicon]}")
            w("  }")

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
                    w(f"  {skey}: \"{slabel}\\n{rel_name}\" {{")
                    if sicon:
                        w(f"    icon: {ICONS[sicon]}")
                    w(f"    link: {link}")
                    w("  }")

        elif stype == "cross_link_list":
            lookup_fn = LOOKUPS.get(section.get("lookup"))
            if lookup_fn:
                related = lookup_fn(data, item)
                if related:
                    sub = section.get("sub_container")
                    w(f"  {skey}: \"{slabel} ({len(related)})\" {{")
                    apply_grid(w, config)
                    if sub:
                        grid_link = resolve_grid_link(resource_defs, rdef["key"], section["target"])
                        w(f"    link: {grid_link}")
                        w("    style.font-color: '#000000'")
                    target_rdef = resource_defs[section["target"]]
                    for rel in related:
                        rel_id = get_item_id(target_rdef, rel)
                        rel_name = _escape(get_item_name(target_rdef, rel))
                        rid = safe_id(rel_id)
                        link = resolve_link(resource_defs, rdef["key"], section["target"], rel_id)
                        w(f"    {rid}: \"{rel_name}\\n{rel_id}\" {{")
                        if sicon:
                            w(f"      icon: {ICONS[sicon]}")
                        w(f"      link: {link}")
                        w("    }")
                    w("  }")

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
                w(f"  {skey}: \"{slabel}\\n{rule_lines}\" {{")
                w("  }")

        elif stype == "text":
            source = section.get("source", "")
            items_list = item.get(source, [])
            if items_list:
                text_lines = "\\n".join(format_route(r) for r in items_list)
                w(f"  {skey}: \"{slabel}\\n{text_lines}\" {{")
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
    lines = []
    w = lines.append

    w(f"{rid}_container: \"{region}\" {{")
    w("  style.font-size: 24")
    w("  link: ../index.html")
    w("  style.font-color: '#000000'")

    for vpc in data["vpcs"]:
        vpc_id = vpc["VpcId"]
        vid = safe_id(vpc_id)
        name = get_name(vpc.get("Tags")) or vpc_id
        cidr = vpc["CidrBlock"]
        w(f"  {vid}: \"{name}\\n{cidr}\" {{")
        w(f"    icon: {ICONS['vpc']}")
        w(f"    link: layers.{vid}")
        w("  }")

    w("}")
    w("")
    w("layers: {")
    for vpc in data["vpcs"]:
        vid = safe_id(vpc["VpcId"])
        w(f"  {vid}: @{vpc['VpcId']}/{vpc['VpcId']}.d2")
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
        items = filter_for_vpc(rdef, data.get(key, []), vpc_id)
        if not items:
            continue
        w(f"  {rdef['key']}: @{rdef['links']['d2_grid']}")
    w("}")

    return "\n".join(lines)


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
            if entry in ("aws-icon-package", "validate.html"):
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
            print("\nValidation not yet implemented for generic generator.")
            return

        print("Generating D2 files...")

        # Main and region files
        if region == regions[0]:
            write_file(os.path.join(DIAGRAMS_DIR, "main.d2"),
                       generate_main(config, regions))
        write_file(os.path.join(DIAGRAMS_DIR, f"{region}.d2"),
                   generate_region(config, resource_defs, data, region))

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
