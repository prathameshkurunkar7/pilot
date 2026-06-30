"""
Parse and read the marketplace based on the current version of frappe running
Show install for apps that are compatibile with the version mentioned in the apps_v2.json only
When install is clicked instead of showing a dropdown of branches just install the expected frappe version compliant branch.
"""

import json
import shlex
import typing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from pilot.utils import run_command

if typing.TYPE_CHECKING:
    from pilot.core.bench import Bench

_REGISTRY_V2_PATH = Path(__file__).parent.parent.parent / "registry" / "apps_v2.json"


@dataclass
class Resolver:
    app: str
    repo: str
    target_type: Literal["tag", "branch", "target"]
    target: str
    frappe_version: str

    def resolve(self):
        """Resolve installation pattern taking the dependencies into account"""
        ...


@dataclass
class Marketplace:
    bench: "Bench"
    frappe_version: str = field(default="", init=False)

    def __post_init__(self):
        self.frappe_version = self.get_current_frappe_version()
        raw = json.loads(_REGISTRY_V2_PATH.read_text())
        self.registry = self._parse_registry(raw)

    def get_current_frappe_version(self) -> str:
        """We need the current framework version to correctly suggest apps for installation"""
        cmd = shlex.split(
            f"{self.bench.env_path / 'bin' / 'python'} -c 'import frappe; print(frappe.__version__)'",
        )
        result = run_command(cmd)
        return result.stdout.strip().decode()

    def _parse_registry(self, raw: list[dict]) -> list[dict]:
        for app in raw:
            for target in app.get("targets", []):
                # Loads in the >=17.0.0-dev,<18.0.0 version specifier for each target
                target["_spec"] = SpecifierSet(target["frappe_core"], prereleases=True)
        return raw

    def read_installable_apps(self) -> list[Resolver]:
        results = []
        current = Version(self.frappe_version)
        for app in self.registry:
            # Checks if the current version is supported in the apps version specifier targets
            # preloaded while parsing the registry.
            match = next((t for t in app.get("targets", []) if current in t["_spec"]), None)
            if match:
                results.append(
                    Resolver(
                        app=app["name"],
                        repo=app["repo"],
                        target_type=match["target_type"],
                        target=match["target"],
                        frappe_version=self.frappe_version,
                    )
                )
        return results


if __name__ == "__main__":
    from pilot.core.bench import Bench, BenchConfig

    bench = Bench(
        BenchConfig.from_file(Path("/home/frappe/bench-cli/benches/test/bench.toml")),
        Path("/home/frappe/bench-cli/benches/test"),
    )
    marketplace = Marketplace(bench)
    print(len(marketplace.registry))
    print(len(Marketplace(bench).read_installable_apps()))
