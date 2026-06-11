# init_admin.py（系统初始化脚本，仅首次启动时执行）
from app import create_app, db, bcrypt
from app.models import User


# 创建Flask应用实例并激活上下文
app = create_app()
with app.app_context():
    # 先检查是否已存在admin账号，避免重复创建
    existing_admin = User.query.filter_by(username='admin').first()
    if not existing_admin:
        # 密码加密（符合系统管理模块的账号安全要求）
        hashed_pwd = bcrypt.generate_password_hash('admin123').decode('utf-8')
        # 创建管理员账号（角色为admin，对应系统管理模块的权限控制）
        admin = User(username='admin', password=hashed_pwd, role='admin', is_active=True)
        db.session.add(admin)
        db.session.commit()
        print("初始管理员账号创建成功！账号：admin，密码：admin123")
    else:
        print("admin账号已存在，无需重复创建")
