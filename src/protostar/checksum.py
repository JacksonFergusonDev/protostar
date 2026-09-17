"""Pure exact-byte ownership gate for generated files and managed regions."""

from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True)
class ChecksumResult:
    """Accepted write, applied digest, and pending-update conflict."""

    write: bool
    digest: str | None
    conflict: bool = False


def checksum_gate(
    local: bytes | None,
    desired: bytes,
    baseline: str | None,
    *,
    overwrite: bool = False,
) -> ChecksumResult:
    """Decides an exact-byte update without adopting existing unowned content."""
    remote = sha256(desired).hexdigest()
    current = sha256(local).hexdigest() if local is not None else None
    if overwrite or (baseline is None and local is None):
        return ChecksumResult(local != desired, remote)
    if baseline is None:
        return ChecksumResult(False, None, local != desired)
    if current in (remote, baseline):
        return ChecksumResult(local != desired, remote)
    return ChecksumResult(False, baseline, remote != baseline)
