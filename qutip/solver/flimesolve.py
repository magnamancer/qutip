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
from qutip.core import data as _data
from qutip import Qobj, QobjEvo, operator_to_vector
from .mesolve import MESolver
from .integrator import qutip_integrator
from .solver_base import Solver
from .result import Result
from time import time
from ..ui.progressbar import progress_bars
from qutip.solver.floquet import fsesolve, FloquetBasis
from collections import defaultdict


def _floquet_rate_matrix(floquet_basis,
                         Nt,
                         T,
                         c_ops,
                         c_op_rates,
                         time_sense=0):
    '''
    Parameters
    ----------
    floquet_basis : FloquetBasis Object
        The FloquetBasis object formed from qutip.floquet.FloquetBasis
    Nt : Int
        Number of points in one period of the Hamiltonian
    T : float
        Time period of the Hamiltonian. Retrieved from the FloquetBasis
        object
    c_ops : list
        list of collapse operator matrices as Qobjs
    c_op_rates : list
        List of collapse operator rates/magnitudes.
    args : *dictionary*
        dictionary of parameters for time-dependent Hamiltonians and
        collapse operators. ***FIX THIS NEXT BIT*** Currently, the first
        element MUST be the frequency-dependence of the Hamiltonian
    time_sense : float 0-1,optional
        the time sensitivity or secular approximation restriction of 
        FLiMESolve. Decides "acceptable" values of (frequency/rate) for rate 
        matrix entries. Lower values imply rate occurs much faster than
        rotation frtequency, i.e. more important matrix entries. Higher
        values meaning rates cause changes slower than the Hamiltonian rotates,
        i.e. the changes average out on longer time scales.

    Returns
    -------
    total_R_tensor : 2D Numpy matrix
        This is the 2D rate matrix for the system,created by summing the
            Rate matrix of each individual collapse operator. Something
            something Rate Matrix something something linear Operator.
    '''
    Hdim = len(floquet_basis.e_quasi)  # Dimensionality of the Hamiltonian
    args_key = (2*np.pi)/T  # Frequency dependence of Hamiltonian

    # Forming tlist to take FFT of collapse operators
    time = T
    dt = time / Nt
    tlist = np.linspace(0, time - dt, Nt)

    total_R_tensor = {}
    for cdx, c_op in enumerate(c_ops):
        # Transforming the lowering operator into the Floquet Basis
        #     and taking the FFT
        c_op_Floquet_basis = np.array(
            [floquet_basis.to_floquet_basis(c_op, t).full() for t in tlist])

        c_op_Fourier_amplitudes_list = np.array(
            np.fft.fft(c_op_Floquet_basis, axis=0) / len(tlist)
        )

        # Next step is to form arrays of the rate products (rate_products)
        #     and the frequency at which these components rotate (delta_array),
        #     then dividing the arrays to form the rate quotient array.

        # In quotient array, setting any undefined value, i.e. those for which
        #     rate_products = 0, equal to time_sense+1 so that the mask
        #     arrays mask out these values.
        rate_products = np.einsum('lab,kcd->abcdlk',
                                  c_op_Fourier_amplitudes_list,
                                  np.conj(c_op_Fourier_amplitudes_list))

        delta_array = np.add.outer(
            np.subtract.outer(
                np.subtract.outer(floquet_basis.e_quasi,
                                  floquet_basis.e_quasi),
                np.subtract.outer(floquet_basis.e_quasi, floquet_basis.e_quasi)
            )/args_key,
            np.subtract.outer(np.arange(Nt), np.arange(Nt))
        )

        # The default "out" value returns values higher than the time_sense
        #   cutoff, so that rate products of 0 are excluded from the
        #   valid_indices list via the quotient mask
        quotient_array = np.divide(
            args_key*delta_array,
            abs(rate_products),
            out=np.full(np.shape(delta_array), (time_sense+1), dtype=complex),
            dtype=complex)

        # Finally, creating masks to mask out "bad" values of the delta_array
        #     and the quotient_array. What remains after masking will be used
        #     to form the rate matrix.

        # Masking any frequency greater than Nyquist Frequency
        nyquist_mask = np.ma.getmaskarray(np.ma.masked_greater(
            delta_array, np.pi/dt))
        # Masking any rate quotient greater than time_sense
        quotient_mask = np.ma.getmaskarray(np.ma.masked_greater(
            abs(quotient_array), time_sense))
        # Full mask formed from the total of the above masks
        full_mask = nyquist_mask | quotient_mask

        # Valid indices are unmasked indices
        valid_indices = np.argwhere(full_mask == False)
        delta_vals_truncd = [
            delta_array[tuple(indices)] for indices in valid_indices]

        # Grouping valid_indices by their frequency values
        delta_dict = defaultdict(list)
        for idx, indices in enumerate(valid_indices):
            delta_dict[delta_vals_truncd[idx]].append(indices)

        # For each valid frequency, form a slice of total_R_tensor
        for key in delta_dict:
            mask_array = np.zeros((Hdim, Hdim, Hdim, Hdim, Nt, Nt))
            for indices in delta_dict[key]:
                mask_array[tuple(indices)] = True
            valid_c_op_products = rate_products * mask_array

            # using c = ap,d = bp,k=lp
            flime_FirstTerm = c_op_rates[cdx] \
                * np.einsum('mpnqlk->mnpq',
                            valid_c_op_products)

            flime_SecondTerm = c_op_rates[cdx] \
                * np.einsum('apamlk,qn->mnpq',
                            valid_c_op_products,
                            np.eye(Hdim, Hdim))

            flime_ThirdTerm = c_op_rates[cdx] \
                * np.einsum('anaqlk,pm->mnpq',
                            valid_c_op_products,
                            np.eye(Hdim, Hdim))
            try:
                total_R_tensor[key] += np.reshape(flime_FirstTerm - (1 / 2)
                                                  * (flime_SecondTerm +
                                                     flime_ThirdTerm),
                                                  (Hdim**2, Hdim**2))
            except KeyError:
                total_R_tensor[key] = np.reshape(flime_FirstTerm - (1 / 2)
                                                 * (flime_SecondTerm +
                                                    flime_ThirdTerm),
                                                 (Hdim**2, Hdim**2))

    return total_R_tensor


def flimesolve(
        H,
        rho0,
        tlist,
        T,
        Nt=None,
        c_ops_and_rates=None,
        e_ops=None,
        args=None,
        time_sense=0,
        options=None):
    """
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

    c_ops_and_rates : list of :class:`qutip.Qobj`.
        List of lists of [collapse operator,collapse operator rate] pairs

    e_ops : list of :class:`qutip.Qobj` / callback function
        List of operators for which to evaluate expectation values.
        The states are reverted to the lab basis before applying the

    args : *dictionary*
        Dictionary of parameters for time-dependent Hamiltonian

    time_sense : float
        Experimental. Value of the secular approximation (in terms of system
        frequency 2*np.pi/T) to use when constructing the rate matrix R(t).
        Default value of zero uses the fully time-independent/most strict
        secular approximation.

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
    if c_ops_and_rates is None:
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

    # With the tlists sorted,the floquet_basis object can be prepared
    if isinstance(H, FloquetBasis):
        floquet_basis = H
    else:
        floquet_basis = FloquetBasis(H, T, args, precompute=None)

    solver = FLiMESolver(floquet_basis,
                         c_ops_and_rates,
                         args,
                         tlist=tlist,
                         Nt=Nt,
                         time_sense=time_sense,
                         options=options)
    return solver.run(rho0, tlist, e_ops=e_ops)


def flimesolve_floquet_state_table(floquet_basis, tlist):

    dims = len(floquet_basis.e_quasi)

    taulist_test = np.array(tlist) % floquet_basis.T
    taulist_correction = np.argwhere(abs(
        taulist_test - floquet_basis.T) < 1e-10)
    taulist_test_new = np.round(taulist_test, 10)
    taulist_test_new[taulist_correction] = 0

    def list_duplicates(seq):
        tally = {}
        for i, item in enumerate(taulist_test_new):
            try:
                tally[item].append(i)
            except KeyError:
                tally[item] = [i]
        return ((key, locs) for key, locs in tally.items())
    sorted_time_args = {key: val for key, val in
                        sorted(list_duplicates(taulist_test_new))}

    fmodes_core_dict = {t: np.stack([floquet_basis.mode(t)[i].full()
                                    for i in range(dims)])[..., 0]
                        for t in (sorted_time_args.keys())}

    tiled_modes = np.zeros((len(tlist), dims, dims), dtype=complex)
    for key in fmodes_core_dict:
        tiled_modes[sorted_time_args[key]] = fmodes_core_dict[key]
    quasi_e_table = np.exp(np.einsum('i,k -> ki', -1j
                                     * floquet_basis.e_quasi, tlist))
    fstates_table = np.einsum('ijk,ij->ikj', tiled_modes, quasi_e_table)
    return fstates_table


class FloquetResult(Result):
    def _post_init(self, floquet_basis):
        self.floquet_basis = floquet_basis
        if self.options["store_floquet_states"]:
            self.floquet_states = []
        else:
            self.floquet_states = None
        super()._post_init()

    def add(self, t, state):
        if self.options["store_floquet_states"]:
            self.floquet_states.append(state)
        super().add(t, state)


class FLiMESolver(MESolver):
    """
    Solver for the Floquet-Markov master equation.

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

    taulist: np.ndarray
        List of number_of_periods*2**n times distributed evenly over the
            entire duration of Hamiltonian driving

    Hargs : list
        The time dependence of the Hamiltonian

   c_ops_and_rates : list of :class:`qutip.Qobj`.
       List of lists of [collapse operator, collapse operator rate] pairs

    options : dict,optional
        Options for the solver,see :obj:`FMESolver.options` and
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
        "method": "adams",
        "store_floquet_states": False,

    }

    def __init__(
        self,
        floquet_basis,
        c_ops_and_rates,
        Hargs,
        *,
        tlist=None,
        Nt=None,
        time_sense=0,
        options=None
    ):
        if isinstance(floquet_basis, FloquetBasis):
            self.floquet_basis = floquet_basis
        else:
            raise TypeError("The ``floquet_basis`` must be a FloquetBasis")
        self.options = options
        self.Hdim = np.shape(self.floquet_basis.e_quasi)[0]

        c_ops = []
        c_op_rates = []
        for c_op, rate in c_ops_and_rates:
            if not isinstance(c_op, Qobj):
                raise TypeError("c_ops must be type Qobj")
            c_ops.append(c_op)
            c_op_rates.append(rate)

        self._num_collapse = len(c_ops)
        if not all(
            isinstance(c_op, Qobj)
            for c_op in c_ops
        ):
            raise TypeError("c_ops must be type Qobj")

        self.dims = len(self.floquet_basis.e_quasi)

        if Nt != None:
            self.Nt = Nt
        elif Nt == None:
            if tlist is not None:
                if tlist[1] - tlist[0] >= self.floquet_basis.T:
                    self.Nt = 2**4
                elif tlist[1] - tlist[0] < self.floquet_basis.T:
                    dt = tlist[1] - tlist[0]
                    tlist_zeroed = tlist - tlist[0]
                    Nt_finder = abs(tlist_zeroed + dt - self.floquet_basis.T)
                    self.Nt = list(np.where(
                        Nt_finder == np.amin(Nt_finder))
                    )[0][0] + 1
            else:
                self.Nt = 2**4
        self.time_sense = time_sense

        RateDic = _floquet_rate_matrix(
            floquet_basis,
            self.Nt,
            self.floquet_basis.T,
            c_ops,
            c_op_rates,
            time_sense=time_sense)

        if time_sense == 0:
            self.solver_options["method"] = "diag"
        self.rhs = self._create_rhs(RateDic)
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

    def _create_rhs(self,
                    rate_matrix_dictionary):
        _time_start = time()

        Rate_Qobj_list = [Qobj(
            RateMat,
            dims=[self.floquet_basis.U(0).dims,
                  self.floquet_basis.U(0).dims],
            type="super",
            superrep="super",
            copy=False
        ).to("csr") for RateMat in rate_matrix_dictionary.values()]
        R0 = Rate_Qobj_list[0]

        Rt_timedep_pairs = [
            [Rate_Qobj_list[idx], 'exp(1j*' + str(list(
                rate_matrix_dictionary.keys())[idx]
                * self.floquet_basis.T) + '*t)']
            for idx in range(0, len(Rate_Qobj_list))]
        Rate_matrix_timedep_list = [R0, *Rt_timedep_pairs[1::]]

        rhs = QobjEvo(Rate_matrix_timedep_list)

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
            raise ValueError("FMESolver cannot update arguments")
        state = super().step(t)
        if not floquet:
            state = self.floquet_basis.from_floquet_basis(state, t)
        elif copy:
            state = state.copy()
        return state

    def run(self, state0, tlist, *, floquet=False, args=None, e_ops=None,):
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

        if state0.type == 'ket':
            state0 = operator_to_vector(
                state0 * state0.dag())
        elif state0.type == 'oper':
            state0 = operator_to_vector(state0)
        else:
            raise ValueError('You need to supply a valid ket or operator')

        # if state0.type == 'ket':
        #     state0 = operator_to_vector(
        #         Qobj(state0 * state0.dag(), dims=[self.floquet_basis.U(0).dims[0], self.floquet_basis.U(0).dims[0]]))
        # elif state0.type == 'oper':
        #     state0 = operator_to_vector(Qobj(state0, dims=[self.floquet_basis.U(
        #         0).dims[0], self.floquet_basis.U(0).dims[0]]))

        fstates_table = flimesolve_floquet_state_table(
            self.floquet_basis, tlist)

        stats["preparation time"] += time() - _time_start

        sols = [self._restore_state(_data0, copy=False).full()]
        progress_bar = progress_bars[self.options['progress_bar']](
            len(tlist)-1, **self.options['progress_kwargs']
        )
        for t, state in self._integrator.run(tlist):
            progress_bar.update()
            sols.append(self._restore_state(state, copy=False).full())
        progress_bar.finished()
        sols = np.array(sols)

        sols_comp_arr = np.einsum(
            'xij,xjk,xkl->xil',
            fstates_table,
            sols,
            np.transpose(fstates_table.conj(), axes=(0, 2, 1))
        )

        sols_comp = [Qobj(
            _data.Dense(state),
            dims=[self.floquet_basis.U(0).dims[0], self.floquet_basis.U(0).dims[0]], type="oper", copy=False)
            for state in sols_comp_arr]

        for idx, state in enumerate(sols_comp):
            results.add(tlist[idx], state)

        stats["run time"] = time() - _time_start
        return results

    def _argument(self, args):
        if args:
            raise ValueError("FLiMESolver cannot update arguments")
