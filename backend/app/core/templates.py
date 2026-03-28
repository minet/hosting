"""Shared Jinja2 environment for email and other templates."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
jinja_env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), autoescape=True)
