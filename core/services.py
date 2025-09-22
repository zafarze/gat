# core/services.py (ПОЛНАЯ ОБНОВЛЕННАЯ ВЕРСИЯ)

from collections import defaultdict
import pandas as pd
from django.db import transaction
from .models import Subject, SchoolClass, Student, StudentResult

def process_excel_results(excel_file, gat_test):
    """
    Обрабатывает загруженный Excel-файл, комбинируя класс из теста
    с секцией (буквой) из файла для создания полного имени класса.
    """
    try:
        # При чтении файла сразу указываем, что колонка 'Code' должна быть текстовой
        df = pd.read_excel(excel_file, dtype={'Code': str})
    except Exception as e:
        raise ValueError(f"Не удалось прочитать Excel файл. Ошибка: {e}")

    # Убеждаемся, что все необходимые колонки существуют в файле
    required_columns = {'Code', 'Surname', 'Name', 'Section'}
    actual_columns = set(df.columns)
    
    if not required_columns.issubset(actual_columns):
        missing_columns = required_columns - actual_columns
        raise ValueError(f"В Excel-файле отсутствуют необходимые колонки: {', '.join(missing_columns)}")

    # Получаем базовый класс (например, "5") и школу из GAT-теста
    base_school_class = gat_test.school_class
    school = base_school_class.school
    
    # --- ОПТИМИЗАЦИЯ: Загружаем аббревиатуры предметов ТОЛЬКО для нужной школы ---
    subject_map = {s.abbreviation: s for s in Subject.objects.filter(school=school) if s.abbreviation}
    
    processed_students = []
    skipped_students = []

    with transaction.atomic():
        for index, row in df.iterrows():
            if pd.isna(row.get('Code')):
                continue
            
            # Создаем полное имя класса, например, "5" + "А" -> "5А"
            section = str(row['Section']).strip()
            full_class_name = f"{base_school_class.name}{section}"
            
            # Находим или создаем объект класса "5А" для нужной школы
            final_class_obj, created = SchoolClass.objects.get_or_create(
                school=school,
                name=full_class_name,
                defaults={'parent': base_school_class} 
            )

            # Очищаем ID студента от возможных ".0" в конце
            student_code_raw = str(row['Code']).strip()
            student_code = student_code_raw[:-2] if student_code_raw.endswith('.0') else student_code_raw
            
            # Создаем или обновляем студента, привязывая его к корректному классу
            student_defaults = {
                'last_name': row['Surname'], 
                'first_name': row['Name'], 
                'school_class': final_class_obj
            }
            student, _ = Student.objects.update_or_create(
                student_id=student_code,
                defaults=student_defaults
            )
            
            # Обработка баллов
            scores_by_subject = defaultdict(dict)
            for col_name in df.columns:
                if '_' not in str(col_name): 
                    continue
                
                parts = col_name.rsplit('_', 1)
                abbr, q_number_str = parts[0], parts[1]
                
                # --- УЛУЧШЕНИЕ: Используем try-except для надежности ---
                try:
                    q_number = int(q_number_str)
                    subject = subject_map.get(abbr)
                    if subject:
                        # Проверяем, что в ячейке не пустое значение (NaN) и оно равно 1
                        is_correct = pd.notna(row[col_name]) and int(row[col_name]) == 1
                        scores_by_subject[subject.id][q_number] = is_correct
                except (ValueError, TypeError):
                    # Если q_number_str не является числом, просто пропускаем эту колонку
                    continue
            
            # Собираем итоговый JSON, сортируя ответы по номеру вопроса
            final_scores = {str(sid): [v for k, v in sorted(q.items())] for sid, q in scores_by_subject.items()}
            
            StudentResult.objects.update_or_create(
                student=student, 
                gat_test=gat_test, 
                defaults={'scores': final_scores}
            )
            processed_students.append(f"{student.last_name} {student.first_name} (класс {final_class_obj.name})")
            
    return {
        'processed_count': len(processed_students),
        'processed_list': processed_students,
        'skipped_count': len(skipped_students),
        'skipped_list': skipped_students
    }