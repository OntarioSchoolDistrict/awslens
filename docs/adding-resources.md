# Adding a New AWS Resource Type

This document describes how to add a new AWS resource type to the diagrams.

## Quick Start

Pre-built templates are available in `scripts/resources/templates/` for common AWS resource types. To enable one:

1. Copy it to `scripts/resources/`:
   ```bash
   cp scripts/resources/templates/rds.yaml scripts/resources/
   ```
2. Add the key to the `resources` list in `config.yaml`
3. Run `python3 scripts/aws_to_d2.py && bash scripts/build.sh`

Available templates:

| Template | Key | Scope |
|----------|-----|-------|
| `cloudfront.yaml` | `cloudfront` | global |
| `ec2_instances.yaml` | `ec2_instances` | vpc |
| `eks.yaml` | `eks` | region |
| `elb.yaml` | `elb` | vpc |
| `lambda_fns.yaml` | `lambda_fns` | region |
| `nat_gateways.yaml` | `nat_gateways` | vpc |
| `rds.yaml` | `rds` | vpc |
| `route53.yaml` | `route53` | global |
| `s3.yaml` | `s3` | global |
| `sns.yaml` | `sns` | region |
| `sqs.yaml` | `sqs` | region |
| `vpc_peering.yaml` | `vpc_peering` | region |
| `vpn.yaml` | `vpn` | region |

To create a resource from scratch instead, copy `scripts/resources/resource.yaml.example` and fill in the sections.

## Step-by-Step Example: Adding RDS

### Step 1 — Create the resource YAML

Create `scripts/resources/rds.yaml`:

```yaml
key: rds
label: "RDS Databases"
icon: rds
type: drilldown

fetch:
  service: rds
  method: describe_db_instances
  result_key: DBInstances

filter:
  scope: vpc
  field: DBSubnetGroup.VpcId

id_field: DBInstanceIdentifier
name_field: DBInstanceIdentifier

grid:
  tile_label: "{DBInstanceIdentifier}\n{Engine}"
  tile_icon: rds

detail:
  sections:
    - key: info
      label: "Info"
      type: fields
      icon: rds
      fields:
        - DBInstanceIdentifier
        - Engine
        - DBInstanceClass
        - DBInstanceStatus

links:
  html_path: "rds/{id}.html"
  d2_detail: "{raw_id}.d2"
  d2_grid: "rds.d2"
```

### Step 2 — Add the icon

Find the icon:
```bash
find html/aws-icon-package -name "*RDS*64.svg"
```

Add it to the `ICONS` dict in `scripts/aws_to_d2.py`:
```python
"rds": f"{ICON_SVC}/Arch_Databases/64/Arch_Amazon-RDS_64.svg",
```

### Step 3 — Add to config

In `config.yaml`, add `rds` to the resources list:
```yaml
resources:
  - subnets
  - igw
  - route_tables
  - nacls
  - security_groups
  - rds
```

### Step 4 — Test

```bash
python3 scripts/aws_to_d2.py
bash scripts/build.sh
```

### Step 5 — Add cross-links (optional)

If the resource relates to other resources (e.g. RDS → subnet), add a lookup function to `scripts/lookups.py`:

```python
def subnet_for_rds(data, db):
    subnet_group = db.get("DBSubnetGroup", {})
    subnets = subnet_group.get("Subnets", [])
    result = []
    for sg_subnet in subnets:
        for s in data.get("subnets", []):
            if s["SubnetId"] == sg_subnet.get("SubnetIdentifier"):
                result.append(s)
    return result

LOOKUPS["subnet_for_rds"] = subnet_for_rds
```

Then reference it in the resource YAML:
```yaml
detail:
  sections:
    - key: subnets
      label: "Subnets"
      type: cross_link_list
      icon: subnet
      target: subnets
      lookup: subnet_for_rds
```

## What's Automatic vs Manual

| What | Automatic | Manual |
|------|-----------|--------|
| VPC tile on overview page | ✅ | |
| Filtering by VPC | ✅ | |
| D2 file naming | ✅ | |
| Back links | ✅ | |
| Grid/detail page generation | ✅ | |
| Stale file cleanup | ✅ | |
| Data fetching | ✅ (from YAML fetch section) | |
| Layout (grid columns, etc.) | ✅ (from layout_defaults) | |
| Resource definition | | ✅ (write YAML file) |
| Icon selection | | ✅ (find SVG, add to ICONS) |
| Enrichment plugins | | ✅ (if needed, write enricher script) |
| Cross-link lookups | | ✅ (if needed, write lookup function) |
| Add to config.yaml | | ✅ (one line) |

## Resource YAML Sections

See `scripts/resources/resource.yaml.example` for a fully documented template with all available options.

### Detail Section Types

| Type | Purpose | Example |
|------|---------|---------|
| `fields` | Display raw field values | Instance ID, CIDR, AZ |
| `cross_link` | Link to a single related resource | Subnet → Route Table |
| `cross_link_list` | Link to multiple related resources | Subnet → Security Groups |
| `rules` | Format security group or NACL rules | Inbound/outbound rules |
| `text` | Format a list of items as text | Route table routes |

### Detail Row Layout

By default, detail sections stack vertically. Add a `row` field to group sections side by side:

```yaml
detail:
  sections:
    - key: info
      label: "Info"
      type: fields
      row: 1          # Info and Networking appear side by side
      fields: [...]

    - key: networking
      label: "Networking"
      type: fields
      row: 1
      fields: [...]

    - key: subnets
      label: "Subnets"
      type: cross_link_list
      row: 2          # Subnets and SGs appear side by side on a second row
      ...

    - key: security_groups
      label: "Security Groups"
      type: cross_link_list
      row: 2
      ...
```

Sections sharing the same `row` number are placed in a grid container. Sections without `row` render in the default vertical stack.

## Enrichment Plugins

Some AWS APIs return minimal data (e.g. EKS `list_clusters` returns only names). Use an enricher to fetch additional details:

1. Create `scripts/enrichers/<name>.py` with an `enrich(items, region)` function
2. Add `enrich: <name>` to the `fetch` section of the resource YAML

Example (`scripts/enrichers/eks.py`):
```python
import boto3

def enrich(items, region):
    client = boto3.client("eks", region_name=region)
    enriched = []
    for item in items:
        name = item.get("cluster_name", "")
        detail = client.describe_cluster(name=name)["cluster"]
        enriched.append(detail)
    return enriched
```

## Discovery

Run `--validate` to check for AWS resources not yet in the diagrams:

```bash
python3 scripts/aws_to_d2.py --validate
```

This queries AWS for common resource types and reports which ones aren't registered. Use this to discover what to add next.
