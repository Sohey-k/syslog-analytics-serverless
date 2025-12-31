# ========================================
# AWS アカウント情報を自動取得
# ========================================
data "aws_caller_identity" "current" {}

# S3 バケット（入力用）
resource "aws_s3_bucket" "input" {
  bucket = var.input_bucket_name != "" ? var.input_bucket_name : "syslog-input-${data.aws_caller_identity.current.account_id}"
}

# バージョニング無効
resource "aws_s3_bucket_versioning" "input" {
  bucket = aws_s3_bucket.input.id

  versioning_configuration {
    status = "Disabled"
  }
}

# 暗号化（SSE-S3）
resource "aws_s3_bucket_server_side_encryption_configuration" "input" {
  bucket = aws_s3_bucket.input.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# パブリックアクセス ブロック
resource "aws_s3_bucket_public_access_block" "input" {
  bucket = aws_s3_bucket.input.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ライフサイクルルール（30日後削除）
resource "aws_s3_bucket_lifecycle_configuration" "input" {
  bucket = aws_s3_bucket.input.id

  rule {
    id     = "delete-old-logs"
    status = "Enabled"

    filter {
      prefix = "raw/"
    }

    expiration {
      days = 30
    }
  }
}

# S3 イベント通知（Lambda トリガー）
resource "aws_s3_bucket_notification" "input" {
  bucket     = aws_s3_bucket.input.id
  depends_on = [aws_lambda_permission.allow_s3]

  lambda_function {
    lambda_function_arn = aws_lambda_function.parser.arn
    events              = ["s3:ObjectCreated:Put"]
    filter_prefix       = "raw/"
    filter_suffix       = ".zip"
  }
}

# 出力用 S3 バケット（Phase 3）
resource "aws_s3_bucket" "output" {
  bucket = "syslog-output-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_versioning" "output" {
  bucket = aws_s3_bucket.output.id

  versioning_configuration {
    status = "Disabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "output" {
  bucket = aws_s3_bucket.output.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# 静的ホスティング設定
resource "aws_s3_bucket_website_configuration" "output" {
  bucket = aws_s3_bucket.output.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "error.html"
  }
}

# パブリックアクセス設定（部分的に公開）
resource "aws_s3_bucket_public_access_block" "output" {
  bucket = aws_s3_bucket.output.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

# バケットポリシー（index.html と data/*.json を公開）
resource "aws_s3_bucket_policy" "output" {
  bucket = aws_s3_bucket.output.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource = [
          "${aws_s3_bucket.output.arn}/index.html",
          "${aws_s3_bucket.output.arn}/data/*.json"
        ]
      }
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.output]
}
