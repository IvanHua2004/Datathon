import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import os

# Les tests n'appellent pas Bedrock pour interpréter les questions vagues.
os.environ["RDC_GREFFIER_MODELE"] = "0"
# Utiliser exclusivement les données locales pendant les tests unitaires (évite les timeouts S3)
os.environ["RDC_S3_BUCKET"] = ""

