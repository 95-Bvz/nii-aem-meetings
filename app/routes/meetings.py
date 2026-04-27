import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, time
from app import db
from app.models import Meeting, MeetingType, Room, Employee, Protocol, Task, meeting_participants
from app.decorators import manager_required, admin_required

bp = Blueprint('meetings', __name__, url_prefix='/meetings')
logger = logging.getLogger(__name__)


def _escape_like(search_term):
    """Экранирует спецсимволы для LIKE/ILIKE запросов (Fix #2)."""
    return search_term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


@bp.route('/')
@login_required
def index():
    """Список совещаний"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    search = request.args.get('search', '').strip()
    
    query = Meeting.query
    
    if status:
        query = query.filter(Meeting.status == status)
    
    try:  # Fix #7
        if date_from:
            query = query.filter(Meeting.date >= datetime.strptime(date_from, '%Y-%m-%d').date())
        if date_to:
            query = query.filter(Meeting.date <= datetime.strptime(date_to, '%Y-%m-%d').date())
    except ValueError:
        flash('Некорректный формат даты', 'warning')
    
    if search:
        safe_search = _escape_like(search)  # Fix #2
        query = query.filter(Meeting.title.ilike(f'%{safe_search}%', escape='\\'))
    
    meetings = query.order_by(Meeting.date.desc(), Meeting.start_time.desc()).paginate(
        page=page, per_page=10, error_out=False
    )
    
    return render_template('meetings/index.html', meetings=meetings)


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Создание нового совещания"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        agenda = request.form.get('agenda', '').strip()
        
        # Валидация (Fix #5)
        if not title:
            flash('Название совещания обязательно', 'danger')
            return redirect(url_for('meetings.create'))
        
        try:  # Fix #7
            meeting_date = datetime.strptime(request.form.get('date', ''), '%Y-%m-%d').date()
            start_time = datetime.strptime(request.form.get('start_time', ''), '%H:%M').time()
            end_time = datetime.strptime(request.form.get('end_time', ''), '%H:%M').time()
        except (ValueError, TypeError):
            flash('Некорректный формат даты или времени', 'danger')
            return redirect(url_for('meetings.create'))
        
        if start_time >= end_time:
            flash('Время окончания должно быть позже времени начала', 'danger')
            return redirect(url_for('meetings.create'))
        
        type_id = request.form.get('type_id', type=int)
        room_id = request.form.get('room_id', type=int)
        organizer_id = request.form.get('organizer_id', type=int)
        participant_ids = request.form.getlist('participants', type=int)
        
        if not organizer_id:
            flash('Необходимо указать организатора', 'danger')
            return redirect(url_for('meetings.create'))
        
        # Проверка доступности комнаты через модель (Fix #8)
        if room_id:
            room = Room.query.get(room_id)
            if room:
                conflict = room.check_conflict(meeting_date, start_time, end_time)
                if conflict:
                    flash(f'Комната занята в это время (конфликт с: {conflict.title})', 'danger')
                    return redirect(url_for('meetings.create'))
        
        try:  # Fix #7
            meeting = Meeting(
                title=title,
                description=description,
                agenda=agenda,
                date=meeting_date,
                start_time=start_time,
                end_time=end_time,
                type_id=type_id if type_id else None,
                room_id=room_id if room_id else None,
                organizer_id=organizer_id,
                status='planned'
            )
            
            # Добавление участников
            if participant_ids:
                participants = Employee.query.filter(Employee.id.in_(participant_ids)).all()
                meeting.participants = participants
            
            db.session.add(meeting)
            db.session.commit()
            logger.info('Совещание создано: %s (id=%s)', title, meeting.id)
            
            flash('Совещание успешно создано!', 'success')
            return redirect(url_for('meetings.view', id=meeting.id))
        except Exception as e:
            db.session.rollback()
            logger.error('Ошибка при создании совещания: %s', e)
            flash('Произошла ошибка при создании совещания', 'danger')
            return redirect(url_for('meetings.create'))
    
    types = MeetingType.query.all()
    rooms = Room.query.filter_by(is_active=True).all()
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.last_name).all()
    
    return render_template('meetings/create.html', 
                          types=types, rooms=rooms, employees=employees)


@bp.route('/<int:id>')
@login_required
def view(id):
    """Просмотр совещания"""
    meeting = Meeting.query.get_or_404(id)
    return render_template('meetings/view.html', meeting=meeting)


@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@manager_required  # Fix #1
def edit(id):
    """Редактирование совещания"""
    meeting = Meeting.query.get_or_404(id)
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        
        # Валидация (Fix #5)
        if not title:
            flash('Название совещания обязательно', 'danger')
            return redirect(url_for('meetings.edit', id=meeting.id))
        
        try:  # Fix #7
            meeting.title = title
            meeting.description = request.form.get('description', '').strip()
            meeting.agenda = request.form.get('agenda', '').strip()
            meeting.date = datetime.strptime(request.form.get('date', ''), '%Y-%m-%d').date()
            meeting.start_time = datetime.strptime(request.form.get('start_time', ''), '%H:%M').time()
            meeting.end_time = datetime.strptime(request.form.get('end_time', ''), '%H:%M').time()
            meeting.type_id = request.form.get('type_id', type=int) or None
            meeting.room_id = request.form.get('room_id', type=int) or None
            meeting.organizer_id = request.form.get('organizer_id', type=int)
            meeting.status = request.form.get('status')
            
            participant_ids = request.form.getlist('participants', type=int)
            if participant_ids:
                participants = Employee.query.filter(Employee.id.in_(participant_ids)).all()
                meeting.participants = participants
            else:
                meeting.participants = []
            
            db.session.commit()
            logger.info('Совещание обновлено: id=%s', meeting.id)
            flash('Совещание обновлено', 'success')
            return redirect(url_for('meetings.view', id=meeting.id))
        except (ValueError, TypeError):
            db.session.rollback()
            flash('Некорректный формат даты или времени', 'danger')
            return redirect(url_for('meetings.edit', id=meeting.id))
        except Exception as e:
            db.session.rollback()
            logger.error('Ошибка при обновлении совещания: %s', e)
            flash('Произошла ошибка при обновлении', 'danger')
            return redirect(url_for('meetings.edit', id=meeting.id))
    
    types = MeetingType.query.all()
    rooms = Room.query.filter_by(is_active=True).all()
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.last_name).all()
    
    return render_template('meetings/edit.html', 
                          meeting=meeting, types=types, rooms=rooms, employees=employees)


@bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required  # Fix #1
def delete(id):
    """Удаление совещания"""
    meeting = Meeting.query.get_or_404(id)
    
    try:  # Fix #7
        # Удаляем связанный протокол и задачи
        if meeting.protocol:
            Task.query.filter_by(protocol_id=meeting.protocol.id).delete()
            db.session.delete(meeting.protocol)
        
        db.session.delete(meeting)
        db.session.commit()
        logger.info('Совещание удалено: id=%s', id)
        
        flash('Совещание удалено', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error('Ошибка при удалении совещания: %s', e)
        flash('Произошла ошибка при удалении', 'danger')
    
    return redirect(url_for('meetings.index'))


@bp.route('/<int:id>/cancel', methods=['POST'])
@login_required
@manager_required  # Fix #1
def cancel(id):
    """Отмена совещания"""
    meeting = Meeting.query.get_or_404(id)
    meeting.status = 'cancelled'
    db.session.commit()
    logger.info('Совещание отменено: id=%s', id)
    
    flash('Совещание отменено', 'info')
    return redirect(url_for('meetings.view', id=meeting.id))


@bp.route('/<int:id>/complete', methods=['POST'])
@login_required
@manager_required  # Fix #1
def complete(id):
    """Завершение совещания"""
    meeting = Meeting.query.get_or_404(id)
    meeting.status = 'completed'
    db.session.commit()
    logger.info('Совещание завершено: id=%s', id)
    
    flash('Совещание отмечено как завершённое', 'success')
    return redirect(url_for('meetings.view', id=meeting.id))


@bp.route('/<int:id>/protocol', methods=['GET', 'POST'])
@login_required
@manager_required  # Fix #1
def protocol(id):
    """Создание/редактирование протокола"""
    meeting = Meeting.query.get_or_404(id)
    
    if request.method == 'POST':
        try:  # Fix #7
            if meeting.protocol:
                proto = meeting.protocol
            else:
                proto = Protocol(meeting_id=meeting.id)
                db.session.add(proto)
            
            proto.number = request.form.get('number', '').strip()
            proto.content = request.form.get('content', '').strip()
            proto.decisions = request.form.get('decisions', '').strip()
            proto.secretary_id = request.form.get('secretary_id', type=int) or None
            
            db.session.commit()
            logger.info('Протокол сохранён для совещания id=%s', meeting.id)
            flash('Протокол сохранён', 'success')
            return redirect(url_for('meetings.view', id=meeting.id))
        except Exception as e:
            db.session.rollback()
            logger.error('Ошибка при сохранении протокола: %s', e)
            flash('Произошла ошибка при сохранении протокола', 'danger')
    
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.last_name).all()
    return render_template('meetings/protocol.html', meeting=meeting, employees=employees)


@bp.route('/<int:id>/tasks', methods=['GET', 'POST'])
@login_required
@manager_required  # Fix #1
def tasks(id):
    """Управление задачами совещания"""
    meeting = Meeting.query.get_or_404(id)
    
    if not meeting.protocol:
        flash('Сначала создайте протокол совещания', 'warning')
        return redirect(url_for('meetings.protocol', id=meeting.id))
    
    if request.method == 'POST':
        description = request.form.get('description', '').strip()
        responsible_id = request.form.get('responsible_id', type=int)
        deadline = request.form.get('deadline', '')
        
        # Валидация (Fix #5)
        if not description:
            flash('Описание задачи обязательно', 'danger')
            return redirect(url_for('meetings.tasks', id=meeting.id))
        
        if not responsible_id:
            flash('Необходимо указать ответственного', 'danger')
            return redirect(url_for('meetings.tasks', id=meeting.id))
        
        try:  # Fix #7
            task = Task(
                protocol_id=meeting.protocol.id,
                description=description,
                responsible_id=responsible_id,
                deadline=datetime.strptime(deadline, '%Y-%m-%d').date() if deadline else None
            )
            
            db.session.add(task)
            db.session.commit()
            
            flash('Задача добавлена', 'success')
            return redirect(url_for('meetings.tasks', id=meeting.id))
        except (ValueError, TypeError):
            flash('Некорректный формат даты дедлайна', 'danger')
            return redirect(url_for('meetings.tasks', id=meeting.id))
        except Exception as e:
            db.session.rollback()
            logger.error('Ошибка при добавлении задачи: %s', e)
            flash('Произошла ошибка при добавлении задачи', 'danger')
    
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.last_name).all()
    return render_template('meetings/tasks.html', meeting=meeting, employees=employees, today=date.today())


@bp.route('/task/<int:id>/update', methods=['POST'])
@login_required
def update_task(id):
    """Обновление статуса задачи"""
    task = Task.query.get_or_404(id)
    
    status = request.form.get('status', '')
    completion_note = request.form.get('completion_note', '').strip()
    
    # Валидация (Fix #5)
    if status not in ('pending', 'in_progress', 'completed', 'overdue'):
        flash('Некорректный статус задачи', 'danger')
        return redirect(url_for('meetings.tasks', id=task.protocol.meeting_id))
    
    try:  # Fix #7
        task.status = status
        if status == 'completed':
            from datetime import timezone
            task.completed_at = datetime.now(timezone.utc)
        task.completion_note = completion_note
        
        db.session.commit()
        flash('Статус задачи обновлён', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error('Ошибка при обновлении задачи: %s', e)
        flash('Произошла ошибка при обновлении задачи', 'danger')
    
    return redirect(url_for('meetings.tasks', id=task.protocol.meeting_id))


@bp.route('/task/<int:id>/delete', methods=['POST'])
@login_required
@manager_required  # Fix #1
def delete_task(id):
    """Удаление задачи"""
    task = Task.query.get_or_404(id)
    meeting_id = task.protocol.meeting_id
    
    try:  # Fix #7
        db.session.delete(task)
        db.session.commit()
        flash('Задача удалена', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error('Ошибка при удалении задачи: %s', e)
        flash('Произошла ошибка при удалении задачи', 'danger')
    
    return redirect(url_for('meetings.tasks', id=meeting_id))


@bp.route('/types')
@login_required
def types():
    """Управление типами совещаний"""
    types = MeetingType.query.all()
    return render_template('meetings/types.html', types=types)


@bp.route('/types/create', methods=['POST'])
@login_required
@manager_required  # Fix #1
def create_type():
    """Создание типа совещания"""
    name = request.form.get('name', '').strip()
    color = request.form.get('color', '#3788d8')
    description = request.form.get('description', '').strip()
    
    # Валидация (Fix #5)
    if not name:
        flash('Название типа обязательно', 'danger')
        return redirect(url_for('meetings.types'))
    
    try:  # Fix #7
        meeting_type = MeetingType(name=name, color=color, description=description)
        db.session.add(meeting_type)
        db.session.commit()
        flash('Тип совещания создан', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error('Ошибка при создании типа совещания: %s', e)
        flash('Произошла ошибка при создании типа', 'danger')
    
    return redirect(url_for('meetings.types'))


@bp.route('/types/<int:id>/delete', methods=['POST'])
@login_required
@admin_required  # Fix #1
def delete_type(id):
    """Удаление типа совещания"""
    meeting_type = MeetingType.query.get_or_404(id)
    
    try:  # Fix #7
        db.session.delete(meeting_type)
        db.session.commit()
        flash('Тип совещания удалён', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error('Ошибка при удалении типа совещания: %s', e)
        flash('Произошла ошибка при удалении типа', 'danger')
    
    return redirect(url_for('meetings.types'))
