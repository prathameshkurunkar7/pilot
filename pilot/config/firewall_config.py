from dataclasses import dataclass, field


@dataclass
class FirewallRule:
    """One HTTP/HTTPS firewall rule: allow or deny an IPv4/IPv6 address or CIDR."""

    ip: str
    action: str = "deny"  # "allow" | "deny"
    description: str = ""


@dataclass
class FirewallConfig:
    """IP allow/block list applied to every nginx vhost of the bench.

    ``default`` is the policy for clients no rule matches: "allow" (blocklist
    mode) or "deny" (allowlist mode). ``enabled`` is a master switch; when off,
    nginx serves everyone regardless of rules.
    """

    enabled: bool = False
    default: str = "allow"  # "allow" | "deny"
    rules: list[FirewallRule] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict | None) -> "FirewallConfig":
        if not data:
            return cls()
        rules = [
            FirewallRule(
                ip=str(rule.get("ip", "")),
                action=str(rule.get("action", "deny")),
                description=str(rule.get("description", "")),
            )
            for rule in data.get("rules", [])
        ]
        return cls(
            enabled=bool(data.get("enabled", False)),
            default=str(data.get("default", "allow")),
            rules=rules,
        )
