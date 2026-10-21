"""Tests for the local web interface."""

import json
import threading
import unittest
from http.server import HTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from web_app import ODESolveHandler, _validate_equation, solve_equation


class WebAppTests(unittest.TestCase):
    def test_caret_power_equation_returns_solution(self):
        result = solve_equation("y' + y/x = x*y ^ 2")
        self.assertEqual(result["ode_type"], "bernoulli")
        self.assertIn("Eq(", result["solution"])
        self.assertTrue(result["steps"])

    def test_rejects_names_outside_supported_math_syntax(self):
        with self.assertRaisesRegex(ValueError, "not a supported name"):
            _validate_equation("__import__('os').system('echo unsafe')")

    def test_http_solve_endpoint(self):
        server = HTTPServer(("127.0.0.1", 0), ODESolveHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/solve"
            request = Request(
                url,
                data=json.dumps({"equation": "y' + y = x"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=5) as response:
                payload = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertEqual(payload["ode_type"], "linear_first_order")

            invalid_request = Request(
                url,
                data=json.dumps({"equation": "unknown(y)"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(HTTPError) as error:
                urlopen(invalid_request, timeout=5)
            self.assertEqual(error.exception.code, 400)
            error.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
