"""Ed25519 signing utilities for owner authorization and event integrity."""
import hashlib
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key
from cryptography.exceptions import InvalidSignature


def sign(private_key_pem: str, data: bytes) -> str:
    """Sign data with Ed25519 private key. Returns hex-encoded signature."""
    key: Ed25519PrivateKey = load_pem_private_key(private_key_pem.encode(), password=None)
    return key.sign(data).hex()


def verify(public_key_pem: str, data: bytes, signature_hex: str) -> bool:
    """Verify Ed25519 signature. Returns True if valid."""
    try:
        key: Ed25519PublicKey = load_pem_public_key(public_key_pem.encode())
        key.verify(bytes.fromhex(signature_hex), data)
        return True
    except (InvalidSignature, ValueError):
        return False


def hash_bytes(data: bytes) -> str:
    """SHA-256 hash, hex-encoded."""
    return hashlib.sha256(data).hexdigest()


def hash_str(data: str) -> str:
    return hash_bytes(data.encode())
