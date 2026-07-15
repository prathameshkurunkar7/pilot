from collections import Counter
from pathlib import Path

from admin.backend.api_contract import API_ROOT_PREFIX, API_V1_PREFIX
from admin.backend.app import create_app
from admin.backend.auth import AuthPolicy, endpoint_auth_policy


SITE_SCOPED_ENDPOINTS = {
    "sites.add_domain",
    "sites.backup_site",
    "sites.clear_cache",
    "sites.delete_backup_schedule",
    "sites.detail",
    "sites.domain_dns_records",
    "sites.download_backup",
    "sites.drop_site",
    "sites.enable_ssl",
    "sites.force_drop_site",
    "sites.force_uninstall_app",
    "sites.get_and_install_app",
    "sites.get_backup_schedule",
    "sites.install_app",
    "sites.list_backups",
    "sites.list_domains",
    "sites.login_to_site",
    "sites.migrate_site",
    "sites.offsite_backup_urls",
    "sites.reinstall_site",
    "sites.remove_domain",
    "sites.set_backup_schedule",
    "sites.set_primary_domain",
    "sites.site_apps",
    "sites.uninstall_app",
    "sites.update_config",
}


def auth_policy(app, endpoint: str) -> str:
    view = app.view_functions[endpoint]
    policy = endpoint_auth_policy(view)
    if policy != AuthPolicy.AUTHENTICATED:
        return policy.value
    if endpoint in SITE_SCOPED_ENDPOINTS:
        return "authenticated+site-scope"
    if endpoint.startswith(("benches.", "bench-readiness.")):
        return "authenticated+bench-management"
    return "authenticated"


def test_admin_route_inventory_matches_baseline(tmp_path: Path) -> None:
    app = create_app(tmp_path)
    routes = [
        (
            ",".join(sorted(rule.methods - {"HEAD", "OPTIONS"})),
            rule.rule,
            rule.endpoint,
            auth_policy(app, rule.endpoint),
        )
        for rule in app.url_map.iter_rules()
        if rule.rule.startswith(API_V1_PREFIX)
    ]
    areas = [
        path.removeprefix(f"{API_V1_PREFIX}/").split("/", 1)[0]
        for _, path, _, _ in routes
    ]
    unversioned = [
        rule.rule
        for rule in app.url_map.iter_rules()
        if rule.rule.startswith(f"{API_ROOT_PREFIX}/")
        and not rule.rule.startswith(f"{API_V1_PREFIX}/")
    ]

    assert len(routes) == 104
    assert unversioned == []
    assert len({(method, path) for method, path, _, _ in routes}) == 104
    assert Counter(method for method, _, _, _ in routes) == {
        "DELETE": 8,
        "GET": 50,
        "PATCH": 2,
        "POST": 43,
        "PUT": 1,
    }
    assert Counter(policy for _, _, _, policy in routes) == {
        "authenticated": 57,
        "authenticated+bench-management": 9,
        "authenticated+site-scope": 26,
        "open": 5,
        "setup-conditional": 7,
    }
    assert Counter(areas) == {
        "apps": 7,
        "bench-readiness-checks": 1,
        "benches": 8,
        "dashboard": 1,
        "database": 8,
        "git": 6,
        "bootstrap": 1,
        "health": 1,
        "logs": 4,
        "monitor-history": 1,
        "monitor-status": 1,
        "processes": 4,
        "settings": 4,
        "setup": 7,
        "sites": 30,
        "ssh-keys": 3,
        "stats": 1,
        "session": 3,
        "system-info": 1,
        "task-worker": 3,
        "tasks": 7,
        "updates": 2,
    }

    route_keys = {(method, path) for method, path, _, _ in routes}
    assert {
        ("GET", "/api/v1/benches"),
        ("POST", "/api/v1/benches"),
        ("GET", "/api/v1/benches/<name>"),
        ("DELETE", "/api/v1/benches/<name>"),
        ("POST", "/api/v1/benches/<name>/actions/start"),
        ("POST", "/api/v1/benches/<name>/actions/stop"),
        ("POST", "/api/v1/benches/<name>/actions/restart"),
        ("GET", "/api/v1/benches/domain-options"),
        ("POST", "/api/v1/bench-readiness-checks"),
    } <= route_keys
    assert {
        ("GET", "/api/v1/tasks"),
        ("POST", "/api/v1/tasks"),
        ("GET", "/api/v1/tasks/<task_id>"),
        ("DELETE", "/api/v1/tasks/<task_id>"),
        ("POST", "/api/v1/tasks/<task_id>/actions/retry"),
        ("GET", "/api/v1/tasks/<task_id>/events"),
        ("GET", "/api/v1/tasks/<task_id>/output/content"),
        ("GET", "/api/v1/task-worker"),
        ("POST", "/api/v1/task-worker/actions/start"),
        ("POST", "/api/v1/task-worker/actions/stop"),
    } <= route_keys
    assert {
        ("GET", "/api/v1/setup/configuration"),
        ("PUT", "/api/v1/setup/configuration"),
        ("GET", "/api/v1/setup/framework-branches"),
        ("POST", "/api/v1/setup/database-validations"),
        ("POST", "/api/v1/setup/actions/start"),
        ("POST", "/api/v1/setup/actions/finish"),
        ("POST", "/api/v1/setup/new-site"),
    } <= route_keys
    assert not {
        path
        for _, path, _, _ in routes
        if path in {
            "/api/v1/tasks/",
            "/api/v1/tasks/run",
            "/api/v1/tasks/<task_id>/kill",
            "/api/v1/tasks/<task_id>/rerun",
            "/api/v1/tasks/<task_id>/stream",
            "/api/v1/tasks/<task_id>/output/download",
            "/api/v1/setup/stream/<task_id>",
            "/api/v1/setup/config",
            "/api/v1/setup/framework_branches",
            "/api/v1/setup/save",
            "/api/v1/setup/validate-mariadb",
            "/api/v1/setup/validate-postgres",
            "/api/v1/setup/start",
            "/api/v1/setup/finish",
            "/api/v1/benches/",
            "/api/v1/benches/new",
            "/api/v1/benches/wildcard-domains",
            "/api/v1/benches/ready",
            "/api/v1/benches/<name>/actions/<action_name>",
        }
    }
