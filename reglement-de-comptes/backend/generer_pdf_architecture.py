"""Script de génération du rapport PDF officiel d'architecture du projet Règlement de comptes."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable, PageBreak
)
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """Canvas permettant de numéroter les pages sous la forme 'Page X sur Y'."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_decorations(self, page_count):
        self.saveState()
        # En-tête (à partir de la page 2)
        if self._pageNumber > 1:
            self.setFont("Helvetica-Bold", 7.5)
            self.setFillColor(colors.HexColor("#2B6CB0"))
            self.drawString(40, 762, "RÈGLEMENT DE COMPTES")
            self.setFont("Helvetica", 7.5)
            self.setFillColor(colors.HexColor("#718096"))
            self.drawString(160, 762, "— Rapport d'Architecture Système, Multi-Agents & Cloud AWS")
            self.setStrokeColor(colors.HexColor("#CBD5E0"))
            self.setLineWidth(0.5)
            self.line(40, 756, 572, 756)

        # Pied de page (sur toutes les pages)
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#718096"))
        self.drawString(40, 24, "Datathon PolyFinances 2026 (AlphaForge AI) — Simulation financière contradictoire")
        page_text = f"Page {self._pageNumber} sur {page_count}"
        self.drawRightString(572, 24, page_text)
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(40, 34, 572, 34)
        self.restoreState()


def generer_rapport_pdf(fichier_sortie: Path) -> Path:
    doc = SimpleDocTemplate(
        str(fichier_sortie),
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=42,
        bottomMargin=42
    )

    styles = getSampleStyleSheet()

    # Typographie soignée
    c_primary = colors.HexColor("#1A365D")
    c_secondary = colors.HexColor("#2B6CB0")
    c_dark = colors.HexColor("#2D3748")
    c_muted = colors.HexColor("#718096")
    c_bg_light = colors.HexColor("#F7FAFC")
    c_border = colors.HexColor("#E2E8F0")

    style_title = ParagraphStyle(
        "RapportTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=c_primary,
        alignment=0,
        spaceAfter=4
    )
    style_subtitle = ParagraphStyle(
        "RapportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=13,
        textColor=c_secondary,
        alignment=0,
        spaceAfter=12
    )
    style_h1 = ParagraphStyle(
        "RapportH1",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=c_primary,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )
    style_h2 = ParagraphStyle(
        "RapportH2",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=c_secondary,
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )
    style_body = ParagraphStyle(
        "RapportBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11.5,
        textColor=c_dark,
        spaceAfter=5
    )
    style_body_bold = ParagraphStyle(
        "RapportBodyBold",
        parent=style_body,
        fontName="Helvetica-Bold"
    )
    style_callout = ParagraphStyle(
        "RapportCallout",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#1A202C")
    )
    style_th = ParagraphStyle(
        "RapportTH",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=0
    )
    style_td = ParagraphStyle(
        "RapportTD",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=c_dark
    )
    style_td_bold = ParagraphStyle(
        "RapportTDBold",
        parent=style_td,
        fontName="Helvetica-Bold",
        textColor=c_primary
    )

    story = []

    # =========================================================================
    # EN-TÊTE / BANDEAU TITRE
    # =========================================================================
    meta_table_data = [
        [
            Paragraph("<b>PROJET :</b> Règlement de comptes", style_td),
            Paragraph("<b>CADRE :</b> Datathon PolyFinances 2026 (AlphaForge AI)", style_td),
            Paragraph(f"<b>DATE :</b> {datetime.now().strftime('%Y-%m-%d')}", style_td),
        ],
        [
            Paragraph("<b>APPLICATION :</b> Tribunal Financier Simulé", style_td),
            Paragraph("<b>RÉGION AWS :</b> us-east-1 (Virginie du Nord)", style_td),
            Paragraph("<b>STATUT :</b> Production / Prototype Final", style_td),
        ]
    ]
    t_meta = Table(meta_table_data, colWidths=[180, 220, 132])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), c_bg_light),
        ('BOX', (0, 0), (-1, -1), 0.5, c_border),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, c_border),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))

    story.append(Paragraph("RÈGLEMENT DE COMPTES", style_title))
    story.append(Paragraph("Revue Complète du Système, Architecture Multi-Agents & Technologies AWS", style_subtitle))
    story.append(t_meta)
    story.append(Spacer(1, 10))

    # =========================================================================
    # SECTION 1 : VUE D'ENSEMBLE & PHILOSOPHIE
    # =========================================================================
    story.append(Paragraph("1. Vue d'Ensemble & Principe Fondamental « Zero Hallucination »", style_h1))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=1, spaceAfter=6))
    
    texte_intro = (
        "<b>Règlement de comptes</b> est une plateforme d'aide à la décision financière et d'éducation patrimoniale. "
        "Elle transforme l'évaluation d'un portefeuille en un <b>tribunal financier contradictoire</b> : un investisseur fictif "
        "(Amira, Mateo, Robert ou persona sur mesure) soumet une volonté d'investissement (ex. : « placer 20 % dans NVDA »), "
        "qui est ensuite débattue et auditée en direct par des agents spécialisés avant d'être jugée."
    )
    story.append(Paragraph(texte_intro, style_body))

    # Boîte de mise en avant (Callout)
    callout_data = [[
        Paragraph(
            "<b>Règle d'or de l'architecture :</b> <i>« Les modèles de langage argumentent, le code calcule et la règle tranche. »</i><br/>"
            "• <b>Aucun calcul confié aux LLM :</b> 1 304 séances quotidiennes réelles (2021-2026 en CAD) auditées par code déterministe.<br/>"
            "• <b>Traçabilité intégrale :</b> Chaque fait est consigné dans une pièce scellée et numérotée ([P-01], [P-02], etc.).<br/>"
            "• <b>Contrôle factuel continu :</b> Le Greffier audite chaque chiffre par Regex ; tout nombre non certifié est signalé.",
            style_callout
        )
    ]]
    t_callout = Table(callout_data, colWidths=[532])
    t_callout.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#EBF8FF")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#3182CE")),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(t_callout)
    story.append(Spacer(1, 8))

    # =========================================================================
    # SECTION 2 : ARCHITECTURE TECHNIQUE ET FLUX
    # =========================================================================
    story.append(Paragraph("2. Cartographie de l'Architecture Système", style_h1))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=1, spaceAfter=6))

    arch_data = [
        [
            Paragraph("<b>Couche</b>", style_th),
            Paragraph("<b>Composants & Technologies</b>", style_th),
            Paragraph("<b>Rôle & Responsabilité</b>", style_th),
        ],
        [
            Paragraph("<b>Frontend (Client)</b>", style_td_bold),
            Paragraph("<b>Angular 19+ (SPA / Standalone)</b><br/>• Signals & Reactive Flow<br/>• Scène d'audience animée (GIFs parlants)<br/>• Web Audio & Synthèse vocale<br/>• Graphiques vectoriels SVG dynamiques<br/>• App Streamlit (frontend/app.py)", style_td),
            Paragraph("Interface utilisateur théâtralisée. Restitution cadencée de l'audience, interaction avec le greffier, consultation du catalogue d'actifs, comparaison et téléchargement de rapport PDF certifié. Aucun calcul exécuté côté client.", style_td),
        ],
        [
            Paragraph("<b>Routage & Gateway</b>", style_td_bold),
            Paragraph("<b>Nginx Reverse Proxy (Port 4200/80)</b><br/>• Relais interne vers API (Port 8000)<br/>• Docker Compose Orchestration", style_td),
            Paragraph("Unifie le point d'entrée réseau, protège l'accès direct aux conteneurs, sert les fichiers compilés Angular et relaie les requêtes REST et streaming SSE.", style_td),
        ],
        [
            Paragraph("<b>Backend API</b>", style_td_bold),
            Paragraph("<b>FastAPI & Uvicorn (Python 3.12)</b><br/>• Endpoints REST (/api/proces, etc.)<br/>• Streaming SSE (/api/proces/stream)<br/>• ReportLab 5.1 (Génération vectorielle)", style_td),
            Paragraph("Point d'accès aux services métier (rdc). Gère la sérialisation, la vérification des personas, l'exécution asynchrone des débats et la production de rapports d'audit.", style_td),
        ],
        [
            Paragraph("<b>Cœur Métier (rdc)</b>", style_td_bold),
            Paragraph("<b>Modules Python Spécialisés</b><br/>• moteur.py (matrices, bootstrap, VaR)<br/>• proces.py (ordonnanceur & timeline)<br/>• greffier.py (scellés & audit regex)<br/>• simulateur.py (stress-testing patrimonial)", style_td),
            Paragraph("Calculs matriciels haute précision. Applique la règle stricte du verdict (Compatible, En tension, Indécidable, Contraire). Règle du tribunal déterministe et infalsifiable.", style_td),
        ],
        [
            Paragraph("<b>Cloud AWS</b>", style_td_bold),
            Paragraph("<b>Amazon Bedrock & Strands Agents</b><br/>• Claude Sonnet 5 / Nova Lite<br/>• Amazon S3 (Datalake fiches JSON/Parquet)<br/>• AWS STS & boto3 client (us-east-1)", style_td),
            Paragraph("Intelligence générative avec Function Calling (@tool convoquer_temoin) pour les plaidoiries et jugements. Persistance cloud et mise en cache des fiches d'actifs précalculées.", style_td),
        ],
    ]

    t_arch = Table(arch_data, colWidths=[90, 200, 242])
    t_arch.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), c_primary),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_bg_light]),
        ('GRID', (0, 0), (-1, -1), 0.5, c_border),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t_arch)
    story.append(Spacer(1, 10))

    # =========================================================================
    # SECTION 3 : LE NOMBRE D'AGENTS UTILISÉ (12 AGENTS)
    # =========================================================================
    story.append(PageBreak())  # Page 2
    story.append(Paragraph("3. Inventaire et Rôle des 12 Agents du Tribunal", style_h1))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=1, spaceAfter=6))
    
    story.append(Paragraph(
        "Le système orchestre un total de <b>12 agents et experts spécialisés</b>, organisés selon trois strates distinctes :",
        style_body
    ))

    # Strate 1
    story.append(Paragraph("Strate A : Les 3 Agents Cognitifs LLM (Amazon Bedrock / Strands Framework)", style_h2))
    agents_llm_data = [
        [Paragraph("<b>Agent</b>", style_th), Paragraph("<b>Avatar / Nom</b>", style_th), Paragraph("<b>Outils & Modèle</b>", style_th), Paragraph("<b>Mission Judiciaire</b>", style_th)],
        [
            Paragraph("<b>La Défense</b>", style_td_bold),
            Paragraph("💼 Me Vigor", style_td),
            Paragraph("Claude Sonnet 5<br/>+ Outil <i>convoquer_temoin</i>", style_td),
            Paragraph("Défend ardemment la demande au nom des ambitions et préférences de l'investisseur. Convoque lui-même les témoins utiles et cite les pièces scellées. Reconnait la limite majeure de sa position.", style_td)
        ],
        [
            Paragraph("<b>Le Procureur</b>", style_td_bold),
            Paragraph("🛡️ Me Austère", style_td),
            Paragraph("Claude Sonnet 5<br/>+ Outil <i>convoquer_temoin</i>", style_td),
            Paragraph("Attaque la demande au nom du profil déclaré : dépassement du budget de perte, volatilité excessive, horizon trop court, concentration de portefeuille et non-respect des critères ESG.", style_td)
        ],
        [
            Paragraph("<b>Le Juge</b>", style_td_bold),
            Paragraph("👨‍⚖️ Le Président", style_td),
            Paragraph("Claude Sonnet 5<br/>(Prompt structuré)", style_td),
            Paragraph("Rédige les motifs solennels du jugement. Il explique pourquoi la règle déterministe a tranché dans ce sens, synthétise les débats et présente ce qui ferait basculer le verdict.", style_td)
        ],
    ]
    t_llm = Table(agents_llm_data, colWidths=[70, 85, 125, 252])
    t_llm.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), c_secondary),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_bg_light]),
        ('GRID', (0, 0), (-1, -1), 0.5, c_border),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_llm)
    story.append(Spacer(1, 6))

    # Strate 2
    story.append(Paragraph("Strate B : Les 3 Officiers de Justice et Contrôleurs Factuels", style_h2))
    agents_ctrl_data = [
        [Paragraph("<b>Rôle</b>", style_th), Paragraph("<b>Avatar / Nom</b>", style_th), Paragraph("<b>Moteur / Fichier</b>", style_th), Paragraph("<b>Responsabilité au Tribunal</b>", style_th)],
        [
            Paragraph("<b>Le Greffier</b>", style_td_bold),
            Paragraph("📜 Greffier d'audience", style_td),
            Paragraph("greffier.py<br/>questions.py", style_td),
            Paragraph("Numérote et scelle les pièces à conviction ([P-01], etc.). <b>Audite en direct</b> chaque chiffre prononcé par la défense et l'accusation pour alerter en cas de chiffre inventé. Génère la Carte d'Audit.", style_td)
        ],
        [
            Paragraph("<b>L'Huissier</b>", style_td_bold),
            Paragraph("📢 Huissier d'audience", style_td),
            Paragraph("proces.py", style_td),
            Paragraph("Ouvre solennellement la séance du tribunal, énonce les chefs d'instruction et rappelle la volonté initiale formulée par l'investisseur.", style_td)
        ],
        [
            Paragraph("<b>L'Archiviste</b>", style_td_bold),
            Paragraph("📚 L'Archiviste", style_td),
            Paragraph("archiviste.py", style_td),
            Paragraph("Agent factuel autonome : récite les fiches techniques des 31 titres, classe le catalogue et compare deux actifs sans émettre d'opinion ni de prédiction subjective.", style_td)
        ],
    ]
    t_ctrl = Table(agents_ctrl_data, colWidths=[70, 100, 110, 252])
    t_ctrl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2C5282")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_bg_light]),
        ('GRID', (0, 0), (-1, -1), 0.5, c_border),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_ctrl)
    story.append(Spacer(1, 6))

    # Strate 3
    story.append(Paragraph("Strate C : Les 6 Témoins Experts Incarnés (Dépositions sous serment)", style_h2))
    temoins_data = [
        [Paragraph("<b>Témoin</b>", style_th), Paragraph("<b>Personnage Incarné</b>", style_th), Paragraph("<b>Pièce</b>", style_th), Paragraph("<b>Faits & Métriques Certifiées</b>", style_th)],
        [
            Paragraph("<b>Risque</b>", style_td_bold),
            Paragraph("📊 Dr. Laurent (Actuaire)", style_td),
            Paragraph("[P-01] risque", style_td),
            Paragraph("Pire baisse historique, perte en dollars vs budget de perte déclaré, temps passé sous le sommet et part du risque portée par le titre.", style_td)
        ],
        [
            Paragraph("<b>Diversification</b>", style_td_bold),
            Paragraph("🧭 Mme Chantal (Cartographe)", style_td),
            Paragraph("[P-02] diversif.", style_td),
            Paragraph("Rendement moyen les 10 % pires jours de marché (jours de crise), corrélation calme vs crise, concentration sectorielle et risque de change USD/CAD.", style_td)
        ],
        [
            Paragraph("<b>Valeurs</b>", style_td_bold),
            Paragraph("🌱 Me Tremblay (Auditeur ESG)", style_td),
            Paragraph("[P-03] valeurs", style_td),
            Paragraph("Preuves matérielles publiques documentées dans esg_preuves.csv, controverses éthiques et conformité aux filtres moraux déclarés.", style_td)
        ],
        [
            Paragraph("<b>Macro</b>", style_td_bold),
            Paragraph("🏦 M. Raymond (Banques Centrales)", style_td),
            Paragraph("[P-04] macro", style_td),
            Paragraph("Taux directeur de la Banque du Canada, obligations 10 ans, taux Fed américain et inflation CPI au moment des pires creux de marché.", style_td)
        ],
        [
            Paragraph("<b>Action</b>", style_td_bold),
            Paragraph("📈 Dr. Laurent (Quant Analyst)", style_td),
            Paragraph("[P-05] action", style_td),
            Paragraph("Fiche financière quantitative : Sharpe, Sortino, Bêta S&P 500, VaR 95%, CVaR (Expected Shortfall), dividendes et diagnostic de distribution.", style_td)
        ],
        [
            Paragraph("<b>Simulation</b>", style_td_bold),
            Paragraph("🔮 Dr. Sterling (Simulateur)", style_td),
            Paragraph("[P-06] simu.", style_td),
            Paragraph("Modélisation déterministe des 3 scénarios patrimoniaux (pire cas de crise, cas médian 1 an, meilleur rallye) et impact net en dollars.", style_td)
        ],
    ]
    t_tem = Table(temoins_data, colWidths=[70, 130, 80, 252])
    t_tem.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#319795")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_bg_light]),
        ('GRID', (0, 0), (-1, -1), 0.5, c_border),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_tem)
    story.append(Spacer(1, 10))

    # =========================================================================
    # SECTION 4 : TECHNOLOGIES AWS UTILISÉES
    # =========================================================================
    story.append(PageBreak())  # Page 3
    story.append(Paragraph("4. Écosystème & Technologies AWS (Région us-east-1)", style_h1))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=1, spaceAfter=6))

    aws_data = [
        [Paragraph("<b>Service AWS</b>", style_th), Paragraph("<b>Implémentation & Modèles</b>", style_th), Paragraph("<b>Rôle & Spécificités Techniques</b>", style_th)],
        [
            Paragraph("<b>Amazon Bedrock</b><br/>(Runtime API)", style_td_bold),
            Paragraph("• <b>global.anthropic.claude-sonnet-5</b><br/>• global.amazon.nova-2-lite-v1:0<br/>• API unifiée boto3 Converse", style_td),
            Paragraph("Moteur d'inférence serverless pour les agents d'audience. Exécution sans paramètre <i>temperature</i> (obligatoire pour le mode de raisonnement de Claude 3.5/5). Allocation de 2 000 maxTokens pour éviter les coupures.", style_td)
        ],
        [
            Paragraph("<b>AWS Strands Agents</b><br/>(Framework SDK)", style_td_bold),
            Paragraph("• Bibliothèque strands-agents<br/>• BedrockModel & Agent<br/>• Décorateur @tool", style_td),
            Paragraph("Orchestration multi-agents autonome. Permet l'outillage et l'appel de fonctions (Function Calling) : Me Vigor et Me Austère décident dynamiquement d'invoquer <i>convoquer_temoin(nom)</i> selon l'argumentation.", style_td)
        ],
        [
            Paragraph("<b>Amazon S3</b><br/>(Stockage d'Objets)", style_td_bold),
            Paragraph("• Bucket privé (SigV4)<br/>• extracted_actions/*.json<br/>• actions_summary.parquet/csv<br/>• s3_service.py", style_td),
            Paragraph("Datalake et cache cloud haute performance. Stocke les données de marché initiales et les fiches analytiques précalculées. Évite de recalculer les métriques lourdes lors des requêtes.", style_td)
        ],
        [
            Paragraph("<b>AWS STS</b><br/>(Security Token Service)", style_td_bold),
            Paragraph("• Credentials éphémères<br/>• aws sts get-caller-identity", style_td),
            Paragraph("Gestion des jetons de sécurité temporaires d'AWS Workshop Studio. Assure une authentification robuste sans secret persistant dans les dépôts de code.", style_td)
        ],
        [
            Paragraph("<b>AWS CLI v2 & CloudShell</b>", style_td_bold),
            Paragraph("• Scripts de provisionnement<br/>• Synchronisation aws s3 sync", style_td),
            Paragraph("Automatisation du déploiement, vérification de l'activation des modèles Bedrock et peuplement initial du bucket de données.", style_td)
        ],
    ]
    t_aws = Table(aws_data, colWidths=[110, 160, 262])
    t_aws.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), c_primary),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_bg_light]),
        ('GRID', (0, 0), (-1, -1), 0.5, c_border),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t_aws)
    story.append(Spacer(1, 10))

    # =========================================================================
    # SECTION 5 : RÉSILIENCE, TESTS & CONCLUSION
    # =========================================================================
    story.append(Paragraph("5. Résilience, Mécanismes de Secours & Synthèse", style_h1))
    story.append(HRFlowable(width="100%", thickness=1, color=c_secondary, spaceBefore=1, spaceAfter=6))

    conclusion_text = (
        "<b>Mécanisme de Fail-safe automatique :</b> Si Amazon Bedrock est inaccessible (expiration de jeton STS, "
        "dépassement de quota ou absence de connectivité réseau), le système bascule instantanément en <i>mode gabarit</i>. "
        "L'audience est intégralement rejouée avec des textes déterministes contrôlés par règles, sans interruption de service.<br/><br/>"
        "<b>Validation & Robustesse :</b> La suite de tests automatisés (pytest) valide à la fois l'indépendance des calculs "
        "(contre-calculs manuels du Drawdown), la recevabilité linguistique du greffier, la consistance mathématique des simulations "
        "patrimoniales et la non-régression des verdicts.<br/><br/>"
        "<b>Conclusion :</b> Le projet <i>Règlement de comptes</i> démontre qu'il est possible d'allier l'éloquence et l'adaptabilité "
        "des modèles d'IA générative AWS Bedrock avec la rigueur mathématique absolue requise dans l'industrie financière."
    )
    story.append(Paragraph(conclusion_text, style_body))

    # Génération du document avec NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    return fichier_sortie


if __name__ == "__main__":
    racine_projet = Path(__file__).resolve().parent.parent
    sortie_pdf = racine_projet / "rapport_architecture_agents_aws.pdf"
    generer_rapport_pdf(sortie_pdf)
    print(f"PDF généré avec succès : {sortie_pdf}")
