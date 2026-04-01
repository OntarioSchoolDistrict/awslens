# awslens — System Architecture

This guide explains how the system works and how it all fits together.

## Overview

The system generates interactive HTML diagrams of your AWS infrastructure using D2. It's driven by YAML configuration files — no custom Python code is needed for most resource types.

## Project Structure

```
awslens/
├── config.yaml                    # Org name, regions, resources, layout defaults
├── scripts/
│   ├── aws_to_d2.py               # Generic generator — reads YAML, fetches AWS, generates D2
│   ├── build.sh                   # Compiles D2 → HTML
│   ├── lookups.py                 # Cross-link relationship functions
│   └── resources/                 # One YAML file per AWS resource type
│       ├── resource.yaml.example  # Template for new resource types
│       ├── subnets.yaml
│       ├── igw.yaml
│       ├── route_tables.yaml
│       ├── nacls.yaml
│       └── security_groups.yaml
├── diagrams/                      # Generated D2 files (gitignored)
├── html/                          # Generated HTML output (gitignored)
│   └── aws-icon-package/          # AWS icons (not in repo, see README)
├── .cache/                        # Cached AWS data for --dry-run (gitignored)
└── docs/
```

## Data Flow

```
config.yaml + scripts/resources/*.yaml
        ↓
aws_to_d2.py
        ↓
    ┌───────────────┐
    │ Fetch AWS data │ ──→ .cache/aws_data.json (for --dry-run)
    └───────────────┘
        ↓
    ┌───────────────┐
    │ Generate D2    │ ──→ diagrams/*.d2
    └───────────────┘
        ↓
    build.sh (d2 CLI)
        ↓
    html/main/index.html
```

## How the Generic Generator Works

1. Reads `config.yaml` for org name, regions, enabled resources, and layout defaults
2. Reads each `scripts/resources/<key>.yaml` for resource definitions
3. Fetches AWS data using the `fetch` section of each resource YAML
4. For each region and VPC:
   - Filters resources using the `filter` section
   - Generates grid/leaf pages using the `grid` section
   - Generates detail pages using the `detail` section
   - Resolves cross-links using `scripts/lookups.py`
5. D2 files are compiled to HTML by `build.sh`

## Diagram Hierarchy

```
My Organization AWS                  # main.d2
└── us-west-2                        # us-west-2.d2 (region layer)
    └── vpc-xxxxxxxx                 # vpc-xxxxxxxx.d2 (VPC layer)
        ├── Subnets                  # subnets.d2 (drilldown)
        │   └── subnet-xxx          # subnet-xxx.d2 (detail)
        ├── Internet Gateway         # igw.d2 (leaf)
        ├── Route Tables             # route_tables.d2 (drilldown)
        │   └── rtb-xxx             # rtb-xxx.d2 (detail)
        ├── Network ACLs             # nacls.d2 (drilldown)
        │   └── acl-xxx             # acl-xxx.d2 (detail)
        └── Security Groups          # security_groups.d2 (drilldown)
            └── sg-xxx              # sg-xxx.d2 (detail)
```

## Resource YAML Structure

Each resource type is defined by a YAML file with these sections:

| Section | Purpose |
|---------|---------|
| **Identity** | `key`, `label`, `icon`, `type` — what is this resource |
| **Data** | `fetch` — how to get the data from AWS (service, method, result_key) |
| **Filter** | `filter` — how to scope items to a VPC (field to match) |
| **Grid** | `grid` — how items appear on the grid page (tile_label, group_by) |
| **Detail** | `detail.sections` — what to show on detail pages (fields, cross-links, rules) |
| **Links** | `links` — where pages live in the HTML hierarchy (html_path, d2 filenames) |

See `scripts/resources/resource.yaml.example` for a fully documented template.

## Page Types

- **Leaf** (`type: leaf`) — single page listing all items, no drill-down. Used for resources with few items (e.g. Internet Gateway).
- **Drilldown** (`type: drilldown`) — grid page with clickable tiles that link to individual detail pages. Used for resources with many items (e.g. Subnets, Security Groups).

## Cross-Linking

Resources can link to each other across pages. Cross-links are defined in the `detail.sections` of a resource YAML:

```yaml
detail:
  sections:
    - key: route_table
      type: cross_link
      target: route_tables
      lookup: route_table_for_subnet
```

The `lookup` references a Python function in `scripts/lookups.py` that finds related items. The generic generator computes the relative HTML path automatically.

## Back Links

Every page has a container box that links back to its parent:
- Detail pages → grid page (`./index.html`)
- Grid/leaf pages with subdirectories → VPC page (`../index.html`)
- Leaf pages without subdirectories → VPC page (`./index.html`)

Back links are computed automatically from the `links.html_path` in the resource YAML.

## Config Reference

### config.yaml

```yaml
org_name: "My Organization AWS"     # Top-level page title

regions:                             # AWS regions to include
  - us-west-2

resources:                           # Resource types to generate (must have matching YAML)
  - subnets
  - igw
  - route_tables
  - nacls
  - security_groups

layout_defaults:                     # Default grid/tile settings
  grid_columns: 2
  grid_gap: null

sub_containers:                      # Sub-container keys for detail page sections
  - vpc_tiles
  - subnet_security_groups
  - nacl_subnets
```

## CLI Reference

```bash
# Full run: fetch AWS data, generate D2, cache data
python3 scripts/aws_to_d2.py

# Dry run: use cached data (no AWS calls)
python3 scripts/aws_to_d2.py --dry-run

# Validate: check for unregistered AWS resources
python3 scripts/aws_to_d2.py --validate

# Build HTML from D2 files
bash scripts/build.sh
```
