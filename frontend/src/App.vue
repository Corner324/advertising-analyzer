<template>
  <div class="min-h-screen bg-gray-100 flex">
    <!-- Боковая панель -->
    <div
      :class="{
        'w-80': isSidebarOpen,
        'w-16': !isSidebarOpen,
        'transition-all duration-300': true,
        'fixed h-full bg-gray-50 z-10 border-r border-gray-200': true,
      }"
    >
      <div class="p-4">
        <button
          class="text-gray-600 hover:text-gray-800 mb-4"
          @click="isSidebarOpen = !isSidebarOpen"
        >
          <svg
            class="h-6 w-6"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              :d="isSidebarOpen ? 'M6 18L18 6M6 6l12 12' : 'M4 6h16M4 12h16M4 18h16'"
            />
          </svg>
        </button>
        <VideoHistory
          v-if="isSidebarOpen"
          :history="history"
          @play-video="openVideoPlayer"
          @delete-video="deleteVideo"
        />
      </div>
    </div>

    <!-- Основной контент -->
    <div
      class="flex-1 p-4 transition-all duration-300"
      :class="{ 'ml-80': isSidebarOpen, 'ml-16': !isSidebarOpen }"
    >
      <UploadVideo @video-processed="addToHistory" @delete-video="deleteVideo" />
    </div>

    <!-- Модальное окно для воспроизведения -->
    <VideoPlayerModal
      :is-open="isVideoPlayerOpen"
      :video="selectedVideo"
      @close="isVideoPlayerOpen = false"
    />
  </div>
</template>

<script>
import UploadVideo from './components/UploadVideo.vue';
import VideoHistory from './components/VideoHistory.vue';
import VideoPlayerModal from './components/VideoPlayerModal.vue';

export default {
  components: { UploadVideo, VideoHistory, VideoPlayerModal },
  data() {
    return {
      isSidebarOpen: true,
      history: [],
      isVideoPlayerOpen: false,
      selectedVideo: {},
    };
  },
  methods: {
    log(message, type = 'info') {
      const logEntry = `[${new Date().toISOString()}] ${type.toUpperCase()}: ${message}`;
      console.log(logEntry);
      const logs = JSON.parse(localStorage.getItem('appLogs') || '[]');
      logs.push(logEntry);
      localStorage.setItem('appLogs', JSON.stringify(logs));
    },
    addToHistory(videoData) {
      this.history.push(videoData);
      localStorage.setItem('videoHistory', JSON.stringify(this.history));
      this.log(`Добавлено в историю: ${videoData.filename}`);
    },
    openVideoPlayer(video) {
      this.selectedVideo = video;
      this.isVideoPlayerOpen = true;
      this.log(`Открыто воспроизведение: ${video.filename}`);
    },
    deleteVideo(id) {
      this.history = this.history.filter(video => video.id !== id);
      localStorage.setItem('videoHistory', JSON.stringify(this.history));
      this.log(`Удалено из истории: ${id}`);
    },
  },
  mounted() {
    this.log('Компонент App смонтирован');
    this.log(`Запуск приложения, окружение: ${process.env.NODE_ENV}, Vite: ${import.meta.env.VITE_APP_VERSION || 'не указана'}`);
    localStorage.setItem('appStart', new Date().toISOString());
    const savedHistory = localStorage.getItem('videoHistory');
    if (savedHistory) {
      this.history = JSON.parse(savedHistory);
    }
  },
};
</script>