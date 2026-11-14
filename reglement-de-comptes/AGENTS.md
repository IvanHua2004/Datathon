# Guide d'Intégration Frontend / UI — Discussion Vivante du Tribunal

> **Ce document est destiné à l'agent IA (Claude / GPT / Antigravity) chargé de concevoir ou d'ajuster l'interface utilisateur (UI/UX) pour la page du Tribunal.**

---

## 🎯 Objectif
L'utilisateur souhaite **ralentir le déroulement du procès** pour que l'audience se dévoile comme une **véritable discussion / débat contradictoire** entre :
1. **L'Avocat de la Défense** (`Me Vigor`)
2. **Le Greffier d'audience** (qui dépose les pièces et audite en temps réel les chiffres cités par chaque avocat)
3. **L'autre Avocat / Le Procureur** (`Me Austère`)
4. **Les Témoins experts** (l'Actuaire, la Cartographe, etc.)
5. **Le Président du Tribunal** (Le Juge qui délibère et prononce le verdict)

Le backend est **déjà prêt et configuré** pour fournir toute la séquence ordonnée des répliques.

---

## 📡 Données fournies par le Backend

### 1. Endpoint principal : `POST /api/proces`
L'objet JSON renvoyé par `/api/proces` contient désormais un champ direct :
```json
{
  "demande": { ... },
  "decision": { ... },
  "plaidoiries": [ ... ],
  "pieces": [ ... ],
  "courbe": [ ... ],
  "discussion": [ ... ]   <-- NOUVEAU : Séquence chronologique complète des répliques
}
```

### 2. Endpoint dédié (léger) : `POST /api/proces/discussion`
Renvoie uniquement le tableau `TourDiscussion[]` sans recharger les courbes SVG ni la salle.

### 3. Endpoint streaming (SSE) : `POST /api/proces/stream`
Si vous préférez le streaming Server-Sent Events côté client, cet endpoint émet chaque prise de parole avec `event: data` et gère un délai naturel `pause_ms`.

---

## 🧩 Modèle TypeScript (`TourDiscussion`)

Le modèle TypeScript est déjà exporté dans `frontend/src/app/models/proces.model.ts` :

```typescript
export interface TourDiscussion {
  ordre: number;            // 1, 2, 3... ordre chronologique de passage
  etape: string;            // 'HUISSIER_OUVERTURE', 'GREFFIER_DEPOT', 'TEMOIN', 'PLAIDOIRIE_DEFENSE', 
                            // 'AUDIT_GREFFIER_DEFENSE', 'REQUISITOIRE_PROCUREUR', 'AUDIT_GREFFIER_PROCUREUR', 'VERDICT_JUGE'
  acteur: string;           // Ex: "Me Vigor (La Défense)", "Le Greffier d'audience", "Me Austère (Le Procureur)"
  role: 'huissier' | 'greffier' | 'avocat_defense' | 'procureur' | 'temoin' | 'juge' | string;
  avatar: string;           // Émoji recommandé (📢, 📜, 💼, 🛡️, ⚖️, 👨‍⚖️, 📊, 🧭)
  titre: string;            // Titre de l'intervention (ex: "Plaidoirie en faveur de la demande")
  texte: string;            // Le discours / dialogue complet à afficher
  pause_ms: number;         // Temps de pause recommandé avant la réplique suivante (ex: 2000 à 4000 ms)
  statut?: 'valide' | 'alerte' | string; // Pour le Greffier : alerte si des chiffres sont non vérifiés
  non_verifies?: string[];  // Liste des chiffres cités qui ne figurent pas dans les pièces
  pieces_associees?: string[]; // Ex: ["P-01", "P-02"]
  piece?: string;           // Pour un témoin spécifique (ex: "P-01")
  temoin?: string;          // Ex: "risque", "diversification", "valeurs", "macro"
  verdict?: Verdict;        // Disponible sur le tour du Juge
  convoques?: string[];     // Témoins convoqués par l'avocat
}
```

---

## 🎬 Déroulé Chronologique du Débat (`discussion`)

| Ordre | Acteur | Rôle | Avatar | Description |
| :---: | :--- | :--- | :---: | :--- |
| **1** | **L'Huissier** | `huissier` | 📢 | Ouverture solennelle de l'audience et appel de l'investisseur. |
| **2** | **Le Greffier** | `greffier` | 📜 | Dépôt et enregistrement des pièces à conviction (`[P-01]`, `[P-02]`, etc.). |
| **3** | **Témoin(s)** | `temoin` | 📊 / 🧭 | Déposition sous serment des experts (Dr Laurent Actuaire, Mme Chantal, etc.). |
| **4** | **Avocat Défense** | `avocat_defense` | 💼 | **Me Vigor** plaide en faveur du projet d'investissement. |
| **5** | **Le Greffier** | `greffier` | ⚖️ | **Audit factuel de la défense** : vérifie si Me Vigor a inventé des chiffres ou s'il s'appuie sur les pièces scellées. |
| **6** | **Le Procureur** | `procureur` | 🛡️ | **Me Austère** attaque le projet sur les contraintes, pertes et volatilité. |
| **7** | **Le Greffier** | `greffier` | ⚖️ | **Audit factuel du procureur** : vérifie la conformité des arguments de l'accusation. |
| **8** | **Le Juge** | `juge` | 👨‍⚖️ | **Verdict et délibéré** : prononce la décision officielle et les motifs. |

---

## 💡 Exemple d'Intégration UI Recommandée (Angular)

### 1. Dans `tribunal.page.ts`
Quand `ouvrirProces()` réussit :
```typescript
readonly discussionActive = signal<boolean>(false);
readonly toursAffiches = signal<TourDiscussion[]>([]);
private timerDiscussion?: any;

// Appeler cette méthode dès la réception de `proces` :
demarrerAnimationDiscussion(tours: TourDiscussion[]): void {
  if (!tours || tours.length === 0) return;
  
  this.discussionActive.set(true);
  this.toursAffiches.set([]);
  let index = 0;

  const jouerProchainTour = () => {
    if (index < tours.length) {
      this.toursAffiches.update(liste => [...liste, tours[index]]);
      const pause = tours[index].pause_ms || 2500;
      index++;
      this.timerDiscussion = setTimeout(jouerProchainTour, pause);
    } else {
      this.discussionActive.set(false); // Fin de la discussion : on peut afficher le reste des graphiques/décisions
    }
  };

  jouerProchainTour();
}

passerAnimation(tousLesTours: TourDiscussion[]): void {
  if (this.timerDiscussion) {
    clearTimeout(this.timerDiscussion);
  }
  this.toursAffiches.set(tousLesTours);
  this.discussionActive.set(false);
}
```

### 2. Dans `tribunal.page.html`
Afficher les messages sous forme de bulles de chat / fil de discussion avec :
- Une bulle distincte par personnage (ex: alignement à gauche pour la Défense, à droite pour le Procureur, centré pour le Greffier/Juge).
- Un badge ou avatar (`msg.avatar`).
- Si `msg.statut === 'alerte'`, mettre le message du Greffier en rouge/orange pour signaler l'infraction.
- Un bouton **"⏩ Passer l'audience"** pour les utilisateurs pressés ou en phase de test.
- Dès que le juge a parlé, afficher la suite (arbitrage OUI/NON, graphique de la courbe de perte, etc.).

---

## 🚀 État du Code Backend
- ✅ `backend/rdc/proces.py` : fonction `construire_timeline_discussion(proces)` ajoutée.
- ✅ `backend/api.py` : champ `discussion` ajouté à `POST /api/proces`.
- ✅ `backend/api.py` : endpoints `POST /api/proces/discussion` et `POST /api/proces/stream` disponibles.
- ✅ `frontend/src/app/models/proces.model.ts` : interface `TourDiscussion` et type `discussion?: TourDiscussion[]` ajoutés.
- ✅ `frontend/src/app/services/api.service.ts` : méthode `discussionProces(...)` disponible.
