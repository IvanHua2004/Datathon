# Script de déploiement automatique sur AWS ECS
# Région : us-east-1 | Compte : 022499011766

Write-Host "=== 1. Connexion à Amazon ECR ===" -ForegroundColor Cyan
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 022499011766.dkr.ecr.us-east-1.amazonaws.com

Write-Host "=== 2. Construction de l'image unifiée (Angular + FastAPI) ===" -ForegroundColor Cyan
docker build -f Dockerfile.aws -t 022499011766.dkr.ecr.us-east-1.amazonaws.com/reglementdecomptes:v2 .

Write-Host "=== 3. Envoi de l'image sur ECR ===" -ForegroundColor Cyan
docker push 022499011766.dkr.ecr.us-east-1.amazonaws.com/reglementdecomptes:v2

Write-Host "=== 4. Enregistrement de la Task Definition Revision 8 ===" -ForegroundColor Cyan
python deploy_ecs.py

Write-Host "=== Déploiement terminé ! ===" -ForegroundColor Green
Write-Host "Vérifiez l'URL officielle : https://re-a7802df919724e0e835df4e1be537b1a.ecs.us-east-1.on.aws/" -ForegroundColor Green
