"""Isolated contracts for the blog + market + visual feedback loop.

Nothing in this package is wired to a production worker.  Importing it has no
network, database, publication, affiliate, image-generation, or filesystem
side effects.
"""

from .core import ContractError, canonical_digest, validate_receipt

__all__ = ["ContractError", "canonical_digest", "validate_receipt"]
