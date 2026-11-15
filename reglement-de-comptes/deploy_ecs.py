import os
import json
import subprocess
from pathlib import Path

# 1. Charger les variables d'environnement locales (.env si présent, sinon environnement système)
env_file = Path(__file__).resolve().parent / ".env"
env_vars = {}
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env_vars[k.strip()] = v.strip().strip('"').strip("'")
            if k.strip() not in os.environ:
                os.environ[k.strip()] = env_vars[k.strip()]

def get_val(key, default=""):
    return os.environ.get(key) or env_vars.get(key) or default

def run(cmd):
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("Erreur:", res.stderr)
    return res.stdout, res.returncode

# Préparer les variables pour le conteneur ECS (serveur uniquement)
# Seul le backend Python y a accès dans le conteneur, jamais le navigateur client.
container_env = [
    {"name": "AWS_REGION", "value": get_val("AWS_REGION", "us-east-1")},
    {"name": "BEDROCK_MODEL_ID", "value": get_val("BEDROCK_MODEL_ID", "global.anthropic.claude-sonnet-5")},
    {"name": "RDC_S3_BUCKET", "value": get_val("RDC_S3_BUCKET", "")},
    {"name": "RDC_S3_PREFIX", "value": get_val("RDC_S3_PREFIX", "alphaforge/")},
]

# Si des clés de session sont présentes, on les transmet au conteneur de façon sécurisée
for key in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"]:
    val = get_val(key)
    if val:
        container_env.append({"name": key, "value": val})

image_uri = get_val("IMAGE_URI", "022499011766.dkr.ecr.us-east-1.amazonaws.com/reglementdecomptes:v2")

new_task_def = {
    "family": "default-reglementdecomptes-238e",
    "executionRoleArn": "arn:aws:iam::022499011766:role/ecsTaskExecutionRole",
    "networkMode": "awsvpc",
    "requiresCompatibilities": ["FARGATE"],
    "cpu": "1024",
    "memory": "2048",
    "containerDefinitions": [
        {
            "name": "Main",
            "image": image_uri,
            "cpu": 1024,
            "memory": 2048,
            "memoryReservation": 2048,
            "portMappings": [
                {
                    "containerPort": 8501,
                    "hostPort": 8501,
                    "protocol": "tcp",
                    "name": "main-8501-tcp"
                }
            ],
            "essential": True,
            "environment": container_env,
            "healthCheck": {
                "command": [
                    "CMD-SHELL",
                    "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8501/api/sante')\" || exit 1"
                ],
                "interval": 30,
                "timeout": 5,
                "retries": 3,
                "startPeriod": 30
            },
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": "/aws/ecs/default/reglementdecomptes-238e-83d2",
                    "awslogs-region": "us-east-1",
                    "awslogs-stream-prefix": "ecs"
                }
            }
        }
    ]
}

# 2. Enregistrer la Task Definition
tmp_json = Path(__file__).resolve().parent / "task_def_rev8.json"
try:
    tmp_json.write_text(json.dumps(new_task_def, indent=2), encoding="utf-8")

    print("Enregistrement de la nouvelle Task Definition...")
    out, code = run([
        "aws", "ecs", "register-task-definition",
        "--cli-input-json", f"file://{tmp_json}",
        "--region", "us-east-1"
    ])
    if code != 0:
        print("Échec de l'enregistrement de la Task Definition.")
        import sys
        sys.exit(1)

    res = json.loads(out)["taskDefinition"]
    rev = res["revision"]
    print(f"Task Definition enregistrée avec succès : Révision {rev}")

    # 3. Mettre à jour le service ECS
    print("Mise à jour du service ECS default/reglementdecomptes-238e...")
    out, code = run([
        "aws", "ecs", "update-service",
        "--cluster", "default",
        "--service", "reglementdecomptes-238e",
        "--task-definition", f"default-reglementdecomptes-238e:{rev}",
        "--force-new-deployment",
        "--region", "us-east-1"
    ])
    if code == 0:
        print(f"Service ECS mis à jour avec succès vers la révision {rev} !")
        print("Déploiement en cours...")
    else:
        print("Erreur lors de la mise à jour du service ECS.")
        import sys
        sys.exit(1)
finally:
    if tmp_json.exists():
        tmp_json.unlink()
