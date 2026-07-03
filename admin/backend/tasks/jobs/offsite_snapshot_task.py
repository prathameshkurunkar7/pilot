import sys

from pilot.integrations.s3.snapshots import OffsiteSnapshot

from .base_task import BaseTask


class OffsiteSnapshotTask(BaseTask):
    @classmethod
    def _parser(cls):
        p = super()._parser()
        p.add_argument("dataset")
        p.add_argument("tag")
        return p

    def __init__(self, bench, bench_root, args):
        super().__init__(bench, bench_root, args)
        self.dataset = args.dataset
        self.tag = args.tag

    def run(self) -> None:
        from pilot.managers.volume_manager import VolumeManager

        self._step("upload", f"Upload snapshot {self.tag}")
        try:
            offsite_snapshot = OffsiteSnapshot.from_config(self.bench.config.s3)
            offsite_snapshot.upload(self.bench.config.name, self.tag, self.dataset)
        except Exception as e:
            print(f"Offsite snapshot upload failed: {e}")
            sys.exit(1)

        self._step("cleanup", "Remove local snapshot copy")
        try:
            VolumeManager(self.bench.config.volume).destroy_snapshot(self.dataset, self.tag)
        except Exception as e:
            # Upload already succeeded, so the snapshot is safe offsite. Failing to
            # remove the local copy is a non-fatal cleanup issue, not a task failure.
            print(f"Offsite upload succeeded, but local cleanup failed: {e}")

        self._step("done")


if __name__ == "__main__":
    OffsiteSnapshotTask.main()
