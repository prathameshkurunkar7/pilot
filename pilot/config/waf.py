import re
from dataclasses import dataclass, field

from pilot.exceptions import ConfigError

# The only accepted values for WafConfig.mode, in UI order. Single source of
# truth: WafConfig.validate(), the settings API, and the admin UI all
# reference this rather than repeating the literals.
WAF_MODES = ("Off", "DetectionOnly", "On")

_SIZE_UNITS = {"k": 1024, "m": 1024**2, "g": 1024**3}
_WAF_EXEMPT_PATH_PATTERN = re.compile(r"^/[A-Za-z0-9._~%/-]*$")


def parse_nginx_size(value: str) -> int:
    """Bytes for an nginx size string ('50m', '1g', '13107200'). Suffixes k/m/g
    are powers of 1024; a bare number is bytes. Raises ValueError on garbage."""
    text = str(value).strip().lower()
    if not text:
        raise ValueError("empty size")
    if text[-1] in _SIZE_UNITS:
        return int(text[:-1]) * _SIZE_UNITS[text[-1]]
    return int(text)


@dataclass
class WafConfig:
    """ModSecurity (layer-7 WAF) settings applied to every nginx vhost of the bench.

    Runs the OWASP Core Rule Set. ``mode`` maps to ``SecRuleEngine``:
    "DetectionOnly" logs matches without blocking (the safe default for a
    monitor-first rollout), "On" enforces, "Off" disables inspection. ``enabled``
    is the master switch; when off, no ModSecurity directives are emitted at all.

    ``paranoia`` is the CRS blocking paranoia level (1 = fewest false positives,
    4 = most aggressive). ``inbound_threshold`` is the anomaly score at which a
    request is blocked. ``body_limit`` caps the request body ModSecurity buffers
    for inspection and must be >= nginx's ``client_max_body_size``. ``exclusions``
    are raw SecLang lines (e.g. ``SecRuleRemoveById``) applied after the CRS to
    silence false positives; ``exempt_paths`` are location prefixes that bypass
    the WAF entirely.
    """

    enabled: bool = False
    mode: str = "DetectionOnly"  # "DetectionOnly" | "On" | "Off"
    paranoia: int = 1
    inbound_threshold: int = 5
    body_limit: str = "50m"
    inspect_responses: bool = False
    exclusions: list[str] = field(default_factory=list)
    exempt_paths: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict | None) -> "WafConfig":
        if not data:
            return cls()
        # paranoia/inbound_threshold pass through unconverted so a hand-edited
        # non-integer surfaces as a clean ConfigError in validate() rather
        # than a raw ValueError here.
        return cls(
            enabled=bool(data.get("enabled", False)),
            mode=str(data.get("mode", "DetectionOnly")),
            paranoia=data.get("paranoia", 1),
            inbound_threshold=data.get("inbound_threshold", 5),
            body_limit=str(data.get("body_limit", "50m")),
            inspect_responses=bool(data.get("inspect_responses", False)),
            exclusions=[str(line) for line in data.get("exclusions", [])],
            exempt_paths=[str(path) for path in data.get("exempt_paths", [])],
        )

    def validate(self, nginx_max_body_size: str) -> None:
        if self.mode not in WAF_MODES:
            raise ConfigError(f"waf.mode '{self.mode}' is invalid. Must be one of: {', '.join(WAF_MODES)}.")
        if not isinstance(self.paranoia, int) or not 1 <= self.paranoia <= 4:
            raise ConfigError(f"waf.paranoia '{self.paranoia}' is invalid. Must be an integer between 1 and 4.")
        if not isinstance(self.inbound_threshold, int) or self.inbound_threshold < 1:
            raise ConfigError(f"waf.inbound_threshold '{self.inbound_threshold}' is invalid. Must be a positive integer.")
        try:
            body_limit = parse_nginx_size(self.body_limit)
        except ValueError:
            raise ConfigError(f"waf.body_limit '{self.body_limit}' is not a valid size (e.g. '50m', '13107200').")
        # Coupling only matters when the WAF is on: a body larger than what
        # ModSecurity buffers would be proxied to the app uninspected.
        if self.enabled and body_limit < parse_nginx_size(nginx_max_body_size):
            raise ConfigError(
                f"waf.body_limit '{self.body_limit}' must be >= nginx.client_max_body_size "
                f"'{nginx_max_body_size}', else large uploads bypass inspection."
            )
        for i, path in enumerate(self.exempt_paths):
            if len(path) > 255 or not _WAF_EXEMPT_PATH_PATTERN.match(path):
                raise ConfigError(
                    f"waf.exempt_paths[{i}] '{path}' is invalid. Must be a URL path starting "
                    f"with '/' using only letters, digits, and . _ ~ % / - characters."
                )
