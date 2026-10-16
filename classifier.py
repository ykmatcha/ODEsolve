"""
classifier.py
-------------
Detects what type of first-order or simple higher-order ODE an equation is.

Classification is done purely through symbolic pattern matching with SymPy (treated here as a calculator/CAS).

USE WITH CAUTION: This is a prototype and not guaranteed to be correct for all inputs. It is intended for educational purposes and may not handle all edge cases or complex ODE forms.

Supported classes (checked in priority order):
    1. separable
    2. linear_first_order
    3. bernoulli
    4. homogeneous
    5. exact
    6. linear_const_coeff_2nd_order   (a y'' + b y' + c y = 0 or = f(x))
    7. unknown (solved through SymPy's general dsolve fallback)
"""

import sympy as sp


class ODEClassification:
    def __init__(self, ode_type, info=None):
        self.ode_type = ode_type
        self.info = info or {}

    def __repr__(self):
        return f"ODEClassification(type={self.ode_type!r}, info={self.info})"


def _get_first_order_form(expr, y, x):
    """
    Try to rearrange expr == 0 into y' = M(x,y)/N(x,y) style pieces
    by isolating Derivative(y(x), x).
    Returns (dydx_solutions) list, or None if no first derivative present.
    """
    yp = sp.Derivative(y(x), x)
    if not expr.has(yp):
        return None
    if any(derivative != yp for derivative in expr.atoms(sp.Derivative)):
        return None
    sols = sp.solve(expr, yp)
    return sols if sols else None


def classify(equation_str):
    """
    equation_str: string like "Eq(y(x).diff(x), x*y(x))" is NOT what user types.
    Instead users type natural math like:
        "dy/dx = x*y"
        "y' + y = x"
        "(x**2+y**2) + 2*x*y*y' = 0"
        "y'' + 3*y' + 2*y = 0"
    This function parses that, builds a SymPy equation, then classifies it.
    """
    x = sp.symbols('x')
    y = sp.Function('y')

    eq = _parse_equation(equation_str, x, y)

    # Try 2nd order linear constant-coefficient first (structurally distinct)
    result = _check_linear_2nd_order(eq, x, y)
    if result:
        return result, eq

    # First-order checks, in a deliberate priority order
    checks = [
        _check_separable,
        _check_bernoulli,
        _check_exact,
        _check_homogeneous,
        _check_linear_first_order,
    ]
    for check in checks:
        result = check(eq, x, y)
        if result:
            return result, eq

    return ODEClassification("unknown"), eq


def _parse_equation(equation_str, x, y):
    """
    Converts a human-friendly string into a SymPy Eq object with
    y(x) and its derivatives. Supports:
        y followed by n primes -> nth derivative of y(x)
        dy/dx -> Derivative(y(x), x)
    """
    import re

    s = equation_str.replace(" ", "").replace("^", "**")
    # Replace dy/dx style first
    s = s.replace("dy/dx", "Derivative(y(x),x)")

    # Replace prime notation, supporting derivatives of any order.
    s = re.sub(
        r"(?<![\w])y('+)",
        lambda match: f"Derivative(y(x),(x,{len(match.group(1))}))",
        s,
    )

    # Replace bare 'y' (not already inside y(x) or Derivative) with y(x)
    # Do this carefully: tokenize-replace using regex word boundary on 'y'
    s = re.sub(r'(?<![\w])y(?![\w(])', 'y(x)', s)

    if "=" in s:
        lhs_str, rhs_str = s.split("=", 1)
        lhs = sp.sympify(lhs_str, locals={"y": y, "x": x, "Derivative": sp.Derivative})
        rhs = sp.sympify(rhs_str, locals={"y": y, "x": x, "Derivative": sp.Derivative})
        expr = sp.expand(lhs - rhs)
    else:
        expr = sp.sympify(s, locals={"y": y, "x": x, "Derivative": sp.Derivative})
        expr = sp.expand(expr)

    return expr


def _check_linear_2nd_order(expr, x, y):
    y2 = sp.Derivative(y(x), x, 2)
    if not expr.has(y2):
        return None
    y1 = sp.Derivative(y(x), x)
    y0 = y(x)

    if any(derivative not in (y1, y2) for derivative in expr.atoms(sp.Derivative)):
        return None

    poly = sp.Poly(expr, y2, y1, y0) if expr.is_polynomial(y2, y1, y0) else None
    if poly is None or poly.total_degree() > 1:
        return None

    a = expr.coeff(y2)
    remainder = sp.expand(expr - a * y2)
    b = remainder.coeff(y1)
    remainder2 = sp.expand(remainder - b * y1)
    c = remainder2.coeff(y0)
    rhs_remainder = sp.expand(remainder2 - c * y0)

    if a.has(x) or b.has(x) or c.has(x):
        return None  # not constant-coefficient; out of scope for this demo
    if a == 0:
        return None

    f_x = sp.simplify(-rhs_remainder)  # since expr = a y'' + b y' + c y - f(x) = 0 form assumed
    return ODEClassification(
        "linear_const_coeff_2nd_order",
        {"a": a, "b": b, "c": c, "f_x": f_x}
    )


def _check_separable(expr, x, y):
    sols = _get_first_order_form(expr, y, x)
    if not sols:
        return None
    for sol in sols:
        sol = sp.simplify(sol)
        num, den = sp.fraction(sp.together(sol))
        # Try splitting num and den into pure-x * pure-y factors
        for target, other in [(num, den)]:
            fx, fy = _split_x_y_factors(target, x, y)
            gx, gy = _split_x_y_factors(other, x, y)
            if fx is not None and gy is not None and fy is not None and gx is not None:
                # y' = [f(x)g(x)] * [h(y)/k(y)] style — check independence
                pass
        # Simpler robust test: y' = g(x) * h(y)
        gx, hy = _try_factor_as_x_times_y(sol, x, y)
        if gx is not None:
            return ODEClassification("separable", {"g_x": gx, "h_y": hy, "dydx_expr": sol})
    return None


def _try_factor_as_x_times_y(expr, x, y):
    """Attempt expr = g(x) * h(y(x)). Returns (g(x), h(y)) or (None, None)."""
    expr = sp.simplify(expr)
    yx = y(x)

    if not expr.has(yx):
        return expr, sp.Integer(1)
    if not expr.has(x):
        return sp.Integer(1), expr

    # Approach 1: factor_list — works when expr is a clean product of factors
    try:
        factors = sp.factor_list(expr)[1]
        g_parts, h_parts = [], []
        ok = True
        Y_test = sp.symbols('Y_test')
        for factor, mult in factors:
            f = factor ** mult
            f_sub = f.subs(yx, Y_test)
            depends_on_x = f_sub.has(x)
            depends_on_y = f.has(yx)
            if depends_on_y and not depends_on_x:
                h_parts.append(f)
            elif depends_on_x and not depends_on_y:
                g_parts.append(f)
            else:
                ok = False
                break
        if ok and (g_parts or h_parts):
            g = sp.Mul(*g_parts) if g_parts else sp.Integer(1)
            h = sp.Mul(*h_parts) if h_parts else sp.Integer(1)
            return g, h
    except sp.PolynomialError:
        pass

    # Approach 2: independence test using a substitution-based split.
    # If expr = g(x)*h(y), then fixing y=y0 gives g(x) up to the constant
    # h(y0); dividing expr by that candidate g(x) should leave something
    # with zero x-dependence. This catches transcendental cases like
    # x*sin(y) that factor_list cannot split (it only factors polynomially).
    try:
        Y = sp.symbols('Y_dummy')
        candidates = []
        for y0_val in (sp.Rational(2, 1), sp.Rational(3, 1), sp.Rational(1, 2),
                       sp.pi / 2, sp.Rational(-1, 1), sp.Rational(5, 1)):
            g_x_raw = sp.simplify(expr.subs(yx, y0_val))
            if g_x_raw == 0 or g_x_raw.has(yx):
                continue
            h_y_raw = sp.simplify(expr / g_x_raw)
            h_y_sub = h_y_raw.subs(yx, Y)
            if sp.simplify(sp.diff(h_y_sub, x)) == 0:
                complexity = sp.count_ops(g_x_raw) + sp.count_ops(h_y_raw)
                candidates.append((complexity, g_x_raw, h_y_raw))
        if candidates:
            candidates.sort(key=lambda c: c[0])
            _, g_best, h_best = candidates[0]
            return g_best, h_best
    except Exception:
        pass

    return None, None


def _split_x_y_factors(expr, x, y):
    return None, None  # placeholder kept simple; main logic uses _try_factor_as_x_times_y


def _check_linear_first_order(expr, x, y):
    sols = _get_first_order_form(expr, y, x)
    if not sols:
        return None
    yx = y(x)
    for sol in sols:
        # y' = sol  =>  y' - sol = 0. Want form y' + P(x) y = Q(x)
        rhs = sp.expand(sol)
        # Collect coefficient of y(x) in rhs
        P_candidate = sp.simplify(sp.diff(rhs, yx))
        if P_candidate.has(yx):
            continue  # not linear in y
        Q = sp.simplify(rhs - P_candidate * yx)
        if Q.has(yx):
            continue
        P = sp.simplify(-P_candidate)
        return ODEClassification("linear_first_order", {"P_x": P, "Q_x": Q})
    return None


def _check_bernoulli(expr, x, y):
    sols = _get_first_order_form(expr, y, x)
    if not sols:
        return None
    yx = y(x)
    n = sp.symbols('n_bernoulli')
    for sol in sols:
        rhs = sp.expand(sol)
        # Try y' = P(x) y + Q(x) y^n  for some numeric n != 0,1
        # Heuristic: look at terms in rhs as polynomial-ish in yx
        terms = sp.Add.make_args(rhs)
        p_term, q_term, power = sp.Integer(0), None, None
        leftover = []
        for t in terms:
            t_simpl = sp.simplify(t)
            if not t_simpl.has(yx):
                leftover.append(t_simpl)
                continue
            # extract power of yx
            poly_t = sp.Poly(t_simpl, yx) if t_simpl.is_polynomial(yx) else None
            deg = None
            if poly_t is not None and poly_t.degree() >= 0:
                deg = poly_t.degree()
            else:
                # might be y(x)**n with non-integer n
                if t_simpl.has(yx**sp.Wild('w')):
                    pass
                base, exp_ = t_simpl.as_base_exp() if t_simpl.is_Pow else (None, None)
            if deg == 1:
                coeff = t_simpl / yx
                p_term += coeff
            elif deg is not None and deg != 1:
                coeff = sp.simplify(t_simpl / yx**deg)
                if not coeff.has(yx):
                    q_term = coeff
                    power = deg
                else:
                    return None
            else:
                # try matching pattern coeff*y**n directly
                w_coeff, w_n = sp.symbols('w_coeff w_n')
                m = t_simpl.match(w_coeff * yx**w_n)
                if m and not m[w_coeff].has(yx) and not m[w_n].has(yx):
                    if m[w_n] == 1:
                        p_term += m[w_coeff]
                    else:
                        q_term = m[w_coeff]
                        power = m[w_n]
                else:
                    return None
        if leftover:
            return None  # has a free term independent of y -> not pure Bernoulli
        if q_term is None or power is None or power in (0, 1):
            continue
        return ODEClassification("bernoulli", {"P_x": p_term, "Q_x": q_term, "n": power})
    return None


def _check_homogeneous(expr, x, y):
    sols = _get_first_order_form(expr, y, x)
    if not sols:
        return None
    yx = y(x)
    v = sp.symbols('v')
    for sol in sols:
        rhs = sp.simplify(sol)
        try:
            test_expr = rhs.subs(yx, v * x)
            ratio = sp.simplify(test_expr - rhs.subs(yx, v * x))  # always 0, placeholder
            # True test: f(tx, t*y) == f(x,y) i.e. function of y/x only
            expr_v = sp.simplify(rhs.subs(yx, v * x))
            if expr_v.has(x):
                # check if it simplifies to function of v alone after substitution
                simplified = sp.simplify(expr_v)
                if simplified.has(x):
                    continue
            return ODEClassification("homogeneous", {"dydx_expr": rhs, "v_form": sp.simplify(rhs.subs(yx, v*x))})
        except Exception:
            continue
    return None


def _check_exact(expr, x, y):
    """
    Looks for form M(x,y) + N(x,y) y' = 0 and tests dM/dy == dN/dx.
    """
    sols = _get_first_order_form(expr, y, x)
    yx = y(x)
    yp = sp.Derivative(yx, x)

    if not sols:
        return None

    N = expr.coeff(yp)
    M = sp.expand(expr - N * yp)
    if N == 0:
        return None

    yvar = sp.symbols('y_dummy')
    M_sub = M.subs(yx, yvar)
    N_sub = N.subs(yx, yvar)

    dM_dy = sp.diff(M_sub, yvar)
    dN_dx = sp.diff(N_sub, x)
    if sp.simplify(dM_dy - dN_dx) == 0:
        return ODEClassification("exact", {"M": M, "N": N})
    return None
