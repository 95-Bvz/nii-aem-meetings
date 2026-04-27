import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Employee, Department
from app.decorators import manager_required, admin_required

bp = Blueprint('employees', __name__, url_prefix='/employees')
logger = logging.getLogger(__name__)


def _escape_like(search_term):
    """Экранирует спецсимволы для LIKE/ILIKE запросов (Fix #2)."""
    return search_term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


@bp.route('/')
@login_required
def index():
    """Список сотрудников"""
    page = request.args.get('page', 1, type=int)
    department_id = request.args.get('department_id', type=int)
    search = request.args.get('search', '').strip()
    
    query = Employee.query.filter_by(is_active=True)
    
    if department_id:
        query = query.filter(Employee.department_id == department_id)
    
    if search:
        safe_search = _escape_like(search)  # Fix #2
        query = query.filter(
            db.or_(
                Employee.last_name.ilike(f'%{safe_search}%', escape='\\'),
                Employee.first_name.ilike(f'%{safe_search}%', escape='\\'),
                Employee.position.ilike(f'%{safe_search}%', escape='\\')
            )
        )
    
    employees = query.order_by(Employee.last_name).paginate(
        page=page, per_page=15, error_out=False
    )
    
    departments = Department.query.all()
    
    return render_template('employees/index.html', 
                          employees=employees, departments=departments)


@bp.route('/create', methods=['GET', 'POST'])
@login_required
@manager_required  # Fix #1
def create():
    """Создание сотрудника"""
    if request.method == 'POST':
        last_name = request.form.get('last_name', '').strip()
        first_name = request.form.get('first_name', '').strip()
        position = request.form.get('position', '').strip()
        
        # Валидация (Fix #5)
        if not last_name or not first_name:
            flash('Фамилия и имя обязательны', 'danger')
            departments = Department.query.all()
            return redirect(url_for('employees.create'))
        
        if not position:
            flash('Должность обязательна', 'danger')
            return redirect(url_for('employees.create'))
        
        try:  # Fix #7
            employee = Employee(
                last_name=last_name,
                first_name=first_name,
                middle_name=request.form.get('middle_name', '').strip(),
                position=position,
                department_id=request.form.get('department_id', type=int) or None,
                email=request.form.get('email', '').strip() or None,
                phone=request.form.get('phone', '').strip(),
                office=request.form.get('office', '').strip()
            )
            
            db.session.add(employee)
            db.session.commit()
            logger.info('Сотрудник создан: %s (id=%s)', employee.full_name, employee.id)
            
            flash('Сотрудник добавлен', 'success')
            return redirect(url_for('employees.view', id=employee.id))
        except Exception as e:
            db.session.rollback()
            logger.error('Ошибка при создании сотрудника: %s', e)
            flash('Произошла ошибка при добавлении сотрудника', 'danger')
            return redirect(url_for('employees.create'))
    
    departments = Department.query.all()
    return render_template('employees/create.html', departments=departments)


@bp.route('/<int:id>')
@login_required
def view(id):
    """Просмотр сотрудника"""
    employee = Employee.query.get_or_404(id)
    
    # Получаем статистику участия в совещаниях
    meetings_count = employee.meetings.count()
    organized_count = employee.organized_meetings.count()
    tasks_count = len(employee.assigned_tasks)
    
    return render_template('employees/view.html', 
                          employee=employee,
                          meetings_count=meetings_count,
                          organized_count=organized_count,
                          tasks_count=tasks_count)


@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@manager_required  # Fix #1
def edit(id):
    """Редактирование сотрудника"""
    employee = Employee.query.get_or_404(id)
    
    if request.method == 'POST':
        last_name = request.form.get('last_name', '').strip()
        first_name = request.form.get('first_name', '').strip()
        position = request.form.get('position', '').strip()
        
        # Валидация (Fix #5)
        if not last_name or not first_name:
            flash('Фамилия и имя обязательны', 'danger')
            return redirect(url_for('employees.edit', id=employee.id))
        
        if not position:
            flash('Должность обязательна', 'danger')
            return redirect(url_for('employees.edit', id=employee.id))
        
        try:  # Fix #7
            employee.last_name = last_name
            employee.first_name = first_name
            employee.middle_name = request.form.get('middle_name', '').strip()
            employee.position = position
            employee.department_id = request.form.get('department_id', type=int) or None
            employee.email = request.form.get('email', '').strip() or None
            employee.phone = request.form.get('phone', '').strip()
            employee.office = request.form.get('office', '').strip()
            
            db.session.commit()
            logger.info('Сотрудник обновлён: id=%s', employee.id)
            flash('Данные сотрудника обновлены', 'success')
            return redirect(url_for('employees.view', id=employee.id))
        except Exception as e:
            db.session.rollback()
            logger.error('Ошибка при обновлении сотрудника: %s', e)
            flash('Произошла ошибка при обновлении', 'danger')
            return redirect(url_for('employees.edit', id=employee.id))
    
    departments = Department.query.all()
    return render_template('employees/edit.html', employee=employee, departments=departments)


@bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required  # Fix #1
def delete(id):
    """Удаление (деактивация) сотрудника"""
    employee = Employee.query.get_or_404(id)
    employee.is_active = False
    db.session.commit()
    logger.info('Сотрудник деактивирован: id=%s', id)
    
    flash('Сотрудник деактивирован', 'success')
    return redirect(url_for('employees.index'))


# === Подразделения ===

@bp.route('/departments')
@login_required
def departments():
    """Список подразделений"""
    departments = Department.query.all()
    return render_template('employees/departments.html', departments=departments)


@bp.route('/departments/create', methods=['GET', 'POST'])
@login_required
@manager_required  # Fix #1
def create_department():
    """Создание подразделения"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        code = request.form.get('code', '').strip()
        
        # Валидация (Fix #5)
        if not name or not code:
            flash('Название и код подразделения обязательны', 'danger')
            return redirect(url_for('employees.create_department'))
        
        try:  # Fix #7
            department = Department(
                name=name,
                code=code,
                description=request.form.get('description', '').strip()
            )
            
            db.session.add(department)
            db.session.commit()
            logger.info('Подразделение создано: %s', name)
            
            flash('Подразделение создано', 'success')
            return redirect(url_for('employees.departments'))
        except Exception as e:
            db.session.rollback()
            logger.error('Ошибка при создании подразделения: %s', e)
            flash('Произошла ошибка при создании подразделения', 'danger')
            return redirect(url_for('employees.create_department'))
    
    return render_template('employees/create_department.html')


@bp.route('/departments/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@manager_required  # Fix #1
def edit_department(id):
    """Редактирование подразделения"""
    department = Department.query.get_or_404(id)
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        code = request.form.get('code', '').strip()
        
        # Валидация (Fix #5)
        if not name or not code:
            flash('Название и код подразделения обязательны', 'danger')
            return redirect(url_for('employees.edit_department', id=id))
        
        try:  # Fix #7
            department.name = name
            department.code = code
            department.description = request.form.get('description', '').strip()
            department.head_id = request.form.get('head_id', type=int) or None
            
            db.session.commit()
            logger.info('Подразделение обновлено: id=%s', id)
            flash('Подразделение обновлено', 'success')
            return redirect(url_for('employees.departments'))
        except Exception as e:
            db.session.rollback()
            logger.error('Ошибка при обновлении подразделения: %s', e)
            flash('Произошла ошибка при обновлении', 'danger')
            return redirect(url_for('employees.edit_department', id=id))
    
    employees = Employee.query.filter_by(is_active=True, department_id=id).all()
    return render_template('employees/edit_department.html', 
                          department=department, employees=employees)


@bp.route('/departments/<int:id>/delete', methods=['POST'])
@login_required
@admin_required  # Fix #1
def delete_department(id):
    """Удаление подразделения"""
    department = Department.query.get_or_404(id)
    
    # Проверяем, есть ли сотрудники в подразделении
    if department.employees.count() > 0:
        flash('Невозможно удалить подразделение с сотрудниками', 'danger')
        return redirect(url_for('employees.departments'))
    
    try:  # Fix #7
        db.session.delete(department)
        db.session.commit()
        logger.info('Подразделение удалено: id=%s', id)
        flash('Подразделение удалено', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error('Ошибка при удалении подразделения: %s', e)
        flash('Произошла ошибка при удалении', 'danger')
    
    return redirect(url_for('employees.departments'))
