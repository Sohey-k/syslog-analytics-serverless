variable "aws_region" {
  description = "AWS リージョン"
  type        = string
  default     = "ap-northeast-1"
}

variable "project_name" {
  description = "プロジェクト名"
  type        = string
  default     = "syslog-analytics"
}

variable "environment" {
  description = "環境名 (dev, staging, prod)"
  type        = string
  default     = "dev"
}

# variable "aws_account_id" {
#  description = "AWS アカウント ID"
#  type        = string
#  sensitive   = true
# }

# S3 バケット設定
variable "input_bucket_name" {
  description = "入力用 S3 バケット名"
  type        = string
  default     = ""
}

variable "dynamodb_table_name" {
  description = "DynamoDB テーブル名"
  type        = string
  default     = "syslog-hourly-stats"
}

# Lambda 設定
variable "lambda_memory" {
  description = "Lambda メモリ (MB)"
  type        = number
  default     = 512
}

variable "lambda_timeout" {
  description = "Lambda タイムアウト (秒)"
  type        = number
  default     = 300
}
