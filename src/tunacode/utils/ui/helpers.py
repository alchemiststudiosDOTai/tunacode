"""
Module: tunacode.utils.ui.helpers

Provides DotDict for dot notation access to dictionary attributes.
"""


class DotDict(dict):
    """dot.notation access to dictionary attributes"""

    __getattr__ = dict.get
    __setattr__ = dict.__setitem__  # type: ignore[assignment]
    __delattr__ = dict.__delitem__  # type: ignore[assignment]
