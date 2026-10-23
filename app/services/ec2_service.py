
import os
import boto3


def launch_ec2_instance(
    instance_type: str,
    resource_id: str,
    expires_at: str,
) -> str:
    """Launch a tagged EC2 instance only when explicitly enabled."""
    enabled = os.getenv("CLOUDEXPIRE_ALLOW_EC2_LAUNCH", "false").lower()

    if enabled != "true":
        raise RuntimeError(
            "EC2 launch is disabled. Set "
            "CLOUDEXPIRE_ALLOW_EC2_LAUNCH=true to enable it."
        )

    ami_id = os.getenv("CLOUDEXPIRE_AMI_ID")
    subnet_id = os.getenv("CLOUDEXPIRE_SUBNET_ID")
    security_group_id = os.getenv("CLOUDEXPIRE_SECURITY_GROUP_ID")
    region = os.getenv("AWS_REGION", "ap-south-1")

    if not all([ami_id, subnet_id, security_group_id]):
        raise ValueError(
            "Set CLOUDEXPIRE_AMI_ID, CLOUDEXPIRE_SUBNET_ID, "
            "and CLOUDEXPIRE_SECURITY_GROUP_ID."
        )

    ec2 = boto3.client("ec2", region_name=region)

    response = ec2.run_instances(
        ImageId=ami_id,
        InstanceType=instance_type,
        MinCount=1,
        MaxCount=1,
        ClientToken=resource_id,
        SubnetId=subnet_id,
        SecurityGroupIds=[security_group_id],
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [
                    {"Key": "Project", "Value": "CloudExpire"},
                    {"Key": "ManagedBy", "Value": "CloudExpire"},
                    {"Key": "ResourceId", "Value": resource_id},
                    {"Key": "ExpiresAt", "Value": expires_at},
                ],
            }
        ],
    )

    instances = response.get("Instances", [])
    if not instances or "InstanceId" not in instances[0]:
        raise RuntimeError("AWS did not return an instance ID.")

    return instances[0]["InstanceId"]
