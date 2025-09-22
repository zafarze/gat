# core/tests.py (НОВАЯ, ИСПРАВЛЕННАЯ ВЕРСИЯ)

from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
import pandas as pd
import io
import datetime

from .models import (
    AcademicYear, Quarter, School, SchoolClass, Subject,
    GatTest, Student, StudentResult
)
from .services import process_excel_results

class ServicesTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        """
        Подготавливает начальные данные в базе один раз для всего набора тестов.
        Это эффективнее, чем создавать их заново для каждого теста.
        """
        cls.year = AcademicYear.objects.create(name="2025", start_date="2025-09-01", end_date="2026-05-31")
        cls.quarter = Quarter.objects.create(name="1 четверть", year=cls.year, start_date="2025-09-01", end_date="2025-10-31")
        cls.school = School.objects.create(name="Тестовая Школа", address="Тестовый адрес")

        # Создаем "базовый" класс "10", к которому будет привязан тест
        cls.base_class = SchoolClass.objects.create(name="10", school=cls.school)

        # Создаем предметы
        cls.math = Subject.objects.create(name="Математика", abbreviation="МАТ", school=cls.school)
        cls.phys = Subject.objects.create(name="Физика", abbreviation="ФИЗ", school=cls.school)

        # Создаем GAT-тест, привязанный к базовому классу "10"
        cls.gat_test = GatTest.objects.create(
            name="GAT для 10-х классов",
            test_number=1,
            test_date=datetime.date.today(),
            quarter=cls.quarter,
            school_class=cls.base_class
        )
        cls.gat_test.subjects.add(cls.math, cls.phys)

    def create_test_excel_file(self):
        """
        Создает в памяти тестовый Excel-файл с помощью pandas.
        """
        # DataFrame с данными учеников. Важно наличие колонки 'Section'.
        df = pd.DataFrame({
            'Code': ['S-1001', 'S-1002', 'S-1003'],
            'Surname': ['Иванов', 'Петров', 'Сидоров'],
            'Name': ['Иван', 'Петр', 'Сидор'],
            'Section': ['А', 'А', 'Б'], # Иванов и Петров из 10А, Сидоров из 10Б
            'МАТ_1': [1, 0, 1],
            'МАТ_2': [0, 1, 1],
            'ФИЗ_1': [1, 1, 0],
        })

        # Записываем DataFrame в байтовый поток в формате Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
        output.seek(0) # Перемещаем курсор в начало файла

        # Возвращаем объект, который Django воспринимает как загруженный файл
        return SimpleUploadedFile(
            "test_results.xlsx",
            output.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    def test_process_excel_creates_correct_classes(self):
        """
        Основной тест.
        Проверяет, что сервис правильно создает классы (10А, 10Б),
        привязывает к ним учеников и корректно сохраняет их результаты.
        """
        # 1. Подготовка: создаем файл
        excel_file = self.create_test_excel_file()

        # 2. Действие: вызываем сервис для обработки файла
        report = process_excel_results(excel_file, self.gat_test)

        # 3. Проверки (Asserts):

        # Проверяем отчет: все 3 ученика должны быть обработаны
        self.assertEqual(report['processed_count'], 3)
        self.assertEqual(report['skipped_count'], 0)

        # Проверяем, что в базе данных появились классы "10А" и "10Б"
        self.assertTrue(SchoolClass.objects.filter(name='10А', school=self.school).exists())
        self.assertTrue(SchoolClass.objects.filter(name='10Б', school=self.school).exists())

        # Проверяем, что общее количество классов теперь 3 (базовый "10", "10А" и "10Б")
        self.assertEqual(SchoolClass.objects.count(), 3)

        # Проверяем, что конкретный студент (Сидоров) привязан к правильному классу (10Б)
        sidorov = Student.objects.get(student_id='S-1003')
        self.assertEqual(sidorov.last_name, "Сидоров")
        self.assertEqual(sidorov.school_class.name, '10Б')

        # Проверяем, что JSON с результатами Сидорова сформирован верно
        sidorov_result = StudentResult.objects.get(student=sidorov)
        expected_scores = {
            str(self.math.id): [True, True], # 2/2 по математике
            str(self.phys.id): [False]       # 0/1 по физике
        }
        self.assertEqual(sidorov_result.scores, expected_scores)