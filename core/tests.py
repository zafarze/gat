# D:\GAT\core\tests.py (ОБНОВЛЕННАЯ ВЕРСИЯ ДЛЯ ЦЕНТРА ВОПРОСОВ)

from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
import pandas as pd
import io
import datetime

from .models import (
    AcademicYear, Quarter, School, SchoolClass, Subject,
    GatTest, Student, StudentResult, StudentAnswer,
    QuestionTopic, BankQuestion, BankAnswerOption, QuestionCount
)
from .services import process_student_results_upload, validate_question_counts

class ServicesTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        """
        Подготавливает начальные данные в базе один раз для всего набора тестов.
        """
        # Создаем пользователя для автора
        cls.user = User.objects.create_user(
            username='testuser', 
            password='testpass123'
        )
        
        cls.year = AcademicYear.objects.create(
            name="2025", 
            start_date="2025-09-01", 
            end_date="2026-05-31"
        )
        cls.quarter = Quarter.objects.create(
            name="1 четверть", 
            year=cls.year, 
            start_date="2025-09-01", 
            end_date="2025-10-31"
        )
        cls.school = School.objects.create(
            school_id="SCH01", 
            name="Тестовая Школа", 
            address="Тестовый адрес"
        )

        # Создаем "базовый" класс "10", к которому будет привязан тест
        cls.base_class = SchoolClass.objects.create(
            name="10", 
            school=cls.school
        )

        # Создаем предметы (теперь без привязки к школе)
        cls.math = Subject.objects.create(
            name="Математика", 
            abbreviation="МАТ"
        )
        cls.phys = Subject.objects.create(
            name="Физика", 
            abbreviation="ФИЗ"
        )

        # Создаем GAT-тест, привязанный к параллели "10"
        cls.gat_test = GatTest.objects.create(
            name="GAT для 10-х классов",
            test_number=1,
            test_date=datetime.date.today(),
            quarter=cls.quarter,
            school=cls.school,      
            school_class=cls.base_class
        )

        # Создаем темы вопросов
        cls.math_topic = QuestionTopic.objects.create(
            name="Алгебра",
            subject=cls.math,
            school_class=cls.base_class,
            author=cls.user
        )
        
        cls.phys_topic = QuestionTopic.objects.create(
            name="Механика",
            subject=cls.phys,
            school_class=cls.base_class,
            author=cls.user
        )

        # Создаем вопросы из банка
        cls.math_question1 = BankQuestion.objects.create(
            topic=cls.math_topic,
            subject=cls.math,
            school_class=cls.base_class,
            text="Сколько будет 2 + 2?",
            difficulty="EASY",
            author=cls.user
        )
        
        cls.math_question2 = BankQuestion.objects.create(
            topic=cls.math_topic,
            subject=cls.math,
            school_class=cls.base_class,
            text="Решите уравнение: x² = 4",
            difficulty="MEDIUM",
            author=cls.user
        )
        
        cls.phys_question1 = BankQuestion.objects.create(
            topic=cls.phys_topic,
            subject=cls.phys,
            school_class=cls.base_class,
            text="Что измеряется в Ньютонах?",
            difficulty="EASY",
            author=cls.user
        )

        # Создаем варианты ответов
        BankAnswerOption.objects.create(
            question=cls.math_question1,
            text="4",
            is_correct=True
        )
        BankAnswerOption.objects.create(
            question=cls.math_question1,
            text="5",
            is_correct=False
        )
        
        BankAnswerOption.objects.create(
            question=cls.math_question2,
            text="2",
            is_correct=True
        )
        BankAnswerOption.objects.create(
            question=cls.math_question2,
            text="-2",
            is_correct=True
        )
        
        BankAnswerOption.objects.create(
            question=cls.phys_question1,
            text="Сила",
            is_correct=True
        )
        BankAnswerOption.objects.create(
            question=cls.phys_question1,
            text="Масса",
            is_correct=False
        )

        # Добавляем вопросы в тест
        cls.gat_test.questions.add(cls.math_question1, cls.math_question2, cls.phys_question1)

        # Создаем настройки количества вопросов
        cls.question_count_math = QuestionCount.objects.create(
            school_class=cls.base_class,
            subject=cls.math,
            number_of_questions=2
        )
        
        cls.question_count_phys = QuestionCount.objects.create(
            school_class=cls.base_class,
            subject=cls.phys,
            number_of_questions=1
        )

    def create_test_excel_file(self):
        """
        Создает в памяти тестовый Excel-файл с помощью pandas.
        """
        df = pd.DataFrame({
            'Code': ['S-1001', 'S-1002', 'S-1003'],
            'Surname': ['Иванов', 'Петров', 'Сидоров'],
            'Name': ['Иван', 'Петр', 'Сидор'],
            'Section': ['А', 'А', 'Б'],
            'МАТ_1': [1, 0, 1],  # Ответ на первый вопрос по математике
            'МАТ_2': [0, 1, 1],  # Ответ на второй вопрос по математике
            'ФИЗ_1': [1, 1, 0],  # Ответ на первый вопрос по физике
        })

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
        output.seek(0)

        return SimpleUploadedFile(
            "test_results.xlsx",
            output.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    def test_process_excel_creates_correct_classes(self):
        """
        Проверяет, что сервис правильно создает классы (10А, 10Б),
        привязывает к ним учеников и корректно сохраняет их результаты.
        """
        excel_file = self.create_test_excel_file()
        
        success, report = process_student_results_upload(self.gat_test, excel_file)

        # Проверяем, что отчет вернул успех
        self.assertTrue(success)
        
        # Проверяем ключи из отчета
        self.assertEqual(report['total_unique_students'], 3)
        self.assertEqual(report['created_students'], 3)
        self.assertEqual(len(report['errors']), 0)

        # Проверяем, что сервис создал подклассы
        self.assertTrue(SchoolClass.objects.filter(
            name='10А', school=self.school, parent=self.base_class
        ).exists())
        self.assertTrue(SchoolClass.objects.filter(
            name='10Б', school=self.school, parent=self.base_class
        ).exists())
        self.assertEqual(SchoolClass.objects.count(), 3)  # 10, 10А, 10Б

        # Проверяем конкретного студента
        sidorov = Student.objects.get(student_id='S-1003')
        self.assertEqual(sidorov.last_name_ru, "Сидоров")
        self.assertEqual(sidorov.school_class.name, '10Б')

        # Проверяем его результат
        sidorov_result = StudentResult.objects.get(student=sidorov)
        
        # Ожидаемые баллы: МАТ_1=1 (правильно), МАТ_2=1 (правильно), ФИЗ_1=0 (неправильно)
        expected_total_score = 2
        
        self.assertEqual(sidorov_result.total_score, expected_total_score)
        
        # Проверяем, что созданы записи StudentAnswer
        sidorov_answers = StudentAnswer.objects.filter(result=sidorov_result)
        self.assertEqual(sidorov_answers.count(), 3)  # 3 вопроса в тесте
        
        # Проверяем конкретные ответы
        math1_answer = sidorov_answers.get(question=self.math_question1)
        self.assertTrue(math1_answer.is_correct)
        
        phys1_answer = sidorov_answers.get(question=self.phys_question1)
        self.assertFalse(phys1_answer.is_correct)

    def test_validate_question_counts(self):
        """
        Проверяет функцию валидации количества вопросов.
        """
        # Тест с правильным количеством вопросов
        warnings = validate_question_counts(self.gat_test)
        self.assertEqual(len(warnings), 0)
        
        # Добавляем лишний вопрос по математике
        extra_math_question = BankQuestion.objects.create(
            topic=self.math_topic,
            subject=self.math,
            school_class=self.base_class,
            text="Лишний вопрос по математике",
            difficulty="EASY",
            author=self.user
        )
        self.gat_test.questions.add(extra_math_question)
        
        warnings = validate_question_counts(self.gat_test)
        self.assertEqual(len(warnings), 1)
        self.assertIn("Математика", warnings[0])
        self.assertIn("ожидается 2 вопросов, фактически 3", warnings[0])
        
        # Убираем лишний вопрос
        self.gat_test.questions.remove(extra_math_question)

    def test_student_answer_creation(self):
        """
        Проверяет создание ответов студентов на вопросы из банка.
        """
        # Создаем студента
        student = Student.objects.create(
            student_id="TEST-001",
            school_class=self.base_class,
            last_name_ru="Тестов",
            first_name_ru="Студент",
            status="ACTIVE"
        )
        
        # Создаем результат теста
        result = StudentResult.objects.create(
            student=student,
            gat_test=self.gat_test,
            total_score=2,
            scores_by_subject={
                str(self.math.id): {"1": True, "2": True},
                str(self.phys.id): {"1": False}
            }
        )
        
        # Создаем ответы студента
        StudentAnswer.objects.create(
            result=result,
            question=self.math_question1,
            is_correct=True,
            chosen_option_order=1
        )
        
        StudentAnswer.objects.create(
            result=result,
            question=self.math_question2,
            is_correct=True,
            chosen_option_order=1
        )
        
        StudentAnswer.objects.create(
            result=result,
            question=self.phys_question1,
            is_correct=False,
            chosen_option_order=2
        )
        
        # Проверяем создание
        answers = StudentAnswer.objects.filter(result=result)
        self.assertEqual(answers.count(), 3)
        
        correct_answers = answers.filter(is_correct=True)
        self.assertEqual(correct_answers.count(), 2)
        
        incorrect_answers = answers.filter(is_correct=False)
        self.assertEqual(incorrect_answers.count(), 1)

    def test_question_topic_creation(self):
        """
        Проверяет создание тем вопросов.
        """
        topic = QuestionTopic.objects.create(
            name="Геометрия",
            subject=self.math,
            school_class=self.base_class,
            author=self.user
        )
        
        self.assertEqual(topic.name, "Геометрия")
        self.assertEqual(topic.subject, self.math)
        self.assertEqual(topic.school_class, self.base_class)
        self.assertEqual(topic.author, self.user)
        
        # Проверяем строковое представление
        self.assertEqual(
            str(topic),
            "Геометрия (Математика, 10 кл.)"
        )

    def test_bank_question_creation(self):
        """
        Проверяет создание вопросов из банка.
        """
        question = BankQuestion.objects.create(
            topic=self.math_topic,
            subject=self.math,
            school_class=self.base_class,
            text="Новый тестовый вопрос",
            difficulty="HARD",
            author=self.user,
            tags="тест, математика"
        )
        
        self.assertEqual(question.text, "Новый тестовый вопрос")
        self.assertEqual(question.difficulty, "HARD")
        self.assertEqual(question.tags, "тест, математика")
        
        # Проверяем автоматическое установление subject и school_class из темы
        self.assertEqual(question.subject, self.math)
        self.assertEqual(question.school_class, self.base_class)

    def test_bank_answer_option_creation(self):
        """
        Проверяет создание вариантов ответов для вопросов из банка.
        """
        # Создаем новый вопрос
        question = BankQuestion.objects.create(
            topic=self.math_topic,
            subject=self.math,
            school_class=self.base_class,
            text="Вопрос с вариантами ответов",
            difficulty="MEDIUM",
            author=self.user
        )
        
        # Создаем варианты ответов
        correct_option = BankAnswerOption.objects.create(
            question=question,
            text="Правильный ответ",
            is_correct=True
        )
        
        incorrect_option = BankAnswerOption.objects.create(
            question=question,
            text="Неправильный ответ",
            is_correct=False
        )
        
        # Проверяем создание
        options = BankAnswerOption.objects.filter(question=question)
        self.assertEqual(options.count(), 2)
        
        correct_options = options.filter(is_correct=True)
        self.assertEqual(correct_options.count(), 1)
        self.assertEqual(correct_options.first(), correct_option)
        
        # Проверяем строковое представление
        self.assertIn("Правильный ответ", str(correct_option))
        self.assertIn("(✓)", str(correct_option))

class ModelRelationshipsTestCase(TestCase):
    """
    Тестирует связи между моделями в новой структуре.
    """
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='modeltest', 
            password='testpass123'
        )
        self.school = School.objects.create(
            school_id="SCH02", 
            name="Школа для теста связей"
        )
        self.base_class = SchoolClass.objects.create(
            name="11", 
            school=self.school
        )
        self.subject = Subject.objects.create(
            name="Химия", 
            abbreviation="ХИМ"
        )
        
    def test_gat_test_questions_relationship(self):
        """
        Проверяет связь Many-to-Many между GatTest и BankQuestion.
        """
        # Создаем тему
        topic = QuestionTopic.objects.create(
            name="Органическая химия",
            subject=self.subject,
            school_class=self.base_class,
            author=self.user
        )
        
        # Создаем вопросы
        question1 = BankQuestion.objects.create(
            topic=topic,
            subject=self.subject,
            school_class=self.base_class,
            text="Первый вопрос по химии",
            author=self.user
        )
        
        question2 = BankQuestion.objects.create(
            topic=topic,
            subject=self.subject,
            school_class=self.base_class,
            text="Второй вопрос по химии",
            author=self.user
        )
        
        # Создаем тест
        gat_test = GatTest.objects.create(
            name="Тест по химии",
            test_number=1,
            test_date=datetime.date.today(),
            school=self.school,
            school_class=self.base_class
        )
        
        # Добавляем вопросы в тест
        gat_test.questions.add(question1, question2)
        
        # Проверяем связь
        self.assertEqual(gat_test.questions.count(), 2)
        self.assertIn(question1, gat_test.questions.all())
        self.assertIn(question2, gat_test.questions.all())
        
        # Проверяем обратную связь
        self.assertEqual(question1.gat_tests.count(), 1)
        self.assertEqual(question1.gat_tests.first(), gat_test)