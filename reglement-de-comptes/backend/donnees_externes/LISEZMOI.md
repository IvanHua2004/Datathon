# Données externes ajoutées par l'équipe

Le jeu de départ ne contient aucune donnée ESG. Ce dossier reçoit les preuves que
l'équipe collecte à la main dans des documents publics (rapports de durabilité,
SEDAR+, SEC EDGAR, méthodologie d'ESGV chez Vanguard).

## `esg_preuves.csv` : une ligne par fait

| Colonne | Contenu |
| --- | --- |
| `ticker` | Titre concerné, écrit comme dans `assets_universe.csv` (ex. `ENB.TO`) |
| `type` | `exclusion` (contraire aux valeurs déclarées), `vigilance` (à examiner) ou `favorable` |
| `fait` | Le fait, en une phrase neutre |
| `nature` | `fait_etabli` (jugement, sanction, chiffre déclaré) ou `allegation` |
| `source` | Nom du document |
| `url` | Lien direct |
| `date_document` | Date du document (AAAA-MM-JJ) |
| `extrait` | Courte citation, moins de 15 mots, avec la page si possible |
| `collecte_par` | Membre de l'équipe |
| `date_collecte` | Date de la collecte (AAAA-MM-JJ) |

Le fichier est livré VIDE volontairement : le témoin des valeurs répond alors
« aucune preuve dans nos sources », et le juge le signale comme information manquante.
N'inscrivez que des faits que vous avez lus vous-mêmes dans la source.
