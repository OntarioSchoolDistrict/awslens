# Changelog

## [Unreleased]

### Added
- Per-region data caching — `--dry-run` now uses `.cache/<region>.json` instead of a single cache file, enabling multi-region workflows
- Nested dot-notation field filtering — `filter.field` now supports paths like `DBSubnetGroup.VpcId` in addition to the existing `Attachments[].VpcId` bracket syntax

## [0.0.1] - 2026-04-01

### Added
- Generic YAML-driven D2 diagram generator
- Resource definitions for subnets, internet gateways, route tables, network ACLs, and security groups
- Config-driven layouts via `config.yaml`
- `--dry-run` flag for cached data usage
- `--validate` flag for discovering unregistered AWS resources
- Cross-linking between resource detail pages
- Automatic back-link computation from HTML path depth
- AWS Architecture Icons integration
