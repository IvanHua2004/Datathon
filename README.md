### 1. Le Pitch : Pourquoi c'est EXACTEMENT ce qu'ils demandent

L'énoncé de la page 9 propose explicitement deux pistes : un **« Agent d'explicabilité »** et un **« Agent de gouvernance »**. De plus, l'énoncé insiste sur la capacité de la solution à « remettre en question une demande incohérente » (le cas de Robert) et à vérifier que les contraintes sont respectées.

**Votre pitch au jury :**

> « Le problème avec les LLMs financiers classiques, c'est la complaisance (sycophancy) : l'IA a tendance à toujours donner raison à l'investisseur. Si Robert, 59 ans, demande 100 % de Bitcoin, un agent classique va souvent justifier cette erreur.
> Pour résoudre cela et répondre au critère d'auto-explicabilité, nous avons conçu **AlphaForge Council**. C'est une architecture agentique contradictoire. Au lieu d'avoir une boîte noire qui donne une réponse unique, nous séparons les cerveaux :
> 1. Un agent propose (le Promoteur).
> 2. Un agent critique en s'appuyant strictement sur les CSV de risque et le profil (la Gouvernance).
> 3. Un agent tranche et source la décision (l'Auditeur/Juge).
> 
> 
> En rendant ce débat visible dans l'interface Angular, l'utilisateur comprend *exactement* pourquoi une décision est prise, quelles données ont été utilisées, et quelles sont les limites. Nous répondons ainsi parfaitement à l'exigence d'encadrement responsable et de traçabilité du défi. »

### 2. Comment ça se connecte bien (L'Architecture Technique)

Puisque l'équipe gère Angular et que tu gères FastAPI/AWS, la connexion se fait par un flux continu (Streaming). Voici le cycle de vie exact d'une requête :

* **Étape 1 (Le Front-end) :** Sur l'interface Angular, l'utilisateur sélectionne son Persona (ex. Mateo) et tape sa requête : *« Je veux investir dans Exxon (XOM) et du Bitcoin (BTC-USD). »*
* **Étape 2 (L'Orchestrateur FastAPI) :** Le backend Python reçoit la requête. Il ne fait pas un simple appel LLM, il lance un workflow (ex. via LangGraph ou du code séquentiel Python).
* **Étape 3 (L'Agent Promoteur - AWS Bedrock) :** FastAPI envoie un prompt à Claude 3.5 via AWS : *« Donne des arguments pour cette requête »*. Claude répond (ex: potentiel de croissance). FastAPI commence à streamer cette réponse vers Angular.
* **Étape 4 (L'Agent Gouvernance - Python + Pandas + S3) :** En parallèle, FastAPI lit les données dans AWS S3. Un script Python pur voit que Mateo a un profil ESG strict et que `XOM` est bloqué, et calcule le risque du Bitcoin avec `prices_daily.csv`. Il génère le refus. FastAPI envoie cette alerte à Angular.
* **Étape 5 (L'Auditeur - AWS Bedrock) :** FastAPI prend la requête initiale, l'avis du Promoteur et le blocage quantitatif de la Gouvernance, et demande à l'Agent final de synthétiser. La réponse finale s'affiche sur Angular avec les citations des fichiers exacts.

La magie réside dans les **Server-Sent Events (SSE)** : Angular n'attend pas 15 secondes pour avoir un bloc de texte. Il voit les agents « réfléchir » et se répondre en direct.

### 3. Vos Livrables avec ce concept

L'énoncé exige 4 livrables précis. Voici comment votre concept les remplit de manière éclatante :

* **Prototype et code source**
* Un repo GitHub contenant votre backend (FastAPI orchestrant Bedrock et lisant les CSV) et le frontend (Angular affichant le chat contradictoire).
* Un fichier `README.md` expliquant comment lancer les agents localement ou sur le cloud.
