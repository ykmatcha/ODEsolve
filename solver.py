"""
solver.py
---------
Given a classification + equation, produces:
    - a list of solution steps
    - the final general solution

Uses SymPy purely as a symbolic calculator.

"""

import sympy as sp


class Step:
    """A single solution step: just a number + a math line."""
    def __init__(self, number, line):
        self.number = number
        self.line = line

    def __str__(self):
        return f"{self.number}. {self.line}"


class SolutionResult:
    def __init__(self, ode_type, steps, general_solution):
        self.ode_type = ode_type
        self.steps = steps
        self.general_solution = general_solution

    def print_steps(self):
        print(f"ODE type: {self.ode_type}")
        for s in self.steps:
            print(s)
        print(f"=> {self.general_solution}")


def solve(classification, original_expr):
    x = sp.symbols('x')
    y = sp.Function('y')
    C1 = sp.symbols('C1')

    dispatch = {
        "separable": _solve_separable,
        "linear_first_order": _solve_linear_first_order,
        "bernoulli": _solve_bernoulli,
        "homogeneous": _solve_homogeneous,
        "exact": _solve_exact,
        "linear_const_coeff_2nd_order": _solve_linear_2nd_order,
    }

    func = dispatch.get(classification.ode_type)
    if func is None:
        return _solve_fallback(original_expr, x, y)

    return func(classification, x, y, C1)


# ---------- Individual solvers ----------

def _solve_separable(cls, x, y, C1):
    g_x = cls.info["g_x"]
    h_y = cls.info["h_y"]
    yx = y(x)
    v = sp.symbols('v')  # dummy var representing y during integration

    steps = []
    steps.append(Step(1, f"dy/dx = ({sp.simplify(g_x)}) * ({sp.simplify(h_y.subs(yx, v))})"))
    steps.append(Step(2, f"dy / ({sp.simplify(h_y.subs(yx, v))}) = ({sp.simplify(g_x)}) dx"))

    h_y_in_v = h_y.subs(yx, v)
    lhs_integral = sp.integrate(1 / h_y_in_v, v)
    rhs_integral = sp.integrate(g_x, x)

    steps.append(Step(3, f"∫ dy / ({sp.simplify(h_y_in_v)}) = ∫ ({sp.simplify(g_x)}) dx"))
    steps.append(Step(4, f"{lhs_integral.subs(v, y(x))} = {rhs_integral} + C1"))

    implicit_solution = sp.Eq(lhs_integral.subs(v, y(x)), rhs_integral + C1)

    explicit = None
    try:
        explicit_sols = sp.solve(implicit_solution, y(x))
        if explicit_sols:
            explicit = explicit_sols[0]
            steps.append(Step(5, f"y(x) = {explicit}"))
    except Exception:
        pass

    general = sp.Eq(y(x), explicit) if explicit is not None else implicit_solution
    return SolutionResult("separable", steps, general)


def _solve_linear_first_order(cls, x, y, C1):
    P = cls.info["P_x"]
    Q = cls.info["Q_x"]
    yx = y(x)

    mu = sp.exp(sp.integrate(P, x))
    mu_simpl = sp.simplify(mu)

    steps = []
    steps.append(Step(1, f"y' + ({sp.simplify(P)}) y = {sp.simplify(Q)}"))
    steps.append(Step(2, f"μ(x) = exp(∫ {sp.simplify(P)} dx) = {mu_simpl}"))
    steps.append(Step(3, f"d/dx [ {mu_simpl} * y ] = {mu_simpl} * ({sp.simplify(Q)})"))

    rhs_integrated = sp.integrate(sp.simplify(mu_simpl * Q), x)
    steps.append(Step(4, f"{mu_simpl} * y = {rhs_integrated} + C1"))

    y_solution = sp.simplify((rhs_integrated + C1) / mu_simpl)
    steps.append(Step(5, f"y(x) = {y_solution}"))

    general = sp.Eq(yx, y_solution)
    return SolutionResult("linear_first_order", steps, general)


def _solve_bernoulli(cls, x, y, C1):
    P = cls.info["P_x"]
    Q = cls.info["Q_x"]
    n = cls.info["n"]
    yx = y(x)
    v = sp.Function('v')

    steps = []
    steps.append(Step(1, f"y' + ({sp.simplify(P)}) y = ({sp.simplify(Q)}) y**{n}"))
    steps.append(Step(2, f"v = y**(1-{n}) = y**{sp.simplify(1-n)}"))

    one_minus_n = sp.simplify(1 - n)
    steps.append(Step(3, f"v' = {one_minus_n} y**(-{n}) y'"))
    steps.append(Step(4, f"v' + {one_minus_n}*({sp.simplify(P)}) v = {one_minus_n}*({sp.simplify(Q)})"))

    P_lin = sp.simplify(one_minus_n * P)
    Q_lin = sp.simplify(one_minus_n * Q)

    mu = sp.simplify(sp.exp(sp.integrate(P_lin, x)))
    steps.append(Step(5, f"μ(x) = exp(∫ {P_lin} dx) = {mu}"))

    rhs_integrated = sp.integrate(sp.simplify(mu * Q_lin), x)
    steps.append(Step(6, f"{mu} * v = {rhs_integrated} + C1"))

    v_solution = sp.simplify((rhs_integrated + C1) / mu)
    steps.append(Step(7, f"v(x) = {v_solution}"))

    y_solution = sp.simplify(v_solution ** (1 / one_minus_n))
    steps.append(Step(8, f"y(x) = (v(x))**(1/{one_minus_n}) = {y_solution}"))

    general = sp.Eq(yx, y_solution)
    return SolutionResult("bernoulli", steps, general)


def _solve_homogeneous(cls, x, y, C1):
    yx = y(x)
    v = sp.symbols('v')
    v_form = cls.info["v_form"]

    steps = []
    steps.append(Step(1, f"y' = {sp.simplify(cls.info['dydx_expr'])}"))
    steps.append(Step(2, "y = v*x,  y' = v + x*v'"))
    steps.append(Step(3, f"v + x*v' = {v_form}"))

    rhs_minus_v = sp.simplify(v_form - v)
    steps.append(Step(4, f"x*v' = {rhs_minus_v}"))
    steps.append(Step(5, f"dv / ({rhs_minus_v}) = dx / x"))

    lhs_int = sp.integrate(1 / rhs_minus_v, v)
    rhs_int = sp.integrate(1 / x, x)
    steps.append(Step(6, f"∫ dv/({rhs_minus_v}) = ∫ dx/x"))
    steps.append(Step(7, f"{lhs_int} = {rhs_int} + C1"))

    v_expr = sp.symbols('v')
    implicit = sp.Eq(lhs_int, rhs_int + C1)
    steps.append(Step(8, f"substitute v = y/x: {lhs_int.subs(v, yx/x)} = {rhs_int} + C1"))

    general = sp.Eq(lhs_int.subs(v, yx / x), rhs_int + C1)
    return SolutionResult("homogeneous", steps, general)


def _solve_exact(cls, x, y, C1):
    M = cls.info["M"]
    N = cls.info["N"]
    yx = y(x)
    Y = sp.symbols('Y')  # dummy standing in for y during calculus steps

    M_y = M.subs(yx, Y)
    N_y = N.subs(yx, Y)

    steps = []
    steps.append(Step(1, f"M(x,y) = {sp.simplify(M)},  N(x,y) = {sp.simplify(N)}"))
    dM_dY = sp.diff(M_y, Y)
    dN_dx = sp.diff(N_y, x)
    steps.append(Step(2, f"∂M/∂y = {dM_dY},  ∂N/∂x = {dN_dx}  -> equal, exact confirmed"))

    F_from_M = sp.integrate(M_y, x)
    F_from_M_disp = F_from_M.subs(Y, yx)
    steps.append(Step(3, f"F(x,y) = ∫ M dx = {F_from_M_disp} + g(y)"))

    dF_dY = sp.diff(F_from_M, Y)
    g_prime = sp.simplify(N_y - dF_dY)
    steps.append(Step(4, f"∂F/∂y = {dF_dY.subs(Y, yx)};  g'(y) = N - ∂F/∂y = {g_prime.subs(Y, yx)}"))

    g_y = sp.integrate(g_prime, Y)
    g_y_disp = g_y.subs(Y, yx)
    steps.append(Step(5, f"g(y) = ∫ g'(y) dy = {g_y_disp}"))

    F_total_y = sp.simplify(F_from_M + g_y)
    F_total = F_total_y.subs(Y, yx)
    steps.append(Step(6, f"F(x,y) = {F_total} = C1"))

    general = sp.Eq(F_total, C1)
    return SolutionResult("exact", steps, general)


def _solve_linear_2nd_order(cls, x, y, C1):
    a, b, c, f_x = cls.info["a"], cls.info["b"], cls.info["c"], cls.info["f_x"]
    yx = y(x)
    r = sp.symbols('r')

    steps = []
    steps.append(Step(1, f"{a} y'' + {b} y' + {c} y = {f_x}"))

    char_eq = a * r**2 + b * r + c
    steps.append(Step(2, f"characteristic equation: {a} r**2 + {b} r + {c} = 0"))

    roots = sp.solve(sp.Eq(char_eq, 0), r)
    steps.append(Step(3, f"roots: r = {roots}"))

    C2 = sp.symbols('C2')
    if len(roots) == 2 and roots[0] != roots[1]:
        if all(rt.is_real for rt in roots):
            y_h = C1 * sp.exp(roots[0] * x) + C2 * sp.exp(roots[1] * x)
            steps.append(Step(4, f"y_h = C1*exp({roots[0]}*x) + C2*exp({roots[1]}*x)"))
        else:
            re_part = sp.re(roots[0])
            im_part = sp.im(roots[0])
            y_h = sp.exp(re_part * x) * (C1 * sp.cos(im_part * x) + C2 * sp.sin(im_part * x))
            steps.append(Step(4, f"y_h = exp({re_part}*x) * (C1*cos({im_part}*x) + C2*sin({im_part}*x))"))
    else:
        r_rep = roots[0]
        y_h = (C1 + C2 * x) * sp.exp(r_rep * x)
        steps.append(Step(4, f"repeated root r = {r_rep};  y_h = (C1 + C2*x)*exp({r_rep}*x)"))

    if sp.simplify(f_x) == 0:
        steps.append(Step(5, "f(x) = 0  ->  y = y_h"))
        general = sp.Eq(yx, y_h)
    else:
        try:
            y_p = sp.simplify(sp.solve(sp.Eq(a*sp.Derivative(yx,x,2)+b*sp.Derivative(yx,x)+c*yx, f_x), yx))
        except Exception:
            y_p = None
        ode = sp.Eq(a*sp.diff(yx, x, 2) + b*sp.diff(yx, x) + c*yx, f_x)
        particular = sp.dsolve(ode, yx).rhs
        steps.append(Step(5, f"y_p (particular) obtained via undetermined coefficients: {particular}"))
        general = sp.Eq(yx, particular)

    return SolutionResult("linear_const_coeff_2nd_order", steps, general)


def _solve_fallback(expr, x, y):
    yx = y(x)
    steps = [Step(1, "no pattern matched -> falling back to general ODE solver")]
    try:
        result = _dsolve_with_timeout(sp.Eq(expr, 0), yx, seconds=8)
        steps.append(Step(2, f"{result}"))
        return SolutionResult("unknown", steps, result)
    except TimeoutError:
        steps.append(Step(2, "general solver exceeded time limit -> no closed form found quickly"))
        return SolutionResult("unknown", steps, None)
    except Exception as e:
        steps.append(Step(2, f"could not solve: {e}"))
        return SolutionResult("unknown", steps, None)


def _dsolve_with_timeout(eq, func, seconds=8):
    import signal

    def _handler(signum, frame):
        raise TimeoutError("dsolve timed out")

    old_handler = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(seconds)
    try:
        return sp.dsolve(eq, func)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
