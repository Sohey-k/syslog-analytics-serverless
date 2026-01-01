#!/bin/bash

#############################################################################
# S3 アップロードスクリプト
#
# 用途: 生成されたログファイル (ZIP) を S3 にアップロード
#
# 使用方法:
#   bash scripts/upload_to_s3.sh [ディレクトリ] [S3バケット] [日付]
#
# 例:
#   bash scripts/upload_to_s3.sh                    # デフォルト: sample_data → syslog-input-bucket、日付は本日
#   bash scripts/upload_to_s3.sh ./data             # カスタムディレクトリ
#   bash scripts/upload_to_s3.sh ./data my-bucket   # カスタムバケット
#   bash scripts/upload_to_s3.sh ./data my-bucket 2025-04-28  # カスタム日付
#############################################################################

set -e

# デフォルト値
DATA_DIR=${1:-sample_data}
# Terraform output から自動取得（フォールバック: 引数指定可能）
DEFAULT_BUCKET=$(cd terraform 2>/dev/null && terraform output -raw s3_input_bucket 2>/dev/null || echo "")
BUCKET=${2:-${DEFAULT_BUCKET}}
LOG_DATE=${3:-$(date +%Y-%m-%d)}

# 色付き出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== S3 アップロードスクリプト ===${NC}"
echo "データディレクトリ: $DATA_DIR"
echo "S3 バケット: $BUCKET"
echo "ログ日付: $LOG_DATE"
echo ""

# チェック
if [ ! -d "$DATA_DIR" ]; then
    echo -e "${RED}ERROR: ディレクトリ $DATA_DIR が見つかりません${NC}"
    exit 1
fi

# ZIP ファイルが存在するか確認
ZIP_COUNT=$(ls -1 "$DATA_DIR"/*.zip 2>/dev/null | wc -l)
if [ "$ZIP_COUNT" -eq 0 ]; then
    echo -e "${RED}ERROR: ZIP ファイルが見つかりません (${DATA_DIR}/*.zip)${NC}"
    exit 1
fi

echo -e "${YELLOW}対象ファイル数: $ZIP_COUNT${NC}"
echo ""

# AWS CLI が利用可能か確認
if ! command -v aws &> /dev/null; then
    echo -e "${RED}ERROR: aws コマンドが見つかりません${NC}"
    echo "AWS CLI をインストール: https://aws.amazon.com/cli/"
    exit 1
fi

# S3 にアップロード
echo -e "${YELLOW}アップロード開始...${NC}"
aws s3 cp "$DATA_DIR"/ "s3://${BUCKET}/raw/${LOG_DATE}/" \
    --recursive \
    --include "*.zip" \
    --no-progress

echo ""
echo -e "${GREEN}✓ アップロード完了！${NC}"
echo ""
echo "アップロード先:"
echo "  s3://${BUCKET}/raw/${LOG_DATE}/"
echo ""
echo "確認コマンド:"
echo "  aws s3 ls s3://${BUCKET}/raw/${LOG_DATE}/"
echo ""
echo "次のステップ:"
echo "  1. CloudWatch Logs で Lambda の実行を監視"
echo "  2. DynamoDB で集計結果を確認"
