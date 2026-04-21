"""DID generation and resolution for did:agentid:local namespace (Phase 1).
Phase 2 will use did:agentid:polygon:<base58-pubkey>.
"""
import uuid
import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, PublicFormat, PrivateFormat, NoEncryption
)


def generate_keypair() -> tuple[str, str]:
    """Returns (private_key_pem, public_key_pem)."""
    private_key = Ed25519PrivateKey.generate()
    priv_pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()
    pub_pem = private_key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()
    return priv_pem, pub_pem


def generate_did(agent_uuid: str | None = None) -> str:
    """Generate a did:agentid:local:<uuid> identifier."""
    uid = agent_uuid or str(uuid.uuid4())
    return f"did:agentid:local:{uid}"


def did_to_uuid(did: str) -> str:
    """Extract UUID from a local DID."""
    parts = did.split(":")
    if len(parts) != 4 or parts[:3] != ["did", "agentid", "local"]:
        raise ValueError(f"Invalid local DID: {did}")
    return parts[3]
