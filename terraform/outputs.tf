output "input_bucket_name" {
  description = "入力用 S3 バケット名"
  value       = aws_s3_bucket.input.id
}

output "dynamodb_table_name" {
  description = "DynamoDB テーブル名"
  value       = aws_dynamodb_table.stats.name
}

output "lambda_function_name" {
  description = "Lambda 関数名"
  value       = aws_lambda_function.parser.function_name
}

output "lambda_function_arn" {
  description = "Lambda 関数 ARN"
  value       = aws_lambda_function.parser.arn
}

output "lambda_role_arn" {
  description = "Lambda 実行ロール ARN"
  value       = aws_iam_role.lambda_exec.arn
}

output "cloudwatch_log_group" {
  description = "CloudWatch ログクループ"
  value       = aws_cloudwatch_log_group.lambda.name
}
