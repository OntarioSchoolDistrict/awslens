"""EKS enricher — fetches full cluster details and node groups."""

import boto3


def enrich(items, region):
    client = boto3.client("eks", region_name=region)
    enriched = []
    for item in items:
        name = item.get("cluster_name", "")
        try:
            detail = client.describe_cluster(name=name)["cluster"]

            # Flatten networking fields
            vpc_config = detail.get("resourcesVpcConfig", {})
            detail["endpointPublicAccess"] = vpc_config.get("endpointPublicAccess")
            detail["endpointPrivateAccess"] = vpc_config.get("endpointPrivateAccess")
            detail["subnetIds"] = vpc_config.get("subnetIds", [])
            detail["securityGroupIds"] = vpc_config.get("securityGroupIds", [])
            detail["clusterSecurityGroupId"] = vpc_config.get("clusterSecurityGroupId")
            detail["vpcId"] = vpc_config.get("vpcId")

            # Fetch node groups
            ng_names = client.list_nodegroups(clusterName=name).get("nodegroups", [])
            node_groups = []
            for ng_name in ng_names:
                try:
                    ng = client.describe_nodegroup(
                        clusterName=name, nodegroupName=ng_name
                    )["nodegroup"]
                    node_groups.append(ng)
                except Exception:
                    node_groups.append({"nodegroupName": ng_name})
            detail["nodeGroups"] = node_groups

            # Flatten node group summaries
            ng_summaries = []
            all_ng_subnet_ids = set()
            all_ng_sg_ids = set()
            for ng in node_groups:
                ng_name = ng.get("nodegroupName", "unknown")
                status = ng.get("status", "")
                instance_types = ", ".join(ng.get("instanceTypes", []))
                scaling = ng.get("scalingConfig", {})
                desired = scaling.get("desiredSize", "")
                min_size = scaling.get("minSize", "")
                max_size = scaling.get("maxSize", "")
                ami = ng.get("amiType", "")
                ng_summaries.append(
                    f"{ng_name}: {status} | {instance_types} | "
                    f"{ami} | {min_size}-{max_size} (desired: {desired})"
                )
                all_ng_subnet_ids.update(ng.get("subnets", []))
                ng_resources = ng.get("resources", {})
                for asg in ng_resources.get("autoScalingGroups", []):
                    pass  # ASG info if needed later
                remote = ng.get("remoteAccess", {})
                if remote.get("sourceSecurityGroups"):
                    all_ng_sg_ids.update(remote["sourceSecurityGroups"])
            detail["nodeGroupSummary"] = "\n".join(ng_summaries) if ng_summaries else "None"
            detail["nodeGroupSubnetIds"] = list(all_ng_subnet_ids)
            detail["nodeGroupCount"] = len(node_groups)

            enriched.append(detail)
        except Exception:
            enriched.append(item)
    return enriched
