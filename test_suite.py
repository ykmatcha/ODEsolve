"""
tests/test_suite.py
--------------------
Regression tests for classifier + solver. No AI involved — just asserts
that classification labels are sensible and solving completes without
hanging or crashing, comparing against known textbook structure.

Run with:  python3 tests/test_suite.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import sympy as sp
from classifier import classify
from solver import solve

PASS = 0
FAIL = 0


def check(name, equation_str, expected_type):
    global PASS, FAIL
    cls, expr = classify(equation_str)
    result = solve(cls, expr)
    ok = (cls.ode_type == expected_type)
    status = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    print(f"[{status}] {name}: expected={expected_type} got={cls.ode_type}")
    if not ok:
        print(f"        equation: {equation_str}")
    return result


def main():
    # Separable takes priority when an equation is separable, even if it
    # could also be solved as linear/Bernoulli -- it's the simpler method.
    check("separable-also-linear", "dy/dx = x*y", "separable")
    check("separable-also-bernoulli", "y' + y = y**2", "separable")
    check("separable-transcendental", "dy/dx = x*sin(y)", "separable")

    # Genuinely linear (not separable): P(x), Q(x) don't factor into a
    # single g(x)*h(y) product.
    check("linear", "y' + 2*y = x", "linear_first_order")

    # Genuinely Bernoulli (not separable): sum of two terms in y that
    # can't be written as one product of an x-function and a y-function.
    check("bernoulli-nonseparable", "y' + y/x = x*y**2", "bernoulli")

    check("homogeneous", "dy/dx = (x**2+y**2)/(x*y)", "homogeneous")
    check("exact-also-homog", "2*x*y + (x**2+3*y**2)*y' = 0", "exact")
    check("exact-pure", "(2*x+y**3) + (3*x*y**2+1)*y' = 0", "exact")

    check("2nd-order-distinct-real-roots", "y'' + 3*y' + 2*y = 0", "linear_const_coeff_2nd_order")
    check("2nd-order-forced", "y'' - y = x", "linear_const_coeff_2nd_order")
    check("2nd-order-complex-roots", "y'' + y = 0", "linear_const_coeff_2nd_order")
    check("2nd-order-repeated-root", "y'' + 2*y' + y = 0", "linear_const_coeff_2nd_order")

    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    main()
