
import importlib.util
from pathlib import Path


def test_lambda_handler_returns_cleanup_result(monkeypatch):
    handler_path = (
        Path(__file__).resolve().parents[1]
        / "lambda"
        / "package"
        / "cleanup_handler.py"
    )

    spec = importlib.util.spec_from_file_location(
        "cleanup_handler",
        handler_path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setattr(
        module,
        "cleanup_expired_resources",
        lambda: {"terminated": 0, "skipped": True},
    )

    result = module.handler({}, None)

    assert result == {
        "statusCode": 200,
        "body": {"terminated": 0, "skipped": True},
    }
