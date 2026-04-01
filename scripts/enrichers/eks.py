"""EKS enricher — fetches full cluster details for each cluster name."""

import boto3


def enrich(items, region):
    client = boto3.client("eks", region_name=region)
    enriched = []
    for item in items:
        name = item.get("cluster_name", "")
        try:
            detail = client.describe_cluster(name=name)["cluster"]
            enriched.append(detail)
        except Exception:
            enriched.append(item)
    return enriched
