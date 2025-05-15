import pdfMake from 'pdfmake/build/pdfmake';
import pdfFonts from 'pdfmake/build/vfs_fonts';

// Устанавливаем шрифты с проверкой структуры модуля
const vfs = pdfFonts.pdfMake?.vfs || pdfFonts; // Проверяем наличие pdfMake.vfs, иначе используем pdfFonts напрямую
pdfMake.vfs = vfs;
pdfMake.fonts = {
  Roboto: {
    normal: 'Roboto-Regular.ttf',
    bold: 'Roboto-Medium.ttf',
  },
};

export default async function generateReportPDF(formatReport, file, log) {
  log('Инициализация генерации PDF');

  // Цвета
  const primaryColor = '#1E3A8A';
  const accentColor = '#3B82F6';
  const textColor = '#6B7280';
  const successColor = '#22C55E';
  const warningColor = '#EAB308';
  const dangerColor = '#EF4444';

  const videoDuration = 30;

  // Определение документа
  const documentDefinition = {
    pageSize: 'A4',
    pageMargins: [15, 15, 15, 15],
    defaultStyle: {
      font: 'Roboto',
      fontSize: 12,
      color: textColor,
    },
    header: (currentPage, pageCount) => ({
      margin: [15, 5, 15, 0],
      columns: [
        {
          text: 'AdVision Analytics',
          color: '#FFFFFF',
          fontSize: 12,
          bold: true,
          alignment: 'left',
        },
        currentPage > 1
          ? {
              text: 'Отчёт по качеству рекламы',
              color: '#FFFFFF',
              fontSize: 10,
              alignment: 'right',
            }
          : {},
      ],
      fillColor: primaryColor,
      padding: [5, 5, 5, 5],
    }),
    footer: (currentPage, pageCount) => ({
      margin: [15, 0, 15, 5],
      columns: [
        {
          text: '© 2025 AdVision Analytics',
          fontSize: 8,
          color: textColor,
        },
        {
          text: `Страница ${currentPage} из ${pageCount}`,
          fontSize: 8,
          color: textColor,
          alignment: 'right',
        },
      ],
      fillColor: '#F3F4F6',
      padding: [5, 0, 5, 5],
    }),
    content: [],
    styles: {
      title: {
        fontSize: 24,
        bold: true,
        color: primaryColor,
        margin: [0, 0, 0, 10],
      },
      sectionHeader: {
        fontSize: 16,
        bold: true,
        color: primaryColor,
        margin: [0, 10, 0, 5],
      },
      subHeader: {
        fontSize: 14,
        bold: true,
        color: primaryColor,
        margin: [0, 5, 0, 5],
      },
      text: {
        fontSize: 12,
        color: textColor,
        margin: [0, 2, 0, 2],
      },
      line: {
        margin: [0, 2, 0, 5],
      },
    },
  };

  // Титульная страница
  log('Создание титульной страницы');
  documentDefinition.content.push(
    {
      text: 'Отчёт по анализу рекламы',
      style: 'title',
      alignment: 'center',
      margin: [0, 150, 0, 10],
    },
    {
      text: `Файл: ${file ? file.name : 'Неизвестно'}`,
      style: 'text',
      alignment: 'center',
    },
    {
      text: `Дата: ${new Date().toLocaleString('ru-RU')}`,
      style: 'text',
      alignment: 'center',
    },
    {
      text: 'AdVision Analytics',
      style: 'text',
      alignment: 'center',
      margin: [0, 10, 0, 0],
      pageBreak: 'after',
    }
  );

  // Метаданные
  log('Добавление метаданных');
  documentDefinition.content.push(
    {
      text: 'Метаданные видео',
      style: 'sectionHeader',
    },
    {
      canvas: [
        {
          type: 'line',
          x1: 0,
          y1: 0,
          x2: 30,
          y2: 0,
          lineWidth: 0.5,
          lineColor: accentColor,
        },
      ],
      style: 'line',
    },
    {
      text: [
        { text: 'Имя файла: ', bold: true },
        file ? file.name : 'Неизвестно',
      ],
      style: 'text',
    },
    {
      text: [
        { text: 'Размер: ', bold: true },
        file ? `${(file.size / 1024 / 1024).toFixed(2)} МБ` : 'Неизвестно',
      ],
      style: 'text',
    },
    {
      text: [
        { text: 'Дата анализа: ', bold: true },
        new Date().toLocaleString('ru-RU'),
      ],
      style: 'text',
    },
    {
      text: [
        { text: 'Длительность: ', bold: true },
        `${videoDuration} сек`,
      ],
      style: 'text',
    }
  );

  // Статистика
  log('Добавление статистики');
  const adCount = formatReport.length;
  const validAds = formatReport.filter(item => item.duration > 0);
  const avgDuration = validAds.length
    ? validAds.reduce((sum, item) => sum + item.duration, 0) / validAds.length
    : 0;
  const scores = formatReport
    .map(item => {
      const match = item.text.match(/балл: ([\d.]+)/);
      return match ? parseFloat(match[1]) : 0;
    })
    .filter(score => score > 0);
  const avgScore = scores.length
    ? scores.reduce((sum, score) => sum + score, 0) / scores.length
    : 0;

  documentDefinition.content.push(
    {
      text: 'Общая статистика',
      style: 'sectionHeader',
      margin: [0, 15, 0, 5],
    },
    {
      canvas: [
        {
          type: 'line',
          x1: 0,
          y1: 0,
          x2: 30,
          y2: 0,
          lineWidth: 0.5,
          lineColor: accentColor,
        },
      ],
      style: 'line',
    },
    {
      text: [
        { text: 'Количество реклам: ', bold: true },
        `${adCount}`,
      ],
      style: 'text',
    },
    {
      text: [
        { text: 'Средняя длительность: ', bold: true },
        `${avgDuration.toFixed(1)} сек`,
      ],
      style: 'text',
    },
    {
      text: [
        { text: 'Средний балл качества: ', bold: true },
        `${avgScore.toFixed(2)}`,
      ],
      style: 'text',
    }
  );

  // График
  if (scores.length) {
    log('Отрисовка графика');
    const chartWidth = 100 * 2.83465; // мм
    const chartHeight = 40 * 2.83465; // мм
    const barWidth = chartWidth / scores.length;
    const maxScore = Math.max(...scores, 1);

    const canvas = [
      // Оси
      {
        type: 'line',
        x1: 0,
        y1: chartHeight,
        x2: chartWidth,
        y2: chartHeight,
        lineWidth: 0.5,
        lineColor: textColor,
      },
      {
        type: 'line',
        x1: 0,
        y1: 0,
        x2: 0,
        y2: chartHeight,
        lineWidth: 0.5,
        lineColor: textColor,
      },
    ];

    // Столбцы
    scores.forEach((score, i) => {
      const barHeight = (score / maxScore) * chartHeight;
      const color = score >= 0.6 ? successColor : score >= 0.3 ? warningColor : dangerColor;
      canvas.push({
        type: 'rect',
        x: i * barWidth,
        y: chartHeight - barHeight,
        w: barWidth - 2.83465,
        h: barHeight,
        color: color,
      });
    });

    documentDefinition.content.push(
      {
        text: 'Баллы качества',
        style: 'sectionHeader',
        margin: [0, 15, 0, 5],
      },
      {
        canvas: [
          {
            type: 'line',
            x1: 0,
            y1: 0,
            x2: 30,
            y2: 0,
            lineWidth: 0.5,
            lineColor: accentColor,
          },
        ],
        style: 'line',
      },
      {
        canvas,
        margin: [0, 10, 0, 0],
      },
      {
        columns: [
          { text: '0', fontSize: 8, color: textColor, alignment: 'left', margin: [-5, 2, 0, 0] },
          {
            text: maxScore.toFixed(1),
            fontSize: 8,
            color: textColor,
            alignment: 'left',
            margin: [-5, chartHeight + 12, 0, 0],
          },
        ],
      }
    );
  }

  // Рекламы
  log('Добавление рекламы');
  formatReport.forEach((item, index) => {
    const content = [
      {
        text: `Реклама ${index + 1}`,
        style: 'subHeader',
      },
      {
        canvas: [
          {
            type: 'line',
            x1: 0,
            y1: 0,
            x2: 20,
            y2: 0,
            lineWidth: 0.5,
            lineColor: accentColor,
          },
        ],
        style: 'line',
      },
    ];

    // Разбиваем текст на строки
    const lines = item.text.split('\n').map(line => ({
      text: line.trim(),
      style: 'text',
    }));
    content.push(...lines);

    // Таймлайн
    if (item.start_time !== undefined && item.duration > 0) {
      log(`Таймлайн для рекламы ${index + 1}`);
      const timelineWidth = 150 * 2.83465;
      const timelineHeight = 3 * 2.83465;
      const scoreMatch = item.text.match(/балл: ([\d.]+)/);
      const score = scoreMatch ? parseFloat(scoreMatch[1]) : 0;
      const color = score >= 0.6 ? successColor : score >= 0.3 ? warningColor : dangerColor;

      const canvas = [
        // Основная линия
        {
          type: 'line',
          x1: 0,
          y1: timelineHeight / 2,
          x2: timelineWidth,
          y2: timelineHeight / 2,
          lineWidth: 0.5,
          lineColor: textColor,
        },
      ];

      // Метки времени
      for (let t = 0; t <= videoDuration; t += 5) {
        const x = (t / videoDuration) * timelineWidth;
        canvas.push(
          {
            type: 'line',
            x1: x,
            y1: timelineHeight / 2 - 1.5,
            x2: x,
            y2: timelineHeight / 2 + 1.5,
            lineWidth: 0.5,
            lineColor: textColor,
          },
          {
            type: 'text',
            x: x,
            y: timelineHeight / 2 + 5,
            text: `${t}`,
            fontSize: 8,
            color: textColor,
            alignment: 'center',
          }
        );
      }

      // Полоса рекламы
      const startPercent = (item.start_time / videoDuration) * timelineWidth;
      const durationPercent = Math.max((item.duration / videoDuration) * timelineWidth, 2 * 2.83465);
      canvas.push(
        {
          type: 'rect',
          x: startPercent,
          y: timelineHeight / 2 - 1.5,
          w: durationPercent,
          h: 3,
          color: color,
        },
        {
          type: 'ellipse',
          x: startPercent,
          y: timelineHeight / 2,
          r1: 1.5,
          r2: 1.5,
          color: accentColor,
        },
        {
          type: 'ellipse',
          x: startPercent + durationPercent,
          y: timelineHeight / 2,
          r1: 1.5,
          r2: 1.5,
          color: accentColor,
        }
      );

      content.push(
        {
          canvas,
          margin: [0, 10, 0, 0],
        },
        {
          columns: [
            {
              text: `${item.start_time.toFixed(1)} сек`,
              fontSize: 10,
              color: textColor,
              margin: [startPercent / 2.83465, 2, 0, 0],
            },
            durationPercent > 20 * 2.83465
              ? {
                  text: `${(item.start_time + item.duration).toFixed(1)} сек`,
                  fontSize: 10,
                  color: textColor,
                  margin: [(startPercent + durationPercent) / 2.83465, 2, 0, 0],
                }
              : {},
          ],
          margin: [0, 10, 0, 0],
        }
      );
    } else {
      if (lines.length > 0) {
        lines[lines.length - 1].margin = [0, 2, 0, 10];
      }
    }

    documentDefinition.content.push(...content);
  });

  // Рекомендации
  log('Добавление рекомендаций');
  documentDefinition.content.push(
    {
      text: 'Рекомендации',
      style: 'sectionHeader',
    },
    {
      canvas: [
        {
          type: 'line',
          x1: 0,
          y1: 0,
          x2: 30,
          y2: 0,
          lineWidth: 0.5,
          lineColor: accentColor,
        },
      ],
      style: 'line',
    },
    {
      ul: [
        'Увеличьте длительность рекламы до 2-3 секунд.',
        'Разместите рекламу в центре кадра.',
        'Повысьте контрастность текста и логотипов.',
        'Используйте яркие цвета и динамику.',
        'Проводите A/B-тестирование размещений.',
      ],
      style: 'text',
    }
  );

  // Сохранение
  log('Сохранение PDF');
  const filename = file ? file.name.replace(/\.[^/.]+$/, '') : 'report';
  pdfMake.createPdf(documentDefinition).download(`${filename}_advision_report.pdf`);
  log(`PDF сохранён: ${filename}_advision_report.pdf`);
}