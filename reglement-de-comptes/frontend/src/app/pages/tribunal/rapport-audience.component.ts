import { Component, computed, input } from '@angular/core';

import { CourbeTailleComponent } from '../../components/courbe-taille/courbe-taille.component';
import { Piece, PointCourbe, Position, Proces, TourDiscussion } from '../../models/proces.model';
import { dollars, pct, tonVerdict } from '../../shared/format';

type Camp = 'avocat_defense' | 'procureur';

export interface InterventionLue {
  tour: TourDiscussion;
  extrait: string;
  complet: boolean;
}

const PHRASES = new Intl.Segmenter('fr', { granularity: 'sentence' });

/**
 * Les phrases d'une plaidoirie qui portent un argument : celles qui citent un chiffre ou
 * une pièce passent avant les formules d'audience (« Monsieur le Président… »).
 * Le texte n'est pas réécrit, seulement sélectionné, dans l'ordre d'origine.
 */
export function argumentsDe(texte: string, n: number): string[] {
  const phrases = Array.from(PHRASES.segment(texte)).map(({ segment }) => segment.trim()).filter((s) => s.length > 25);
  const fortes = phrases.filter((s) => /\d|\[P-\d+\]/.test(s));
  const choisies = new Set((fortes.length >= n ? fortes : [...fortes, ...phrases.filter((s) => !fortes.includes(s))]).slice(0, n));
  return phrases.filter((s) => choisies.has(s));
}

/** Pire baisse, part du risque… avant et après la demande, lus sur la courbe du procès. */
export function chiffresCles(pr: Proces | null) {
  if (!pr?.courbe.length) return null;
  const avant = pointPour(pr.courbe, 0)!;
  const apres = pointPour(pr.courbe, pr.demande.taille)!;
  // budgetPerte arrive déjà en négatif depuis l'API (ex. -0,12).
  return { avant, apres, depasse: apres.pireBaisse < pr.budgetPerte };
}

/** Le point de la courbe le plus proche d'une part donnée. */
function pointPour(courbe: readonly PointCourbe[], taille: number): PointCourbe | undefined {
  return [...courbe].sort((a, b) => Math.abs(a.taille - taille) - Math.abs(b.taille - taille))[0];
}

/**
 * Le rapport d'analyse de l'audience, organisé autour des 4 questions d'une explication
 * crédible : quelle conclusion et pourquoi, sur quelles données, avec quelles limites,
 * et qu'est-ce qui changerait la réponse. Tout vient de la réponse de l'API : aucun chiffre
 * n'est recalculé ici, sauf le portefeuille après ajout (simple règle de trois).
 */
@Component({
  selector: 'rdc-rapport-audience',
  imports: [CourbeTailleComponent],
  styleUrl: './rapport-audience.component.css',
  template: `
    @if (proces(); as pr) {
      <div class="rapport-imprimable">
        @if (!audienceTerminee()) {
          <p class="bandeau-encours" role="status">
            Audience en cours : la synthèse est déjà disponible, la transcription se complète au fil des interventions.
          </p>
        }

        <!-- A. La synthèse (la décision du tribunal reste scellée tant que l'investisseur n'a pas voté) -->
        @if (masquerDecision()) {
          <section class="synthese synthese--scellee" aria-labelledby="r-verdict">
            <p class="sur-titre">Verdict du tribunal · règle fixe</p>
            <h3 id="r-verdict" class="verdict">Révélé après votre vote</h3>
            <p class="question">{{ pr.demande.nom }} · {{ pct(pr.demande.taille, 0) }} du portefeuille dans
              {{ pr.demande.nomTitre }} ({{ pr.demande.ticker }}), soit {{ dollars(pr.demande.capital * pr.demande.taille) }}</p>
            <p class="motif-unique">Pour ne pas vous influencer, la décision du tribunal et ce qui la ferait changer
              s’affichent dès que vous avez rendu votre verdict.</p>
          </section>
        } @else {
        <section class="synthese" [attr.data-ton]="ton()" aria-labelledby="r-verdict">
          <p class="sur-titre">Verdict du tribunal · règle fixe</p>
          <h3 id="r-verdict" class="verdict">{{ pr.decision.verdict }}</h3>
          <p class="question">{{ pr.demande.nom }} · {{ pct(pr.demande.taille, 0) }} du portefeuille dans
            {{ pr.demande.nomTitre }} ({{ pr.demande.ticker }}), soit {{ dollars(pr.demande.capital * pr.demande.taille) }}</p>
          @if (motifs().length) {
            <ul class="motifs">
              @for (m of motifs(); track $index) { <li>{{ m }}</li> }
            </ul>
          } @else {
            <p class="motif-unique">La demande respecte les contraintes déclarées et ne crée pas de tension notable avec le profil.</p>
          }
        </section>
        }

        @if (vote(); as v) {
          <p class="vote" [class.accord]="accord()" [class.desaccord]="accord() === false">
            <strong>Votre verdict :</strong> vous avez suivi {{ v === 'avocat_defense' ? 'la défense (pour la demande)' : 'l’accusation (contre la demande)' }}.
            @if (accord() === true) { Le tribunal arrive à la même conclusion. }
            @else if (accord() === false) { Le tribunal arrive à la conclusion inverse : relisez les motifs ci-dessus. }
            @else { Le tribunal ne tranche pas : une information manque. }
          </p>
        } @else if (!pendantLeVote() && !horsAudience()) {
          <p class="vote vote--attente">Vous n’avez pas encore rendu votre verdict : « Terminer », puis « Passer au verdict ».</p>
        }

        @if (chiffres(); as c) {
          <div class="tuiles" role="list" aria-label="Chiffres clés">
            <div class="tuile" role="listitem" [class.alerte]="c.depasse">
              <span class="libelle">Pire baisse du portefeuille</span>
              <span class="valeur">{{ pct(c.avant.pireBaisse) }} → <strong>{{ pct(c.apres.pireBaisse) }}</strong></span>
              <span class="aide">budget déclaré : {{ pct(pr.budgetPerte, 0) }}{{ c.depasse ? ' · dépassé' : ' · respecté' }}</span>
            </div>
            <div class="tuile" role="listitem" [class.alerte]="c.depasse">
              <span class="libelle">Perte au pire moment</span>
              <span class="valeur"><strong>{{ dollars(c.apres.pireBaisse * pr.demande.capital) }}</strong></span>
              <span class="aide">budget : {{ dollars(pr.budgetPerte * pr.demande.capital) }}</span>
            </div>
            <div class="tuile" role="listitem" [class.alerte]="c.apres.partDuRisque > 0.25">
              <span class="libelle">Part du risque due à {{ pr.demande.ticker }}</span>
              <span class="valeur"><strong>{{ pct(c.apres.partDuRisque, 0) }}</strong></span>
              <span class="aide">pour {{ pct(pr.demande.taille, 0) }} du portefeuille</span>
            </div>
            <div class="tuile" role="listitem">
              <span class="libelle">Mauvaise année (1 sur 20)</span>
              <span class="valeur">{{ pct(c.avant.defavorable12Mois) }} → <strong>{{ pct(c.apres.defavorable12Mois) }}</strong></span>
              <span class="aide">sur 12 mois, observé</span>
            </div>
          </div>
        }

        <!-- C. Ce qui changerait le verdict -->
        @if (pr.salle.length && !masquerDecision()) {
          <section aria-labelledby="r-salle">
            <h3 id="r-salle">Qu’est-ce qui changerait le verdict ?</h3>
            <table class="salle">
              <thead><tr><th scope="col">Si…</th><th scope="col">Verdict</th><th scope="col">Change ?</th></tr></thead>
              <tbody>
                @for (h of pr.salle; track h.hypothese) {
                  <tr [class.change]="h.change">
                    <th scope="row">{{ h.hypothese }}</th>
                    <td><span class="pastille" [attr.data-ton]="tonVerdict(h.verdict)">{{ h.verdict }}</span></td>
                    <td>{{ h.change ? 'Oui' : 'Non' }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </section>
        }

        <!-- B. Le visuel -->
        <section aria-labelledby="r-visuel">
          <h3 id="r-visuel">Où la limite est-elle franchie ?</h3>
          <p class="note">Pire baisse observée du portefeuille selon la part placée dans {{ pr.demande.ticker }}
            ({{ pr.periode.debut }} au {{ pr.periode.fin }}). Le passé observé, pas une prévision.</p>
          <rdc-courbe-taille [courbe]="pr.courbe" [budget]="pr.budgetPerte" [tailleDemandee]="pr.demande.taille"
            [ticker]="pr.demande.ticker" />
          @if (portefeuilles(); as pf) {
            <div class="portefeuilles">
              @for (ligne of pf; track ligne.nom) {
                <div class="portefeuille">
                  <span class="libelle">{{ ligne.nom }}</span>
                  <div class="barre" role="img" [attr.aria-label]="ligne.description">
                    @for (x of ligne.positions; track x.ticker; let i = $index) {
                      <span [style.flex-basis.%]="x.poids * 100" [attr.data-i]="x.ticker === pr.demande.ticker ? 'demande' : i % 6"
                        [title]="x.ticker + ' · ' + pct(x.poids, 0)"></span>
                    }
                  </div>
                </div>
              }
              <p class="legende"><span class="carre" data-i="demande"></span> {{ pr.demande.ticker }}, le titre demandé ;
                les autres couleurs sont les positions actuelles, réduites à proportion.</p>
            </div>
          }
        </section>

        <!-- D. Le débat résumé -->
        <section aria-labelledby="r-debat">
          <h3 id="r-debat">Le débat en bref</h3>
          <div class="camps">
            @for (camp of camps(); track camp.titre) {
              <article class="camp" [attr.data-camp]="camp.cle">
                <h4>{{ camp.titre }}</h4>
                <ul>
                  @for (a of camp.arguments; track $index) { <li>{{ a }}</li> }
                </ul>
                <p class="controle" [class.alerte]="camp.nonVerifies.length">
                  @if (camp.nonVerifies.length) {
                    Greffier : chiffres absents des pièces → {{ camp.nonVerifies.join(', ') }}
                  } @else {
                    Greffier : tous les chiffres cités figurent dans les pièces.
                  }
                </p>
              </article>
            }
          </div>
          <details class="transcription">
            <summary>Transcription complète de l’audience ({{ interventions().length }} intervention{{ interventions().length > 1 ? 's' : '' }})</summary>
            <ol>
              @for (entree of interventions(); track entree.tour.ordre) {
                <li>
                  <h4>{{ entree.tour.acteur }} · {{ entree.tour.titre }}</h4>
                  <p>{{ entree.extrait }}{{ entree.complet ? '' : '…' }}</p>
                  @if (entree.complet && entree.tour.non_verifies?.length) {
                    <p class="alerte">Chiffres non vérifiés : {{ entree.tour.non_verifies!.join(', ') }}</p>
                  }
                </li>
              } @empty {
                <li>Les interventions apparaîtront au fil de l’audience.</li>
              }
            </ol>
          </details>
        </section>

        <!-- E. Sources et limites -->
        <section aria-labelledby="r-sources">
          <h3 id="r-sources">Sources et limites</h3>
          <ul class="limites">
            <li>Données : prix quotidiens ajustés du jeu AlphaForge, convertis en dollars canadiens, du {{ pr.periode.debut }} au {{ pr.periode.fin }}.</li>
            <li>Le verdict suit une règle fixe ; les agents argumentent, ils ne décident pas.</li>
            <li>Le passé observé ne prédit pas l’avenir. Profil fictif : ce n’est pas un conseil financier.</li>
            @if (pr.avertissement) { <li class="alerte">{{ pr.avertissement }}</li> }
          </ul>
          @for (piece of pieces(); track piece.numero) {
            <details class="piece">
              <summary>{{ piece.numero }} · {{ piece.description }}</summary>
              <dl>
                @for (fait of piece.faits; track $index) {
                  <dt>{{ fait.libelle }}</dt><dd>{{ fait.valeur }}</dd>
                }
              </dl>
              <p>{{ piece.source }} · {{ piece.periode }}</p>
              @if (piece.limites) { <p>Limites : {{ piece.limites }}</p> }
            </details>
          }
        </section>
      </div>
    } @else {
      <p>Le rapport sera disponible dès que le tribunal aura statué.</p>
    }
  `,
})
export class RapportAudienceComponent {
  readonly proces = input<Proces | null>(null);
  readonly interventions = input<readonly InterventionLue[]>([]);
  readonly pieces = input<readonly Piece[]>([]);
  readonly vote = input<Camp | null>(null);
  readonly audienceTerminee = input(false);
  /** Affiché à côté du vote : inutile de rappeler comment voter. */
  readonly pendantLeVote = input(false);
  /** Rapport relu après coup (tableau de bord) : pas d'invitation à voter. */
  readonly horsAudience = input(false);
  /** Avant le vote de l'investisseur : la décision du tribunal reste scellée. */
  readonly masquerDecision = input(false);
  readonly portefeuille = input<readonly Position[]>([]);

  readonly pct = pct;
  readonly dollars = dollars;
  readonly tonVerdict = tonVerdict;

  readonly ton = computed(() => tonVerdict(this.proces()?.decision.verdict ?? ''));

  readonly motifs = computed(() => {
    const d = this.proces()?.decision;
    return d ? [...d.contraintes, ...d.tensions, ...d.manquants].map((m) => m.texte) : [];
  });

  /** Le tribunal donne raison à la défense si le verdict est compatible, à l'accusation sinon. */
  readonly accord = computed<boolean | null>(() => {
    const v = this.vote();
    const ton = this.ton();
    if (!v || ton === 'indecidable') return null;
    const tribunalPour = ton === 'compatible';
    return (v === 'avocat_defense') === tribunalPour;
  });

  readonly chiffres = computed(() => chiffresCles(this.proces()));

  readonly portefeuilles = computed(() => {
    const pr = this.proces();
    const actuel = this.portefeuille();
    if (!pr || !actuel.length) return null;
    const t = pr.demande.taille;
    const apres = actuel.map((x) => ({ ticker: x.ticker, poids: x.poids * (1 - t) }));
    const existant = apres.find((x) => x.ticker === pr.demande.ticker);
    if (existant) existant.poids += t;
    else apres.push({ ticker: pr.demande.ticker, poids: t });
    const decrire = (p: { ticker: string; poids: number }[]) =>
      p.map((x) => `${x.ticker} ${pct(x.poids, 0)}`).join(', ');
    return [
      { nom: 'Avant', positions: actuel, description: `Portefeuille avant : ${decrire([...actuel])}` },
      { nom: 'Après', positions: apres, description: `Portefeuille après : ${decrire(apres)}` },
    ];
  });

  readonly camps = computed(() => {
    const pl = this.proces()?.plaidoiries ?? [];
    return [
      { cle: 'defense', titre: 'La Défense · pour la demande', p: pl[0] },
      { cle: 'accusation', titre: 'L’accusation · contre la demande', p: pl[1] },
    ].map(({ cle, titre, p }) => ({
      cle,
      titre,
      arguments: p ? argumentsDe(p.texte, 3) : ['Plaidoirie indisponible.'],
      nonVerifies: p?.non_verifies ?? [],
    }));
  });

}
