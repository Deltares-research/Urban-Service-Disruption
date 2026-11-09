"""Test script for python template."""
from datetime import datetime
import unittest
from {{cookiecutter.python_import_name}} import {{cookiecutter.python_import_name}}


class MyTest(unittest.TestCase):
    def tearDown(self) -> None:
        import logging
        from importlib import reload

        logging.shutdown()
        reload(logging)
        return super().tearDown()

    def test__testable_function__is_correct(self) -> None:
        # Arrange
        current_time = datetime(1970, 1, 1, 13, 00)

        # Act
        result = {{cookiecutter.python_import_name}}.testable_function(current_time)

        # Assert
        expected_result = datetime(1970, 1, 1, 14, 00)
        self.assertEqual(expected_result, result)

    def test_start_app_info(self) -> None:
        try:
            {{cookiecutter.python_import_name}}.start_app(loglevel="INFO", colors=True)
        except Exception as e:
            self.fail(f"{{cookiecutter.python_import_name}}.start_app() raised an exception: {e}")

    def test_start_app_debug(self) -> None:
        try:
            {{cookiecutter.python_import_name}}.start_app(loglevel="DEBUG", colors=False)
        except Exception as e:
            self.fail(f"{{cookiecutter.python_import_name}}.start_app() raised an exception: {e}")

    def test_start_app_wrong_logtype(self) -> None:
        with self.assertRaises(ValueError):
            {{cookiecutter.python_import_name}}.start_app(loglevel="WRONG_LOG_TYPE", colors=False)
