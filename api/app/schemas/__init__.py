"""API request/response schemas (Pydantic v2 DTOs).

CONTRACT DRAFT — US-E4-00. These are the API contract types: separate from the ORM
(``app.db.models``) on purpose. Enums mirror the native PG enums by value
(``app.schemas.enums``); every response is wrapped in the success/error envelope
(``app.schemas.envelope``).
"""
