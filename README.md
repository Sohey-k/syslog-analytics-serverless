# Juniper Syslog Analytics Serverless

Juniper ネットワーク機器のシステムログを AWS 上で無料で処理・分析する Serverless アーキテクチャ。

## 🎯 プロジェクト概要

- **入力**: Syslog CSV を ZIP 圧縮したファイル
- **処理**: S3 → Lambda（Python）で CSV 解析
- **出力**: DynamoDB に時間別統計を保存
- **可視化**: S3 静的ホスティングでダッシュボード（Phase 3）

### 費用

**月額 $0** 🎉

```
- Lambda: 無料枠内（100万回/月、400,000 GB秒/月）
- S3: 無料枠内（5GB、PUT/GET含む）
- DynamoDB: オンデマンド課金（月 17,280 WCU = 無料枠内）
```

詳細は [docs/design.md](docs/design.md) の **10. コスト設計** を参照。

---

## 📋 ディレクトリ構成

```
syslog-analytics-serverless/
├── README.md                  ← このファイル
├── docs/
│   ├── requirements.md        ← 要件定義書
│   └── design.md              ← 設計書（詳細なアーキテクチャ）
│
├── generator/                 ← ログジェネレーター
│   ├── generate.py            ← CSV 生成・ZIP 圧縮
│   └── README.md              ← 使用方法
│
├── sample_data/               ← 生成ログの出力先
│   └── .gitkeep
│
├── scripts/                   ← 便利スクリプト
│   ├── generate_sample.sh     ← ジェネレーター実行ラッパー
│   └── upload_to_s3.sh        ← S3 アップロード
│
├── terraform/                 ← インフラコード
│   ├── main.tf                ← Provider & Backend
│   ├── variables.tf           ← 変数定義
│   ├── outputs.tf             ← 出力値
│   ├── s3.tf                  ← S3 バケット
│   ├── lambda.tf              ← Lambda 関数
│   ├── iam.tf                 ← IAM ロール
│   ├── dynamodb.tf            ← DynamoDB テーブル
│   └── cloudwatch.tf          ← CloudWatch Logs
│
└── lambda/                    ← Lambda 関数ソース
    └── syslog_parser/
        ├── lambda_function.py  ← メインハンドラー
        ├── requirements.txt    ← 依存パッケージ（なし）
        └── tests/              ← ユニットテスト
            └── test_parser.py
```

---

## 🚀 クイックスタート

### 1. サンプルデータ生成

```bash
bash scripts/generate_sample.sh
```

**出力**: `sample_data/00.zip` ～ `sample_data/23.zip` (24 ファイル)

詳細は [generator/README.md](generator/README.md) 参照。

### 2. AWS 環境をセットアップ

#### 前提条件

- AWS CLI インストール済み
- AWS 認証情報設定済み (`~/.aws/credentials` または環境変数)

#### Terraform でデプロイ

```bash
cd terraform

# 初期化
terraform init

# デプロイプラン確認
terraform plan

# デプロイ実行
terraform apply
```

**作成されるリソース:**
- S3 バケット（入力用）
- Lambda 関数（CSV 解析）
- DynamoDB テーブル（集計結果）
- IAM ロール（最小権限）
- CloudWatch Logs

### 3. サンプルデータを S3 アップロード

```bash
bash scripts/upload_to_s3.sh sample_data
```

**自動処理:**
1. S3 へアップロード
2. Lambda が自動起動
3. CSV を解析
4. DynamoDB に時間別統計を保存

### 4. 結果確認

```bash
# CloudWatch Logs で Lambda ログを確認
aws logs tail /aws/lambda/syslog-parser-function --follow

# DynamoDB で集計結果を確認
aws dynamodb query \
  --table-name syslog-hourly-stats \
  --key-condition-expression "log_date = :date" \
  --expression-attribute-values '{":date":{"S":"2025-04-28"}}'
```

---

## 📚 ドキュメント

| ファイル | 説明 |
|---------|------|
| [docs/requirements.md](docs/requirements.md) | 要件定義書（機能・制約） |
| [docs/design.md](docs/design.md) | 設計書（14 章構成、詳細設計） |
| [generator/README.md](generator/README.md) | ログジェネレーター使用方法 |

---

## 🧪 テスト

### ローカル単体テスト

```bash
cd lambda/syslog_parser
python -m unittest tests.test_parser -v
```

### 統合テスト（E2E）

```bash
# 1. サンプルデータ生成
bash scripts/generate_sample.sh

# 2. S3 にアップロード
bash scripts/upload_to_s3.sh sample_data

# 3. Lambda 実行確認（ログ監視）
aws logs tail /aws/lambda/syslog-parser-function --follow

# 4. 結果確認
aws dynamodb query \
  --table-name syslog-hourly-stats \
  --key-condition-expression "log_date = :date" \
  --expression-attribute-values '{":date":{"S":"2025-04-28"}}'
```

---

## 🔄 開発フロー

### Phase 1（現在）: コアパイプライン ✅ 準備中

- [x] ディレクトリ構造設計
- [ ] Generator コード実装
- [ ] Lambda 関数実装
- [ ] Terraform コード実装
- [ ] ローカルテスト
- [ ] AWS デプロイ・動作確認

### Phase 2: 運用・監視

- CloudWatch アラート
- IAM 最小権限化
- Terraform モジュール化
- GitHub Actions CI/CD

### Phase 3: 可視化

- ダッシュボード（HTML + Chart.js）
- S3 静的ホスティング
- API Gateway（オプション）

### Phase 4: スケール対応

- 100MB+ ファイル対応
- Step Functions（分割処理）
- Kinesis（ストリーミング）

---

## 🛠️ 環境要件

- **Python 3.8+**（Generator 実行用）
- **Terraform 1.0+**（デプロイ用）
- **AWS CLI**（s3 アップロード・確認用）
- **AWS アカウント**（リソース作成用）

### 依存パッケージ

- **Generator**: 標準ライブラリのみ ✅
- **Lambda**: 標準ライブラリ + boto3（Lambda プリインストール） ✅
- **venv 不要**: 外部パッケージゼロ

---

## 📝 設定

### AWS CLI プロファイル設定

```bash
aws configure --profile default
```

または `.env` ファイルで環境変数指定（`.env.example` 参照）：

```bash
cp .env.example .env
# 編集: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
```

### Terraform 変数（オプション）

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# 編集: aws_account_id, project_name 等
```

---

## 🐛 トラブルシューティング

### Lambda 起動しない

```bash
# S3 イベント通知を確認
aws s3api get-bucket-notification-configuration \
  --bucket syslog-input-<account-id>
```

### DynamoDB 書き込み失敗

```bash
# IAM ロールを確認
aws iam get-role-policy \
  --role-name syslog-parser-lambda-role \
  --policy-name syslog-parser-lambda-policy
```

### Terraform エラー

```bash
# 初期化し直す
rm -rf .terraform terraform.lock.hcl
terraform init
```

---

## 📊 アーキテクチャダイアグラム

```
┌──────────────┐
│  User (WSL2) │
│   - Generator│──────┐
│   - AWS CLI  │      │ (1) Generate ZIP
│   - Terraform│      │
└──────────────┘      ▼
                 ┌──────────────────────┐
                 │  S3 Bucket           │ (2) Upload
                 │  raw/YYYY-MM-DD/     │◄────────┐
                 │  ├─ 00.zip           │         │
                 │  └─ 23.zip           │         │
                 └──────────┬───────────┘         │
                            │                     │
                    (3) S3 Event Notification     │
                            ▼                     │
                  ┌──────────────────┐            │
                  │  Lambda Function │            │
                  │  (Python 3.11)   │            │
                  │  512MB Memory    │            │
                  │  300s Timeout    │            │
                  └────────┬─────────┘            │
                           │                      │
                    (4) Parse CSV                 │
                    (5) Aggregate by hour         │
                           │                      │
                           ▼                      │
           ┌─────────────────────────────────┐   │
           │  DynamoDB Table               │   │
           │  syslog-hourly-stats          │   │
           │                               │   │
           │  PK: log_date (S)             │   │
           │  SK: hour (S)                 │   │
           │  Attributes:                  │   │
           │  - critical_count (N)         │   │
           │  - warning_count (N)          │   │
           │  - hostname (S)               │   │
           └─────────────────────────────────┘   │
                                                 │
                    (6) Query Results           │
                                                 │
           ┌─────────────────────────────────┐   │
           │  Dashboard (Phase 3)            │   │
           │  - Chart.js グラフ               │   │
           │  - S3 Static Hosting            │   │
           └─────────────────────────────────┘   │
                                                 │
             (7) CloudWatch Logs                │
             - /aws/lambda/syslog-parser-       │
               function                         │
             - 7日保持                          │
```

---

## 📞 サポート

問題が発生した場合：

1. [docs/design.md](docs/design.md) の **7. エラーハンドリング** を確認
2. [docs/design.md](docs/design.md) の **13. 運用設計** でトラブルシューティング
3. CloudWatch Logs でエラーを確認

---

## 📄 ライセンス

MIT License

---

## 🎓 学習ポイント

このプロジェクトで学べること：

- **Python 標準ライブラリ活用**（zipfile, csv, json, boto3）
- **AWS Serverless パターン**（S3 → Lambda → DynamoDB）
- **Terraform Infrastructure as Code**
- **IAM 最小権限の原則**
- **CloudWatch 監視・ログ**
- **コスト最適化**（無料枠の活用）

---

**作成者**: Sohey  
**作成日**: 2025-12-30  
**最終更新**: 2025-12-30
