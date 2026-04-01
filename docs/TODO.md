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
- ~~Multi-region data caching~~ — per-region cache files in .cache/<region>.json
- ~~Nested field filtering~~ — supports dot-notation (e.g. DBSubnetGroup.VpcId)
- ~~Validate HTML report~~ — `--validate` generates html/validate.html

## Open
