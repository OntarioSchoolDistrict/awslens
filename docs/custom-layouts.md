# Customizing Diagram Layouts

This document explains how to customize the visual layout of diagrams.

## config.yaml — Layout Settings

All layout settings are in `config.yaml`. Edit and re-run to apply changes — no code needed.

### Layout Defaults

```yaml
layout_defaults:
  grid_columns: 2       # Number of columns in grid layouts
  grid_gap: null         # Pixel gap between grid cells (null = D2 default)
  tile_width: null       # Fixed tile width (null = auto-size)
  tile_height: null      # Fixed tile height (null = auto-size)
  tile_font_size: null   # Tile label font size (null = D2 default)
```

These defaults apply to all resource grid pages and sub-containers.

### Sub-Containers

Sub-containers are sections inside detail pages (e.g. "Security Groups" inside a subnet detail). List them to enable grid layout:

```yaml
sub_containers:
  - vpc_tiles
  - subnet_security_groups
  - nacl_subnets
```

All sub-containers use `layout_defaults` for their grid settings.

## Resource-Level Layout

Grid layout for each resource type is controlled by the `grid` section in its YAML file (`scripts/resources/<key>.yaml`):

```yaml
grid:
  group_by: AvailabilityZone    # Group items into nested containers
  tile_label: "{Name}\n{CidrBlock}"  # Label template for each tile
  tile_icon: subnet              # Icon for each tile
```

### Tile Label Templates

Use `{FieldName}` to insert AWS field values:

```yaml
tile_label: "{GroupName}\n{inbound_count} inbound, {outbound_count} outbound"
```

Available computed fields:
- `{Name}` — Name tag value
- `{main_or_custom}` — "Main" or "Custom" (route tables)
- `{default_or_custom}` — "Default" or "Custom" (NACLs)
- `{route_count}` — number of routes
- `{subnet_count}` — number of associated subnets
- `{inbound_count}` — number of inbound rules
- `{outbound_count}` — number of outbound rules

## D2 Layout Properties Reference

### Grid Layout

```
container: "My Grid" {
  grid-columns: 4
  grid-gap: 16
  item1: "A"
  item2: "B"
}
```

### Shape Sizing

```
my_shape: "Label" {
  width: 300
  height: 170
}
```

### Font Size

```
my_shape: "Label" {
  style.font-size: 14
}
```

### Icons

```
my_shape: "Label" {
  icon: aws-icon-package/path/to/icon.svg
}
```

Find available icons:
```bash
find html/aws-icon-package -name "*<keyword>*64.svg" | grep -v MACOSX
```

### Connections

```
shape_a -> shape_b
shape_a -> shape_b: "label"
```

### Containers

```
outer: "Group" {
  inner1: "A"
  inner2: "B"
}
```

### Tooltips

```
my_shape: "Label" {
  tooltip: "Hover text"
}
```

## D2 Documentation

- [Containers](https://d2lang.com/tour/containers)
- [Grid diagrams](https://d2lang.com/tour/grid-diagrams)
- [Icons](https://d2lang.com/tour/icons)
- [Styles](https://d2lang.com/tour/style)
