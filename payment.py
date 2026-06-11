import sys
import os
import math  # 新增：导入math模块用于向上取整
import csv
from io import StringIO
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file
from flask_login import login_required, current_user

# 路径处理：确保项目根目录在搜索路径中
current_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_path)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入所需模块和模型
from app import db
from app.models import Payment, ParkingRecord, SystemSetting, User, ParkingSpace  # 补充导入ParkingSpace

# 创建蓝图
payment_bp = Blueprint('payment', __name__)

# 1. 费用计算与缴费
@payment_bp.route('/calculate-fee/<int:record_id>', methods=['GET', 'POST'])
@login_required
def calculate_fee(record_id):
    record = ParkingRecord.query.get_or_404(record_id)
    
    # 业务逻辑校验
    if record.exit_time is None:
        flash('请先完成车辆离场登记', 'danger')
        return redirect(url_for('vehicle.vehicle_exit'))
    if record.is_paid:
        flash('该记录已缴费，无需重复操作', 'info')
        return redirect(url_for('payment.payment_record'))

    # 计算停车费用
    duration = (record.exit_time - record.entry_time).total_seconds() / 3600
    duration_ceil = math.ceil(duration) if duration > 0 else 1  # 使用math.ceil需要导入math模块
    setting = SystemSetting.query.first()
    hourly_fee = setting.hourly_fee if setting else 5.0
    total_fee = round(duration_ceil * hourly_fee, 2)

    if request.method == 'POST':
        payment_method = request.form.get('payment_method')
        if not payment_method:
            flash('请选择支付方式', 'danger')
            return render_template('payment/calculate_fee.html',
                                  record=record, duration=duration_ceil, 
                                  hourly_fee=hourly_fee, total_fee=total_fee)

        # 创建收费记录
        new_payment = Payment(
            parking_record_id=record_id,
            amount=total_fee,
            payment_method=payment_method,
            operator_id=current_user.id
        )
        
        # 更新停车记录状态
        record.is_paid = True
        record.payment_id = new_payment.id
        
        # 释放关联车位
        if record.space_id:
            space = ParkingSpace.query.get(record.space_id)
            if space:
                space.status = 'idle'
                space.updated_at = datetime.now()

        db.session.add(new_payment)
        try:
            db.session.commit()
            flash(f'缴费成功！金额：{total_fee}元，支付方式：{payment_method}', 'success')
            return redirect(url_for('payment.payment_record'))
        except Exception as e:
            db.session.rollback()
            flash(f'缴费失败：{str(e)}', 'danger')

    return render_template('payment/calculate_fee.html',
                          record=record, duration=duration_ceil, 
                          hourly_fee=hourly_fee, total_fee=total_fee)

# 2. 收费记录查询
@payment_bp.route('/record')
@login_required
def payment_record():
    query_date = request.args.get('query_date', '')
    query = Payment.query.join(User, Payment.operator_id == User.id)
    
    if query_date:
        try:
            query_date_obj = datetime.strptime(query_date, '%Y-%m-%d')
            next_day = datetime(query_date_obj.year, query_date_obj.month, query_date_obj.day + 1)
            query = query.filter(Payment.payment_time >= query_date_obj, Payment.payment_time < next_day)
        except ValueError:
            flash('日期格式错误，请使用YYYY-MM-DD格式', 'danger')
    
    payments = query.order_by(Payment.payment_time.desc()).all()
    return render_template('payment/payment_record.html', payments=payments, query_date=query_date)

# 3. 收费统计与导出
@payment_bp.route('/statistic', methods=['GET', 'POST'])
@login_required
def payment_statistic():
    total_amount = 0
    cash_amount = 0
    scan_amount = 0
    start_date = ''
    end_date = ''
    payments = []

    if request.method == 'POST':
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        if not start_date or not end_date:
            flash('请选择统计日期范围', 'danger')
            return render_template('payment/payment_statistic.html')

        try:
            # 转换日期格式并处理边界
            start_obj = datetime.strptime(start_date, '%Y-%m-%d')
            end_obj = datetime.strptime(end_date, '%Y-%m-%d')
            end_obj = datetime(end_obj.year, end_obj.month, end_obj.day + 1)  # 包含结束日当天
            
            # 查询统计数据
            payments = Payment.query.filter(
                Payment.payment_time >= start_obj, 
                Payment.payment_time < end_obj
            ).all()
            
            # 计算各类型金额
            for p in payments:
                total_amount += p.amount
                if p.payment_method == 'cash':
                    cash_amount += p.amount
                else:
                    scan_amount += p.amount
                    
        except ValueError:
            flash('日期格式错误，请使用YYYY-MM-DD格式', 'danger')
        except Exception as e:
            flash(f'统计失败：{str(e)}', 'danger')

    return render_template('payment/payment_statistic.html',
                          total_amount=round(total_amount, 2),
                          cash_amount=round(cash_amount, 2),
                          scan_amount=round(scan_amount, 2),
                          start_date=start_date, end_date=end_date,
                          payments=payments)

# 4. 导出统计数据（CSV格式）
@payment_bp.route('/export', methods=['POST'])
@login_required
def export_statistic():
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    
    if not start_date or not end_date:
        flash('请选择导出日期范围', 'danger')
        return redirect(url_for('payment.payment_statistic'))

    try:
        # 解析日期
        start_obj = datetime.strptime(start_date, '%Y-%m-%d')
        end_obj = datetime.strptime(end_date, '%Y-%m-%d')
        end_obj = datetime(end_obj.year, end_obj.month, end_obj.day + 1)
        
        # 查询数据
        payments = Payment.query.join(User, Payment.operator_id == User.id).filter(
            Payment.payment_time >= start_obj, 
            Payment.payment_time < end_obj
        ).all()

        # 生成CSV
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['车牌', '缴费金额（元）', '支付方式', '操作人', '缴费时间'])
        
        for p in payments:
            record = ParkingRecord.query.get(p.parking_record_id)
            if record:  # 增加记录存在性检查
                writer.writerow([
                    record.license_plate,
                    p.amount,
                    '现金' if p.payment_method == 'cash' else '扫码',
                    p.operator.username,
                    p.payment_time.strftime('%Y-%m-%d %H:%M')
                ])

        # 导出文件
        output.seek(0)
        return send_file(
            StringIO(output.getvalue()),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'停车收费统计_{start_date}_{end_date}.csv'
        )
        
    except ValueError:
        flash('日期格式错误，请使用YYYY-MM-DD格式', 'danger')
    except Exception as e:
        flash(f'导出失败：{str(e)}', 'danger')
        
    return redirect(url_for('payment.payment_statistic'))
