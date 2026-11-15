"""Tests unitaires du module rdc.conversation : politesse, glossaire, fautes de frappe et profil."""
from rdc import conversation, donnees, questions


def test_politesse():
    # Salutations
    salut = conversation.politesse("bonjour", "Robert")
    assert salut is not None and salut[0] == "salutation" and "Bonjour Robert" in salut[1]

    # Remerciements
    merci = conversation.politesse("merci beaucoup", "Robert")
    assert merci is not None and merci[0] == "remerciement" and "Avec plaisir" in merci[1]

    # Au revoir
    bye = conversation.politesse("au revoir", "Robert")
    assert bye is not None and bye[0] == "au_revoir" and "L'audience est levée" in bye[1]

    # Recommencer
    reset = conversation.politesse("recommencer à zéro", "Robert")
    assert reset is not None and reset[0] == "recommencer" and "j'efface le contexte" in reset[1]

    # Question financière : pas de la politesse
    assert conversation.politesse("devrais-je placer 10 % dans NVDA ?", "Robert") is None


def test_glossaire_definitions():
    # Définition de la volatilité
    terme_vol = conversation.terme_demande("c'est quoi la volatilite ?", a_des_titres=False)
    assert terme_vol == "volatilité"
    assert "mesure l'ampleur" in conversation.GLOSSAIRE["volatilité"][1]

    # Définition de la pire baisse
    terme_pb = conversation.terme_demande("explique-moi la pire baisse", a_des_titres=False)
    assert terme_pb == "pire baisse"

    # Définition du budget de perte
    terme_bp = conversation.terme_demande("qu'est-ce que le budget de perte ?", a_des_titres=False)
    assert terme_bp == "budget de perte"

    # Définition d'un FNB
    terme_fnb = conversation.terme_demande("c'est quoi un fnb ?", a_des_titres=False)
    assert terme_fnb == "FNB"

    # Si la question contient un titre, ce n'est pas une simple définition du glossaire
    assert conversation.terme_demande("c'est quoi la volatilite de NVDA ?", a_des_titres=True) is None


def test_fautes_de_frappe_titres():
    d = donnees.charger()
    univers = {t: str(n) for t, n in d.univers["name"].items()}
    alias = questions.ALIAS

    # "nvidai" doit être reconnu comme NVDA
    approx = conversation.titres_approchants("que penses-tu de nvidai ?", univers, alias)
    assert any(ticker == "NVDA" for _, ticker in approx)

    # "shoppify" doit être reconnu comme SHOP.TO
    approx_shop = conversation.titres_approchants("combien vaut shoppify ?", univers, alias)
    assert any(ticker == "SHOP.TO" for _, ticker in approx_shop)

    # Les mots courants de la finance ne doivent pas être confondus avec des titres
    approx_courants = conversation.titres_approchants("mon portefeuille et mes actions", univers, alias)
    assert approx_courants == []


def test_question_sur_le_profil():
    assert conversation.question_sur_le_profil("qu'est-ce que j'ai dans mon portefeuille ?")
    assert conversation.question_sur_le_profil("quel est mon budget de risque ?")
    assert conversation.question_sur_le_profil("qui suis-je ?")
    assert not conversation.question_sur_le_profil("est-ce que NVDA monte demain ?")
