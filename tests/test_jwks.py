from __future__ import annotations

import json
import time
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from jwt import PyJWKClient
from jwt.algorithms import ECAlgorithm, RSAAlgorithm

from admin.backend import jwks
from admin.backend.auth import decode_session_token
from admin.backend.jwks import verify_jwks_token
from pilot.commands.generate_session import issue_token

JWKS_URL = "https://issuer.example.com/.well-known/jwks.json"

# One RSA and one EC keypair the "remote issuer" signs with; the public halves
# are published in the stubbed JWKS document below.
_RSA = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_EC = ec.generate_private_key(ec.SECP256R1())


def _jwks_document() -> dict:
    rsa_jwk = json.loads(RSAAlgorithm.to_jwk(_RSA.public_key()))
    rsa_jwk.update(kid="rsa-key", alg="RS256", use="sig")
    ec_jwk = json.loads(ECAlgorithm.to_jwk(_EC.public_key()))
    ec_jwk.update(kid="ec-key", alg="ES256", use="sig")
    return {"keys": [rsa_jwk, ec_jwk]}


def _mint(key=_RSA, alg: str = "RS256", kid: str = "rsa-key", **claims) -> str:
    payload = {"sub": "admin", "scope": "bench", "exp": int(time.time()) + 300, **claims}
    return jwt.encode(payload, key, algorithm=alg, headers={"kid": kid})


@pytest.fixture(autouse=True)
def _stub_fetch(monkeypatch):
    monkeypatch.setattr(PyJWKClient, "fetch_data", lambda self: _jwks_document())
    jwks._clients.clear()
    yield
    jwks._clients.clear()


# ── verifier ──────────────────────────────────────────────────────────────────


def test_rsa_token_verifies() -> None:
    claims = verify_jwks_token(_mint(scope="site", site="a.com"), JWKS_URL)
    assert claims and claims["site"] == "a.com"


def test_ec_token_verifies() -> None:
    # The reason for switching to PyJWT: EC (ES256) keys work too.
    claims = verify_jwks_token(_mint(_EC, alg="ES256", kid="ec-key"), JWKS_URL)
    assert claims and claims["sub"] == "admin"


def test_expired_token_rejected() -> None:
    assert verify_jwks_token(_mint(exp=int(time.time()) - 10), JWKS_URL) is None


def test_tampered_signature_rejected() -> None:
    assert verify_jwks_token(_mint()[:-4] + "AAAA", JWKS_URL) is None


def test_unknown_kid_rejected() -> None:
    assert verify_jwks_token(_mint(kid="rotated-away"), JWKS_URL) is None


def test_symmetric_algorithm_not_accepted() -> None:
    # A published public key must never be replayable as an HMAC secret.
    forged = jwt.encode({"sub": "admin", "exp": int(time.time()) + 300}, "x" * 32, algorithm="HS256", headers={"kid": "rsa-key"})
    assert verify_jwks_token(forged, JWKS_URL) is None


def test_no_jwks_url_rejected() -> None:
    assert verify_jwks_token(_mint(), "") is None


# ── audience binding ──────────────────────────────────────────────────────────


def test_audience_accepted_when_matching() -> None:
    assert verify_jwks_token(_mint(aud="bench-a"), JWKS_URL, "bench-a")


def test_audience_rejected_when_mismatched() -> None:
    assert verify_jwks_token(_mint(aud="bench-b"), JWKS_URL, "bench-a") is None


def test_audience_required_but_absent_rejected() -> None:
    assert verify_jwks_token(_mint(), JWKS_URL, "bench-a") is None


def test_no_audience_config_ignores_aud_claim() -> None:
    assert verify_jwks_token(_mint(aud="anything"), JWKS_URL)


# ── unified session decoding ────────────────────────────────────────────────


class _Config:
    class admin:
        jwt_secret = "local-secret"
        jwks_url = JWKS_URL
        jwks_audience = ""


def test_session_decode_accepts_local_secret() -> None:
    assert decode_session_token(issue_token("local-secret"), _Config)["scope"] == "bench"


def test_session_decode_falls_back_to_jwks() -> None:
    assert decode_session_token(_mint(), _Config)["sub"] == "admin"


def test_session_decode_rejects_unknown() -> None:
    assert decode_session_token(issue_token("stranger"), _Config) is None


def test_session_decode_skips_jwks_when_unconfigured() -> None:
    class NoJwks:
        class admin:
            jwt_secret = "local-secret"
            jwks_url = ""

    assert decode_session_token(_mint(), NoJwks) is None


# ── admin backend integration ─────────────────────────────────────────────────


def _client(tmp_path: Path):
    from admin.backend.app import create_app
    from pilot.config.bench_config import BenchConfig
    from pilot.config.bench_toml_builder import BenchTomlBuilder
    from pilot.config.toml_writer import bench_config_to_toml

    bench_root = tmp_path / "benches" / "current"
    bench_root.mkdir(parents=True)
    toml_path = bench_root / "bench.toml"
    toml_path.write_text(BenchTomlBuilder(bench_root.name, {"admin_enabled": True, "admin_password": "secret"}).render())
    config = BenchConfig.from_file(toml_path)
    config.admin.jwt_secret = "local-secret"
    config.admin.jwks_url = JWKS_URL
    toml_path.write_text(bench_config_to_toml(config))
    (bench_root / "env" / "bin").mkdir(parents=True)
    (bench_root / "env" / "bin" / "python").touch()
    app = create_app(bench_root)
    app.config["TESTING"] = True
    return app.test_client()


def test_jwks_bearer_token_authenticates(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.get("/api/benches/", headers={"Authorization": f"Bearer {_mint()}"})
    assert resp.status_code != 401


def test_jwks_ec_bearer_token_authenticates(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.get("/api/benches/", headers={"Authorization": f"Bearer {_mint(_EC, alg='ES256', kid='ec-key')}"})
    assert resp.status_code != 401


def test_jwks_sid_login_with_jti_sets_cookie(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.post("/api/login", json={"sid": _mint(jti="login-1")})
    assert resp.status_code == 200
    assert client.get("/api/benches/").status_code != 401


def test_jwks_sid_login_requires_jti(tmp_path: Path) -> None:
    # A token without a jti must not be exchangeable for a session (else it is
    # replayable until expiry).
    client = _client(tmp_path)
    assert client.post("/api/login", json={"sid": _mint()}).status_code == 401


def test_jwks_sid_login_is_single_use(tmp_path: Path) -> None:
    client = _client(tmp_path)
    sid = _mint(jti="login-2")
    assert client.post("/api/login", json={"sid": sid}).status_code == 200
    assert client.post("/api/login", json={"sid": sid}).status_code == 401


def test_jwks_site_scoped_token_cannot_bootstrap_session(tmp_path: Path) -> None:
    # A site-scoped token (even with a jti) must not escalate to a bench session.
    client = _client(tmp_path)
    resp = client.post("/api/login", json={"sid": _mint(jti="login-3", scope="site", site="a.com")})
    assert resp.status_code == 401


def test_jwks_site_scoped_bearer_is_enforced(tmp_path: Path) -> None:
    client = _client(tmp_path)
    ok = client.get("/api/sites/a.com/apps", headers={"Authorization": f"Bearer {_mint(scope='site', site='a.com')}"})
    denied = client.get("/api/sites/a.com/apps", headers={"Authorization": f"Bearer {_mint(scope='site', site='other.com')}"})
    assert ok.status_code != 403
    assert denied.status_code == 403
