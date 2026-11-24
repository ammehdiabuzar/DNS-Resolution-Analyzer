"""DNS Resolution Analyzer: an iterative resolver built from raw DNS packets."""

from .message import build_query, parse_message, encode_name, decode_name  # noqa: F401
from .resolver import IterativeResolver, Resolution, Step, format_step  # noqa: F401

__version__ = "1.0.0"
