"""Verify RS256/384/512 JWTs against a remote JWKS endpoint, stdlib only.

Lets a remote control plane mint session tokens with its own private key; the
bench trusts them by fetching the matching public keys from ``admin.jwks_url``.
No shared secret and no third-party crypto library — RSA PKCS#1 v1.5
verification is plain integer math."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.request

from pilot.commands.generate_session import _unb64

_CACHE_TTL = 300
_FETCH_TIMEOUT = 5
_cache: dict[str, tuple[float, dict[str, dict]]] = {}

# EMSA-PKCS1-v1_5 DigestInfo prefix per RSA-SHA algorithm.
_DIGEST_INFO = {
    "RS256": ("sha256", bytes.fromhex("3031300d060960864801650304020105000420")),
    "RS384": ("sha384", bytes.fromhex("3041300d060960864801650304020205000430")),
    "RS512": ("sha512", bytes.fromhex("3051300d060960864801650304020305000440")),
}


def verify_jwks_token(token: str, jwks_url: str) -> dict | None:
    """Return the token's claims if a JWKS public key verifies it and it has
    not expired, else None. Fails closed on any error."""
    if not token or not jwks_url:
        return None
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        header = json.loads(_unb64(header_b64))
        algorithm = header.get("alg")
        if algorithm not in _DIGEST_INFO:
            return None
        key = _find_key(jwks_url, header.get("kid"))
        if not key or not _rsa_verify(f"{header_b64}.{payload_b64}", _unb64(signature_b64), key, algorithm):
            return None
        payload = json.loads(_unb64(payload_b64))
    except (ValueError, KeyError, json.JSONDecodeError):
        return None
    exp = payload.get("exp")
    return payload if isinstance(exp, int) and time.time() < exp else None


def _find_key(jwks_url: str, kid: str | None) -> dict | None:
    """Look the signing key up by ``kid``, refetching once if the cache misses
    (keys may have rotated)."""
    key = _select(_keys(jwks_url), kid)
    if key is None:
        key = _select(_keys(jwks_url, refresh=True), kid)
    return key


def _select(keys: dict[str, dict], kid: str | None) -> dict | None:
    if kid:
        return keys.get(kid)
    return next(iter(keys.values()), None)


def _keys(jwks_url: str, refresh: bool = False) -> dict[str, dict]:
    cached = _cache.get(jwks_url)
    if not refresh and cached and time.time() - cached[0] < _CACHE_TTL:
        return cached[1]
    keys = _fetch_keys(jwks_url)
    _cache[jwks_url] = (time.time(), keys)
    return keys


def _fetch_keys(jwks_url: str) -> dict[str, dict]:
    try:
        with urllib.request.urlopen(jwks_url, timeout=_FETCH_TIMEOUT) as response:
            document = json.loads(response.read().decode())
    except (OSError, ValueError):
        return {}
    rsa_keys = [k for k in document.get("keys", []) if k.get("kty") == "RSA"]
    return {key.get("kid", str(index)): key for index, key in enumerate(rsa_keys)}


def _rsa_verify(signing_input: str, signature: bytes, key: dict, algorithm: str) -> bool:
    modulus = int.from_bytes(_unb64(key["n"]), "big")
    exponent = int.from_bytes(_unb64(key["e"]), "big")
    encoded_length = (modulus.bit_length() + 7) // 8
    if len(signature) != encoded_length:
        return False
    decrypted = pow(int.from_bytes(signature, "big"), exponent, modulus)
    return hmac.compare_digest(decrypted.to_bytes(encoded_length, "big"), _expected_block(signing_input, algorithm, encoded_length))


def _expected_block(signing_input: str, algorithm: str, encoded_length: int) -> bytes:
    hash_name, digest_info = _DIGEST_INFO[algorithm]
    tail = digest_info + hashlib.new(hash_name, signing_input.encode()).digest()
    padding = b"\xff" * (encoded_length - len(tail) - 3)
    return b"\x00\x01" + padding + b"\x00" + tail
