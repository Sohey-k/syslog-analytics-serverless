# CloudWatch Logs グループ
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.project_name}-parser-function"
  retention_in_days = 7

  tags = {
    Name = "${var.project_name}-parser-logs"
  }
}

# 今後の拡張用：アラーム設定（Phase 2）
# resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
#   alarm_name          = "${var.project_name}-lambda-errors"
#   comparison_operator = "GreaterThanOrEqualToThreshold"
#   evaluation_periods  = 1
#   metric_name         = "Errors"
#   namespace           = "AWS/Lambda"
#   period              = 300
#   statistic           = "Sum"
#   threshold           = 1
#   alarm_description   = "Lambda 実行エラーが発生しました"
#   treat_missing_data  = "notBreaching"
#
#   dimensions = {
#     FunctionName = aws_lambda_function.parser.function_name
#   }
#
#   alarm_actions = [] # SNS Topic ARN を指定
# }
