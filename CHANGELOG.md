# Changelog

## [1.0.0] - 2026-04-01

### Core
- Generic YAML-driven D2 diagram generator — no custom Python needed per resource type
- Config-driven layouts via `config.yaml`
- `--dry-run` flag for cached data usage (per-region cache files)
- `--validate` flag with HTML report showing registered vs unregistered AWS resources
- Cross-linking between resource detail pages
- Automatic back-link computation from HTML path depth
- AWS Architecture Icons integration

### Resource Support
- 5 default resources: Subnets, Internet Gateways, Route Tables, Network ACLs, Security Groups
- 13 pre-built templates in `scripts/resources/templates/`: EC2, ELB, RDS, Lambda, S3, CloudFront, Route 53, SNS, SQS, EKS, NAT Gateways, VPC Peering, VPN
- Region and global scope support — resources render at the region level alongside VPCs
- Nested dot-notation field filtering (e.g. `DBSubnetGroup.VpcId`)
- `fetch.flatten` for nested API responses (e.g. EC2 Reservations)
- `fetch.wrap_as` for string-list API responses (e.g. SQS, EKS)

### Enrichment Plugins
- Plugin system — `fetch.enrich` runs a post-fetch script to augment data with additional API calls
- EKS enricher — fetches full cluster details, node groups (status, instance types, scaling, AMI type), and cross-links to subnets and security groups

### Detail Page Layout
- `row` field in detail sections groups them side by side in a grid
