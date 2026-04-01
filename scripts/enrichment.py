"""Enrichment plugin loader.

Each enricher is a Python module in scripts/enrichers/ with an `enrich(items, region)` function.
The function receives the raw fetched items and returns enriched items.
"""

import importlib.util
import os

ENRICHERS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "enrichers")


def run_enricher(name, items, region):
    """Load and run an enricher by name, returning enriched items."""
    path = os.path.join(ENRICHERS_DIR, f"{name}.py")
    if not os.path.exists(path):
        print(f"  warning: enricher '{name}' not found at {path}")
        return items
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.enrich(items, region)
