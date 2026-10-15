"""
main.py
-------
CLI entry point.

Usage:
    python3 main.py "dy/dx = x*y"
    python3 main.py            (interactive mode)

Accepted syntax:
    y'        -> dy/dx
    y''       -> d2y/dx2
    dy/dx     -> dy/dx
    y         -> y(x)   (implicit)
    Standard python/sympy operators: + - * / ** , functions: exp, sin, cos, log, sqrt
"""

import sys
from classifier import classify
from solver import solve


def run(equation_str):
    print(f"\nInput: {equation_str}")
    classification, expr = classify(equation_str)
    result = solve(classification, expr)
    result.print_steps()
    return result


def main():
    if len(sys.argv) > 1:
        equation_str = " ".join(sys.argv[1:])
        run(equation_str)
        return

    print("ODE Classifier & Step Solver (no AI tokens used — pure symbolic math)")
    print("Type an ODE (e.g. \"y' + y = x\"), or 'quit' to exit.\n")
    while True:
        try:
            equation_str = input("ODE> ").strip()
        except EOFError:
            break
        if equation_str.lower() in ("quit", "exit", ""):
            break
        try:
            run(equation_str)
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
