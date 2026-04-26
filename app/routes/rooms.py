import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from app import db
from app.models import Room, Meeting
from app.decorators import manager_required, admin_required

bp = Blueprint('rooms', __name__, url_prefix='/rooms')
logger = logging.getLogger(__name__)


@bp.route('/')
@login_required
def index():
    """Список переговорных комнат"""
    rooms = Room.query.order_by(Room.name).all()
    return render_template('rooms/index.html', rooms=rooms)


@bp.route('/create', methods=['GET', 'POST'])
@login_required
@manager_required  # Fix #1
def create():
    """Создание комнаты"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        
        # Валидация (Fix #5)
        if not name:
            flash('Название комнаты обязательно', 'danger')
            return redirect(url_for('rooms.create'))
        
        try:  # Fix #7
            room = Room(
                name=name,
                building=request.form.get('building', '').strip(),
                floor=request.form.get('floor', type=int),
                room_number=request.form.get('room_number', '').strip(),
                capacity=request.form.get('capacity', type=int) or 10,
                has_projector=request.form.get('has_projector') == 'on',
                has_video_conf=request.form.get('has_video_conf') == 'on',
                has_whiteboard=request.form.get('has_whiteboard') == 'on',
                description=request.form.get('description', '').strip()
            )
            
            db.session.add(room)
            db.session.commit()
            logger.info('Комната создана: %s (id=%s)', name, room.id)
            
            flash('Переговорная комната создана', 'success')
            return redirect(url_for('rooms.view', id=room.id))
        except Exception as e:
            db.session.rollback()
            logger.error('Ошибка при создании комнаты: %s', e)
            flash('Произошла ошибка при создании комнаты', 'danger')
            return redirect(url_for('rooms.create'))
    
    return render_template('rooms/create.html')


@bp.route('/<int:id>')
@login_required
def view(id):
    """Просмотр комнаты"""
    room = Room.query.get_or_404(id)
    
    # Ближайшие совещания в этой комнате
    today = date.today()
    upcoming_meetings = Meeting.query.filter(
        Meeting.room_id == room.id,
        Meeting.date >= today,
        Meeting.status != 'cancelled'
    ).order_by(Meeting.date, Meeting.start_time).limit(10).all()
    
    return render_template('rooms/view.html', room=room, upcoming_meetings=upcoming_meetings)


@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@manager_required  # Fix #1
def edit(id):
    """Редактирование комнаты"""
    room = Room.query.get_or_404(id)
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        
        # Валидация (Fix #5)
        if not name:
            flash('Название комнаты обязательно', 'danger')
            return redirect(url_for('rooms.edit', id=room.id))
        
        try:  # Fix #7
            room.name = name
            room.building = request.form.get('building', '').strip()
            room.floor = request.form.get('floor', type=int)
            room.room_number = request.form.get('room_number', '').strip()
            room.capacity = request.form.get('capacity', type=int) or 10
            room.has_projector = request.form.get('has_projector') == 'on'
            room.has_video_conf = request.form.get('has_video_conf') == 'on'
            room.has_whiteboard = request.form.get('has_whiteboard') == 'on'
            room.description = request.form.get('description', '').strip()
            room.is_active = request.form.get('is_active') == 'on'
            
            db.session.commit()
            logger.info('Комната обновлена: id=%s', room.id)
            flash('Данные комнаты обновлены', 'success')
            return redirect(url_for('rooms.view', id=room.id))
        except Exception as e:
            db.session.rollback()
            logger.error('Ошибка при обновлении комнаты: %s', e)
            flash('Произошла ошибка при обновлении', 'danger')
            return redirect(url_for('rooms.edit', id=room.id))
    
    return render_template('rooms/edit.html', room=room)


@bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required  # Fix #1
def delete(id):
    """Удаление (деактивация) комнаты"""
    room = Room.query.get_or_404(id)
    room.is_active = False
    db.session.commit()
    logger.info('Комната деактивирована: id=%s', id)
    
    flash('Комната деактивирована', 'success')
    return redirect(url_for('rooms.index'))


@bp.route('/<int:id>/activate', methods=['POST'])
@login_required
@manager_required
def activate(id):
    """Активация деактивированной комнаты"""
    room = Room.query.get_or_404(id)
    
    if room.is_active:
        flash('Комната уже активна', 'info')
        return redirect(url_for('rooms.view', id=room.id))
    
    room.is_active = True
    db.session.commit()
    logger.info('Комната активирована: id=%s', id)
    
    flash(f'Комната «{room.name}» снова активна', 'success')
    return redirect(url_for('rooms.view', id=room.id))


@bp.route('/<int:id>/permanent-delete', methods=['POST'])
@login_required
@admin_required
def permanent_delete(id):
    """Полное удаление деактивированной комнаты"""
    room = Room.query.get_or_404(id)
    
    if room.is_active:
        flash('Нельзя удалить активную комнату. Сначала деактивируйте её.', 'danger')
        return redirect(url_for('rooms.view', id=room.id))
    
    # Проверяем, есть ли связанные совещания
    meetings_count = Meeting.query.filter_by(room_id=room.id).count()
    if meetings_count > 0:
        # Обнуляем ссылки на комнату в совещаниях
        Meeting.query.filter_by(room_id=room.id).update({Meeting.room_id: None})
    
    try:
        db.session.delete(room)
        db.session.commit()
        logger.info('Комната удалена навсегда: id=%s, name=%s', id, room.name)
        flash(f'Комната «{room.name}» удалена навсегда', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error('Ошибка при удалении комнаты: %s', e)
        flash('Произошла ошибка при удалении комнаты', 'danger')
        return redirect(url_for('rooms.view', id=room.id))
    
    return redirect(url_for('rooms.index'))


@bp.route('/<int:id>/schedule')
@login_required
def schedule(id):
    """Расписание комнаты"""
    room = Room.query.get_or_404(id)
    
    # Получаем дату из параметров или берём текущую неделю
    date_str = request.args.get('date', '')
    try:  # Fix #7
        if date_str:
            current_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            current_date = date.today()
    except ValueError:
        flash('Некорректный формат даты', 'warning')
        current_date = date.today()
    
    # Начало и конец недели
    start_of_week = current_date - timedelta(days=current_date.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    
    meetings = Meeting.query.filter(
        Meeting.room_id == room.id,
        Meeting.date >= start_of_week,
        Meeting.date <= end_of_week,
        Meeting.status != 'cancelled'
    ).order_by(Meeting.date, Meeting.start_time).all()
    
    # Группируем по дням
    week_schedule = {}
    for i in range(7):
        day = start_of_week + timedelta(days=i)
        week_schedule[day] = []
    
    for meeting in meetings:
        week_schedule[meeting.date].append(meeting)
    
    return render_template('rooms/schedule.html', 
                          room=room, 
                          week_schedule=week_schedule,
                          start_of_week=start_of_week,
                          end_of_week=end_of_week,
                          timedelta=timedelta)


@bp.route('/availability')
@login_required
def availability():
    """Проверка доступности комнат"""
    check_date = request.args.get('date', '')
    start_time = request.args.get('start_time', '')
    end_time = request.args.get('end_time', '')
    
    if not all([check_date, start_time, end_time]):
        rooms = Room.query.filter_by(is_active=True).all()
        return render_template('rooms/availability.html', rooms=rooms, results=None)
    
    try:  # Fix #7
        check_date = datetime.strptime(check_date, '%Y-%m-%d').date()
        start_time = datetime.strptime(start_time, '%H:%M').time()
        end_time = datetime.strptime(end_time, '%H:%M').time()
    except ValueError:
        flash('Некорректный формат даты или времени', 'warning')
        rooms = Room.query.filter_by(is_active=True).all()
        return render_template('rooms/availability.html', rooms=rooms, results=None)
    
    rooms = Room.query.filter_by(is_active=True).all()
    results = []
    
    for room in rooms:
        # Используем метод модели (Fix #8)
        conflict = room.check_conflict(check_date, start_time, end_time)
        
        results.append({
            'room': room,
            'available': conflict is None,
            'conflict': conflict
        })
    
    return render_template('rooms/availability.html', 
                          rooms=rooms, 
                          results=results,
                          check_date=check_date,
                          start_time=start_time,
                          end_time=end_time)
