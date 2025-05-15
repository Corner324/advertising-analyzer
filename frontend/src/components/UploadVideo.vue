<template>
  <div class="min-h-screen bg-gray-100 flex items-center justify-center p-4">
    <div class="max-w-3xl w-full bg-white rounded-xl shadow-2xl p-8">
      <!-- Заголовок -->
      <h2 class="text-3xl font-bold text-gray-900 mb-6 text-center">Анализ рекламного видео</h2>

      <!-- Зона drag-and-drop -->
      <div
        class="border-2 border-dashed rounded-lg p-10 text-center transition-all duration-300"
        :class="{
          'border-blue-600 bg-blue-50': isDragging,
          'border-green-600 bg-green-100': success && !file,
          'border-gray-300': !isDragging && !success
        }"
        @dragover.prevent="isDragging = true"
        @dragleave.prevent="isDragging = false"
        @drop.prevent="handleDrop"
      >
        <input
          type="file"
          accept="video/*"
          class="hidden"
          ref="fileInput"
          @change="handleFileUpload"
        />
        <div v-if="!file">
          <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
          </svg>
          <p class="mt-2 text-gray-600">Перетащите видео сюда или</p>
          <button
            class="mt-4 bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition-all duration-200"
            @click="$refs.fileInput.click()"
          >
            Выберите файл
          </button>
        </div>
        <div v-else class="flex items-center justify-center space-x-4">
          <svg class="h-10 w-10 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 4v16l13-8L7 4z" />
          </svg>
          <span class="text-gray-800 font-medium">{{ file.name }}</span>
          <button
            class="text-red-500 hover:text-red-600"
            @click="clearFile"
          >
            <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <!-- Прогресс -->
      <div v-if="uploadProgress > 0 && uploadProgress < 100" class="mt-4">
        <div class="w-full bg-gray-200 rounded-full h-2.5">
          <div
            class="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
            :style="{ width: `${uploadProgress}%` }"
          ></div>
        </div>
        <p class="text-sm text-gray-600 mt-2">Загрузка: {{ uploadProgress }}%</p>
      </div>
      <p v-if="isLoading && uploadProgress === 100" class="mt-4 text-sm text-gray-600 text-center">
        Загрузка завершена, обработка видео на сервере...
      </p>

      <!-- Кнопка отправки -->
      <button
        class="mt-6 w-full bg-gradient-to-r from-blue-600 to-blue-700 text-white py-3 rounded-lg hover:from-blue-700 hover:to-blue-800 transition-all duration-200 disabled:opacity-50"
        :disabled="!file || isLoading"
        @click="uploadVideo"
      >
        {{ isLoading ? 'Обработка...' : 'Анализировать видео' }}
      </button>

      <!-- Статус -->
      <div v-if="status" class="mt-4 flex items-center justify-center space-x-2">
        <svg v-if="status.includes('Ошибка')" class="h-5 w-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p class="text-center text-sm" :class="status.includes('Ошибка') ? 'text-red-600' : 'text-green-600'">
          {{ status }}
        </p>
      </div>

      <!-- Сообщение о дополнительном ожидании -->
      <p v-if="showWaitMessage" class="mt-4 text-sm text-gray-600 text-center">
        Обработка может занять дополнительное время, пожалуйста, подождите.
      </p>

      <!-- Экран ожидания -->
      <div v-if="isLoading" class="fixed inset-0 bg-gray-900 bg-opacity-75 flex items-center justify-center z-50">
        <div class="bg-white rounded-xl p-8 flex flex-col items-center shadow-lg w-full max-w-2xl">
          <div class="animate-spin rounded-full h-12 w-12 border-t-4 border-blue-600"></div>
          <p class="mt-4 text-gray-800 font-medium">
            {{ uploadProgress === 100 ? 'Обработка видео...' : 'Загрузка видео...' }}
          </p>
          <div v-if="processingProgress < 100 && uploadProgress === 100" class="w-full mt-4">
            <div class="w-full bg-gray-200 rounded-full h-2.5">
              <div
                class="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
                :style="{ width: `${processingProgress}%` }"
              ></div>
            </div>
            <p class="text-sm text-gray-600 mt-2">Обработка: {{ processingProgress.toFixed(2) }}%</p>
          </div>
          <div v-if="backendLogs.length > 0" class="mt-4 w-full max-h-64 overflow-y-auto bg-gray-100 p-4 rounded-lg">
            <p class="text-sm text-gray-800 font-medium mb-2">Логи обработки:</p>
            <div v-for="(log, index) in backendLogs" :key="index" class="text-xs text-gray-700 mb-1">
              {{ log }}
            </div>
          </div>
        </div>
      </div>

      <!-- Отчет -->
      <div v-if="report" class="mt-8 animate-fade-in">
        <div class="flex justify-between items-center mb-4">
          <h3 class="text-2xl font-semibold text-gray-900">Результаты анализа</h3>
          <button
            class="bg-gradient-to-r from-blue-600 to-blue-700 text-white px-4 py-2 rounded-lg hover:from-blue-700 hover:to-blue-800 transition-all duration-200"
            :disabled="!report"
            @click="saveToPDF"
          >
            Сохранить в PDF
          </button>
        </div>
        <div class="bg-gray-50 p-6 rounded-lg shadow-inner">
          <div v-for="(item, index) in formatReport" :key="index" class="mb-6 last:mb-0">
            <div class="border-l-4 border-blue-600 pl-4">
              <p v-for="line in item.text.split('\n')" :key="line" class="text-gray-700 leading-relaxed">{{ line }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios';
import axiosRetry from 'axios-retry';
import { v4 as uuidv4 } from 'uuid';
import jsPDF from 'jspdf';

axiosRetry(axios, {
  retries: 3,
  retryDelay: (retryCount) => retryCount * 1000,
  retryCondition: (error) => error.code === 'ECONNREFUSED' || error.code === 'ECONNABORTED',
});

export default {
  data() {
    return {
      file: null,
      status: '',
      report: '',
      isDragging: false,
      isLoading: false,
      uploadProgress: 0,
      processingProgress: 0,
      backendLogs: [],
      logs: [],
      backendAvailable: false,
      success: false,
      progressInterval: null,
      logInterval: null,
      videoId: null,
      showWaitMessage: false,
      processingTimeout: null,
    };
  },
  computed: {
    formatReport() {
      if (!this.report) return [];
      const items = this.report.split('\n\n').filter(item => item.trim());
      const regex = /Реклама в видео [0-9a-f-]+\.mp4/;
      // Временные start_time с интервалами, пока нет данных от бэкенда
      let currentTime = 2.0; // Начало первой рекламы
      return items.map((item, index) => {
        const text = this.file ? item.replace(regex, `Реклама в видео ${this.file.name}`) : item;
        // Парсинг duration из текста
        let duration = 0;
        const durationMatch = item.match(/Длительность: ([\d.]+) сек/);
        if (durationMatch) {
          duration = parseFloat(durationMatch[1]);
        }
        // Парсинг start_time (если будет в отчёте)
        let start_time = currentTime;
        const startTimeMatch = item.match(/Начало: ([\d.]+) сек/);
        if (startTimeMatch) {
          start_time = parseFloat(startTimeMatch[1]);
        }
        // Обновляем currentTime для следующей рекламы
        currentTime += duration + 4.0; // Интервал 4 сек между рекламой
        this.log(`Секция ${index + 1}: start_time=${start_time}, duration=${duration}`);
        return { text, start_time, duration };
      });
    },
  },
  methods: {
    log(message, type = 'info') {
      const logEntry = `[${new Date().toISOString()}] ${type.toUpperCase()}: ${message}`;
      console.log(logEntry);
      this.logs.push(logEntry);
      try {
        localStorage.setItem('appLogs', JSON.stringify(this.logs));
      } catch (e) {
        console.error(`Ошибка сохранения логов в localStorage: ${e.message}`);
      }
    },
    handleFileUpload(event) {
      this.log('Обработка выбора файла');
      const file = event.target.files[0];
      if (file && file.size > 500 * 1024 * 1024) {
        this.status = 'Ошибка: Файл слишком большой (максимум 500 МБ)';
        this.log('Файл слишком большой', 'error');
        return;
      }
      this.file = file;
      this.isDragging = false;
      this.status = '';
      this.report = '';
      this.uploadProgress = 0;
      this.success = false;
      this.showWaitMessage = false;
      this.log(`Файл выбран: ${file?.name}, размер: ${(file.size / 1024 / 1024).toFixed(2)} МБ`);
    },
    handleDrop(event) {
      this.log('Обработка перетаскивания файла');
      const file = event.dataTransfer.files[0];
      if (file && file.size > 500 * 1024 * 1024) {
        this.status = 'Ошибка: Файл слишком большой (максимум 500 МБ)';
        this.log('Файл слишком большой', 'error');
        return;
      }
      this.file = file;
      this.isDragging = false;
      this.status = '';
      this.report = '';
      this.uploadProgress = 0;
      this.success = false;
      this.showWaitMessage = false;
      this.log(`Файл перетащен: ${file?.name}, размер: ${(file.size / 1024 / 1024).toFixed(2)} МБ`);
    },
    clearFile() {
      this.log('Очистка файла');
      this.file = null;
      this.status = '';
      this.report = '';
      this.uploadProgress = 0;
      this.success = false;
      this.showWaitMessage = false;
      this.log('Файл удалён');
    },
    async checkBackend() {
      this.log('Проверка доступности бэкенда: /api/health');
      const startTime = Date.now();
      try {
        const response = await axios.get('/api/health', {
          timeout: 5000,
          headers: { 'X-Debug': 'health-check' },
        });
        this.backendAvailable = response.status === 200;
        this.log(`Бэкенд доступен: ${response.status} ${response.statusText}, данные: ${JSON.stringify(response.data)}, время: ${Date.now() - startTime} мс`);
      } catch (error) {
        this.backendAvailable = false;
        this.log(`Бэкенд недоступен: ${error.message} (${error.code || 'нет кода'})`, 'error');
        this.log(`Конфигурация запроса: ${JSON.stringify(error.config)}`, 'error');
      }
      return this.backendAvailable;
    },
    startProcessingProgress() {
      this.log('Запуск прогресса обработки');
      this.processingProgress = 0;
      const totalTime = 300000;
      const intervalTime = 1000;
      const increment = (intervalTime / totalTime) * 100;
      this.progressInterval = setInterval(() => {
        if (this.processingProgress < 100) {
          this.processingProgress = Math.min(this.processingProgress + increment + (Math.random() * increment * 0.5), 99);
        }
      }, intervalTime);
    },
    stopProcessingProgress() {
      this.log('Остановка прогресса обработки');
      if (this.progressInterval) {
        clearInterval(this.progressInterval);
        this.progressInterval = null;
      }
      if (this.processingTimeout) {
        clearTimeout(this.processingTimeout);
        this.processingTimeout = null;
      }
      this.processingProgress = 100;
    },
    async fetchBackendLogs() {
      if (!this.videoId) return;
      this.log(`Запрос логов для videoId: ${this.videoId}`);
      try {
        const response = await axios.get(`/api/logs?video_id=${this.videoId}`, {
          timeout: 5000,
          headers: { 'X-Debug': 'log-request' },
        });
        this.backendLogs = response.data.logs;
        this.log(`Получено логов: ${response.data.logs.length}`);
      } catch (error) {
        this.log(`Ошибка получения логов: ${error.message}`, 'error');
      }
    },
    async uploadVideo() {
      this.log('Начало загрузки видео');
      if (!this.file) {
        this.status = 'Ошибка: Файл не выбран';
        this.log('Попытка загрузки без файла', 'error');
        return;
      }

      this.isLoading = true;
      this.status = 'Проверка соединения...';
      this.uploadProgress = 0;
      this.backendLogs = [];
      this.videoId = null;
      this.success = false;
      this.showWaitMessage = false;
      this.report = '';
      const startTime = Date.now();
      this.log(`Начало загрузки файла: ${this.file.name}, размер: ${(this.file.size / 1024 / 1024).toFixed(2)} МБ`);

      if (!(await this.checkBackend())) {
        this.status = 'Ошибка: Сервер недоступен. Проверьте соединение.';
        this.isLoading = false;
        this.log('Загрузка отменена: бэкенд недоступен', 'error');
        return;
      }

      this.logInterval = setInterval(() => this.fetchBackendLogs(), 1000);

      this.processingTimeout = setTimeout(() => {
        this.showWaitMessage = true;
        this.log('Истекло 5 минут обработки, отображено сообщение ожидания', 'info');
      }, 300000);

      const formData = new FormData();
      formData.append('file', this.file);
      formData.append('filename', this.file.name);

      try {
        this.log('Отправка POST-запроса на /api/upload');
        const response = await axios.post('/api/upload', formData, {
          timeout: 300000,
          headers: {
            'Content-Type': 'multipart/form-data',
            'X-Debug': 'upload-request',
          },
          onUploadProgress: (progressEvent) => {
            const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            this.uploadProgress = percent;
            this.log(`Прогресс загрузки: ${percent}%, время: ${Date.now() - startTime} мс`);
            if (percent === 100) {
              this.startProcessingProgress();
            }
          },
        });

        this.videoId = response.data.video_id;
        this.stopProcessingProgress();
        clearInterval(this.logInterval);
        this.showWaitMessage = false;
        this.log(`Ответ получен: ${response.status} ${response.statusText}, время: ${Date.now() - startTime} мс`);
        this.log(`Данные ответа: ${JSON.stringify(response.data)}`);
        if (response.data.report_path.includes(response.data.video_id)) {
          this.log('Использован кэшированный отчёт', 'info');
        }

        const reportId = response.data.report_path.split('/').pop().replace('_report.txt', '');
        this.log(`Формирование reportId: ${reportId}`);
        const reportUrl = `/api/report/${reportId}`;
        this.log(`Запрос отчета: ${reportUrl}`);

        const reportResponse = await axios.get(reportUrl, {
          timeout: 30000,
          headers: { 'X-Debug': 'report-request' },
        });
        this.log(`Отчет получен: ${reportResponse.status} ${response.statusText}, время: ${Date.now() - startTime} мс`);
        this.log(`Содержимое отчёта: ${reportResponse.data}`);
        this.report = reportResponse.data;
        this.success = true;

        const videoData = {
          id: uuidv4(),
          filename: this.file.name,
          date: new Date().toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }),
          status: 'Успех',
          videoUrl: URL.createObjectURL(this.file),
        };
        this.$emit('video-processed', videoData);

        this.status = '';
      } catch (error) {
        this.stopProcessingProgress();
        clearInterval(this.logInterval);
        this.showWaitMessage = false;
        let errorMessage = 'Неизвестная ошибка';
        if (error.response) {
          errorMessage = `Сервер ответил ошибкой: ${error.response.status} ${error.response.statusText}`;
          this.log(`Ошибка ответа: ${JSON.stringify(error.response.data)}`, 'error');
        } else if (error.request) {
          errorMessage = 'Сервер не ответил вовремя. Обработка может занять дополнительное время, пожалуйста, подождите.';
          this.log(`Ошибка: Нет ответа от сервера (${error.code || 'нет кода'})`, 'error');
        } else {
          errorMessage = error.message;
          this.log(`Ошибка: ${error.message}`, 'error');
        }
        this.status = `Ошибка: ${errorMessage}`;
        this.log(`Полная ошибка: ${JSON.stringify(error, Object.getOwnPropertyNames(error))}`, 'error');
        this.log(`Конфигурация запроса: ${JSON.stringify(error.config)}`, 'error');
        this.log(`Время ошибки: ${Date.now() - startTime} мс`, 'error');

        const videoData = {
          id: uuidv4(),
          filename: this.file.name,
          date: new Date().toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }),
          status: 'Ошибка',
          videoUrl: URL.createObjectURL(this.file),
        };
        this.$emit('video-processed', videoData);
      } finally {
        this.isLoading = false;
        this.uploadProgress = 0;
        this.backendLogs = [];
        this.videoId = null;
        this.log('Завершение загрузки видео');
      }
    },
    async saveToPDF() {
      this.log('Начало генерации PDF отчёта');
      try {
        // Проверка отчёта
        this.log(`formatReport: ${JSON.stringify(this.formatReport)}`);
        if (!this.formatReport || !this.formatReport.length) {
          this.log('Ошибка: отчёт пустой', 'error');
          this.status = 'Ошибка: Отчёт пустой';
          return;
        }

        this.log('Инициализация jsPDF');
        const doc = new jsPDF({
          orientation: 'portrait',
          unit: 'mm',
          format: 'a4',
        });

        // Загрузка шрифта
        this.log('Попытка загрузки шрифта /fonts/NotoSans-Regular.ttf');
        const fontResponse = await fetch('/fonts/NotoSans-Regular.ttf');
        this.log(`Статус ответа шрифта: ${fontResponse.status}`);
        if (!fontResponse.ok) {
          this.log(`Не удалось загрузить шрифт: ${fontResponse.statusText}`, 'error');
          this.log('Использование шрифта helvetica как запасного', 'warning');
          doc.setFont('helvetica', 'normal');
        } else {
          const fontArrayBuffer = await fontResponse.arrayBuffer();
          this.log(`Шрифт загружен, размер: ${fontArrayBuffer.byteLength} байт`);
          const fontBytes = new Uint8Array(fontArrayBuffer);
          let binary = '';
          const chunkSize = 8192;
          for (let i = 0; i < fontBytes.length; i += chunkSize) {
            const chunk = fontBytes.subarray(i, i + chunkSize);
            binary += String.fromCharCode.apply(null, chunk);
          }
          const base64String = btoa(binary);
          this.log('Шрифт конвертирован в base64');
          doc.addFileToVFS('NotoSans-Regular.ttf', base64String);
          doc.addFont('NotoSans-Regular.ttf', 'NotoSans', 'normal');
          doc.setFont('NotoSans');
          this.log('Шрифт установлен: NotoSans');
        }

        // Параметры страницы
        const margin = 15;
        const pageWidth = doc.internal.pageSize.getWidth();
        const maxLineWidth = pageWidth - 2 * margin;
        let y = margin;
        // Предполагаемая длина видео
        const videoDuration = 30; // в секундах

        // Заголовок
        this.log('Добавление заголовка');
        doc.setFontSize(16);
        doc.text('Отчет по качеству отображения рекламы', margin, y, { maxWidth: maxLineWidth });
        y += 10;

        // Разделитель
        this.log('Добавление разделителя');
        doc.setLineWidth(0.5);
        doc.line(margin, y, pageWidth - margin, y);
        y += 10;

        // Текст отчёта и таймлайн
        this.log('Добавление текста отчёта и таймлайнов');
        doc.setFontSize(12);
        this.formatReport.forEach((item, index) => {
          if (index === 0 && item.text.includes('Отчет по качеству')) {
            // Пропускаем заголовок отчёта, он уже добавлен
            return;
          }
          if (y > doc.internal.pageSize.getHeight() - 30) {
            this.log(`Добавление новой страницы, текущая y: ${y}`);
            doc.addPage();
            y = margin;
          }
          // Текст группы
          const lines = doc.splitTextToSize(item.text, maxLineWidth);
          this.log(`Обработка секции ${index}: строк=${lines.length}, start_time=${item.start_time}, duration=${item.duration}`);
          doc.text(lines, margin, y);
          y += lines.length * 7;

          // Таймлайн
          if (item.start_time !== undefined && item.duration !== undefined && item.duration > 0) {
            this.log(`Отрисовка таймлайна для секции ${index}: start_time=${item.start_time}, duration=${item.duration}`);
            // Фон таймлайна (серая линия)
            doc.setLineWidth(0.5);
            doc.setDrawColor(200, 200, 200);
            doc.setFillColor(200, 200, 200);
            const timelineWidth = 150;
            const timelineX = margin;
            const timelineY = y + 2;
            doc.line(timelineX, timelineY, timelineX + timelineWidth, timelineY);

            // Полоса рекламы (синяя)
            const startPercent = (item.start_time / videoDuration) * timelineWidth;
            const durationPercent = Math.max((item.duration / videoDuration) * timelineWidth, 2); // Минимальная ширина 2 мм
            doc.setFillColor(59, 130, 246); // Синий цвет
            doc.rect(timelineX + startPercent, timelineY - 1, durationPercent, 2, 'F');

            // Подписи времени
            doc.setFontSize(10);
            doc.setTextColor(0, 0, 0);
            const startLabel = `${item.start_time.toFixed(1)} сек`;
            const endLabel = `${(item.start_time + item.duration).toFixed(1)} сек`;
            doc.text(startLabel, timelineX + startPercent, timelineY - 2);
            if (durationPercent > 20) { // Показываем endLabel, если полоса длинная
              doc.text(endLabel, timelineX + startPercent + durationPercent, timelineY - 2);
            }
            y += 10; // Отступ после таймлайна
          }
          if (index < this.formatReport.length - 1) {
            doc.setLineWidth(0.2);
            doc.line(margin, y, pageWidth - margin, y);
            y += 5;
          }
        });

        // Сохранение файла
        this.log('Сохранение PDF');
        const filename = this.file ? this.file.name.replace(/\.[^/.]+$/, '') : 'report';
        doc.save(`${filename}_report.pdf`);
        this.log(`PDF успешно сохранён: ${filename}_report.pdf`);
      } catch (error) {
        this.log(`Ошибка генерации PDF: ${error.message}, stack: ${error.stack}`, 'error');
        this.status = 'Ошибка: Не удалось сохранить PDF';
      }
    },
    deleteVideo(id) {
      this.log(`Удаление видео с id: ${id}`);
      this.$emit('delete-video', id);
    },
  },
  async mounted() {
    this.log('Компонент UploadVideo смонтирован');
    const savedLogs = localStorage.getItem('appLogs');
    if (savedLogs) {
      this.logs = JSON.parse(savedLogs);
      this.log(`Загружено ${this.logs.length} сохранённых логов`);
    }
    await this.checkBackend();
  },
};
</script>

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.5s ease-in;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>