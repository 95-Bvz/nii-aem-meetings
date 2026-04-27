import logging
from flask import Blueprint, render_template, request, Response
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from app import db
from app.models import Meeting, Employee, Room, Department, Task, MeetingType
from app.decorators import manager_required

bp = Blueprint('reports', __name__, url_prefix='/reports')
logger = logging.getLogger(__name__)


@bp.route('/')
@login_required
@manager_required
def index():
    """Главная страница отчётов"""
    return render_template('reports/index.html')


@bp.route('/meetings')
@login_required
@manager_required
def meetings_report():
    """Отчёт по совещаниям"""
    # Параметры фильтрации
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    department_id = request.args.get('department_id', type=int)
    status = request.args.get('status', '')
    
    # По умолчанию - текущий месяц
    if not date_from:
        today = date.today()
        date_from = date(today.year, today.month, 1).strftime('%Y-%m-%d')
    if not date_to:
        today = date.today()
        next_month = today.replace(day=28) + timedelta(days=4)
        date_to = (next_month - timedelta(days=next_month.day)).strftime('%Y-%m-%d')
    
    try:  # Fix #7
        from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
        to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
    except ValueError:
        from flask import flash
        flash('Некорректный формат даты', 'warning')
        from_date = date.today().replace(day=1)
        to_date = date.today()
    
    # Оптимизация: joinedload для связанных данных (Fix #9)
    query = Meeting.query.options(
        joinedload(Meeting.meeting_type),
        joinedload(Meeting.room),
        joinedload(Meeting.organizer)
    ).filter(
        Meeting.date >= from_date,
        Meeting.date <= to_date
    )
    
    if status:
        query = query.filter(Meeting.status == status)
    
    if department_id:
        query = query.join(Employee, Meeting.organizer_id == Employee.id).filter(
            Employee.department_id == department_id
        )
    
    meetings = query.order_by(Meeting.date, Meeting.start_time).all()
    
    # Статистика
    stats = {
        'total': len(meetings),
        'completed': sum(1 for m in meetings if m.status == 'completed'),
        'cancelled': sum(1 for m in meetings if m.status == 'cancelled'),
        'planned': sum(1 for m in meetings if m.status == 'planned'),
        'total_duration': sum(m.duration_minutes for m in meetings if m.status == 'completed'),
        'avg_participants': sum(len(m.participants) for m in meetings) / len(meetings) if meetings else 0
    }
    
    departments = Department.query.all()
    
    return render_template('reports/meetings.html',
                          meetings=meetings,
                          stats=stats,
                          departments=departments,
                          date_from=date_from,
                          date_to=date_to)


@bp.route('/rooms')
@login_required
@manager_required
def rooms_report():
    """Отчёт по загрузке переговорных комнат"""
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    # По умолчанию - текущий месяц
    if not date_from:
        today = date.today()
        date_from = date(today.year, today.month, 1).strftime('%Y-%m-%d')
    if not date_to:
        today = date.today()
        next_month = today.replace(day=28) + timedelta(days=4)
        date_to = (next_month - timedelta(days=next_month.day)).strftime('%Y-%m-%d')
    
    try:  # Fix #7
        from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
        to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
    except ValueError:
        from flask import flash
        flash('Некорректный формат даты', 'warning')
        from_date = date.today().replace(day=1)
        to_date = date.today()
    
    # Загружаем комнаты и совещания, считаем в Python (совместимо с PostgreSQL и SQLite)
    rooms_list = Room.query.filter_by(is_active=True).all()
    total_days = (to_date - from_date).days + 1
    max_minutes = total_days * 8 * 60  # 8 часов в рабочий день
    
    room_stats = []
    for room in rooms_list:
        meetings = Meeting.query.filter(
            Meeting.room_id == room.id,
            Meeting.date >= from_date,
            Meeting.date <= to_date,
            Meeting.status != 'cancelled'
        ).all()
        
        total_minutes = sum(m.duration_minutes for m in meetings)
        utilization = (total_minutes / max_minutes * 100) if max_minutes > 0 else 0
        
        room_stats.append({
            'room': room,
            'meetings_count': len(meetings),
            'total_hours': round(total_minutes / 60, 1),
            'utilization': round(utilization, 1)
        })
    
    # Сортируем по загрузке
    room_stats.sort(key=lambda x: x['utilization'], reverse=True)
    
    return render_template('reports/rooms.html',
                          room_stats=room_stats,
                          date_from=date_from,
                          date_to=date_to)


@bp.route('/employees')
@login_required
@manager_required
def employees_report():
    """Отчёт по участию сотрудников"""
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    department_id = request.args.get('department_id', type=int)
    
    # По умолчанию - текущий месяц
    if not date_from:
        today = date.today()
        date_from = date(today.year, today.month, 1).strftime('%Y-%m-%d')
    if not date_to:
        today = date.today()
        next_month = today.replace(day=28) + timedelta(days=4)
        date_to = (next_month - timedelta(days=next_month.day)).strftime('%Y-%m-%d')
    
    try:  # Fix #7
        from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
        to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
    except ValueError:
        from flask import flash
        flash('Некорректный формат даты', 'warning')
        from_date = date.today().replace(day=1)
        to_date = date.today()
    
    query = Employee.query.filter_by(is_active=True)
    if department_id:
        query = query.filter(Employee.department_id == department_id)
    
    # Загружаем связанные данные (Fix #9 — частичная оптимизация)
    employees = query.order_by(Employee.last_name).all()
    employee_stats = []
    
    for emp in employees:
        # Совещания, где сотрудник - участник
        participated = emp.meetings.filter(
            Meeting.date >= from_date,
            Meeting.date <= to_date,
            Meeting.status != 'cancelled'
        ).count()
        
        # Совещания, которые организовал
        organized = emp.organized_meetings.filter(
            Meeting.date >= from_date,
            Meeting.date <= to_date,
            Meeting.status != 'cancelled'
        ).count()
        
        # Задачи
        pending_tasks = sum(1 for t in emp.assigned_tasks 
                          if t.status in ['pending', 'in_progress'])
        completed_tasks = sum(1 for t in emp.assigned_tasks 
                            if t.status == 'completed')
        
        employee_stats.append({
            'employee': emp,
            'participated': participated,
            'organized': organized,
            'pending_tasks': pending_tasks,
            'completed_tasks': completed_tasks
        })
    
    # Сортируем по активности
    employee_stats.sort(key=lambda x: x['participated'] + x['organized'], reverse=True)
    
    departments = Department.query.all()
    
    return render_template('reports/employees.html',
                          employee_stats=employee_stats,
                          departments=departments,
                          date_from=date_from,
                          date_to=date_to)


@bp.route('/tasks')
@login_required
@manager_required
def tasks_report():
    """Отчёт по задачам"""
    status = request.args.get('status', '')
    department_id = request.args.get('department_id', type=int)
    
    # Оптимизация: joinedload (Fix #9)
    query = Task.query.options(
        joinedload(Task.responsible),
        joinedload(Task.protocol)
    )
    
    if status:
        query = query.filter(Task.status == status)
    
    if department_id:
        query = query.join(Employee, Task.responsible_id == Employee.id).filter(
            Employee.department_id == department_id
        )
    
    tasks = query.order_by(Task.deadline.asc().nullslast()).all()
    
    # Статистика
    stats = {
        'total': len(tasks),
        'pending': sum(1 for t in tasks if t.status == 'pending'),
        'in_progress': sum(1 for t in tasks if t.status == 'in_progress'),
        'completed': sum(1 for t in tasks if t.status == 'completed'),
        'overdue': sum(1 for t in tasks if t.deadline and t.deadline < date.today() 
                      and t.status not in ['completed'])
    }
    
    departments = Department.query.all()
    
    return render_template('reports/tasks.html',
                          tasks=tasks,
                          stats=stats,
                          departments=departments,
                          today=date.today())


@bp.route('/statistics')
@login_required
@manager_required
def statistics():
    """Общая статистика системы"""
    today = date.today()
    current_month_start = date(today.year, today.month, 1)
    
    # Статистика по месяцам за последний год
    monthly_stats = []
    for i in range(12):
        month_date = today - timedelta(days=30*i)
        month_start = date(month_date.year, month_date.month, 1)
        if month_date.month == 12:
            month_end = date(month_date.year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(month_date.year, month_date.month + 1, 1) - timedelta(days=1)
        
        count = Meeting.query.filter(
            Meeting.date >= month_start,
            Meeting.date <= month_end
        ).count()
        
        monthly_stats.append({
            'month': month_start.strftime('%B %Y'),
            'count': count
        })
    
    monthly_stats.reverse()
    
    # Статистика по типам совещаний
    type_stats = db.session.query(
        MeetingType.name,
        MeetingType.color,
        func.count(Meeting.id)
    ).join(Meeting, MeetingType.id == Meeting.type_id).group_by(
        MeetingType.id
    ).all()
    
    # Топ организаторов
    top_organizers = db.session.query(
        Employee,
        func.count(Meeting.id).label('count')
    ).join(Meeting, Employee.id == Meeting.organizer_id).group_by(
        Employee.id
    ).order_by(func.count(Meeting.id).desc()).limit(10).all()
    
    # Топ комнат
    top_rooms = db.session.query(
        Room,
        func.count(Meeting.id).label('count')
    ).join(Meeting, Room.id == Meeting.room_id).group_by(
        Room.id
    ).order_by(func.count(Meeting.id).desc()).limit(5).all()
    
    return render_template('reports/statistics.html',
                          monthly_stats=monthly_stats,
                          type_stats=type_stats,
                          top_organizers=top_organizers,
                          top_rooms=top_rooms)
