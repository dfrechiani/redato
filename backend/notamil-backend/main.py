import os

OFFLINE = os.getenv("REDATO_DEV_OFFLINE") == "1"

# Apply dev-offline stubs BEFORE anything else imports the real services.
if OFFLINE:
    from redato_backend.dev_offline import apply_patches
    apply_patches()

from redato_backend.base_api.main import app  # noqa: E402

# Cloud Function handlers are only needed when deployed to GCP. They pull in
# heavy deps (openai, anthropic, spacy, opencv, etc.) so we skip them in dev.
if not OFFLINE:
    from redato_backend.functions.essay_function.main import essay_handler  # noqa: E402,F401
    from redato_backend.functions.essay_ocr.main import ocr_handler  # noqa: E402,F401
    from redato_backend.functions.tutor.main import chat_tutor  # noqa: E402,F401
