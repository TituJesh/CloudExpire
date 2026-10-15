
# CloudExpire

CloudExpire is a Python-based AWS resource lifecycle manager
that tracks temporary cloud resources and automatically cleans
them up when they expire.

## Current Features

- FastAPI application
- Health-check endpoint
- Automated tests using pytest
- GitHub Actions CI workflow

## Planned Technologies

- Python and boto3
- AWS Lambda and API Gateway
- Amazon DynamoDB
- Amazon EventBridge
- Terraform
- GitHub Actions with AWS OIDC
- Amazon CloudWatch

## Local Setup

Create and activate a Python virtual environment,
then install the dependencies:

    pip install -r requirements.txt

Start the API:

    uvicorn app.main:app --reload

Run the tests:

    python -m pytest -v

API documentation: http://127.0.0.1:8000/docs
