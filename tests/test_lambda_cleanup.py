
import importlib.util
from pathlib import Path


def test_lambda_handler_returns_cleanup_result(monkeypatch):
    handler_path = (
        Path(__file__).resolve().parents[1]
        / "lambda"
        / "src"
        / "cleanup_handler.py"
    )

    spec = importlib.util.spec_from_file_location(
        "cleanup_handler",
        handler_path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    expected = {"terminated": 0, "skipped": True}

    monkeypatch.setattr(
        module,
        "cleanup_expired_resources",
        lambda: expected,
    )

    response = module.handler({}, None)

    assert response == {
        "statusCode": 200,
        "body": expected,
    }
