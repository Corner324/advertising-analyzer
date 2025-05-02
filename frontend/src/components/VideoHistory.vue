<template>
    <div>
      <h3 class="text-lg font-semibold mb-4">История загрузок</h3>
      <div v-if="history.length === 0" class="text-gray-600">История пуста</div>
      <div v-for="video in history" :key="video.id" class="mb-4 p-3 bg-white rounded-lg shadow">
        <p class="text-sm font-medium">{{ video.filename }}</p>
        <p class="text-xs text-gray-600">{{ video.date }}</p>
        <p class="text-xs" :class="video.status === 'Успех' ? 'text-green-600' : 'text-red-600'">{{ video.status }}</p>
        <div class="mt-2 flex space-x-2">
          <button
            @click="$emit('play-video', video)"
            class="text-blue-500 hover:text-blue-600"
            title="Воспроизвести"
          >
            <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.2A1 1 0 0010 9.768v4.464a1 1 0 001.555.832l3.197-2.2a1 1 0 000-1.664z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </button>
          <button
            @click="$emit('delete-video', video.id)"
            class="text-red-500 hover:text-red-600"
            title="Удалить"
          >
            <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5-4h4a1 1 0 011 1v1H9V4a1 1 0 011-1zm-7 4h18" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </template>

  <script>
  export default {
    props: {
      history: {
        type: Array,
        required: true,
      },
    },
  };
  </script>

  <style scoped>
  button {
    transition: color 0.2s ease-in-out;
  }
  </style>