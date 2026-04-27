import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse
from app import db
from app.models import User

bp = Blueprint('auth', __name__, url_prefix='/auth')
logger = logging.getLogger(__name__)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))  # Fix #10
        
        # Валидация (Fix #5)
        if not username or not password:
            flash('Введите имя пользователя и пароль', 'danger')
            return redirect(url_for('auth.login'))
        
        user = User.query.filter_by(username=username).first()
        
        if user is None or not user.check_password(password):
            logger.warning('Неудачная попытка входа: %s', username)
            flash('Неверное имя пользователя или пароль', 'danger')
            return redirect(url_for('auth.login'))
        
        if user.is_blocked:
            logger.warning('Попытка входа заблокированного пользователя: %s', username)
            flash('Ваш аккаунт заблокирован. Обратитесь к администратору.', 'danger')
            return redirect(url_for('auth.login'))
        
        login_user(user, remember=remember)
        logger.info('Пользователь вошёл: %s', username)
        
        next_page = request.args.get('next')
        if not next_page or urlparse(next_page).netloc != '':
            next_page = url_for('main.index')
        
        flash('Вы успешно вошли в систему!', 'success')
        return redirect(next_page)
    
    return render_template('auth/login.html')


@bp.route('/logout')
@login_required
def logout():
    """Выход из системы"""
    logger.info('Пользователь вышел: %s', current_user.username)
    logout_user()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('auth.login'))


@bp.route('/register', methods=['GET', 'POST'])
def register():
    """Страница регистрации"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')
        
        # Валидация (Fix #5)
        if not username or len(username) < 3:
            flash('Имя пользователя должно содержать минимум 3 символа', 'danger')
            return redirect(url_for('auth.register'))
        
        if not email or '@' not in email:
            flash('Введите корректный email', 'danger')
            return redirect(url_for('auth.register'))
        
        if not password or len(password) < 6:
            flash('Пароль должен содержать минимум 6 символов', 'danger')
            return redirect(url_for('auth.register'))
        
        if password != password2:
            flash('Пароли не совпадают', 'danger')
            return redirect(url_for('auth.register'))
        
        if User.query.filter_by(username=username).first():
            flash('Это имя пользователя уже занято', 'danger')
            return redirect(url_for('auth.register'))
        
        if User.query.filter_by(email=email).first():
            flash('Этот email уже зарегистрирован', 'danger')
            return redirect(url_for('auth.register'))
        
        try:  # Fix #7
            user = User(username=username, email=email)
            user.set_password(password)
            
            # Первый пользователь становится администратором
            if User.query.count() == 0:
                user.role = 'admin'
            
            db.session.add(user)
            db.session.commit()
            logger.info('Зарегистрирован новый пользователь: %s', username)
            
            flash('Регистрация успешна! Теперь вы можете войти.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            logger.error('Ошибка при регистрации: %s', e)
            flash('Произошла ошибка при регистрации', 'danger')
            return redirect(url_for('auth.register'))
    
    return render_template('auth/register.html')


@bp.route('/profile')
@login_required
def profile():
    """Профиль пользователя"""
    return render_template('auth/profile.html')


@bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Редактирование профиля"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        
        # Валидация (Fix #5)
        if not email or '@' not in email:
            flash('Введите корректный email', 'danger')
            return redirect(url_for('auth.edit_profile'))
        
        try:  # Fix #7
            if email != current_user.email:
                if User.query.filter_by(email=email).first():
                    flash('Этот email уже используется', 'danger')
                    return redirect(url_for('auth.edit_profile'))
                current_user.email = email
            
            # Смена пароля
            new_password = request.form.get('new_password', '')
            if new_password:
                if len(new_password) < 6:
                    flash('Новый пароль должен содержать минимум 6 символов', 'danger')
                    return redirect(url_for('auth.edit_profile'))
                current_password = request.form.get('current_password', '')
                if not current_user.check_password(current_password):
                    flash('Неверный текущий пароль', 'danger')
                    return redirect(url_for('auth.edit_profile'))
                current_user.set_password(new_password)
            
            db.session.commit()
            flash('Профиль обновлён', 'success')
            return redirect(url_for('auth.profile'))
        except Exception as e:
            db.session.rollback()
            logger.error('Ошибка при обновлении профиля: %s', e)
            flash('Произошла ошибка при обновлении профиля', 'danger')
            return redirect(url_for('auth.edit_profile'))
    
    return render_template('auth/edit_profile.html')


# === Админ-панель управления пользователями ===

@bp.route('/admin/users')
@login_required
def admin_users():
    """Список пользователей (только для admin)"""
    if not current_user.is_admin():
        abort(403)
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('auth/admin_users.html', users=users)


@bp.route('/admin/users/<int:id>/role', methods=['POST'])
@login_required
def change_role(id):
    """Изменение роли пользователя"""
    if not current_user.is_admin():
        abort(403)
    
    user = User.query.get_or_404(id)
    
    if user.id == current_user.id:
        flash('Нельзя изменить свою собственную роль', 'danger')
        return redirect(url_for('auth.admin_users'))
    
    new_role = request.form.get('role', '')
    if new_role not in ('admin', 'manager', 'user'):
        flash('Некорректная роль', 'danger')
        return redirect(url_for('auth.admin_users'))
    
    user.role = new_role
    db.session.commit()
    logger.info('Роль пользователя %s изменена на %s', user.username, new_role)
    flash(f'Роль пользователя {user.username} изменена на «{new_role}»', 'success')
    return redirect(url_for('auth.admin_users'))


@bp.route('/admin/users/<int:id>/toggle-block', methods=['POST'])
@login_required
def toggle_block(id):
    """Блокировка/разблокировка пользователя"""
    if not current_user.is_admin():
        abort(403)
    
    user = User.query.get_or_404(id)
    
    if user.id == current_user.id:
        flash('Нельзя заблокировать самого себя', 'danger')
        return redirect(url_for('auth.admin_users'))
    
    user.is_blocked = not user.is_blocked
    db.session.commit()
    
    status = 'заблокирован' if user.is_blocked else 'разблокирован'
    logger.info('Пользователь %s %s', user.username, status)
    flash(f'Пользователь {user.username} {status}', 'success')
    return redirect(url_for('auth.admin_users'))


@bp.route('/admin/users/<int:id>/delete', methods=['POST'])
@login_required
def delete_user(id):
    """Удаление пользователя"""
    if not current_user.is_admin():
        abort(403)
    
    user = User.query.get_or_404(id)
    
    if user.id == current_user.id:
        flash('Нельзя удалить самого себя', 'danger')
        return redirect(url_for('auth.admin_users'))
    
    username = user.username
    try:
        db.session.delete(user)
        db.session.commit()
        logger.info('Пользователь удалён: %s', username)
        flash(f'Пользователь {username} удалён', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error('Ошибка при удалении пользователя: %s', e)
        flash('Произошла ошибка при удалении', 'danger')
    
    return redirect(url_for('auth.admin_users'))
