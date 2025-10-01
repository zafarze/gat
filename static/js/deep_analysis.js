document.addEventListener('DOMContentLoaded', function () {
    // --- ПОЛУЧЕНИЕ ДАННЫХ ИЗ HTML ---
    const analysisForm = document.getElementById('analysis-form');
    if (!analysisForm) return; // Если формы нет на странице, ничего не делаем

    // Получаем URL'ы и данные, переданные из Django через data-атрибуты
    const dynamicOptionsUrl = analysisForm.dataset.dynamicOptionsUrl;
    const schoolsComparisonChartEl = document.getElementById('schoolsComparisonChart');
    const overallPerformanceChartEl = document.getElementById('overallPerformanceChart');
    const trendChartEl = document.getElementById('trendChart');

    const urlParams = new URLSearchParams(window.location.search);
    
    // --- ЛОГИКА ДЛЯ ФИЛЬТРОВ ---
    // Инициализация начальных значений фильтров из URL
    document.querySelectorAll('.filter-card').forEach(card => {
        const filterName = card.dataset.filter;
        const paramValues = urlParams.getAll(filterName);
        if (paramValues.length > 0) {
            card.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                if (paramValues.includes(cb.value)) {
                    cb.checked = true;
                }
            });
        }
    });

    // Динамическая загрузка Классов и Предметов
    const schoolsContainer = document.querySelector('[data-filter="schools"]');
    const classesContainer = document.querySelector('[data-filter="school_classes"] .chip-container');
    const subjectsContainer = document.querySelector('[data-filter="subjects"] .chip-container');
    
    const selectedClasses = urlParams.getAll('school_classes');
    const selectedSubjects = urlParams.getAll('subjects');

    function loadDynamicOptions() {
        const selectedSchoolIds = Array.from(schoolsContainer.querySelectorAll('input:checked')).map(cb => cb.value);
        if (selectedSchoolIds.length === 0) {
            classesContainer.innerHTML = '<span class="text-sm text-gray-500 p-2">Сначала выберите школу</span>';
            subjectsContainer.innerHTML = '<span class="text-sm text-gray-500 p-2">Сначала выберите школу</span>';
            return;
        }
        
        classesContainer.innerHTML = '<span class="text-sm text-gray-500 p-2">Загрузка...</span>';
        subjectsContainer.innerHTML = '<span class="text-sm text-gray-500 p-2">Загрузка...</span>';
        
        // Используем URL из data-атрибута
        const url = `${dynamicOptionsUrl}?${selectedSchoolIds.map(id => `school_ids[]=${id}`).join('&')}`;
        fetch(url)
            .then(response => response.json())
            .then(data => {
                classesContainer.innerHTML = '';
                data.classes.forEach(c => {
                    const isChecked = selectedClasses.includes(String(c.id));
                    classesContainer.innerHTML += `<label class="chip"><input type="checkbox" name="school_classes" value="${c.id}" ${isChecked ? 'checked' : ''}><span>${c.name}</span></label>`;
                });
                subjectsContainer.innerHTML = '';
                data.subjects.forEach(s => {
                    const isChecked = selectedSubjects.includes(String(s.id));
                    subjectsContainer.innerHTML += `<label class="chip"><input type="checkbox" name="subjects" value="${s.id}" ${isChecked ? 'checked' : ''}><span>${s.name}</span></label>`;
                });
            });
    }
    
    schoolsContainer.addEventListener('change', loadDynamicOptions);
    loadDynamicOptions();

    // Поиск по фильтрам
    document.querySelectorAll('.filter-search').forEach(input => {
        input.addEventListener('keyup', () => {
            const query = input.value.toLowerCase();
            const container = input.closest('.filter-card').querySelector('.chip-container');
            container.querySelectorAll('.chip').forEach(chip => {
                const text = chip.textContent.toLowerCase();
                chip.style.display = text.includes(query) ? '' : 'none';
            });
        });
    });

    // --- ЛОГИКА ДЛЯ ВКЛАДОК ---
    const tabs = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(item => item.classList.remove('active'));
            tab.classList.add('active');
            const target = document.getElementById(tab.dataset.tab);
            tabContents.forEach(content => content.classList.remove('active'));
            target.classList.add('active');
        });
    });

    // --- ЛОГИКА ДЛЯ СОХРАНЕНИЯ/ЗАГРУЗКИ ОТЧЕТОВ ---
    const saveBtn = document.getElementById('save-report-btn');
    const deleteBtn = document.getElementById('delete-report-btn');
    const reportsSelect = document.getElementById('saved-reports');
    
    function loadReports() {
        reportsSelect.innerHTML = '<option value="">Загрузить отчет...</option>';
        const reports = JSON.parse(localStorage.getItem('savedGatReports') || '{}');
        for (const name in reports) {
            const option = new Option(name, reports[name]);
            reportsSelect.add(option);
        }
    }

    if (saveBtn) {
        saveBtn.addEventListener('click', () => {
            const name = prompt('Введите название для этого отчета:');
            if (name) {
                const reports = JSON.parse(localStorage.getItem('savedGatReports') || '{}');
                reports[name] = window.location.search;
                localStorage.setItem('savedGatReports', JSON.stringify(reports));
                loadReports();
                alert('Отчет сохранен!');
            }
        });
    }
    
    if (deleteBtn) {
        deleteBtn.addEventListener('click', () => {
            const selectedName = reportsSelect.options[reportsSelect.selectedIndex].text;
            if (selectedName && selectedName !== 'Загрузить отчет...') {
                if (confirm(`Вы уверены, что хотите удалить отчет "${selectedName}"?`)) {
                    const reports = JSON.parse(localStorage.getItem('savedGatReports') || '{}');
                    delete reports[selectedName];
                    localStorage.setItem('savedGatReports', JSON.stringify(reports));
                    loadReports();
                }
            }
        });
    }

    if (reportsSelect) {
        reportsSelect.addEventListener('change', () => {
            if (reportsSelect.value) {
                window.location.search = reportsSelect.value;
            }
        });
        loadReports();
    }

    // --- ЛОГИКА ДЛЯ ОТРИСОВКИ ГРАФИКОВ ---
    if (schoolsComparisonChartEl && schoolsComparisonChartEl.dataset.chartData) {
        Chart.register(ChartDataLabels);
        
        // 1. Сравнение школ (вертикальный столбчатый)
        new Chart(schoolsComparisonChartEl, {
            type: 'bar',
            data: JSON.parse(schoolsComparisonChartEl.dataset.chartData),
            options: {
                responsive: true,
                plugins: {
                    legend: { position: 'top' },
                    title: { display: false },
                    datalabels: { display: false }
                },
                scales: {
                    y: { beginAtZero: true, max: 100, ticks: { callback: (v) => v + '%' } }
                }
            }
        });

        // 2. Общая успеваемость (горизонтальный столбчатый)
        const overallPerformanceData = JSON.parse(overallPerformanceChartEl.dataset.chartData);
        new Chart(overallPerformanceChartEl, {
            type: 'bar',
            data: overallPerformanceData,
            options: {
                indexAxis: 'y',
                responsive: true,
                plugins: {
                    legend: { position: 'top' },
                    title: { display: false },
                    datalabels: {
                        anchor: 'end',
                        align: 'right',
                        formatter: (value, context) => context.dataset.type === 'line' ? '' : (value > 0 ? value + '%' : ''),
                        color: '#374151',
                        font: { weight: 'bold', size: 12 }
                    }
                },
                scales: {
                    x: { beginAtZero: true, max: 100, ticks: { callback: (v) => v + '%' } }
                }
            }
        });
        
        // 3. График динамики (если есть данные)
        if (trendChartEl && trendChartEl.dataset.chartData) {
            new Chart(trendChartEl, {
                type: 'line',
                data: JSON.parse(trendChartEl.dataset.chartData),
                options: {
                    responsive: true,
                    plugins: { legend: { position: 'top' }, datalabels: { display: false } },
                    scales: { y: { beginAtZero: true, max: 100 } }
                }
            });
        }
    }
});