#!/usr/bin/env python

from troposphere import (
    Template,
    Ref,
    Parameter,
    Output,
    Sub,
    Tags,
)
from troposphere.ec2 import (
    VPC,
    Subnet,
    InternetGateway,
    VPCGatewayAttachment,
    RouteTable,
    Route,
    SubnetRouteTableAssociation,
    NatGateway,
    EIP,
    SecurityGroup,
    SecurityGroupRule,
)

import boto3
import botocore
import json
import os


def build_template():
    t = Template()
    t.set_description(
        "TP4 - VPC polystudentlab-vpc reproduite en Python avec Troposphere "
        "(2 AZ, 4 subnets, IGW, NAT GW, route tables, security group)."
    )

    # -----------------------
    # Paramètres
    # -----------------------

    vpc_cidr_param = t.add_parameter(
        Parameter(
            "VpcCidr",
            Type="String",
            Default="10.0.0.0/16",
            Description="CIDR de la VPC",
        )
    )

    public_subnet1_cidr = t.add_parameter(
        Parameter(
            "PublicSubnet1Cidr",
            Type="String",
            Default="10.0.0.0/24",
            Description="CIDR du subnet public AZ1",
        )
    )

    private_subnet1_cidr = t.add_parameter(
        Parameter(
            "PrivateSubnet1Cidr",
            Type="String",
            Default="10.0.1.0/24",
            Description="CIDR du subnet privé AZ1",
        )
    )

    public_subnet2_cidr = t.add_parameter(
        Parameter(
            "PublicSubnet2Cidr",
            Type="String",
            Default="10.0.2.0/24",
            Description="CIDR du subnet public AZ2",
        )
    )

    private_subnet2_cidr = t.add_parameter(
        Parameter(
            "PrivateSubnet2Cidr",
            Type="String",
            Default="10.0.3.0/24",
            Description="CIDR du subnet privé AZ2",
        )
    )

    az1_param = t.add_parameter(
        Parameter(
            "AZ1",
            Type="AWS::EC2::AvailabilityZone::Name",
            Default="us-east-1a",  # adapte à ta région : ex. ca-central-1a
            Description="Première zone de disponibilité",
        )
    )

    az2_param = t.add_parameter(
        Parameter(
            "AZ2",
            Type="AWS::EC2::AvailabilityZone::Name",
            Default="us-east-1b",  # adapte à ta région : ex. ca-central-1b
            Description="Deuxième zone de disponibilité",
        )
    )

    # -----------------------
    # VPC
    # -----------------------

    vpc = t.add_resource(
        VPC(
            "PolystudentVpc",
            CidrBlock=Ref(vpc_cidr_param),
            EnableDnsHostnames=True,
            EnableDnsSupport=True,
            Tags=Tags(
                Name="polystudent-vpc-py",
                Project="INF8102-TP4",
            ),
        )
    )

    # -----------------------
    # Subnets
    # -----------------------

    public_subnet1 = t.add_resource(
        Subnet(
            "PublicSubnet1",
            VpcId=Ref(vpc),
            CidrBlock=Ref(public_subnet1_cidr),
            AvailabilityZone=Ref(az1_param),
            MapPublicIpOnLaunch=True,
            Tags=Tags(
                Name="public-subnet-az1",
                Type="public",
            ),
        )
    )

    private_subnet1 = t.add_resource(
        Subnet(
            "PrivateSubnet1",
            VpcId=Ref(vpc),
            CidrBlock=Ref(private_subnet1_cidr),
            AvailabilityZone=Ref(az1_param),
            MapPublicIpOnLaunch=False,
            Tags=Tags(
                Name="private-subnet-az1",
                Type="private",
            ),
        )
    )

    public_subnet2 = t.add_resource(
        Subnet(
            "PublicSubnet2",
            VpcId=Ref(vpc),
            CidrBlock=Ref(public_subnet2_cidr),
            AvailabilityZone=Ref(az2_param),
            MapPublicIpOnLaunch=True,
            Tags=Tags(
                Name="public-subnet-az2",
                Type="public",
            ),
        )
    )

    private_subnet2 = t.add_resource(
        Subnet(
            "PrivateSubnet2",
            VpcId=Ref(vpc),
            CidrBlock=Ref(private_subnet2_cidr),
            AvailabilityZone=Ref(az2_param),
            MapPublicIpOnLaunch=False,
            Tags=Tags(
                Name="private-subnet-az2",
                Type="private",
            ),
        )
    )

    # -----------------------
    # Internet Gateway + attachment
    # -----------------------

    igw = t.add_resource(
        InternetGateway(
            "InternetGateway",
            Tags=Tags(
                Name="polystudent-igw",
            ),
        )
    )

    igw_attachment = t.add_resource(
        VPCGatewayAttachment(
            "IgwAttachment",
            VpcId=Ref(vpc),
            InternetGatewayId=Ref(igw),
        )
    )

    # -----------------------
    # EIP + NAT Gateway (un par AZ)
    # -----------------------

    eip_nat1 = t.add_resource(
        EIP(
            "NatEip1",
            Domain="vpc",
        )
    )

    nat_gw1 = t.add_resource(
        NatGateway(
            "NatGateway1",
            AllocationId=Sub("${NatEip1.AllocationId}"),
            SubnetId=Ref(public_subnet1),
            Tags=Tags(Name="nat-gw-az1"),
        )
    )

    eip_nat2 = t.add_resource(
        EIP(
            "NatEip2",
            Domain="vpc",
        )
    )

    nat_gw2 = t.add_resource(
        NatGateway(
            "NatGateway2",
            AllocationId=Sub("${NatEip2.AllocationId}"),
            SubnetId=Ref(public_subnet2),
            Tags=Tags(Name="nat-gw-az2"),
        )
    )

    # -----------------------
    # Route table publique + associations
    # -----------------------

    public_rt = t.add_resource(
        RouteTable(
            "PublicRouteTable",
            VpcId=Ref(vpc),
            Tags=Tags(Name="public-rt"),
        )
    )

    public_default_route = t.add_resource(
        Route(
            "PublicDefaultRoute",
            RouteTableId=Ref(public_rt),
            DestinationCidrBlock="0.0.0.0/0",
            GatewayId=Ref(igw),
            DependsOn=igw_attachment.title,
        )
    )

    t.add_resource(
        SubnetRouteTableAssociation(
            "PublicSubnet1RouteAssociation",
            RouteTableId=Ref(public_rt),
            SubnetId=Ref(public_subnet1),
        )
    )

    t.add_resource(
        SubnetRouteTableAssociation(
            "PublicSubnet2RouteAssociation",
            RouteTableId=Ref(public_rt),
            SubnetId=Ref(public_subnet2),
        )
    )

    # -----------------------
    # Route tables privées + associations
    # -----------------------

    private_rt1 = t.add_resource(
        RouteTable(
            "PrivateRouteTable1",
            VpcId=Ref(vpc),
            Tags=Tags(Name="private-rt-az1"),
        )
    )

    private_rt2 = t.add_resource(
        RouteTable(
            "PrivateRouteTable2",
            VpcId=Ref(vpc),
            Tags=Tags(Name="private-rt-az2"),
        )
    )

    # Route privée AZ1 -> NAT GW1
    t.add_resource(
        Route(
            "PrivateRoute1ToNat",
            RouteTableId=Ref(private_rt1),
            DestinationCidrBlock="0.0.0.0/0",
            NatGatewayId=Ref(nat_gw1),
        )
    )

    # Route privée AZ2 -> NAT GW2
    t.add_resource(
        Route(
            "PrivateRoute2ToNat",
            RouteTableId=Ref(private_rt2),
            DestinationCidrBlock="0.0.0.0/0",
            NatGatewayId=Ref(nat_gw2),
        )
    )

    # Associations subnets privés
    t.add_resource(
        SubnetRouteTableAssociation(
            "PrivateSubnet1RouteAssociation",
            RouteTableId=Ref(private_rt1),
            SubnetId=Ref(private_subnet1),
        )
    )

    t.add_resource(
        SubnetRouteTableAssociation(
            "PrivateSubnet2RouteAssociation",
            RouteTableId=Ref(private_rt2),
            SubnetId=Ref(private_subnet2),
        )
    )

    # -----------------------
    # Security Group polystudent-sg
    # (ports comme dans la Fig. 9)
    # -----------------------

    sg = t.add_resource(
        SecurityGroup(
            "PolystudentSecurityGroup",
            GroupDescription="Security group pour polystudentlab-vpc (TP4)",
            VpcId=Ref(vpc),
            SecurityGroupIngress=[
                # SSH
                SecurityGroupRule(
                    IpProtocol="tcp", FromPort=22, ToPort=22, CidrIp="0.0.0.0/0"
                ),
                # HTTP
                SecurityGroupRule(
                    IpProtocol="tcp", FromPort=80, ToPort=80, CidrIp="0.0.0.0/0"
                ),
                # HTTPS
                SecurityGroupRule(
                    IpProtocol="tcp", FromPort=443, ToPort=443, CidrIp="0.0.0.0/0"
                ),
                # DNS TCP
                SecurityGroupRule(
                    IpProtocol="tcp", FromPort=53, ToPort=53, CidrIp="0.0.0.0/0"
                ),
                # DNS UDP
                SecurityGroupRule(
                    IpProtocol="udp", FromPort=53, ToPort=53, CidrIp="0.0.0.0/0"
                ),
                # MSSQL
                SecurityGroupRule(
                    IpProtocol="tcp", FromPort=1433, ToPort=1433, CidrIp="0.0.0.0/0"
                ),
                # PostgreSQL
                SecurityGroupRule(
                    IpProtocol="tcp", FromPort=5432, ToPort=5432, CidrIp="0.0.0.0/0"
                ),
                # MySQL
                SecurityGroupRule(
                    IpProtocol="tcp", FromPort=3306, ToPort=3306, CidrIp="0.0.0.0/0"
                ),
                # RDP
                SecurityGroupRule(
                    IpProtocol="tcp", FromPort=3389, ToPort=3389, CidrIp="0.0.0.0/0"
                ),
                # OSSEC
                SecurityGroupRule(
                    IpProtocol="tcp", FromPort=1514, ToPort=1514, CidrIp="0.0.0.0/0"
                ),
                # ElasticSearch
                SecurityGroupRule(
                    IpProtocol="tcp",
                    FromPort=9200,
                    ToPort=9300,
                    CidrIp="0.0.0.0/0",
                ),
            ],
            # Egress: tout trafic sortant autorisé
            SecurityGroupEgress=[
                SecurityGroupRule(
                    IpProtocol="-1",
                    FromPort=0,
                    ToPort=65535,
                    CidrIp="0.0.0.0/0",
                )
            ],
            Tags=Tags(Name="polystudent-sg"),
        )
    )

    # -----------------------
    # Outputs
    # -----------------------

    t.add_output(
        [
            Output(
                "VpcId",
                Description="ID de la VPC",
                Value=Ref(vpc),
            ),
            Output(
                "PublicSubnet1Id",
                Description="Subnet public AZ1",
                Value=Ref(public_subnet1),
            ),
            Output(
                "PrivateSubnet1Id",
                Description="Subnet privé AZ1",
                Value=Ref(private_subnet1),
            ),
            Output(
                "PublicSubnet2Id",
                Description="Subnet public AZ2",
                Value=Ref(public_subnet2),
            ),
            Output(
                "PrivateSubnet2Id",
                Description="Subnet privé AZ2",
                Value=Ref(private_subnet2),
            ),
            Output(
                "SecurityGroupId",
                Description="Security group polystudent-sg",
                Value=Ref(sg),
            ),
        ]
    )

    return t


def deploy_stack(template, stack_name="polystudent-vpc-py"):
    cf = boto3.client("cloudformation")

    template_body = template.to_yaml()

    # Sauvegarde locale pour preuve / debug
    with open("vpc_template.yaml", "w", encoding="utf-8") as f:
        f.write(template_body)
    print("Template CloudFormation générée dans vpc_template.yaml")

    try:
        # On tente de créer le stack (simple pour le TP4)
        print(f"Création du stack CloudFormation {stack_name}...")
        response = cf.create_stack(
            StackName=stack_name,
            TemplateBody=template_body,
            Capabilities=[
                "CAPABILITY_NAMED_IAM",
                "CAPABILITY_IAM",
            ],
        )
        print("Stack en cours de création, id:", response["StackId"])
        print(
            "Tu peux maintenant aller dans la console AWS → CloudFormation "
            "pour suivre la création et prendre des captures d'écran."
        )
    except botocore.exceptions.ClientError as e:
        if "AlreadyExistsException" in str(e):
            print(
                f"Le stack {stack_name} existe déjà. "
                "Supprime-le ou adapte le code pour faire un update_stack."
            )
        else:
            raise


if __name__ == "__main__":
    template = build_template()
    deploy_stack(template)
