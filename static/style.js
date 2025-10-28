document.addEventListener("DOMContentLoaded", () => {
  const fileInput = document.querySelector('input[type="file"][name="xmlfiles"]');
  const fileCountSpan = document.getElementById('file-chosen');

  if (fileInput && fileCountSpan) {
    fileInput.addEventListener('change', () => {
      const count = fileInput.files.length;
      if (count === 0) {
        fileCountSpan.textContent = "Nenhum arquivo selecionado";
      } else if (count === 1) {
        fileCountSpan.textContent = "1 arquivo selecionado";
      } else {
        fileCountSpan.textContent = `${count} arquivos selecionados`;
      }
    });
  }
});