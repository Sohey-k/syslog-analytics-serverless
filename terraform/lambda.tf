# データソース: Lambda 関数のソースコード
data "archive_file" "lambda" {
  type        = "zip"
  source_file = "${path.module}/../lambda/syslog_parser/lambda_function.py"
  output_path = "${path.module}/lambda_function.zip"
}

# Lambda 関数
resource "aws_lambda_function" "parser" {
  filename      = data.archive_file.lambda.output_path
  function_name = "${var.project_name}-parser-function"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.11"

  memory_size = var.lambda_memory
  timeout     = var.lambda_timeout

  environment {
    variables = {
      DYNAMODB_TABLE = aws_dynamodb_table.stats.name
      OUTPUT_BUCKET  = aws_s3_bucket.output.id
    }
  }

  source_code_hash = data.archive_file.lambda.output_base64sha256

  depends_on = [
    aws_iam_role_policy.lambda_policy,
    aws_cloudwatch_log_group.lambda
  ]
}

# S3 から Lambda を起動する権限
resource "aws_lambda_permission" "allow_s3" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.parser.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.input.arn
}
