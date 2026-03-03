"""Runtime configuration bootstrap utilities."""


def bootstrap_runtime_config() -> None:
    from .runtime import bootstrap_runtime_config as _bootstrap_runtime_config

    _bootstrap_runtime_config()


__all__ = ["bootstrap_runtime_config"]
