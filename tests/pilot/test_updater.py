from __future__ import annotations

from unittest.mock import patch

from pilot import updater


def test_update_available_true_when_tag_differs() -> None:
    with (
        patch.object(updater.pilot, "__version__", "v0.0.1-pre-alpha"),
        patch.object(updater, "latest_release", return_value={"tag": "v0.0.2-pre-alpha", "asset_url": "x"}),
    ):
        available, latest = updater.update_available()

    assert available is True
    assert latest == "v0.0.2-pre-alpha"


def test_update_available_false_on_same_tag() -> None:
    with (
        patch.object(updater.pilot, "__version__", "v0.0.2-pre-alpha"),
        patch.object(updater, "latest_release", return_value={"tag": "v0.0.2-pre-alpha", "asset_url": "x"}),
    ):
        available, latest = updater.update_available()

    assert available is False
    assert latest == "v0.0.2-pre-alpha"


def test_update_available_false_when_no_release() -> None:
    with patch.object(updater, "latest_release", return_value=None):
        available, latest = updater.update_available()

    assert available is False
    assert latest is None


def test_perform_upgrade_routes_to_dev_when_dev_build() -> None:
    with (
        patch.object(updater.pilot, "is_dev_build", True),
        patch.object(updater, "_upgrade_dev") as dev,
        patch.object(updater, "_upgrade_release") as release,
    ):
        updater.perform_upgrade()

    dev.assert_called_once()
    release.assert_not_called()


def test_perform_upgrade_routes_to_release_when_not_dev() -> None:
    with (
        patch.object(updater.pilot, "is_dev_build", False),
        patch.object(updater, "_upgrade_dev") as dev,
        patch.object(updater, "_upgrade_release") as release,
    ):
        updater.perform_upgrade()

    release.assert_called_once()
    dev.assert_not_called()
