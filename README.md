# ODE SOLVE README

ODESOLVE a first-order or simple second-order ODE and solves it,
printing each algebraic step as a plain math line
Classification and solving are both done with
deterministic symbolic-math code (SymPy used purely as a calculator:
derivatives, integrals, algebraic solving).

This program does NOT solve laplace equations
## Files

- `classifier.py` — parses the equation string into a SymPy expression
  and detects its ODE type via pattern matching:
  - separable
  - linear (first order)
  - Bernoulli
  - homogeneous
  - exact
  - linear, constant-coefficient, second order
  - falls back to SymPy's general `dsolve` (time-boxed) if nothing matches
- `solver.py` — given a classification, runs the textbook solution
  method for that type and records each algebraic step (`Step` objects),
  with no explanatory prose attached.
- `main.py` — CLI / interactive entry point.
- `web_app.py` — local browser interface, served on port 3000 by default.
- `test_suite.py` — regression tests covering each type.
- `test_web_app.py` — tests for the web interface and input validation.

## Usage

```bash
python3 main.py "dy/dx = x*y"
python3 main.py "y' + 2*y = x"
python3 main.py "y' + y = y**2"
python3 main.py "dy/dx = (x**2+y**2)/(x*y)"
python3 main.py "2*x*y + (x**2+3*y**2)*y' = 0"
python3 main.py "y'' + 3*y' + 2*y = 0"
```

Or run interactively:

```bash
python3 main.py
ODE> y' + y/x = x*y**2
```

## Run the web app

Start the local web server from the project directory:

```bash
python3 web_app.py
```

Open <http://127.0.0.1:3000> in your browser. To choose another port, use
`python3 web_app.py --port 3001`.

In VS Code when the project is running in a remote environment:

1. Start `python3 web_app.py` in the integrated terminal.
2. Open the **Ports** view (View → Open View → Ports).
3. Choose **Forward a Port**, enter `3000`, and open the forwarded address.

The server listens on `127.0.0.1` and is intended for local/forwarded use,
not direct public exposure.

## Input syntax

| You type     | Means                  |
|--------------|-------------------------|
| `y'`         | dy/dx                   |
| `y''`        | d²y/dx²                 |
| `y'''`       | d³y/dx³ (additional primes work for higher orders) |
| `dy/dx`     | dy/dx                   |
| `y`          | y(x) (implicit)         |
| `^` or `**`  | exponent                |
| `exp, sin, cos, log, sqrt` | standard functions |

## Running tests

```bash
python3 test_suite.py
python3 -m unittest test_web_app
```

## Design notes

- All "steps" are just the resulting line of math after each algebraic
  move — e.g. for a linear ODE:
  ```
  1. y' + (2) y = x
  2. μ(x) = exp(∫ 2 dx) = exp(2*x)
  3. d/dx [ exp(2*x) * y ] = exp(2*x) * (x)
  4. exp(2*x) * y = (2*x - 1)*exp(2*x)/4 + C1
  5. y(x) = C1*exp(-2*x) + x/2 - 1/4
  ```
- When an equation matches multiple categories (e.g. it's both separable
  and linear), the classifier prefers whichever method is structurally
  simplest, in this priority order: separable → Bernoulli → exact →
  homogeneous → linear.
- The general `dsolve` fallback runs under a hard wall-clock timeout
  (`signal.alarm`) so an unsupported/hard equation reports "no closed
  form found quickly" instead of freezing the program. It can also solve
  higher-order equations that do not match the specialized methods when
  SymPy has a supported solution method.
