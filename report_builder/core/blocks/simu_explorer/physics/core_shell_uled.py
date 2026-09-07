"""
Modele compact electro-optique pour uLEDs a nanofils core-shell InGaN/GaN.
Reference: Tsormpatzoglou et al., J. Appl. Phys. 140, 014501 (2026).

Fonctions pures (Eq. 2, 3, 5, 6, 8, 9 du papier) + pipeline de fit
scipy.optimize.curve_fit sur donnees experimentales digitalisees (ex. via
WebPlotDigitizer depuis les Fig. 1-8). Miroir exact de la physique portee en
JS dans CoreShellULEDBlock (report_builder/core/blocks/simu_explorer/core_shell_uled_block.py) —
toute modification d'equation ici doit etre repercutee la-bas.
"""
from __future__ import annotations
import numpy as np
from scipy.optimize import curve_fit

# ---------------------------------------------------------------------------
# Constantes physiques
# ---------------------------------------------------------------------------
q = 1.602176634e-19        # C
k_B = 1.380649e-23         # J/K
eps0 = 8.8541878128e-14    # F/cm
T = 300.0                  # K


# ===========================================================================
# 1) REGIME I : courant SCLC avec pieges exponentiels (Eq. 2)
# ===========================================================================
def sclc_current(V, Dp, m, kTc_eV, Nt, eps_r, t_ebl, S_nw, Nv=3e19):
    """Courant SCLC (trap-limited) - Eq. (2)."""
    mu_p = q * Dp / (k_B * T)
    I0 = q * mu_p * Nv * S_nw
    pref = (eps0 * eps_r * m / (q * Nt * (m + 1))) ** m
    pref *= ((2 * m + 1) / (m + 1)) ** (m + 1)
    return I0 * pref * (V ** (m + 1)) / (t_ebl ** (2 * m + 1))


def fit_sclc(V_data, I_data, Dp_fixed, m_fixed, t_ebl, S_nw, eps_r=8.9, Nv=3e19,
             p0=(0.322, 1.33e20)):
    """Fit du regime I pour extraire kTc et Nt (Dp, m fixes depuis le regime II)."""
    def model(V, kTc_eV, Nt):
        return sclc_current(V, Dp_fixed, m_fixed, kTc_eV, Nt, eps_r, t_ebl, S_nw, Nv)
    return curve_fit(model, V_data, I_data, p0=p0, maxfev=20000)


# ===========================================================================
# 2) REGIME II : concentration de trous injectee (Eq. 5)
# ===========================================================================
def pinj_from_current(I, Ldif, Dp, S_nw):
    """Eq. (5): p_inj = I * Ldif / (q * S_nw * Dp)."""
    return I * Ldif / (q * S_nw * Dp)


# ===========================================================================
# 3) Puissance optique vs pinj a faible injection (Eq. 6)
# ===========================================================================
def power_vs_pinj(p_inj, B, LEE, hv_eV, V_active):
    """Eq. (6): P = LEE * hv * V_active * B * p_inj^2."""
    return LEE * (hv_eV * q) * V_active * B * p_inj ** 2


def fit_B_low_injection(pinj_data, P_data, LEE, hv_eV, V_active, p0=3e-9):
    """Fit de B a faible injection (loi P ~ p_inj^2), Eq. (6)."""
    def model(p_inj, B):
        return power_vs_pinj(p_inj, B, LEE, hv_eV, V_active)
    popt, pcov = curve_fit(model, pinj_data, P_data, p0=[p0], maxfev=20000)
    return popt[0], pcov


# ===========================================================================
# 4) Modele ABC classique (Eq. 3)
# ===========================================================================
def eqe_abc(p_inj, A, B, C, LEE):
    """Eq. (3): EQE = LEE * B*p_inj^2 / (A*p_inj + B*p_inj^2 + C*p_inj^3)."""
    num = B * p_inj ** 2
    den = A * p_inj + B * p_inj ** 2 + C * p_inj ** 3
    return LEE * num / den


# ===========================================================================
# 5) Modele ABC(p_inj) modifie avec Auger PSF (Eq. 8)
# ===========================================================================
def c_psf(p_inj, C0, pinj0):
    """Eq. (8): C(p_inj) = C0 / (1 + p_inj/p_inj0)."""
    return C0 / (1.0 + p_inj / pinj0)


def eqe_abc_psf(p_inj, A, B, C0, pinj0, LEE):
    """EQE avec Auger dependant de p_inj (effet PSF), reproduit l'asymetrie (Fig. 6)."""
    C = c_psf(p_inj, C0, pinj0)
    num = B * p_inj ** 2
    den = A * p_inj + B * p_inj ** 2 + C * p_inj ** 3
    return LEE * num / den


def fit_eqe_abc_psf(pinj_data, eqe_data, LEE, p0=(2e6, 3e-9, 3e-26, 1e17)):
    """Fit complet EQE(p_inj) avec le modele modifie ABC(p_inj). p0 = (A, B, C0, pinj0)."""
    def model(p_inj, A, B, C0, pinj0):
        return eqe_abc_psf(p_inj, A, B, C0, pinj0, LEE)
    return curve_fit(model, pinj_data, eqe_data, p0=p0, maxfev=50000, bounds=(0, np.inf))


# ===========================================================================
# 6) Bande passante -3dB (Eq. 9)
# ===========================================================================
def bandwidth_3dB(B, J, t_qw):
    """Eq. (9): f_-3dB = (sqrt(3)/2pi) * sqrt(B*J/(q*t))."""
    return (np.sqrt(3) / (2 * np.pi)) * np.sqrt(np.maximum(B * J / (q * t_qw), 0))
