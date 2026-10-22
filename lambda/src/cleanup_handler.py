
import json
import logging

from app.services.cleanup_service import cleanup_expired_resources

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """AWS Lambda entry point for scheduled CloudExpire cleanup."""
    try:
        result = cleanup_expired_resources()

        # Emit one structured JSON record for every successful run.
        logger.info(
            json.dumps(
                {
                    "event": "cloudexpire_cleanup_completed",
                    "request_id": getattr(context, "aws_request_id", None),
                    "result": result,
                },
                sort_keys=True,
            )
        )

        return {
            "statusCode": 200,
            "body": result,
        }

    except Exception:
        logger.exception("CloudExpire cleanup execution failed")
        raise
