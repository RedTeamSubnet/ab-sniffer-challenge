try:
    from .__version__ import __version__  # noqa: F401
except ImportError:
    __version__ = "0.0.0.dev0"
