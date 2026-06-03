from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape


TEMPLATE_DIR = Path(__file__).parent / "templates"


def build_template_environment(template_dir: Path = TEMPLATE_DIR) -> Environment:
    """Build the Jinja2 environment for the Control Center UI.

    Boundary:
    - This renderer is presentation-only.
    - Business, gate and lifecycle decisions must be prepared before rendering.
    - Templates should consume ViewModel-shaped objects that can later be exposed
      as JSON to a React frontend.
    """

    return Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(enabled_extensions=("html", "xml")),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_template(template_name: str, context: dict[str, Any]) -> str:
    environment = build_template_environment()
    template = environment.get_template(template_name)
    return template.render(**context)
