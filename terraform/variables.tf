
variable "aws_region" {
  description = "AWS region for CloudExpire resources"
  type        = string
  default     = "ap-south-1"
}

variable "api_token_parameter_name" {
  description = "Name of the SSM SecureString containing the API bearer token"
  type        = string
  default     = "/cloudexpire/prod/api-token"
}

variable "ec2_ami_id" {
  description = "Approved AMI for CloudExpire instances"
  type        = string
  default     = "ami-088fb12f8e8397f06"
}

variable "ec2_subnet_id" {
  description = "Subnet in which CloudExpire instances are launched"
  type        = string
  default     = "subnet-0cfda13a746570e0c"
}

variable "ec2_security_group_id" {
  description = "Dedicated security group for CloudExpire instances"
  type        = string
  default     = "sg-0105d936bff853379"
}
