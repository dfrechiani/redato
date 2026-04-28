# Firestore TTL — tutor conversations

Tutor conversations are stored in Firestore at:

```
conversations/{essay_id}/chat_ids/{user_id}
```

Each document has an `expirationTime` field refreshed on every write to
`now + 90 days` (see `CONVERSATION_RETENTION_DAYS` in `shared/firestore.py`).

Enable Firestore's TTL policy once per environment so the platform deletes
expired conversations automatically:

```
gcloud firestore fields ttls update expirationTime \
  --collection-group=chat_ids \
  --enable-ttl \
  --database=redato-intelligence-api \
  --project=notamil-prd
```

The TTL policy scans every doc in the `chat_ids` collection group (which
covers all tutor conversations) and deletes rows whose `expirationTime` is in
the past.

Verify:

```
gcloud firestore fields ttls list \
  --database=redato-intelligence-api \
  --project=notamil-prd
```

You should see `expirationTime` under `chat_ids` with state `ACTIVE`.

Notes:
- Deletion is eventual (usually within 24 hours of the TTL expiring).
- If you change `CONVERSATION_RETENTION_DAYS` in code, existing docs get the
  new expiration on their next write.
- The TTL field is configured at the Firestore level, not per-document, so
  there's nothing to backfill.
