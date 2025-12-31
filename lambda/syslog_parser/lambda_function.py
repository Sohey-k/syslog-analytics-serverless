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
OUTPUT_BUCKET = os.environ.get('OUTPUT_BUCKET', 'syslog-output-235270183100')

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
    if total_rows > 0:
        print(f"  Filter ratio: {filtered_rows/total_rows*100:.1f}%")
    else:
        print(f"  Filter ratio: N/A (no data)")
    
    return {
        'log_date': log_date,
        'hostname': hostname,
        'hourly_stats': dict(stats)
    }


def save_to_dynamodb(stats, file_name):
    """
    DynamoDBに時間別統計を保存 + S3にJSON出力
    
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
    
    # === S3にJSON出力（ダッシュボード用） ===
    export_to_s3_json(stats, processed_at)


def export_to_s3_json(stats, processed_at):
    """
    S3にJSON形式で統計データを出力（ダッシュボード用）
    DynamoDBから該当日の全時間データを取得してJSONを生成
    
    Args:
        stats (dict): parse_csv()の返り値
        processed_at (str): 処理日時（ISO 8601形式）
    
    出力先:
        s3://{OUTPUT_BUCKET}/data/{log_date}.json
    
    JSONフォーマット:
        {
          "log_date": "2025-04-28",
          "hostname": "srx-fw01",
          "processed_at": "2025-04-28T12:34:56Z",
          "hourly_stats": [
            {"hour": "00:00", "critical": 15, "warning": 43, "total": 58},
            {"hour": "01:00", "critical": 12, "warning": 38, "total": 50},
            ...
          ]
        }
    """
    log_date = stats['log_date']
    hostname = stats['hostname']
    
    # DynamoDBから該当日の全時間データを取得
    try:
        response = table.query(
            KeyConditionExpression='log_date = :date',
            ExpressionAttributeValues={
                ':date': log_date
            }
        )
        
        # 時間別データを配列に変換（ソート済み）
        hourly_list = []
        for item in sorted(response['Items'], key=lambda x: x['hour']):
            hourly_list.append({
                'hour': item['hour'],
                'critical': int(item['critical_count']),  # Decimal → int
                'warning': int(item['warning_count']),     # Decimal → int
                'total': int(item['total_count'])          # Decimal → int
            })
        
        # JSON構造作成
        output_data = {
            'log_date': log_date,
            'hostname': hostname,
            'processed_at': processed_at,
            'total_hours': len(hourly_list),
            'hourly_stats': hourly_list
        }
        
        # S3にアップロード（バケットポリシーで公開）
        json_key = f"data/{log_date}.json"
        
        s3_client.put_object(
            Bucket=OUTPUT_BUCKET,
            Key=json_key,
            Body=json.dumps(output_data, ensure_ascii=False, indent=2),
            ContentType='application/json'
        )
        print(f"JSON exported to s3://{OUTPUT_BUCKET}/{json_key} ({len(hourly_list)} hours)")
        
    except Exception as e:
        print(f"WARNING: Failed to export JSON: {str(e)}")
        import traceback
        traceback.print_exc()
        # DynamoDB保存が成功していればエラーにしない
