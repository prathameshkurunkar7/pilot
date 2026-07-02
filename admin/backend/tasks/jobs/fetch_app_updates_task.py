import json
from typing import TYPE_CHECKING

from admin.backend.readers.app_reader import AppReader
from pilot.core.marketplace import Marketplace

from .base_task import BaseTask

if TYPE_CHECKING:
    from pilot.core.app import App


class FetchAppUpdatesTask(BaseTask):
    @classmethod
    def _parser(cls):
        p = super()._parser()
        return p

    def __init__(self, bench, bench_root, args):
        super().__init__(bench, bench_root, args)
        # Index the registry by name once so each app is an O(1) lookup.
        self._marketplace_by_name = {app["name"]: app for app in Marketplace.registry()}

    @staticmethod
    def _is_on_target_revision(bench_app: "App", target: dict) -> bool:
        target_type, ref = target["target_type"], target["target"]
        if target_type == "tag":
            return bench_app.installed_tag == ref
        if target_type == "commit":
            return bool(bench_app.installed_hash) and bench_app.installed_hash.startswith(ref)
        return False

    def _is_pinned_by_marketplace(self, name: str) -> bool:
        """Whether the marketplace pins this app to a fixed revision it is still on.

        A commit/tag target pins the app only while it is actually checked out at
        that revision. If the marketplace now points at a different tag/commit than
        the app's current one, the update is allowed so it can move forward. Branch
        targets are always updatable.
        """
        app = self._marketplace_by_name.get(name)
        if not app:
            return False
        bench_app = self.bench.app(name)
        if bench_app.config.repo != app["repo"]:
            return False

        version = bench_app.installed_version
        return any(target["version"] == version and self._is_on_target_revision(bench_app, target) for target in app["targets"])

    def run(self) -> None:
        # No trailing "done" step: Sites.vue reads output[-1] as the JSON result,
        # so the dumped JSON must stay the last line.
        self._step("fetch", "Check for app updates")
        apps_dir = self.bench_root / "apps"
        app_names = [d.name for d in sorted(apps_dir.iterdir()) if d.is_dir() and (d / ".git").exists()]
        apps_to_check = [name for name in app_names if not self._is_pinned_by_marketplace(name)]
        updates = AppReader(self.bench_root).check_remote_updates(apps_to_check)
        print(json.dumps(updates), flush=True)


if __name__ == "__main__":
    FetchAppUpdatesTask.main()
