"""
NaviRoom 统一配置系统
=====================

配置加载链：.env 文件 → 环境变量 → Pydantic Settings.model_validate()

使用方式：
    from recommendation.config import settings
    mode = settings.reco_semantic_mode

生产环境建议：
    - 所有敏感值通过环境变量注入，不在 .env 中写明文
    - systemd EnvironmentFile 或 Docker Compose environment 注入
    - Kubernetes 使用 Secret + envFrom

参考：AI Marketing Matrix (DEPLOYMENT_ARCHITECTURE.md) 的配置管理模式
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_project_root() -> Path:
    """向上查找项目根目录（包含 recommendation/ 和 Data_processing/ 的目录）"""
    current = Path(__file__).resolve().parent
    for _ in range(5):
        if (current / "recommendation").is_dir() and (current / "Data_processing").is_dir():
            return current
        current = current.parent
    # Fallback: 返回当前文件的祖父目录
    return Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """NaviRoom 全局配置，所有字段可通过环境变量覆盖"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ============================================================
    # 数据库
    # ============================================================
    db_host: str = Field(default="127.0.0.1", description="MySQL 主机地址")
    db_port: int = Field(default=3306, description="MySQL 端口")
    db_name: str = Field(default="navi_room_db", description="数据库名")
    db_user: str = Field(default="root", description="数据库用户名")
    db_password: str = Field(default="", description="数据库密码")

    @property
    def db_url(self) -> str:
        """构建 SQLAlchemy 数据库连接 URL"""
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    # ============================================================
    # LLM (DeepSeek)
    # ============================================================
    llm_api_key: str = Field(default="", description="DeepSeek API Key")
    llm_base_url: str = Field(
        default="https://api.deepseek.com/v1",
        description="LLM API 地址",
    )
    llm_model: str = Field(default="deepseek-chat", description="LLM 模型名")
    llm_timeout_s: float = Field(default=15.0, description="LLM 请求超时（秒）")

    # ============================================================
    # 推荐引擎
    # ============================================================
    reco_semantic_mode: str = Field(
        default="hybrid",
        description="语义匹配模式: lexical | llm | hybrid | zero_shot",
    )
    reco_requirements_mode: str = Field(
        default="merge",
        description="需求提取模式: manual | llm | merge",
    )
    reco_llm_top_k: int = Field(
        default=8,
        ge=1,
        description="LLM rerank 最大候选房间数",
    )
    reco_recency_half_life_days: float = Field(
        default=30.0,
        gt=0,
        description="行为评分时间衰减半衰期（天）",
    )
    reco_dataset_path: str = Field(
        default="Data_processing/output/dku_dataset.json",
        description="默认数据集路径",
    )

    # ============================================================
    # JWT 认证
    # ============================================================
    secret_key: str = Field(
        default="change_me_in_production",
        min_length=16,
        description="JWT 签名密钥（生产环境必须更换）",
    )
    algorithm: str = Field(default="HS256", description="JWT 签名算法")
    access_token_expire_minutes: int = Field(
        default=1440,
        ge=1,
        description="JWT 过期时间（分钟）",
    )

    # ============================================================
    # 服务器
    # ============================================================
    api_host: str = Field(default="0.0.0.0", description="API 监听地址")
    api_port: int = Field(default=8000, ge=1, le=65535, description="API 端口")
    cors_origins: list[str] = Field(
        default_factory=lambda: ["*"],
        description="允许的 CORS 来源（生产环境应限制）",
    )

    # ============================================================
    # 路径（自动推断，也可通过环境变量覆盖）
    # ============================================================
    @property
    def project_root(self) -> Path:
        return _find_project_root()

    @property
    def data_processing_dir(self) -> Path:
        return self.project_root / "Data_processing"

    @property
    def scripts_dir(self) -> Path:
        return self.data_processing_dir / "scripts"

    @property
    def output_dir(self) -> Path:
        return self.data_processing_dir / "output"

    @property
    def dataset_path(self) -> Path:
        """默认数据集的绝对路径"""
        p = Path(self.reco_dataset_path)
        if p.is_absolute():
            return p
        return self.project_root / p

    # ============================================================
    # 安全校验
    # ============================================================
    def validate_security(self) -> list[str]:
        """检查不安全的默认配置，返回警告列表"""
        warnings: list[str] = []
        if self.secret_key == "change_me_in_production":
            warnings.append("SECRET_KEY 仍为默认值，请更换为随机字符串")
        if not self.db_password:
            warnings.append("DB_PASSWORD 未设置")
        if not self.llm_api_key and self.reco_semantic_mode in ("llm", "hybrid"):
            warnings.append(
                f"LLM_API_KEY 未设置，但 RECO_SEMANTIC_MODE={self.reco_semantic_mode}，"
                f"LLM 功能将降级为本地匹配"
            )
        if self.cors_origins == ["*"]:
            warnings.append("CORS origins 为通配符 *，生产环境请限制具体域名")
        return warnings


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例（带缓存）"""
    return Settings()


# 全局单例 — 直接 import 使用
settings = get_settings()
