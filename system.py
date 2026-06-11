import sys
import os
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user, logout_user, login_user
from datetime import datetime

# 路径处理：必须在所有app相关导入前执行
current_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_path)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入应用核心模块
from app import db, bcrypt
from app.models import User, SystemSetting

# 创建蓝图
system_bp = Blueprint('system', __name__)

# 1. 用户登录
@system_bp.route('/login', methods=['GET', 'POST'])
def login():
    # 已登录用户直接跳转
    if current_user.is_authenticated:
        return redirect(url_for('parking_space.space_list'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        # 输入验证
        if not username or not password:
            flash('账号和密码不能为空', 'danger')
            return render_template('system/login.html')
            
        user = User.query.filter_by(username=username).first()

        # 验证账号密码
        if user and user.is_active and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            flash(f'欢迎回来，{username}', 'success')
            return redirect(url_for('parking_space.space_list'))
        else:
            flash('账号不存在、已禁用或密码错误', 'danger')

    return render_template('system/login.html')

# 2. 用户注销
@system_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('已成功注销', 'info')
    return redirect(url_for('system.login'))

# 3. 用户列表管理（仅管理员）
@system_bp.route('/user/list')
@login_required
def user_list():
    if current_user.role != 'admin':
        flash('仅管理员可访问此页面', 'danger')
        return redirect(url_for('parking_space.space_list'))
    
    users = User.query.all()
    return render_template('system/user_list.html', users=users)

# 4. 添加新用户（仅管理员）
@system_bp.route('/user/add', methods=['GET', 'POST'])
@login_required
def add_user():
    if current_user.role != 'admin':
        flash('仅管理员可操作', 'danger')
        return redirect(url_for('parking_space.space_list'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        role = request.form.get('role', 'cashier')

        # 表单验证
        if not username or not password or not confirm_password:
            flash('账号、密码和确认密码不能为空', 'danger')
            return render_template('system/add_user.html')
        
        if password != confirm_password:
            flash('两次输入的密码不一致', 'danger')
            return render_template('system/add_user.html')
            
        if len(password) < 6:
            flash('密码长度不能少于6位', 'danger')
            return render_template('system/add_user.html')
            
        if User.query.filter_by(username=username).first():
            flash('账号已存在', 'danger')
            return render_template('system/add_user.html')

        # 创建新用户
        try:
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            new_user = User(
                username=username,
                password=hashed_password,
                role=role,
                created_at=datetime.now()  # 补充创建时间
            )
            db.session.add(new_user)
            db.session.commit()
            flash(f'账号{username}创建成功', 'success')
            return redirect(url_for('system.user_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'创建失败：{str(e)}', 'danger')
            return render_template('system/add_user.html')

    return render_template('system/add_user.html')

# 5. 切换用户状态（启用/禁用）
@system_bp.route('/toggle-user-status/<int:user_id>', methods=['POST'])
@login_required
def toggle_user_status(user_id):
    if current_user.role != 'admin':
        flash('仅管理员可操作', 'danger')
        return redirect(url_for('parking_space.space_list'))
    
    # 禁止禁用当前登录账号
    if user_id == current_user.id:
        flash('不能禁用当前登录账号', 'danger')
        return redirect(url_for('system.user_list'))
        
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    user.updated_at = datetime.now()  # 记录状态更新时间
    
    try:
        db.session.commit()
        status = '启用' if user.is_active else '禁用'
        flash(f'用户{user.username}已{status}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'操作失败：{str(e)}', 'danger')
        
    return redirect(url_for('system.user_list'))

# 6. 修改用户密码
@system_bp.route('/change-password/<int:user_id>', methods=['POST'])
@login_required
def change_password(user_id):
    if current_user.role != 'admin':
        flash('仅管理员可操作', 'danger')
        return redirect(url_for('parking_space.space_list'))
        
    user = User.query.get_or_404(user_id)
    new_password = request.form.get('new_password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()
    
    # 密码验证
    if not new_password or not confirm_password:
        flash('新密码和确认密码不能为空', 'danger')
        return redirect(url_for('system.user_list'))
        
    if new_password != confirm_password:
        flash('两次输入的密码不一致', 'danger')
        return redirect(url_for('system.user_list'))
        
    if len(new_password) < 6:
        flash('密码长度不能少于6位', 'danger')
        return redirect(url_for('system.user_list'))
    
    # 更新密码
    try:
        user.password = bcrypt.generate_password_hash(new_password).decode('utf-8')
        user.updated_at = datetime.now()  # 记录密码更新时间
        db.session.commit()
        flash(f'用户{user.username}的密码已更新', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'密码更新失败：{str(e)}', 'danger')
        
    return redirect(url_for('system.user_list'))

# 7. 系统基础设置
@system_bp.route('/setting', methods=['GET', 'POST'])
@login_required
def system_setting():
    # 只有管理员可以修改系统设置
    if current_user.role != 'admin':
        flash('仅管理员可修改系统设置', 'danger')
        return redirect(url_for('parking_space.space_list'))
        
    setting = SystemSetting.query.first() or SystemSetting()

    if request.method == 'POST':
        parking_name = request.form.get('parking_name', '').strip()
        hourly_fee = request.form.get('hourly_fee', '').strip()

        # 表单验证
        if not parking_name:
            flash('停车场名称不能为空', 'danger')
            return render_template('system/system_setting.html', setting=setting)
            
        try:
            hourly_fee = float(hourly_fee)
            if hourly_fee < 0:
                raise ValueError
        except ValueError:
            flash('停车费需为非负数字', 'danger')
            return render_template('system/system_setting.html', setting=setting)

        # 更新设置
        setting.parking_name = parking_name
        setting.hourly_fee = hourly_fee
        setting.updated_at = datetime.now()

        try:
            if not SystemSetting.query.first():
                db.session.add(setting)
            db.session.commit()
            flash('系统设置更新成功', 'success')
            return redirect(url_for('system.system_setting'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失败：{str(e)}', 'danger')

    return render_template('system/system_setting.html', setting=setting)
