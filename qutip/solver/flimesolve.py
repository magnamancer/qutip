# -*- coding: utf-8 -*-
"""
Created on Thu Jun 29 22:07:34 2023

@author: Fenton
"""

__all__ = [
    "flimesolve",
    "FLiMESolver",
]

import numpy as np
from collections import defaultdict
from itertools import product
from qutip.core import data as _data
from qutip import Qobj, QobjEvo, operator_to_vector
from .mesolve import MESolver
from .solver_base import Solver
from .result import Result
from time import time
from ..ui.progressbar import progress_bars
from qutip.solver.floquet import fsesolve, FloquetBasis


def _floquet_rate_matrix(floquet_basis, Nt, c_ops, time_sense=0):
    """
    Parameters
    ----------
    floquet_basis : FloquetBasis Object
        The FloquetBasis object formed from qutip.floquet.FloquetBasis
    Nt : Int
        Number of points in one period of the Hamiltonian
    c_ops : list of :obj:`.Qobj`, :obj:`.QobjEvo`
        Single collapse operator, or list of collapse operators
    args : *dictionary*
        dictionary of parameters for time-dependent Hamiltonians and
        collapse operators.
    time_sense : float 0-1,optional
        the time sensitivity or secular approximation restriction of
        FLiMESolve. Decides "acceptable" values of (frequency/rate) for rate
        matrix entries. Lower values imply rate occurs much faster than
        rotation frtequency, i.e. more important matrix entries. Higher
        values meaning rates cause changes slower than the Hamiltonian rotates,
        i.e. the changes average out on "longer" time scales.

    Returns
    -------
    total_R_tensor : Dictionary of {frequency: 2D rate matrix} pairs
        This function returns a list of dictionaries whose keys are the
        frequency of a specific rate matrix term, and whose values are the
        rate matrices for the associated frequency.
    """
    Hdim = len(floquet_basis.e_quasi)  # Dimensionality of the Hamiltonian

    # Forming tlist to take FFT of collapse operators
    timet = floquet_basis.T
    dt = timet / Nt
    tlist = np.linspace(0, timet - dt, Nt)
    omega = (
        2 * np.pi
    ) / floquet_basis.T  # Frequency dependence of Hamiltonian

    total_R_tensor = defaultdict(lambda: 0)
    for cdx, c_op in enumerate(c_ops):
        # Transforming the lowering operator into the Floquet Basis
        #     and taking the FFT
        modes_table = _floquet_mode_table(floquet_basis, tlist)

        c_op_Floquet_basis = np.einsum(
            "xij,jk,xkl->xil",
            np.transpose(modes_table.conj(), (0, 2, 1)),
            c_op.full(),
            modes_table,
        )
        c_op_Fourier_amplitudes_list = np.fft.fftshift(
            np.fft.fft(c_op_Floquet_basis, axis=0)
        ) / len(tlist)

        # Building the Rate matrix
        delta_m = np.add.outer(-floquet_basis.e_quasi, floquet_basis.e_quasi)
        delta_m = np.add.outer(delta_m, -delta_m)
        delta_m /= omega
        for l, k in product(np.arange(Nt), repeat=2):
            delta_shift = delta_m + (l - k)
            mask = {}
            if time_sense <= 0.0:
                mask[0] = delta_shift == 0
                if not np.any(mask):
                    continue
                rate_products = np.multiply.outer(
                    c_op_Fourier_amplitudes_list[l],
                    np.conj(c_op_Fourier_amplitudes_list)[k],
                )
            else:
                rate_products = np.multiply.outer(
                    c_op_Fourier_amplitudes_list[l],
                    np.conj(c_op_Fourier_amplitudes_list[k]),
                )
            included_deltas = abs(delta_shift * omega) <= abs(
                rate_products * time_sense
            )
            if not np.any(included_deltas):
                continue
            keys = np.unique(delta_shift[included_deltas])
            for key in keys:
                mask[key] = np.logical_and(delta_shift == key, included_deltas)

            for key in mask.keys():
                valid_c_op_products = rate_products * mask[key]
                I_ = np.eye(Hdim, Hdim)
                flime_FirstTerm = np.transpose(
                    valid_c_op_products, [0, 2, 1, 3]
                ).reshape(Hdim**2, Hdim**2)
                tmp = np.trace(valid_c_op_products, axis1=0, axis2=2)
                flime_SecondTerm = np.kron(tmp.T, I_)
                flime_ThirdTerm = np.kron(I_, tmp)

                total_R_tensor[key] += flime_FirstTerm - (0.5) * (
                    flime_SecondTerm + flime_ThirdTerm
                )

    # Turning the Rate Matrix into a super operator
    dims = [floquet_basis.U(0).dims] * 2
    total_R_tensor = {
        key: Qobj(RateMat, dims=dims, copy=False)
        for key, RateMat in total_R_tensor.items()
    }

    return total_R_tensor


def flimesolve(
    H,
    rho0,
    tlist,
    T,
    Nt=None,
    c_ops=None,
    e_ops=None,
    args=None,
    time_sense=0,
    options={},
):
    """
    Solve system dynamics using the Floquet-Lindblad Master Equation

    Parameters
    ----------

    H : :class:`Qobj`,:class:`QobjEvo`,:class:`QobjEvo` compatible format.
        Periodic system Hamiltonian as :class:`QobjEvo`. List of
        :class:`Qobj`, :class:`Coefficient` or callable that
        can be made into :class:`QobjEvo` are also accepted.

    rho0 / psi0 : :class:`qutip.Qobj`
        Initial density matrix or state vector (ket).

    tlist : *list* / *array*
        List of times for :math:`t`.

    T : float
        The period of the time-dependence of the hamiltonian.

    Nt: int
        The number of points within one period of the Hamiltonian, used for
        forming the rate matrix. If none is supplied, flimesolve will try to
        pull Nt from tlist.

    c_ops : list of (:obj:`.QobjEvo`, :obj:`.QobjEvo` compatible format)
        Single collapse operator, or list of collapse operators

    e_ops : list of :class:`qutip.Qobj` / callback function
        List of operators for which to evaluate expectation values.
        The states are reverted to the lab basis before applying the

    args : *dictionary*
        Dictionary of parameters for time-dependent Hamiltonian

    time_sense : float
        Value of the secular approximation to use when constructing the rate
        matrix R(t).Default value of zero uses the fully time-independent/most
        strict secular approximation, and will utilize the "diag" solver method.
        Values greater than zero have time dependence, and will subsequently
        use the "Adams" method for the ODE solver.

    options : None / dict
        Dictionary of options for the solver.

        - store_final_state : bool
          Whether or not to store the final state of the evolution in the
          result class.
        - store_states : bool,None
          Whether or not to store the state vectors or density matrices.
          On `None` the states will be saved if no expectation operators are
          given.
        - store_floquet_states : bool
          Whether or not to store the density matrices in the floquet basis in
          ``result.floquet_states``.
        - normalize_output : bool
          Normalize output state to hide ODE numerical errors.
        - progress_bar : str {'text','enhanced','tqdm',''}
          How to present the solver progress.
          'tqdm' uses the python module of the same name and raise an error
          if not installed. Empty string or False will disable the bar.
        - progress_kwargs : dict
          kwargs to pass to the progress_bar. Qutip's bars use `chunk_size`.
        - method : str ["adams","bdf","lsoda","dop853","vern9",etc.]
          Which differential equation integration method to use.
        - atol,rtol : float
          Absolute and relative tolerance of the ODE integrator.
        - nsteps :
          Maximum number of (internally defined) steps allowed in one ``tlist``
          step.
        - max_step : float,0
          Maximum lenght of one internal step. When using pulses,it should be
          less than half the width of the thinnest pulse.

        Other options could be supported depending on the integration method,
        see `Integrator <./classes.html#classes-ode>`_.

    Returns
    -------
    result: :class:`qutip.Result`

        An instance of the class :class:`qutip.Result`,which contains
        the expectation values for the times specified by `tlist`,and/or the
        state density matrices corresponding to the times.

    """
    if c_ops is None:
        return fsesolve(
            H,
            rho0,
            tlist,
            e_ops=e_ops,
            T=T,
            w_th=0,
            args=args,
            options=options,
        )

    if isinstance(H, FloquetBasis):
        floquet_basis = H
    else:
        floquet_basis = FloquetBasis(H, T, args, precompute=None)

        if Nt != None:
            Nt = Nt
        else:
            if tlist is not None:
                if tlist[1] - tlist[0] >= floquet_basis.T:
                    Nt = 2**4
                elif tlist[1] - tlist[0] < floquet_basis.T:
                    dt = tlist[1] - tlist[0]
                    tlist_zeroed = tlist - tlist[0]
                    Nt_finder = abs(tlist_zeroed + dt - floquet_basis.T)
                    Nt = (
                        list(np.where(Nt_finder == np.amin(Nt_finder)))[0][0]
                        + 1
                    )
            else:
                Nt = 2**4
    options["Nt"] = Nt
    solver = FLiMESolver(
        floquet_basis,
        c_ops,
        time_sense=time_sense,
        options=options,
    )
    return solver.run(rho0, tlist, e_ops=e_ops)


def _floquet_mode_table(floquet_basis, tlist):
    """
    Parameters
    ----------

    floquet_basis : Floquet Basis object for the solver/Hamiltonian of interest.

    tlist : tlist : *list* / *array*
        List of times for :math:`t`.

    Returns
    -------
    result: :class:`np.array`

        An array, indexed by (i,j,k), for the jth row, kth column, and
            ith time point of the Floquet modes used to transform into the
            FLoquet Basis
    NOTE: Technically speaking, these are the dagger of the modes, s.t.
            mode @ state @ mode.conj().T will transform INTO the Floquet basis.
            I just think the name works better this way?
    """
    return np.stack(
        [np.hstack([i.full() for i in floquet_basis.mode(t)]) for t in tlist]
    )


def _floquet_state_table(floquet_basis, tlist):
    """
    Parameters
    ----------

    floquet_basis : Floquet Basis object for the solver/Hamiltonian of interest.

    tlist : tlist : *list* / *array*
        List of times for :math:`t`.

    Returns
    -------
    result: :class:`np.array`

        An array, indexed by (i,j,k), for the jth row, kth column, and
            ith time point of the Floquet States, specifically found
            to hit every t%tau in the system evolution, even if a
            certain time point doesn't happen every period'

    """

    dims = len(floquet_basis.e_quasi)

    taulist_test = np.array(tlist) % floquet_basis.T
    taulist_correction = np.argwhere(
        abs(taulist_test - floquet_basis.T) < 1e-10
    )
    taulist_test_new = np.round(taulist_test, 10)
    taulist_test_new[taulist_correction] = 0

    tally = {}
    for i, item in enumerate(taulist_test_new):
        try:
            tally[item].append(i)
        except KeyError:
            tally[item] = [i]

    sorted_time_args = {key: tally[key] for key in np.sort(list(tally.keys()))}

    fmodes_core_dict = {
        t: np.hstack([i.full() for i in floquet_basis.mode(t)])
        for t in (sorted_time_args.keys())
    }

    tiled_modes = np.zeros((len(tlist), dims, dims), dtype=complex)
    for key in fmodes_core_dict:
        tiled_modes[sorted_time_args[key]] = fmodes_core_dict[key]
    quasi_e_table = np.exp(
        np.einsum("i,k -> ik", -1j * np.array(tlist), floquet_basis.e_quasi)
    )
    fstates_table = np.einsum("ijk,ik->ijk", tiled_modes, quasi_e_table)
    return fstates_table


class FloquetResult(Result):
    def _post_init(self, floquet_basis):
        self.floquet_basis = floquet_basis
        if self.options["store_floquet_states"]:
            self.floquet_states = []
        else:
            self.floquet_states = None
        super()._post_init()

    def add(self, t, state, floquet_state):
        if self.options["store_floquet_states"]:
            self.floquet_states.append(floquet_state)
        super().add(t, state)


class FLiMESolver(MESolver):
    """
    Solver for the Floquet-Lindblad master equation.

     .. note ::
         Operators (``c_ops`` and ``e_ops``) are in the laboratory basis.

     Parameters
     ----------
    floquet_basis : :class:`qutip.FloquetBasis`
         The system Hamiltonian wrapped in a FloquetBasis object. Choosing a
         different integrator for the ``floquet_basis`` than for the evolution
         of the floquet state can improve the performance.

    tlist : np.ndarray
         List of 2**n times distributed evenly over one period of the
             Hamiltonian

    c_ops : list of (:obj:`.QobjEvo`, :obj:`.QobjEvo` compatible format)
        Single collapse operator, or list of collapse operators

    time_sense : float
        Value of the secular approximation to use when constructing the rate
        matrix R(t).Default value of zero uses the fully time-independent/most
        strict secular approximation, and will utilize the "diag" solver method.
        Values greater than zero have time dependence, and will subsequently
        use the "Adams" method for the ODE solver.

    options : dict,optional
         Options for the solver,see :obj:`FLiMESolver.options` and
         `Integrator <./classes.html#classes-ode>`_ for a list of all options.
    """

    name = "flimesolve"
    _avail_integrators = {}
    resultclass = FloquetResult
    solver_options = {
        "progress_bar": "text",
        "progress_kwargs": {"chunk_size": 10},
        "store_final_state": False,
        "store_states": None,
        "normalize_output": True,
        "method": None,
        "store_floquet_states": False,
        "Nt": 2**4,
    }

    def __init__(
        self,
        floquet_basis,
        c_ops,
        time_sense,
        *,
        options=None,
    ):
        if time_sense == 0:
            self.solver_options["method"] = "diag"
        else:
            self.solver_options["method"] = "adams"

        if isinstance(floquet_basis, FloquetBasis):
            self.floquet_basis = floquet_basis
        else:
            raise TypeError("The ``floquet_basis`` must be a FloquetBasis")

        self.options = options

        self.Nt = self.options["Nt"]

        self.Hdim = np.shape(self.floquet_basis.e_quasi)[0]

        self._num_collapse = len(c_ops)
        if not all(isinstance(c_op, Qobj) for c_op in c_ops):
            raise TypeError("c_ops must be type Qobj")

        self.dims = len(self.floquet_basis.e_quasi)

        self.time_sense = time_sense

        self.RateDic = _floquet_rate_matrix(
            floquet_basis, self.Nt, c_ops, time_sense=time_sense
        )

        self.rhs = self._create_rhs(self.RateDic)
        self._integrator = self._get_integrator()
        self._state_metadata = {}
        self.stats = self._initialize_stats()

    def _initialize_stats(self):
        stats = Solver._initialize_stats(self)
        stats.update(
            {
                "solver": "Floquet-Lindblad master equation",
                "num_collapse": self._num_collapse,
                "init rhs time": self._init_rhs_time,
            }
        )
        return stats

    def _create_rhs(self, rate_matrix_dictionary):
        _time_start = time()

        Rate_Qobj_list = {
            key: Qobj(
                rate_matrix_dictionary[key],
                dims=[
                    self.floquet_basis.U(0).dims,
                    self.floquet_basis.U(0).dims,
                ],
                copy=False,
            ).to("csr")
            for key in rate_matrix_dictionary
        }

        Rt_timedep_pairs = [
            Rate_Qobj_list[0],
            *[
                [
                    Rate_Qobj_list[key],
                    lambda t, key=key: np.exp(
                        (1j * key * 2 * np.pi * t) / self.floquet_basis.T
                    ),
                ]
                for key in set(Rate_Qobj_list) - {0}
            ],
        ]

        rhs = QobjEvo(Rt_timedep_pairs)

        self._init_rhs_time = time() - _time_start
        return rhs

    def start(self, state0, t0, *, floquet=False):
        """
        Set the initial state and time for a step evolution.
        ``options`` for the evolutions are read at this step.

        Parameters
        ----------
        state0 : :class:`Qobj`
            Initial state of the evolution.

        t0 : double
            Initial time of the evolution.

        floquet : bool,optional {False}
            Whether the initial state is in the floquet basis or laboratory
            basis.
        """
        if not floquet:
            state0 = self.floquet_basis.to_floquet_basis(state0, t0)
        super().start(state0, t0)

    def step(self, t, *, args=None, copy=True, floquet=False):
        """
        Evolve the state to ``t`` and return the state as a :class:`Qobj`.

        Parameters
        ----------
        t : double
            Time to evolve to,must be higher than the last call.

        copy : bool,optional {True}
            Whether to return a copy of the data or the data in the ODE solver.

        floquet : bool,optional {False}
            Whether to return the state in the floquet basis or laboratory
            basis.

        args : dict,optional {None}
            Not supported

        .. note::
            The state must be initialized first by calling ``start`` or
            ``run``. If ``run`` is called,``step`` will continue from the last
            time and state obtained.
        """
        if args:
            raise ValueError("FLiMESolver cannot update arguments")
        state = super().step(t)
        if not floquet:
            state = self.floquet_basis.from_floquet_basis(state, t)
        elif copy:
            state = state.copy()
        return state

    def run(
        self,
        state0,
        tlist,
        *,
        floquet=False,
        args=None,
        e_ops=None,
    ):
        """
        Calculate the evolution of the quantum system.

        For a ``state0`` at time ``tlist[0]`` do the evolution as directed by
        ``rhs`` and for each time in ``tlist`` store the state and/or
        expectation values in a :class:`Result`. The evolution method and
        stored results are determined by ``options``.

        Parameters
        ----------
        state0 : :class:`Qobj`
            Initial state of the evolution.

        tlist : list of double
            Time for which to save the results (state and/or expect) of the
            evolution. The first element of the list is the initial time of the
            evolution. Each times of the list must be increasing,but does not
            need to be uniformy distributed.

        floquet : bool,optional {False}
            Whether the initial state in the floquet basis or laboratory basis.

        args : dict,optional {None}
            Not supported

        e_ops : list {None}
            List of Qobj,QobjEvo or callable to compute the expectation
            values. Function[s] must have the signature
            f(t : float,state : Qobj) -> expect.

        Returns
        -------
        results : :class:`qutip.solver.FloquetResult`
            Results of the evolution. States and/or expect will be saved. You
            can control the saved data in the options.
        """

        if args:
            raise ValueError("FLiMESolver cannot update arguments")
        if not floquet:
            state0 = self.floquet_basis.to_floquet_basis(state0, tlist[0])

        _time_start = time()
        _data0 = self._prepare_state(state0)
        self._integrator.set_state(tlist[0], _data0)
        stats = self._initialize_stats()
        results = self.resultclass(
            e_ops,
            self.options,
            solver=self.name,
            stats=stats,
            floquet_basis=self.floquet_basis,
        )

        if state0.type == "ket":
            state0 = operator_to_vector(state0 * state0.dag())
        elif state0.type == "oper":
            state0 = operator_to_vector(state0)
        else:
            raise ValueError("You need to supply a valid ket or operator")

        fstates_table = _floquet_state_table(self.floquet_basis, tlist)

        stats["preparation time"] += time() - _time_start

        sols = [self._restore_state(_data0, copy=False).full()]
        progress_bar = progress_bars[self.options["progress_bar"]](
            len(tlist) - 1, **self.options["progress_kwargs"]
        )
        for t, state in self._integrator.run(tlist):
            progress_bar.update()
            sols.append(self._restore_state(state, copy=False).full())
        progress_bar.finished()
        sols = np.array(sols)

        sols_comp_arr = np.einsum(
            "xij,xjk,xkl->xil",
            fstates_table,
            sols,
            np.transpose(fstates_table.conj(), axes=(0, 2, 1)),
        )

        sols_comp = [
            Qobj(
                _data.Dense(state),
                dims=[
                    self.floquet_basis.U(0).dims[0],
                    self.floquet_basis.U(0).dims[0],
                ],
                copy=False,
            )
            for state in sols_comp_arr
        ]

        for idx, state in enumerate(sols_comp):
            results.add(tlist[idx], state, Qobj(fstates_table[idx]))

        stats["run time"] = time() - _time_start
        return results

    def steadystate(self):
        """
        Uses the time-independent part of the Rate matrix to find the
            steady state of the system. Note: This only uses the full secular
            approximation.
        """
        monomat = self.RateDic[0].full()
        val, vec = np.linalg.eig(monomat)

        idx = np.where(abs(val) == np.amin(abs(val)))
        state = Qobj(
            np.square(
                np.reshape((vec[:, *idx]), (self.Hdim, self.Hdim), order="F")
            )
        )

        test = self.floquet_basis.from_floquet_basis(state, 0)
        return test

    def _argument(self, args):
        if args:
            raise ValueError("FLiMESolver cannot update arguments")
