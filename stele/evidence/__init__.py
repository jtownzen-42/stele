"""Compliance Vault: a timestamped evidence package for one vault item.

The package is one ZIP holding provenance.json, the license files, a
CycloneDX SBOM, the checksums, and the docs. Times come from the PC's own
clock only; nothing here contacts a time server or a timestamp authority.
"""
