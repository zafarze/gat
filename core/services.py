# D:\New_GAT\core\services.py (ОБНОВЛЕННАЯ ВЕРСИЯ)

import pandas as pd
from collections import defaultdict
from django.db import transaction
import re
from datetime import datetime
from .models import Student, SchoolClass, GatTest, StudentResult, Subject

def extract_test_date_from_excel(file):
    """
    Извлекает дату теста из Excel файла.
    """
    try:
        # Сохраняем позицию файла для последующего чтения
        file.seek(0)
        
        # Вариант 1: из имени файла (например: "GAT_2024_03_15_10A.xlsx")
        filename = file.name
        date_pattern = r'(\d{4})[_-](\d{1,2})[_-](\d{1,2})'
        match = re.search(date_pattern, filename)
        
        if match:
            year, month, day = match.groups()
            return datetime(int(year), int(month), int(day)).date()
        
        # Вариант 2: попробовать прочитать дату из содержимого Excel
        try:
            # Читаем только первую строку для скорости
            df = pd.read_excel(file, nrows=5)
            file.seek(0)  # Сбрасываем позицию файла
            
            # Ищем столбцы с датой или временем
            for col in df.columns:
                if any(keyword in str(col).lower() for keyword in ['date', 'time', 'дата', 'время']):
                    # Пробуем извлечь дату из первой ячейки этого столбца
                    if not pd.isna(df[col].iloc[0]):
                        date_value = df[col].iloc[0]
                        if isinstance(date_value, (datetime, pd.Timestamp)):
                            return date_value.date()
                        elif isinstance(date_value, str):
                            date_match = re.search(date_pattern, date_value)
                            if date_match:
                                year, month, day = date_match.groups()
                                return datetime(int(year), int(month), int(day)).date()
        except Exception as e:
            print(f"Warning: Could not extract date from Excel content: {e}")
            file.seek(0)
        
        # Если дату не удалось извлечь, возвращаем None
        return None
        
    except Exception as e:
        print(f"Error extracting date from Excel: {e}")
        return None

# Эта функция для загрузки списка студентов остается без изменений.
def process_student_upload(excel_file):
    try:
        df = pd.read_excel(excel_file, dtype={'student_id': str})
    except Exception as e:
        return {'errors': [f"Ошибка чтения файла: {e}"]}
    df.columns = [str(col).strip().lower() for col in df.columns]
    required_columns = {'student_id', 'класс', 'фамилия_рус', 'имя_рус'}
    if not required_columns.issubset(df.columns):
        missing = required_columns - set(df.columns)
        return {'errors': [f"Отсутствуют обязательные колонки: {', '.join(missing)}"]}
    created_count, updated_count, skipped_count, errors = 0, 0, 0, []
    class_names = df['класс'].dropna().unique()
    classes_cache = {cls.name: cls for cls in SchoolClass.objects.filter(name__in=class_names)}
    for index, row in df.iterrows():
        student_id, class_name = row.get('student_id'), row.get('класс')
        if pd.isna(student_id) or pd.isna(class_name):
            skipped_count += 1
            continue
        school_class = classes_cache.get(str(class_name).strip())
        if not school_class:
            errors.append(f"Строка {index + 2}: Класс '{class_name}' не найден.")
            continue
        student_data = {
            'school_class': school_class, 'status': 'ACTIVE',
            'last_name_ru': str(row.get('фамилия_рус', '')).strip(),
            'first_name_ru': str(row.get('имя_рус', '')).strip(),
        }
        try:
            _, created = Student.objects.update_or_create(student_id=str(student_id).strip(), defaults=student_data)
            if created: created_count += 1
            else: updated_count += 1
        except Exception as e:
            errors.append(f"Строка {index + 2}: Ошибка сохранения студента ID {student_id}. {e}")
    return {"created": created_count, "updated": updated_count, "skipped": skipped_count, "errors": errors}

@transaction.atomic
def process_student_results_upload(gat_test, excel_file):
    """
    СОВЕРШЕННО НОВАЯ ВЕРСИЯ для обработки сложного Excel-файла с результатами.
    """
    try:
        # pd.read_excel с sheet_name=None читает все листы в словарь
        excel_sheets = pd.read_excel(excel_file, sheet_name=None, dtype={'Code': str})
    except Exception as e:
        return False, f"Критическая ошибка чтения Excel-файла: {e}"

    # --- Подготовка данных ---
    parent_class = gat_test.school_class
    if not parent_class or parent_class.parent is not None:
        return False, "GAT-тест должен быть привязан к классу-параллели (например, '10'), а не к подклассу ('10А')."

    # --- ✨ ИСПРАВЛЕНИЕ ЗДЕСЬ ✨ ---
    # Создаем словарь для быстрой конвертации аббревиатур предметов в ID
    # Убрали фильтр по школе, так как предметы глобальные
    subject_abbr_map = {
        s.abbreviation.upper(): s.id
        for s in Subject.objects.all() # <-- Теперь берем все предметы
        if s.abbreviation
    }
    # --- ✨ КОНЕЦ ИСПРАВЛЕНИЯ ✨ ---

    # Словарь для хранения всех результатов перед записью в БД
    # Структура: { 'student_id': { 'student': obj, 'scores_by_subject': defaultdict } }
    all_results = defaultdict(lambda: {
        'student': None,
        'scores_by_subject': defaultdict(list)
    })

    errors = []
    processed_rows = 0
    created_students = 0
    updated_students = 0

    # --- Обработка каждого листа в файле ---
    for sheet_name, df in excel_sheets.items():
        df.columns = [str(col).strip() for col in df.columns]
        required_cols = {'Code', 'Surname', 'Name', 'Section'}
        if not required_cols.issubset(df.columns):
            errors.append(f"На листе '{sheet_name}' отсутствуют обязательные колонки: {', '.join(required_cols - set(df.columns))}")
            continue

        # --- Обработка каждой строки (ученика) на листе ---
        for index, row in df.iterrows():
            student_id = row.get('Code')
            if pd.isna(student_id):
                continue

            processed_rows += 1

            # 1. Находим или создаем ученика
            class_letter = str(row.get('Section', '')).strip()
            class_name = f"{parent_class.name}{class_letter}"

            # Находим или создаем подкласс (например, 10А)
            school_class, _ = SchoolClass.objects.get_or_create(
                name=class_name,
                school=gat_test.school, # Школа берется из GAT теста
                defaults={'parent': parent_class}
            )

            # Находим или создаем самого ученика
            student_defaults = {
                'school_class': school_class,
                'last_name_ru': str(row.get('Surname', '')).strip(),
                'first_name_ru': str(row.get('Name', '')).strip(),
                'status': 'ACTIVE' # Устанавливаем статус при создании/обновлении
            }
            student, created = Student.objects.update_or_create(
                student_id=student_id,
                defaults=student_defaults
            )
            if created: created_students += 1
            else: updated_students += 1

            all_results[student_id]['student'] = student

            # 2. Разбираем его ответы по предметам
            for col_name, value in row.items():
                if '_' not in col_name or col_name in required_cols:
                    continue # Пропускаем служебные колонки

                parts = col_name.split('_')
                subject_abbr = parts[0].upper()
                question_num_str = parts[1] # Номер вопроса как строка

                # Проверяем, что номер вопроса - это число
                if not question_num_str.isdigit():
                    continue

                if subject_abbr in subject_abbr_map:
                    subject_id = subject_abbr_map[subject_abbr]
                    # Добавляем результат (True/False) в список ответов по этому предмету
                    is_correct = False
                    if not pd.isna(value):
                        try:
                            # Сравниваем с 1 (числом)
                            if int(value) == 1:
                                is_correct = True
                        except (ValueError, TypeError):
                            pass # Если не число, считаем неверным

                    # --- ИЗМЕНЕНИЕ: Сохраняем как словарь {номер_вопроса: True/False} ---
                    # Убедимся, что scores_by_subject[subject_id] - это словарь
                    if not isinstance(all_results[student_id]['scores_by_subject'][subject_id], dict):
                         all_results[student_id]['scores_by_subject'][subject_id] = {}
                    # Сохраняем ответ по номеру вопроса
                    all_results[student_id]['scores_by_subject'][subject_id][question_num_str] = is_correct
                    # --- КОНЕЦ ИЗМЕНЕНИЯ ---


    # --- Сохранение результатов в базу данных ---
    for student_id, data in all_results.items():
        student_obj = data['student']
        scores_by_subject_dict = data['scores_by_subject']

        # Считаем итоговый балл (сумма всех True во всех словарях предметов)
        total_score = sum(
            sum(1 for is_correct in answers.values() if is_correct is True)
            for answers in scores_by_subject_dict.values() if isinstance(answers, dict)
        )

        # Преобразуем ID предметов (ключи верхнего уровня) в строки для JSON
        scores_dict_str_keys = {str(k): v for k, v in scores_by_subject_dict.items()}

        StudentResult.objects.update_or_create(
            student=student_obj,
            gat_test=gat_test,
            defaults={
                'total_score': total_score,
                'scores_by_subject': scores_dict_str_keys # Сохраняем словарь {subj_id_str: {q_num_str: bool}}
            }
        )

    report = {
        "processed_rows": processed_rows,
        "created_students": created_students,
        "updated_students": updated_students,
        "total_unique_students": len(all_results),
        "errors": errors
    }
    return True, report