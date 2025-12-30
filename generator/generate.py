import os
import csv
import random
import zipfile
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# デフォルト設定
# プロジェクトルート（このファイルの1つ上）にsource_logsを作成
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = str(BASE_DIR / "source_logs")

DEFAULT_DATE = datetime(2025, 4, 28)
DEFAULT_HOSTNAME = "srx-fw01"
DEFAULT_ROWS_PER_HOUR = 5000
DEFAULT_THREAT_RATIO = 0.1

# Juniper SRX風のアプリケーション名とメッセージ
JUNOS_APPS = [
    "RT_FLOW",  # セッションログ
    "RT_SCREEN",  # 脅威検知
    "RT_IDP",  # IDP/IPS
    "UI_AUTH",  # 認証
    "SSHD",  # SSH
    "RT_UTM",  # UTM関連
]

# Juniper風の通常ログメッセージ
NORMAL_MESSAGES = {
    "RT_FLOW": [
        "RT_FLOW_SESSION_CREATE: session created",
        "RT_FLOW_SESSION_CLOSE: session closed",
        "RT_FLOW_SESSION_DENY: session denied",
    ],
    "UI_AUTH": [
        "UI_LOGIN_EVENT: User logged in via ssh",
        "UI_LOGOUT_EVENT: User logged out",
        "UI_COMMIT: Commit complete",
    ],
    "SSHD": [
        "SSHD_LOGIN_SUCCESS: Password authentication succeeded",
        "SSHD_LOGOUT_INFO: Closed connection",
    ],
    "RT_UTM": [
        "RT_UTM_WEBFILTER_BLOCKED: URL blocked by policy",
        "RT_UTM_AV_SCAN_OK: No virus detected",
    ],
}

# Juniper風の脅威ログメッセージ
THREAT_MESSAGES = {
    "RT_SCREEN": [
        "RT_SCREEN_TCP: SYN flood attack detected",
        "RT_SCREEN_IP: IP spoofing detected",
        "RT_SCREEN_ICMP: ICMP flood detected",
        "RT_SCREEN_UDP: UDP flood detected",
    ],
    "RT_IDP": [
        "RT_IDP_ATTACK_LOG: SQL injection attack detected",
        "RT_IDP_ATTACK_LOG: SSH brute force attack detected",
        "RT_IDP_ATTACK_LOG: Port scan detected",
        "RT_IDP_ATTACK_LOG: Malware signature match",
    ],
    "RT_FLOW": ["RT_FLOW_SESSION_DENY: Policy deny"],
}

# RFC5424準拠のSeverityレベル
SEVERITIES = {
    "EMERGENCY": 0,
    "ALERT": 1,
    "CRITICAL": 2,
    "ERROR": 3,
    "WARNING": 4,
    "NOTICE": 5,
    "INFO": 6,
    "DEBUG": 7,
}


class JuniperSyslogGenerator:
    def __init__(self, output_dir, date, hostname, rows_per_hour, threat_ratio):
        self.output_dir = Path(output_dir)
        self.date = date
        self.hostname = hostname
        self.rows_per_hour = rows_per_hour
        self.threat_ratio = threat_ratio

        # --- ディレクトリの条件分岐処理 ---
        if self.output_dir.exists():
            print(
                f"INFO: Output directory '{self.output_dir}' already exists. Using it."
            )
        else:
            print(f"INFO: Creating new directory '{self.output_dir}'...")
            # parents=True: 親ディレクトリも必要なら作る, exist_ok=True: 作成直前に他で作られてもエラーにしない
            self.output_dir.mkdir(parents=True, exist_ok=True)
        # --------------------------------

    def random_timestamp(self, base_time):
        """ランダムなタイムスタンプ生成（秒単位でランダム）"""
        offset = random.randint(0, 3599)
        return (base_time + timedelta(seconds=offset)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def random_private_ip(self):
        """プライベートIPアドレスをランダム生成"""
        choice = random.randint(1, 3)
        if choice == 1:
            return f"10.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
        elif choice == 2:
            return f"172.{random.randint(16,31)}.{random.randint(0,255)}.{random.randint(1,254)}"
        else:
            return f"192.168.{random.randint(0,255)}.{random.randint(1,254)}"

    def random_global_ip(self, max_attempts=100):
        """グローバルIPアドレスをランダム生成"""
        for _ in range(max_attempts):
            oct1 = random.randint(1, 223)
            if oct1 in [10, 127]:
                continue
            oct2 = random.randint(0, 255)
            if oct1 == 172 and 16 <= oct2 <= 31:
                continue
            if oct1 == 192 and oct2 == 168:
                continue
            oct3 = random.randint(0, 255)
            oct4 = random.randint(1, 254)
            return f"{oct1}.{oct2}.{oct3}.{oct4}"
        # フォールバック（滅多に到達しない）
        return "8.8.8.8"

    def random_dst_ip(self):
        """宛先IPをプライベート6:グローバル4の比率で生成"""
        if random.random() < 0.6:
            return self.random_private_ip()
        else:
            return self.random_global_ip()

    def generate_log_row(self, base_time):
        """1行のログデータを生成"""
        timestamp = self.random_timestamp(base_time)
        src_ip = self.random_private_ip()
        dst_ip = self.random_dst_ip()
        src_port = random.randint(1024, 65535)
        dst_port = random.choice([22, 80, 443, 53, 123, 8080])
        protocol = random.choice(["tcp", "udp", "icmp"])

        # 脅威ログか通常ログかを判定
        if random.random() < self.threat_ratio:
            appname = random.choice(["RT_SCREEN", "RT_IDP"])
            severity = "CRITICAL" if random.random() < 0.3 else "WARNING"
            message = random.choice(THREAT_MESSAGES[appname])
            log_type = "THREAT"
        else:
            appname = random.choice(list(NORMAL_MESSAGES.keys()))
            severity = random.choice(["INFO", "NOTICE"])
            message = random.choice(NORMAL_MESSAGES[appname])
            log_type = "NORMAL"

        severity_level = SEVERITIES[severity]

        # Juniper風のログフォーマット（SeverityLevel/Severity情報を本文に追加）
        full_message = (
            f"{message} {src_ip}/{src_port} > {dst_ip}/{dst_port} protocol={protocol} "
            f"SeverityLevel={severity_level} Severity={severity}"
        )

        return [
            timestamp,
            self.hostname,
            appname,
            severity_level,
            severity,
            log_type,
            full_message,
        ]

    def create_hourly_log(self, hour):
        """1時間分のログファイルを生成してZIP圧縮"""
        try:
            base_time = self.date + timedelta(hours=hour)
            hour_str = f"{hour:02d}"
            csv_path = self.output_dir / f"{hour_str}.csv"

            with open(
                csv_path, "w", newline="", encoding="utf-8", buffering=1024 * 1024
            ) as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(
                    [
                        "Timestamp",
                        "Hostname",
                        "AppName",
                        "SeverityLevel",
                        "Severity",
                        "LogType",
                        "Message",
                    ]
                )

                # バッチ処理で効率化
                rows = [
                    self.generate_log_row(base_time) for _ in range(self.rows_per_hour)
                ]
                writer.writerows(rows)

            # ZIP圧縮
            zip_path = self.output_dir / f"{hour_str}.zip"
            with zipfile.ZipFile(
                zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
            ) as zipf:
                zipf.write(csv_path, arcname=f"{hour_str}.csv")

            os.remove(csv_path)
            return True

        except IOError as e:
            print(f"Error creating hourly log for hour {hour}: {e}")
            return False

    def generate(self):
        """メイン処理：24時間分のログを生成"""
        print(
            f"Generating Juniper-style syslog for {self.date.strftime('%Y-%m-%d')}..."
        )
        print(f"Target Path: {self.output_dir}")
        print(f"Hostname: {self.hostname}")
        print(f"Rows per hour: {self.rows_per_hour:,}")
        print(f"Threat ratio: {self.threat_ratio*100:.1f}%")
        print("-" * 60)

        for hour in range(24):
            if self.create_hourly_log(hour):
                print(f"✓ Hour {hour:02d}:00 completed")
            else:
                print(f"✗ Hour {hour:02d}:00 failed")

        print("-" * 60)
        print(f"Done! 24 ZIP files are ready in: {self.output_dir}")
        print("You can now run run.py immediately.")


def main():
    parser = argparse.ArgumentParser(
        description="Generate Juniper-style syslog test data (v2)"
    )
    parser.add_argument(
        "-o",
        "--output",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "-d",
        "--date",
        default=DEFAULT_DATE.strftime("%Y-%m-%d"),
        help=f"Log date in YYYY-MM-DD format (default: {DEFAULT_DATE.strftime('%Y-%m-%d')})",
    )
    parser.add_argument(
        "-H",
        "--hostname",
        default=DEFAULT_HOSTNAME,
        help=f"Hostname for logs (default: {DEFAULT_HOSTNAME})",
    )
    parser.add_argument(
        "-r",
        "--rows",
        type=int,
        default=DEFAULT_ROWS_PER_HOUR,
        help=f"Rows per hour (default: {DEFAULT_ROWS_PER_HOUR})",
    )
    parser.add_argument(
        "-t",
        "--threat-ratio",
        type=float,
        default=DEFAULT_THREAT_RATIO,
        help=f"Threat log ratio 0.0-1.0 (default: {DEFAULT_THREAT_RATIO})",
    )

    args = parser.parse_args()

    try:
        log_date = datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print("Error: Invalid date format. Use YYYY-MM-DD")
        return

    if not 0.0 <= args.threat_ratio <= 1.0:
        print("Error: Threat ratio must be between 0.0 and 1.0")
        return

    generator = JuniperSyslogGenerator(
        output_dir=args.output,
        date=log_date,
        hostname=args.hostname,
        rows_per_hour=args.rows,
        threat_ratio=args.threat_ratio,
    )

    generator.generate()


if __name__ == "__main__":
    main()