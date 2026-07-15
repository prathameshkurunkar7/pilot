import json

from admin.backend.views.sites import _public_config
from tests.test_admin_app import _client


def test_public_site_config_hides_system_and_secret_like_fields() -> None:
    config = {
        "developer_mode": 1,
        "maintenance_mode": 0,
        "pause_scheduler": 1,
        "frappe_branch": "version-16",
        "db_password": "database-secret",
        "encryption_key": "encryption-secret",
        "pilot_auth_token": "session-secret",
        "future_provider_api_token": "unknown-secret",
        "apiKey": "camel-secret",
        "apiKeys": ["camel-secret"],
        "accessKey": "camel-secret",
        "key": "generic-secret",
        "custom_provider": {
            "endpoint": "https://provider.example",
            "access_token": "nested-secret",
            "options": [
                {"region": "eu", "client_secret": "list-secret"},
                "unchanged",
            ],
        },
        "unreviewed_option": True,
    }

    assert _public_config(config) == {
        "developer_mode": 1,
        "maintenance_mode": 0,
        "pause_scheduler": 1,
        "frappe_branch": "version-16",
        "custom_provider": {
            "endpoint": "https://provider.example",
            "options": [{"region": "eu"}, "unchanged"],
        },
        "unreviewed_option": True,
    }


def test_public_site_config_copies_mutable_values() -> None:
    config = {"maintenance_mode": {"enabled": True}}

    public = _public_config(config)
    public["maintenance_mode"]["enabled"] = False

    assert config["maintenance_mode"] == {"enabled": True}


def test_site_detail_preserves_custom_keys_without_exposing_secrets(tmp_path) -> None:
    bench_root = tmp_path / "benches" / "current"
    client = _client(bench_root)
    site_dir = bench_root / "sites" / "s.localhost"
    site_dir.mkdir(parents=True)
    (site_dir / "site_config.json").write_text(json.dumps({
        "installed_apps": [],
        "db_name": "private-database-name",
        "db_host": "private-database-host",
        "developer_mode": 1,
        "custom_app_mode": "strict",
        "future_provider_api_token": "unknown-secret",
    }))

    response = client.get("/api/v1/sites/s.localhost")

    assert response.status_code == 200
    body = response.get_json()
    assert body["site_config"] == {
        "developer_mode": 1,
        "custom_app_mode": "strict",
    }
    assert "db_name" not in body
    assert "db_host" not in body
    assert "db_type" not in body


def test_site_config_update_preserves_hidden_custom_keys(tmp_path) -> None:
    bench_root = tmp_path / "benches" / "current"
    client = _client(bench_root)
    config_path = bench_root / "sites" / "s.localhost" / "site_config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "installed_apps": [],
                "developer_mode": 0,
                "future_provider_api_token": "unknown-secret",
                "custom_credential": {"value": "also-hidden"},
                "custom_provider": {
                    "endpoint": "https://old.example",
                    "accessToken": "nested-secret",
                    "regions": [
                        {"name": "eu", "apiKey": "region-secret"},
                    ],
                },
            }
        )
    )

    response = client.patch(
        "/api/v1/sites/s.localhost/config",
        json={
            "developer_mode": 1,
            "custom_provider": {
                "endpoint": "https://new.example",
                "regions": [{"name": "europe"}],
            },
        },
    )

    assert response.status_code == 200
    assert json.loads(config_path.read_text()) == {
        "developer_mode": 1,
        "installed_apps": [],
        "future_provider_api_token": "unknown-secret",
        "custom_credential": {"value": "also-hidden"},
        "custom_provider": {
            "endpoint": "https://new.example",
            "accessToken": "nested-secret",
            "regions": [
                {"name": "europe", "apiKey": "region-secret"},
            ],
        },
    }


def test_site_detail_rejects_symlinked_site(tmp_path) -> None:
    bench_root = tmp_path / "benches" / "current"
    client = _client(bench_root)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "site_config.json").write_text(json.dumps({"installed_apps": []}))
    sites = bench_root / "sites"
    sites.mkdir()
    (sites / "linked.localhost").symlink_to(outside, target_is_directory=True)

    response = client.get("/api/v1/sites/linked.localhost")

    assert response.status_code == 404
