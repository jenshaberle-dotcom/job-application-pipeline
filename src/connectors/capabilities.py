from dataclasses import dataclass


@dataclass(frozen=True)
class SourceCapabilities:
    """Describes which filters a source can apply server-side."""

    supports_keyword: bool
    supports_location: bool
    supports_radius: bool
    supports_employment_type: bool
    supports_remote_filter: bool
    supports_pagination: bool
    supports_full_fetch: bool
