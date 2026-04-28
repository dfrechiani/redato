import logging
import os

from dotenv import load_dotenv

load_dotenv()

GCP_PROJECT_ID = "notamil-prd"
FIREBASE_SERVICE_ACCOUNT = os.getenv("FIREBASE_SERVICE_ACCOUNT")
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "redato-prd")
REDATO_API_URL = "https://redato-api-206258371448.us-east1.run.app"

# FIRESTORE
FIRESTORE_COLLECTION_NAME = os.environ.get(
    "GCP_FIRESTORE_COLLECTION_NAME", "conversations"
)
FIRESTORE_DATABASE_NAME = os.environ.get(
    "GCP_FIRESTORE_DATABASE_NAME", "redato-intelligence-api"
)

FIREBASE_SCOPES = [
    "https://www.googleapis.com/auth/firebase.database",
    "https://www.googleapis.com/auth/firebase.messaging",
    "https://www.googleapis.com/auth/identitytoolkit",
]


ENABLE_STACKDRIVER = "True"
LOG_LEVEL = logging.INFO
LOGGER_NAME = "ester-functions"

# BigQuery
REDATO_DATASET = "redato"
USERS_TABLE = f"{GCP_PROJECT_ID}.{REDATO_DATASET}.users"
ESSAYS_RAW_TABLE = f"{GCP_PROJECT_ID}.{REDATO_DATASET}.essays_raw"
ESSAYS_GRADED_TABLE = f"{GCP_PROJECT_ID}.{REDATO_DATASET}.essays_graded"
ESSAYS_DETAILED_TABLE = f"{GCP_PROJECT_ID}.{REDATO_DATASET}.essays_detailed"
ESSAYS_ERRORS_TABLE = f"{GCP_PROJECT_ID}.{REDATO_DATASET}.essays_errors"
ESSAYS_OCR_TABLE = f"{GCP_PROJECT_ID}.{REDATO_DATASET}.essays_ocr"
CLASSES_TABLE = f"{GCP_PROJECT_ID}.{REDATO_DATASET}.classes"
STUDENTS_TABLE = f"{GCP_PROJECT_ID}.{REDATO_DATASET}.students"
PROFESSORS_TABLE = f"{GCP_PROJECT_ID}.{REDATO_DATASET}.professors"
SCHOOLS_TABLE = f"{GCP_PROJECT_ID}.{REDATO_DATASET}.schools"
THEMES_TABLE = f"{GCP_PROJECT_ID}.{REDATO_DATASET}.classes_themes"
COMPETENCIES_TABLE = f"{GCP_PROJECT_ID}.{REDATO_DATASET}.competencies"
PROFESSOR_CORRECTIONS_TABLE = (
    f"{GCP_PROJECT_ID}.{REDATO_DATASET}.professor_corrections"
)
CORRECTION_REVIEW_TABLE = (
    f"{GCP_PROJECT_ID}.{REDATO_DATASET}.correction_review"
)

# Email
EMAIL_USER = os.environ.get("EMAIL_USER", "")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")

# OpenAI
OPENAI_GPT_TEMPERATURE = 0.1
OPENAI_GPT_MODEL = "ft:gpt-4o-2024-08-06:personal::BKs9jGEn"
OPENAI_MAX_TOKENS = 5000
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-pro-exp-03-25"

# Claude
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_CLAUDE_MODEL = "claude-opus-4-7"

# OCR pipeline — Mudança 5 (2026-04-25): Cloud Vision desligada por default.
# A/B com 5 redações × 3 configs × n=2 mostrou que Cloud Vision adicionava
# +4.3 pts de % uncertain, dobrava variância (σ=5.2 vs 2.0) e triplicava
# latência (~50s vs ~17s). Hipótese: transcripts errados poluíam contexto
# do Claude. Setar OCR_USE_CLOUD_VISION=1 no .env pra reverter.
OCR_USE_CLOUD_VISION = os.environ.get("OCR_USE_CLOUD_VISION", "0") == "1"

# OCR pipeline — Mudança 6 (2026-04-25): 3 enhanced mantidas como default.
# A/B com 5 redações × 2 configs × n=3 (30 chamadas) mostrou que 3 enhanced
# ganha +1.7 a +2.0 pts em redações de letra difícil (Carlos 02_08, 05_12-1)
# e empata em letras limpas. Custo extra (+3.7s/call, ~$40/mês a 10k calls)
# é proporcional ao ganho. Flag fica como mecanismo de rollback.
# Quando "0", AnthropicVisionAgent envia só a imagem original ao Claude.
OCR_USE_ENHANCED_IMAGES = os.environ.get("OCR_USE_ENHANCED_IMAGES", "1") == "1"

# Essay Grader
COMPETENCIES = {
    "d7d30def-7f7f-4cc4-ae92-b41228a9855e": "Domínio da Norma Culta",
    "3334fd6a-adf0-4c43-8e83-630270c17f86": "Seleção e Organização das Informações",
    "5467abb2-bd17-44be-90bd-a5065d1e6ee0": "Conhecimento dos Mecanismos Linguísticos",
    "a7c812b2-fefd-4757-8774-e08bcdba82cc": "Compreensão do Tema",
    "fd207ce5-b400-475b-a136-ce9c4d5cd00d": "Proposta de Intervenção",
}

ESSAYS_ANALYZER_CLOUD_FUNCTION = (
    "https://us-east1-notamil-prd.cloudfunctions.net/essay_handler"
)
ESSAY_OCR_CLOUD_FUNCTION = "https://us-east1-notamil-prd.cloudfunctions.net/ocr_handler"
TUTOR_CLOUD_FUNCTION = "https://us-east1-notamil-prd.cloudfunctions.net/chat_tutor"
