# Dashboard

Chart.js を使った Syslog Analytics ダッシュボード

## 📊 機能

### グラフ表示

1. **折れ線グラフ**: 時間別 CRITICAL/WARNING 推移
2. **ドーナツチャート**: CRITICAL/WARNING 比率
3. **棒グラフ**: 時間別合計ログ数

### 統計情報

- CRITICAL 合計件数
- WARNING 合計件数
- 総ログ数
- 時間別平均

## 🚀 使い方

### ローカルでプレビュー

```bash
# シンプルな HTTP サーバーで起動
cd dashboard
python3 -m http.server 8080

# ブラウザで開く
open http://localhost:8080
```

### AWS 認証設定

#### Option 1: Cognito Identity Pool（推奨）

1. **Cognito Identity Pool 作成**

```bash
aws cognito-identity create-identity-pool \
  --identity-pool-name SyslogAnalyticsDashboard \
  --allow-unauthenticated-identities \
  --region ap-northeast-1
```

2. **IAM ロール作成**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:Query"
      ],
      "Resource": "arn:aws:dynamodb:ap-northeast-1:*:table/syslog-hourly-stats"
    }
  ]
}
```

3. **index.html の修正**

```javascript
AWS.config.credentials = new AWS.CognitoIdentityCredentials({
    IdentityPoolId: 'ap-northeast-1:YOUR_ACTUAL_IDENTITY_POOL_ID'
});
```

#### Option 2: ローカル AWS CLI 認証（開発用）

ローカルで `~/.aws/credentials` がある場合、自動で認証されます。

```bash
aws configure
```

### S3 静的ホスティングでデプロイ

```bash
# 1. dashboard/ を S3 にアップロード
aws s3 sync dashboard/ s3://syslog-output-235270183100/ --acl public-read

# 2. S3 静的ホスティング有効化（Terraform で設定済み）
aws s3 website s3://syslog-output-235270183100/ \
  --index-document index.html

# 3. ブラウザで開く
open http://syslog-output-235270183100.s3-website-ap-northeast-1.amazonaws.com
```

## 📁 ファイル構成

```
dashboard/
├── index.html          ← メインHTML（Chart.js + AWS SDK）
└── README.md           ← このファイル
```

## 🎨 カスタマイズ

### グラフの色変更

```javascript
// index.html 内の色定義
borderColor: '#dc3545',      // CRITICAL: 赤
borderColor: '#ffc107',      // WARNING: 黄色
backgroundColor: '#667eea',  // 合計: 青紫
```

### 日付範囲の拡張

現在は1日分のみ対応。複数日対応には：

1. DynamoDB クエリを複数回実行
2. データを結合してグラフ化

```javascript
// 7日間分のデータ取得例
for (let i = 0; i < 7; i++) {
    const date = new Date();
    date.setDate(date.getDate() - i);
    const dateStr = date.toISOString().split('T')[0];
    // クエリ実行...
}
```

## 🐛 トラブルシューティング

### エラー: "データが見つかりません"

**原因**: 指定日付のデータが DynamoDB にない

**対処**:
```bash
# DynamoDB にデータがあるか確認
aws dynamodb query \
  --table-name syslog-hourly-stats \
  --key-condition-expression "log_date = :date" \
  --expression-attribute-values '{":date":{"S":"2025-04-28"}}'
```

### エラー: "AWS 認証情報を確認してください"

**原因**: Cognito Identity Pool ID が未設定

**対処**:
1. Cognito Identity Pool を作成
2. `index.html` の `YOUR_IDENTITY_POOL_ID` を実際の ID に置換

### グラフが表示されない

**原因**: Chart.js or AWS SDK の読み込み失敗

**対処**:
```javascript
// ブラウザコンソールで確認
console.log(typeof Chart);  // "function" であるべき
console.log(typeof AWS);    // "object" であるべき
```

## 📊 データフォーマット

DynamoDB から取得するデータ形式：

```json
{
  "Items": [
    {
      "log_date": "2025-04-28",
      "hour": "00:00",
      "critical_count": 15,
      "warning_count": 43,
      "hostname": "juniper-router-01"
    },
    {
      "log_date": "2025-04-28",
      "hour": "01:00",
      "critical_count": 12,
      "warning_count": 38,
      "hostname": "juniper-router-01"
    }
  ]
}
```

## 🔒 セキュリティ

### Cognito Identity Pool（推奨）

- 未認証アクセスを許可（ダッシュボード表示のみ）
- IAM ロールで DynamoDB Query のみ許可
- 書き込み権限は付与しない

### CORS 設定

S3 バケットに CORS 設定が必要：

```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["GET", "HEAD"],
    "AllowedOrigins": ["*"],
    "ExposeHeaders": []
  }
]
```

## 📈 パフォーマンス

- **初回読み込み**: ~2秒（DynamoDB クエリ + グラフ描画）
- **グラフ更新**: ~500ms（既存データの再描画）
- **推奨ブラウザ**: Chrome, Firefox, Safari, Edge（最新版）

## 🎓 学習ポイント

- **Chart.js**: JavaScript グラフライブラリの使い方
- **AWS SDK for JavaScript**: ブラウザから DynamoDB アクセス
- **Cognito Identity Pool**: 匿名認証の実装
- **S3 静的ホスティング**: シンプルな Web アプリデプロイ

---

**Phase 2 完了後**: このダッシュボードを S3 で公開し、URL を共有可能！
