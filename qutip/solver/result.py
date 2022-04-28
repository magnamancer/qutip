""" Class for solve function results"""
import numpy as np
from copy import copy
from ..core import Qobj, QobjEvo, spre, issuper, expect
#from . import SolverResultsOptions

__all__ = ["Result", "MultiTrajResult", "McResult"]


class _Expect_Caller:
    """pickable partial(expect, oper) with extra `t` input"""
    def __init__(self, oper):
        self.oper = oper

    def __call__(self, t, state):
        return expect(self.oper, state)


class Result:
    """
    Class for storing simulation results from single trajectory
    dynamics solvers.

    Parameters
    ----------
    e_ops : list of :class:`Qobj` / callback function
        Single operator or list of operators for which to evaluate
        expectation values or callable or list of callable.
        Callable signature must be, `f(t: float, state: Qobj)`.
        See :func:`expect` for more detail of operator expectation.

    options : mapping
        Result options, dict or equivalent containing entry for 'store_states',
        'store_final_state' and 'normalize_output'. Only ket and density
        matrices can be normalized.

    ts : float, iterable, [optional]
        Time of the first time or tlist from which to extract that time.
        If tlist is passed, it will be used to recognized when the last state
        is added if options['store_final_state'] is True.
        (Memory management optimization)

    state0 : Qobj, [optional]
        First state of the evolution.

    stats : dict, [optional]
        Extra data to store with the result. Will be added to ``self.stats``.
    """
    def __init__(self, e_ops, options, ts=None, state0=None, stats=None):
        # Initialize output data
        self._times = []
        self._states = []
        self._expects = []
        self._last_state = None
        self._last_time = -np.inf
        if hasattr(ts, '__iter__') and len(ts) > 1:
            self._last_time = ts[-1]
            ts = ts[0]  # We only the first and last values.

        # Read e_ops
        self._raw_e_ops = e_ops
        e_ops_list = self._e_ops_as_list(e_ops)
        self._e_num = len(e_ops_list)

        self._e_ops = []
        dims = state0.dims[0] if state0 is not None else None
        for e_op in e_ops_list:
            self._e_ops.append(self._read_single_e_op(e_op, dims))
            self._expects.append([])

        # Read options
        self._read_options(options, state0)

        # Write some extra info.
        self.stats = {
            "num_expect": self._e_num,
            "solver": "",
            "method": "",
        }
        if stats:
            self.stats.update(stats)

        if state0 is not None:
            self.add(ts, state0)

    def _e_ops_as_list(self, e_ops):
        """ Promote ``e_ops`` to a list. """
        self._e_ops_keys = False

        if isinstance(e_ops, list):
            pass
        elif e_ops is None:
            e_ops = []
        elif isinstance(e_ops, (Qobj, QobjEvo)):
            e_ops = [e_ops]
        elif callable(e_ops):
            e_ops = [e_ops]
        elif isinstance(e_ops, dict):
            self._e_ops_keys = [e for e in e_ops.keys()]
            e_ops = [e for e in e_ops.values()]
        else:
            raise TypeError("e_ops format not understood.")

        return e_ops

    def _read_single_e_op(self, e_op, dims):
        """ Promote each c_ops to a callable(t, state). """
        if isinstance(e_op, Qobj):
            if dims and e_op.dims[1] != dims:
                raise TypeError("Dimensions of the e_ops do "
                                "not match the state")
            e_op_call = _Expect_Caller(e_op)
        elif isinstance(e_op, QobjEvo):
            if dims and e_op.dims[1] != dims:
                raise TypeError("Dimensions of the e_ops do "
                                "not match the state")
            e_op_call = e_op.expect
        elif callable(e):
            e_op_call = e_op
        else:
            raise TypeError("e_ops format not understood.")
        return e_op_call

    def _read_options(self, options, state0):
        """ Read options. """
        if options['store_states'] is not None:
            self._store_states = options['store_states']
        else:
            self._store_states = self._e_num == 0

        self._store_final_state = options['store_final_state']

        # TODO: Reminder for when reworking options
        # By having separate option for mesolve and sesolve, we could simplify
        # the way we decide whether to normalize the state.

        # We can normalize ket and dm, but not operators.
        if state0 is None:
            # Cannot guess the type of state, we trust the option.
            normalize = options['normalize_output'] in {True, 'all'}
        elif state0.isket:
            normalize = options['normalize_output'] in {'ket', True, 'all'}
        elif (
            state0.dims[0] != state0.dims[1]  # rectangular states
            or state0.issuper  # super operator state
            or abs(state0.norm()-1) > 1e-10  # initial state is not normalized
        ):
            # We don't try to normalize those.
            normalize = False
        else:
            # The state is an operator with a trace of 1,
            # While this is not enough to be 100% certain that we are working
            # with a density matrix, odd are good enough that we go with it.
            normalize = options['normalize_output'] in {'dm', True, 'all'}
        self._normalize_outputs = normalize

    def _normalize(self, state):
        return state * (1/state.norm())

    def add(self, t, state, copy=True):
        """
        Add a state to the results for the time t of the evolution.
        The state is expected to be a Qobj with the right dims.
        """
        self._times.append(t)

        if self._normalize_outputs:
            state = self._normalize(state)
            copy = False  # normalization create a copy.

        if self._store_states:
            self._states.append(state.copy() if copy else state)
        elif self._store_final_state and t >= self._last_time:
            self._last_state = state.copy() if copy else state

        for i, e_call in enumerate(self._e_ops):
            self._expects[i].append(e_call(t, state))

    @property
    def times(self):
        return self._times.copy()

    @property
    def states(self):
        return self._states.copy()

    @property
    def final_state(self):
        if self._store_states:
            return self._states[-1]
        elif self._store_final_state:
            return self._last_state
        else:
            return None

    @property
    def expect(self):
        result = []
        for expect_vals in self._expects:
            result.append(np.array(expect_vals))
        if self._e_ops_keys:
            result = {e: result[n]
                      for n, e in enumerate(self._e_ops_keys)}
        return result

    @property
    def num_expect(self):
        return self._e_num

    @property
    def num_collapse(self):
        if 'num_collapse' in self.stats:
            return self.stats["num_collapse"]
        else:
            return 0

    def __repr__(self):
        out = ""
        out += self.stats['solver'] + "\n"
        out += "solver : " + self.stats['method'] + "\n"
        out += "number of expect : {}\n".format(self._e_num)
        if self._store_states:
            out += "State saved\n"
        elif self._store_final_state:
            out += "Final state saved\n"
        else:
            out += "State not available\n"
        out += "times from {} to {} in {} steps\n".format(self.times[0],
                                                          self.times[-1],
                                                          len(self.times))
        return out


class MultiTrajResult:
    """
    It contains the results of simulations with multiple trajectories.

    Parameters
    ----------
    ntraj : int
        Number of trajectories expected.

    state : Qobj
        Initial state of the evolution.

    tlist : array_like
        Times at which the expectation results are desired.

    e_ops : Qobj, QobjEvo, callable or iterable of these.
        list of Qobj or QobjEvo to compute the expectation values.
        Alternatively, function[s] with the signature f(t, state) -> expect
        can be used.

    solver_id : int, [optional]
        Identifier of the Solver creating the object.

    options : SolverResultsOptions, [optional]
        Options conserning result to save.
    """
    def __init__(self, ntraj, state, tlist, e_ops, solver_id=0, options=None):
        """
        Parameters:
        -----------
        num_c_ops: int
            Number of collapses operator used in the McSolver
        """
        from . import SolverResultsOptions
        self.options = copy(options) or SolverResultsOptions()
        self.initial_state = state
        self.tlist = tlist
        self.solver_id = solver_id
        self._save_traj = self.options['keep_runs_results']
        self.trajectories = []
        self._sum_states = None
        self._sum_last_states = None
        self._sum_expect = None
        self._sum2_expect = None
        e_ops = e_ops or []
        if not isinstance(e_ops, (list, dict)):
            e_ops = [e_ops]
        self.num_e_ops = len(e_ops or ())
        self.e_ops = e_ops
        self._e_ops_dict = e_ops if isinstance(e_ops, dict) else False
        self.num_c_ops = 0
        self._target_ntraj = ntraj
        self._num = 0
        self.seeds = []
        self.stats = {
            "num_expect": self.num_e_ops,
            "solver": "",
            "method": "",
        }
        self._target_tols = None
        self._tol_reached = False

    def add(self, one_traj):
        """
        Add a trajectory.
        Return the number of trajectories still needed to reach the desired
        tolerance.
        """
        if self._save_traj:
            self.trajectories.append(one_traj)
        else:
            if self._num == 0:
                self.trajectories = [one_traj]
                if one_traj.states and one_traj.states[0].isket:
                    self._sum_states = [state.proj()
                                        for state in one_traj.states]
                else:
                    self._sum_states = one_traj.states
                if one_traj.final_state and one_traj.final_state.isket:
                    self._sum_last_states = one_traj.final_state.proj()
                else:
                    self._sum_last_states = one_traj.final_state
                self._sum_expect = [np.array(expect)
                                    for expect in one_traj._expects]
                self._sum2_expect = [np.abs(np.array(expect))**2
                                     for expect in one_traj._expects]
            else:
                if self._sum_states and one_traj.states[0].isket:
                    self._sum_states = [
                        state.proj() + accu
                        for accu, state
                        in zip(self._sum_states, one_traj.states)
                    ]
                elif self._sum_states:
                    self._sum_states = [
                        state + accu
                        for accu, state
                        in zip(self._sum_states, one_traj.states)
                    ]
                if self._sum_last_states and one_traj.final_state.isket:
                    self._sum_last_states += one_traj.final_state.proj()
                elif self._sum_last_states:
                    self._sum_last_states += one_traj.final_state

                if self._sum_expect:
                    self._sum_expect = [
                        np.array(one) + accu
                        for one, accu
                        in zip(one_traj._expects, self._sum_expect)
                    ]
                    self._sum2_expect = [
                        np.abs(np.array(one))**2 + accu
                        for one, accu
                        in zip(one_traj._expects, self._sum2_expect)
                    ]
        self._num += 1
        if hasattr(one_traj, 'seed'):
            self.seeds.append(one_traj.seed)

        if self._target_tols is not None:
            num_traj = self._num
            if num_traj >= self.next_check:
                traj_left = self._check_expect_tol()
                target = traj_left + num_traj
                confidence = 0.5 * (1 - 3 / num_traj)
                confidence += 0.5 * min(1 / abs(target - self.last_target), 1)
                self.next_check = int(traj_left * confidence + num_traj)
                self.last_target = target
                return traj_left
            else:
                return max(self.last_target - self._num, 1)
        else:
            return np.inf

    def set_expect_tol(self, target_tol):
        """
        Set the capacity to stop the map when the estimated error on the
        expectation values is within given tolerance.

        Error estimation is done with jackknife resampling.

        target_tol : float, list, [optional]
            Target tolerance of the evolution. The evolution will compute
            trajectories until the error on the expectation values is lower
            than this tolerance. The error is computed using jackknife
            resampling. ``target_tol`` can be an absolute tolerance, a pair of
            absolute and relative tolerance, in that order. Lastly, it can be a
            list of pairs of (atol, rtol) for each e_ops.
        """
        self._target_tols = None
        self._tol_reached = False
        if not target_tol:
            return
        if not self.num_e_ops:
            raise ValueError("Cannot target a tolerance without e_ops")
        self.next_check = 5
        self.last_target = np.inf

        targets = np.array(target_tol)
        if targets.ndim == 0:
            self._target_tols = np.array([(target_tol, 0.)] * self.num_e_ops)
        elif targets.shape == (2,):
            self._target_tols = np.ones((self.num_e_ops, 2)) * targets
        elif targets.shape == (self.num_e_ops, 2):
            self._target_tols = targets
        else:
            raise ValueError("target_tol must be a number, a pair of (atol, "
                             "rtol) or a list of (atol, rtol) for each e_ops")

    def spawn(self, _super, oper_state):
        """
        Create a :cls:`Result` for a trajectory of this ``MultiTrajResult``.
        """
        return Result(self.e_ops, self.options, _super, oper_state)

    def _check_expect_tol(self):
        """
        Compute the error on the expectation values using jackknife resampling.
        Return the approximate number of trajectories needed to reach the
        desired tolerance.
        """
        if self._num <= 1:
            return np.inf
        avg = np.array(self._mean_expect())
        avg2 = np.array(self._mean_expect2())
        target = np.array([atol + rtol * mean
                           for mean, (atol, rtol)
                           in zip(avg, self._target_tols)])
        traj_left = np.max((avg2 - abs(avg)**2) / target**2 - self._num + 1)
        self._tol_reached = traj_left < 0
        return traj_left

    @property
    def runs_states(self):
        """
        States of every runs as ``states[run][t]``.
        """
        if self._save_traj:
            return [traj.states for traj in self.trajectories]
        else:
            return None

    @property
    def average_states(self):
        """
        States averages as density matrices.
        """
        if not self._save_traj:
            finals = self._sum_states
        elif self.trajectories[0].states[0].isket:
            finals = [state.proj() for state in self.trajectories[0].states]
            for i in range(1, len(self.trajectories)):
                finals = [state.proj() + final for final, state
                          in zip(finals, self.trajectories[i].states)]
        else:
            finals = [state for state in self.trajectories[0].states]
            for i in range(1, len(self.trajectories)):
                finals = [state + final for final, state
                          in zip(finals, self.trajectories[i].states)]
        return [final / self._num for final in finals]

    @property
    def states(self):
        """
        Runs final states if available, average otherwise.
        This imitate v4's behaviour, expect for the steady state which must be
        obtained directly.
        """
        return self.runs_states or self.average_states

    @property
    def runs_final_states(self):
        """
        Last states of each trajectories.
        """
        if self._save_traj:
            return [traj.final_state for traj in self.trajectories]
        else:
            return None

    @property
    def average_final_state(self):
        """
        Last states of each trajectories averaged into a density matrix.
        """
        if self.trajectories[0].final_state is None:
            return None
        if not self._save_traj:
            final = self._sum_last_states
        elif self.trajectories[0].states[0].isket:
            final = sum(traj.final_state.proj() for traj in self.trajectories)
        else:
            final = sum(traj.final_state for traj in self.trajectories)
        return final / self._num

    @property
    def final_state(self):
        """
        Runs final states if available, average otherwise.
        This imitate v4's behaviour.
        """
        return self.runs_final_states or self.average_final_state

    @property
    def steady_state(self):
        """
        Average the states at all times of every runs as a density matrix.
        Should converge to the steady state with long times.
        """
        return sum(self.average_states) / len(self.times)

    def _format_expect(self, expect):
        """
        Restore the dict format when needed.
        """
        if self._e_ops_dict:
            expect = {e: expect[n]
                      for n, e in enumerate(self._e_ops_dict.keys())}
        return expect

    def _mean_expect(self):
        """
        Average of expectation values as list of numpy array.
        """
        if self._save_traj:
            return [np.mean(
                np.stack([traj._expects[i] for traj in self.trajectories]),
                axis=0
            ) for i in range(self.num_e_ops)]
        else:
            return [sum_expect / self._num
                    for sum_expect in self._sum_expect]

    def _mean_expect2(self):
        """
        Average of the square of expectation values as list of numpy array.
        """
        if self._save_traj:
            return [np.mean(
                np.stack([np.abs(traj._expects[i])**2
                          for traj in self.trajectories]),
                axis=0
            ) for i in range(self.num_e_ops)]
        else:
            return [sum_expect / self._num
                    for sum_expect in self._sum2_expect]

    @property
    def average_expect(self):
        """
        Average of the expectation values.
        Return a ``dict`` if ``e_ops`` was one.
        """
        result = self._mean_expect()
        return self._format_expect(result)

    @property
    def std_expect(self):
        """
        Standard derivation of the expectation values.
        Return a ``dict`` if ``e_ops`` was one.
        """
        avg = self._mean_expect()
        avg2 = self._mean_expect2()
        result = [np.sqrt(a2 - abs(a*a)) for a, a2 in zip(avg, avg2)]
        return self._format_expect(result)

    @property
    def runs_expect(self):
        """
        Expectation values for each trajectories as ``expect[e_op][run][t]``.
        Return ``None`` is run data is not saved.
        Return a ``dict`` if ``e_ops`` was one.
        """
        if not self._save_traj:
            return None
        result = [np.stack([traj._expects[i] for traj in self.trajectories])
                  for i in range(self.num_e_ops)]
        return self._format_expect(result)

    def expect_traj_avg(self, ntraj=-1):
        """
        Average of the expectation values for the ``ntraj`` first runs.
        Return a ``dict`` if ``e_ops`` was one.
        """
        if not self._save_traj:
            return None
        result = [
            np.mean(np.stack([
                traj._expects[i]
                for traj in self.trajectories[:ntraj]
            ]), axis=0)
            for i in range(self.num_e_ops)
        ]
        return self._format_expect(result)

    def expect_traj_std(self, ntraj=-1):
        """
        Standard derivation of the expectation values for the ``ntraj``
        first runs.
        Return a ``dict`` if ``e_ops`` was one.
        """
        if not self._save_traj:
            return None
        result = [
            np.std(np.stack([
                traj._expects[i]
                for traj in self.trajectories[:ntraj]
            ]), axis=0)
            for i in range(self.num_e_ops)
        ]
        return self._format_expect(result)

    @property
    def expect(self):
        """
        Runs expectation values if available, average otherwise.
        This imitate v4's behaviour.
        """
        return self.runs_expect or self.average_expect

    def __repr__(self):
        out = ""
        out += self.stats['solver'] + "\n"
        out += "solver : " + self.stats['method'] + "\n"
        if self._save_traj:
            out += "{} runs saved\n".format(self.num_traj)
        else:
            out += "{} trajectories averaged\n".format(self.num_traj)
        out += "number of expect : {}\n".format(self.num_e_ops)
        if self.trajectories[0]._store_states:
            out += "States saved\n"
        elif self.trajectories[0]._store_final_state:
            out += "Final state saved\n"
        else:
            out += "State not available\n"
        out += "times from {} to {} in {} steps\n".format(
            self.times[0], self.times[-1], len(self.times))
        return out

    @property
    def times(self):
        return self.tlist

    @property
    def num_traj(self):
        return self._num

    @property
    def num_expect(self):
        return self.num_e_ops

    @property
    def num_collapse(self):
        return self.num_c_ops

    @property
    def end_condition(self):
        if self._target_tols is not None and self._tol_reached:
            return "target tolerance reached"
        elif self._target_ntraj == self._num:
            return "ntraj reached"
        else:
            return "timeout"


class McResult(MultiTrajResult):
    # Collapse are only produced by mcsolve.
    def __init__(self, ntraj, state, tlist, e_ops, solver_id=0, options=None):
        super().__init__(ntraj, state, tlist,
                         e_ops, solver_id=solver_id, options=options)
        self._collapse = []

    def add(self, one_traj):
        out = super().add(one_traj)
        if hasattr(one_traj, 'collapse'):
            self._collapse.append(one_traj.collapse)
        return out

    @property
    def collapse(self):
        """
        For each runs, a list of every collapse as a tuple of the time it
        happened and the corresponding ``c_ops`` index.
        """
        return self._collapse

    @property
    def col_times(self):
        """
        List of the times of the collapses for each runs.
        """
        if self._collapse is None:
            return None
        out = []
        for col_ in self.collapse:
            col = list(zip(*col_))
            col = ([] if len(col) == 0 else col[0])
            out.append(col)
        return out

    @property
    def col_which(self):
        """
        List of the indexes of the collapses for each runs.
        """
        if self._collapse is None:
            return None
        out = []
        for col_ in self.collapse:
            col = list(zip(*col_))
            col = ([] if len(col) == 0 else col[1])
            out.append(col)
        return out

    @property
    def photocurrent(self):
        """
        Average photocurrent or measurement of the evolution.
        """
        if self._collapse is None:
            return None
        cols = [[] for _ in range(self.num_c_ops)]
        tlist = self.times
        for collapses in self.collapse:
            for t, which in collapses:
                cols[which].append(t)
        mesurement = [
            np.histogram(cols[i], tlist)[0] / np.diff(tlist) / self._num
            for i in range(self.num_c_ops)
        ]
        return mesurement

    @property
    def runs_photocurrent(self):
        """
        Photocurrent or measurement of each runs.
        """
        if self._collapse is None:
            return None
        tlist = self.times
        measurements = []
        for collapses in self.collapse:
            cols = [[] for _ in range(self.num_c_ops)]
            for t, which in collapses:
                cols[which].append(t)
            measurements.append([
                np.histogram(cols[i], tlist)[0] / np.diff(tlist)
                for i in range(self.num_c_ops)
            ])
        return measurements
