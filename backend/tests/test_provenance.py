from __future__ import annotations

import pytest
from pydantic import ValidationError

from kitchen_almanac.provenance import MeasurementRange


def test_measurement_range_requires_ordered_values_and_unit() -> None:
    measurement = MeasurementRange(low=50, expected=60, high=75, unit="days")
    assert measurement.expected == 60

    with pytest.raises(ValidationError, match="low <= expected <= high"):
        MeasurementRange(low=75, expected=60, high=50, unit="days")
