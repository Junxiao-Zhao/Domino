from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from hydra import compose, initialize_config_dir
from omegaconf import OmegaConf

from domino.runner import run


def main(argv: Sequence[str] | None = None) -> None:
    args, overrides = _parse_args(argv)
    config_dir = Path(args.config_path)
    if not config_dir.is_absolute():
        config_dir = Path.cwd() / config_dir

    with initialize_config_dir(config_dir=str(config_dir.resolve()), version_base=None):
        cfg = compose(config_name=args.config_name, overrides=list(overrides))

    print(OmegaConf.to_yaml(cfg, resolve=False))
    run(cfg)


def _parse_args(
    argv: Sequence[str] | None = None,
) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        prog="domino",
        description="Run a Hydra-configured domino workflow.",
    )
    parser.add_argument(
        "--config-path", required=True, help="Path to the config directory."
    )
    parser.add_argument(
        "--config-name", required=True, help="Config name without .yaml."
    )
    return parser.parse_known_args(argv)
