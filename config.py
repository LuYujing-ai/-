import os

class Config:
    # 密钥（用于会话管理）
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'parking-system-dev-key'
    # 数据库配置（SQLite，文件存储在项目根目录）
    SQLALCHEMY_DATABASE_URI = 'sqlite:///parking.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # 关闭数据修改跟踪（减少资源占用）
    # 停车费默认配置（可在系统管理中修改）
    DEFAULT_HOURLY_FEE = 5.0  # 默认每小时5元
