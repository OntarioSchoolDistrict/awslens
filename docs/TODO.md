# TODO — Future Improvements

## Completed

- ~~Centralize back links~~ — computed from html_path depth
- ~~Eliminate duplicate filtering~~ — registry-driven, then YAML-driven
- ~~Standardize generator patterns~~ — replaced by generic YAML-driven generator
- ~~Fix D2 file naming~~ — raw AWS IDs
- ~~Single source of truth~~ — RESOURCES registry, then resource YAML files
- ~~Add --dry-run flag~~ — cached data in .cache/aws_data.json
- ~~Add --validate flag~~ — checks AWS for unregistered resources
- ~~Unified generator entry point~~ — replaced by generic generator
- ~~Derive HTML paths from registry~~ — computed from links.html_path
- ~~Separate D2 content from structure~~ — YAML defines content, generator handles structure
- ~~Config-driven layouts~~ — config.yaml layout_defaults
- ~~Generic YAML-driven generator~~ — no custom Python per resource type

## Open

### Multi-region data caching
Currently `--dry-run` uses a single cache file. With multiple regions, each region should have its own cache file.

### Validate HTML report
The `--validate` flag writes an HTML report but the generic generator doesn't include it yet. Need to port the validate report generation.

### Nested field filtering
The `filter.field` supports `Attachments[].VpcId` syntax but deeper nesting like `DBSubnetGroup.VpcId` is not yet implemented.

### Per-resource layout overrides
Currently all resources use `layout_defaults`. Could add per-resource layout settings back if needed.
