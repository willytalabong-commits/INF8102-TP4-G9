#!/usr/bin/env python3

import boto3
import botocore

from troposphere import (
    Template,
    Ref,
    Parameter,
    Output,
)
from troposphere.s3 import (
    Bucket,
    VersioningConfiguration,
    BucketEncryption,
    ServerSideEncryptionRule,
    ServerSideEncryptionByDefault,
)


def build_template():
    """
    Construit une template CloudFormation qui reproduit le bucket S3 polystudens3
    (Fig. 11) avec :
    - ACL privée
    - Versioning activé
    - Encryption SSE-KMS avec la clé polystudent-kms1
    - DeletionPolicy = Retain
    """
    t = Template()
    t.set_description(
        "TP4 - S3 bucket polystudents3-group9 reproduit en Python avec Troposphere "
        "(ACL private, SSE-KMS, versioning, deletion policy)."
    )

    # Paramètre pour l'ARN de la clé KMS polystudent-kms1
    kms_arn_param = t.add_parameter(
        Parameter(
            "KmsKeyArn",
            Type="String",
            Description="ARN de la clé KMS polystudent-kms1 utilisée pour chiffrer le bucket.",
        )
    )

    # Bucket S3 tel que montré dans la Fig. 11
    bucket = t.add_resource(
        Bucket(
            "Polystudents3Bucket",
            BucketName="polystudents3-group9",  # Nom du bucket pour le groupe 9
            AccessControl="Private",
            VersioningConfiguration=VersioningConfiguration(
                Status="Enabled"
            ),
            BucketEncryption=BucketEncryption(
                ServerSideEncryptionConfiguration=[
                    ServerSideEncryptionRule(
                        ServerSideEncryptionByDefault=ServerSideEncryptionByDefault(
                            SSEAlgorithm="aws:kms",
                            # ⚠️ Propriété correcte : KMSMasterKeyID (ID en majuscules)
                            KMSMasterKeyID=Ref(kms_arn_param),
                        )
                    )
                ]
            ),
        )
    )

    # Important : conserver les données même si le stack est supprimé
    bucket.DeletionPolicy = "Retain"

    # Outputs
    t.add_output(
        [
            Output(
                "BucketName",
                Description="Nom du bucket S3 créé",
                Value=Ref(bucket),
            ),
            Output(
                "KmsKeyArnUsed",
                Description="ARN de la clé KMS utilisée pour l'encryption",
                Value=Ref(kms_arn_param),
            ),
        ]
    )

    return t


def deploy_stack(template, stack_name="polystudents3-s3-stack"):
    """
    Déploie le template CloudFormation via boto3.
    """
    cf = boto3.client("cloudformation", region_name="us-east-1")

    template_body = template.to_yaml()

    # Sauvegarde locale pour preuve
    with open("s3_template.yaml", "w", encoding="utf-8") as f:
        f.write(template_body)
    print("Template S3 CloudFormation générée dans s3_template.yaml")

    # ARN réel de ta clé polystudent-kms1
    default_kms_arn = (
        "arn:aws:kms:us-east-1:411342274889:key/a39fe93a-6789-433f-80fe-ef2d26cbf21a"
    )

    try:
        print(f"Création du stack CloudFormation {stack_name}...")
        response = cf.create_stack(
            StackName=stack_name,
            TemplateBody=template_body,
            Parameters=[
                {
                    "ParameterKey": "KmsKeyArn",
                    "ParameterValue": default_kms_arn,
                }
            ],
            Capabilities=[
                "CAPABILITY_NAMED_IAM",
                "CAPABILITY_IAM",
            ],
        )
        print("Stack en cours de création, id :", response["StackId"])
        print(
            "Va dans la console AWS → CloudFormation pour vérifier l'état du stack "
            "et prendre des captures d'écran comme preuve pour le TP."
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
