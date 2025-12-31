terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # 将来的にリモート state を使う場合（現在はローカル）
  # backend "s3" {
  #   bucket         = "terraform-state-bucket"
  #   key            = "syslog-analytics/terraform.tfstate"
  #   region         = "ap-northeast-1"
  #   encrypt        = true
  #   dynamodb_table = "terraform-locks"
  # }
}

provider "aws" {
  region = var.aws_region
}