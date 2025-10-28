// ----------------- UPLOAD DE XML -----------------
document.getElementById("xmlfiles").addEventListener("change", function(event) {
    const files = event.target.files;
    const tableBody = document.querySelector("#tabela_boletos tbody");
    tableBody.innerHTML = ""; // Limpa a tabela antes de exibir os novos dados

    Array.from(files).forEach(file => {
        const reader = new FileReader();

        reader.onload = function(e) {
            const parser = new DOMParser();
            const xmlDoc = parser.parseFromString(e.target.result, "text/xml");

            const numeroDoc = xmlDoc.querySelector("nDup")?.textContent || "N/A";
            const parcela = xmlDoc.querySelector("nPar")?.textContent || "N/A"; 
            const vencimento = xmlDoc.querySelector("dVenc")?.textContent || "N/A";
            const valor = xmlDoc.querySelector("vDup")?.textContent || "N/A";

            // Converte data para DD/MM/YYYY
            let vencimentoBR = vencimento;
            if (/^\d{4}-\d{2}-\d{2}$/.test(vencimento)) {
                const partes = vencimento.split("-");
                vencimentoBR = `${partes[2]}/${partes[1]}/${partes[0]}`;
            }

            const row = document.createElement("tr");
            row.innerHTML = `
                <td>${numeroDoc}</td>
                <td>${parcela}</td>
                <td>${vencimentoBR}</td>
                <td>${valor}</td>
            `;
            tableBody.appendChild(row);
        };

        reader.readAsText(file);
    });
});

// ----------------- DATE PICKER CUSTOMIZADO -----------------
const calendarBtn = document.getElementById('calendarBtn');
const datePicker = document.getElementById('datePicker');
const customPeriod = document.getElementById('customPeriod');
const startDateInput = document.getElementById('startDate');
const endDateInput = document.getElementById('endDate');

const monthPicker = document.getElementById('monthPicker');
const currentYearSpan = document.getElementById('currentYear');
let selectedYear = new Date().getFullYear();
currentYearSpan.textContent = selectedYear;

// Helper para posicionar qualquer elemento abaixo do botão
function posicionarElemento(elem) {
    const rect = calendarBtn.getBoundingClientRect();
    elem.style.position = "absolute";
    elem.style.top = rect.bottom + window.scrollY + "px";
    elem.style.left = rect.left + window.scrollX + "px";
    elem.style.zIndex = 999;
}

// Posicionar datePicker
function posicionarDatePicker() {
    posicionarElemento(datePicker);
}

calendarBtn.addEventListener('click', () => {
    if (datePicker.style.display === 'block') {
        datePicker.style.display = 'none';
    } else {
        posicionarDatePicker();
        datePicker.style.display = 'block';
        monthPicker.style.display = 'none';
        customPeriod.style.display = 'none';
    }
});

// Navegação de ano
document.getElementById('prevYear').addEventListener('click', () => {
    selectedYear--;
    currentYearSpan.textContent = selectedYear;
});
document.getElementById('nextYear').addEventListener('click', () => {
    selectedYear++;
    currentYearSpan.textContent = selectedYear;
});

// Seleção do mês
document.querySelectorAll('.month').forEach(monthDiv => {
    monthDiv.addEventListener('click', () => {
        const month = monthDiv.getAttribute('data-month');
        const firstDay = `${selectedYear}-${month}-01`;
        const lastDayDate = new Date(selectedYear, parseInt(month), 0);
        const lastDay = `${selectedYear}-${month}-${lastDayDate.getDate()}`;

        startDateInput.value = firstDay;
        endDateInput.value = lastDay;

        monthPicker.style.display = 'none';
        datePicker.style.display = 'none';

        filtrarTabela();
    });
});

// Opções rápidas
document.getElementById('opHoje').addEventListener('click', () => {
    const today = new Date().toISOString().split('T')[0];
    startDateInput.value = today;
    endDateInput.value = today;
    customPeriod.style.display = 'none';
    monthPicker.style.display = 'none';
    datePicker.style.display = 'none';
    filtrarTabela();
});

document.getElementById('opSemana').addEventListener('click', () => {
    const curr = new Date();
    const first = new Date(curr.setDate(curr.getDate() - curr.getDay() + 1));
    const last = new Date(first);
    last.setDate(first.getDate() + 6);
    startDateInput.value = first.toISOString().split('T')[0];
    endDateInput.value = last.toISOString().split('T')[0];
    customPeriod.style.display = 'none';
    monthPicker.style.display = 'none';
    datePicker.style.display = 'none';
    filtrarTabela();
});

// Abrir Month Picker
document.getElementById('opMes').addEventListener('click', () => {
    monthPicker.style.display = 'flex';
    customPeriod.style.display = 'none';
    datePicker.style.display = 'block';
    posicionarElemento(monthPicker);
});

// Abrir Custom Period
document.getElementById('opCustom').addEventListener('click', () => {
    customPeriod.style.display = 'flex';
    monthPicker.style.display = 'none';
    datePicker.style.display = 'block';
    posicionarElemento(customPeriod);
});

document.getElementById('applyCustom').addEventListener('click', () => {
    customPeriod.style.display = 'none';
    monthPicker.style.display = 'none';
    datePicker.style.display = 'none';
    filtrarTabela();
});

// ----------------- FILTRO DE TABELA -----------------
function filtrarTabela() {
    const inicio = startDateInput.value;
    const fim = endDateInput.value;

    const linhas = document.querySelectorAll("#tabela_boletos tbody tr");

    linhas.forEach(linha => {
        const tdData = linha.cells[2]; // Coluna Data de Vencimento
        if (tdData) {
            const dataPagamento = tdData.textContent.trim();
            let mostrar = true;

            // Converte DD/MM/YYYY → YYYY-MM-DD
            let dataNormalizada = dataPagamento.includes("/")
                ? dataPagamento.split("/").reverse().join("-")
                : dataPagamento;

            if (inicio && fim) {
                mostrar = dataNormalizada >= inicio && dataNormalizada <= fim;
            }

            linha.style.display = mostrar ? "" : "none";
        }
    });
}