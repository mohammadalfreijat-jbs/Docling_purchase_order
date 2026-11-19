/**
 * upload.js — handles drag-and-drop upload, result rendering, and CSV export
 * for the Purchase Order Consolidator.
 */

// ============================================================
// Shared helpers
// ============================================================

function fmt(n) {
  return Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function tagPO(text) {
  return `<span class="tag-po">${esc(text)}</span>`;
}

function tagVendor(text) {
  return `<span class="tag-vendor">${esc(text)}</span>`;
}

function esc(str) {
  const el = document.createElement('span');
  el.textContent = str;
  return el.innerHTML;
}

// ============================================================
// UPLOAD PAGE logic
// ============================================================

const isUploadPage = document.getElementById('drop-zone');

if (isUploadPage) {
  const dropZone   = document.getElementById('drop-zone');
  const fileInput  = document.getElementById('file-input');
  const fileList   = document.getElementById('file-list');
  const processBtn = document.getElementById('process-btn');
  const errorBanner = document.getElementById('error-banner');
  const errorMsg   = document.getElementById('error-msg');
  const loadingOverlay = document.getElementById('loading-overlay');
  const loadingMsgEl  = document.getElementById('loading-msg');

  let selectedFiles = [];

  // Open file browser on click
  dropZone.addEventListener('click', () => fileInput.click());
  dropZone.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') fileInput.click(); });

  // File input change
  fileInput.addEventListener('change', () => {
    addFiles(Array.from(fileInput.files));
    fileInput.value = '';
  });

  // Drag events
  dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    addFiles(Array.from(e.dataTransfer.files));
  });

  function addFiles(files) {
    const pdfs = files.filter(f => f.name.toLowerCase().endsWith('.pdf'));
    if (pdfs.length !== files.length) showError('Only PDF files are accepted.');
    else hideError();

    // Deduplicate by name
    pdfs.forEach(f => {
      if (!selectedFiles.find(sf => sf.name === f.name)) selectedFiles.push(f);
    });
    renderFileList();
  }

  function renderFileList() {
    fileList.innerHTML = '';
    selectedFiles.forEach((f, i) => {
      const li = document.createElement('li');
      li.innerHTML = `${esc(f.name)} <span style="color:#8d8d8d;">(${(f.size/1024).toFixed(1)} KB)</span>
        <button type="button" onclick="removeFile(${i})"
          style="background:none;border:none;color:#da1e28;cursor:pointer;margin-left:.5rem;font-size:.8rem;">✕</button>`;
      fileList.appendChild(li);
    });
    processBtn.disabled = selectedFiles.length === 0;
  }

  window.removeFile = function(i) {
    selectedFiles.splice(i, 1);
    renderFileList();
  };

  function showError(msg) {
    errorMsg.textContent = msg;
    errorBanner.style.display = 'block';
  }
  function hideError() {
    errorBanner.style.display = 'none';
  }

  // Process button
  processBtn.addEventListener('click', async () => {
    if (!selectedFiles.length) return;
    hideError();

    loadingMsgEl.textContent = `Processing ${selectedFiles.length} file(s) via Docling…`;
    loadingOverlay.classList.add('visible');
    processBtn.disabled = true;

    const formData = new FormData();
    selectedFiles.forEach(f => formData.append('files[]', f));

    try {
      const resp = await fetch('/api/process', { method: 'POST', body: formData });
      const data = await resp.json();

      if (!resp.ok) {
        throw new Error(data.error || `Server error ${resp.status}`);
      }

      // Store result in sessionStorage and navigate to results page
      sessionStorage.setItem('po_result', JSON.stringify(data));
      window.location.href = '/results';
    } catch (err) {
      showError(err.message);
      processBtn.disabled = false;
    } finally {
      loadingOverlay.classList.remove('visible');
    }
  });
}

// ============================================================
// RESULTS PAGE logic
// ============================================================

const isResultsPage = document.getElementById('stat-grid');

if (isResultsPage) {
  const raw = sessionStorage.getItem('po_result');
  if (!raw) {
    // Nothing in session — redirect back to upload
    window.location.href = '/';
  } else {
    const result = JSON.parse(raw);
    renderStats(result);
    renderLineItems(result.line_items || []);
    renderByVendor(result.by_vendor || []);
    renderByProduct(result.by_product || []);
    setupExport(result.line_items || []);
  }

  function renderStats(r) {
    const grid = document.getElementById('stat-grid');
    const cards = [
      { label: 'Total POs',      value: r.total_pos,     cls: 'purple'  },
      { label: 'Total Vendors',  value: r.total_vendors,  cls: 'green'   },
      { label: 'Line Items',     value: (r.line_items || []).length, cls: 'magenta' },
      { label: 'Total Spend',    value: '$' + fmt(r.total_spend), cls: 'blue' },
    ];
    grid.innerHTML = cards.map(c => `
      <div class="stat-card ${c.cls}">
        <div class="stat-value">${esc(String(c.value))}</div>
        <div class="stat-label">${esc(c.label)}</div>
      </div>
    `).join('');
  }

  function renderLineItems(items) {
    const tbody = document.getElementById('tbody-line-items');
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:#8d8d8d;">No line items found.</td></tr>';
      return;
    }
    tbody.innerHTML = items.map(r => `
      <tr>
        <td>${tagPO(r.po_number)}</td>
        <td>${tagVendor(r.vendor)}</td>
        <td>${esc(r.date)}</td>
        <td><code>${esc(r.item_code)}</code></td>
        <td>${esc(r.description)}</td>
        <td class="currency">${fmt(r.quantity)}</td>
        <td class="currency">$${fmt(r.unit_price)}</td>
        <td class="currency">$${fmt(r.line_total)}</td>
      </tr>
    `).join('');
  }

  function renderByVendor(vendors) {
    const tbody = document.getElementById('tbody-by-vendor');
    if (!vendors.length) {
      tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;color:#8d8d8d;">No vendor data.</td></tr>';
      return;
    }
    tbody.innerHTML = vendors.map(r => `
      <tr>
        <td>${tagVendor(r.vendor)}</td>
        <td class="currency">${r.total_pos}</td>
        <td class="currency">$${fmt(r.total_spend)}</td>
      </tr>
    `).join('');
  }

  function renderByProduct(products) {
    const tbody = document.getElementById('tbody-by-product');
    if (!products.length) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#8d8d8d;">No product data.</td></tr>';
      return;
    }
    tbody.innerHTML = products.map(r => `
      <tr>
        <td><code>${esc(r.item_code)}</code></td>
        <td>${esc(r.description)}</td>
        <td class="currency">${fmt(r.total_quantity)}</td>
        <td class="currency">$${fmt(r.total_cost)}</td>
        <td>${(r.vendors || []).map(v => tagVendor(v)).join(' ')}</td>
      </tr>
    `).join('');
  }

  function setupExport(lineItems) {
    const btn = document.getElementById('export-csv-btn');
    const hint = document.getElementById('export-hint');
    if (!lineItems.length) {
      btn.disabled = true;
      return;
    }
    hint.textContent = `${lineItems.length} row(s) ready`;
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      btn.textContent = 'Exporting…';
      try {
        const resp = await fetch('/api/export/csv', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ line_items: lineItems }),
        });
        if (!resp.ok) throw new Error('Export failed');
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'purchase_orders.csv';
        a.click();
        URL.revokeObjectURL(url);
      } catch (err) {
        alert('CSV export failed: ' + err.message);
      } finally {
        btn.disabled = false;
        btn.textContent = '⬇ Export CSV';
      }
    });
  }
}
