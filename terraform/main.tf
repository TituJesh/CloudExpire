
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.7"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

resource "aws_dynamodb_table" "resources" {
  name         = "cloudexpire-resources"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "resource_id"

  attribute {
    name = "resource_id"
    type = "S"
  }

  tags = {
    Project     = "CloudExpire"
    Environment = "Development"
    ManagedBy   = "Terraform"
  }
}

# Lambda assumes this role.
resource "aws_iam_role" "cleanup_lambda" {
  name = "cloudexpire-cleanup-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = {
    Project = "CloudExpire"
  }
}

resource "aws_iam_role_policy" "cleanup_lambda" {
  name = "cloudexpire-cleanup-policy"
  role = aws_iam_role.cleanup_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "WriteLambdaLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.cleanup.arn}:*"
      },
      {
        Sid    = "ReadAndUpdateResourceRegistry"
        Effect = "Allow"
        Action = [
          "dynamodb:Scan",
          "dynamodb:PutItem"
        ]
        Resource = aws_dynamodb_table.resources.arn
      },
      {
        Sid      = "DescribeInstances"
        Effect   = "Allow"
        Action   = "ec2:DescribeInstances"
        Resource = "*"
      },
      {
        Sid      = "TerminateOnlyTaggedCloudExpireInstances"
        Effect   = "Allow"
        Action   = "ec2:TerminateInstances"
        Resource = "*"
        Condition = {
          StringEquals = {
            "ec2:ResourceTag/Project"   = "CloudExpire"
            "ec2:ResourceTag/ManagedBy" = "CloudExpire"
          }
        }
      }
    ]
  })
}

resource "aws_cloudwatch_log_group" "cleanup" {
  name              = "/aws/lambda/cloudexpire-cleanup"
  retention_in_days = 14

  tags = {
    Project = "CloudExpire"
  }
}

# The package directory must contain cleanup_handler.py and the app code.
data "archive_file" "cleanup_lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/package"
  output_path = "${path.module}/cloudexpire-cleanup.zip"
}

resource "aws_lambda_function" "cleanup" {
  function_name = "cloudexpire-cleanup"
  role          = aws_iam_role.cleanup_lambda.arn
  handler       = "cleanup_handler.handler"
  runtime       = "python3.12"
  architectures = ["x86_64"]

  filename         = data.archive_file.cleanup_lambda.output_path
  source_code_hash = data.archive_file.cleanup_lambda.output_base64sha256
  timeout          = 60
  memory_size      = 256

  environment {
    variables = {
      CLOUDEXPIRE_STORAGE               = "dynamodb"
      DYNAMODB_TABLE_NAME               = aws_dynamodb_table.resources.name
      CLOUDEXPIRE_ALLOW_EC2_TERMINATION = "false"
    }
  }

  depends_on = [
    aws_iam_role_policy.cleanup_lambda,
    aws_cloudwatch_log_group.cleanup
  ]

  tags = {
    Project = "CloudExpire"
  }
}

resource "aws_cloudwatch_event_rule" "cleanup_schedule" {
  name                = "cloudexpire-cleanup-every-five-minutes"
  description         = "Trigger CloudExpire expiry checks every five minutes"
  schedule_expression = "rate(5 minutes)"

  tags = {
    Project = "CloudExpire"
  }
}

resource "aws_cloudwatch_event_target" "cleanup_lambda" {
  rule      = aws_cloudwatch_event_rule.cleanup_schedule.name
  target_id = "CloudExpireCleanupLambda"
  arn       = aws_lambda_function.cleanup.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cleanup.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.cleanup_schedule.arn
}
