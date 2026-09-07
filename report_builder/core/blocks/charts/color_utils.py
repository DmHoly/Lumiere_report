"""color_utils.py — Utilitaires de conversion couleur (physique optique)."""
from __future__ import annotations


def lambda_to_srgb(lam: float) -> str:
    """Convertit une longueur d'onde (nm) en couleur sRGB hex."""
    l = lam
    if   l < 380: r, g, b = 0, 0, 0
    elif l < 440: r, g, b = -(l-440)/60, 0, 1
    elif l < 490: r, g, b = 0, (l-440)/50, 1
    elif l < 510: r, g, b = 0, 1, -(l-510)/20
    elif l < 580: r, g, b = (l-510)/70, 1, 0
    elif l < 645: r, g, b = 1, -(l-645)/65, 0
    elif l <= 700: r, g, b = 1, 0, 0
    else:          r, g, b = 0, 0, 0
    r, g, b = (max(0, min(1, x)) ** 0.8 for x in (r, g, b))
    return "#{:02x}{:02x}{:02x}".format(int(r*255), int(g*255), int(b*255))


# Alias de compatibilité — les anciens imports via _helpers continuent de fonctionner
_lambda_to_srgb = lambda_to_srgb
