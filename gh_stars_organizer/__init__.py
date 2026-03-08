__all__ = ["__version__"]

try:
    from ._version import version as __version__
except Exception:
    try:
        from importlib.metadata import PackageNotFoundError, version

        __version__ = version("gh-stars-organizer")
    except Exception:
        __version__ = "0.0.0"
