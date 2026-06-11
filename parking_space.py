import sys
import os
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required

# 路径处理：必须在所有app相关导入前执行
current_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_path)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import db
from app.models import ParkingSpace, ParkingRecord
from datetime import datetime

parking_space_bp = Blueprint('parking_space', __name__)

# 1. 车位列表（支持筛选和搜索，适配界面原型）
@parking_space_bp.route('/list')
@login_required
def space_list():
    # 筛选条件（状态、车型）
    status_filter = request.args.get('status', 'all')
    car_type_filter = request.args.get('car_type', 'all')
    # 搜索条件（车位编号）
    search_code = request.args.get('search', '')

    # 构建查询
    query = ParkingSpace.query
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    if car_type_filter != 'all':
        query = query.filter_by(fit_car_type=car_type_filter)
    if search_code:
        query = query.filter(ParkingSpace.space_code.like(f'%{search_code}%'))
    
    # 统计各状态车位数量（底部统计区）
    total = ParkingSpace.query.count()
    idle = ParkingSpace.query.filter_by(status='idle').count()
    occupied = ParkingSpace.query.filter_by(status='occupied').count()
    fault = ParkingSpace.query.filter_by(status='fault').count()

    return render_template('parking_space/space_list.html',
                           spaces=query.all(),
                           total=total, idle=idle, occupied=occupied, fault=fault,
                           status_filter=status_filter, car_type_filter=car_type_filter, search_code=search_code)

# 2. 添加车位（适配IPO图输入输出）
@parking_space_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_space():
    if request.method == 'POST':
        space_code = request.form.get('space_code').strip()
        location = request.form.get('location').strip()
        fit_car_type = request.form.get('fit_car_type')

        # 输入校验（IPO图“处理”步骤）
        if not space_code or not location:
            flash('车位编号和位置不能为空', 'danger')
            return render_template('parking_space/add_space.html')
        if ParkingSpace.query.filter_by(space_code=space_code).first():
            flash('车位编号已存在，请重新输入', 'danger')
            return render_template('parking_space/add_space.html')

        # 保存车位（IPO图“输出”步骤）
        new_space = ParkingSpace(
            space_code=space_code,
            location=location,
            fit_car_type=fit_car_type,
            status='idle'  # 默认空闲
        )
        db.session.add(new_space)
        db.session.commit()

        flash(f'车位{space_code}添加成功', 'success')
        return redirect(url_for('parking_space.space_list'))

    return render_template('parking_space/add_space.html')

# 3. 修改车位状态（空闲/占用/故障）
@parking_space_bp.route('/update-status/<int:space_id>', methods=['POST'])
@login_required
def update_status(space_id):
    space = ParkingSpace.query.get_or_404(space_id)
    new_status = request.form.get('new_status')
    old_status = space.status

    # 占用状态校验：若车位已被占用，需先确认是否有未离场车辆
    if new_status == 'occupied':
        # 检查是否有未离场且关联该车位的记录
        active_record = ParkingRecord.query.filter_by(
            space_id=space_id, exit_time=None
        ).first()
        if not active_record:
            flash('请先登记车辆入场，再将车位标记为占用', 'warning')
            return redirect(url_for('parking_space.space_list'))
    
    # 更新状态
    space.status = new_status
    space.updated_at = datetime.now()
    db.session.commit()

    flash(f'车位{space.space_code}状态从{old_status}改为{new_status}', 'success')
    return redirect(url_for('parking_space.space_list'))

# 4. 删除车位（仅允许删除空闲车位）
@parking_space_bp.route('/delete/<int:space_id>', methods=['POST'])
@login_required
def delete_space(space_id):
    space = ParkingSpace.query.get_or_404(space_id)
    if space.status != 'idle':
        flash('仅空闲车位可删除，请先处理车位状态', 'danger')
        return redirect(url_for('parking_space.space_list'))

    db.session.delete(space)
    db.session.commit()
    flash(f'车位{space.space_code}已删除', 'success')
    return redirect(url_for('parking_space.space_list'))
