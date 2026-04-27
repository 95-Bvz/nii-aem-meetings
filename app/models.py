from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db, login_manager


# Таблица связи участников совещаний
meeting_participants = db.Table('meeting_participants',
    db.Column('meeting_id', db.Integer, db.ForeignKey('meeting.id'), primary_key=True),
    db.Column('employee_id', db.Integer, db.ForeignKey('employee.id'), primary_key=True),
    db.Column('confirmed', db.Boolean, default=False),
    db.Column('attended', db.Boolean, default=False)
)


class User(UserMixin, db.Model):
    """Модель пользователя системы"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256))
    role = db.Column(db.String(20), default='user')  # admin, manager, user
    is_blocked = db.Column(db.Boolean, default=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    employee = db.relationship('Employee', backref='user_account', uselist=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role == 'admin'
    
    def is_manager(self):
        return self.role in ['admin', 'manager']


@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))


class Department(db.Model):
    """Модель подразделения НИИ АЭМ"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    description = db.Column(db.Text)
    head_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=True)
    
    employees = db.relationship('Employee', backref='department', lazy='dynamic',
                               foreign_keys='Employee.department_id')
    
    def __repr__(self):
        return f'<Подразделение {self.name}>'


class Employee(db.Model):
    """Модель сотрудника"""
    id = db.Column(db.Integer, primary_key=True)
    last_name = db.Column(db.String(100), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    middle_name = db.Column(db.String(100))
    position = db.Column(db.String(200), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    email = db.Column(db.String(120), unique=True)
    phone = db.Column(db.String(20))
    office = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Совещания, организованные сотрудником
    organized_meetings = db.relationship('Meeting', backref='organizer', lazy='dynamic',
                                        foreign_keys='Meeting.organizer_id')
    
    @property
    def full_name(self):
        if self.middle_name:
            return f'{self.last_name} {self.first_name} {self.middle_name}'
        return f'{self.last_name} {self.first_name}'
    
    @property
    def short_name(self):
        result = f'{self.last_name} {self.first_name[0]}.'
        if self.middle_name:
            result += f'{self.middle_name[0]}.'
        return result
    
    def __repr__(self):
        return f'<Сотрудник {self.full_name}>'


class Room(db.Model):
    """Модель переговорной комнаты"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    building = db.Column(db.String(100))
    floor = db.Column(db.Integer)
    room_number = db.Column(db.String(20))
    capacity = db.Column(db.Integer, default=10)
    has_projector = db.Column(db.Boolean, default=False)
    has_video_conf = db.Column(db.Boolean, default=False)
    has_whiteboard = db.Column(db.Boolean, default=True)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    
    meetings = db.relationship('Meeting', backref='room', lazy='dynamic')
    
    @property
    def location(self):
        parts = []
        if self.building:
            parts.append(self.building)
        if self.floor:
            parts.append(f'{self.floor} этаж')
        if self.room_number:
            parts.append(f'каб. {self.room_number}')
        return ', '.join(parts) if parts else 'Не указано'
    
    def check_conflict(self, check_date, start_time, end_time, exclude_id=None):
        """Проверяет конфликт бронирования комнаты. Возвращает конфликтное совещание или None.
        Fix #8, #16 — вынесено из дублированного кода в meetings.py и rooms.py.
        """
        query = Meeting.query.filter(
            Meeting.room_id == self.id,
            Meeting.date == check_date,
            Meeting.status != 'cancelled',
            db.or_(
                db.and_(Meeting.start_time <= start_time, Meeting.end_time > start_time),
                db.and_(Meeting.start_time < end_time, Meeting.end_time >= end_time),
                db.and_(Meeting.start_time >= start_time, Meeting.end_time <= end_time)
            )
        )
        if exclude_id:
            query = query.filter(Meeting.id != exclude_id)
        return query.first()
    
    def __repr__(self):
        return f'<Комната {self.name}>'


class MeetingType(db.Model):
    """Тип совещания/мероприятия"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    color = db.Column(db.String(7), default='#3788d8')  # HEX цвет для календаря
    description = db.Column(db.Text)
    
    meetings = db.relationship('Meeting', backref='meeting_type', lazy='dynamic')
    
    def __repr__(self):
        return f'<Тип {self.name}>'


class Meeting(db.Model):
    """Модель совещания/мероприятия"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    agenda = db.Column(db.Text)  # Повестка дня
    
    date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    
    type_id = db.Column(db.Integer, db.ForeignKey('meeting_type.id'))
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'))
    organizer_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    
    status = db.Column(db.String(20), default='planned')  # planned, ongoing, completed, cancelled
    is_recurring = db.Column(db.Boolean, default=False)
    recurrence_pattern = db.Column(db.String(50))  # weekly, monthly, etc.
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))
    
    # Участники совещания
    participants = db.relationship('Employee', secondary=meeting_participants,
                                  backref=db.backref('meetings', lazy='dynamic'))
    
    # Протокол совещания
    protocol = db.relationship('Protocol', backref='meeting', uselist=False)
    
    @property
    def datetime_start(self):
        return datetime.combine(self.date, self.start_time)
    
    @property
    def datetime_end(self):
        return datetime.combine(self.date, self.end_time)
    
    @property
    def duration_minutes(self):
        start = datetime.combine(self.date, self.start_time)
        end = datetime.combine(self.date, self.end_time)
        return int((end - start).total_seconds() / 60)
    
    @property
    def status_display(self):
        statuses = {
            'planned': 'Запланировано',
            'ongoing': 'Проводится',
            'completed': 'Завершено',
            'cancelled': 'Отменено'
        }
        return statuses.get(self.status, self.status)
    
    def __repr__(self):
        return f'<Совещание {self.title}>'


class Protocol(db.Model):
    """Протокол совещания"""
    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey('meeting.id'), nullable=False, unique=True)
    number = db.Column(db.String(50))  # Номер протокола
    
    content = db.Column(db.Text)  # Основное содержание
    decisions = db.Column(db.Text)  # Принятые решения
    
    secretary_id = db.Column(db.Integer, db.ForeignKey('employee.id'))
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))
    
    secretary = db.relationship('Employee', backref='protocols_as_secretary')
    tasks = db.relationship('Task', backref='protocol', lazy='dynamic')
    
    def __repr__(self):
        return f'<Протокол №{self.number}>'


class Task(db.Model):
    """Задача/поручение из протокола"""
    id = db.Column(db.Integer, primary_key=True)
    protocol_id = db.Column(db.Integer, db.ForeignKey('protocol.id'), nullable=False)
    
    description = db.Column(db.Text, nullable=False)
    responsible_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    deadline = db.Column(db.Date)
    
    status = db.Column(db.String(20), default='pending')  # pending, in_progress, completed, overdue
    completion_note = db.Column(db.Text)
    completed_at = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    responsible = db.relationship('Employee', backref='assigned_tasks')
    
    @property
    def status_display(self):
        statuses = {
            'pending': 'Ожидает',
            'in_progress': 'В работе',
            'completed': 'Выполнено',
            'overdue': 'Просрочено'
        }
        return statuses.get(self.status, self.status)
    
    def __repr__(self):
        return f'<Задача {self.id}>'
