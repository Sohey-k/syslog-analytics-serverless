# Dashboard

Chart.js を使った Syslog Analytics ダッシュボード（**CloudFront HTTPS 配信対応**）

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

### AWS デプロイ（CloudFront + S3）

#### 1. ダッシュボードをS3にアップロード

```bash
# 環境変数設定
OUTPUT_BUCKET=$(cd terraform && terraform output -raw s3_output_bucket)

# index.htmlをアップロード
aws s3 cp dashboard/index.html s3://${OUTPUT_BUCKET}/
```

#### 2. CloudFrontキャッシュクリア（必要に応じて）

```bash
DIST_ID=$(cd terraform && terraform output -raw cloudfront_distribution_id)
aws cloudfront create-invalidation --distribution-id ${DIST_ID} --paths "/*"
```

#### 3. ブラウザでアクセス

```bash
# CloudFront URL取得
DASHBOARD_URL=$(cd terraform && terraform output -raw dashboard_url)
echo "🌐 ダッシュボード: ${DASHBOARD_URL}"

# ブラウザで開く（HTTPS）
open ${DASHBOARD_URL}
```

**特徴:**
- ✅ HTTPS で暗号化通信
- ✅ CloudFront CDN でグローバル配信
- ✅ S3 OAC でセキュアなアクセス制御
- ✅ 相対パス（`./data/*.json`）でデータ取得

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
