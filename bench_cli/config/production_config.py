from dataclasses import dataclass

VALID_PROCESS_MANAGERS = ("none", "supervisor", "systemd", "openrc")


@dataclass
class ProductionConfig:
    process_manager: str = "none"  # none | supervisor | systemd | openrc
    nginx: bool = False

    @property
    def enabled(self) -> bool:
        return self.process_manager != "none"
