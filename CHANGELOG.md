# Changelog

## [Unreleased]

### Added
- Per-region data caching — `--dry-run` now uses `.cache/<region>.json` instead of a single cache file, enabling multi-region workflows
- Nested dot-notation field filtering — `filter.field` now supports paths like `DBSubnetGroup.VpcId` in addition to the existing `Attachments[].VpcId` bracket syntax
- Validate HTML report — `--validate` now queries AWS for well-known resource types and generates `html/validate.html` showing registered vs unregistered resources
- Region and global scope support — resources with `filter.scope` of `region` or `global` now render at the region level alongside VPCs instead of inside each VPC
- 13 pre-built resource templates in `scripts/resources/templates/` — EC2, ELB, RDS, Lambda, S3, CloudFront, Route 53, SNS, SQS, EKS, NAT Gateways, VPC Peering, VPN
- Enrichment plugin system — `fetch.enrich` runs a post-fetch script to augment data with additional API calls
- EKS enricher — fetches full cluster details via `describe_cluster`
- EKS node groups — enricher fetches node group details (status, instance types, scaling, AMI type)
- Detail page row layout — `row` field in detail sections groups them side by side
- EKS cross-links to subnets and security groups
- Icons for all new resource types
- `fetch.flatten` option for nested API responses (e.g. EC2 Reservations)
- `fetch.wrap_as` option for string-list API responses (e.g. SQS, EKS)

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
