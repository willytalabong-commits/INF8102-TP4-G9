#!/usr/bin/env python3

import boto3
import botocore

from troposphere import (
    Template,
    Ref,
    Output,
    Tags,
)

from troposphere.ec2 import (
    VPC,
    InternetGateway,
    VPCGatewayAttachment,
    Subnet,
    RouteTable,
    Route,
    SubnetRouteTableAssociation,
    FlowLog,
    DestinationOptions,
)


def build_template():
    """
    Construit une VPC simple (comme dans l'exemple du TP) et ajoute
    un VPC Flow Log qui envoie uniquement les paquets REJECT vers
    le bucket S3 polystudents3-group9.
    """
    t = Template()
    t.set_description(
        "TP4 - VPC avec VPC Flow Logs (REJECT uniquement) vers S3 polystudents3-group9 - Groupe 9"
    )

    # 1) VPC
    vpc = t.add_resource(
        VPC(
            "PolystudentVPC",
            CidrBlock="10.0.0.0/16",
            EnableDnsSupport=True,
            EnableDnsHostnames=True,
            Tags=Tags(Name="polystudent-vpc-group9"),
        )
    )

    # 2) Internet Gateway + attachement
    igw = t.add_resource(
        InternetGateway(
            "InternetGateway",
            Tags=Tags(Name="polystudent-igw-group9"),
        )
    )

    t.add_resource(
        VPCGatewayAttachment(
            "VPCGatewayAttachment",
            InternetGatewayId=Ref(igw),
            VpcId=Ref(vpc),
        )
    )

    # 3) Subnet publique (exemple)
    public_subnet = t.add_resource(
        Subnet(
            "PublicSubnet",
            VpcId=Ref(vpc),
            CidrBlock="10.0.1.0/24",
            MapPublicIpOnLaunch=True,
            Tags=Tags(Name="public-subnet-group9"),
        )
    )

    # 4) Route table + route vers l’IGW
    public_rt = t.add_resource(
        RouteTable(
            "PublicRouteTable",
            VpcId=Ref(vpc),
            Tags=Tags(Name="public-rt-group9"),
        )
    )

    t.add_resource(
        Route(
            "DefaultRouteToInternet",
            RouteTableId=Ref(public_rt),
            DestinationCidrBlock="0.0.0.0/0",
            GatewayId=Ref(igw),
        )
    )

    t.add_resource(
        SubnetRouteTableAssociation(
            "PublicSubnetRouteTableAssociation",
            SubnetId=Ref(public_subnet),
            RouteTableId=Ref(public_rt),
        )
    )

    # 5) VPC Flow Log : on capture uniquement le trafic REJECT et on l'envoie vers S3

    # ARN du bucket S3 de la Question 2
    s3_bucket_arn = "arn:aws:s3:::polystudents3-group9"

    flow_log = t.add_resource(
        FlowLog(
            "VpcRejectedFlowLogs",
            ResourceId=Ref(vpc),
            ResourceType="VPC",          # on loggue la VPC entière
            TrafficType="REJECT",        # uniquement les paquets REJECT (demandé dans l'énoncé)
            LogDestinationType="s3",
            LogDestination=s3_bucket_arn,
            # DestinationOptions optionnelles mais propres
            DestinationOptions=DestinationOptions(
                FileFormat="plain-text",
                HiveCompatiblePartitions=False,
                PerHourPartition=True,
            ),
            # DeliverLogsPermissionArn est optionnel pour S3 si la
            # bucket policy permet la livraison (AWS peut l’attacher automatiquement).
        )
    )

    # Outputs pour preuve
    t.add_output(
        [
            Output(
                "VpcId",
                Description="ID de la VPC créée",
                Value=Ref(vpc),
            ),
            Output(
                "PublicSubnetId",
                Description="ID du subnet public",
                Value=Ref(public_subnet),
            ),
            Output(
                "VpcFlowLogId",
                Description="ID du VPC Flow Log (REJECT -> S3)",
                Value=Ref(flow_log),
            ),
        ]
    )

    return t


def deploy_stack(template, stack_name="polystudent-vpc-flowlogs-stack"):
    """
    Déploie le template CloudFormation via boto3.
    """
    cf = boto3.client("cloudformation", region_name="us-east-1")

    template_body = template.to_yaml()

    # Sauvegarde locale pour preuve
    with open("vpc_flowlogs_template.yaml", "w", encoding="utf-8") as f:
        f.write(template_body)
    print("Template VPC + Flow Logs générée dans vpc_flowlogs_template.yaml")

    try:
        print(f"Création du stack CloudFormation {stack_name}...")
        response = cf.create_stack(
            StackName=stack_name,
            TemplateBody=template_body,
            Capabilities=[
                "CAPABILITY_NAMED_IAM",
                "CAPABILITY_IAM",
            ],
        )
        print("Stack en cours de création, id :", response["StackId"])
        print(
            "Va dans la console AWS → CloudFormation pour vérifier l'état du stack "
            "et prends des captures d'écran pour le rapport (stack + VPC Flow Logs + S3)."
        )

    except botocore.exceptions.ClientError as e:
        if "AlreadyExistsException" in str(e):
            print(
                f"Le stack {stack_name} existe déjà. "
                "Supprime-le dans CloudFormation ou change le nom du stack."
            )
        else:
            raise


if __name__ == "__main__":
    template = build_template()
    deploy_stack(template)
