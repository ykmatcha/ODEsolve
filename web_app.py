"""Local web interface for the ODE solver."""

import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer

import sympy as sp

from classifier import classify
from solver import solve


MAX_EQUATION_LENGTH = 300
TOKEN_PATTERN = re.compile(
    r"dy/dx|y'+|[A-Za-z_][A-Za-z0-9_]*|(?:\d+(?:\.\d*)?|\.\d+)|[()+\-*/^=,]"
)
ALLOWED_NAMES = {"x", "y", "sin", "cos", "exp", "log", "sqrt"}


def _validate_equation(equation):
    if not isinstance(equation, str):
        raise ValueError("Enter the equation as text.")

    equation = equation.strip()
    if not equation:
        raise ValueError("Enter an equation to solve.")
    if len(equation) > MAX_EQUATION_LENGTH:
        raise ValueError(f"Keep the equation under {MAX_EQUATION_LENGTH} characters.")

    tokens = []
    position = 0
    while position < len(equation):
        if equation[position].isspace():
            position += 1
            continue
        match = TOKEN_PATTERN.match(equation, position)
        if match is None:
            raise ValueError("Use only standard ODE notation, numbers, and supported functions.")
        token = match.group()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token) and token not in ALLOWED_NAMES:
            raise ValueError(f"'{token}' is not a supported name.")
        tokens.append(token)
        position = match.end()

    return equation


def solve_equation(equation):
    equation = _validate_equation(equation)
    classification, expression = classify(equation)
    result = solve(classification, expression)
    return {
        "equation": equation,
        "ode_type": result.ode_type,
        "steps": [str(step) for step in result.steps],
        "solution": (
            str(result.general_solution) if result.general_solution is not None else None
        ),
    }


HTML_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ODEsolve</title>
  <style>
    :root { color-scheme: light; font: 16px/1.5 system-ui, sans-serif; }
    body { background: #f3f5f8; color: #182230; margin: 0; }
    main { box-sizing: border-box; margin: 8vh auto; max-width: 760px; padding: 0 24px; }
    h1 { font-size: 2rem; margin-bottom: 4px; }
    .muted { color: #536273; }
    form, .result { background: white; border: 1px solid #dce2e9; border-radius: 12px; padding: 22px; }
    label { display: block; font-weight: 650; margin-bottom: 8px; }
    textarea { box-sizing: border-box; font: 1rem/1.5 ui-monospace, monospace; min-height: 100px; padding: 12px; resize: vertical; width: 100%; }
    button { background: #155eef; border: 0; border-radius: 7px; color: white; cursor: pointer; font: inherit; font-weight: 650; margin-top: 12px; padding: 10px 16px; }
    button:disabled { cursor: wait; opacity: .65; }
    .result { margin-top: 18px; }
    .result h2 { font-size: 1.1rem; margin: 14px 0 5px; }
    pre { background: #f6f8fa; border-radius: 6px; overflow-wrap: anywhere; padding: 12px; white-space: pre-wrap; }
    [hidden] { display: none; }
    #error { color: #b42318; }
  </style>
</head>
<body>
  <main>
    <h1>ODEsolve</h1>
    <p class="muted">Enter an ordinary differential equation. Use y', y'', y''' for derivatives and ^ or ** for powers.</p>
    <form id="solver-form">
      <label for="equation">Equation</label>
      <textarea id="equation" name="equation" required spellcheck="false">y' + y = x</textarea>
      <div class="muted">Example: <code>y' + y/x = x*y ^ 2</code></div>
      <button id="solve-button" type="submit">Solve</button>
    </form>
    <p id="error" role="alert" hidden></p>
    <section id="result" class="result" aria-live="polite" hidden>
      <div id="type" class="muted"></div>
      <h2>General solution</h2>
      <pre id="solution"></pre>
      <h2>Steps</h2>
      <pre id="steps"></pre>
    </section>
  </main>
  <script>
    const form = document.querySelector("#solver-form");
    const button = document.querySelector("#solve-button");
    const error = document.querySelector("#error");
    const result = document.querySelector("#result");

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      button.disabled = true;
      button.textContent = "Solving...";
      error.hidden = true;
      result.hidden = true;
      try {
        const response = await fetch("/solve", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ equation: document.querySelector("#equation").value })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Could not solve this equation.");
        document.querySelector("#type").textContent = `Detected type: ${data.ode_type}`;
        document.querySelector("#solution").textContent = data.solution || "No closed-form solution found.";
        document.querySelector("#steps").textContent = data.steps.join("\\n") || "No solution steps available.";
        result.hidden = false;
      } catch (exception) {
        error.textContent = exception.message;
        error.hidden = false;
      } finally {
        button.disabled = false;
        button.textContent = "Solve";
      }
    });
  </script>
</body>
</html>
"""


class ODESolveHandler(BaseHTTPRequestHandler):
    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path != "/":
            self.send_error(404)
            return
        body = HTML_PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/solve":
            self._send_json(404, {"error": "Not found."})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"error": "Invalid request length."})
            return
        if content_length <= 0 or content_length > 4096:
            self._send_json(413, {"error": "Request body must be between 1 and 4096 bytes."})
            return

        try:
            request = json.loads(self.rfile.read(content_length))
            payload = solve_equation(request.get("equation") if isinstance(request, dict) else None)
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, {"error": "Send a valid JSON object containing an equation."})
            return
        except ValueError as error:
            self._send_json(400, {"error": str(error)})
            return
        except (sp.SympifyError, TypeError) as error:
            self.log_error("Unable to parse submitted equation: %s", error)
            self._send_json(400, {"error": "Could not parse that equation. Check its notation."})
            return
        except Exception as error:
            self.log_error("Solver failed: %s", error)
            self._send_json(500, {"error": "The solver encountered an error. Check the server log."})
            return

        self._send_json(200, payload)


def main():
    parser = argparse.ArgumentParser(description="Run the ODEsolve local web app.")
    parser.add_argument("--port", type=int, default=3000, help="local port to listen on (default: 3000)")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")

    server = HTTPServer(("127.0.0.1", args.port), ODESolveHandler)
    print(f"ODEsolve is running at http://127.0.0.1:{args.port} (local access only). Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping ODEsolve.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
