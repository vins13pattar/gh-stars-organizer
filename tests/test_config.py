from pathlib import Path

from gh_stars_organizer.config import AppConfig, load_config, save_config


def test_load_config_creates_default(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    cfg = load_config(config_path)
    assert cfg.model == "gpt-4.1-mini"
    assert config_path.exists()


def test_save_and_load_roundtrip(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    cfg = AppConfig(model="gpt-4o-mini", categories=["a", "b", "other"])
    save_config(cfg, config_path)
    loaded = load_config(config_path)
    assert loaded.model == "gpt-4o-mini"
    assert loaded.categories == ["a", "b", "other"]

