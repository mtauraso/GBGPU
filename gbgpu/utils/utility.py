import numpy as np

from gbgpu.utils.constants import *
from newfastgbthird_cpu import third_body_vLOS


def get_chirp_mass(m1, m2):
    return (m1 * m2) ** (3 / 5) / (m1 + m2) ** (1 / 5)


def get_eta(m1, m2):
    return (m1 * m2) / (m1 + m2) ** 2


def get_amplitude(m1, m2, f, d):
    Mc = get_chirp_mass(m1, m2) * MSUN
    d = d * 1e3 * PC  # kpc to meters
    A = 2 * (G * Mc) ** (5.0 / 3.0) / (Clight ** 4 * d) * (np.pi * f) ** (2.0 / 3.0)
    return A


def get_fdot(m1, m2, f):
    Mc = get_chirp_mass(m1, m2) * MSUN
    fdot = (
        (96.0 / 5.0)
        * np.pi ** (8 / 3)
        * (G * Mc / Clight ** 3) ** (5 / 3)
        * f ** (11 / 3)
    )
    return fdot


def third_body_factors(
    chirp_mass,
    eta,
    mc,
    orbit_period,
    orbit_eccentricity,
    orbit_inclination,
    orbit_Omega2,
    orbit_omega2,
    orbit_phi2,
    orbit_lambda,
    orbit_beta,
    third_mass_unit="Mjup",
    third_period_unit="years",
):

    chirp_mass *= MSUN

    if third_mass_unit == "Mjup":
        factor = Mjup
    elif third_mass_unit == "MSUN":
        factor = MSUN

    else:
        raise NotImplementedError

    mc *= factor

    if third_period_unit == "years":
        orbit_period *= YEAR
    else:
        raise NotImplementedError

    P = orbit_period
    M = chirp_mass / eta ** (3 / 5)
    m2 = M + mc
    iota = orbit_inclination
    Omega2 = orbit_Omega2
    omega2 = orbit_omega2
    phi2 = orbit_phi2
    theta = np.pi / 2 - orbit_beta
    phi = orbit_lambda

    a2 = (G * M * P ** 2 / (4 * np.pi ** 2)) ** (1 / 3)
    e2 = orbit_eccentricity
    p2 = a2 * (1 - e2 ** 2)  # semilatus rectum

    # get C and S
    C = np.cos(theta) * np.sin(iota) + np.sin(theta) * np.cos(iota) * np.sin(
        phi - Omega2
    )
    S = np.sin(theta) * np.cos(phi - Omega2)

    # bar quantities
    A_bar = np.sqrt(C ** 2 + S ** 2)
    phi_bar = np.arctan(C / (-S))
    omega_bar = (omega2 + phi_bar) % (2 * np.pi)
    # check factor of 0.77
    amp2 = (mc / m2) * np.sqrt(G * m2 / p2) * A_bar

    # compute T2
    u2 = 2.0 * np.arctan(np.sqrt((1 - e2) / (1 + e2)) * np.tan(phi2 / 2.0))

    n2 = 2 * np.pi / P

    temp_T2 = (u2 - e2 * np.sin(u2)) / n2
    T2 = (temp_T2 / YEAR) * (temp_T2 >= 0.0) + ((P - np.abs(temp_T2)) / YEAR) * (
        temp_T2 < 0.0
    )

    return amp2, omega_bar, T2


def get_vLOS(A2, omegabar, e2, P2, T2, t):

    # check if inputs are scalar or array
    if isinstance(A2, float):
        scalar = True

    else:
        scalar = False

    A2_in = np.atleast_1d(A2)
    omegabar_in = np.atleast_1d(omegabar)
    e2_in = np.atleast_1d(e2)
    P2_in = np.atleast_1d(P2)
    T2_in = np.atleast_1d(T2)
    t_in = np.atleast_1d(t)

    # make sure all are same length
    assert np.all(
        np.array(
            [
                len(A2_in),
                len(omegabar_in),
                len(e2_in),
                len(P2_in),
                len(T2_in),
                len(t_in),
            ]
        )
        == len(A2_in)
    )

    n2_in = 2 * np.pi / (P2_in * YEAR)
    T2_in *= YEAR

    vLOS = third_body_vLOS(A2_in, omegabar_in, e2_in, n2_in, T2_in, t_in)

    # set output to shape of input
    if scalar:
        return vLOS[0]

    return vLOS


def get_aLOS(A2, omegabar, e2, P2, T2, t, eps=1e-9):

    # central differencing for derivative of velocity
    up = get_vLOS(A2, omegabar, e2, P2, T2, t + eps)
    down = get_vLOS(A2, omegabar, e2, P2, T2, t - eps)

    aLOS = (up - down) / (2 * eps)

    return aLOS


def get_f_derivatives(f0, fdot, A2, omegabar, e2, P2, T2, eps=5e4, t=None):

    if t is not None and not isinstance(t, list) and not isinstance(t, np.ndarray):
        raise ValueError("t must be 1d list or 1d np.ndarray")

    elif t is None:
        t = np.array([-eps, 0.0, eps])

    else:
        t = np.asarray(t)

    fddot = 11 / 3 * fdot ** 2 / f0

    A2_in = np.full_like(t, A2)
    omegabar_in = np.full_like(t, omegabar)
    e2_in = np.full_like(t, e2)
    P2_in = np.full_like(t, P2)
    T2_in = np.full_like(t, T2)
    f0_in = np.full_like(t, f0)
    fdot_in = np.full_like(t, fdot)

    f_temp = f0 + fdot * t + 0.5 * fddot * t * t
    f_temp *= 1.0 + get_vLOS(A2_in, omegabar_in, e2_in, P2_in, T2_in, t) / Clight

    fdot_new = (f_temp[2] - f_temp[0]) / (2 * eps)

    fddot_new = (f_temp[2] - 2 * f_temp[1] + f_temp[0]) / (2 * eps) ** 2

    return (f_temp[1], fdot_new, fddot_new)
