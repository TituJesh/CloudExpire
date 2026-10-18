
output "dynamodb_table_name" {
  description = "Name of the CloudExpire resource registry"
  value       = aws_dynamodb_table.resources.name
}

output "dynamodb_table_arn" {
  description = "ARN of the CloudExpire resource registry"
  value       = aws_dynamodb_table.resources.arn
}
