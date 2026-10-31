# API contracts and assessment rules

The backend OpenAPI document at `/openapi.json` is the runtime contract. Exercise configurations carry schema/exercise versions and omit server answer keys. Trial submissions contain response data and approximate browser timing; correctness, completion and score fields are server-owned.

All baseline items are frozen and uncoached. A valid item can be submitted only once per assessment session. A network retry reuses the exact event ID and payload. Interrupted observations remain in the event history but do not fill valid baseline slots; they can be retried. Scores must use a coherent assessment session for each dimension.

The reasoning index is100*correct/6 only after six valid items. Other dimensions remain unassessed until their own family is implemented and sufficiently completed. Training uses distinct item IDs/versions/blocks and never rewrites baseline evidence. Four comparable eligible trials yield a versioned, exactly-once decision; hinted evidence forces a hold rather than promotion.

Each new family must document its response shape, controlled bank, timing rules, scorer and success definition for future adaptive training. Those additions are being implemented in Batch3; consult the final requirement matrix for verified coverage.
