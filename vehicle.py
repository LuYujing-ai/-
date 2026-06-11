import sys
import os
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required

# 路径处理：确保项目根目录在搜索路径中
current_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_path)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    
from app import db
from app.models import ParkingRecord, ParkingSpace, SystemSetting
from datetime import datetime
import math

vehicle_bp = Blueprint('vehicle', __name__)

# 1. 车辆入场登记
@vehicle_bp.route('/entry', methods=['GET', 'POST'])
@login_required
def vehicle_entry():
    if request.method == 'POST':
        license_plate = request.form.get('license_plate').strip()
        car_type = request.form.get('car_type')
        space_id = request.form.get('space_id')  # 可选：关联固定车位

        # 输入校验
        if not license_plate:
            flash('车牌号码不能为空', 'danger')
            return render_template('vehicle/vehicle_entry.html', spaces=ParkingSpace.query.filter_by(status='idle').all())
        
        # 检查是否有未离场的相同车牌记录
        active_record = ParkingRecord.query.filter_by(
            license_plate=license_plate, exit_time=None
        ).first()
        if active_record:
            flash(f'车牌{license_plate}已有未离场记录，请勿重复登记', 'danger')
            return render_template('vehicle/vehicle_entry.html', spaces=ParkingSpace.query.filter_by(status='idle').all())

        # 若关联车位，标记车位为占用
        if space_id:
            space = ParkingSpace.query.get(space_id)
            if space and space.status == 'idle':
                space.status = 'occupied'
                space.updated_at = datetime.now()

        # 创建入场记录
        new_record = ParkingRecord(
            license_plate=license_plate,
            car_type=car_type,
            space_id=space_id if space_id else None,
            entry_time=datetime.now()
        )
        db.session.add(new_record)
        db.session.commit()

        flash(f'车牌{license_plate}入场登记成功，时间：{new_record.entry_time.strftime("%Y-%m-%d %H:%M")}', 'success')
        return redirect(url_for('vehicle.vehicle_entry'))

    # GET请求：显示空闲车位列表（供选择）
    idle_spaces = ParkingSpace.query.filter_by(status='idle').all()
    return render_template('vehicle/vehicle_entry.html', spaces=idle_spaces)

# 2. 车辆离场处理（含费用计算）
@vehicle_bp.route('/exit', methods=['GET', 'POST'])
@login_required
def vehicle_exit():
    if request.method == 'POST':
        license_plate = request.form.get('license_plate').strip()
        # 获取未离场记录
        record = ParkingRecord.query.filter_by(
            license_plate=license_plate, exit_time=None
        ).first()
        
        if not record:
            flash(f'未找到车牌{license_plate}的未离场记录', 'danger')
            return render_template('vehicle/vehicle_exit.html')

        # 记录离场时间
        exit_time = datetime.now()
        record.exit_time = exit_time

        # 计算停车时长（小时，向上取整）
        duration = (exit_time - record.entry_time).total_seconds() / 3600
        duration_ceil = math.ceil(duration) if duration > 0 else 1

        # 获取当前停车费标准
        setting = SystemSetting.query.first()
        hourly_fee = setting.hourly_fee if setting else 5.0
        total_fee = round(duration_ceil * hourly_fee, 2)

        # 标记为“未缴费”（后续在收费模块处理）
        record.is_paid = False

        db.session.commit()

        # 跳转至收费页面
        return redirect(url_for('payment.calculate_fee', record_id=record.id))

    return render_template('vehicle/vehicle_exit.html')

# 3. 停车记录查询
@vehicle_bp.route('/record', methods=['GET', 'POST'])
@login_required
def parking_record():
    records = []
    if request.method == 'POST':
        # 按车牌或日期筛选
        license_plate = request.form.get('license_plate', '').strip()
        query_date = request.form.get('query_date', '')

        query = ParkingRecord.query
        if license_plate:
            query = query.filter(ParkingRecord.license_plate.like(f'%{license_plate}%'))
        if query_date:
            # 转换日期格式，查询当天记录
            query_date_obj = datetime.strptime(query_date, '%Y-%m-%d')
            next_day = datetime(query_date_obj.year, query_date_obj.month, query_date_obj.day + 1)
            query = query.filter(ParkingRecord.entry_time >= query_date_obj, ParkingRecord.entry_time < next_day)
        
        records = query.order_by(ParkingRecord.entry_time.desc()).all()

    return render_template('vehicle/parking_record.html', records=records)
