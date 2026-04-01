# awslens
AWS infrastructure diagrams powered by D2.

## Prerequisites

- [D2](https://d2lang.com/) CLI installed
- Python 3 with boto3 (`pip install -r requirements.txt`)
- AWS credentials configured

## AWS Architecture Icons

The rendered HTML diagrams use the AWS Architecture Icons 2026 package. This is not included in the repo.

1. Download the icon package from [AWS Architecture Icons](https://aws.amazon.com/architecture/icons/)
2. Extract it to `html/aws-icon-package/`

The expected structure is:
```
html/aws-icon-package/
├── Architecture-Group-Icons_01302026/
├── Architecture-Service-Icons_01302026/
├── Category-Icons_01302026/
└── Resource-Icons_01302026/
```

## Configuration

Edit `config.yaml` to customize:
- Organization name and AWS region
- Grid column counts and tile sizes per resource type
- Sub-container layouts inside detail pages

See `docs/custom-layouts.md` for details.

## Getting Started

Run `--validate` first to see what AWS resources exist in your account:

```bash
python3 scripts/aws_to_d2.py --validate
```

This generates `html/validate.html` showing which resource types are registered and which aren't. Use this to decide what to add — see `docs/adding-resources.md`.

## Usage

```bash
# Fetch AWS data and generate D2 diagrams
python3 scripts/aws_to_d2.py

# Build HTML from D2 diagrams
bash scripts/build.sh
```

Open `html/main/index.html` in a browser to view the diagrams.

### Options

```bash
# Use cached data (skip AWS API calls) — useful for layout tweaks
python3 scripts/aws_to_d2.py --dry-run

# Check for AWS resources not yet in the diagrams
python3 scripts/aws_to_d2.py --validate

# Combine: validate using cached data for the summary
python3 scripts/aws_to_d2.py --validate --dry-run
```

## Documentation

- `docs/expanding.md` — system architecture and how it all fits together
- `docs/adding-resources.md` — step-by-step guide to add a new AWS resource type
- `docs/custom-layouts.md` — config.yaml reference and D2 layout properties
- `docs/TODO.md` — future improvements and completed items
