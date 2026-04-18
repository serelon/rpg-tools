# Tests

Run all tests:

    python tests/run_tests.py

Run a specific module:

    python -m unittest tests.test_namegen_discovery -v

Run a specific test:

    python -m unittest tests.test_namegen_discovery.TestDiscovery.test_loads_single_file -v

No external dependencies. Uses stdlib `unittest`.
