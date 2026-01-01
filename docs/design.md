# 設計書

## プロジェクト情報

**プロジェクト名:** Juniper Syslog Analytics Serverless  
**作成日:** 2025-12-30    
**最終更新:** 2026-01-01 (Phase 2: CloudFront対応)  
**対応要件定義書:** requirements.md v2.0

---

## 1. システム構成設計

### 1.1 全体アーキテクチャ

```
┌─────────────────────────────────────────────────────────┐
│                    AWS Account                          │
│                  (ap-northeast-1)                       │
│                                                         │
│  ┌───────────────────────────────────────────────┐    │
│  │  S3 Bucket: syslog-input-bucket               │    │
│  │  ├─ raw/YYYY-MM-DD/*.zip                      │    │
│  │  └─ Versioning: Disabled                      │    │
│  │     Lifecycle: 30日後削除                      │    │
│  │     Encryption: SSE-S3                        │    │
│  └────────────┬──────────────────────────────────┘    │
│               │ Event: s3:ObjectCreated:Put            │
│               │ Filter: prefix=raw/, suffix=.zip       │
│               ↓                                         │
│  ┌───────────────────────────────────────────────┐    │
│  │  Lambda Function: syslog-parser-function      │    │
│  │  ┌─────────────────────────────────────────┐ │    │
│  │  │ Runtime: python3.11                     │ │    │
│  │  │ Memory: 512MB                           │ │    │
│  │  │ Timeout: 300s (5分)                     │ │    │
│  │  │ Handler: lambda_function.lambda_handler │ │    │
│  │  │ Package: ZIP形式 (標準ライブラリのみ)     │ │    │
│  │  │ Environment Variables:                  │ │    │
│  │  │   - DYNAMODB_TABLE: stats-table-name   │ │    │
│  │  └─────────────────────────────────────────┘ │    │
│  │                                                │    │
│  │  IAM Role: lambda-execution-role              │    │
│  │  ├─ S3 GetObject (input-bucket)               │    │
│  │  ├─ DynamoDB PutItem (stats-table)            │    │
│  │  └─ CloudWatch Logs (CreateLogGroup等)        │    │
│  └────────────┬──────────────────────────────────┘    │
│               │ boto3.Table.put_item()                 │
│               ↓                                         │
│  ┌───────────────────────────────────────────────┐    │
│  │  DynamoDB Table: syslog-hourly-stats          │    │
│  │  ┌─────────────────────────────────────────┐ │    │
│  │  │ Table Class: Standard                   │ │    │
│  │  │ Billing Mode: PAY_PER_REQUEST           │ │    │
│  │  │ Partition Key: log_date (S)             │ │    │
│  │  │ Sort Key: hour (S)                      │ │    │
│  │  │ Point-in-time Recovery: Disabled        │ │    │
│  │  │ Encryption: AWS Managed (default)       │ │    │
│  │  └─────────────────────────────────────────┘ │    │
│  └────────────┬──────────────────────────────────┘    │
│               │                                         │
│               ↓ (Phase 3実装)                          │
│  ┌───────────────────────────────────────────────┐    │
│  │  S3 Bucket: syslog-output-bucket              │    │
│  │  ├─ index.html (Dashboard)                    │    │
│  │  ├─ data/YYYY-MM-DD.json (統計データ)          │    │
│  │  └─ Public Access: BLOCKED (OAC経由のみ)      │    │
│  │     Encryption: SSE-S3                        │    │
│  └────────────┬──────────────────────────────────┘    │
│               │ Origin Access Control (OAC)            │
│               │                                         │
│  ┌───────────▼───────────────────────────────────┐    │
│  │  CloudFront Distribution (HTTPS)               │    │
│  │  ┌─────────────────────────────────────────┐ │    │
│  │  │ Domain: d1xxxxx.cloudfront.net          │ │    │
│  │  │ SSL: CloudFront Default Certificate     │ │    │
│  │  │ Price Class: 200 (米国,欧州,アジア)      │ │    │
│  │  │ Cache: index.html(1h), data/*.json(5m)  │ │    │
│  │  │ Viewer Protocol: redirect-to-https      │ │    │
│  │  └─────────────────────────────────────────┘ │    │
│  └────────────┬──────────────────────────────────┘    │
│               │ HTTPS                                   │
│               ↓                                         │
│         [ User Browser ]                                │
│                                                         │
│  ┌───────────────────────────────────────────────┐    │
│  │  CloudWatch Logs                               │    │
│  │  └─ /aws/lambda/syslog-parser-function        │    │
│  │     Retention: 7 days                         │    │
│  └───────────────────────────────────────────────┘    │
│                                                         │
└─────────────────────────────────────────────────────────┘

【外部システム】
User PC (WSL2)
  ├─ Syslog Generator (Python)
  ├─ AWS CLI
  └─ Terraform
```

### 1.2 データフロー詳細

```
【フロー1: ログアップロード〜解析】

Step 1: ユーザー操作
  User: AWS CLI実行
  $ aws s3 cp 10.zip s3://syslog-input-bucket/raw/2025-04-28/
  
  Duration: ~5秒 (10MB ZIP)

Step 2: S3イベント発火
  Event Type: s3:ObjectCreated:Put
  Event Payload:
  {
    "Records": [{
      "eventName": "ObjectCreated:Put",
      "s3": {
        "bucket": {"name": "syslog-input-bucket"},
        "object": {
          "key": "raw/2025-04-28/10.zip",
          "size": 10485760
        }
      }
    }]
  }
  
  Duration: ~100ms (イベント伝播)

Step 3: Lambda起動
  Invocation Type: Event (非同期)
  Trigger: S3イベント通知
  Cold Start: 初回のみ ~3秒
  Warm Start: ~100ms
  
Step 4: Lambda処理実行
  4-1. S3ダウンロード (5秒)
       boto3.download_file()
       /tmp/input.zip (10MB)
  
  4-2. ZIP解凍 (2秒)
       zipfile.ZipFile.extractall()
       /tmp/extracted/10.csv (10MB)
  
  4-3. CSV解析 (20秒)
       csv.DictReader()
       50,000行をメモリ上で処理
       CRITICAL/WARNING フィルタ
       時間別集計
       
       メモリ使用量: ~200MB
       
  4-4. DynamoDB書き込み (3秒)
       24回のput_item() (時間ごと)
       
  Total Duration: ~30秒 (10MBファイル)
  
Step 5: CloudWatch Logs出力
  Log Group: /aws/lambda/syslog-parser-function
  Log Stream: 2025/04/28/[$LATEST]xxxxx
  
  ログ内容:
  - 処理開始ログ
  - S3ダウンロード完了
  - CSV解析統計（CRITICAL: X件, WARNING: Y件）
  - DynamoDB書き込み完了
  - 処理完了（所要時間）
```

---

## 2. Lambda関数詳細設計

### 2.1 関数構成

```
lambda/syslog_parser/
├── lambda_function.py    # メインハンドラー
└── requirements.txt      # 空ファイル（標準ライブラリのみ）
```

### 2.2 lambda_function.py 実装仕様

```python
"""
Juniper Syslog Parser Lambda Function

S3にアップロードされたZIP形式のSyslogを解析し、
CRITICAL/WARNING ログを時間別に集計してDynamoDBに保存する。

Author: Sohey
Created: 2025-12-30
"""

import os
import json
import boto3
import zipfile
import csv
from datetime import datetime
from collections import defaultdict
from pathlib import Path

# 環境変数
DYNAMODB_TABLE = os.environ['DYNAMODB_TABLE']

# AWSクライアント初期化（グローバル変数で再利用）
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMODB_TABLE)

def lambda_handler(event, context):
    """
    メインハンドラー
    
    Args:
        event (dict): S3イベント通知
            {
              "Records": [{
                "s3": {
                  "bucket": {"name": "bucket-name"},
                  "object": {"key": "raw/2025-04-28/10.zip"}
                }
              }]
            }
        context (LambdaContext): Lambda実行コンテキスト
    
    Returns:
        dict: 処理結果
            {
              'statusCode': 200,
              'body': 'Successfully processed ...'
            }
    
    Raises:
        Exception: S3アクセスエラー、ZIP解凍エラー等
    """
    try:
        print("=== Lambda Function Started ===")
        
        # 1. イベントからS3情報取得
        bucket, key = extract_s3_info(event)
        print(f"Processing: s3://{bucket}/{key}")
        
        # 2. ZIPダウンロード
        local_zip = download_zip(bucket, key)
        print(f"Downloaded to: {local_zip}")
        
        # 3. CSV解凍
        csv_path = extract_csv(local_zip)
        print(f"Extracted to: {csv_path}")
        
        # 4. CSV解析
        stats = parse_csv(csv_path)
        print(f"Parsed log_date: {stats['log_date']}")
        print(f"Total hours: {len(stats['hourly_stats'])}")
        
        # 5. DynamoDB保存
        save_to_dynamodb(stats, key)
        print(f"Saved to DynamoDB: {DYNAMODB_TABLE}")
        
        print("=== Lambda Function Completed ===")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Successfully processed {key}',
                'log_date': stats['log_date'],
                'total_hours': len(stats['hourly_stats'])
            })
        }
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

def extract_s3_info(event):
    """
    S3イベントからバケット名とキーを抽出
    
    Args:
        event (dict): S3イベント
    
    Returns:
        tuple: (bucket_name, object_key)
    """
    record = event['Records'][0]
    bucket = record['s3']['bucket']['name']
    key = record['s3']['object']['key']
    return bucket, key

def download_zip(bucket, key):
    """
    S3からZIPファイルをダウンロード
    
    Args:
        bucket (str): S3バケット名
        key (str): S3オブジェクトキー
    
    Returns:
        str: ローカルファイルパス
    """
    local_path = '/tmp/input.zip'
    s3_client.download_file(bucket, key, local_path)
    return local_path

def extract_csv(zip_path):
    """
    ZIPを解凍してCSVパスを返す
    
    Args:
        zip_path (str): ZIPファイルパス
    
    Returns:
        str: CSVファイルパス
    
    Raises:
        Exception: ZIP内にCSVが見つからない場合
    """
    extract_dir = '/tmp/extracted'
    Path(extract_dir).mkdir(exist_ok=True)
    
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(extract_dir)
        csv_files = [f for f in z.namelist() if f.endswith('.csv')]
        
        if not csv_files:
            raise Exception("No CSV file found in ZIP")
        
        return f"{extract_dir}/{csv_files[0]}"

def parse_csv(csv_path):
    """
    CSVを解析して時間別統計を作成
    
    Args:
        csv_path (str): CSVファイルパス
    
    Returns:
        dict: {
            'log_date': '2025-04-28',
            'hostname': 'srx-fw01',
            'hourly_stats': {
                '10:00': {'CRITICAL': 15, 'WARNING': 43},
                '11:00': {'CRITICAL': 8, 'WARNING': 37},
                ...
            }
        }
    
    処理内容:
        1. CSV読み込み (csv.DictReader)
        2. Timestamp から時間抽出 (文字列スライス)
        3. Severity フィルタ (CRITICAL, WARNING)
        4. 時間別カウント (defaultdict)
    """
    stats = defaultdict(lambda: {'CRITICAL': 0, 'WARNING': 0})
    log_date = None
    hostname = None
    total_rows = 0
    filtered_rows = 0
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            total_rows += 1
            
            # 初回のみ日付とホスト名取得
            if not log_date:
                # "2025-04-28T10:15:30Z" → "2025-04-28"
                log_date = row['Timestamp'][:10]
                hostname = row['Hostname']
            
            severity = row['Severity']
            
            # CRITICAL/WARNING のみカウント
            if severity in ['CRITICAL', 'WARNING']:
                filtered_rows += 1
                # "2025-04-28T10:15:30Z" → "10:00"
                hour = row['Timestamp'][11:13] + ':00'
                stats[hour][severity] += 1
    
    print(f"CSV Statistics:")
    print(f"  Total rows: {total_rows}")
    print(f"  Filtered rows (CRITICAL/WARNING): {filtered_rows}")
    print(f"  Filter ratio: {filtered_rows/total_rows*100:.1f}%")
    
    return {
        'log_date': log_date,
        'hostname': hostname,
        'hourly_stats': dict(stats)
    }

def save_to_dynamodb(stats, file_name):
    """
    DynamoDBに時間別統計を保存
    
    Args:
        stats (dict): parse_csv()の返り値
        file_name (str): S3オブジェクトキー
    
    DynamoDBスキーマ:
        PK: log_date (String)
        SK: hour (String)
        Attributes:
            - critical_count (Number)
            - warning_count (Number)
            - total_count (Number)
            - hostname (String)
            - processed_at (String)
            - file_name (String)
    """
    log_date = stats['log_date']
    hostname = stats['hostname']
    processed_at = datetime.utcnow().isoformat() + 'Z'
    
    saved_count = 0
    
    # 時間ごとにアイテム作成
    for hour, counts in stats['hourly_stats'].items():
        critical = counts['CRITICAL']
        warning = counts['WARNING']
        total = critical + warning
        
        table.put_item(Item={
            'log_date': log_date,
            'hour': hour,
            'critical_count': critical,
            'warning_count': warning,
            'total_count': total,
            'hostname': hostname,
            'processed_at': processed_at,
            'file_name': file_name
        })
        
        saved_count += 1
    
    print(f"DynamoDB: Saved {saved_count} items")
```

### 2.3 Lambda設定値

| 設定項目 | 値 | 理由 |
|---------|---|------|
| Runtime | python3.11 | 最新、高速 |
| Memory | 512MB | CSV 50,000行処理に必要 |
| Timeout | 300秒 (5分) | 100MBファイル処理余裕 |
| Ephemeral Storage | 512MB (デフォルト) | ZIP+CSV で最大200MB |
| Architecture | x86_64 | 互換性重視 |
| Reserved Concurrency | なし | 同時実行制限なし |

### 2.4 環境変数

| 変数名 | 値 | 説明 |
|-------|---|------|
| DYNAMODB_TABLE | `syslog-hourly-stats` | DynamoDBテーブル名 |

---

## 3. DynamoDB設計

### 3.1 テーブル仕様

```
テーブル名: syslog-hourly-stats
リージョン: ap-northeast-1
Table Class: Standard
Billing Mode: PAY_PER_REQUEST (オンデマンド)

キー設計:
  Partition Key: log_date (String)
    形式: YYYY-MM-DD
    例: "2025-04-28"
  
  Sort Key: hour (String)
    形式: HH:00
    例: "10:00"

属性:
  - log_date (S) [PK]
  - hour (S) [SK]
  - critical_count (N)
  - warning_count (N)
  - total_count (N)
  - hostname (S)
  - processed_at (S)
  - file_name (S)

インデックス: なし

設定:
  - Point-in-time Recovery: 無効
  - Encryption: AWS Managed
  - Time to Live (TTL): 未設定
  - Stream: 無効
```

### 3.2 アクセスパターン

**パターン1: 特定日の全時間データ取得**

```python
response = table.query(
    KeyConditionExpression=Key('log_date').eq('2025-04-28')
)

# 返却データ: 24件 (00:00 ~ 23:00)
```

**パターン2: 特定時刻のデータ取得**

```python
response = table.query(
    KeyConditionExpression=Key('log_date').eq('2025-04-28') & Key('hour').eq('10:00')
)

# 返却データ: 1件
```

**パターン3: 時間範囲でのデータ取得**

```python
response = table.query(
    KeyConditionExpression=Key('log_date').eq('2025-04-28') & Key('hour').between('10:00', '12:00')
)

# 返却データ: 3件 (10:00, 11:00, 12:00)
```

### 3.3 容量見積もり

```
1アイテムのサイズ:
  log_date: 10 bytes
  hour: 5 bytes
  critical_count: 8 bytes
  warning_count: 8 bytes
  total_count: 8 bytes
  hostname: 10 bytes
  processed_at: 25 bytes
  file_name: 30 bytes
  
  合計: 約 100 bytes

1日分: 100 bytes × 24時間 = 2.4 KB
1ヶ月分: 2.4 KB × 30日 = 72 KB
1年分: 72 KB × 12ヶ月 = 864 KB

→ 無料枠 25GB に対して十分小さい
```

---

## 4. S3バケット設計

### 4.1 入力バケット (syslog-input-bucket)

```
Bucket Name: syslog-input-{AWS_ACCOUNT_ID}
Region: ap-northeast-1

Versioning: 無効
Encryption: SSE-S3 (AES-256)
Public Access: すべてブロック

Lifecycle Rule:
  Name: delete-old-logs
  Filter: Prefix = raw/
  Action: Delete after 30 days
  Status: Enabled

Event Notification:
  Event Type: s3:ObjectCreated:Put
  Filter:
    Prefix: raw/
    Suffix: .zip
  Destination: Lambda Function (syslog-parser-function)

ディレクトリ構造:
  raw/
  └── YYYY-MM-DD/
      ├── 00.zip
      ├── 01.zip
      ...
      └── 23.zip
```

### 4.2 出力バケット (syslog-output-bucket) - Phase 3

```
Bucket Name: syslog-output-{AWS_ACCOUNT_ID}
Region: ap-northeast-1

Versioning: 無効
Encryption: SSE-S3
Public Access: 
  - BlockPublicAcls: true
  - IgnorePublicAcls: true
  - BlockPublicPolicy: false (静的ホスティング用)
  - RestrictPublicBuckets: false

Static Website Hosting:
  Enabled: Yes
  Index Document: dashboard/index.html
  Error Document: error.html

Bucket Policy:
  Allow s3:GetObject for * (公開読み取り)

ディレクトリ構造:
  dashboard/
  └── index.html
```

---

## 5. IAM設計

### 5.1 Lambda実行ロール

```hcl
# Terraform定義

resource "aws_iam_role" "lambda_exec" {
  name = "syslog-parser-lambda-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "lambda_policy" {
  role = aws_iam_role.lambda_exec.id
  name = "syslog-parser-lambda-policy"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # S3読み取り（入力バケットのみ）
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = "${aws_s3_bucket.input.arn}/*"
      },
      
      # DynamoDB書き込み（statsテーブルのみ）
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem"
        ]
        Resource = aws_dynamodb_table.stats.arn
      },
      
      # CloudWatch Logs（全Lambda標準）
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}
```

### 5.2 最小権限の原則

**許可していない操作:**
- S3: DeleteObject, PutObject (不要)
- DynamoDB: DeleteItem, UpdateItem, Scan (不要)
- Lambda: InvokeFunction (不要)
- 他サービス: すべて拒否

---

## 6. Terraformディレクトリ構成

```
terraform/
├── main.tf              # Provider、Backend設定
├── variables.tf         # 変数定義
├── outputs.tf           # 出力値
├── s3.tf               # S3バケット
├── lambda.tf           # Lambda関数
├── iam.tf              # IAMロール・ポリシー
├── dynamodb.tf         # DynamoDBテーブル
└── cloudwatch.tf       # CloudWatch Logs

各ファイルの役割:
  - main.tf: 共通設定（provider, region等）
  - s3.tf: 入力/出力バケット、イベント通知
  - lambda.tf: 関数定義、トリガー設定
  - iam.tf: 最小権限IAMロール
  - dynamodb.tf: テーブル定義
  - cloudwatch.tf: ログ保持期間設定
```

---

## 7. エラーハンドリング設計

### 7.1 Lambda内エラー処理

| エラー種別 | 処理 | CloudWatch出力 |
|----------|-----|---------------|
| S3アクセスエラー | 例外スロー | ERROR + traceback |
| ZIP解凍エラー | 例外スロー | ERROR + traceback |
| CSV形式エラー | 例外スロー | ERROR + 行番号 |
| DynamoDB書き込みエラー | 例外スロー | ERROR + Item情報 |

```python
try:
    # 処理
except Exception as e:
    print(f"ERROR: {str(e)}")
    import traceback
    traceback.print_exc()
    raise  # Lambda が失敗として記録
```

### 7.2 リトライ戦略

- **Lambda:** S3イベント通知は自動リトライ（最大2回）
- **DynamoDB:** boto3デフォルトリトライ（Exponential Backoff）

---

## 8. 監視・ログ設計

### 8.1 CloudWatch Logs

```
Log Group: /aws/lambda/syslog-parser-function
Retention: 7 days
Encryption: デフォルト (AES-256)

ログレベル:
  - INFO: 処理開始/完了、統計情報
  - ERROR: 例外発生時

サンプルログ:
[INFO] === Lambda Function Started ===
[INFO] Processing: s3://syslog-input-123456/raw/2025-04-28/10.zip
[INFO] Downloaded to: /tmp/input.zip
[INFO] Extracted to: /tmp/extracted/10.csv
[INFO] CSV Statistics:
[INFO]   Total rows: 50400
[INFO]   Filtered rows (CRITICAL/WARNING): 5040
[INFO]   Filter ratio: 10.0%
[INFO] Parsed log_date: 2025-04-28
[INFO] Total hours: 24
[INFO] DynamoDB: Saved 24 items
[INFO] === Lambda Function Completed ===
```

### 8.2 CloudWatch Metrics（自動収集）

- Lambda Invocations
- Lambda Duration
- Lambda Errors
- Lambda Throttles

### 8.3 アラート設計（Phase 3）

```
アラート1: Lambda実行エラー
  Metric: Errors
  Threshold: > 0
  Period: 5分
  Action: SNS通知

アラート2: Lambda実行時間超過
  Metric: Duration
  Threshold: > 240秒 (4分)
  Period: 5分
  Action: SNS通知
```

---

## 9. セキュリティ設計

### 9.1 データ保護

| データ | 保護方法 |
|-------|---------|
| S3 (転送中) | HTTPS強制 |
| S3 (保管時) | SSE-S3 (AES-256) |
| DynamoDB (転送中) | HTTPS (boto3デフォルト) |
| DynamoDB (保管時) | AWS Managed Key |
| Lambda環境変数 | 暗号化なし（機密情報なし） |

### 9.2 アクセス制御

```
Lambda → S3: 
  ✓ GetObject (入力バケットのみ)
  ✗ PutObject, DeleteObject

Lambda → DynamoDB:
  ✓ PutItem (statsテーブルのみ)
  ✗ DeleteItem, UpdateItem, Scan

User → S3:
  AWS CLI経由 (IAM User認証)
```

### 9.3 ネットワーク設計

- **Lambda:** VPC不要（パブリックサービスのみアクセス）
- **S3:** VPC Endpoint不要（無料枠優先）
- **DynamoDB:** VPC Endpoint不要

---

## 10. コスト設計

### 10.1 月間コスト見積もり（30日間）

```
【前提】
- 1日あたり24ファイル (10MB × 24)
- Lambda実行: 30秒/ファイル
- DynamoDB書き込み: 24件/ファイル
- ダッシュボードアクセス: 10回/日

【Lambda】
  実行回数: 24 × 30 = 720回/月
  無料枠: 100万回/月
  → $0 ✅

  実行時間: 720回 × 30秒 × 512MB = 10,800 GB秒
  無料枠: 400,000 GB秒/月
  → $0 ✅

【S3】
  Storage: 240MB (10MB × 24ファイル)
  無料枠: 5GB
  → $0 ✅
  
  PUT: 720回/月 + 30回(Lambda→Output)
  無料枠: 2,000回/月
  → $0 ✅
  
  GET (Lambda): 720回/月
  無料枠: 20,000回/月
  → $0 ✅

【DynamoDB】
  Storage: 72 KB/月
  無料枠: 25GB
  → $0 ✅
  
  Write: 720ファイル × 24件 = 17,280 WCU
  無料枠: 200万 WCU/月
  → $0 ✅

【CloudFront】🆕
  HTTPS リクエスト: 300回/月 (10回/日 × 30日)
  無料枠: 1,000万回/月
  → $0 ✅
  
  データ転送: 15MB/月 (50KB × 300回)
  無料枠: 50GB/月 (最初の12ヶ月)
  → $0 ✅
  
  13ヶ月目以降:
  15MB × $0.114/GB = $0.0017/月 (0.17円)

合計: 
  最初の12ヶ月: $0/月 🎉
  13ヶ月目以降: ~$0.002/月 (0.2円)
```

### 10.2 コスト最適化施策

- S3 Lifecycle: 30日後自動削除
- DynamoDB: オンデマンド課金（待機コストゼロ）
- Lambda: 標準ライブラリのみ（Layer不要）
- CloudWatch Logs: 7日保持（最小限）
- **CloudFront: Price Class 200（日本含む、グローバル配信は不要）** 🆕
- **S3 OAC: S3→CloudFront転送は無料** 🆕

---

## 11. テスト設計

### 11.1 ユニットテスト

```python
# lambda/syslog_parser/tests/test_parser.py

import unittest
from lambda_function import extract_s3_info, parse_csv

class TestLambdaFunction(unittest.TestCase):
    
    def test_extract_s3_info(self):
        event = {
            'Records': [{
                's3': {
                    'bucket': {'name': 'test-bucket'},
                    'object': {'key': 'raw/2025-04-28/10.zip'}
                }
            }]
        }
        bucket, key = extract_s3_info(event)
        self.assertEqual(bucket, 'test-bucket')
        self.assertEqual(key, 'raw/2025-04-28/10.zip')
    
    def test_parse_csv(self):
        # サンプルCSVを使ってテスト
        csv_path = './test_data/sample.csv'
        stats = parse_csv(csv_path)
        
        self.assertIn('log_date', stats)
        self.assertIn('hostname', stats)
        self.assertIn('hourly_stats', stats)

if __name__ == '__main__':
    unittest.main()
```

### 11.2 統合テスト

```bash
# E2Eテストスクリプト

#!/bin/bash

# 1. サンプルデータ生成
python generator/generate.py -r 2100 -o ./test_data

# 2. S3アップロード
aws s3 cp test_data/10.zip s3://syslog-input-bucket/raw/2025-04-28/

# 3. Lambda実行確認（CloudWatch Logs監視）
aws logs tail /aws/lambda/syslog-parser-function --follow

# 4. DynamoDB確認
aws dynamodb query \
  --table-name syslog-hourly-stats \
  --key-condition-expression "log_date = :date" \
  --expression-attribute-values '{":date":{"S":"2025-04-28"}}'

# 5. 結果検証
# - 24件のアイテムが存在すること
# - CRITICAL/WARNING のカウントが正確であること
```

---

## 12. デプロイ設計

### 12.1 デプロイフロー

```
【ローカル → AWS】

1. Terraform初期化
   $ cd terraform
   $ terraform init

2. 変数設定
   $ cp terraform.tfvars.example terraform.tfvars
   $ vi terraform.tfvars
   
   aws_region = "ap-northeast-1"
   project_name = "syslog-analytics"

3. デプロイプラン確認
   $ terraform plan

4. デプロイ実行
   $ terraform apply

5. 動作確認
   $ aws s3 cp test.zip s3://...
```

### 12.2 CI/CD設計（GitHub Actions）

```yaml
# .github/workflows/terraform.yml

name: Terraform

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  terraform:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v2
        with:
          terraform_version: 1.6.0
      
      - name: Configure AWS Credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ap-northeast-1
      
      - name: Terraform Init
        run: terraform init
        working-directory: ./terraform
      
      - name: Terraform Format Check
        run: terraform fmt -check
        working-directory: ./terraform
      
      - name: Terraform Validate
        run: terraform validate
        working-directory: ./terraform
      
      - name: Terraform Plan
        if: github.event_name == 'pull_request'
        run: terraform plan
        working-directory: ./terraform
      
      - name: Terraform Apply
        if: github.event_name == 'push' && github.ref == 'refs/heads/main'
        run: terraform apply -auto-approve
        working-directory: ./terraform
```

---

## 13. 運用設計

### 13.1 日常運用

```
【日次】
- CloudWatch Logs確認（エラーがないか）
- DynamoDB容量確認（25GB以下か）

【週次】
- S3ストレージ確認（Lifecycle動作確認）
- コスト確認（$0維持できているか）

【月次】
- Lambda実行統計レビュー
- DynamoDBデータ精査
```

### 13.2 トラブルシューティング

| 症状 | 原因 | 対処 |
|-----|-----|-----|
| Lambda起動しない | S3イベント通知未設定 | Terraform再適用 |
| DynamoDB書き込み失敗 | IAM権限不足 | ロール確認 |
| Lambda Timeout | ファイルサイズ大 | メモリ増加 |
| S3アップロード失敗 | バケット名誤り | バケット名確認 |

---

## 14. 拡張性設計

### 14.1 Phase 3: 可視化

```
Option A実装時:
  1. dashboard/index.html 作成
  2. Chart.js でグラフ描画
  3. DynamoDB API経由でデータ取得
  4. S3静的ホスティング有効化
```

### 14.2 Phase 4: 大容量対応

```
100MB超のファイル対応:
  1. Step Functions導入
  2. ファイル分割処理
  3. 並列実行
  
または:
  1. Kinesis Data Firehose
  2. ストリーミング処理
```

---

**文書履歴:**

| バージョン | 日付 | 変更内容 | 作成者 |
|----------|-----|---------|-------|
| 1.0 | 2025-04-28 | 初版作成 | Sohey |