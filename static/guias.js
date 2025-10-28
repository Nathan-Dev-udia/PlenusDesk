document.addEventListener("DOMContentLoaded", () => {
  const tabs = document.querySelectorAll(".tab");
  const content = document.getElementById("dynamic-content");

  // Conteúdos simulados para cada aba
  const pages = {
    mural: content.innerHTML, // mantém o conteúdo original dos cards
    guiaspostadas: `
    <div class="add-guide-container">
        <a href="/cadastroguias" class="add-guide-btn">+ Adicionar guia</a>
    </div>

    <div class="card">
        <div class="icon">
        <i data-lucide="clipboard"></i>
        </div>
        <div class="content">
        <h3>Guia postada 1</h3>
        <p class="meta">Postado dia: 18 set, 2025 às 14:00</p>
        <p class="empresa">Empresa A <span class="cnpj">12.345.678/0001-90</span></p>
        </div>
    </div>

    <div class="card">
        <div class="icon">
        <i data-lucide="clipboard"></i>
        </div>
        <div class="content">
        <h3>Guia postada 2</h3>
        <p class="meta">Postado dia: 20 set, 2025 às 11:30</p>
        <p class="empresa">Empresa B <span class="cnpj">98.765.432/0001-12</span></p>
        </div>
    </div>
    `,
    empresas: `
      <div class="card">
        <div class="icon">
          <i data-lucide="briefcase"></i>
        </div>
        <div class="content">
          <h3>Empresa A</h3>
          <p class="meta">CNPJ: 12.345.678/0001-90</p>
        </div>
      </div>
      <div class="card">
        <div class="icon">
          <i data-lucide="briefcase"></i>
        </div>
        <div class="content">
          <h3>Empresa B</h3>
          <p class="meta">CNPJ: 98.765.432/0001-12</p>
        </div>
      </div>
    `
  };

  tabs.forEach(tab => {
    tab.addEventListener("click", (e) => {
      e.preventDefault();

      // Remove active de todas
      tabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");

      const page = tab.getAttribute("data-page");
      content.innerHTML = pages[page];

      // recria os ícones do lucide
      lucide.createIcons();
    });
  });
});
