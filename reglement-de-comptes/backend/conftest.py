import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import os

# Les tests n'appellent pas Bedrock pour interpréter les questions vagues.
os.environ.setdefault("RDC_GREFFIER_MODELE", "0")
