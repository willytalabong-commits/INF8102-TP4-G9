🧩 1. Description générale du TP

Ce projet consiste à reproduire et sécuriser l’infrastructure AWS créée dans le TP3, en utilisant exclusivement une approche Infrastructure as Code (IaC) avec :

Troposphere

Boto3

CloudFormation

Trivy

jq

Git/GitHub pour le versionnement professionnel

L’objectif est :

d’automatiser complètement le déploiement,

d’appliquer les bonnes pratiques DevSecOps,

d’assurer la reproductibilité,

d’analyser les vulnérabilités du code IaC.

L’infrastructure déployée inclut :

une VPC complète (4 subnets, IGW, 2 NAT GW, routes, SG),

un bucket S3 sécurisé (KMS, versioning, deletion policy),

des Flow Logs REJECT vers S3,

4 instances EC2 + rôle IAM + CloudWatch alarms,

une réplication S3 + CloudTrail Data Events,

un scan de sécurité complet du IaC.

📁 2. Structure du dépôt
INF8102-TP4-G9/
├── iac/
│   ├── vpc/
│   │   ├── deploiement_vpc_iac.py
│   │   └── vpc_template.yaml
│   ├── vpc_flowlogs/
│   │   ├── deploiement_vpc_flowlogs_iac.py
│   │   └── vpc_flowlogs_template.yaml
│   ├── s3/
│   │   ├── deploiement_s3_iac.py
│   │   └── s3_template.yaml
│   ├── s3_replication_cloudtrail/
│   │   └── deploiement_s3_replication_cloudtrail.py
│   └── ec2_alarms/
│       ├── deploiement_ec2_alarms_iac.py
│       └── ec2_alarms_template.yaml
├── scans/
│   ├── trivy_report.json
│   └── cve.json
├── polylab/
│   ├── vpc_template.yaml
│   ├── s3_template.yaml
│   ├── vpc_flowlogs_template.yaml
│   └── ec2_alarms_template.yaml
├── docs/
│   ├── captures_vpc_*.png
│   ├── captures_s3_*.png
│   ├── captures_flowlogs_*.png
│   ├── captures_ec2_*.png
│   ├── captures_cloudtrail_*.png
│   └── Rapport_TP4.pdf
├── README.md
└── .gitignore

🚀 3. Déploiement de l’infrastructure (scripts IaC)
🔧 3.1 Prérequis
pip install boto3 troposphere
aws configure  # compte étudiant Poly

🌐 3.2 Déployer la VPC
cd iac/vpc
python deploiement_vpc_iac.py


Ce script :

génère vpc_template.yaml

crée la VPC via CloudFormation

🧱 3.3 Déployer le bucket S3 sécurisé
cd iac/s3
python deploiement_s3_iac.py


Fonctionnalités :
✔ SSE-KMS
✔ Versioning
✔ ACL private
✔ DeletionPolicy = Retain

📡 3.4 Déployer les VPC Flow Logs
cd iac/vpc_flowlogs
python deploiement_vpc_flowlogs_iac.py


Fonctionnalités :
✔ TrafficType = REJECT
✔ Destination = S3

💻 3.5 Déployer les 4 EC2 + alarmes CloudWatch
cd iac/ec2_alarms
python deploiement_ec2_alarms_iac.py


Fonctionnalités :
✔ 2 EC2 publiques
✔ 2 EC2 privées
✔ IAM InstanceProfile = LabInstanceProfile
✔ 4 alarmes NetworkPacketsIn

🔁 3.6 Réplication S3 + CloudTrail Data Events
cd iac/s3_replication_cloudtrail
python deploiement_s3_replication_cloudtrail.py


Fonctionnalités :
✔ 2 buckets versionnés
✔ rôle IAM de réplication
✔ CloudTrail activé sur opérations S3 (Put/Delete)

🛡️ 4. Analyse de sécurité du IaC avec Trivy
📌 4.1 Scanner le IaC

Créer un dossier polylab/ contenant les templates YAML.

Lancer le scan :

trivy fs \
  --security-checks vuln,secret,config \
  --severity MEDIUM,HIGH,CRITICAL \
  -f json \
  -o scans/trivy_report.json \
  polylab/

📌 4.2 Extraire les vulnérabilités HIGH avec jq
jq '
  .Results[]? 
  | .Vulnerabilities? // [] 
  | map(select(.Severity == "HIGH")) 
  | map({
      ID: .VulnerabilityID,
      Title: .Title,
      Description: .Description,
      Severity: .Severity,
      CVSSv3: (.CVSS? | to_entries[]?.value?.V3Vector // null)
  })
' scans/trivy_report.json > scans/cve.json

📌 4.3 Mesures de sécurité recommandées

Limiter l’exposition réseau (réduire les CIDR 0.0.0.0/0).

Activer des linters IaC (cfn-lint, checkov, trivy-config).

Utiliser des paramètres IAM minimaux (principle of least privilege).

Externaliser les secrets dans AWS SSM (pas dans le code).

Activer CloudFormation Drift Detection.

📝 5. Preuves

Dans le dossier docs/, toutes les captures exigées sont présentes :

création des stacks CloudFormation

Flow Logs dans VPC

CloudWatch alarms

CloudTrail Data Events

Scan Trivy + cve.json

🔐 6. Sécurité

Un fichier .gitignore a été ajouté pour éviter de publier des clés privées, des caches Python, ou des fichiers sensibles.

🎉 7. Auteur

Projet réalisé par Willy Talabong,
Cours INF8102 – Sécurité Cloud, Polytechnique Montréal.