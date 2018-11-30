'''
CRKSPH corrections
###################

These are equations for the basic kernel corrections in [CRKSPH2017].

References
-----------

    .. [CRKSPH2017] Nicholas Frontiere, Cody D. Raskin, J. Michael Owen (2017)
        CRKSPH - A Conservative Reproducing Kernel Smoothed Particle
        Hydrodynamics Scheme.

'''

from math import sqrt, exp
from pysph.cpy.api import declare
from pysph.sph.equation import Equation, Group
from pysph.sph.wc.linalg import (
    augmented_matrix, dot, gj_solve, identity, mat_vec_mult
)
from pysph.sph.scheme import Scheme
from pysph.base.utils import get_particle_array


class CRKSPHPreStep(Equation):

    def __init__(self, dest, sources, dim=2):
        self.dim = dim
        super(CRKSPHPreStep, self).__init__(dest, sources)

    def _get_helpers_(self):
        return [augmented_matrix, gj_solve, identity, dot, mat_vec_mult]

    def loop_all(self, d_idx, d_x, d_y, d_z, d_h, s_x, s_y, s_z, s_h, s_m,
                 s_rho, SPH_KERNEL, NBRS, N_NBRS, d_ai, d_gradai, d_bi,
                 d_gradbi):
        x = d_x[d_idx]
        y = d_y[d_idx]
        z = d_z[d_idx]
        h = d_h[d_idx]
        i, j, k, s_idx, d, d2 = declare('int', 6)
        alp, bet, gam, phi, psi = declare('int', 5)
        xij = declare('matrix(3)')
        dwij = declare('matrix(3)')
        d = self.dim
        d2 = d*d

        m0 = 0.0
        m1 = declare('matrix(3)')
        m2 = declare('matrix(9)')
        temp_vec = declare('matrix(3)')
        temp_aug_m2 = declare('matrix(18)')
        m2inv = declare('matrix(9)')
        grad_m0 = declare('matrix(3)')
        grad_m1 = declare('matrix(9)')
        grad_m2 = declare('matrix(27)')
        ai = 0.0
        bi = declare('matrix(3)')
        grad_ai = declare('matrix(3)')
        grad_bi = declare('matrix(9)')

        for i in range(3):
            m1[i] = 0.0
            grad_m0[i] = 0.0
            bi[i] = 0.0
            grad_ai[i] = 0.0
            for j in range(3):
                m2[3*i + j] = 0.0
                grad_m1[3*i + j] = 0.0
                grad_bi[3*i + j] = 0.0
                for k in range(3):
                    grad_m2[9*i + 3*j + k] = 0.0

        for i in range(N_NBRS):
            s_idx = NBRS[i]
            xij[0] = x - s_x[s_idx]
            xij[1] = y - s_y[s_idx]
            xij[2] = z - s_z[s_idx]
            hij = (h + s_h[s_idx]) * 0.5
            rij = sqrt(xij[0] * xij[0] + xij[1] * xij[1] + xij[2] * xij[2])
            wij = SPH_KERNEL.kernel(xij, rij, hij)
            SPH_KERNEL.gradient(xij, rij, hij, dwij)
            V = s_m[s_idx] / s_rho[s_idx]

            m0 += V * wij
            for alp in range(d):
                m1[alp] += V * wij * xij[alp]
                for bet in range(d):
                    m2[d*alp + bet] += V * wij * xij[alp] * xij[bet]
            for gam in range(d):
                grad_m0[gam] += V * dwij[gam]
                for alp in range(d):
                    fac = 1.0 if alp == gam else 0.0
                    temp = (xij[alp] * dwij[gam] + fac * wij)
                    grad_m1[d*gam + alp] += V * temp
                    for bet in range(d):
                        fac2 = 1.0 if bet == gam else 0.0
                        temp = xij[alp] * fac2 + xij[bet] * fac
                        temp2 = (xij[alp] * xij[bet] * dwij[gam] + temp * wij)
                        grad_m2[d2*gam + d*alp + bet] += V * temp2

        identity(m2inv, d)
        augmented_matrix(m2, m2inv, d, d, temp_aug_m2)

        # If is_singular > 0 then matrix was singular
        is_singular = gj_solve(temp_aug_m2, d, d, m2inv)

        if is_singular > 0.0:
            # Cannot do much if the matrix is singular.  Perhaps later
            # we can tag such particles to see if the user can do something.
            pass
        else:
            mat_vec_mult(m2inv, m1, d, temp_vec)

            # Eq. 12.
            ai = 1.0/(m0 - dot(temp_vec, m1, d))
            # Eq. 13.
            mat_vec_mult(m2inv, m1, d, bi)
            for gam in range(d):
                bi[gam] = -bi[gam]

            # Eq. 14. and 15.
            for gam in range(d):
                temp1 = grad_m0[gam]
                for alp in range(d):
                    temp2 = 0.0
                    for bet in range(d):
                        temp1 -= m2inv[d*alp + bet] * (
                            m1[bet] * grad_m1[d*gam + alp] +
                            m1[alp] * grad_m1[d*gam + bet]
                        )
                        temp2 -= (
                            m2inv[d*alp + bet] * grad_m1[d*gam + bet]
                        )
                        for phi in range(d):
                            for psi in range(d):
                                temp1 += (
                                    m2inv[d*alp + phi] * m2inv[d*psi + bet] *
                                    grad_m2[d2*gam + d*phi + psi] *
                                    m1[bet] * m1[alp]
                                )
                                temp2 += (
                                    m2inv[d*alp + phi] * m2inv[d*psi + bet] *
                                    grad_m2[d2*gam + d*phi + psi] * m1[bet]
                                )
                    grad_bi[d*gam + alp] = temp2
                grad_ai[gam] = -ai*ai*temp1

        if N_NBRS < 2 or is_singular > 0.0:
            d_ai[d_idx] = 1.0
            for i in range(d):
                d_gradai[d * d_idx + i] = 0.0
                d_bi[d * d_idx + i] = 0.0
                for j in range(d):
                    d_gradbi[d2 * d_idx + d * i + j] = 0.0
        else:
            d_ai[d_idx] = ai
            for i in range(d):
                d_gradai[d * d_idx + i] = grad_ai[i]
                d_bi[d * d_idx + i] = bi[i]
                for j in range(d):
                    d_gradbi[d2 * d_idx + d * i + j] = grad_bi[d*i + j]


class CRKSPH(Equation):
    r"""**Conservative Reproducing Kernel SPH**

    Equations from the paper [CRKSPH2017].

    .. math::
            W_{ij}^{R} = A_{i}\left(1+B_{i}^{\alpha}x_{ij}^{\alpha}
            \right)W_{ij}
    .. math::
            \partial_{\gamma}W_{ij}^{R} = A_{i}\left(1+B_{i}^{\alpha}
            x_{ij}^{\alpha}\right)\partial_{\gamma}W_{ij} +
            \partial_{\gamma}A_{i}\left(1+B_{i}^{\alpha}x_{ij}^{\alpha}
            \right)W_{ij} + A_{i}\left(\partial_{\gamma}B_{i}^{\alpha}
            x_{ij}^{\alpha} + B_{i}^{\gamma}\right)W_{ij}
    .. math::
            \nabla\tilde{W}_{ij} = 0.5 * \left(\nabla W_{ij}^{R}-\nabla
             W_{ji}^{R} \right)

    where,

    .. math::
            A_{i} = \left[m_{0} - \left(m_{2}^{-1}\right)^{\alpha \beta}
            m_1^{\beta}m_1^{\alpha}\right]^{-1}
    .. math::
            B_{i}^{\alpha} = -\left(m_{2}^{-1}\right)^{\alpha \beta}
            m_{1}^{\beta}
    .. math::
            \partial_{\gamma}A_{i} = -A_{i}^{2}\left(\partial_{\gamma}
            m_{0}-\left(m_{2}^{-1}\right)^{\alpha \beta}\left(
            m_{1}^{\beta}\partial_{\gamma}m_{1}^{\alpha} +
            \partial_{\gamma}m_{1}^{\beta}m_{1}^{\alpha}\right) +
            \left(m_{2}^{-1}\right)^{\alpha \phi}\partial_{\gamma}
            m_{2}^{\phi \psi}\left(m_{2}^{-1}\right)^{\psi \beta}
            m_{1}^{\beta}m_{1}^{\alpha} \right)
    .. math::
            \partial_{\gamma}B_{i}^{\alpha} = -\left(m_{2}^{-1}\right)^
            {\alpha \beta}\partial_{\gamma}m_{1}^{\beta} +
            \left(m_{2}^{-1}\right)^
            {\alpha \phi}\partial_{\gamma}m_{2}^{\phi \psi}\left(m_{2}^
            {-1}\right)^{\psi \beta}m_{1}^{\beta}
    .. math::
            m_{0} = \sum_{j}V_{j}W_{ij}
    .. math::
            m_{1}^{\alpha} = \sum_{j}V_{j}x_{ij}^{\alpha}W_{ij}
    .. math::
            m_{2}^{\alpha \beta} = \sum_{j}V_{j}x_{ij}^{\alpha}
            x_{ij}^{\beta}W_{ij}
    .. math::
            \partial_{\gamma}m_{0} = \sum_{j}V_{j}\partial_{\gamma}
            W_{ij}
    .. math::
            \partial_{\gamma}m_{1}^{\alpha} = \sum_{j}V_{j}\left[
            x_{ij}^{\alpha}\partial_{\gamma}W_{ij}+\delta^
            {\alpha \gamma}W_{ij} \right]
    .. math::
            \partial_{\gamma}m_{2}^{\alpha \beta} = \sum_{j}V_{j}\left[
            x_{ij}^{\alpha}x_{ij}^{\beta}\partial_{\gamma}W_{ij} +
            \left(x_{ij}^{\alpha}\delta^{\beta \gamma} + x_{ij}^{\beta}
            \delta^{\alpha \gamma} \right)W_{ij} \right]
    """

    def __init__(self, dest, sources, dim=2, tol=0.5):
        r"""
        Parameters
        ----------

        dim : int
            Dimensionality of the problem.
        tol : float
            Tolerence value to decide std or corrected kernel
        """
        self.dim = dim
        self.tol = tol
        super(CRKSPH, self).__init__(dest, sources)

    def loop(self, d_idx, s_idx, d_ai, d_gradai, d_cwij, d_bi, d_gradbi,
             WIJ, DWIJ, XIJ, HIJ):
        alp, gam, d = declare('int', 3)
        res = declare('matrix(3)')
        dbxij = declare('matrix(3)')
        d = self.dim
        ai = d_ai[d_idx]
        eps = 1.0e-04 * HIJ
        bxij = 0.0
        for alp in range(d):
            bxij += d_bi[d*d_idx + alp] * XIJ[alp]
        for gam in range(d):
            temp = 0.0
            for alp in range(d):
                temp += d_gradbi[d*d*d_idx + d*gam + alp]*XIJ[alp]
            dbxij[gam] = temp

        d_cwij[d_idx] = (ai*(1 + bxij))

        for gam in range(d):
            res[gam] = ((ai * DWIJ[gam] + d_gradai[d * d_idx + gam] * WIJ) *
                        (1 + bxij))
            res[gam] += ai * (dbxij[gam] + d_bi[d * d_idx + gam]) * WIJ

        res_mag = 0.0
        dwij_mag = 0.0
        for i in range(d):
            res_mag += abs(res[i])
            dwij_mag += abs(DWIJ[i])
        change = abs(res_mag - dwij_mag)/(dwij_mag + eps)
        if change < self.tol:
            for i in range(d):
                DWIJ[i] = res[i]


class CRKSPHSymmetric(Equation):
    r"""**Conservative Reproducing Kernel SPH**

    This is symmetric and will only work for particles of the same array.

    Equations from the paper [CRKSPH2017].

    .. math::
            W_{ij}^{R} = A_{i}\left(1+B_{i}^{\alpha}x_{ij}^{\alpha}
            \right)W_{ij}
    .. math::
            \partial_{\gamma}W_{ij}^{R} = A_{i}\left(1+B_{i}^{\alpha}
            x_{ij}^{\alpha}\right)\partial_{\gamma}W_{ij} +
            \partial_{\gamma}A_{i}\left(1+B_{i}^{\alpha}x_{ij}^{\alpha}
            \right)W_{ij} + A_{i}\left(\partial_{\gamma}B_{i}^{\alpha}
            x_{ij}^{\alpha} + B_{i}^{\gamma}\right)W_{ij}
    .. math::
            \nabla\tilde{W}_{ij} = 0.5 * \left(\nabla W_{ij}^{R}-\nabla
             W_{ji}^{R} \right)

    where,

    .. math::
            A_{i} = \left[m_{0} - \left(m_{2}^{-1}\right)^{\alpha \beta}
            m1_{\beta}m1_{\alpha}\right]^{-1}
    .. math::
            B_{i}^{\alpha} = -\left(m_{2}^{-1}\right)^{\alpha \beta}
            m_{1}^{\beta}
    .. math::
            \partial_{\gamma}A_{i} = -A_{i}^{2}\left(\partial_{\gamma}
            m_{0}-\left[m_{2}^{-1}\right]^{\alpha \beta}\left[
            m_{1}^{\beta}\partial_{\gamma}m_{1}^{\beta}m_{1}^{\alpha} +
            \partial_{\gamma}m_{1}^{\alpha}m_{1}^{\beta}\right] +
            \left[m_{2}^{-1}\right]^{\alpha \phi}\partial_{\gamma}
            m_{2}^{\phi \psi}\left[m_{2}^{-1}\right]^{\psi \beta}
            m_{1}^{\beta}m_{1}^{\alpha} \right)
    .. math::
            \partial_{\gamma}B_{i}^{\alpha} = -\left(m_{2}^{-1}\right)^ {\alpha
            \beta}\partial_{\gamma}m_{1}^{\beta} + \left(m_{2}^{-1}\right)^
            {\alpha \phi}\partial_{\gamma}m_{2}^{\phi \psi}\left(m_{2}^
            {-1}\right)^{\psi \beta}m_{1}^{\beta}
    .. math::
            m_{0} = \sum_{j}V_{j}W_{ij}
    .. math::
            m_{1}^{\alpha} = \sum_{j}V_{j}x_{ij}^{\alpha}W_{ij}
    .. math::
            m_{2}^{\alpha \beta} = \sum_{j}V_{j}x_{ij}^{\alpha}
            x_{ij}^{\beta}W_{ij}
    .. math::
            \partial_{\gamma}m_{0} = \sum_{j}V_{j}\partial_{\gamma}
            W_{ij}
    .. math::
            \partial_{\gamma}m_{1}^{\alpha} = \sum_{j}V_{j}\left[
            x_{ij}^{\alpha}\partial_{\gamma}W_{ij}+\delta^
            {\alpha \gamma}W_{ij} \right]
    .. math::
            \partial_{\gamma}m_{2}^{\alpha \beta} = \sum_{j}V_{j}\left[
            x_{ij}^{\alpha}x_{ij}^{\beta}\partial_{\gamma}W_{ij} +
            \left(x_{ij}^{\alpha}\delta^{\beta \gamma} + x_{ij}^{\beta}
            \delta^{\alpha \gamma} \right)W_{ij} \right]
    """

    def __init__(self, dest, sources, dim=2, tol=0.5):
        self.dim = dim
        self.tol = tol
        super(CRKSPHSymmetric, self).__init__(dest, sources)

    def loop(self, d_idx, s_idx, d_ai, d_gradai, d_cwij, d_bi, d_gradbi, s_ai,
             s_gradai, s_bi, s_gradbi, WIJ, DWIJ, XIJ, HIJ):
        alp, gam, d = declare('int', 3)
        res = declare('matrix(3)')
        dbxij = declare('matrix(3)')
        dbxji = declare('matrix(3)')
        d = self.dim
        ai = d_ai[d_idx]
        aj = s_ai[s_idx]
        eps = 1.0e-04 * HIJ
        bxij = 0.0
        bxji = 0.0
        for alp in range(d):
            bxij += d_bi[d*d_idx + alp] * XIJ[alp]
            bxji -= s_bi[d*s_idx + alp] * XIJ[alp]
        for gam in range(d):
            temp = 0.0
            temp1 = 0.0
            for alp in range(d):
                temp += d_gradbi[d*d*d_idx + d*gam + alp]*XIJ[alp]
                temp1 -= s_gradbi[d*d*s_idx + d*gam + alp]*XIJ[alp]
            dbxij[gam] = temp
            dbxji[gam] = temp1

        d_cwij[d_idx] = 1.0/(ai*(1 + bxij))

        for gam in range(d):
            temp = ((ai * DWIJ[gam] + d_gradai[d * d_idx + gam] * WIJ) *
                    (1 + bxij))
            temp += ai * (dbxij[gam] + d_bi[d * d_idx + gam]) * WIJ
            temp += ((aj * DWIJ[gam] - s_gradai[d * s_idx + gam] * WIJ) *
                     (1 + bxji))
            temp -= aj * (dbxji[gam] + s_bi[d * s_idx + gam]) * WIJ
            res[gam] = 0.5*temp

        res_mag = 0.0
        dwij_mag = 0.0
        for i in range(d):
            res_mag += abs(res[i])
            dwij_mag += abs(DWIJ[i])
        change = abs(res_mag - dwij_mag)/(dwij_mag + eps)
        if change < self.tol:
            for i in range(d):
                DWIJ[i] = res[i]


class NumberDensity(Equation):
    r"""**Number Density**

    From [CRKSPH2017], equation (75):

    .. math::
        V_{i}^{-1} = \sum_{j} W_{i}
    """
    def initialize(self, d_idx, d_V):
        d_V[d_idx] = 0.0

    def loop(self, d_idx, d_V, WIJ):
        d_V[d_idx] += WIJ


class SummationDensityCRKSPH(Equation):
    r"""**Summation Density CRKSPH**

    From [CRKSPH2017], equation (76):

    .. math::
        \rho_{i} = \frac{\sum_j m_{ij} V_j W_{ij}^R}
        {\sum_{j} V_{j}^{2} W_{ij}^R}
    """

    def initialize(self, d_idx, d_rho, d_rhofac):
        d_rho[d_idx] = 0.0
        d_rhofac[d_idx] = 0.0

    def loop(self, d_idx, s_idx, d_m, d_rho, d_rhofac, s_V, WIJ, d_cwij):
        Vj = 1.0/s_V[s_idx]
        fac = Vj * d_cwij[d_idx] * WIJ
        d_rho[d_idx] += d_m[d_idx] * fac
        d_rhofac[d_idx] += Vj * fac

    def post_loop(self, d_idx, d_rho, d_rhofac):
        d_rho[d_idx] = d_rho[d_idx] / d_rhofac[d_idx]


class VelocityGradient(Equation):
    r"""**Velocity Gradient**

    From [CRKSPH2017], equation (74)

    .. math::
        \partial_{\beta} v_i^{\alpha} = -\sum_j V_j v_{ij}^{\alpha}
        \partial_{\beta} W_{ij}^R
    """
    def __init__(self, dest, sources, dim):
        r"""
        Parameters
        ----------

        dim : int
            Dimensionality of the Problem.
        """
        self.dim = dim
        super(VelocityGradient, self).__init__(dest, sources)

    def initialize(self, d_idx, d_gradv):
        i = declare('int')
        for i in range(9):
            d_gradv[9*d_idx + i] = 0.0

    def loop(self, d_idx, s_idx, s_V, d_gradv, d_h, s_h, XIJ, DWIJ, VIJ):
        alp, bet, d = declare('int', 5)
        d = self.dim

        Vj = 1.0/s_V[s_idx]

        for alp in range(d):
            for bet in range(d):
                d_gradv[d_idx*d*d + d*alp + bet] += -Vj * VIJ[alp] * DWIJ[bet]


class MomentumEquation(Equation):
    r"""**Momentum Equation**

    From [CRKSPH2017], equation (64):

    .. math::
        \frac{Dv_{i}^{\alpha}}{Dt} = -\frac{1}{2 m_i}\sum_{j} V_i V_j (P_i
        + P_j + Q_i + Q_j)
        (\partial_{\alpha}W_{ij}^R - \partial_{\alpha} W_{ji}^R)

    where,

    .. math::
        V_{i/j} = \text{dest/source particle number density}

    .. math::
        P_{i/j} = \text{dest/source particle pressure}

    .. math::
        Q_i = \rho_{i} (-C_{l} c_{i} \mu_{i} + C_{q} \mu_{i}^{2})

    .. math::
        \mu_i = \min \left(0, \frac{\hat{v}_{ij}
        \eta_{i}^{\alpha}}{\eta_{i}^{\alpha}\eta_{i}^{\alpha}
        + \epsilon^{2}}\right)

    .. math::
        \hat{v}_{ij}^{\alpha} = v_{i}^{\alpha} - v_{j}^{\alpha}
        - \frac{\phi_{ij}}{2}\left(\partial_{\beta} v_i^{\alpha}
        + \partial_{\beta}v_j^{\alpha}\right) x_{ij}^{\beta}

    .. math::
        \phi_{ij} = \max \left[0, \min \left[1, \frac{4r_{ij}}{(1
        + r_{ij})^2}\right]\right] \times
        \begin{cases}
        \exp{\left[-\left((\eta_{ij}
        - \eta_{crit})/\eta_{fold}\right)^2\right]}, &\eta_{ij} < \eta_{crit}
        \\
        1, &  \eta_{ij} >= \eta_{crit}
        \end{cases}

    .. math::
        \eta_{ij} = \min(\eta_i, \eta_j)

    .. math::
        \eta_{i/j} = (x_{ij}^{\alpha} x_{ij}^{\alpha})^{1/2} / h_{i/j}

    .. math::
        r_{ij} = \frac{\partial_{\beta} v_i^{\alpha} x_{ij}^{\alpha}
        x_{ij}^{\beta}}{\partial_{\beta} v_j^{\alpha}x_{ij}^{\alpha}
        x_{ij}^{\beta}}

    .. math::
        \partial_{\beta} v_i^{\alpha} = -\sum_j V_j v_{ij}^{\alpha}
        \partial_{\beta} W_{ij}^R
    """

    def __init__(self, dest, sources, dim, gx=0.0, gy=0.0, gz=0.0, cl=2, cq=1,
                 eta_crit=0.5, eta_fold=0.2, tol=0.5):
        self.dim = dim
        self.gx = gx
        self.gy = gy
        self.gz = gz
        self.cl = cl
        self.cq = cq
        self.eta_crit = eta_crit
        self.eta_fold = eta_fold
        self.tol = tol
        super(MomentumEquation, self).__init__(dest, sources)

    def _get_helpers_(self):
        return [dot]

    def initialize(self, d_idx, d_au, d_av, d_aw):
        d_au[d_idx] = self.gx
        d_av[d_idx] = self.gy
        d_aw[d_idx] = self.gz

    def loop(self, d_idx, s_idx, d_m, s_m, d_rho, s_rho, d_p, s_p, d_cs, s_cs,
             d_u, d_v, d_w, s_u, s_v, s_w, d_gradv, s_gradv, d_h, s_h, s_ai,
             s_bi, s_gradai, s_gradbi, d_au, d_av, d_aw, d_V, s_V, XIJ, VIJ,
             DWIJ, EPS, HIJ, WIJ):
        Cl = self.cl
        Cq = self.cq
        eta_fold = self.eta_fold
        eta_crit = self.eta_crit

        mi = d_m[d_idx]
        Vi = 1.0/d_V[d_idx]
        Vj = 1.0/s_V[s_idx]

        pi = d_p[d_idx]
        pj = s_p[s_idx]

        rhoi = d_rho[d_idx]
        rhoj = s_rho[s_idx]

        ci = d_cs[d_idx]
        cj = s_cs[s_idx]

        hi = d_h[d_idx]
        hj = s_h[s_idx]

        alp, bet, i, d = declare('int', 4)
        uijhat, tmpdvxij = declare('matrix(3)', 2)

        d = self.dim

        tmpri = 0.0
        tmprj = 0.0
        for alp in range(d):
            for bet in range(d):
                tmpri += d_gradv[d*d*d_idx + d*alp + bet] * XIJ[alp] * XIJ[bet]
                tmprj += s_gradv[d*d*s_idx + d*alp + bet] * XIJ[alp] * XIJ[bet]
        rij = tmpri/tmprj

        tmprij = min(1, 4*rij/(1 + rij)**2.0)
        phiij = max(0, tmprij)

        tmpxij = dot(XIJ, XIJ, d)
        etai_scalar = sqrt(tmpxij)/hi
        etaj_scalar = sqrt(tmpxij)/hj
        etaij = min(etai_scalar, etaj_scalar)

        if etaij < eta_crit:
            tmpphi = (etaij - eta_crit)/eta_fold
            phiij = phiij * exp(-tmpphi*tmpphi)

        for alp in range(d):
            s = 0.0
            for bet in range(d):
                s += (d_gradv[d*d*d_idx + d*alp + bet] +
                      s_gradv[d*d*s_idx + d*alp + bet]) * XIJ[bet]
            tmpdvxij[alp] = s

        uijhat[0] = d_u[d_idx] - s_u[s_idx] - 0.5*phiij * tmpdvxij[0]
        uijhat[1] = d_v[d_idx] - s_v[s_idx] - 0.5*phiij * tmpdvxij[1]
        uijhat[2] = d_w[d_idx] - s_w[s_idx] - 0.5*phiij * tmpdvxij[2]

        tmpmui = dot(uijhat, XIJ, d) / (tmpxij/hi + EPS * hi)
        mui = min(0, tmpmui)

        tmpmuj = dot(uijhat, XIJ, d) / (tmpxij/hi + EPS * hj)
        muj = min(0, tmpmuj)

        Qi = rhoi * (-Cl*ci*mui + Cq*mui*mui)
        Qj = rhoj * (-Cl*cj*muj + Cq*muj*muj)

        fac = -(0.5/mi) * Vi * Vj * (pi + pj + Qi + Qj)

        d_au[d_idx] += fac * DWIJ[0]
        d_av[d_idx] += fac * DWIJ[1]
        d_aw[d_idx] += fac * DWIJ[2]


class EnergyEquation(Equation):
    r"""**Energy Equation**

    From [CRKSPH2017], equation (66):

    .. math::
        \Delta u_{ij} = \frac{f_{ij}}{2}\left(v_j^{\alpha}(t) + v_j^{\alpha}(t
        + \Delta t) - v_i^{\alpha}(t) - v_i^{\alpha}(t + \Delta t)\right)
        \frac{Dv_{ij}^{\alpha}}{Dt}

    .. math::
        f_{ij} = \begin{cases}
        1/2 &|s_i - s_j| = 0,\\
        s_{\min} / (s_{\min} + s_{\max}) &\Delta u_{ij}\times(s_i - s_j) > 0\\
        s_{\max} / (s_{\min} + s_{\max}) &\Delta u_{ij}\times(s_i - s_j) < 0\\
        \end{cases}

    .. math::
        s_{\min} = \min(|s_i|, |s_j|)

    .. math::
        s_{\max} = \max(|s_i|, |s_j|)

    .. math::
        s_{i/j} = \frac{p_{i/j}}{\rho_{i/j}^\gamma}

    see MomentumEquation for :math:`\frac{Dv_{ij}^{\alpha}}{Dt}`
    """

    def __init__(self, dest, sources, dim, gamma):
        self.dim = dim
        self.gamma = gamma
        super(EnergyEquation, self).__init__(dest, sources)

    def _get_helpers_(self):
        return [dot]

    def initialize(self, d_idx, d_ae):
        d_ae[d_idx] = 0.0

    def loop(self, d_idx, s_idx, d_au, d_av, d_aw, d_ae, s_au, s_av, s_aw,
             d_u0, d_v0, d_w0, s_u0, s_v0, s_w0, d_u, d_v, d_w, s_u, s_v, s_w,
             d_p, d_rho, s_p, s_rho):
        gamma = self.gamma
        d = declare('int')
        d = self.dim
        auij, delu = declare('matrix(3)', 2)
        auij[0] = d_au[d_idx] - s_au[s_idx]
        auij[1] = d_av[d_idx] - s_av[s_idx]
        auij[2] = d_aw[d_idx] - s_aw[s_idx]

        delu[0] = s_u0[s_idx] + s_u[s_idx] - d_u0[d_idx] - d_u[d_idx]
        delu[1] = s_v0[s_idx] + s_v[s_idx] - d_v0[d_idx] - d_v[d_idx]
        delu[2] = s_w0[s_idx] + s_w[s_idx] - d_w0[d_idx] - d_w[d_idx]

        aeij = dot(delu, auij, d)

        si = d_p[d_idx]/((d_rho[d_idx])**gamma)
        sj = s_p[s_idx]/((s_rho[s_idx])**gamma)
        smin = min(abs(si), abs(sj))
        smax = max(abs(si), abs(sj))

        fij = 0.5
        sdiff = si - sj
        if sdiff * aeij > 0:
            fij = smin/(smin + smax)
        elif sdiff * aeij < 0:
            fij = smax/(smin + smax)

        d_ae[d_idx] += 0.5*fij * aeij


class StateEquation(Equation):
    def __init__(self, dest, sources, gamma):
        self.gamma = gamma
        super(StateEquation, self).__init__(dest, sources)

    def initialize(self, d_idx, d_p, d_rho, d_e):
        d_p[d_idx] = (self.gamma - 1) * d_rho[d_idx] * d_e[d_idx]


def get_particle_array_crksph(constants=None, **props):
    crksph_props = [
        'e', 'au', 'av', 'aw', 'ae', 'u0', 'v0', 'w0', 'cs', 'V', 'rhofac',
        'x0', 'y0', 'z0', 'rho0', 'ax', 'ay', 'az', 'arho'
    ]

    pa = get_particle_array(
        additional_props=crksph_props, constants=constants, **props
    )
    pa.add_property('cwij')
    pa.add_property('ai')
    pa.add_property('bi', stride=3)
    pa.add_property('gradai', stride=3)
    pa.add_property('gradbi', stride=9)
    pa.add_property('gradv', stride=9)
    pa.add_output_arrays(['p', 'V'])
    return pa


class CRKSPHScheme(Scheme):
    def __init__(self, fluids, solids, dim, rho0, c0, nu, h0, p0, gx=0.0,
                 gy=0.0, gz=0.0, cl=2, cq=1, gamma=7.0, eta_crit=0.5,
                 eta_fold=0.2, tol=0.5):
        self.fluids = fluids
        self.solids = solids
        self.solver = None
        self.dim = dim
        self.rho0 = rho0
        self.c0 = c0
        self.h0 = h0
        self.p0 = p0
        self.nu = nu
        self.gx = gx
        self.gy = gy
        self.gz = gz
        self.cl = cl
        self.cq = cq
        self.gamma = gamma
        self.eta_crit = eta_crit
        self.eta_fold = eta_fold
        self.tol = tol

    def configure_solver(self, kernel=None, integrator_cls=None,
                         extra_steppers=None, **kw):
        """Configure the solver to be generated.

        Parameters
        ----------

        kernel : Kernel instance.
            Kernel to use, if none is passed a default one is used.
        integrator_cls : pysph.sph.integrator.Integrator
            Integrator class to use, use sensible default if none is
            passed.
        extra_steppers : dict
            Additional integration stepper instances as a dict.
        **kw : extra arguments
            Any additional keyword args are passed to the solver instance.
        """
        from pysph.base.kernels import QuinticSpline
        from pysph.sph.integrator import PECIntegrator
        from pysph.sph.integrator_step import WCSPHStep
        if kernel is None:
            kernel = QuinticSpline(dim=self.dim)
        steppers = {}
        if extra_steppers is not None:
            steppers.update(extra_steppers)

        step_cls = WCSPHStep
        for fluid in self.fluids:
            if fluid not in steppers:
                steppers[fluid] = step_cls()

        cls = integrator_cls if integrator_cls is not None else PECIntegrator
        integrator = cls(**steppers)

        from pysph.solver.solver import Solver
        self.solver = Solver(
            dim=self.dim, integrator=integrator, kernel=kernel,
            output_at_times=[0, 0.2, 0.4, 0.8], **kw
        )

    def get_equations(self):
        from pysph.sph.basic_equations import XSPHCorrection, SummationDensity
        from pysph.sph.wc.basic import TaitEOS
        from pysph.sph.wc.viscosity import LaminarViscosity
        all = self.fluids

        equations = []

        eq0 = []
        for fluid in self.fluids:
            eq0.append(CRKSPHPreStep(dest=fluid, sources=all, dim=2))
        equations.append(Group(equations=eq0, real=False))

        eq1 = []
        for fluid in self.fluids:
            eq1.append(NumberDensity(dest=fluid, sources=all))
        equations.append(Group(equations=eq1, real=False))

        eq2 = []
        for fluid in self.fluids:
            eq2.extend([
                CRKSPH(dest=fluid, sources=all, dim=self.dim, tol=self.tol),
                SummationDensityCRKSPH(dest=fluid, sources=all)
            ])
        equations.append(Group(equations=eq2, real=False))

        eq3 = []
        for fluid in self.fluids:
            eq3.append(
                TaitEOS(dest=fluid, sources=None, rho0=self.rho0, c0=self.c0,
                        p0=self.p0, gamma=self.gamma))
        equations.append(Group(equations=eq3, real=False))

        eq4 = []
        for fluid in self.fluids:
            eq4.extend([
                CRKSPH(dest=fluid, sources=all, dim=self.dim, tol=self.tol),
                VelocityGradient(dest=fluid, sources=all, dim=self.dim)
            ])
        equations.append(Group(equations=eq4))

        eq5 = []
        for fluid in self.fluids:
            eq5.extend([
                CRKSPHSymmetric(dest=fluid, sources=all, dim=self.dim,
                                tol=self.tol),
                MomentumEquation(
                    dest=fluid, sources=all, dim=self.dim, gx=self.gx,
                    gy=self.gy, gz=self.gz, cl=self.cl, cq=self.cq,
                    eta_crit=self.eta_crit, eta_fold=self.eta_fold
                ),
                XSPHCorrection(dest=fluid, sources=all)
            ])

            if abs(self.nu) > 1e-14:
                eq5.append(LaminarViscosity(
                    dest=fluid, sources=self.fluids, nu=self.nu
                ))
        equations.append(Group(equations=eq5))
        return equations

    def setup_properties(self, particles, clean=True):
        particle_arrays = dict([(p.name, p) for p in particles])
        dummy = get_particle_array_crksph(name='junk')
        props = list(dummy.properties.keys())
        output_props = dummy.output_property_arrays
        for fluid in self.fluids:
            pa = particle_arrays[fluid]
            self._ensure_properties(pa, props, clean)
            pa.set_output_arrays(output_props)
