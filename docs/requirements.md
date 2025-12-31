# 要件定義書 v2.0

## プロジェクト概要

**プロジェクト名:** Juniper Syslog Analytics Serverless  
**作成日:** 2025-12-30  
**最終更新:** 2025-12-30  
**目的:** 既存のJuniper Syslogジェネレーターのログを、AWSサーバーレスで自動分析  
**背景:** Python自動化実績を、クラウドネイティブな構成で再実装

---

## 1. 機能要件

### 1.1 入力データ仕様

**ソースデータ:**
- **生成ツール:** 既存のJuniper Syslogジェネレーター
- **出力形式:** ZIP圧縮CSV（00.zip ~ 23.zip）
- **CSV構造:**

```csv
Timestamp,Hostname,AppName,SeverityLevel,Severity,LogType,Message
2025-04-28T10:15:30Z,srx-fw01,RT_SCREEN,2,CRITICAL,THREAT,RT_SCREEN_TCP: SYN flood...
```

**フィールド定義:**

| カラム名 | 型 | 説明 | 例 |
|---------|---|------|---|
| Timestamp | String (ISO8601) | ログ発生時刻 | 2025-04-28T10:15:30Z |
| Hostname | String | 機器名 | srx-fw01 |
| AppName | String | アプリケーション | RT_SCREEN, RT_IDP |
| SeverityLevel | Integer | Severity数値 | 0-7 (RFC5424) |
| Severity | String | **重要度** | CRITICAL, WARNING, INFO |
| LogType | String | ログ種別 | THREAT, NORMAL |
| Message | String | 詳細メッセージ | 攻撃内容、送信元IP等 |

**データ量:**

```
検証用: 10MB (2,100行/時間 × 24時間 = 50,400行)
本番想定: 100MB (21,000行/時間 × 24時間 = 504,000行)
```

### 1.2 処理要件

**抽出条件:**
- **対象Severity:** `CRITICAL` および `WARNING` のみ
- **集計軸:** 時間単位（HH:00形式）

**処理フロー:**

```
1. ZIPファイル受信 (例: 10.zip)
2. /tmpディレクトリに解凍
3. CSV読み込み (標準ライブラリのみ、pandas不使用)
4. Timestampから時間部分抽出
   - "2025-04-28T10:15:30Z" → "10:00"
5. Severity でフィルタ (CRITICAL, WARNING)
6. 時間別にカウント
7. DynamoDB保存
```

**サンプル処理結果:**

```python
{
    "log_date": "2025-04-28",
    "hourly_stats": {
        "10:00": {"CRITICAL": 15, "WARNING": 43, "total": 58},
        "11:00": {"CRITICAL": 8, "WARNING": 37, "total": 45},
        # ... 24時間分
    }
}
```

### 1.3 データ保存仕様

**DynamoDB テーブル設計:**

```
テーブル名: syslog-hourly-stats

パーティションキー: log_date (String)
  例: "2025-04-28"

ソートキー: hour (String)
  例: "10:00"

属性:
  - critical_count (Number)
  - warning_count (Number)
  - total_count (Number)
  - hostname (String)
  - processed_at (String, ISO8601)
  - file_name (String)

インデックス: なし (単純な時系列検索のみ)
```

**アクセスパターン:**

```
クエリ1: 特定日の全時間データ取得
  → Query: log_date = "2025-04-28"

クエリ2: 特定日時のデータ取得
  → Query: log_date = "2025-04-28" AND hour = "10:00"
```

### 1.4 可視化要件（Phase 3）

**優先順位付き選択肢:**

**Option A (推奨): S3静的ホスティング**

```
メリット:
- 完全無料枠内
- シンプル
- Chart.js でリッチなグラフ

構成:
- S3バケット (静的ウェブホスティング有効)
- index.html (Chart.js CDN読み込み)
- JavaScript で DynamoDB API経由データ取得
```

**Option B: CloudWatch Metrics**

```
メリット:
- AWS標準の監視基盤
- アラート設定可能

構成:
- Lambda内でPutMetricData
- CloudWatch Dashboard作成
```

**Option C: API Gateway + Lambda**

```
メリット:
- リアルタイム性
- 外部連携可能

構成:
- API Gateway (REST API)
- Lambda (DynamoDB読み取り)
- 返却JSON をフロントで描画
```

---

## 2. 非機能要件

### 2.1 パフォーマンス

| 項目 | 検証用 (10MB) | 本番想定 (100MB) | 上限 |
|-----|-------------|----------------|-----|
| Lambda実行時間 | 30秒 | 3-5分 | 5分(300秒) |
| メモリ使用量 | 256MB | 512MB | 10GB |
| /tmp使用量 | 30MB | 300MB | 10GB |
| 処理行数 | 5万行 | 50万行 | - |

### 2.2 コスト

**目標: 月額 $0（無料枠内）**

| サービス | 無料枠 | 想定使用量 | 備考 |
|---------|-------|-----------|-----|
| Lambda | 100万req/月 | 720req/月 (24×30日) | ✅ 安全 |
| Lambda GB秒 | 40万GB秒/月 | 3,600GB秒/月 | ✅ 安全 |
| S3 Storage | 5GB | 1GB | ✅ 安全 |
| S3 PUT | 2,000回/月 | 720回/月 | ✅ 安全 |
| DynamoDB Storage | 25GB | <1GB | ✅ 安全 |
| DynamoDB WCU | 25/秒 | <1/秒 | ✅ 安全 |

### 2.3 セキュリティ

**IAM最小権限設計:**

```
Lambda実行ロール権限:
✓ S3: GetObject (input-bucketのみ)
✓ DynamoDB: PutItem (stats-tableのみ)
✓ CloudWatch Logs: CreateLogGroup, CreateLogStream, PutLogEvents
✗ S3: DeleteObject (不要)
✗ DynamoDB: DeleteItem (不要)
✗ 他リソース: すべて拒否
```

**データ保護:**

```
- S3バケット: プライベート (出力バケット除く)
- DynamoDB: 保管時暗号化 (デフォルト有効)
- Lambda: 環境変数は暗号化しない (機密情報なし)
```

### 2.4 可用性・信頼性

- **Lambda:** AWSマネージドサービス、自動スケーリング
- **DynamoDB:** マルチAZ自動レプリケーション
- **S3:** 99.999999999% (イレブンナイン) の耐久性

**エラーハンドリング:**

- Lambda実行エラー → CloudWatch Logs に記録
- S3アクセスエラー → 例外スロー、リトライなし
- DynamoDB書き込みエラー → 例外スロー

---

## 3. 技術スタック

| レイヤー | 技術 | バージョン | 選定理由 |
|---------|-----|-----------|---------|
| **IaC** | Terraform | 1.6+ | 再現性、コードレビュー可能 |
| **言語** | Python | 3.11 | Lambda最新、高速 |
| **ライブラリ** | 標準ライブラリのみ | - | Lambda Layer不要、軽量 |
| | zipfile | - | ZIP解凍 |
| | csv | - | CSV解析 |
| | boto3 | - | DynamoDB書き込み |
| **DB** | DynamoDB | - | サーバーレス、無料枠大 |
| **可視化** | Chart.js | 4.x | CDN、AWS不要 |
| **CI/CD** | GitHub Actions | - | Terraform自動適用 |

### 3.1 重要な技術選定理由

**なぜpandasを使わない？**

```
pandas + numpy のサイズ: 100MB超
→ Lambda Layer必要
→ コールドスタート遅延
→ 標準ライブラリで十分処理可能
```

**なぜDynamoDB？**

```
vs RDS:
- サーバーレス (管理不要)
- 無料枠が大きい (25GB vs 20GB)
- オンデマンド課金 (待機コストゼロ)
```

**なぜEC2ではなくLambda？**

```
- 処理が断続的（1日24回のみ）
- サーバー維持コスト不要
- 自動スケーリング
- 無料枠が大きい
```

---

## 4. システム構成

```
┌─────────────────────────────────────────────────────────┐
│                    AWS Account                          │
│                                                         │
│  ┌───────────────────────────────────────────────┐    │
│  │  S3: syslog-input-bucket                      │    │
│  │  ├─ raw/2025-04-28/                           │    │
│  │  │   ├─ 00.zip  ← User upload                │    │
│  │  │   ├─ 10.zip                                │    │
│  │  │   └─ 23.zip                                │    │
│  │  └─ Event Notification → Lambda               │    │
│  └────────────┬──────────────────────────────────┘    │
│               │ S3:ObjectCreated:Put                   │
│               ↓                                         │
│  ┌───────────────────────────────────────────────┐    │
│  │  Lambda: syslog-parser-function               │    │
│  │  ┌─────────────────────────────────────────┐ │    │
│  │  │ Handler: lambda_function.lambda_handler │ │    │
│  │  │ Memory: 512MB                           │ │    │
│  │  │ Timeout: 300s                           │ │    │
│  │  │ Runtime: Python 3.11                    │ │    │
│  │  └─────────────────────────────────────────┘ │    │
│  │  処理内容:                                     │    │
│  │  1. S3からZIPダウンロード                      │    │
│  │  2. /tmpに解凍                                │    │
│  │  3. CSVパース                                 │    │
│  │  4. CRITICAL/WARNING抽出                      │    │
│  │  5. 時間別集計                                │    │
│  │  6. DynamoDB書き込み                          │    │
│  └────────────┬──────────────────────────────────┘    │
│               │ boto3.put_item()                       │
│               ↓                                         │
│  ┌───────────────────────────────────────────────┐    │
│  │  DynamoDB: syslog-hourly-stats                │    │
│  │  ┌─────────────────────────────────────────┐ │    │
│  │  │ PK: log_date (2025-04-28)              │ │    │
│  │  │ SK: hour (10:00)                       │ │    │
│  │  │ Attributes:                            │ │    │
│  │  │   - critical_count: 15                 │ │    │
│  │  │   - warning_count: 43                  │ │    │
│  │  │   - total_count: 58                    │ │    │
│  │  │   - hostname: srx-fw01                 │ │    │
│  │  │   - processed_at: 2025-04-28T...       │ │    │
│  │  │   - file_name: 10.zip                  │ │    │
│  │  └─────────────────────────────────────────┘ │    │
│  └────────────┬──────────────────────────────────┘    │
│               │ (Phase 3で読み取り)                    │
│               ↓                                         │
│  ┌───────────────────────────────────────────────┐    │
│  │  S3: syslog-output-bucket (静的ホスティング)   │    │
│  │  └─ dashboard/index.html                      │    │
│  │     └─ Chart.js でグラフ表示                   │    │
│  └───────────────────────────────────────────────┘    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 5. 実装フェーズ

### Phase 0: 準備 (30分)

- [ ] GitHubリポジトリ作成
- [ ] ディレクトリ構造作成
- [ ] サンプルデータ生成 (10MB)

### Phase 1: ローカル開発 (1-2日)

- [ ] Lambda関数実装
- [ ] ローカルテスト用スクリプト作成
- [ ] CSVパースロジック検証
- [ ] 時間別集計ロジック検証

### Phase 2: Terraform実装 (1-2日)

- [ ] S3バケット作成
- [ ] DynamoDBテーブル作成
- [ ] IAMロール作成（最小権限）
- [ ] Lambda関数デプロイ
- [ ] S3イベント通知設定

### Phase 3: E2Eテスト (1日)

- [ ] S3にZIPアップロード
- [ ] Lambda自動起動確認
- [ ] CloudWatch Logs確認
- [ ] DynamoDBデータ確認
- [ ] 24時間分処理成功

### Phase 4: 可視化 (1日)

- [ ] Option選択（S3静的ホスティング推奨）
- [ ] ダッシュボード実装
- [ ] グラフ表示確認

### Phase 5: CI/CD (1日)

- [ ] GitHub Actions設定
- [ ] terraform plan 自動実行
- [ ] terraform apply 自動実行（main merge時）

---

## 6. 完了条件

- [ ] S3にCSVアップロードで自動処理
- [ ] CRITICAL/WARNING行の正確な抽出
- [ ] 時間別集計の正常動作
- [ ] DynamoDBへの保存確認
- [ ] グラフでの可視化（Option選択後）
- [ ] Terraform apply で環境構築可能
- [ ] README に設計理由を記載
- [ ] 無料枠内での動作確認
- [ ] GitHub Actions でCI/CD動作

---

## 7. 面接アピールポイント

### 技術的強み

- IAM最小権限設計
- ファイル分割によるTerraform可読性
- エラーハンドリング実装
- CloudWatch Logsでの運用監視設計
- コスト最適化（無料枠内）

### 実務経験との接続

- Stadium City時代のSyslog処理実績
- Pythonログ解析（3時間→10分削減）
- インフラ視点でのアーキテクチャ選定
- 既存ツールの活用（ジェネレーター）

### 拡張性への配慮

- 「100MB超ならStep Functions検討」と説明可能
- 「本番ならKinesisも選択肢」と提案可能
- レイヤー分離の理解（インフラ/アプリ）

---

## 8. リスクと対策

| リスク | 影響 | 対策 |
|-------|-----|-----|
| Lambda実行時間超過 | 処理失敗 | ファイルサイズを10MBで検証 |
| DynamoDB書き込みエラー | データ欠損 | CloudWatch Logsで検知 |
| 無料枠超過 | 課金発生 | S3 Lifecycle設定、定期削除 |
| ZIP解凍失敗 | 処理失敗 | try-exceptでエラーハンドリング |

---

## 9. 用語集

| 用語 | 説明 |
|-----|-----|
| Syslog | システムログの標準プロトコル（RFC5424） |
| Severity | ログの重要度（CRITICAL, WARNING等） |
| DynamoDB | AWSのマネージドNoSQLデータベース |
| Lambda | AWSのサーバーレスコンピューティング |
| IaC | Infrastructure as Code、インフラのコード化 |
| Terraform | HashiCorp社のIaCツール |

---

**文書履歴:**

| バージョン | 日付 | 変更内容 | 作成者 |
|----------|-----|---------|-------|
| 1.0 | 2025-04-28 | 初版作成 | Sohey |
| 2.0 | 2025-04-28 | ジェネレーター対応版 | Sohey |