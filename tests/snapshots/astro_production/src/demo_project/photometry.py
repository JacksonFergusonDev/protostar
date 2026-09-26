"""Photometry helpers for demo-project."""

import numpy as np
import numpy.typing as npt


def magnitude(flux: npt.ArrayLike, zero_point: float = 0.0) -> npt.NDArray[np.float64]:
    """Converts fluxes to astronomical magnitudes.

    Args:
        flux: Fluxes, in the units the zero point is defined for.
        zero_point: The magnitude of a unit flux.

    Returns:
        The magnitude of each flux.
    """
    fluxes = np.asarray(flux, dtype=np.float64)
    magnitudes: npt.NDArray[np.float64] = zero_point - 2.5 * np.log10(fluxes)
    return magnitudes
