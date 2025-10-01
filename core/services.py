# D:\New_GAT\core\services.py (ПОЛНАЯ ИСПРАВЛЕННАЯ ВЕРСИЯ)

from collections import defaultdict
import pandas as pd
from django.db import transaction
from .models import Subject, School, SchoolClass, Student, StudentResult


def process_excel_results(excel_file, gat_test):
    """
    Обрабатывает загруженный Excel-файл с результатами GAT-теста.
    """
    try:
        df = pd.read_excel(excel_file, dtype={'Code': str})
    except Exception as e:
        raise ValueError(f"Не удалось прочитать Excel файл. Ошибка: {e}")

    required_columns = {'Code', 'Surname', 'Name', 'Section'}
    if not required_columns.issubset(set(df.columns)):
        missing_columns = required_columns - set(df.columns)
        raise ValueError(f"В Excel-файле отсутствуют необходимые колонки: {', '.join(missing_columns)}")

    base_school_class = gat_test.school_class
    school = base_school_class.school
    
    subject_map = {s.abbreviation: s for s in Subject.objects.filter(school=school) if s.abbreviation}
    
    processed_students = []
    skipped_students = []

    with transaction.atomic():
        for index, row in df.iterrows():
            if pd.isna(row.get('Code')):
                continue
            
            section = str(row['Section']).strip()
            full_class_name = f"{base_school_class.name}{section}"
            
            final_class_obj, _ = SchoolClass.objects.get_or_create(
                school=school,
                name=full_class_name,
                defaults={'parent': base_school_class} 
            )

            student_code_raw = str(row['Code']).strip()
            student_code = student_code_raw[:-2] if student_code_raw.endswith('.0') else student_code_raw
            
            student, created = Student.objects.get_or_create(
                student_id=student_code,
                defaults={
                    'school_class': final_class_obj,
                    'last_name_ru': row['Surname'], 
                    'first_name_ru': row['Name'],
                    'last_name_tj': '',
                    'first_name_tj': '',
                    'last_name_en': '',
                    'first_name_en': '',
                }
            )

            if not created and student.school_class != final_class_obj:
                student.school_class = final_class_obj
                student.save()
            
            scores_by_subject = defaultdict(dict)
            for col_name in df.columns:
                if '_' not in str(col_name): 
                    continue
                
                parts = col_name.rsplit('_', 1)
                abbr, q_number_str = parts[0], parts[1]
                
                try:
                    q_number = int(q_number_str)
                    subject = subject_map.get(abbr)
                    if subject:
                        is_correct = pd.notna(row[col_name]) and int(row[col_name]) == 1
                        scores_by_subject[subject.id][q_number] = is_correct
                except (ValueError, TypeError):
                    continue
            
            final_scores = {str(sid): [v for k, v in sorted(q.items())] for sid, q in scores_by_subject.items()}
            
            StudentResult.objects.update_or_create(
                student=student, 
                gat_test=gat_test, 
                defaults={'scores': final_scores}
            )
            processed_students.append(f"{student.last_name_ru} {student.first_name_ru} (класс {final_class_obj.name})")
            
    return {
        'processed_count': len(processed_students),
        'processed_list': processed_students,
        'skipped_count': len(skipped_students),
        'skipped_list': skipped_students
    }


def process_student_excel(excel_file):
    """
    Обрабатывает Excel-файл для массового создания или обновления учеников.
    """
    try:
        df = pd.read_excel(excel_file, dtype={'ID учеников': str})
    except Exception as e:
        return {'error': f"Не удалось прочитать Excel файл. Ошибка: {e}"}

    # --- ИЗМЕНЕНИЕ 1: Обновляем список обязательных колонок ---
    required_columns = {'Имя', 'Фамилия', 'Ном', 'Насаб', 'Name', 'Surname', 'ID учеников', 'Школа', 'Класс'}
    if not required_columns.issubset(set(df.columns)):
        missing = required_columns - set(df.columns)
        return {'error': f"В файле отсутствуют колонки: {', '.join(missing)}"}

    processed_count = 0
    created_count = 0
    updated_count = 0
    errors = []

    with transaction.atomic():
        for index, row in df.iterrows():
            student_id = str(row['ID учеников']).strip()
            school_name = str(row['Школа']).strip()
            class_name = str(row['Класс']).strip()

            try:
                school = School.objects.get(name__iexact=school_name)
                school_class = SchoolClass.objects.get(name__iexact=class_name, school=school)
            except School.DoesNotExist:
                errors.append(f"Строка {index + 2}: Школа '{school_name}' не найдена.")
                continue
            except SchoolClass.DoesNotExist:
                errors.append(f"Строка {index + 2}: Класс '{class_name}' в школе '{school_name}' не найден.")
                continue

            # --- ИЗМЕНЕНИЕ 2: Читаем данные из отдельных колонок ---
            student_data = {
                'school_class': school_class,
                'first_name_ru': str(row.get('Имя', '')),
                'last_name_ru': str(row.get('Фамилия', '')),
                'first_name_tj': str(row.get('Ном', '')),
                'last_name_tj': str(row.get('Насаб', '')),
                'first_name_en': str(row.get('Name', '')),
                'last_name_en': str(row.get('Surname', '')),
            }
            
            _, created = Student.objects.update_or_create(
                student_id=student_id,
                defaults=student_data
            )
            
            processed_count += 1
            if created:
                created_count += 1
            else:
                updated_count += 1

    return {
        'processed_count': processed_count,
        'created_count': created_count,
        'updated_count': updated_count,
        'errors': errors
    }