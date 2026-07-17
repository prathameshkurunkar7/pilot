import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from pilot.integrations.marketplace import Marketplace

from pilot.managers.task.base_task import BaseTask


class FetchAppUpdatesTask(BaseTask):
    command = "fetch-all-app-updates"

    @classmethod
    def _parser(cls):
        p = super()._parser()
        return p

    def __init__(self, bench, bench_root, args):
        super().__init__(bench, bench_root, args)
        # Index the registry by name once so each app is an O(1) lookup.
        self._marketplace_by_name = {app["name"]: app for app in Marketplace.registry()}

    def _check_update(self, name: str) -> bool:
        app = self.bench.app(name)
        return app.has_marketplace_update(self._marketplace_by_name.get(name))

    def run(self) -> None:
        # No trailing "done" step: Sites.vue reads output[-1] as the JSON result,
        # so the dumped JSON must stay the last line.
        self._step("fetch", "Check for app updates")
        apps_dir = self.bench_root / "apps"
        app_names = [d.name for d in sorted(apps_dir.iterdir()) if d.is_dir() and (d / ".git").exists()]

        updates: dict[str, bool] = {}
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(self._check_update, name): name for name in app_names}
            for future in as_completed(futures):
                updates[futures[future]] = future.result()

        print(json.dumps(updates), flush=True)


if __name__ == "__main__":
    FetchAppUpdatesTask.main()
