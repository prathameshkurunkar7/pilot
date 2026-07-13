from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pytest

from pilot.commands import jwks
from pilot.commands.generate_session import _b64, decode_session_token, issue_token
from pilot.commands.jwks import verify_jwks_token

# Fixed 2048-bit RSA keypair (openssl-generated) so tests need no crypto library:
# tokens are signed here with `pow(block, D, N)`, mirroring the verifier.
N_B64U = "r0mcEtzxi9eu5vcXce0MeWB-16I-jmzk6IdSrmrYSSTFPX65ERxRcCP6S00zW8JeFjFlSJCiPIYxG-48C6_pitOc58731GZXy7XGS75amer3CcUnz_eLJkZt85FJQ5f4hjpQG8FHsL6EgvS_I15N98j8ckF1x8iATFORyhx_8W__ilbc1Sgb8XSIapZlNei33wl1XzTrpnnKZM5647hLa9-nrkLvVXHh3LGg6nv0cJ969JipBynQtnjhYunm2Lp3tJw2cznDWceaFC5AHkQIbJ9uwxIZ1LgfXruCM3IYH1uT9JoxmUR5h6mZVlwGbcCcgU0BMypu7skSgRTvubgOMQ"
E_B64U = "AQAB"
D = 965738692797157223609243464350015292322488599589498559388016588862366059032278574023086559761796787925093757511686509389252897886329793947667282792321462407021736677685231930343026644931298549745623638883052298004334415302332604933228009036353730540677355081280423677648935051923901340654602103028808001179290730837095110075664827301834136997044174028679042195782455510766868051569145563185859289450529981687025916886423187343413246116807983193523122554650209156392288317244495570666026308402289993913970636797530621396149759245567683628521757293598174936135020245384912078217261718702446969786202967607575674250205
N = 22128001646655814339193772895064051118936783620766355069176625534227037640345578500393680226242068382220739301125215895758576057609088613215023411366269270787163204840645763488817738739222974584277226263955457898543856157912410428986614466642955838980638692408661874508199722575976478336677093969477839340368159279495912794571104322310233776673569937984728040960306181924650729339623352642096161975694142394220762958145296929132396078918492147805943654094648324511008950541452501345804987035298046974261984645667831087436360717295624807222053169172424241324908830202484520357341479202742282301496317148544376319249969

JWKS_URL = "https://issuer.example.com/.well-known/jwks.json"


def _sign(signing_input: str) -> bytes:
    encoded_length = (N.bit_length() + 7) // 8
    tail = jwks._DIGEST_INFO["RS256"][1] + hashlib.sha256(signing_input.encode()).digest()
    block = b"\x00\x01" + b"\xff" * (encoded_length - len(tail) - 3) + b"\x00" + tail
    return pow(int.from_bytes(block, "big"), D, N).to_bytes(encoded_length, "big")


def _mint(claims: dict | None = None, kid: str = "test-key", alg: str = "RS256") -> str:
    now = int(time.time())
    payload = {"sub": "admin", "iat": now, "exp": now + 300, "scope": "bench", **(claims or {})}
    body = ".".join(_b64(json.dumps(p, separators=(",", ":")).encode()) for p in ({"alg": alg, "typ": "JWT", "kid": kid}, payload))
    return f"{body}.{_b64(_sign(body))}"


@pytest.fixture(autouse=True)
def _stub_jwks(monkeypatch):
    key = {"kty": "RSA", "kid": "test-key", "alg": "RS256", "use": "sig", "n": N_B64U, "e": E_B64U}
    monkeypatch.setattr(jwks, "_fetch_keys", lambda url: {"test-key": key})
    jwks._cache.clear()
    yield
    jwks._cache.clear()


# ── verifier ──────────────────────────────────────────────────────────────────


def test_valid_token_returns_claims() -> None:
    claims = verify_jwks_token(_mint({"scope": "site", "site": "a.com"}), JWKS_URL)
    assert claims and claims["site"] == "a.com"


def test_expired_token_rejected() -> None:
    assert verify_jwks_token(_mint({"exp": int(time.time()) - 10}), JWKS_URL) is None


def test_tampered_signature_rejected() -> None:
    assert verify_jwks_token(_mint()[:-4] + "AAAA", JWKS_URL) is None


def test_non_rsa_algorithm_rejected() -> None:
    assert verify_jwks_token(_mint(alg="HS256"), JWKS_URL) is None


def test_unknown_kid_rejected() -> None:
    assert verify_jwks_token(_mint(kid="rotated-away"), JWKS_URL) is None


def test_no_jwks_url_rejected() -> None:
    assert verify_jwks_token(_mint(), "") is None


def test_unreachable_endpoint_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(jwks, "_fetch_keys", lambda url: {})
    jwks._cache.clear()
    assert verify_jwks_token(_mint(), JWKS_URL) is None


# ── unified session decoding ────────────────────────────────────────────────


class _Config:
    class admin:
        jwt_secret = "local-secret"
        jwks_url = JWKS_URL


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


def test_jwks_sid_login_without_jti_sets_cookie(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.post("/api/login", json={"sid": _mint()})
    assert resp.status_code == 200
    assert client.get("/api/benches/").status_code != 401


def test_jwks_site_scoped_bearer_is_enforced(tmp_path: Path) -> None:
    client = _client(tmp_path)
    ok = client.get("/api/sites/a.com/apps", headers={"Authorization": f"Bearer {_mint({'scope': 'site', 'site': 'a.com'})}"})
    denied = client.get("/api/sites/a.com/apps", headers={"Authorization": f"Bearer {_mint({'scope': 'site', 'site': 'other.com'})}"})
    assert ok.status_code != 403
    assert denied.status_code == 403
