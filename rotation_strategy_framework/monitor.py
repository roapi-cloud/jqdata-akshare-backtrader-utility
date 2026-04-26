# -*- coding: utf-8 -*-
"""
监控与日志系统: 多层次日志、实时监控面板、报警系统、报告生成、性能监控、日志持久化

核心类:
- LogConfig: 日志配置 (level, file_path, rotation, format)
- Logger: 增强日志器 (结构化日志、上下文追踪)
- MonitorDashboard: 监控面板 (实时指标、图表数据)
- AlertManager: 报警管理器 (规则、通知渠道、静默期)
- ReportGenerator: 报告生成器 (日报/周报/月报)
- PerformanceMonitor: 性能监控 (CPU/内存/延迟)

报警规则:
- 策略回撤超过阈值
- 组合回撤超过阈值
- 单日亏损超过阈值
- 订单失败
- 数据异常
- 系统资源不足

报告内容:
- 日报: 当日交易、持仓变化、盈亏、风险指标
- 周报: 周度表现、策略排名变化、风险趋势
- 月报: 月度总结、策略调整建议、市场回顾
"""

import logging
import datetime
import json
import os
import sys
import time
import threading
import traceback
import psutil
import sqlite3
import smtplib
from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Tuple, Any, Callable, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import deque, defaultdict
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# ---------------------------------------------------------------------------
# 日志级别枚举
# ---------------------------------------------------------------------------
class LogLevel(Enum):
    """日志级别"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# ---------------------------------------------------------------------------
# 报警渠道
# ---------------------------------------------------------------------------
class AlertChannel(Enum):
    """报警通知渠道"""

    CONSOLE = "console"
    EMAIL = "email"
    WECHAT = "wechat"


# ---------------------------------------------------------------------------
# 报警类型
# ---------------------------------------------------------------------------
class AlertType(Enum):
    """报警类型"""

    STRATEGY_DRAWDOWN = "strategy_drawdown"
    PORTFOLIO_DRAWDOWN = "portfolio_drawdown"
    DAILY_LOSS = "daily_loss"
    ORDER_FAILURE = "order_failure"
    DATA_ANOMALY = "data_anomaly"
    SYSTEM_RESOURCE = "system_resource"


# ---------------------------------------------------------------------------
# 报告周期
# ---------------------------------------------------------------------------
class ReportPeriod(Enum):
    """报告周期"""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


# ---------------------------------------------------------------------------
# 日志持久化目标
# ---------------------------------------------------------------------------
class LogStorage(Enum):
    """日志存储目标"""

    FILE = "file"
    DATABASE = "database"
    BOTH = "both"


# ---------------------------------------------------------------------------
# LogConfig: 日志配置
# ---------------------------------------------------------------------------
@dataclass
class LogConfig:
    """
    日志配置

    Attributes:
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)
        file_path: 日志文件路径
        rotation: 日志轮转大小 (MB)，0 表示不轮转
        backup_count: 保留的备份文件数
        format: 日志格式字符串
        console_output: 是否输出到控制台
        storage: 持久化目标 (FILE/DATABASE/BOTH)
        db_path: 数据库路径 (当 storage 包含 DATABASE 时使用)
        db_table: 数据库表名
        context_fields: 需要记录的上下文字段
        max_context_history: 上下文历史最大长度
    """

    level: LogLevel = LogLevel.INFO
    file_path: str = "logs/monitor.log"
    rotation: float = 50.0
    backup_count: int = 10
    format: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    console_output: bool = True
    storage: LogStorage = LogStorage.FILE
    db_path: str = "logs/monitor.db"
    db_table: str = "log_entries"
    context_fields: List[str] = field(
        default_factory=lambda: ["strategy", "symbol", "order_id"]
    )
    max_context_history: int = 10000

    def __post_init__(self):
        if self.rotation < 0:
            raise ValueError("rotation 不能为负")
        if self.backup_count < 0:
            raise ValueError("backup_count 不能为负")

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["level"] = self.level.value
        d["storage"] = self.storage.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LogConfig":
        level = LogLevel(d.get("level", "INFO"))
        storage = LogStorage(d.get("storage", "file"))
        return cls(
            level=level,
            file_path=d.get("file_path", "logs/monitor.log"),
            rotation=d.get("rotation", 50.0),
            backup_count=d.get("backup_count", 10),
            format=d.get(
                "format", "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
            ),
            console_output=d.get("console_output", True),
            storage=storage,
            db_path=d.get("db_path", "logs/monitor.db"),
            db_table=d.get("db_table", "log_entries"),
            context_fields=d.get("context_fields", ["strategy", "symbol", "order_id"]),
            max_context_history=d.get("max_context_history", 10000),
        )


# ---------------------------------------------------------------------------
# LogEntry: 结构化日志条目
# ---------------------------------------------------------------------------
@dataclass
class LogEntry:
    """
    结构化日志条目

    Attributes:
        timestamp: 日志时间
        level: 日志级别
        logger_name: 日志器名称
        message: 日志消息
        context: 上下文信息
        trace_id: 追踪ID
        span_id: 跨度ID
        extra: 额外字段
    """

    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    level: LogLevel = LogLevel.INFO
    logger_name: str = ""
    message: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    trace_id: str = ""
    span_id: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "logger_name": self.logger_name,
            "message": self.message,
            "context": self.context,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
        }
        if self.extra:
            d["extra"] = self.extra
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LogEntry":
        return cls(
            timestamp=datetime.datetime.fromisoformat(d["timestamp"]),
            level=LogLevel(d.get("level", "INFO")),
            logger_name=d.get("logger_name", ""),
            message=d.get("message", ""),
            context=d.get("context", {}),
            trace_id=d.get("trace_id", ""),
            span_id=d.get("span_id", ""),
            extra=d.get("extra", {}),
        )

    def __repr__(self) -> str:
        ctx = f" | context={self.context}" if self.context else ""
        return f"LogEntry({self.level.value}, {self.logger_name}, {self.message}{ctx})"


# ---------------------------------------------------------------------------
# Logger: 增强日志器
# ---------------------------------------------------------------------------
class Logger:
    """
    增强日志器

    支持结构化日志、上下文追踪、多目标持久化 (文件+数据库)。

    Attributes:
        config: 日志配置
        _entries: 日志条目缓存
        _lock: 线程锁
        _db_conn: 数据库连接
        _trace_counter: 追踪ID计数器
        _context_stack: 上下文栈 (线程局部)
    """

    _instances: Dict[str, "Logger"] = {}
    _global_context: Dict[str, Any] = {}

    def __init__(self, name: str = "monitor", config: Optional[LogConfig] = None):
        self.name = name
        self.config = config or LogConfig()
        self._entries: deque = deque(maxlen=self.config.max_context_history)
        self._lock = threading.Lock()
        self._db_conn: Optional[sqlite3.Connection] = None
        self._trace_counter = 0
        self._context_stack: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        self._python_logger = logging.getLogger(name)
        self._python_logger.setLevel(self._to_python_level(self.config.level))
        self._setup_handlers()
        self._init_database()

    @classmethod
    def get_instance(
        cls, name: str = "monitor", config: Optional[LogConfig] = None
    ) -> "Logger":
        if name not in cls._instances:
            cls._instances[name] = cls(name, config)
        return cls._instances[name]

    @classmethod
    def set_global_context(cls, key: str, value: Any) -> None:
        cls._global_context[key] = value

    @classmethod
    def clear_global_context(cls) -> None:
        cls._global_context.clear()

    def _to_python_level(self, level: LogLevel) -> int:
        mapping = {
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.CRITICAL: logging.CRITICAL,
        }
        return mapping.get(level, logging.INFO)

    def _setup_handlers(self) -> None:
        if not self._python_logger.handlers:
            fmt = logging.Formatter(self.config.format)

            if self.config.console_output:
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setLevel(self._to_python_level(self.config.level))
                console_handler.setFormatter(fmt)
                self._python_logger.addHandler(console_handler)

            if self.config.storage in (LogStorage.FILE, LogStorage.BOTH):
                log_dir = os.path.dirname(self.config.file_path)
                if log_dir and not os.path.exists(log_dir):
                    os.makedirs(log_dir, exist_ok=True)

                if self.config.rotation > 0:
                    from logging.handlers import RotatingFileHandler

                    max_bytes = int(self.config.rotation * 1024 * 1024)
                    file_handler = RotatingFileHandler(
                        self.config.file_path,
                        maxBytes=max_bytes,
                        backupCount=self.config.backup_count,
                        encoding="utf-8",
                    )
                else:
                    file_handler = logging.FileHandler(
                        self.config.file_path, encoding="utf-8"
                    )

                file_handler.setLevel(self._to_python_level(self.config.level))
                file_handler.setFormatter(fmt)
                self._python_logger.addHandler(file_handler)

    def _init_database(self) -> None:
        if self.config.storage not in (LogStorage.DATABASE, LogStorage.BOTH):
            return

        db_dir = os.path.dirname(self.config.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        try:
            self._db_conn = sqlite3.connect(
                self.config.db_path, check_same_thread=False
            )
            self._db_conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.config.db_table} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    logger_name TEXT NOT NULL,
                    message TEXT NOT NULL,
                    context TEXT,
                    trace_id TEXT,
                    span_id TEXT,
                    extra TEXT
                )
                """
            )
            self._db_conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{self.config.db_table}_timestamp "
                f"ON {self.config.db_table}(timestamp)"
            )
            self._db_conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{self.config.db_table}_level "
                f"ON {self.config.db_table}(level)"
            )
            self._db_conn.commit()
        except Exception as e:
            self._python_logger.error(f"数据库初始化失败: {e}")
            self._db_conn = None

    def _get_thread_context(self) -> Dict[str, Any]:
        thread_id = threading.get_ident()
        ctx = dict(self._global_context)
        for stack_ctx in self._context_stack.get(thread_id, []):
            ctx.update(stack_ctx)
        return ctx

    def _generate_trace_id(self) -> str:
        self._trace_counter += 1
        return f"trace-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{self._trace_counter:06d}"

    def log(
        self,
        level: LogLevel,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> LogEntry:
        """
        记录结构化日志

        Args:
            level: 日志级别
            message: 日志消息
            context: 上下文信息
            trace_id: 追踪ID (自动生成)
            span_id: 跨度ID
            extra: 额外字段

        Returns:
            LogEntry
        """
        if trace_id is None:
            trace_id = self._generate_trace_id()

        thread_ctx = self._get_thread_context()
        merged_ctx = {**thread_ctx}
        if context:
            merged_ctx.update(context)

        entry = LogEntry(
            timestamp=datetime.datetime.now(),
            level=level,
            logger_name=self.name,
            message=message,
            context=merged_ctx,
            trace_id=trace_id,
            span_id=span_id or "",
            extra=extra or {},
        )

        with self._lock:
            self._entries.append(entry)

        log_msg = message
        if merged_ctx:
            ctx_str = " | ".join(f"{k}={v}" for k, v in merged_ctx.items())
            log_msg = f"{message} [{ctx_str}]"

        python_level = self._to_python_level(level)
        self._python_logger.log(python_level, log_msg)

        self._persist_to_db(entry)

        return entry

    def _persist_to_db(self, entry: LogEntry) -> None:
        if self._db_conn is None:
            return

        try:
            self._db_conn.execute(
                f"""
                INSERT INTO {self.config.db_table}
                (timestamp, level, logger_name, message, context, trace_id, span_id, extra)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.timestamp.isoformat(),
                    entry.level.value,
                    entry.logger_name,
                    entry.message,
                    json.dumps(entry.context, ensure_ascii=False, default=str),
                    entry.trace_id,
                    entry.span_id,
                    json.dumps(entry.extra, ensure_ascii=False, default=str),
                ),
            )
            self._db_conn.commit()
        except Exception as e:
            self._python_logger.error(f"日志写入数据库失败: {e}")

    def debug(self, message: str, **kwargs) -> LogEntry:
        return self.log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs) -> LogEntry:
        return self.log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs) -> LogEntry:
        return self.log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs) -> LogEntry:
        return self.log(LogLevel.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs) -> LogEntry:
        return self.log(LogLevel.CRITICAL, message, **kwargs)

    def exception(self, message: str, **kwargs) -> LogEntry:
        tb = traceback.format_exc()
        return self.log(
            LogLevel.ERROR,
            f"{message}\n{tb}",
            extra={"traceback": tb},
            **kwargs,
        )

    def push_context(self, ctx: Dict[str, Any]) -> None:
        thread_id = threading.get_ident()
        self._context_stack[thread_id].append(ctx)

    def pop_context(self) -> None:
        thread_id = threading.get_ident()
        if self._context_stack.get(thread_id):
            self._context_stack[thread_id].pop()

    def get_entries(
        self,
        since: Optional[datetime.datetime] = None,
        level: Optional[LogLevel] = None,
        limit: int = 100,
    ) -> List[LogEntry]:
        results = list(self._entries)
        if since:
            results = [e for e in results if e.timestamp >= since]
        if level:
            results = [e for e in results if e.level == level]
        return results[-limit:]

    def query_db(
        self,
        since: Optional[datetime.datetime] = None,
        until: Optional[datetime.datetime] = None,
        level: Optional[LogLevel] = None,
        logger_name: Optional[str] = None,
        trace_id: Optional[str] = None,
        limit: int = 1000,
    ) -> List[LogEntry]:
        if self._db_conn is None:
            return []

        conditions = []
        params = []

        if since:
            conditions.append("timestamp >= ?")
            params.append(since.isoformat())
        if until:
            conditions.append("timestamp <= ?")
            params.append(until.isoformat())
        if level:
            conditions.append("level = ?")
            params.append(level.value)
        if logger_name:
            conditions.append("logger_name = ?")
            params.append(logger_name)
        if trace_id:
            conditions.append("trace_id = ?")
            params.append(trace_id)

        where = " AND ".join(conditions) if conditions else "1=1"
        query = f"""
            SELECT timestamp, level, logger_name, message, context, trace_id, span_id, extra
            FROM {self.config.db_table}
            WHERE {where}
            ORDER BY timestamp DESC
            LIMIT ?
        """
        params.append(limit)

        try:
            cursor = self._db_conn.execute(query, params)
            entries = []
            for row in cursor.fetchall():
                entries.append(
                    LogEntry(
                        timestamp=datetime.datetime.fromisoformat(row[0]),
                        level=LogLevel(row[1]),
                        logger_name=row[2],
                        message=row[3],
                        context=json.loads(row[4]) if row[4] else {},
                        trace_id=row[5] or "",
                        span_id=row[6] or "",
                        extra=json.loads(row[7]) if row[7] else {},
                    )
                )
            return entries
        except Exception as e:
            self._python_logger.error(f"数据库查询失败: {e}")
            return []

    def close(self) -> None:
        if self._db_conn:
            self._db_conn.close()
            self._db_conn = None

    def __del__(self):
        self.close()


# ---------------------------------------------------------------------------
# AlertRule: 报警规则
# ---------------------------------------------------------------------------
@dataclass
class AlertRule:
    """
    报警规则

    Attributes:
        rule_id: 规则唯一标识
        name: 规则名称
        alert_type: 报警类型
        condition: 条件表达式 (callable, 接收 metrics 返回 bool)
        channels: 通知渠道列表
        severity: 严重程度 (1-5)
        message_template: 消息模板 (支持 {key} 占位符)
        cooldown_seconds: 静默期 (秒)
        enabled: 是否启用
        metadata: 额外元数据
    """

    rule_id: str = ""
    name: str = ""
    alert_type: AlertType = AlertType.STRATEGY_DRAWDOWN
    condition: Optional[Callable[[Dict[str, Any]], bool]] = None
    channels: List[AlertChannel] = field(default_factory=lambda: [AlertChannel.CONSOLE])
    severity: int = 3
    message_template: str = ""
    cooldown_seconds: float = 300.0
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.rule_id:
            self.rule_id = f"rule-{self.alert_type.value}-{id(self)}"
        if not self.name:
            self.name = self.rule_id
        if not self.message_template:
            self.message_template = f"[{self.alert_type.value}] {self.name} 触发报警"

    def evaluate(self, metrics: Dict[str, Any]) -> bool:
        if not self.enabled or self.condition is None:
            return False
        try:
            return self.condition(metrics)
        except Exception:
            return False

    def format_message(self, metrics: Dict[str, Any]) -> str:
        try:
            return self.message_template.format(**metrics)
        except (KeyError, ValueError):
            return self.message_template

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "alert_type": self.alert_type.value,
            "channels": [c.value for c in self.channels],
            "severity": self.severity,
            "message_template": self.message_template,
            "cooldown_seconds": self.cooldown_seconds,
            "enabled": self.enabled,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# AlertRecord: 报警记录
# ---------------------------------------------------------------------------
@dataclass
class AlertRecord:
    """
    报警记录

    Attributes:
        record_id: 记录ID
        rule_id: 触发规则ID
        alert_type: 报警类型
        message: 报警消息
        severity: 严重程度
        channels_sent: 已发送的渠道
        timestamp: 报警时间
        metrics_snapshot: 触发时的指标快照
        resolved: 是否已解决
        resolved_at: 解决时间
    """

    record_id: str = ""
    rule_id: str = ""
    alert_type: AlertType = AlertType.STRATEGY_DRAWDOWN
    message: str = ""
    severity: int = 3
    channels_sent: List[str] = field(default_factory=list)
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    metrics_snapshot: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[datetime.datetime] = None

    def __post_init__(self):
        if not self.record_id:
            self.record_id = f"alert-{self.timestamp.strftime('%Y%m%d%H%M%S')}-{id(self) % 10000:04d}"

    def resolve(self) -> None:
        self.resolved = True
        self.resolved_at = datetime.datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "rule_id": self.rule_id,
            "alert_type": self.alert_type.value,
            "message": self.message,
            "severity": self.severity,
            "channels_sent": self.channels_sent,
            "timestamp": self.timestamp.isoformat(),
            "metrics_snapshot": self.metrics_snapshot,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }

    def __repr__(self) -> str:
        status = "RESOLVED" if self.resolved else "ACTIVE"
        return (
            f"AlertRecord({self.alert_type.value}, severity={self.severity}, {status})"
        )


# ---------------------------------------------------------------------------
# 通知渠道基类
# ---------------------------------------------------------------------------
class NotificationChannel(ABC):
    """通知渠道基类"""

    @abstractmethod
    def send(self, message: str, severity: int, **kwargs) -> bool:
        pass

    @property
    @abstractmethod
    def channel_type(self) -> AlertChannel:
        pass


# ---------------------------------------------------------------------------
# ConsoleChannel: 控制台通知
# ---------------------------------------------------------------------------
class ConsoleChannel(NotificationChannel):
    """控制台通知渠道"""

    @property
    def channel_type(self) -> AlertChannel:
        return AlertChannel.CONSOLE

    def send(self, message: str, severity: int, **kwargs) -> bool:
        prefix = {
            1: "[INFO]",
            2: "[WARN]",
            3: "[ALERT]",
            4: "[CRITICAL]",
            5: "[EMERGENCY]",
        }.get(severity, "[ALERT]")
        print(f"{prefix} {message}")
        return True


# ---------------------------------------------------------------------------
# EmailChannel: 邮件通知
# ---------------------------------------------------------------------------
class EmailChannel(NotificationChannel):
    """
    邮件通知渠道

    Attributes:
        smtp_server: SMTP 服务器地址
        smtp_port: SMTP 端口
        username: 发件人邮箱
        password: 邮箱密码/授权码
        recipients: 收件人列表
        use_tls: 是否使用 TLS
    """

    def __init__(
        self,
        smtp_server: str = "smtp.example.com",
        smtp_port: int = 587,
        username: str = "",
        password: str = "",
        recipients: Optional[List[str]] = None,
        use_tls: bool = True,
    ):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.recipients = recipients or []
        self.use_tls = use_tls

    @property
    def channel_type(self) -> AlertChannel:
        return AlertChannel.EMAIL

    def send(self, message: str, severity: int, **kwargs) -> bool:
        if not self.recipients:
            return False

        subject = kwargs.get(
            "subject",
            f"[监控系统] {'紧急' if severity >= 4 else '警告' if severity >= 3 else '通知'} 报警",
        )

        try:
            msg = MIMEMultipart()
            msg["From"] = self.username
            msg["To"] = ", ".join(self.recipients)
            msg["Subject"] = subject

            body = f"""
报警时间: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
严重程度: {severity}/5
报警内容:
{message}

---
此邮件由监控系统自动生成，请勿回复。
"""
            msg.attach(MIMEText(body, "plain", "utf-8"))

            if self.use_tls:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)

            server.login(self.username, self.password)
            server.sendmail(self.username, self.recipients, msg.as_string())
            server.quit()
            return True
        except Exception as e:
            logging.getLogger(__name__).error(f"邮件发送失败: {e}")
            return False


# ---------------------------------------------------------------------------
# WechatChannel: 微信通知
# ---------------------------------------------------------------------------
class WechatChannel(NotificationChannel):
    """
    微信通知渠道 (企业微信机器人)

    Attributes:
        webhook_url: 企业微信机器人 Webhook URL
    """

    def __init__(self, webhook_url: str = ""):
        self.webhook_url = webhook_url

    @property
    def channel_type(self) -> AlertChannel:
        return AlertChannel.WECHAT

    def send(self, message: str, severity: int, **kwargs) -> bool:
        if not self.webhook_url:
            return False

        import urllib.request
        import urllib.error

        severity_text = {1: "通知", 2: "警告", 3: "报警", 4: "严重", 5: "紧急"}.get(
            severity, "报警"
        )

        payload = {
            "msgtype": "text",
            "text": {
                "content": f"[{severity_text}] 监控系统报警\n时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{message}"
            },
        }

        try:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result.get("errcode", -1) == 0
        except Exception as e:
            logging.getLogger(__name__).error(f"微信通知发送失败: {e}")
            return False


# ---------------------------------------------------------------------------
# AlertManager: 报警管理器
# ---------------------------------------------------------------------------
class AlertManager:
    """
    报警管理器

    管理报警规则、通知渠道、静默期。

    Attributes:
        rules: 报警规则字典 {rule_id: AlertRule}
        channels: 通知渠道字典 {AlertChannel: NotificationChannel}
        records: 报警记录列表
        cooldowns: 静默期记录 {rule_id: last_alert_time}
        logger: 日志器
    """

    def __init__(self, logger: Optional[Logger] = None):
        self.rules: Dict[str, AlertRule] = {}
        self.channels: Dict[AlertChannel, NotificationChannel] = {
            AlertChannel.CONSOLE: ConsoleChannel(),
        }
        self.records: List[AlertRecord] = []
        self.cooldowns: Dict[str, datetime.datetime] = {}
        self.logger = logger or Logger.get_instance("alert_manager")
        self._lock = threading.Lock()
        self._alert_callbacks: List[Callable[[AlertRecord], None]] = []
        self._setup_default_rules()

    def _setup_default_rules(self) -> None:
        self.add_rule(
            AlertRule(
                name="策略回撤超限",
                alert_type=AlertType.STRATEGY_DRAWDOWN,
                condition=lambda m: (
                    m.get("strategy_drawdown", 0)
                    > m.get("strategy_drawdown_threshold", 0.10)
                ),
                channels=[AlertChannel.CONSOLE],
                severity=3,
                message_template="策略 {strategy_name} 回撤 {strategy_drawdown:.2%} 超过阈值 {strategy_drawdown_threshold:.2%}",
                cooldown_seconds=600,
            )
        )

        self.add_rule(
            AlertRule(
                name="组合回撤超限",
                alert_type=AlertType.PORTFOLIO_DRAWDOWN,
                condition=lambda m: (
                    m.get("portfolio_drawdown", 0)
                    > m.get("portfolio_drawdown_threshold", 0.15)
                ),
                channels=[AlertChannel.CONSOLE],
                severity=4,
                message_template="组合回撤 {portfolio_drawdown:.2%} 超过阈值 {portfolio_drawdown_threshold:.2%}",
                cooldown_seconds=300,
            )
        )

        self.add_rule(
            AlertRule(
                name="单日亏损超限",
                alert_type=AlertType.DAILY_LOSS,
                condition=lambda m: (
                    m.get("daily_loss", 0) > m.get("daily_loss_threshold", 0.05)
                ),
                channels=[AlertChannel.CONSOLE],
                severity=3,
                message_template="单日亏损 {daily_loss:.2%} 超过阈值 {daily_loss_threshold:.2%}",
                cooldown_seconds=600,
            )
        )

        self.add_rule(
            AlertRule(
                name="订单失败",
                alert_type=AlertType.ORDER_FAILURE,
                condition=lambda m: (
                    m.get("order_failure_count", 0)
                    > m.get("order_failure_threshold", 3)
                ),
                channels=[AlertChannel.CONSOLE],
                severity=3,
                message_template="订单失败次数 {order_failure_count} 超过阈值 {order_failure_threshold}",
                cooldown_seconds=300,
            )
        )

        self.add_rule(
            AlertRule(
                name="数据异常",
                alert_type=AlertType.DATA_ANOMALY,
                condition=lambda m: m.get("data_anomaly", False),
                channels=[AlertChannel.CONSOLE],
                severity=2,
                message_template="检测到数据异常: {data_anomaly_message}",
                cooldown_seconds=1800,
            )
        )

        self.add_rule(
            AlertRule(
                name="系统资源不足",
                alert_type=AlertType.SYSTEM_RESOURCE,
                condition=lambda m: (
                    m.get("cpu_usage", 0) > m.get("cpu_threshold", 90)
                    or m.get("memory_usage", 0) > m.get("memory_threshold", 90)
                ),
                channels=[AlertChannel.CONSOLE],
                severity=3,
                message_template="系统资源不足: CPU {cpu_usage:.1f}%, 内存 {memory_usage:.1f}%",
                cooldown_seconds=900,
            )
        )

    def add_rule(self, rule: AlertRule) -> None:
        with self._lock:
            self.rules[rule.rule_id] = rule
            self.logger.info(f"添加报警规则: {rule.name} ({rule.rule_id})")

    def remove_rule(self, rule_id: str) -> bool:
        with self._lock:
            if rule_id in self.rules:
                del self.rules[rule_id]
                self.logger.info(f"移除报警规则: {rule_id}")
                return True
            return False

    def add_channel(self, channel: NotificationChannel) -> None:
        self.channels[channel.channel_type] = channel

    def remove_channel(self, channel_type: AlertChannel) -> bool:
        if channel_type in self.channels and channel_type != AlertChannel.CONSOLE:
            del self.channels[channel_type]
            return True
        return False

    def on_alert(self, callback: Callable[[AlertRecord], None]) -> None:
        self._alert_callbacks.append(callback)

    def check_alerts(self, metrics: Dict[str, Any]) -> List[AlertRecord]:
        """
        检查并发送报警

        Args:
            metrics: 当前指标

        Returns:
            触发的报警记录列表
        """
        triggered = []
        now = datetime.datetime.now()

        for rule in self.rules.values():
            if not rule.enabled:
                continue

            last_alert = self.cooldowns.get(rule.rule_id)
            if (
                last_alert
                and (now - last_alert).total_seconds() < rule.cooldown_seconds
            ):
                continue

            if rule.evaluate(metrics):
                record = self._fire_alert(rule, metrics)
                triggered.append(record)

        return triggered

    def _fire_alert(self, rule: AlertRule, metrics: Dict[str, Any]) -> AlertRecord:
        message = rule.format_message(metrics)
        record = AlertRecord(
            rule_id=rule.rule_id,
            alert_type=rule.alert_type,
            message=message,
            severity=rule.severity,
            metrics_snapshot=dict(metrics),
        )

        with self._lock:
            self.records.append(record)
            self.cooldowns[rule.rule_id] = datetime.datetime.now()

        for channel_type in rule.channels:
            channel = self.channels.get(channel_type)
            if channel:
                success = channel.send(message, rule.severity)
                if success:
                    record.channels_sent.append(channel_type.value)

        self.logger.warning(
            f"报警触发: {rule.name} | {message}",
            context={"alert_type": rule.alert_type.value, "severity": rule.severity},
        )

        for cb in self._alert_callbacks:
            try:
                cb(record)
            except Exception as e:
                self.logger.error(f"报警回调执行失败: {e}")

        return record

    def resolve_alert(self, record_id: str) -> bool:
        with self._lock:
            for record in self.records:
                if record.record_id == record_id:
                    record.resolve()
                    self.logger.info(f"报警已解决: {record_id}")
                    return True
        return False

    def get_active_alerts(self, limit: int = 50) -> List[AlertRecord]:
        return [r for r in self.records if not r.resolved][-limit:]

    def get_alert_history(
        self,
        since: Optional[datetime.datetime] = None,
        alert_type: Optional[AlertType] = None,
        limit: int = 100,
    ) -> List[AlertRecord]:
        results = self.records
        if since:
            results = [r for r in results if r.timestamp >= since]
        if alert_type:
            results = [r for r in results if r.alert_type == alert_type]
        return results[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        total = len(self.records)
        active = sum(1 for r in self.records if not r.resolved)
        resolved = total - active

        by_type = defaultdict(int)
        for r in self.records:
            by_type[r.alert_type.value] += 1

        return {
            "total_alerts": total,
            "active_alerts": active,
            "resolved_alerts": resolved,
            "by_type": dict(by_type),
            "rules_count": len(self.rules),
            "channels_count": len(self.channels),
        }


# ---------------------------------------------------------------------------
# MonitorDashboard: 监控面板
# ---------------------------------------------------------------------------
@dataclass
class DashboardMetrics:
    """
    面板指标快照

    Attributes:
        timestamp: 快照时间
        strategy_performance: 策略表现 {name: {return, sharpe, drawdown, ...}}
        risk_metrics: 风险指标 {metric_name: value}
        positions: 持仓状态 {symbol: {quantity, value, pnl, ...}}
        portfolio_summary: 组合摘要 {total_value, cash, total_pnl, ...}
        market_data: 市场数据 {index, volatility, ...}
        system_status: 系统状态 {cpu, memory, latency, ...}
    """

    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    strategy_performance: Dict[str, Dict[str, float]] = field(default_factory=dict)
    risk_metrics: Dict[str, float] = field(default_factory=dict)
    positions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    portfolio_summary: Dict[str, Any] = field(default_factory=dict)
    market_data: Dict[str, Any] = field(default_factory=dict)
    system_status: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "strategy_performance": self.strategy_performance,
            "risk_metrics": self.risk_metrics,
            "positions": self.positions,
            "portfolio_summary": self.portfolio_summary,
            "market_data": self.market_data,
            "system_status": self.system_status,
        }


class MonitorDashboard:
    """
    监控面板

    实时展示策略表现、风险指标、持仓状态。

    Attributes:
        metrics_history: 历史指标快照
        max_history: 最大历史长度
        logger: 日志器
        _lock: 线程锁
        _current_metrics: 当前指标
        _subscribers: 订阅者回调
    """

    def __init__(self, max_history: int = 1440, logger: Optional[Logger] = None):
        self.metrics_history: deque = deque(maxlen=max_history)
        self.max_history = max_history
        self.logger = logger or Logger.get_instance("dashboard")
        self._lock = threading.Lock()
        self._current_metrics: Optional[DashboardMetrics] = None
        self._subscribers: List[Callable[[DashboardMetrics], None]] = []
        self._strategy_rankings: Dict[str, int] = {}

    def update_dashboard(self, metrics: Dict[str, Any]) -> DashboardMetrics:
        """
        更新监控面板

        Args:
            metrics: 指标数据，包含:
                - strategy_performance: {name: {return, sharpe, drawdown, ...}}
                - risk_metrics: {metric_name: value}
                - positions: {symbol: {quantity, value, pnl, ...}}
                - portfolio_summary: {total_value, cash, total_pnl, ...}
                - market_data: {index, volatility, ...}
                - system_status: {cpu, memory, latency, ...}

        Returns:
            DashboardMetrics
        """
        dashboard = DashboardMetrics(
            timestamp=datetime.datetime.now(),
            strategy_performance=metrics.get("strategy_performance", {}),
            risk_metrics=metrics.get("risk_metrics", {}),
            positions=metrics.get("positions", {}),
            portfolio_summary=metrics.get("portfolio_summary", {}),
            market_data=metrics.get("market_data", {}),
            system_status=metrics.get("system_status", {}),
        )

        with self._lock:
            self._current_metrics = dashboard
            self.metrics_history.append(dashboard)

        self._update_strategy_rankings(dashboard.strategy_performance)

        for sub in self._subscribers:
            try:
                sub(dashboard)
            except Exception as e:
                self.logger.error(f"面板订阅者回调失败: {e}")

        return dashboard

    def subscribe(self, callback: Callable[[DashboardMetrics], None]) -> None:
        self._subscribers.append(callback)

    def _update_strategy_rankings(
        self, performance: Dict[str, Dict[str, float]]
    ) -> None:
        sorted_strategies = sorted(
            performance.items(),
            key=lambda x: x[1].get("return", 0),
            reverse=True,
        )
        for rank, (name, _) in enumerate(sorted_strategies, 1):
            self._strategy_rankings[name] = rank

    def get_current_metrics(self) -> Optional[DashboardMetrics]:
        with self._lock:
            return self._current_metrics

    def get_history(
        self,
        since: Optional[datetime.datetime] = None,
        limit: int = 100,
    ) -> List[DashboardMetrics]:
        results = list(self.metrics_history)
        if since:
            results = [m for m in results if m.timestamp >= since]
        return results[-limit:]

    def get_strategy_rankings(self) -> Dict[str, int]:
        return dict(self._strategy_rankings)

    def get_strategy_performance_summary(self) -> Dict[str, Any]:
        if not self.metrics_history:
            return {}

        latest = self.metrics_history[-1]
        perf = latest.strategy_performance

        summary = {}
        for name, metrics in perf.items():
            returns = metrics.get("return", 0)
            sharpe = metrics.get("sharpe", 0)
            drawdown = metrics.get("drawdown", 0)
            summary[name] = {
                "return": returns,
                "sharpe": sharpe,
                "drawdown": drawdown,
                "ranking": self._strategy_rankings.get(name, 0),
            }

        return summary

    def get_risk_summary(self) -> Dict[str, Any]:
        if not self.metrics_history:
            return {}

        latest = self.metrics_history[-1]
        return latest.risk_metrics

    def get_positions_summary(self) -> Dict[str, Any]:
        if not self.metrics_history:
            return {}

        latest = self.metrics_history[-1]
        total_value = sum(p.get("value", 0) for p in latest.positions.values())
        total_pnl = sum(p.get("pnl", 0) for p in latest.positions.values())

        return {
            "total_value": total_value,
            "total_pnl": total_pnl,
            "position_count": len(latest.positions),
            "positions": latest.positions,
        }

    def get_chart_data(
        self,
        metric_name: str,
        period: int = 100,
    ) -> List[Dict[str, Any]]:
        history = list(self.metrics_history)[-period:]
        data = []
        for m in history:
            value = m.risk_metrics.get(metric_name)
            if value is not None:
                data.append({"timestamp": m.timestamp.isoformat(), "value": value})
        return data

    def get_portfolio_equity_curve(self, period: int = 100) -> List[Dict[str, Any]]:
        history = list(self.metrics_history)[-period:]
        data = []
        for m in history:
            total_value = m.portfolio_summary.get("total_value", 0)
            data.append({"timestamp": m.timestamp.isoformat(), "value": total_value})
        return data


# ---------------------------------------------------------------------------
# PerformanceMonitor: 性能监控
# ---------------------------------------------------------------------------
class PerformanceMonitor:
    """
    性能监控

    监控 CPU、内存、延迟等系统资源指标。

    Attributes:
        logger: 日志器
        _cpu_history: CPU 使用率历史
        _memory_history: 内存使用率历史
        _latency_history: 延迟历史
        _start_time: 监控启动时间
        _lock: 线程锁
        _operation_timings: 操作耗时记录
    """

    def __init__(self, max_history: int = 10000, logger: Optional[Logger] = None):
        self.max_history = max_history
        self.logger = logger or Logger.get_instance("performance")
        self._cpu_history: deque = deque(maxlen=max_history)
        self._memory_history: deque = deque(maxlen=max_history)
        self._latency_history: deque = deque(maxlen=max_history)
        self._disk_history: deque = deque(maxlen=max_history)
        self._start_time = datetime.datetime.now()
        self._lock = threading.Lock()
        self._operation_timings: Dict[str, List[float]] = defaultdict(list)
        self._max_timings_per_op = 1000
        self._process = psutil.Process(os.getpid())

    def get_cpu_usage(self) -> float:
        return psutil.cpu_percent(interval=0.1)

    def get_memory_usage(self) -> Dict[str, Any]:
        mem = psutil.virtual_memory()
        proc_mem = self._process.memory_info()
        return {
            "total_mb": mem.total / (1024 * 1024),
            "available_mb": mem.available / (1024 * 1024),
            "used_mb": mem.used / (1024 * 1024),
            "percent": mem.percent,
            "process_rss_mb": proc_mem.rss / (1024 * 1024),
            "process_vms_mb": proc_mem.vms / (1024 * 1024),
        }

    def get_disk_usage(self, path: str = "/") -> Dict[str, Any]:
        disk = psutil.disk_usage(path)
        return {
            "total_gb": disk.total / (1024 * 1024 * 1024),
            "used_gb": disk.used / (1024 * 1024 * 1024),
            "free_gb": disk.free / (1024 * 1024 * 1024),
            "percent": disk.percent,
        }

    def get_network_io(self) -> Dict[str, Any]:
        net = psutil.net_io_counters()
        if net is None:
            return {}
        return {
            "bytes_sent_mb": net.bytes_sent / (1024 * 1024),
            "bytes_recv_mb": net.bytes_recv / (1024 * 1024),
            "packets_sent": net.packets_sent,
            "packets_recv": net.packets_recv,
        }

    def measure_latency(self, operation_name: str) -> "LatencyContext":
        return LatencyContext(self, operation_name)

    def record_latency(self, operation_name: str, duration_ms: float) -> None:
        with self._lock:
            timings = self._operation_timings[operation_name]
            timings.append(duration_ms)
            if len(timings) > self._max_timings_per_op:
                self._operation_timings[operation_name] = timings[
                    -self._max_timings_per_op :
                ]

    def snapshot(self) -> Dict[str, Any]:
        """
        采集当前性能快照

        Returns:
            性能指标字典
        """
        cpu = self.get_cpu_usage()
        mem = self.get_memory_usage()
        disk = self.get_disk_usage()

        with self._lock:
            self._cpu_history.append(
                {"timestamp": datetime.datetime.now().isoformat(), "value": cpu}
            )
            self._memory_history.append(
                {
                    "timestamp": datetime.datetime.now().isoformat(),
                    "value": mem["percent"],
                }
            )
            self._disk_history.append(
                {
                    "timestamp": datetime.datetime.now().isoformat(),
                    "value": disk["percent"],
                }
            )

        return {
            "cpu_usage": cpu,
            "memory": mem,
            "disk": disk,
            "network": self.get_network_io(),
            "uptime_seconds": (
                datetime.datetime.now() - self._start_time
            ).total_seconds(),
        }

    def get_performance_stats(self) -> Dict[str, Any]:
        """
        获取性能统计

        Returns:
            包含 CPU/内存/延迟 统计的字典
        """
        import statistics

        stats = {}

        with self._lock:
            if self._cpu_history:
                cpu_vals = [x["value"] for x in self._cpu_history]
                stats["cpu"] = {
                    "current": cpu_vals[-1],
                    "avg": statistics.mean(cpu_vals),
                    "max": max(cpu_vals),
                    "min": min(cpu_vals),
                    "samples": len(cpu_vals),
                }

            if self._memory_history:
                mem_vals = [x["value"] for x in self._memory_history]
                stats["memory"] = {
                    "current": mem_vals[-1],
                    "avg": statistics.mean(mem_vals),
                    "max": max(mem_vals),
                    "min": min(mem_vals),
                    "samples": len(mem_vals),
                }

            for op_name, timings in self._operation_timings.items():
                if timings:
                    stats[f"latency_{op_name}"] = {
                        "count": len(timings),
                        "avg_ms": statistics.mean(timings),
                        "max_ms": max(timings),
                        "min_ms": min(timings),
                        "p50_ms": statistics.median(timings),
                        "p95_ms": sorted(timings)[int(len(timings) * 0.95)]
                        if len(timings) >= 20
                        else max(timings),
                        "p99_ms": sorted(timings)[int(len(timings) * 0.99)]
                        if len(timings) >= 100
                        else max(timings),
                    }

        stats["uptime_seconds"] = (
            datetime.datetime.now() - self._start_time
        ).total_seconds()
        return stats

    def get_latency_stats(self, operation_name: Optional[str] = None) -> Dict[str, Any]:
        import statistics

        if operation_name:
            timings = self._operation_timings.get(operation_name, [])
            if not timings:
                return {}
            sorted_t = sorted(timings)
            n = len(sorted_t)
            return {
                "count": n,
                "avg_ms": statistics.mean(sorted_t),
                "max_ms": max(sorted_t),
                "min_ms": min(sorted_t),
                "p50_ms": sorted_t[n // 2],
                "p95_ms": sorted_t[int(n * 0.95)] if n >= 20 else max(sorted_t),
                "p99_ms": sorted_t[int(n * 0.99)] if n >= 100 else max(sorted_t),
            }

        result = {}
        for name, timings in self._operation_timings.items():
            if timings:
                sorted_t = sorted(timings)
                n = len(sorted_t)
                result[name] = {
                    "count": n,
                    "avg_ms": statistics.mean(sorted_t),
                    "max_ms": max(sorted_t),
                    "p95_ms": sorted_t[int(n * 0.95)] if n >= 20 else max(sorted_t),
                }
        return result

    def get_resource_alerts(self) -> List[Dict[str, Any]]:
        alerts = []
        cpu = self.get_cpu_usage()
        mem = self.get_memory_usage()
        disk = self.get_disk_usage()

        if cpu > 90:
            alerts.append({"type": "cpu_high", "value": cpu, "threshold": 90})
        if mem["percent"] > 90:
            alerts.append(
                {"type": "memory_high", "value": mem["percent"], "threshold": 90}
            )
        if disk["percent"] > 90:
            alerts.append(
                {"type": "disk_high", "value": disk["percent"], "threshold": 90}
            )
        if mem["process_rss_mb"] > 2048:
            alerts.append(
                {
                    "type": "process_memory_high",
                    "value": mem["process_rss_mb"],
                    "threshold": 2048,
                }
            )

        return alerts

    def reset(self) -> None:
        with self._lock:
            self._cpu_history.clear()
            self._memory_history.clear()
            self._latency_history.clear()
            self._disk_history.clear()
            self._operation_timings.clear()
        self._start_time = datetime.datetime.now()


# ---------------------------------------------------------------------------
# LatencyContext: 延迟测量上下文
# ---------------------------------------------------------------------------
class LatencyContext:
    """延迟测量上下文管理器"""

    def __init__(self, monitor: PerformanceMonitor, operation_name: str):
        self.monitor = monitor
        self.operation_name = operation_name
        self.start_time = 0.0
        self.duration_ms = 0.0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration_ms = (time.perf_counter() - self.start_time) * 1000
        self.monitor.record_latency(self.operation_name, self.duration_ms)
        return False


# ---------------------------------------------------------------------------
# ReportGenerator: 报告生成器
# ---------------------------------------------------------------------------
class ReportGenerator:
    """
    报告生成器

    自动生成日报/周报/月报。

    Attributes:
        logger: 日志器
        dashboard: 监控面板
        alert_manager: 报警管理器
        perf_monitor: 性能监控
        report_dir: 报告存储目录
    """

    def __init__(
        self,
        dashboard: Optional[MonitorDashboard] = None,
        alert_manager: Optional[AlertManager] = None,
        perf_monitor: Optional[PerformanceMonitor] = None,
        logger: Optional[Logger] = None,
        report_dir: str = "reports",
    ):
        self.dashboard = dashboard or MonitorDashboard()
        self.alert_manager = alert_manager or AlertManager()
        self.perf_monitor = perf_monitor or PerformanceMonitor()
        self.logger = logger or Logger.get_instance("report_generator")
        self.report_dir = report_dir
        self._reports: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

        if not os.path.exists(self.report_dir):
            os.makedirs(self.report_dir, exist_ok=True)

    def generate_report(self, period: ReportPeriod, **kwargs) -> Dict[str, Any]:
        """
        生成报告

        Args:
            period: 报告周期 (DAILY/WEEKLY/MONTHLY)
            **kwargs: 额外参数 (data_source, start_date, end_date 等)

        Returns:
            报告字典
        """
        if period == ReportPeriod.DAILY:
            report = self._generate_daily_report(**kwargs)
        elif period == ReportPeriod.WEEKLY:
            report = self._generate_weekly_report(**kwargs)
        elif period == ReportPeriod.MONTHLY:
            report = self._generate_monthly_report(**kwargs)
        else:
            raise ValueError(f"未知报告周期: {period}")

        with self._lock:
            self._reports.append(report)

        self._save_report(report, period)

        self.logger.info(
            f"报告生成: {period.value} | {report.get('title', '')}",
            context={"period": period.value},
        )

        return report

    def _generate_daily_report(self, **kwargs) -> Dict[str, Any]:
        data_source = kwargs.get("data_source", {})
        current_metrics = self.dashboard.get_current_metrics()

        today = datetime.date.today()
        title = f"交易日报 - {today.strftime('%Y-%m-%d')}"

        trades = data_source.get("trades", [])
        positions = data_source.get("positions", {})
        pnl = data_source.get("daily_pnl", 0)
        risk_metrics = data_source.get("risk_metrics", {})

        strategy_perf = {}
        if current_metrics:
            strategy_perf = current_metrics.strategy_performance

        report = {
            "title": title,
            "period": ReportPeriod.DAILY.value,
            "date": today.isoformat(),
            "generated_at": datetime.datetime.now().isoformat(),
            "summary": {
                "daily_pnl": pnl,
                "daily_pnl_pct": data_source.get("daily_pnl_pct", 0),
                "trade_count": len(trades),
                "position_count": len(positions),
                "total_value": data_source.get("total_value", 0),
            },
            "trades": [
                {
                    "symbol": t.get("symbol", ""),
                    "side": t.get("side", ""),
                    "quantity": t.get("quantity", 0),
                    "price": t.get("price", 0),
                    "pnl": t.get("pnl", 0),
                    "time": t.get("time", ""),
                }
                for t in trades
            ],
            "positions": {
                symbol: {
                    "quantity": pos.get("quantity", 0),
                    "value": pos.get("value", 0),
                    "pnl": pos.get("pnl", 0),
                    "pnl_pct": pos.get("pnl_pct", 0),
                    "weight": pos.get("weight", 0),
                }
                for symbol, pos in positions.items()
            },
            "strategy_performance": strategy_perf,
            "risk_metrics": risk_metrics,
            "alerts": [
                r.to_dict() for r in self.alert_manager.get_alert_history(limit=20)
            ],
            "system_status": self.perf_monitor.get_performance_stats(),
        }

        return report

    def _generate_weekly_report(self, **kwargs) -> Dict[str, Any]:
        data_source = kwargs.get("data_source", {})
        today = datetime.date.today()
        week_start = today - datetime.timedelta(days=today.weekday())
        title = f"交易周报 - {week_start.strftime('%Y-%m-%d')} 至 {today.strftime('%Y-%m-%d')}"

        weekly_pnl = data_source.get("weekly_pnl", 0)
        weekly_pnl_pct = data_source.get("weekly_pnl_pct", 0)
        strategy_rankings = self.dashboard.get_strategy_rankings()
        risk_history = data_source.get("risk_history", [])

        ranking_changes = []
        current_rankings = self.dashboard.get_strategy_rankings()
        prev_rankings = data_source.get("prev_week_rankings", {})
        for name, rank in current_rankings.items():
            prev_rank = prev_rankings.get(name, 0)
            if prev_rank > 0:
                change = prev_rank - rank
                if change != 0:
                    ranking_changes.append(
                        {
                            "strategy": name,
                            "current_rank": rank,
                            "prev_rank": prev_rank,
                            "change": change,
                        }
                    )

        risk_trend = []
        for rm in risk_history[-7:]:
            risk_trend.append(
                {
                    "date": rm.get("date", ""),
                    "drawdown": rm.get("drawdown", 0),
                    "volatility": rm.get("volatility", 0),
                    "var": rm.get("var", 0),
                }
            )

        report = {
            "title": title,
            "period": ReportPeriod.WEEKLY.value,
            "week_start": week_start.isoformat(),
            "week_end": today.isoformat(),
            "generated_at": datetime.datetime.now().isoformat(),
            "summary": {
                "weekly_pnl": weekly_pnl,
                "weekly_pnl_pct": weekly_pnl_pct,
                "weekly_volatility": data_source.get("weekly_volatility", 0),
                "weekly_sharpe": data_source.get("weekly_sharpe", 0),
                "max_drawdown": data_source.get("max_drawdown", 0),
                "trade_count": data_source.get("weekly_trade_count", 0),
                "win_rate": data_source.get("weekly_win_rate", 0),
            },
            "strategy_rankings": current_rankings,
            "ranking_changes": ranking_changes,
            "risk_trend": risk_trend,
            "alerts_summary": self.alert_manager.get_stats(),
            "system_performance": self.perf_monitor.get_performance_stats(),
        }

        return report

    def _generate_monthly_report(self, **kwargs) -> Dict[str, Any]:
        data_source = kwargs.get("data_source", {})
        today = datetime.date.today()
        month_start = today.replace(day=1)
        title = f"交易月报 - {month_start.strftime('%Y-%m')}"

        monthly_pnl = data_source.get("monthly_pnl", 0)
        monthly_pnl_pct = data_source.get("monthly_pnl_pct", 0)
        monthly_sharpe = data_source.get("monthly_sharpe", 0)
        max_drawdown = data_source.get("max_drawdown", 0)
        win_rate = data_source.get("win_rate", 0)
        profit_factor = data_source.get("profit_factor", 0)

        strategy_adjustments = []
        strategy_perf = data_source.get("strategy_performance", {})
        for name, perf in strategy_perf.items():
            sharpe = perf.get("sharpe", 0)
            dd = perf.get("drawdown", 0)
            ret = perf.get("return", 0)

            suggestion = ""
            if sharpe < 0:
                suggestion = "建议暂停或调整策略"
            elif dd > 0.15:
                suggestion = "建议降低仓位或收紧止损"
            elif ret < 0 and sharpe < 0.5:
                suggestion = "建议观察，考虑减少权重"
            elif sharpe > 1.5 and dd < 0.05:
                suggestion = "表现优异，可适当增加权重"

            if suggestion:
                strategy_adjustments.append(
                    {
                        "strategy": name,
                        "return": ret,
                        "sharpe": sharpe,
                        "drawdown": dd,
                        "suggestion": suggestion,
                    }
                )

        market_review = data_source.get("market_review", {})

        report = {
            "title": title,
            "period": ReportPeriod.MONTHLY.value,
            "month": month_start.strftime("%Y-%m"),
            "generated_at": datetime.datetime.now().isoformat(),
            "summary": {
                "monthly_pnl": monthly_pnl,
                "monthly_pnl_pct": monthly_pnl_pct,
                "monthly_sharpe": monthly_sharpe,
                "max_drawdown": max_drawdown,
                "win_rate": win_rate,
                "profit_factor": profit_factor,
                "total_trades": data_source.get("total_trades", 0),
                "avg_trade_pnl": data_source.get("avg_trade_pnl", 0),
                "best_trade": data_source.get("best_trade", 0),
                "worst_trade": data_source.get("worst_trade", 0),
            },
            "strategy_adjustments": strategy_adjustments,
            "strategy_performance_summary": {
                name: {
                    "return": perf.get("return", 0),
                    "sharpe": perf.get("sharpe", 0),
                    "drawdown": perf.get("drawdown", 0),
                    "volatility": perf.get("volatility", 0),
                }
                for name, perf in strategy_perf.items()
            },
            "market_review": market_review,
            "alerts_summary": self.alert_manager.get_stats(),
            "system_performance": self.perf_monitor.get_performance_stats(),
        }

        return report

    def _save_report(self, report: Dict[str, Any], period: ReportPeriod) -> str:
        date_str = report.get(
            "date", report.get("month", datetime.date.today().isoformat())
        )
        filename = f"{period.value}_{date_str}.json"
        filepath = os.path.join(self.report_dir, filename)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2, default=str)
            self.logger.info(f"报告已保存: {filepath}")
            return filepath
        except Exception as e:
            self.logger.error(f"报告保存失败: {e}")
            return ""

    def get_reports(
        self,
        period: Optional[ReportPeriod] = None,
        since: Optional[datetime.date] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        results = self._reports
        if period:
            results = [r for r in results if r.get("period") == period.value]
        if since:
            results = [
                r
                for r in results
                if r.get("date", r.get("month", "")) >= since.isoformat()
            ]
        return results[-limit:]

    def get_latest_report(
        self, period: Optional[ReportPeriod] = None
    ) -> Optional[Dict[str, Any]]:
        if period:
            for r in reversed(self._reports):
                if r.get("period") == period.value:
                    return r
            return None
        return self._reports[-1] if self._reports else None


# ---------------------------------------------------------------------------
# MonitorSystem: 监控系统 (统一入口)
# ---------------------------------------------------------------------------
class MonitorSystem:
    """
    监控系统统一入口

    整合日志、面板、报警、报告、性能监控。

    Attributes:
        logger: 增强日志器
        dashboard: 监控面板
        alert_manager: 报警管理器
        report_generator: 报告生成器
        perf_monitor: 性能监控
    """

    def __init__(
        self,
        log_config: Optional[LogConfig] = None,
        report_dir: str = "reports",
        enable_perf_monitor: bool = True,
    ):
        self.logger = Logger.get_instance("monitor_system", log_config)
        self.dashboard = MonitorDashboard(logger=self.logger)
        self.alert_manager = AlertManager(logger=self.logger)
        self.perf_monitor = (
            PerformanceMonitor(logger=self.logger) if enable_perf_monitor else None
        )
        self.report_generator = ReportGenerator(
            dashboard=self.dashboard,
            alert_manager=self.alert_manager,
            perf_monitor=self.perf_monitor,
            logger=self.logger,
            report_dir=report_dir,
        )

        self.logger.info("监控系统初始化完成")

    def log(
        self, level: LogLevel, message: str, context: Optional[Dict[str, Any]] = None
    ) -> LogEntry:
        return self.logger.log(level, message, context=context)

    def update_dashboard(self, metrics: Dict[str, Any]) -> DashboardMetrics:
        return self.dashboard.update_dashboard(metrics)

    def check_alerts(self, metrics: Dict[str, Any]) -> List[AlertRecord]:
        if self.perf_monitor:
            resource_snapshot = self.perf_monitor.snapshot()
            metrics["cpu_usage"] = resource_snapshot["cpu_usage"]
            metrics["memory_usage"] = resource_snapshot["memory"]["percent"]

        return self.alert_manager.check_alerts(metrics)

    def generate_report(self, period: ReportPeriod, **kwargs) -> Dict[str, Any]:
        return self.report_generator.generate_report(period, **kwargs)

    def get_performance_stats(self) -> Dict[str, Any]:
        if self.perf_monitor is None:
            return {"status": "disabled"}
        return self.perf_monitor.get_performance_stats()

    def run_periodic_check(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行周期性检查 (日志+面板+报警+性能)

        Args:
            metrics: 当前指标

        Returns:
            检查结果
        """
        self.logger.debug(
            "执行周期性检查", context={"metrics_keys": list(metrics.keys())}
        )

        dashboard = self.update_dashboard(metrics)

        alerts = self.check_alerts(metrics)

        perf_stats = {}
        if self.perf_monitor:
            perf_stats = self.perf_monitor.snapshot()
            dashboard.system_status.update(perf_stats)

        return {
            "timestamp": datetime.datetime.now().isoformat(),
            "dashboard_updated": True,
            "alerts_triggered": len(alerts),
            "alerts": [a.to_dict() for a in alerts],
            "performance": perf_stats,
        }

    def shutdown(self) -> None:
        self.logger.info("监控系统关闭")
        self.logger.close()
