#!/usr/bin/env python3

import boto3
import botocore

from troposphere import (
    Template,
    Ref,
    Sub,
    Parameter,
    Output,
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
    SecurityGroup,
    SecurityGroupRule,
    Instance,
)

from troposphere.cloudwatch import (
    Alarm,
    MetricDimension,
)


def build_template():
    """
    Construit une VPC avec 4 subnets (2 publics, 2 privés),
    4 instances EC2 (2 publiques, 2 privées) associées à l'InstanceProfile IAM
    EXISTANT 'LabInstanceProfile', et des alarmes CloudWatch NetworkPacketsIn
    (> 1000 pkts/s) pour chaque instance.
    """
    t = Template()
    t.set_description(
        "TP4 - EC2 instances (2 publiques, 2 privées) avec rôle IAM LabRole via "
        "l'InstanceProfile existant 'LabInstanceProfile' et alarmes CloudWatch "
        "sur NetworkPacketsIn (seuil 1000 pkts/s)."
    )

    # -----------------------
    # Paramètres
    # -----------------------

    # AMI Amazon Linux 2 pour us-east-1 (à adapter si besoin)
    ami_param = t.add_parameter(
        Parameter(
            "AmiId",
            Type="AWS::EC2::Image::Id",
            Description="AMI à utiliser pour les instances EC2",
            Default="ami-0c02fb55956c7d316",  # Amazon Linux 2 - us-east-1
        )
    )

    instance_type_param = t.add_parameter(
        Parameter(
            "InstanceType",
            Type="String",
            Default="t3.micro",
            Description="Type des instances EC2",
        )
    )

    keyname_param = t.add_parameter(
        Parameter(
            "KeyName",
            Type="AWS::EC2::KeyPair::KeyName",
            Description="Nom de la paire de clés EC2 pour SSH",
        )
    )

    az1_param = t.add_parameter(
        Parameter(
            "AZ1",
            Type="AWS::EC2::AvailabilityZone::Name",
            Default="us-east-1a",
            Description="Première zone de disponibilité",
        )
    )

    az2_param = t.add_parameter(
        Parameter(
            "AZ2",
            Type="AWS::EC2::AvailabilityZone::Name",
            Default="us-east-1b",
            Description="Deuxième zone de disponibilité",
        )
    )

    # -----------------------
    # VPC + Subnets
    # -----------------------

    vpc = t.add_resource(
        VPC(
            "PolystudentVpc",
            CidrBlock="10.0.0.0/16",
            EnableDnsSupport=True,
            EnableDnsHostnames=True,
            Tags=Tags(Name="polystudent-vpc-ec2-alarms"),
        )
    )

    # Subnets publics
    public_subnet_az1 = t.add_resource(
        Subnet(
            "PublicSubnetAz1",
            VpcId=Ref(vpc),
            CidrBlock="10.0.0.0/24",
            AvailabilityZone=Ref(az1_param),
            MapPublicIpOnLaunch=True,
            Tags=Tags(Name="public-az1"),
        )
    )

    public_subnet_az2 = t.add_resource(
        Subnet(
            "PublicSubnetAz2",
            VpcId=Ref(vpc),
            CidrBlock="10.0.1.0/24",
            AvailabilityZone=Ref(az2_param),
            MapPublicIpOnLaunch=True,
            Tags=Tags(Name="public-az2"),
        )
    )

    # Subnets privés
    private_subnet_az1 = t.add_resource(
        Subnet(
            "PrivateSubnetAz1",
            VpcId=Ref(vpc),
            CidrBlock="10.0.2.0/24",
            AvailabilityZone=Ref(az1_param),
            MapPublicIpOnLaunch=False,
            Tags=Tags(Name="private-az1"),
        )
    )

    private_subnet_az2 = t.add_resource(
        Subnet(
            "PrivateSubnetAz2",
            VpcId=Ref(vpc),
            CidrBlock="10.0.3.0/24",
            AvailabilityZone=Ref(az2_param),
            MapPublicIpOnLaunch=False,
            Tags=Tags(Name="private-az2"),
        )
    )

    # -----------------------
    # IGW + Route table publique
    # -----------------------

    igw = t.add_resource(
        InternetGateway(
            "InternetGateway",
            Tags=Tags(Name="polystudent-ec2-alarms-igw"),
        )
    )

    t.add_resource(
        VPCGatewayAttachment(
            "IgwAttachment",
            VpcId=Ref(vpc),
            InternetGatewayId=Ref(igw),
        )
    )

    public_rt = t.add_resource(
        RouteTable(
            "PublicRouteTable",
            VpcId=Ref(vpc),
            Tags=Tags(Name="public-rt"),
        )
    )

    t.add_resource(
        Route(
            "DefaultPublicRoute",
            RouteTableId=Ref(public_rt),
            DestinationCidrBlock="0.0.0.0/0",
            GatewayId=Ref(igw),
        )
    )

    t.add_resource(
        SubnetRouteTableAssociation(
            "PublicAz1RTA",
            RouteTableId=Ref(public_rt),
            SubnetId=Ref(public_subnet_az1),
        )
    )

    t.add_resource(
        SubnetRouteTableAssociation(
            "PublicAz2RTA",
            RouteTableId=Ref(public_rt),
            SubnetId=Ref(public_subnet_az2),
        )
    )

    # -----------------------
    # Security Group pour les instances
    # -----------------------

    sg_instances = t.add_resource(
        SecurityGroup(
            "InstanceSecurityGroup",
            GroupDescription="Security group pour instances EC2 (TP4)",
            VpcId=Ref(vpc),
            SecurityGroupIngress=[
                # SSH
                SecurityGroupRule(
                    IpProtocol="tcp",
                    FromPort=22,
                    ToPort=22,
                    CidrIp="0.0.0.0/0",
                ),
                # HTTP
                SecurityGroupRule(
                    IpProtocol="tcp",
                    FromPort=80,
                    ToPort=80,
                    CidrIp="0.0.0.0/0",
                ),
            ],
            SecurityGroupEgress=[
                SecurityGroupRule(
                    IpProtocol="-1",
                    FromPort=0,
                    ToPort=65535,
                    CidrIp="0.0.0.0/0",
                )
            ],
            Tags=Tags(Name="polystudent-ec2-sg"),
        )
    )

    # -----------------------
    # On RÉUTILISE l'InstanceProfile EXISTANT : "LabInstanceProfile"
    # -----------------------

    existing_instance_profile_name = "LabInstanceProfile"

    # -----------------------
    # Instances EC2 (2 publiques, 2 privées)
    # -----------------------

    # 1) Instance publique AZ1
    public_instance_az1 = t.add_resource(
        Instance(
            "PublicInstanceAz1",
            ImageId=Ref(ami_param),
            InstanceType=Ref(instance_type_param),
            KeyName=Ref(keyname_param),
            SubnetId=Ref(public_subnet_az1),
            SecurityGroupIds=[Ref(sg_instances)],
            IamInstanceProfile=existing_instance_profile_name,
            Tags=Tags(Name="public-instance-az1"),
        )
    )

    # 2) Instance publique AZ2
    public_instance_az2 = t.add_resource(
        Instance(
            "PublicInstanceAz2",
            ImageId=Ref(ami_param),
            InstanceType=Ref(instance_type_param),
            KeyName=Ref(keyname_param),
            SubnetId=Ref(public_subnet_az2),
            SecurityGroupIds=[Ref(sg_instances)],
            IamInstanceProfile=existing_instance_profile_name,
            Tags=Tags(Name="public-instance-az2"),
        )
    )

    # 3) Instance privée AZ1
    private_instance_az1 = t.add_resource(
        Instance(
            "PrivateInstanceAz1",
            ImageId=Ref(ami_param),
            InstanceType=Ref(instance_type_param),
            KeyName=Ref(keyname_param),
            SubnetId=Ref(private_subnet_az1),
            SecurityGroupIds=[Ref(sg_instances)],
            IamInstanceProfile=existing_instance_profile_name,
            Tags=Tags(Name="private-instance-az1"),
        )
    )

    # 4) Instance privée AZ2
    private_instance_az2 = t.add_resource(
        Instance(
            "PrivateInstanceAz2",
            ImageId=Ref(ami_param),
            InstanceType=Ref(instance_type_param),
            KeyName=Ref(keyname_param),
            SubnetId=Ref(private_subnet_az2),
            SecurityGroupIds=[Ref(sg_instances)],
            IamInstanceProfile=existing_instance_profile_name,
            Tags=Tags(Name="private-instance-az2"),
        )
    )

    # -----------------------
    # Alarmes CloudWatch NetworkPacketsIn (> 1000 pkts/s)
    # -----------------------

    def add_packets_in_alarm(logical_name, instance_ref, description_suffix):
        return t.add_resource(
            Alarm(
                logical_name,
                AlarmDescription=Sub(
                    "Alarm when NetworkPacketsIn > 1000 pkts/s on ${Desc}",
                    Desc=description_suffix,
                ),
                Namespace="AWS/EC2",
                MetricName="NetworkPacketsIn",
                Statistic="Average",
                Period=60,          # 60 secondes
                EvaluationPeriods=1,
                Threshold=1000,     # 1000 pkts/sec
                ComparisonOperator="GreaterThanThreshold",
                Dimensions=[
                    MetricDimension(
                        Name="InstanceId",
                        Value=Ref(instance_ref),
                    )
                ],
                TreatMissingData="notBreaching",
            )
        )

    add_packets_in_alarm(
        "AlarmPublicAz1PacketsIn",
        public_instance_az1,
        "public-instance-az1",
    )

    add_packets_in_alarm(
        "AlarmPublicAz2PacketsIn",
        public_instance_az2,
        "public-instance-az2",
    )

    add_packets_in_alarm(
        "AlarmPrivateAz1PacketsIn",
        private_instance_az1,
        "private-instance-az1",
    )

    add_packets_in_alarm(
        "AlarmPrivateAz2PacketsIn",
        private_instance_az2,
        "private-instance-az2",
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
                "PublicInstanceAz1Id",
                Description="Instance publique AZ1",
                Value=Ref(public_instance_az1),
            ),
            Output(
                "PublicInstanceAz2Id",
                Description="Instance publique AZ2",
                Value=Ref(public_instance_az2),
            ),
            Output(
                "PrivateInstanceAz1Id",
                Description="Instance privée AZ1",
                Value=Ref(private_instance_az1),
            ),
            Output(
                "PrivateInstanceAz2Id",
                Description="Instance privée AZ2",
                Value=Ref(private_instance_az2),
            ),
        ]
    )

    return t


def deploy_stack(template, stack_name="polystudent-ec2-alarms-stack"):
    """
    Déploie le template CloudFormation via boto3.
    """
    cf = boto3.client("cloudformation", region_name="us-east-1")

    template_body = template.to_yaml()

    # Sauvegarde IaC pour la preuve
    with open("ec2_alarms_template.yaml", "w", encoding="utf-8") as f:
        f.write(template_body)
    print("Template EC2 + alarmes générée dans ec2_alarms_template.yaml")

    # NOM DE TA KEYPAIR DANS AWS (sans .pem)
    keypair_name = "polystudent-pairs"

    try:
        print(f"Création du stack CloudFormation {stack_name}...")
        response = cf.create_stack(
            StackName=stack_name,
            TemplateBody=template_body,
            Parameters=[
                {
                    "ParameterKey": "KeyName",
                    "ParameterValue": keypair_name,
                }
            ],
            Capabilities=[
                "CAPABILITY_NAMED_IAM",
                "CAPABILITY_IAM",
            ],
        )
        print("Stack en cours de création, id :", response["StackId"])
        print(
            "Vérifie dans la console AWS → CloudFormation, EC2 (instances + IAM role via "
            "LabInstanceProfile) et CloudWatch (alarmes NetworkPacketsIn)."
        )

    except botocore.exceptions.ClientError as e:
        if "AlreadyExistsException" in str(e):
            print(
                f"Le stack {stack_name} existe déjà. "
                "Supprime-le dans CloudFormation ou change son nom."
            )
        else:
            raise


if __name__ == "__main__":
    template = build_template()
    deploy_stack(template)
