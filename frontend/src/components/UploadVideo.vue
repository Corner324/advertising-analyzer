<template>
    <div>
      <h2>Загрузка видео</h2>
      <input type="file" accept="video/*" @change="handleFileUpload" />
      <button :disabled="!file" @click="uploadVideo">Отправить</button>
      <p v-if="status">{{ status }}</p>
      <div v-if="report">
        <h3>Отчет</h3>
        <pre>{{ report }}</pre>
      </div>
    </div>
  </template>

  <script>
  export default {
    data() {
      return {
        file: null,
        status: "",
        report: "",
      };
    },
    methods: {
      handleFileUpload(event) {
        this.file = event.target.files[0];
      },
      async uploadVideo() {
        if (!this.file) return;
        this.status = "Обработка...";
        const formData = new FormData();
        formData.append("file", this.file);

        try {
          const response = await fetch("http://localhost:8000/upload", {
            method: "POST",
            body: formData,
          });
          const result = await response.json();
          if (response.ok) {
            this.status = "Видео обработано!";
            const reportResponse = await fetch(`http://localhost:8000/report/${result.report_path.split('/').pop()}`);
            this.report = await reportResponse.text();
          } else {
            this.status = `Ошибка: ${result.detail}`;
          }
        } catch (error) {
          this.status = `Ошибка: ${error.message}`;
        }
      },
    },
  };
  </script>