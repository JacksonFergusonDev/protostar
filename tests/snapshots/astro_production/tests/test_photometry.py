"""Tests for the photometry helpers."""

import numpy as np

from demo_project.photometry import magnitude


def test_a_hundredfold_flux_is_five_magnitudes_brighter() -> None:
    """Magnitudes fall by five for every factor of a hundred in flux."""
    np.testing.assert_allclose(magnitude([1.0, 100.0], zero_point=20.0), [20.0, 15.0])
