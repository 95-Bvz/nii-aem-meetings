"""
Скрипт инициализации базы данных с тестовыми данными
для Информационной системы планирования совещаний НИИ АЭМ
"""
from datetime import date, time, timedelta
import random
from app import create_app, db
from app.models import User, Department, Employee, Room, MeetingType, Meeting, Protocol, Task

app = create_app()

def init_database():
    with app.app_context():
        # Создаём таблицы
        db.create_all()
        
        # Проверяем, есть ли уже данные
        if User.query.first():
            print("База данных уже содержит данные. Пропускаем инициализацию.")
            return
        
        print("Инициализация базы данных...")
        
        # === Создаём администратора ===
        admin = User(username='admin', email='admin@nii-aem.ru', role='admin')
        admin.set_password('admin123')
        db.session.add(admin)
        
        manager = User(username='manager', email='manager@nii-aem.ru', role='manager')
        manager.set_password('manager123')
        db.session.add(manager)
        
        user = User(username='user', email='user@nii-aem.ru', role='user')
        user.set_password('user123')
        db.session.add(user)
        
        print("✓ Пользователи созданы")
        
        # === Подразделения ===
        departments_data = [
            ('ОГК', 'Отдел главного конструктора', 'Проектирование и разработка'),
            ('ОГТ', 'Отдел главного технолога', 'Технологическое обеспечение'),
            ('ОТК', 'Отдел технического контроля', 'Контроль качества продукции'),
            ('ПЭО', 'Планово-экономический отдел', 'Планирование и экономика'),
            ('ИТ', 'Отдел информационных технологий', 'IT-поддержка и разработка'),
            ('НИЛ', 'Научно-исследовательская лаборатория', 'Научные исследования'),
            ('АДМ', 'Администрация', 'Административное управление'),
        ]
        
        departments = []
        for code, name, desc in departments_data:
            dept = Department(code=code, name=name, description=desc)
            db.session.add(dept)
            departments.append(dept)
        
        print("✓ Подразделения созданы")
        
        # === Сотрудники ===
        employees_data = [
            ('Иванов', 'Иван', 'Иванович', 'Директор НИИ', 6),
            ('Петров', 'Пётр', 'Петрович', 'Заместитель директора', 6),
            ('Сидорова', 'Анна', 'Михайловна', 'Главный конструктор', 0),
            ('Козлов', 'Алексей', 'Сергеевич', 'Ведущий инженер-конструктор', 0),
            ('Новикова', 'Елена', 'Владимировна', 'Инженер-конструктор', 0),
            ('Морозов', 'Дмитрий', 'Андреевич', 'Главный технолог', 1),
            ('Волкова', 'Ольга', 'Игоревна', 'Технолог', 1),
            ('Соколов', 'Николай', 'Васильевич', 'Начальник ОТК', 2),
            ('Лебедева', 'Мария', 'Александровна', 'Контролёр ОТК', 2),
            ('Кузнецов', 'Сергей', 'Николаевич', 'Начальник ПЭО', 3),
            ('Попова', 'Татьяна', 'Дмитриевна', 'Экономист', 3),
            ('Васильев', 'Андрей', 'Олегович', 'Начальник IT-отдела', 4),
            ('Михайлова', 'Ирина', 'Сергеевна', 'Системный администратор', 4),
            ('Фёдоров', 'Виктор', 'Александрович', 'Программист', 4),
            ('Николаев', 'Павел', 'Викторович', 'Заведующий лабораторией', 5),
            ('Егорова', 'Светлана', 'Павловна', 'Научный сотрудник', 5),
            ('Орлов', 'Михаил', 'Игоревич', 'Младший научный сотрудник', 5),
        ]
        
        employees = []
        for last, first, middle, position, dept_idx in employees_data:
            emp = Employee(
                last_name=last,
                first_name=first,
                middle_name=middle,
                position=position,
                department_id=None,  # Установим после commit
                email=f'{last.lower()}@nii-aem.ru',
                phone=f'+7 (495) {random.randint(100,999)}-{random.randint(10,99)}-{random.randint(10,99)}',
                office=str(random.randint(100, 500))
            )
            employees.append((emp, dept_idx))
        
        db.session.flush()
        
        # Устанавливаем подразделения
        for emp, dept_idx in employees:
            emp.department_id = departments[dept_idx].id
            db.session.add(emp)
        
        print("✓ Сотрудники созданы")
        
        # === Переговорные комнаты ===
        rooms_data = [
            ('Конференц-зал №1', 'Главный корпус', 1, '101', 50, True, True, True),
            ('Конференц-зал №2', 'Главный корпус', 2, '201', 30, True, True, True),
            ('Переговорная "А"', 'Главный корпус', 3, '305', 12, True, False, True),
            ('Переговорная "Б"', 'Главный корпус', 3, '310', 8, False, False, True),
            ('Зал совещаний ОГК', 'Корпус Б', 2, '215', 15, True, True, True),
            ('Малый зал', 'Главный корпус', 4, '401', 6, False, True, True),
        ]
        
        rooms = []
        for name, building, floor, room_num, capacity, proj, video, board in rooms_data:
            room = Room(
                name=name,
                building=building,
                floor=floor,
                room_number=room_num,
                capacity=capacity,
                has_projector=proj,
                has_video_conf=video,
                has_whiteboard=board
            )
            db.session.add(room)
            rooms.append(room)
        
        print("✓ Переговорные комнаты созданы")
        
        # === Типы совещаний ===
        types_data = [
            ('Планёрка', '#3498db', 'Регулярное планирование работ'),
            ('Техническое совещание', '#27ae60', 'Обсуждение технических вопросов'),
            ('Совещание руководства', '#e74c3c', 'Совещание руководителей подразделений'),
            ('Научный совет', '#9b59b6', 'Научно-технический совет'),
            ('Рабочая встреча', '#f39c12', 'Оперативные рабочие вопросы'),
            ('Совещание по проекту', '#1abc9c', 'Обсуждение хода проекта'),
        ]
        
        meeting_types = []
        for name, color, desc in types_data:
            mt = MeetingType(name=name, color=color, description=desc)
            db.session.add(mt)
            meeting_types.append(mt)
        
        print("✓ Типы совещаний созданы")
        
        db.session.flush()
        
        # === Совещания ===
        today = date.today()
        employee_list = [emp for emp, _ in employees]
        
        meetings_data = [
            # Прошедшие совещания
            ('Планёрка ОГК', today - timedelta(days=7), time(9, 0), time(10, 0), 0, 0, 2, 'completed'),
            ('Техсовет по проекту АЭС-2006', today - timedelta(days=5), time(14, 0), time(16, 0), 1, 1, 0, 'completed'),
            ('Совещание директората', today - timedelta(days=3), time(10, 0), time(12, 0), 2, 0, 0, 'completed'),
            
            # Сегодняшние
            ('Еженедельная планёрка', today, time(9, 0), time(10, 0), 0, 2, 2, 'planned'),
            ('Обсуждение технической документации', today, time(14, 0), time(15, 30), 1, 4, 2, 'planned'),
            
            # Будущие
            ('Научный совет: результаты Q1', today + timedelta(days=2), time(10, 0), time(13, 0), 3, 0, 14, 'planned'),
            ('Рабочая встреча IT и ПЭО', today + timedelta(days=3), time(11, 0), time(12, 0), 4, 5, 11, 'planned'),
            ('Совещание по модернизации', today + timedelta(days=5), time(14, 0), time(16, 0), 5, 1, 0, 'planned'),
            ('Планёрка ОГТ', today + timedelta(days=7), time(9, 0), time(10, 0), 0, 4, 5, 'planned'),
        ]
        
        meetings = []
        for title, m_date, start, end, type_idx, room_idx, org_idx, status in meetings_data:
            meeting = Meeting(
                title=title,
                date=m_date,
                start_time=start,
                end_time=end,
                type_id=meeting_types[type_idx].id,
                room_id=rooms[room_idx].id,
                organizer_id=employee_list[org_idx].id,
                status=status,
                description=f'Совещание по теме: {title}',
                agenda='1. Вступительное слово\n2. Основные вопросы\n3. Обсуждение\n4. Принятие решений\n5. Разное'
            )
            
            # Добавляем случайных участников
            num_participants = random.randint(3, 8)
            participants = random.sample(employee_list, min(num_participants, len(employee_list)))
            meeting.participants = participants
            
            db.session.add(meeting)
            meetings.append(meeting)
        
        print("✓ Совещания созданы")
        
        db.session.flush()
        
        # === Протоколы для завершённых совещаний ===
        for i, meeting in enumerate(meetings[:3]):  # Первые 3 завершённые
            protocol = Protocol(
                meeting_id=meeting.id,
                number=f'{i+1}/2024',
                content='По результатам обсуждения были рассмотрены все вопросы повестки дня.',
                decisions='1. Продолжить работу согласно плану.\n2. Подготовить отчёт к следующему совещанию.',
                secretary_id=random.choice(employee_list).id
            )
            db.session.add(protocol)
            db.session.flush()
            
            # Добавляем задачи
            for j in range(random.randint(2, 4)):
                task = Task(
                    protocol_id=protocol.id,
                    description=f'Задача {j+1}: Выполнить работы по направлению {j+1}',
                    responsible_id=random.choice(employee_list).id,
                    deadline=today + timedelta(days=random.randint(7, 30)),
                    status=random.choice(['pending', 'in_progress', 'completed'])
                )
                db.session.add(task)
        
        print("✓ Протоколы и задачи созданы")
        
        db.session.commit()
        print("\n" + "="*50)
        print("База данных успешно инициализирована!")
        print("="*50)
        print("\nУчётные записи для входа:")
        print("  Администратор: admin / admin123")
        print("  Менеджер:      manager / manager123")
        print("  Пользователь:  user / user123")
        print("\nДля запуска приложения выполните: python run.py")


if __name__ == '__main__':
    init_database()
