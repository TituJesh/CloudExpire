
from app.services.cleanup_service import cleanup_expired_resources


def handler(event, context):
    """AWS Lambda entry point for scheduled CloudExpire cleanup."""
    result = cleanup_expired_resources()

    return {
        "statusCode": 200,
        "body": result,
    }
