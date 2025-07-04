"""Test initialization of the AI Task component."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components import media_source
from homeassistant.components.ai_task import AITaskPreferences
from homeassistant.components.ai_task.const import DATA_PREFERENCES
from homeassistant.core import HomeAssistant

from .conftest import TEST_ENTITY_ID, MockAITaskEntity

from tests.common import flush_store


async def test_preferences_storage_load(
    hass: HomeAssistant,
) -> None:
    """Test that AITaskPreferences are stored and loaded correctly."""
    preferences = AITaskPreferences(hass)
    await preferences.async_load()

    # Initial state should be None for entity IDs
    for key in AITaskPreferences.KEYS:
        assert getattr(preferences, key) is None, f"Initial {key} should be None"

    new_values = {key: f"ai_task.test_{key}" for key in AITaskPreferences.KEYS}

    preferences.async_set_preferences(**new_values)

    # Verify that current preferences object is updated
    for key, value in new_values.items():
        assert getattr(preferences, key) == value, (
            f"Current {key} should match set value"
        )

    await flush_store(preferences._store)

    # Create a new preferences instance to test loading from store
    new_preferences_instance = AITaskPreferences(hass)
    await new_preferences_instance.async_load()

    for key in AITaskPreferences.KEYS:
        assert getattr(preferences, key) == getattr(new_preferences_instance, key), (
            f"Loaded {key} should match saved value"
        )


@pytest.mark.parametrize(
    ("set_preferences", "msg_extra"),
    [
        (
            {"gen_data_entity_id": TEST_ENTITY_ID},
            {},
        ),
        (
            {},
            {
                "entity_id": TEST_ENTITY_ID,
                "attachments": [
                    {
                        "media_content_id": "media-source://mock/blah_blah_blah.mp4",
                        "media_content_type": "video/mp4",
                    }
                ],
            },
        ),
    ],
)
async def test_generate_data_service(
    hass: HomeAssistant,
    init_components: None,
    freezer: FrozenDateTimeFactory,
    set_preferences: dict[str, str | None],
    msg_extra: dict[str, str],
    mock_ai_task_entity: MockAITaskEntity,
) -> None:
    """Test the generate data service."""
    preferences = hass.data[DATA_PREFERENCES]
    preferences.async_set_preferences(**set_preferences)

    with patch(
        "homeassistant.components.media_source.async_resolve_media",
        return_value=media_source.PlayMedia(
            url="http://example.com/media.mp4",
            mime_type="video/mp4",
        ),
    ):
        result = await hass.services.async_call(
            "ai_task",
            "generate_data",
            {
                "task_name": "Test Name",
                "instructions": "Test prompt",
            }
            | msg_extra,
            blocking=True,
            return_response=True,
        )

    assert result["data"] == "Mock result"

    assert len(mock_ai_task_entity.mock_generate_data_tasks) == 1
    task = mock_ai_task_entity.mock_generate_data_tasks[0]

    assert len(task.attachments) == len(
        msg_attachments := msg_extra.get("attachments", [])
    )

    for msg_attachment, attachment in zip(
        msg_attachments, task.attachments, strict=False
    ):
        assert attachment.url == "http://example.com/media.mp4"
        assert attachment.mime_type == "video/mp4"
        assert attachment.media_content_id == msg_attachment["media_content_id"]
