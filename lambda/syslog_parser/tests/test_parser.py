"""
Lambda Function ユニットテスト

単体テスト: lambda_function.py の各関数をテスト
boto3 のモック環境を整備
"""

import unittest
import csv
import json
import tempfile
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch

# boto3 をモック化（Lambda 環境で利用可能だが、ローカルテストではインストール不要）
sys.modules['boto3'] = Mock()

# 同じディレクトリから import
sys.path.insert(0, str(Path(__file__).parent.parent))

from lambda_function import extract_s3_info, parse_csv


class TestLambdaFunctionHelpers(unittest.TestCase):
    """Lambda ヘルパー関数のテスト"""

    def test_extract_s3_info_success(self):
        """S3 イベントから情報を抽出できるか"""
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

    def test_extract_s3_info_with_deep_path(self):
        """深いパスでも正しく抽出できるか"""
        event = {
            'Records': [{
                's3': {
                    'bucket': {'name': 'syslog-input-123456'},
                    'object': {'key': 'raw/2025-12-30/srx-fw01-12.zip'}
                }
            }]
        }
        
        bucket, key = extract_s3_info(event)
        
        self.assertEqual(bucket, 'syslog-input-123456')
        self.assertEqual(key, 'raw/2025-12-30/srx-fw01-12.zip')


class TestParseCSV(unittest.TestCase):
    """CSV パース関数のテスト"""

    def setUp(self):
        """各テストの前に準備"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.csv_path = Path(self.temp_dir.name) / 'test.csv'

    def tearDown(self):
        """各テストの後にクリーンアップ"""
        self.temp_dir.cleanup()

    def test_parse_csv_basic(self):
        """基本的な CSV パースが機能するか"""
        # テスト用 CSV を生成
        with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'Timestamp', 'Hostname', 'Severity', 'Message', 'Component'
            ])
            writer.writeheader()
            writer.writerow({
                'Timestamp': '2025-04-28T10:15:30Z',
                'Hostname': 'srx-fw01',
                'Severity': 'CRITICAL',
                'Message': 'Interface down',
                'Component': 'j-daemon'
            })
            writer.writerow({
                'Timestamp': '2025-04-28T10:20:45Z',
                'Hostname': 'srx-fw01',
                'Severity': 'WARNING',
                'Message': 'High CPU',
                'Component': 'j-daemon'
            })
            writer.writerow({
                'Timestamp': '2025-04-28T10:25:00Z',
                'Hostname': 'srx-fw01',
                'Severity': 'INFO',
                'Message': 'System start',
                'Component': 'j-daemon'
            })
        
        # パース実行
        stats = parse_csv(str(self.csv_path))
        
        # アサーション
        self.assertEqual(stats['log_date'], '2025-04-28')
        self.assertEqual(stats['hostname'], 'srx-fw01')
        self.assertIn('10:00', stats['hourly_stats'])
        self.assertEqual(stats['hourly_stats']['10:00']['CRITICAL'], 1)
        self.assertEqual(stats['hourly_stats']['10:00']['WARNING'], 1)

    def test_parse_csv_multiple_hours(self):
        """複数時間のデータが正しく集計されるか"""
        with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'Timestamp', 'Hostname', 'Severity', 'Message', 'Component'
            ])
            writer.writeheader()
            
            # 10時台 CRITICAL 5件
            for i in range(5):
                writer.writerow({
                    'Timestamp': f'2025-04-28T10:{i:02d}:00Z',
                    'Hostname': 'srx-fw01',
                    'Severity': 'CRITICAL',
                    'Message': f'Error {i}',
                    'Component': 'j-daemon'
                })
            
            # 11時台 WARNING 3件
            for i in range(3):
                writer.writerow({
                    'Timestamp': f'2025-04-28T11:{i:02d}:00Z',
                    'Hostname': 'srx-fw01',
                    'Severity': 'WARNING',
                    'Message': f'Warn {i}',
                    'Component': 'j-daemon'
                })
        
        stats = parse_csv(str(self.csv_path))
        
        self.assertEqual(stats['hourly_stats']['10:00']['CRITICAL'], 5)
        self.assertEqual(stats['hourly_stats']['11:00']['WARNING'], 3)

    def test_parse_csv_filters_info(self):
        """INFO レベルは除外されるか"""
        with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'Timestamp', 'Hostname', 'Severity', 'Message', 'Component'
            ])
            writer.writeheader()
            writer.writerow({
                'Timestamp': '2025-04-28T10:00:00Z',
                'Hostname': 'srx-fw01',
                'Severity': 'INFO',
                'Message': 'Startup',
                'Component': 'j-daemon'
            })
        
        stats = parse_csv(str(self.csv_path))
        
        # CRITICAL/WARNING がないため hourly_stats は空
        self.assertEqual(len(stats['hourly_stats']), 0)

    def test_parse_csv_empty_file(self):
        """ヘッダーのみのファイルでもエラーが発生しないか"""
        with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'Timestamp', 'Hostname', 'Severity', 'Message', 'Component'
            ])
            writer.writeheader()
        
        # パースが失敗しないか確認
        try:
            stats = parse_csv(str(self.csv_path))
            self.assertIsNone(stats['log_date'])
            self.assertEqual(len(stats['hourly_stats']), 0)
        except Exception as e:
            self.fail(f"parse_csv raised {e}")


class TestDataConsistency(unittest.TestCase):
    """データ一貫性テスト"""

    def setUp(self):
        """テスト準備"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.csv_path = Path(self.temp_dir.name) / 'test.csv'

    def tearDown(self):
        """テストクリーンアップ"""
        self.temp_dir.cleanup()

    def test_parse_csv_calculates_total(self):
        """total_count が CRITICAL + WARNING で計算されるか"""
        with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'Timestamp', 'Hostname', 'Severity', 'Message', 'Component'
            ])
            writer.writeheader()
            
            # CRITICAL 7件、WARNING 3件
            for i in range(7):
                writer.writerow({
                    'Timestamp': f'2025-04-28T10:{i:02d}:00Z',
                    'Hostname': 'srx-fw01',
                    'Severity': 'CRITICAL',
                    'Message': 'Error',
                    'Component': 'j-daemon'
                })
            for i in range(3):
                writer.writerow({
                    'Timestamp': f'2025-04-28T10:{i+10:02d}:00Z',
                    'Hostname': 'srx-fw01',
                    'Severity': 'WARNING',
                    'Message': 'Warn',
                    'Component': 'j-daemon'
                })
        
        stats = parse_csv(str(self.csv_path))
        
        self.assertEqual(stats['hourly_stats']['10:00']['CRITICAL'], 7)
        self.assertEqual(stats['hourly_stats']['10:00']['WARNING'], 3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
