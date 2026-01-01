# ========================================
# CloudFront Distribution（HTTPS 配信）
# ========================================

# CloudFront OAC（Origin Access Control）
resource "aws_cloudfront_origin_access_control" "output" {
  name                              = "syslog-output-oac"
  description                       = "OAC for syslog output bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# CloudFront Distribution
resource "aws_cloudfront_distribution" "output" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "Syslog Analytics Dashboard Distribution"
  default_root_object = "index.html"
  price_class         = "PriceClass_200" # 米国、欧州、アジア（日本含む）

  # S3 Origin
  origin {
    domain_name              = aws_s3_bucket.output.bucket_regional_domain_name
    origin_id                = "S3-${aws_s3_bucket.output.id}"
    origin_access_control_id = aws_cloudfront_origin_access_control.output.id
  }

  # デフォルトキャッシュ動作
  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-${aws_s3_bucket.output.id}"
    viewer_protocol_policy = "redirect-to-https" # HTTP を HTTPS にリダイレクト

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 3600  # 1時間キャッシュ
    max_ttl     = 86400 # 最大24時間
    compress    = true  # Gzip圧縮有効
  }

  # data/*.json のキャッシュ動作（短時間キャッシュ）
  ordered_cache_behavior {
    path_pattern           = "data/*.json"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-${aws_s3_bucket.output.id}"
    viewer_protocol_policy = "redirect-to-https"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 300  # 5分キャッシュ（データ更新反映のため短め）
    max_ttl     = 600  # 最大10分
    compress    = true
  }

  # カスタムエラーレスポンス（404 → index.html）
  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  # 地理的制限（なし）
  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  # SSL証明書（CloudFront デフォルト証明書）
  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = {
    Name = "syslog-analytics-dashboard"
  }
}
