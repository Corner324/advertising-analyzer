<template>
  <div class="min-h-screen bg-gray-100 flex items-center justify-center p-4">
    <UploadVideo />
  </div>
</template>

<script>
import UploadVideo from './components/UploadVideo.vue';

export default {
  components: { UploadVideo },
  methods: {
    log(message, type = 'info') {
      const logEntry = `[${new Date().toISOString()}] ${type.toUpperCase()}: ${message}`;
      console.log(logEntry);
      const logs = JSON.parse(localStorage.getItem('appLogs') || '[]');
      logs.push(logEntry);
      localStorage.setItem('appLogs', JSON.stringify(logs));
    },
  },
  mounted() {
    this.log('Компонент App смонтирован');
    this.log(`Запуск приложения, окружение: ${process.env.NODE_ENV}, Vite: ${import.meta.env.VITE_APP_VERSION || 'не указана'}`);
    localStorage.setItem('appStart', new Date().toISOString());
  },
};
</script>