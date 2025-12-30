# Syslog Generator

Juniper ネットワーク機器から出力されるログを CSV 形式で生成し、ZIP 圧縮するツール。

## 機能

- **CSV 生成**: Juniper Syslog 形式の CSV ファイルを生成
- **ZIP 圧縮**: 生成した CSV を ZIP 形式で圧縮
- **時系列データ対応**: 指定日付の 00:00 〜 23:59 のログを生成
- **CRITICAL/WARNING フィルタ**: ランダムに重大度を割り当て

## 使用方法

### 基本的な実行方法

```bash
cd generator
python generate.py -r 2100 -o ../sample_data
```

### オプション

| オプション | 短縮系 | 説明 | デフォルト |
|----------|-------|------|----------|
| `--rows` | `-r` | CSV に生成するログ行数 | 2100 |
| `--output` | `-o` | 出力ディレクトリパス | `./output` |
| `--date` | `-d` | ログの日付 (YYYY-MM-DD) | 本日 |
| `--hostname` | `-H` | Juniper デバイスホスト名 | srx-fw01 |

### 実行例

```bash
# 2100 行のログを生成して sample_data に出力
python generate.py -r 2100 -o ../sample_data

# 2025-04-28 のログを生成（ログ開始日を指定）
python generate.py -r 2100 -d 2025-04-28 -o ../sample_data

# デバイス名を指定
python generate.py -r 2100 -H vsrx-prod01 -o ../sample_data
```

## 出力ファイル形式

### ZIP ファイル構成

```
sample_data/
├── 00.zip (2025-04-28 00:00 ～ 00:59 のログ)
├── 01.zip (2025-04-28 01:00 ～ 01:59 のログ)
├── ...
└── 23.zip (2025-04-28 23:00 ～ 23:59 のログ)
```

### CSV ファイル内容

各 ZIP には以下のカラムを持つ CSV が含まれます：

| カラム | 説明 | 例 |
|--------|------|-----|
| `Timestamp` | ログ発生時刻 (ISO 8601) | `2025-04-28T10:15:30Z` |
| `Hostname` | Juniper デバイス名 | `srx-fw01` |
| `Severity` | ログレベル (CRITICAL, WARNING, INFO) | `CRITICAL` |
| `Message` | ログメッセージ | `Interface ge-0/0/0 is down` |
| `Component` | Juniper コンポーネント名 | `j-daemon` |

### 重大度の分布

生成されたログの約 **10%** が CRITICAL/WARNING レベル、**90%** が INFO レベルです。

```
例：2100 行生成時
- CRITICAL: 約 105 行
- WARNING: 約 105 行
- INFO: 約 1890 行
計: 2100 行
```

## 環境要件

- Python 3.8 以上
- 標準ライブラリのみ（外部パッケージ不要）

## パフォーマンス

```
実行時間の目安：
- 2,100 行 → 約 0.5 秒
- 50,000 行 → 約 10 秒
```

## トラブルシューティング

### ファイルが生成されない

- 出力ディレクトリが存在するか確認
- ディレクトリの書き込み権限を確認

```bash
mkdir -p ../sample_data
```

### CSV が ZIP に入っていない

- ZIP ファイルの内容を確認

```bash
unzip -l ../sample_data/00.zip
```

## スクリプト実行ラッパー

簡単実行のため、プロジェクトルートから以下を実行：

```bash
bash scripts/generate_sample.sh
```

詳細は [scripts/README.md](../scripts/README.md) 参照。
