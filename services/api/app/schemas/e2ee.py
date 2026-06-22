from pydantic import BaseModel, ConfigDict, Field
import uuid


class PublicKeyUpsert(BaseModel):
    # Exported public key as a JWK JSON string (stored verbatim, server never sees private key).
    public_key_jwk: str = Field(min_length=2, max_length=4000)
    key_fingerprint: str = Field(min_length=2, max_length=64)


class PublicKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    public_key_jwk: str
    key_fingerprint: str
