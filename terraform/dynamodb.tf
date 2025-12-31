# DynamoDB テーブル
resource "aws_dynamodb_table" "stats" {
  name         = var.dynamodb_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "log_date"
  range_key    = "hour"

  attribute {
    name = "log_date"
    type = "S"
  }

  attribute {
    name = "hour"
    type = "S"
  }

  tags = {
    Name = var.dynamodb_table_name
  }
}

# 注記:
# - Point-in-time Recovery: デフォルト無効（コスト削減）
# - Encryption: デフォルト有効（AWS Managed Key）
# - TTL: 必要に応じて後から追加（future enhancement）
