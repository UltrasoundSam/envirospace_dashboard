from datetime import date, datetime
from typing import Any

import pandas as pd

from envirospace_dashboard.dashboard import build_trend_figure
from envirospace_dashboard.database import get_readings


class FakeCursor:
    def __init__(self) -> None:
        self.query: str | None = None
        self.parameters: tuple[Any, ...] | None = None
        self.closed = False

    def execute(self, query: str, parameters: tuple[Any, ...]) -> None:
        self.query = query
        self.parameters = parameters

    def fetchall(self) -> list[tuple[Any, ...]]:
        return []

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self) -> None:
        self.fake_cursor = FakeCursor()

    def cursor(self) -> FakeCursor:
        return self.fake_cursor


def test_get_readings_includes_the_full_end_date() -> None:
    connection = FakeConnection()

    result = get_readings(
        connection,  # type: ignore[arg-type]
        "room101",
        date(2026, 11, 1),
        date(2026, 11, 7),
    )

    assert result == []
    assert connection.fake_cursor.parameters == (
        "room101",
        datetime(2026, 11, 1),
        datetime(2026, 11, 8),
    )
    assert connection.fake_cursor.closed


def test_trend_figure_uses_drag_to_zoom() -> None:
    frame = pd.DataFrame(
        {
            "recorded_at": [datetime(2026, 11, 1), datetime(2026, 11, 2)],
            "temperature": [20.0, 21.0],
        }
    )

    figure = build_trend_figure(frame, "temperature")

    assert figure.layout.dragmode == "zoom"
    assert figure.layout.title.text == "Temperature over time"
