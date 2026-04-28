from datetime import datetime, timedelta, timezone

from google.cloud import firestore
from redato_backend.shared.constants import (
    FIRESTORE_COLLECTION_NAME,
    FIRESTORE_DATABASE_NAME,
)
from redato_backend.shared.logger import logger
from redato_backend.shared.models import FirestoreConversationModel


# Tutor conversations are retained for this long past their last update, after
# which Firestore's TTL policy on `expirationTime` deletes them. Anchored on
# last-write so active conversations don't expire mid-session.
CONVERSATION_RETENTION_DAYS = 90


class FirestoreCache:
    def __init__(self):
        try:
            self.db = firestore.Client(database=FIRESTORE_DATABASE_NAME)
            self.collection = self.db.collection(FIRESTORE_COLLECTION_NAME)
            logger.info("Conectado ao Firestore com sucesso.")
        except Exception as e:
            logger.error(f"Falha ao conectar ao Firestore: {e}")
            self.db = None

    def get_conversation(  # noqa: C901
        self, client_id: str, chat_id: str
    ) -> FirestoreConversationModel:
        if not self.db:
            return FirestoreConversationModel(expirationTime=datetime.now(timezone.utc))
        try:
            chat_id_doc = (
                self.collection.document(chat_id)
                .collection("chat_ids")
                .document(client_id)
            )
            data = chat_id_doc.get()
            if not data.exists:
                return FirestoreConversationModel(
                    expirationTime=datetime.now(timezone.utc)
                )

            doc_dict = data.to_dict()
            timestamp_fields = ["timestamp", "status_expiration", "expirationTime"]

            for field in timestamp_fields:
                timestamp_value = doc_dict.get(field)
                if hasattr(timestamp_value, "timestamp"):
                    doc_dict[field] = datetime.fromtimestamp(
                        timestamp_value.timestamp(), tz=timezone.utc
                    )

            conversation_model = FirestoreConversationModel.from_firestore(doc_dict)
            logger.debug(
                f"Created conversation model with "
                f"{len(conversation_model.conversation)} messages"
            )
            return conversation_model

        except Exception as e:
            logger.error(f"Erro ao recuperar conversa do Firestore: {e}")
            return FirestoreConversationModel(expirationTime=datetime.now(timezone.utc))

    def set_conversation(
        self,
        client_id: str,
        chat_id: str,
        conversation_model: FirestoreConversationModel,
    ) -> None:
        if not self.db:
            return

        try:
            chat_id_doc = (
                self.collection.document(chat_id)
                .collection("chat_ids")
                .document(client_id)
            )
            now = datetime.now(timezone.utc)
            data_to_save = conversation_model.to_firestore()
            data_to_save["timestamp"] = now
            # Refresh the TTL anchor on every write so active conversations
            # survive long past their initial creation. Firestore's TTL policy
            # deletes docs once this timestamp is in the past.
            data_to_save["expirationTime"] = now + timedelta(
                days=CONVERSATION_RETENTION_DAYS
            )
            timestamp_fields = ["timestamp", "status_expiration", "expirationTime"]

            for field in timestamp_fields:
                if isinstance(data_to_save.get(field), datetime):
                    # Convert all datetime fields to UTC
                    dt = data_to_save[field].astimezone(timezone.utc)
                    data_to_save[field] = dt

            chat_id_doc.set(data_to_save)
        except Exception as e:
            logger.error(f"Erro ao salvar conversa no Firestore: {e}")
