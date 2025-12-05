#!/usr/bin/env python3
import json

import boto3
import botocore


REGION = "us-east-1"
SOURCE_BUCKET = "polystudents3-group9"
DEST_BUCKET = "polystudents3-back-group9"
REPLICATION_ROLE_NAME = "polystudents3-replication-role-group9"
TRAIL_NAME = "polystudents3-trail-group9"


def get_account_id():
    sts = boto3.client("sts", region_name=REGION)
    return sts.get_caller_identity()["Account"]


def ensure_bucket_exists_and_versioning(bucket_name):
    """
    Vérifie si le bucket existe, sinon le crée, puis active le versioning.
    Attention : en us-east-1, il ne faut PAS mettre CreateBucketConfiguration.
    """
    s3 = boto3.client("s3", region_name=REGION)

    # 1) Vérifier l'existence du bucket
    try:
        s3.head_bucket(Bucket=bucket_name)
        print(f"Bucket {bucket_name} existe déjà.")
    except botocore.exceptions.ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code in ("404", "NoSuchBucket", "NotFound"):
            print(f"Création du bucket {bucket_name} ...")
            if REGION == "us-east-1":
                # Cas particulier : us-east-1 -> pas de LocationConstraint
                s3.create_bucket(Bucket=bucket_name)
            else:
                s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": REGION},
                )
        else:
            # Autre erreur (droits, etc.) -> on lève
            raise

    # 2) Activer le versioning
    print(f"Activation du versioning sur {bucket_name} ...")
    s3.put_bucket_versioning(
        Bucket=bucket_name,
        VersioningConfiguration={"Status": "Enabled"},
    )


def ensure_replication_role(account_id):
    """
    Crée (ou récupère) un rôle IAM assumable par S3, avec les permissions
    nécessaires pour répliquer les objets du bucket source vers le bucket
    destination.
    """
    iam = boto3.client("iam", region_name=REGION)

    assume_role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "s3.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }

    try:
        print(f"Création du rôle IAM {REPLICATION_ROLE_NAME} ...")
        role = iam.create_role(
            RoleName=REPLICATION_ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(assume_role_policy),
            Description=(
                "Role de réplication S3 pour "
                "polystudents3-group9 -> polystudents3-back-group9"
            ),
        )
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            print(
                f"Rôle {REPLICATION_ROLE_NAME} existe déjà, "
                "récupération de l'ARN ..."
            )
            role = iam.get_role(RoleName=REPLICATION_ROLE_NAME)
        else:
            raise

    role_arn = role["Role"]["Arn"]

    # Policy inline pour la réplication
    replication_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowS3ReplicationSourceActions",
                "Effect": "Allow",
                "Action": [
                    "s3:GetReplicationConfiguration",
                    "s3:ListBucket",
                    "s3:GetObjectVersion",
                    "s3:GetObjectVersionAcl",
                    "s3:GetObjectVersionTagging",
                ],
                "Resource": [
                    f"arn:aws:s3:::{SOURCE_BUCKET}",
                    f"arn:aws:s3:::{SOURCE_BUCKET}/*",
                ],
            },
            {
                "Sid": "AllowS3ReplicationDestinationActions",
                "Effect": "Allow",
                "Action": [
                    "s3:ReplicateObject",
                    "s3:ReplicateDelete",
                    "s3:ReplicateTags",
                    "s3:GetObjectVersionTagging",
                    "s3:PutObjectAcl",
                ],
                "Resource": [
                    f"arn:aws:s3:::{DEST_BUCKET}/*",
                ],
            },
        ],
    }

    print(
        f"Attachement de la policy de réplication au rôle "
        f"{REPLICATION_ROLE_NAME} ..."
    )
    iam.put_role_policy(
        RoleName=REPLICATION_ROLE_NAME,
        PolicyName="polystudents3ReplicationPolicy",
        PolicyDocument=json.dumps(replication_policy),
    )

    return role_arn


def configure_bucket_replication(role_arn):
    """
    Configure la réplication sur le bucket source vers le bucket de backup.
    """
    s3 = boto3.client("s3", region_name=REGION)

    replication_config = {
        "Role": role_arn,
        "Rules": [
            {
                "ID": "ReplicateAllObjectsToBackupBucket",
                "Status": "Enabled",
                "Prefix": "",  # Tous les objets
                "Destination": {
                    "Bucket": f"arn:aws:s3:::{DEST_BUCKET}",
                    # On pourrait ajouter "StorageClass": "STANDARD_IA" etc.
                },
            }
        ],
    }

    print(
        f"Configuration de la réplication sur le bucket source {SOURCE_BUCKET} "
        f"vers {DEST_BUCKET} ..."
    )
    s3.put_bucket_replication(
        Bucket=SOURCE_BUCKET,
        ReplicationConfiguration=replication_config,
    )
    print("Réplication configurée.")


def ensure_cloudtrail_bucket_policy(bucket_name, account_id):
    """
    Applique la bucket policy minimale recommandée pour CloudTrail :
    - cloudtrail.amazonaws.com peut faire GetBucketAcl sur le bucket
    - cloudtrail.amazonaws.com peut PutObject sous AWSLogs/<account-id>/*
      avec l'ACL bucket-owner-full-control.
    """
    s3 = boto3.client("s3", region_name=REGION)

    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AWSCloudTrailAclCheck20150319",
                "Effect": "Allow",
                "Principal": {"Service": "cloudtrail.amazonaws.com"},
                "Action": "s3:GetBucketAcl",
                "Resource": f"arn:aws:s3:::{bucket_name}",
            },
            {
                "Sid": "AWSCloudTrailWrite20150319",
                "Effect": "Allow",
                "Principal": {"Service": "cloudtrail.amazonaws.com"},
                "Action": "s3:PutObject",
                "Resource": (
                    f"arn:aws:s3:::{bucket_name}/AWSLogs/{account_id}/*"
                ),
                "Condition": {
                    "StringEquals": {
                        "s3:x-amz-acl": "bucket-owner-full-control"
                    }
                },
            },
        ],
    }

    print(f"Application de la bucket policy CloudTrail sur {bucket_name} ...")
    s3.put_bucket_policy(
        Bucket=bucket_name,
        Policy=json.dumps(policy),
    )
    print("Bucket policy CloudTrail appliquée.")


def ensure_cloudtrail_for_bucket(account_id):
    """
    Crée (ou réutilise) un trail CloudTrail qui journalise
    les opérations d'écriture (Put/Delete) sur les objets du bucket source.
    Les logs CloudTrail sont envoyés dans le bucket de backup.
    """
    cloudtrail = boto3.client("cloudtrail", region_name=REGION)

    trail_bucket_name = DEST_BUCKET  # simple pour le TP

    # 1) S'assurer que la bucket policy CloudTrail est en place
    ensure_cloudtrail_bucket_policy(trail_bucket_name, account_id)

    # 2) Créer le trail s'il n'existe pas
    try:
        print(f"Création du trail CloudTrail {TRAIL_NAME} ...")
        cloudtrail.create_trail(
            Name=TRAIL_NAME,
            S3BucketName=trail_bucket_name,
            IsMultiRegionTrail=False,
            IncludeGlobalServiceEvents=False,
        )
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "TrailAlreadyExistsException":
            print(f"Le trail {TRAIL_NAME} existe déjà, on le réutilise.")
        else:
            raise

    # 3) Configurer les data events S3 pour logguer les écritures
    print(
        "Configuration des data events CloudTrail pour journaliser les "
        "écritures (Put/Delete) sur les objets de polystudents3-group9 ..."
    )

    cloudtrail.put_event_selectors(
        TrailName=TRAIL_NAME,
        EventSelectors=[
            {
                "ReadWriteType": "WriteOnly",  # Modifications / suppressions
                "IncludeManagementEvents": False,
                "DataResources": [
                    {
                        "Type": "AWS::S3::Object",
                        "Values": [
                            f"arn:aws:s3:::{SOURCE_BUCKET}/",
                        ],
                    }
                ],
            }
        ],
    )

    # 4) Démarrer le logging
    print("Démarrage du logging CloudTrail ...")
    cloudtrail.start_logging(Name=TRAIL_NAME)
    print("CloudTrail est maintenant actif pour le bucket source.")


def main():
    print("=== Déploiement réplication S3 + CloudTrail pour polystudents3-group9 ===")
    account_id = get_account_id()
    print(f"Compte AWS détecté : {account_id}")

    # (1) S'assurer que les deux buckets existent et ont le versioning activé
    ensure_bucket_exists_and_versioning(SOURCE_BUCKET)
    ensure_bucket_exists_and_versioning(DEST_BUCKET)

    # (2) Créer / mettre à jour le rôle de réplication
    role_arn = ensure_replication_role(account_id)

    # (3) Configurer la réplication du bucket source vers le bucket destination
    configure_bucket_replication(role_arn)

    # (4) Configurer CloudTrail pour journaliser les opérations objets S3
    ensure_cloudtrail_for_bucket(account_id)

    print(
        "=== Déploiement terminé. "
        "Vérifie S3 (Replication), le bucket de backup et CloudTrail (Trails & Event history). ==="
    )


if __name__ == "__main__":
    main()
