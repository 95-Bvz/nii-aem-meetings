import logging
from flask import Blueprint, render_template, url_for
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from sqlalchemy import func
from app import db
from app.models import Meeting, Employee, Room, Task, Department

bp = Blueprint('main', __name__)
logger = logging.getLogger(__name__)


@bp.route('/')
@bp.route('/index')
@login_required
def index():
    """Главная страница - дашборд"""
    today = date.today()
    
    # Статистика — видна всем пользователям
    stats = {
        'total_meetings': Meeting.query.count(),
        'today_meetings': Meeting.query.filter(Meeting.date == today).count(),
        'week_meetings': Meeting.query.filter(
            Meeting.date >= today,
            Meeting.date <= today + timedelta(days=7)
        ).count(),
        'total_employees': Employee.query.filter_by(is_active=True).count(),
        'total_rooms': Room.query.filter_by(is_active=True).count(),
        'pending_tasks': Task.query.filter_by(status='pending').count(),
    }
    
    # Ближайшие совещания
    upcoming_meetings = Meeting.query.filter(
        Meeting.date >= today,
        Meeting.status.in_(['planned', 'ongoing'])
    ).order_by(Meeting.date, Meeting.start_time).limit(5).all()
    
    # Сегодняшние совещания
    today_meetings = Meeting.query.filter(
        Meeting.date == today
    ).order_by(Meeting.start_time).all()
    
    # Просроченные задачи
    overdue_tasks = Task.query.filter(
        Task.status.in_(['pending', 'in_progress']),
        Task.deadline < today
    ).limit(5).all()
    
    return render_template('index.html', 
                          stats=stats,
                          upcoming_meetings=upcoming_meetings,
                          today_meetings=today_meetings,
                          overdue_tasks=overdue_tasks)


@bp.route('/calendar')
@login_required
def calendar():
    """Страница календаря"""
    rooms = Room.query.filter_by(is_active=True).all()
    return render_template('calendar.html', rooms=rooms)


@bp.route('/api/calendar-events')
@login_required
def calendar_events():
    """API для получения событий календаря"""
    from flask import request, jsonify
    
    start = request.args.get('start', '')
    end = request.args.get('end', '')
    room_id = request.args.get('room_id', type=int)
    
    try:  # Fix #7
        query = Meeting.query
        
        if start:
            try:
                start_date = datetime.fromisoformat(start.replace('Z', '+00:00')).date()
            except (ValueError, TypeError):
                start_date = datetime.strptime(start[:10], '%Y-%m-%d').date()
            query = query.filter(Meeting.date >= start_date)
        
        if end:
            try:
                end_date = datetime.fromisoformat(end.replace('Z', '+00:00')).date()
            except (ValueError, TypeError):
                end_date = datetime.strptime(end[:10], '%Y-%m-%d').date()
            query = query.filter(Meeting.date <= end_date)
        
        if room_id:
            query = query.filter(Meeting.room_id == room_id)
        
        meetings = query.all()
        
        events = []
        for m in meetings:
            color = m.meeting_type.color if m.meeting_type else '#3788d8'
            if m.status == 'cancelled':
                color = '#6c757d'
            elif m.status == 'completed':
                color = '#28a745'
            
            events.append({
                'id': m.id,
                'title': m.title,
                'start': f'{m.date}T{m.start_time}',
                'end': f'{m.date}T{m.end_time}',
                'color': color,
                'url': url_for('meetings.view', id=m.id),  # Fix #18
                'extendedProps': {
                    'room': m.room.name if m.room else 'Не указано',
                    'organizer': m.organizer.short_name if m.organizer else 'Не указано',
                    'status': m.status_display
                }
            })
        
        return jsonify(events)
    except Exception as e:
        logger.error('Ошибка при получении событий: %s', e)
        return jsonify([])
