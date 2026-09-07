"""
analysis.py — Fonctions pures d'analyse Farfield, portées de Farfield_MDA.ipynb.
"""
from __future__ import annotations

import numpy as np
from scipy import stats

EXTRAPOLATION_ANGLES = np.arange(76, 91)  # 76..90°
WAVELENGTH_DOWNSAMPLE = 100  # points cible pour la grille lambda du diagramme de bande
THETA_DOWNSAMPLE = 40        # points cible pour theta dans le diagramme de bande
PHI_DOWNSAMPLE = 19          # points cible pour phi (slider) dans le diagramme de bande
BAND_WAVELENGTH_RANGE = (400.0, 800.0)  # plage visible restreinte pour le diagramme de bande


def _downsample_indices(n: int, target: int) -> np.ndarray:
    if n <= target:
        return np.arange(n)
    return np.linspace(0, n - 1, target).round().astype(int)


def intensity_to_flux(angle: np.ndarray, data: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Retourne (flux_par_pas, flux_cumule_normalise_a_pi)."""
    flux = np.zeros(len(data))
    cumulative = np.zeros(len(data))
    for i in range(1, len(data)):
        delta_omega = 2 * np.pi * (
            np.cos(np.deg2rad(angle[i - 1])) - np.cos(np.deg2rad(angle[i]))
        )
        flux[i] = data[i] * delta_omega
    for j in range(1, len(data)):
        cumulative[j] = cumulative[j - 1] + flux[j]
    if np.max(cumulative) > 0:
        cumulative = np.pi * (cumulative / np.max(cumulative))
    return flux, cumulative


def flux_to_intensity(angle: np.ndarray, flux: np.ndarray) -> np.ndarray:
    intensity = np.zeros(len(flux))
    for i in range(1, len(flux)):
        delta_omega = 2 * np.pi * (
            np.cos(np.deg2rad(angle[i - 1])) - np.cos(np.deg2rad(angle[i]))
        )
        intensity[i] = flux[i] / delta_omega if delta_omega != 0 else 0.0
    if len(intensity) > 1:
        intensity[0] = intensity[1]
    return intensity


def extrapolate_farfield(theta: np.ndarray, sum_intensity_norm: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Régression linéaire sur les 10 derniers points mesurés, extrapolée à 76-90°."""
    slope, intercept, *_ = stats.linregress(theta[-10:], sum_intensity_norm[-10:])
    ff_extra = slope * EXTRAPOLATION_ANGLES + intercept

    theta_ext = np.append(theta, EXTRAPOLATION_ANGLES)
    ff_ext = np.append(sum_intensity_norm, ff_extra)
    ff_ext = np.where(ff_ext < 0, 0, ff_ext)
    return theta_ext, ff_ext


def ratio_at_angle(theta_ext: np.ndarray, cumulative_flux: np.ndarray,
                    cumulative_flux_lambertian: np.ndarray, angle: float) -> float:
    """Ratio flux_cumule(mesure)/flux_cumule(lambertienne) à `angle`, interpolé."""
    measured = float(np.interp(angle, theta_ext, cumulative_flux))
    lamb = float(np.interp(angle, theta_ext, cumulative_flux_lambertian))
    return measured / lamb if lamb != 0 else float("nan")


def build_measurement_summary(cube: dict, ratio_angle: float = 12.0) -> dict:
    """
    À partir d'un cube {theta, phi, wavelength, intensity_corrected} (loader.load_cube),
    calcule tout ce dont AngularFluxBlock a besoin pour une mesure.
    """
    theta = np.array(cube["theta"], dtype=float)
    phi_list = cube["phi"]
    wavelength = np.array(cube["wavelength"], dtype=float)
    intensity_corrected = cube["intensity_corrected"]  # {(theta,phi): array aligned to wavelength}

    # Somme spectrale par (theta, phi) → intensité angulaire brute
    sum_intensity = {}
    for (t, p), arr in intensity_corrected.items():
        sum_intensity[(t, p)] = float(np.sum(arr))

    # Normalisation par phi (référence theta=0)
    sum_norm_phi = {}
    for p in phi_list:
        ref = sum_intensity.get((0, p))
        if not ref:
            continue
        for t in cube["theta"]:
            val = sum_intensity.get((t, p))
            if val is not None:
                sum_norm_phi[(t, p)] = val / ref

    # Moyenne sur phi → farfield 1D
    ff_by_theta = []
    for t in cube["theta"]:
        vals = [sum_norm_phi[(t, p)] for p in phi_list if (t, p) in sum_norm_phi]
        ff_by_theta.append(np.mean(vals) if vals else 0.0)
    ff_by_theta = np.array([v if v > 0 else 0.0 for v in ff_by_theta])

    theta_ext, ff_ext = extrapolate_farfield(theta, ff_by_theta)
    ff_ext_norm = ff_ext / np.max(ff_ext) if np.max(ff_ext) > 0 else ff_ext

    lambertian = ff_ext[0] * np.cos(np.deg2rad(theta_ext))
    flux, cumulative_flux = intensity_to_flux(theta_ext, ff_ext)
    flux_lamb, cumulative_flux_lamb = intensity_to_flux(theta_ext, lambertian)

    intensity_meas = flux_to_intensity(theta_ext, flux / max(np.max(flux), 1e-30))
    intensity_lamb = flux_to_intensity(theta_ext, flux_lamb / max(np.max(flux_lamb), 1e-30))
    intensity_lamb_max = max(np.max(intensity_lamb), 1e-30)

    ratio = ratio_at_angle(theta_ext, cumulative_flux, cumulative_flux_lamb, ratio_angle)

    # Spectre pondéré par intensité totale (theta=0, moyenne des phi) → lambda dominant
    spectra_theta0 = [intensity_corrected[(0, p)] for p in phi_list if (0, p) in intensity_corrected]
    if spectra_theta0:
        mean_spectrum = np.mean(spectra_theta0, axis=0)
        mean_spectrum = np.clip(mean_spectrum, 0, None)
        lambda_dominant = float(wavelength[int(np.argmax(mean_spectrum))]) if mean_spectrum.sum() > 0 else None
    else:
        mean_spectrum = np.zeros_like(wavelength)
        lambda_dominant = None

    # Diagramme de bande theta x lambda pour chaque phi — restreint à la plage
    # visible (400-800nm) puis downsample lambda/theta/phi (sinon theta(76) x
    # lambda(~1700) x phi(~37) par mesure est prohibitif dans un rapport HTML
    # qui charge toutes les mesures en mémoire).
    wl_lo, wl_hi = BAND_WAVELENGTH_RANGE
    wl_range_mask = (wavelength >= wl_lo) & (wavelength <= wl_hi)
    wl_range_idx = np.nonzero(wl_range_mask)[0]
    if len(wl_range_idx) == 0:
        wl_range_idx = np.arange(len(wavelength))

    wl_ds_idx = wl_range_idx[_downsample_indices(len(wl_range_idx), target=WAVELENGTH_DOWNSAMPLE)]
    wavelength_ds = wavelength[wl_ds_idx]

    theta_arr = np.array(cube["theta"])
    theta_ds_idx = _downsample_indices(len(theta_arr), target=THETA_DOWNSAMPLE)
    theta_band = theta_arr[theta_ds_idx].tolist()

    phi_ds_idx = _downsample_indices(len(phi_list), target=PHI_DOWNSAMPLE)
    phi_band = [phi_list[i] for i in phi_ds_idx]

    band_diagram = {}
    for p in phi_band:
        rows = []
        for ti in theta_ds_idx:
            t = int(theta_arr[ti])
            arr = intensity_corrected.get((t, p))
            if arr is None:
                rows.append([0.0] * len(wl_ds_idx))
            else:
                rows.append(arr[wl_ds_idx].tolist())
        band_diagram[p] = rows

    return {
        "theta_measured": cube["theta"],
        "theta_ext": theta_ext.tolist(),
        "wavelength_band": wavelength_ds.tolist(),
        "theta_band": theta_band,
        "phi_band": phi_band,
        "farfield_measured_norm": ff_by_theta.tolist(),
        "farfield_ext_norm": ff_ext_norm.tolist(),
        "cumulative_flux": cumulative_flux.tolist(),
        "cumulative_flux_lambertian": cumulative_flux_lamb.tolist(),
        "intensity_meas_norm": (intensity_meas / intensity_lamb_max).tolist(),
        "intensity_lambertian_norm": (intensity_lamb / intensity_lamb_max).tolist(),
        "phi_list": phi_list,
        "wavelength": wavelength.tolist(),
        "band_diagram": band_diagram,
        "mean_spectrum_theta0": mean_spectrum.tolist(),
        "ratio_12deg": ratio,
        "lambda_dominant": lambda_dominant,
    }
