<template>
    <div
      v-if="isOpen"
      class="fixed inset-0 bg-gray-900 bg-opacity-75 flex items-center justify-center z-50"
    >
      <div class="bg-white rounded-xl p-6 max-w-3xl w-full">
        <div class="flex justify-between items-center mb-4">
          <h3 class="text-lg font-semibold text-gray-900">{{ video.filename }}</h3>
          <button
            class="text-gray-500 hover:text-gray-700"
            @click="$emit('close')"
          >
            <svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <video
          :src="video.videoUrl"
          controls
          class="w-full rounded-lg"
          autoplay
        ></video>
      </div>
    </div>
  </template>

  <script>
  export default {
    props: {
      isOpen: {
        type: Boolean,
        default: false,
      },
      video: {
        type: Object,
        default: () => ({}),
      },
    },
    methods: {
      log(message, type = 'info') {
        const logEntry = `[${new Date().toISOString()}] ${type.toUpperCase()}: ${message}`;
        console.log(logEntry);
        const logs = JSON.parse(localStorage.getItem('appLogs') || '[]');
        logs.push(logEntry);
        localStorage.setItem('appLogs', JSON.stringify(logs));
      },
    },
  };
  </script>