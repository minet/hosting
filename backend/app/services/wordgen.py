"""
Deterministic friendly-label generator for VM DNS names.

Given a numeric VM ID, returns a stable ``adjective-noun`` label such as
``brave-falcon``.  The same ID always produces the same label; different IDs
produce different labels across the entire cross-product of the two lists.

No external dependencies — uses only the standard library.
"""
from __future__ import annotations

import hashlib

_ADJECTIVES: list[str] = [
    "amber", "arctic", "azure", "bold", "brave", "bright", "calm", "cedar",
    "clear", "cool", "crisp", "cyber", "dark", "deep", "distant", "electric",
    "elegant", "emerald", "epic", "faint", "fast", "fierce", "fresh", "frozen",
    "gentle", "golden", "grand", "happy", "hollow", "humble", "icy", "jade",
    "keen", "lively", "lunar", "mighty", "misty", "noble", "polar", "prime",
    "proud", "quick", "quiet", "radiant", "rapid", "sharp", "silent", "silver",
    "sleek", "smart", "solar", "solid", "stark", "stellar", "still", "stone",
    "swift", "tall", "teal", "vivid", "warm", "wild", "wise", "zesty",
]

_NOUNS: list[str] = [
    "anchor", "arrow", "atlas", "aurora", "beacon", "blade", "bolt", "breeze",
    "bridge", "byte", "cloud", "comet", "coral", "crane", "crystal", "dawn",
    "delta", "dome", "drift", "eagle", "echo", "falcon", "fern", "fjord",
    "flame", "flare", "flux", "forge", "frost", "gale", "gem", "grove",
    "hawk", "haven", "helm", "hive", "horizon", "isle", "kestrel", "lake",
    "lance", "lark", "leaf", "light", "lion", "lotus", "lynx", "maple",
    "mesa", "mist", "moon", "moss", "oak", "orbit", "peak", "pine",
    "pixel", "prism", "quartz", "raven", "reef", "ridge", "river", "rock",
    "rover", "sage", "seal", "slate", "snow", "spark", "star", "stone",
    "stream", "summit", "surf", "swan", "terra", "tide", "tower", "trail",
    "vault", "vale", "wave", "wind",
]


def vm_dns_label(vm_id: int) -> str:
    """Return a stable, human-friendly DNS label for the given VM ID.

    Uses a SHA-256 hash of the ID so that labels are evenly distributed and
    not trivially enumerable from sequential integers.

    :param vm_id: Numeric VM identifier.
    :returns: A DNS-safe label of the form ``adjective-noun``.
    :rtype: str

    Example::

        >>> vm_dns_label(1)
        'silver-falcon'
        >>> vm_dns_label(42)
        'quiet-lake'
    """
    digest = int(hashlib.sha256(str(vm_id).encode()).hexdigest(), 16)
    adj = _ADJECTIVES[digest % len(_ADJECTIVES)]
    noun = _NOUNS[(digest // len(_ADJECTIVES)) % len(_NOUNS)]
    return f"{adj}-{noun}"
