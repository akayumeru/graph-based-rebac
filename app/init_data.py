from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

class DataInitializer:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
            auth=(
                os.getenv("NEO4J_USERNAME", "neo4j"),
                os.getenv("NEO4J_PASSWORD", "ktrwbz123")
            )
        )

    def is_database_empty(self):
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (n)
                RETURN count(n) AS count
                """
            ).single()
            return result["count"] == 0

    def create_academic_structure(self):
        roles = [
            ("rector", "Ректор института", 100),
            ("prorector", "Проректор", 90),
            ("dean", "Декан факультета", 80),
            ("kaf_head", "Заведующий кафедрой", 70),
            ("professor", "Преподаватель (профессор)", 60),
            ("associate_professor", "Доцент", 50),
            ("assistant", "Ассистент", 40),
            ("student", "Студент", 10)
        ]
        
        with self.driver.session() as session:
            for role_key, description, level in roles:
                session.run(
                    """
                    MERGE (r:Role {key: $key})
                    SET r.description = $description
                    """,
                    key=role_key, description=description, level=level
                )
            
            session.run("""
                MATCH (child:Role {key: 'rector'})
                MATCH (parent:Role {key: 'prorector'})
                MERGE (child)-[:ROLE_INHERITS]->(parent)
            """)
            
            session.run("""
                MATCH (child:Role {key: 'prorector'})
                MATCH (parent:Role {key: 'dean'})
                MERGE (child)-[:ROLE_INHERITS]->(parent)
            """)
            
            session.run("""
                MATCH (child:Role {key: 'dean'})
                MATCH (parent:Role {key: 'kaf_head'})
                MERGE (child)-[:ROLE_INHERITS]->(parent)
            """)
            
            session.run("""
                MATCH (child:Role {key: 'kaf_head'})
                MATCH (parent:Role {key: 'professor'})
                MERGE (child)-[:ROLE_INHERITS]->(parent)
            """)
            
            session.run("""
                MATCH (child:Role {key: 'professor'})
                MATCH (parent:Role {key: 'associate_professor'})
                MERGE (child)-[:ROLE_INHERITS]->(parent)
            """)
            
            session.run("""
                MATCH (child:Role {key: 'associate_professor'})
                MATCH (parent:Role {key: 'assistant'})
                MERGE (child)-[:ROLE_INHERITS]->(parent)
            """)
            
            print("  Иерархия ролей создана")

    def create_permissions(self):
        
        permissions = [
            ("university:manage", "Управление университетом"),
            ("university:finance", "Управление финансами"),
            ("university:strategy", "Стратегическое планирование"),
            
            ("faculty:manage", "Управление факультетом"),
            ("faculty:schedule", "Управление расписанием"),
            ("faculty:staff", "Управление персоналом"),
            
            ("department:manage", "Управление кафедрой"),
            ("department:courses", "Управление курсами"),
            
            ("teaching:create", "Создание учебных материалов"),
            ("teaching:grade", "Выставление оценок"),
            ("teaching:attendance", "Отметка посещаемости"),
            ("teaching:consult", "Проведение консультаций"),
         
            ("education:view_grades", "Просмотр своих оценок"),
            ("education:view_schedule", "Просмотр расписания"),
            ("education:enroll", "Запись на ДВС"),
       
            ("common:view_profile", "Просмотр профиля"),
            ("common:edit_profile", "Редактирование профиля")
        ]
        
        with self.driver.session() as session:
            for key, description in permissions:
                session.run(
                    """
                    MERGE (p:Permission {key: $key})
                    SET p.description = $description
                    """,
                    key=key, description=description
                )
            print("  Права доступа созданы")

    def assign_permissions_to_roles(self):
        role_permissions = {
            'rector': [
                'university:manage', 'university:finance', 'university:strategy',
                'faculty:manage', 'department:manage'
            ],
            'prorector': [
                'university:finance', 'university:strategy',
                'faculty:manage', 'faculty:schedule'
            ],
            'dean': [
                'faculty:manage', 'faculty:schedule', 'faculty:staff',
                'department:manage', 'department:courses'
            ],
            'kaf_head': [
                'department:manage', 'department:courses',
                'teaching:create', 'teaching:grade'
            ],
            'professor': [
                'teaching:create', 'teaching:grade', 'teaching:attendance',
                'teaching:consult', 'department:courses'
            ],
            'associate_professor': [
                'teaching:create', 'teaching:grade', 'teaching:attendance'
            ],
            'assistant': [
                'teaching:attendance', 'teaching:consult',
                'education:view_grades', 'education:view_schedule'
            ],
            'student': [
                'education:view_grades', 'education:view_schedule',
                'education:enroll', 'common:view_profile', 'common:edit_profile'
            ]
        }
        
        with self.driver.session() as session:
            for role_key, permissions in role_permissions.items():
                for perm_key in permissions:
                    session.run("""
                        MATCH (r:Role {key: $role_key})
                        MATCH (p:Permission {key: $perm_key})
                        MERGE (r)-[:ROLE_HAS_PERMISSION]->(p)
                    """, role_key=role_key, perm_key=perm_key)
            print("  Права назначены ролям")

    def create_test_users(self):
        
        test_users = [
            ("rector_ivanov", "Иванов И.И.", "rector", "university"),
            ("prorector_petrov", "Петров П.П.", "prorector", "university"),
            ("dean_sidorov", "Сидоров С.С.", "dean", "fit"),
            ("dean_smirnova", "Смирнова А.А.", "dean", "fem"),
            ("hod_kozlova", "Козлова Е.В.", "kaf_head", "cs"),
            ("prof_volkov", "Волков В.В.", "professor", "cs"),
            ("assoc_morozov", "Морозов Д.С.", "associate_professor", "cs"),
            ("assist_sokolova", "Соколова М.И.", "assistant", "cs"),
            ("student_001", "Алексеев Алексей", "student", "cs-31"),
            ("student_002", "Борисова Елена", "student", "cs-31"),
            ("student_003", "Васильев Дмитрий", "student", "cs-32")
        ]
        
        with self.driver.session() as session:
            for user_id, name, role_key, scope in test_users:
                session.run("""
                    MERGE (u:User {user_id: $user_id})
                    SET u.name = $name
                """, user_id=user_id, name=name)
   
                session.run("""
                    MATCH (u:User {user_id: $user_id})
                    MATCH (r:Role {key: $role_key})
                    MERGE (u)-[:HAS_ROLE {scope: $scope}]->(r)
                """, user_id=user_id, role_key=role_key, scope=scope)
            
            print("  Тестовые пользователи созданы")

    def init_default_data(self):
        print("\nапуск инициализации данных...")
        
        print("Создание академической структуры...")
        self.create_academic_structure()
        
        print("Создание прав доступа...")
        self.create_permissions()
        
        print("Назначение прав ролям...")
        self.assign_permissions_to_roles()
        
        print("Создание тестовых пользователей...")
        self.create_test_users()
        
        print("Инициализация данных завершена успешно!\n")

    def run(self):
        try:
            with self.driver.session() as session:
                session.run("RETURN 1")
            
            if self.is_database_empty():
                print(" База данных пуста. Загружаем данные по умолчанию...")
                self.init_default_data()
            else:
                print(" База данных уже содержит данные. Пропускаем инициализацию.")
                
                with self.driver.session() as session:
                    result = session.run("""
                        MATCH (r:Role) 
                        RETURN r.key AS role, r.description AS desc
                        ORDER BY r.level DESC
                    """)
                    roles = list(result)
                    if roles:
                        print("\n Существующие роли в БД:")
                        for r in roles:
                            print(f"  • {r['role']}: {r['desc']}")
                
        except Exception as e:
            print(f" Ошибка при инициализации данных: {e}")
            raise
        finally:
            self.driver.close()

if __name__ == "__main__":
    initializer = DataInitializer()
    initializer.run()