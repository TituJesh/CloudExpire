
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
      CLOUDEXPIRE_ALLOW_EC2_TERMINATION = "true"
    }
  }

  depends_on = [
    aws_iam_role_policy.cleanup_lambda,
    aws_cloudwatch_log_group.cleanup
  ]

  tags = {
    Project = "CloudExpire"
  }
  lifecycle {
    # Keep the existing cleanup code unchanged while adding the API.
    # Cleanup code deployments must be handled deliberately.
    ignore_changes = [
      filename,
      source_code_hash
    ]
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


# Current AWS account, used to scope IAM resources.
data "aws_caller_identity" "current" {}

# Dedicated execution role for the FastAPI Lambda.
resource "aws_iam_role" "api_lambda" {
  name = "cloudexpire-api-lambda-role"

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

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/cloudexpire-api"
  retention_in_days = 14

  tags = {
    Project = "CloudExpire"
  }
}

resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/cloudexpire-api"
  retention_in_days = 14

  tags = {
    Project = "CloudExpire"
  }
}

resource "aws_iam_role_policy" "api_lambda" {
  name = "cloudexpire-api-policy"
  role = aws_iam_role.api_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "WriteApiLambdaLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.api.arn}:*"
      },
      {
        Sid    = "AccessCloudExpireResourceRegistry"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:Scan",
          "dynamodb:PutItem"
        ]
        Resource = aws_dynamodb_table.resources.arn
      },
      {
        Sid      = "ReadApiTokenFromParameterStore"
        Effect   = "Allow"
        Action   = ["ssm:GetParameter"]
        Resource = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.api_token_parameter_name}"
      },
      {
        Sid    = "LaunchOnlyApprovedCloudExpireConfiguration"
        Effect = "Allow"
        Action = ["ec2:RunInstances"]
        Resource = [
          "arn:aws:ec2:${var.aws_region}::image/${var.ec2_ami_id}",
          "arn:aws:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:subnet/${var.ec2_subnet_id}",
          "arn:aws:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:security-group/${var.ec2_security_group_id}",
          "arn:aws:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:network-interface/*",
          "arn:aws:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:volume/*"
        ]
      },
      {
        Sid      = "LaunchTaggedCloudExpireInstances"
        Effect   = "Allow"
        Action   = ["ec2:RunInstances"]
        Resource = "arn:aws:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:instance/*"

        Condition = {
          StringEquals = {
            "ec2:InstanceType"         = ["t3.micro", "t3.small"]
            "aws:RequestTag/Project"   = "CloudExpire"
            "aws:RequestTag/ManagedBy" = "CloudExpire"
          }
          StringLike = {
            "aws:RequestTag/ResourceId" = "ce-*"
            "aws:RequestTag/ExpiresAt"  = "*"
          }
        }
      },
      {
        Sid      = "TagInstancesOnlyDuringApprovedLaunch"
        Effect   = "Allow"
        Action   = ["ec2:CreateTags"]
        Resource = "arn:aws:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:instance/*"

        Condition = {
          StringEquals = {
            "ec2:CreateAction"         = "RunInstances"
            "aws:RequestTag/Project"   = "CloudExpire"
            "aws:RequestTag/ManagedBy" = "CloudExpire"
          }
          StringLike = {
            "aws:RequestTag/ResourceId" = "ce-*"
            "aws:RequestTag/ExpiresAt"  = "*"
          }
        }
      }
    ]
  })
}

resource "aws_lambda_function" "api" {
  function_name = "cloudexpire-api"
  role          = aws_iam_role.api_lambda.arn
  handler       = "api_handler.handler"
  runtime       = "python3.12"
  architectures = ["x86_64"]

  filename         = "${path.module}/cloudexpire-api.zip"
  source_code_hash = filebase64sha256("${path.module}/cloudexpire-api.zip")

  timeout     = 30
  memory_size = 512

  environment {
    variables = {
      CLOUDEXPIRE_STORAGE             = "dynamodb"
      DYNAMODB_TABLE_NAME             = aws_dynamodb_table.resources.name
      CLOUDEXPIRE_API_TOKEN_PARAMETER = var.api_token_parameter_name
      CLOUDEXPIRE_PROVISION_EC2       = "true"
      CLOUDEXPIRE_ALLOW_EC2_LAUNCH    = "true"
      CLOUDEXPIRE_AMI_ID              = var.ec2_ami_id
      CLOUDEXPIRE_SUBNET_ID           = var.ec2_subnet_id
      CLOUDEXPIRE_SECURITY_GROUP_ID   = var.ec2_security_group_id
    }
  }

  depends_on = [
    aws_iam_role_policy.api_lambda,
    aws_cloudwatch_log_group.api
  ]

  tags = {
    Project = "CloudExpire"
  }
}

resource "aws_apigatewayv2_api" "api" {
  name          = "cloudexpire-api"
  protocol_type = "HTTP"
  description   = "Authenticated CloudExpire resource lifecycle API"

  tags = {
    Project = "CloudExpire"
  }
}

resource "aws_apigatewayv2_integration" "api_lambda" {
  api_id                 = aws_apigatewayv2_api.api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.api_lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId        = "$context.requestId"
      requestTime      = "$context.requestTime"
      routeKey         = "$context.routeKey"
      status           = "$context.status"
      responseLength   = "$context.responseLength"
      integrationError = "$context.integrationErrorMessage"
    })
  }

  tags = {
    Project = "CloudExpire"
  }
}

resource "aws_lambda_permission" "allow_api_gateway" {
  statement_id  = "AllowCloudExpireApiGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}

output "api_base_url" {
  description = "Base URL for the CloudExpire HTTP API"
  value       = aws_apigatewayv2_api.api.api_endpoint
}

output "api_token_parameter_name" {
  description = "SSM parameter name holding the API bearer token"
  value       = var.api_token_parameter_name
}
