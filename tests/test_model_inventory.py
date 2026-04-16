from regfinder.app_types import AppConfig
from regfinder.model_inventory import ModelInventory


def test_snapshot_refreshes_empty_inventory_without_hanging(monkeypatch, tmp_path):
    models_dir = tmp_path / "models"
    inventory_path = tmp_path / "model_inventory.json"

    monkeypatch.setattr("regfinder.model_inventory.get_models_directory", lambda: str(models_dir))
    monkeypatch.setattr(
        "regfinder.model_inventory.get_model_cache_path",
        lambda model_id, models_dir=None: str((tmp_path / "models" / model_id.replace("/", "__"))),
    )
    monkeypatch.setattr("regfinder.model_inventory.is_model_downloaded", lambda model_id, models_dir=None: False)

    inventory = ModelInventory(inventory_path=str(inventory_path))
    snapshot = inventory.snapshot()

    assert set(snapshot.keys()) == set(AppConfig.AVAILABLE_MODELS.keys())
    assert all(state["downloaded"] is False for state in snapshot.values())
