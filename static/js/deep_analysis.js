// D:\GAT\static\js\deep_analysis.js -- FIXED VERSION

document.addEventListener('DOMContentLoaded', function () {
    const analysisForm = document.getElementById('deep-analysis-form'); // Исправил ID формы на тот, что в HTML
    if (!analysisForm) return;

    // --- НАСТРОЙКИ (URL из атрибутов) ---
    // Мы берем URL прямо из HTML, чтобы не хардкодить их в JS
    // Предполагаем, что в HTML есть data-атрибуты, но если нет - используем те, что были в скрипте шаблона
    const classesApiUrl = "/api/load-classes-as-chips/"; // Хардкод или лучше data-атрибут
    const subjectsApiUrl = "/api/load-subjects-for-filters/";

    const schoolsContainer = document.querySelector('[data-filter="schools"]');
    const classesContainer = document.getElementById('classes-chip-container');
    const subjectsContainer = document.getElementById('subjects-chip-container');
    
    // --- ФУНКЦИИ ЗАГРУЗКИ (Взяты из твоего шаблона и улучшены) ---
    
    function getSelectedValues(container) {
        if (!container) return [];
        return Array.from(container.querySelectorAll('input:checked')).map(cb => cb.value);
    }

    function loadDynamicOptions() {
        // Эта функция дублирует логику из HTML-шаблона. 
        // В идеале, код должен быть либо только в .js, либо только в .html
        // Сейчас в твоем deep_analysis.html уже есть мощный скрипт.
        // Этот файл (deep_analysis.js) должен дополнять его, а не конфликтовать.
        
        // ДАВАЙ ОСТАВИМ ЗДЕСЬ ТОЛЬКО ОБЩУЮ ЛОГИКУ ГРАФИКОВ, 
        // так как фильтры у тебя уже отлично работают внутри шаблона.
    }

    // --- ЛОГИКА ДЛЯ ОТРИСОВКИ ГРАФИКОВ ---
    // Исправленный ID: comparisonChart
    const comparisonChartEl = document.getElementById('comparisonChart'); 
    const overallPerformanceChartEl = document.getElementById('overallPerformanceChart');
    const trendChartEl = document.getElementById('trendChart');
    
    if (comparisonChartEl && comparisonChartEl.dataset.chartData) {
        Chart.register(ChartDataLabels);
        
        // 1. Сравнение успеваемости (Столбчатая)
        new Chart(comparisonChartEl, {
            type: 'bar',
            data: JSON.parse(comparisonChartEl.dataset.chartData),
            options: {
                responsive: true,
                maintainAspectRatio: false, // Важно для адаптивности
                plugins: {
                    legend: { position: 'top' },
                    datalabels: {
                        anchor: 'end',
                        align: 'top',
                        formatter: (value) => value + '%',
                        color: '#4b5563',
                        font: { weight: 'bold' }
                    }
                },
                scales: {
                    y: { beginAtZero: true, max: 100 }
                }
            }
        });
    }

    if (overallPerformanceChartEl && overallPerformanceChartEl.dataset.chartData) {
        // 2. Общая успеваемость (Горизонтальная)
        new Chart(overallPerformanceChartEl, {
            type: 'bar',
            data: JSON.parse(overallPerformanceChartEl.dataset.chartData),
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    datalabels: {
                        anchor: 'end',
                        align: 'right',
                        formatter: (value) => value + '%',
                        color: '#374151',
                        font: { weight: 'bold' }
                    }
                },
                scales: {
                    x: { beginAtZero: true, max: 100 }
                }
            }
        });
    }
        
    if (trendChartEl && trendChartEl.dataset.chartData) {
        // 3. Динамика
        new Chart(trendChartEl, {
            type: 'line',
            data: JSON.parse(trendChartEl.dataset.chartData),
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'top' }, datalabels: { display: false } },
                scales: { y: { beginAtZero: true, max: 100 } }
            }
        });
    }

    // --- ЛОГИКА ТАБОВ (ВКЛАДОК) ---
    const tabs = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Убираем активность со всех
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            // Добавляем активному
            tab.classList.add('active');
            const targetId = tab.dataset.tab;
            const targetContent = document.getElementById(targetId);
            if (targetContent) {
                targetContent.classList.add('active');
            }
        });
    });
});