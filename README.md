# CloudExpire

> **Temporary AWS Resource Lifecycle Manager**  
> CloudExpire is an automated lifecycle management system designed to track temporary AWS cloud resources and enforce scheduled cleanup upon expiration. Built with FastAPI, AWS Lambda, DynamoDB, EventBridge, Terraform, and GitHub Actions, it demonstrates cloud automation, Infrastructure as Code (IaC), and cost-conscious engineering safeguards.

[![CI](https://github.com/TituJesh/CloudExpire/actions/workflows/ci.yml/badge.svg)](https://github.com/TituJesh/CloudExpire/actions)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Terraform](https://img.shields.io/badge/IaC-Terraform-7B42BC.svg)](https://www.terraform.io/)

---

## Architecture & Workflows

### 1. Application Flow (Provisioning & Registry)
```text
FastAPI Client ──▶ DynamoDB (Resource Table) ──▶ Optional EC2 Provisioning (Disabled by default)
```
- Accepts resource registrations with configurable TTL / expiration windows (1 to 24 hours).
- Records resource metadata, timestamps, and state in Amazon DynamoDB.

### 2. Automated Cleanup Flow
```text
Amazon EventBridge (cron: 5m) ──▶ AWS Lambda ──▶ DynamoDB Scan ──▶ EC2 Termination (Disabled by default)
```
- EventBridge triggers the Lambda cleanup handler every 5 minutes.
- Evaluates expired records against DynamoDB and inspects EC2 instance states.
- Applies strict ownership verification tags before issuing any termination requests.

---

## Technology Stack

| Layer | Technology |
|---|---|
| **Runtime & Language** | Python 3.12+ |
| **API Framework** | FastAPI, Uvicorn |
| **AWS SDK** | Boto3 |
| **Compute & Serverless** | AWS Lambda, optional Amazon EC2 |
| **Database** | Amazon DynamoDB (On-Demand capacity) |
| **Scheduling & Logs** | Amazon EventBridge, Amazon CloudWatch Logs (14-day retention) |
| **Infrastructure as Code** | Terraform (`~> 5.0` AWS Provider, `~> 2.7` Archive Provider) |
| **Testing & Quality** | pytest (14 passing unit & integration tests) |
| **CI/CD** | GitHub Actions |

---

## Current Features

- **RESTful Endpoints**: Health probe (`/health`) and resource registry management (`/resources`).
- **Configurable Expiry**: Enforces lifetime constraints between 1 and 24 hours.
- **Pluggable Persistence**: DynamoDB-backed repository alongside in-memory options for local testing.
- **Scheduled Serverless Janitor**: AWS Lambda function invoked automatically via EventBridge rule.
- **Tag-Based Safeguards**: Strict 3-point tag validation (`Project: CloudExpire`, `ManagedBy: CloudExpire`, and matching resource ID) prevents accidental termination of foreign resources.
- **Robust State Tracking**: Distinguishes between `pending`, `running`, `stopping`, `shutting-down`, and `terminated` EC2 states.
- **Automated CI**: Full test suite verified on each commit via GitHub Actions.

---

## Safety & Cost Controls

1. **Disabled Defaults**: EC2 provisioning (`CLOUDEXPIRE_ALLOW_EC2_PROVISIONING`) and termination (`CLOUDEXPIRE_ALLOW_EC2_TERMINATION`) are turned **off** by default.
2. **Dry-Run Inspection**: Lambda performs reads and state audits without issuing mutation commands when termination is disabled.
3. **Mandatory Ownership Tags**: Cleanup checks tag requirements before any termination request can be dispatched.
4. **On-Demand Capacity**: DynamoDB operates in on-demand billing mode (`PAY_PER_REQUEST`) to eliminate idle costs.
5. **Log Expiration**: CloudWatch log retention is constrained to 14 days to minimize logging storage fees.
6. **Zero Hardcoded Secrets**: Uses environment variables and AWS IAM roles for secure credential delegation.

> **Verification Status**: AWS infrastructure deployment and dry-run Lambda execution have been verified. Live EC2 provisioning and end-to-end instance termination are disabled by default for cost protection.

---

## Local Setup

### 1. Clone the Repository
```bash
git clone https://github.com/TituJesh/CloudExpire.git
cd CloudExpire
```

### 2. Set Up Virtual Environment
**Windows PowerShell**:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS**:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
python -m pip install -r requirements.txt
```

### 4. Run the API Locally
```bash
python -m uvicorn app.main:app --reload
```
- **Interactive OpenAPI Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

### 5. Run the Test Suite
```bash
python -m pytest -q --import-mode=importlib
```

---

## AWS Infrastructure (Terraform)

Infrastructure definitions reside in [`terraform/`](terraform/):
- **DynamoDB Table**: Stores resource lifecycle status, timestamps, and AWS resource IDs.
- **IAM Execution Role & Policy**: Grants least-privilege permissions (`logs:*`, `dynamodb:*`, and conditional `ec2:TerminateInstances` restricted by resource tags).
- **Lambda Function**: Container-built Python 3.12 deployment package running `cleanup_handler.handler`.
- **EventBridge Schedule**: Rate rule triggering cleanup execution every 5 minutes.
- **CloudWatch Log Group**: Structured logging with 14-day retention.

To review or apply infrastructure:
```bash
cd terraform
terraform init
terraform plan
terraform apply
```
*(Requires configured AWS CLI credentials with appropriate administrative IAM permissions.)*

---

## Project Competencies

CloudExpire showcases foundational cloud engineering principles:
- Cloud resource lifecycle orchestration & serverless architectures.
- Python backend automation using Boto3 and FastAPI.
- Declarative Infrastructure as Code (IaC) with Terraform.
- Least-privilege IAM scoping and defense-in-depth safety checks.
- Test-driven validation and automated GitHub Actions workflows.

---

## Repository

- **GitHub**: [https://github.com/TituJesh/CloudExpire](https://github.com/TituJesh/CloudExpire)
