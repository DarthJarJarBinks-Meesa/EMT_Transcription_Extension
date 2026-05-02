const el = {
  apiBase: document.getElementById("apiBase"),
  apiKey: document.getElementById("apiKey"),
  fileInput: document.getElementById("fileInput"),
  dropzone: document.getElementById("dropzone"),
  submitBtn: document.getElementById("submitBtn"),
  fileMeta: document.getElementById("fileMeta"),
  status: document.getElementById("status"),
  output: document.getElementById("output"),
  summary: document.getElementById("summary"),
};

let selectedFile = null;

const KEY_STORAGE = "epcr_ui_api_key";
const BASE_STORAGE = "epcr_ui_api_base";

function setStatus(msg, isError = false) {
  el.status.style.color = isError ? "#fb7185" : "#4ade80";
  el.status.textContent = msg;
}

function readPersistedSettings() {
  const savedBase = localStorage.getItem(BASE_STORAGE);
  const savedKey = localStorage.getItem(KEY_STORAGE);
  if (savedBase) el.apiBase.value = savedBase;
  if (savedKey) el.apiKey.value = savedKey;
}

function persistSettings() {
  localStorage.setItem(BASE_STORAGE, el.apiBase.value.trim());
  localStorage.setItem(KEY_STORAGE, el.apiKey.value);
}

function setFile(file) {
  selectedFile = file;
  if (!file) {
    el.submitBtn.disabled = true;
    el.fileMeta.textContent = "No file selected.";
    return;
  }
  const kb = (file.size / 1024).toFixed(1);
  el.fileMeta.textContent = `${file.name} (${kb} KB)`;
  el.submitBtn.disabled = false;
}

async function processAudio() {
  if (!selectedFile) return;
  persistSettings();

  const base = el.apiBase.value.trim().replace(/\/$/, "");
  const apiKey = el.apiKey.value.trim();
  if (!base || !apiKey) {
    setStatus("Provide API base URL and API key first.", true);
    return;
  }

  setStatus("Uploading audio and waiting for transcription...");
  el.submitBtn.disabled = true;

  const fd = new FormData();
  fd.append("file", selectedFile, selectedFile.name);

  try {
    const res = await fetch(`${base}/api/v1/process-audio`, {
      method: "POST",
      headers: { "X-API-Key": apiKey },
      body: fd,
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setStatus(`Request failed (${res.status}): ${data.detail || "Unknown error"}`, true);
      el.output.textContent = JSON.stringify(data, null, 2);
      return;
    }

    setStatus("Success. Structured ePCR generated.");
    el.output.textContent = JSON.stringify(data, null, 2);
    const summary = data?.epcr_data?.call_summary || data?.epcr_data?.narrative || "";
    if (summary) {
      el.summary.classList.remove("hidden");
      el.summary.textContent = summary;
    } else {
      el.summary.classList.add("hidden");
      el.summary.textContent = "";
    }
  } catch (err) {
    setStatus(`Network error: ${err.message}`, true);
  } finally {
    el.submitBtn.disabled = false;
  }
}

el.apiBase.addEventListener("change", persistSettings);
el.apiKey.addEventListener("change", persistSettings);
el.fileInput.addEventListener("change", (e) => setFile(e.target.files?.[0] || null));
el.submitBtn.addEventListener("click", processAudio);

["dragenter", "dragover"].forEach((ev) =>
  el.dropzone.addEventListener(ev, (e) => {
    e.preventDefault();
    el.dropzone.classList.add("dragover");
  }),
);
["dragleave", "drop"].forEach((ev) =>
  el.dropzone.addEventListener(ev, (e) => {
    e.preventDefault();
    el.dropzone.classList.remove("dragover");
  }),
);
el.dropzone.addEventListener("drop", (e) => {
  const file = e.dataTransfer?.files?.[0] || null;
  if (file) setFile(file);
});

readPersistedSettings();
