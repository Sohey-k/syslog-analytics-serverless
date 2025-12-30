#!/bin/bash

#############################################################################
# Syslog Generator ラッパースクリプト
# 
# 用途: generator/generate.py を簡単に実行
# 
# 使用方法:
#   bash scripts/generate_sample.sh [行数] [出力先]
#   
# 例:
#   bash scripts/generate_sample.sh              # デフォルト: 2100 行、sample_data 出力
#   bash scripts/generate_sample.sh 5000         # カスタム: 5000 行
#   bash scripts/generate_sample.sh 5000 ./data  # カスタム: 5000 行、./data に出力
#############################################################################

set -e

# デフォルト値
ROWS=${1:-2100}
OUTPUT_DIR=${2:-sample_data}
GENERATOR_DIR="generator"

# 色付き出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Syslog Generator ラッパー ===${NC}"
echo "行数: $ROWS"
echo "出力先: $OUTPUT_DIR"
echo ""

# プロジェクトルートにいるか確認
if [ ! -d "$GENERATOR_DIR" ]; then
    echo -e "${RED}ERROR: $GENERATOR_DIR ディレクトリが見つかりません${NC}"
    echo "プロジェクトルートから実行してください"
    exit 1
fi

# 出力ディレクトリを作成
mkdir -p "$OUTPUT_DIR"

# Generator を実行
echo -e "${YELLOW}実行: python ${GENERATOR_DIR}/generate.py -r ${ROWS} -o ${OUTPUT_DIR}${NC}"
python "${GENERATOR_DIR}/generate.py" -r "$ROWS" -o "$OUTPUT_DIR"

# 結果確認
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ 生成完了！${NC}"
    echo ""
    echo "生成ファイル:"
    ls -lh "$OUTPUT_DIR"/*.zip 2>/dev/null || echo "  (ファイルなし)"
    echo ""
    echo "S3 にアップロードするには:"
    echo "  bash scripts/upload_to_s3.sh $OUTPUT_DIR"
else
    echo -e "${RED}ERROR: 生成に失敗しました${NC}"
    exit 1
fi
